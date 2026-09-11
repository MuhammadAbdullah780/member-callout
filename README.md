# CrewLink Member Callout

A union local sends an approved announcement to its active members; the system
creates one durable delivery record per member and tracks read/acknowledge
state independently. See `DESIGN.md` for the architecture and `PRD.md` for the
implementation contract.

## Run it

```bash
cp .env.example .env
docker compose up --build -d
until curl -sf http://localhost:8000/health/ >/dev/null; do sleep 2; done
docker compose exec backend python manage.py seed_callout_data
```

The `until` loop matters: `up -d` returns once containers have *started*, but
the backend still has to run `migrate` before any `manage.py` command works.
This starts Postgres, Redis, the Django API (`:8000`), a Celery worker, and the
Next.js leadership console (`:3000`).

Seeding is safe to re-run. Run the backend test suite (22 tests):

```bash
docker compose exec backend python manage.py test
```

For local development with hot reload instead of production builds:

```bash
docker compose -f docker-compose.yml -f docker-compose-dev.yml up --build
```

### Optional: the AI draft feature

Set `AI_PROVIDER_API_KEY` in `.env` to an [OpenRouter](https://openrouter.ai/keys)
key. `AI_PROVIDER_MODEL` is a comma-separated preference order tried left to
right, so a rate-limited free model falls through to the next one. Without a
key the endpoint returns a clean `502` and manual title/body entry still works.

## TEST ACCOUNTS

```json
{
  "auth": "POST /api/auth/login/ returns {access, refresh}; send access as 'Authorization: Bearer <access>'",
  "local_27": {
    "note": "larger local, 2001 members",
    "leader": { "username": "leader27", "password": "crewlink-dev-2026" },
    "member": { "username": "member27", "password": "crewlink-dev-2026", "member_id": 2201 },
    "sent_announcement_id": 1,
    "member27_delivery_id": 1601
  },
  "local_58": {
    "note": "smaller local, 201 members",
    "leader": { "username": "leader58", "password": "crewlink-dev-2026" },
    "member": { "username": "member58", "password": "crewlink-dev-2026", "member_id": 2202 }
  },
  "endpoints": [
    { "method": "POST", "path": "/api/auth/login/",                    "auth": "none",       "purpose": "exchange username/password for a JWT pair" },
    { "method": "POST", "path": "/api/auth/refresh/",                  "auth": "refresh JWT","purpose": "rotate an access token" },
    { "method": "POST", "path": "/api/announcements/",                 "auth": "leader JWT", "purpose": "create a draft announcement" },
    { "method": "POST", "path": "/api/announcements/{id}/ai-draft/",   "auth": "leader JWT", "purpose": "AI-clean messy text; draft status only" },
    { "method": "POST", "path": "/api/announcements/{id}/approve/",    "auth": "leader JWT", "purpose": "approve the displayed draft" },
    { "method": "POST", "path": "/api/announcements/{id}/send/",       "auth": "leader JWT", "purpose": "send; requires Idempotency-Key header" },
    { "method": "GET",  "path": "/api/announcements/{id}/stats/",      "auth": "leader JWT", "purpose": "sent/read/acknowledged counts" },
    { "method": "GET",  "path": "/api/me/deliveries/",                 "auth": "member JWT", "purpose": "the caller's own delivery inbox" },
    { "method": "POST", "path": "/api/deliveries/{id}/read/",          "auth": "member JWT", "purpose": "mark own delivery read" },
    { "method": "POST", "path": "/api/deliveries/{id}/acknowledge/",   "auth": "member JWT", "purpose": "acknowledge own delivery" },
    { "method": "GET",  "path": "/health/",                            "auth": "none",       "purpose": "liveness check" }
  ]
}
```

Leadership endpoints operate only on the caller's own local; member endpoints
operate only on the caller's own deliveries. Both are enforced server-side from
the JWT, never from request parameters — which is why the leadership screen has
no "pick a local" control: the local is derived from the token, not chosen by
the client.

## Curl walkthrough

Log in and capture tokens:

```bash
L27=$(curl -s -X POST http://localhost:8000/api/auth/login/ -H "Content-Type: application/json" \
  -d '{"username":"leader27","password":"crewlink-dev-2026"}' | grep -o '"access":"[^"]*"' | cut -d'"' -f4)
L58=$(curl -s -X POST http://localhost:8000/api/auth/login/ -H "Content-Type: application/json" \
  -d '{"username":"leader58","password":"crewlink-dev-2026"}' | grep -o '"access":"[^"]*"' | cut -d'"' -f4)
M27=$(curl -s -X POST http://localhost:8000/api/auth/login/ -H "Content-Type: application/json" \
  -d '{"username":"member27","password":"crewlink-dev-2026"}' | grep -o '"access":"[^"]*"' | cut -d'"' -f4)
```

**Member read/acknowledge** — the member acts on their own delivery from the
seeded sent announcement, and leadership's counters move:

```bash
curl -s http://localhost:8000/api/me/deliveries/ -H "Authorization: Bearer $M27"
curl -X POST http://localhost:8000/api/deliveries/1601/read/        -H "Authorization: Bearer $M27"
curl -X POST http://localhost:8000/api/deliveries/1601/acknowledge/ -H "Authorization: Bearer $M27"
curl -s http://localhost:8000/api/announcements/1/stats/ -H "Authorization: Bearer $L27"
# {"sent":1601,"read":0,...} -> {"sent":1601,"read":1,"acknowledged":1}
```

**Rule 1, cross-local denial** — Local 58's leader cannot read Local 27's
announcement, even knowing its id. 404, not another local's counts:

```bash
curl -i http://localhost:8000/api/announcements/1/stats/ -H "Authorization: Bearer $L58"   # 404
curl -i -X POST http://localhost:8000/api/announcements/ -H "Authorization: Bearer $M27" \
  -H "Content-Type: application/json" -d '{"title":"x","body":"y"}'                        # 403, member != leader
curl -i http://localhost:8000/api/announcements/1/stats/                                   # 401, no token
```

**Rule 2, idempotent send** — create, approve, send, then replay the same key:

```bash
ANN=$(curl -s -X POST http://localhost:8000/api/announcements/ -H "Authorization: Bearer $L27" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","body":"Body","audience_classification":"","needs_ack":true}' \
  | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

curl -X POST http://localhost:8000/api/announcements/$ANN/approve/ -H "Authorization: Bearer $L27"
curl -X POST http://localhost:8000/api/announcements/$ANN/send/ -H "Authorization: Bearer $L27" -H "Idempotency-Key: demo-key-1"
curl -X POST http://localhost:8000/api/announcements/$ANN/send/ -H "Authorization: Bearer $L27" -H "Idempotency-Key: demo-key-1"
```

Fan-out is asynchronous, so counts climb for a few seconds after `202` and then
settle — a 1601-member send takes roughly 8s. Poll until the number stops
moving before judging it:

```bash
curl -s http://localhost:8000/api/announcements/$ANN/stats/ -H "Authorization: Bearer $L27"
```

Rule 2 is also proved automatically: `IdempotencyTests` in
`backend/callouts/tests.py` replays the send request and independently re-runs
the fan-out task, then asserts the delivery count and the
`(announcement_id, member_id)` pairs are unchanged either way.

## What was cut

See "Scope cut and next steps" at the bottom of `DESIGN.md`.
