# CrewLink Member Callout

A union local sends an approved announcement to its active members; the system
creates one durable delivery record per member and tracks read/acknowledge
state independently. See `DESIGN.md` for the architecture and `PRD.md` for the
implementation contract.

## Run it

```bash
cp .env.example .env
docker compose up --build
```

This starts Postgres, Redis, the Django API (`:8000`), a Celery worker, and
the Next.js leadership console (`:3000`). The `backend` service runs
migrations and `collectstatic` on startup.

Seed deterministic test data (safe to re-run):

```bash
docker compose exec backend python manage.py seed_callout_data
```

Run the backend test suite:

```bash
docker compose exec backend python manage.py test
```

For local development with hot reload instead of production builds:

```bash
docker compose -f docker-compose.yml -f docker-compose-dev.yml up --build
```

## API endpoints

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| POST | `/api/auth/login/` | anyone | exchange username/password for a JWT pair |
| POST | `/api/auth/refresh/` | anyone with a refresh token | rotate an access token |
| POST | `/api/announcements/` | leadership | create a draft announcement |
| POST | `/api/announcements/{id}/ai-draft/` | leadership | AI-clean messy text into title/body/push preview |
| POST | `/api/announcements/{id}/approve/` | leadership | approve the displayed draft |
| POST | `/api/announcements/{id}/send/` | leadership | send (requires `Idempotency-Key` header) |
| GET | `/api/announcements/{id}/stats/` | leadership | sent/read/acknowledged counts |
| GET | `/api/me/deliveries/` | member | the caller's own delivery inbox |
| POST | `/api/deliveries/{id}/read/` | member | mark own delivery read |
| POST | `/api/deliveries/{id}/acknowledge/` | member | acknowledge own delivery |
| GET | `/health/` | anyone | liveness check |

Leadership endpoints operate only on the caller's own local; member endpoints
operate only on the caller's own deliveries. Both are enforced server-side
from the JWT, never from request parameters.

## TEST ACCOUNTS

```json
{
  "local_27": {
    "leader": { "username": "leader27", "password": "crewlink-dev-2026" },
    "member": { "username": "member27", "password": "crewlink-dev-2026", "member_id": 2201 },
    "sent_announcement_id": 1
  },
  "local_58": {
    "leader": { "username": "leader58", "password": "crewlink-dev-2026" },
    "member": { "username": "member58", "password": "crewlink-dev-2026", "member_id": 2202 }
  }
}
```

## Curl walkthrough

Log in as the Local 27 leader and capture the access token:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"leader27","password":"crewlink-dev-2026"}' \
  | grep -o '"access":"[^"]*"' | cut -d'"' -f4)
```

**Member read/acknowledge** — log in as the Local 27 member and act on their
own delivery from the seeded sent announcement:

```bash
MEMBER_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"member27","password":"crewlink-dev-2026"}' \
  | grep -o '"access":"[^"]*"' | cut -d'"' -f4)

curl -X POST http://localhost:8000/api/deliveries/1601/read/ \
  -H "Authorization: Bearer $MEMBER_TOKEN"

curl -X POST http://localhost:8000/api/deliveries/1601/acknowledge/ \
  -H "Authorization: Bearer $MEMBER_TOKEN"
```

**Cross-local denial** — the Local 27 leader cannot read Local 58's data, even
by guessing an ID. Find a real Local 58 announcement id, then confirm it 404s
for the Local 27 leader:

```bash
LOCAL58_ANN=$(docker compose exec -T backend python manage.py shell -c "
from callouts.models import Announcement
print(Announcement.objects.filter(local__name='Local 58').first().id)
" | tail -1)

curl -i http://localhost:8000/api/announcements/$LOCAL58_ANN/stats/ \
  -H "Authorization: Bearer $TOKEN"
# -> 404, not another local's counts
```

**Idempotent send** — create, approve, and send an announcement, then replay
the same `Idempotency-Key`:

```bash
ANN_ID=$(curl -s -X POST http://localhost:8000/api/announcements/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Test","body":"Body","audience_classification":"","needs_ack":true}' \
  | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

curl -X POST http://localhost:8000/api/announcements/$ANN_ID/approve/ \
  -H "Authorization: Bearer $TOKEN"

curl -X POST http://localhost:8000/api/announcements/$ANN_ID/send/ \
  -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: demo-key-1"

# Replay - same key, no second send or duplicate deliveries:
curl -X POST http://localhost:8000/api/announcements/$ANN_ID/send/ \
  -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: demo-key-1"
```

Rule 2 is also proved automatically: `IdempotencyTests` in
`backend/callouts/tests.py` replays the send request and independently
re-runs the fan-out task, then asserts the delivery count and the
`(announcement_id, member_id)` pairs are unchanged either way.

## What was cut

See "Scope cut and next steps" at the bottom of `DESIGN.md`. In summary: no
real push credentials (notifications are logged), no member-facing UI beyond
the read/acknowledge API, and RSVP is designed but not implemented.
