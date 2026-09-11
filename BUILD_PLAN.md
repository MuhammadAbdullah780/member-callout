# CrewLink Build Plan

Use this file as the implementation sequence. Finish and verify each phase before asking Cursor to begin the next one. `DESIGN.md` remains the architecture decision record; `PRD.md` is the functional contract.

## Ground rules

- Work in small, reviewable commits. Do not let Cursor replace existing frontend or backend scaffolds.
- Keep the required core ahead of polish, real push, deployment, or the nginx bonus.
- Use PostgreSQL for idempotency checks. SQLite is not an acceptable substitute for the core proof.
- Do not create Django migrations until the custom `User` model and `AUTH_USER_MODEL` are final.
- The default reviewer command must be `docker compose up --build` from the repository root.

---

## Phase 0 - Baseline and decisions

**Goal:** Ensure the existing frontend/backend scaffolds and root documents agree before adding features.

### Work

1. Read `DESIGN.md` and `PRD.md`.
2. Confirm the repository contains `frontend/`, `backend/`, `README.md`, `docker-compose.yml`, and `docker-compose-dev.yml`.
3. Inspect the Django project: installed apps, settings module, database configuration, and whether any migrations already exist.
4. Use these stable application boundaries:
   - `core` - `Local`
   - `accounts` - custom `User`
   - `callouts` - members, announcements, deliveries, tasks, APIs
5. Add/update `.gitignore` for `.env`, Python virtualenvs, `__pycache__`, Next.js `.next`, and local database/volume artifacts.

### Exit check

- No unplanned migrations exist for Django's default user model.
- `AUTH_USER_MODEL` can be set before the first project migration.
- Current changes are understood and committed.

---

## Phase 1 - Docker and local runtime

**Goal:** Run every required service locally using containers.

### Work

1. Create/finish `backend/Dockerfile`.
2. Create/finish `frontend/Dockerfile` without replacing the existing Next.js app.
3. Create `.env.example` with safe development values:
   - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
   - `REDIS_URL`
   - `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`
   - `CORS_ALLOWED_ORIGINS=http://localhost:3000`
   - optional AI provider key/model variables
4. Finish `docker-compose.yml` with these services:
   - `db` - PostgreSQL with a named volume and health check
   - `redis`
   - `backend` - Django API on port 8000
   - `worker` - Celery worker using the backend image
   - `frontend` - Next.js on port 3000
5. Use `docker-compose-dev.yml` only as an override for bind mounts and hot reload. The base file must remain runnable by itself.
6. Add backend health endpoint `GET /health/`.

### Exit check

```bash
docker compose up --build
curl http://localhost:8000/health/
```

- Frontend is reachable at `http://localhost:3000`.
- Backend health check returns a successful response.
- Backend connects to Postgres; worker connects to Redis.

### Commit

`chore: containerize frontend and backend development stack`

---

## Phase 2 - Data model and migrations

**Goal:** Make the database embody tenant isolation and idempotency.

### Work

1. Implement `Local` in `core`.
2. Implement custom `User` in `accounts`, extending `AbstractUser`, with `local` foreign key and `leadership`/`member` roles.
3. Set `AUTH_USER_MODEL` before running migrations.
4. Implement `Member`, `Announcement`, `Delivery`, `DeliveryEvent`, `NotificationAttempt`, and `OutboxEvent` in `callouts`.
5. Apply database-level rules:
   - `Delivery`: unique `(announcement_id, member_id)`.
   - Announcement send/idempotency: unique `(local_id, client_idempotency_key)` when a key is present.
   - Check/validation rules for allowed delivery and announcement states.
   - Tenant/local foreign keys and indexes required by `DESIGN.md`.
6. Register models in Django admin only as a development aid.
7. Create and apply migrations in Docker.

### Exit check

```bash
docker compose exec backend python manage.py makemigrations --check
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py check
```

- Schema includes both unique constraints.
- `python manage.py check` has no errors.

### Commit

`feat: add tenant-scoped callout data model`

---

## Phase 3 - Seed data and authentication

**Goal:** Give reviewers deterministic accounts and enough data to expose a careless query.

### Work

1. Add JWT authentication and CORS configuration for the Next.js client.
2. Implement `POST /api/auth/login/`.
3. Create a re-runnable management command such as `seed_callout_data`.
4. Seed:
   - Local 27 with approximately 2,000 members.
   - Local 58 with approximately 200 members.
   - 3-4 classifications; active, retired, and suspended states.
   - one leadership and one member account for each local.
   - one Local 27 announcement already sent with recipient delivery rows.
5. Make credentials and IDs deterministic or print them clearly after each seed run.

### Exit check

```bash
docker compose exec backend python manage.py seed_callout_data
curl -X POST http://localhost:8000/api/auth/login/ ...
```

- The seed command can run twice without duplicate fixtures or errors.
- Both Local 27 and Local 58 leader/member logins work.

### Commit

`feat: add test accounts and repeatable callout seed data`

---

## Phase 4 - Authorization boundary

**Goal:** Enforce Rule 1 before building business actions.

### Work

1. Add a centralized authenticated actor/permission layer.
2. Leadership-only endpoints must reject members with `403`.
3. Every queryset must be scoped by `request.user.local_id` before object retrieval.
4. Member delivery operations must additionally match the authenticated member/user.
5. Never trust a local ID, role, or member ID supplied by a browser as authority.
6. Add tests where Local 27 tries to fetch Local 58 announcements, stats, members, and deliveries.

### Exit check

- Local 27 leader cannot read Local 58 announcement/stats: `404` or `403` consistently.
- Local 27 member cannot acknowledge a Local 58 delivery.
- A member cannot create, approve, or send announcements.

### Commit

`feat: enforce local and role authorization boundaries`

---

## Phase 5 - Announcement draft and AI review flow

**Goal:** Implement safe message composition without allowing AI to send anything.

### Work

1. Implement leader-only draft creation endpoint.
2. Implement a provider adapter for AI cleanup with a short timeout and clear error response.
3. Input: messy text. Output: title, body, and push preview of 120 characters or fewer.
4. Store AI output as an editable draft; do not change the announcement to approved or sent.
5. Implement a separate leader-only approval endpoint that records approver and timestamp.
6. Reject Send for every non-approved draft.
7. If no AI key is configured, return a useful “AI unavailable” response while manual title/body creation still works.

### Exit check

- AI response, timeout, and provider error all leave the announcement unsent.
- Send before approval is rejected.
- Approval and send are visible in audit/event data.

### Commit

`feat: add reviewable AI announcement drafts`

---

## Phase 6 - Idempotent send and fan-out

**Goal:** Implement Rule 2 using the database, not UI state or process memory.

### Work

1. Implement leader-only send endpoint accepting an `Idempotency-Key` header.
2. In one transaction, record the send state and durable outbox event.
3. Return `202 Accepted` quickly; do not synchronously loop through every recipient in the HTTP request.
4. Implement Celery/outbox processing that:
   - selects active members in the leader's local;
   - optionally filters by classification;
   - inserts deliveries in batches;
   - uses conflict-safe insert/`get_or_create` backed by the unique database constraint;
   - records/logs a notification attempt for new deliveries.
5. Make task retries safe and observable.
6. Add tests for duplicate API requests, duplicate worker tasks, and concurrent worker attempts.

### Exit check

- Sending to a Local 27 classification produces exactly one delivery per eligible Local 27 member.
- Replaying the same `Idempotency-Key` produces no additional announcement or delivery rows.
- Re-running the fan-out task produces no duplicate deliveries.

### Commit

`feat: add idempotent announcement fan-out`

---

## Phase 7 - Member receipts and leadership statistics

**Goal:** Prove delivery state changes and leadership visibility.

### Work

1. Implement member inbox endpoint: `GET /api/me/deliveries/`.
2. Implement member-owned `read` and `acknowledge` endpoints.
3. Record `DeliveryEvent` audit rows and timestamps. Make state operations idempotent.
4. Implement leader-only announcement stats endpoint returning at least `sent`, `read`, and `acknowledged` counts.
5. Cache/project counts or use restrained frontend polling; never issue one database query per delivery from the browser.
6. Add tests proving receipt events update aggregate counts and cannot cross member/local boundaries.

### Exit check

- A seeded member reads then acknowledges a delivery.
- Local leader sees correct counts change.
- Repeating read/ack is safe.

### Commit

`feat: add member receipts and leadership callout status`

---

## Phase 8 - Leadership frontend

**Goal:** Deliver the required one-screen vertical slice.

### Work

1. Add a login flow using a seeded leadership account.
2. Build one leadership screen with:
   - messy source input and/or manual title/body;
   - AI improvement action and visible error state;
   - AI title/body/push-preview review;
   - local display locked to signed-in leader's local;
   - optional classification selector;
   - explicit approval control;
   - Send action;
   - sent/read/acknowledged status counts.
3. Poll the stats endpoint at a restrained interval or connect to a status stream.
4. Keep styling minimal; usability matters more than appearance.

### Exit check

- A leader can complete draft -> approve -> send in the browser.
- Counts visibly update after member API actions.
- Member UI is not required.

### Commit

`feat: add leadership announcement console`

---

## Phase 9 - Tests, README, and review readiness

**Goal:** Make the submission independently reviewable.

### Work

1. Run backend tests in Docker.
2. Add focused tests for Rule 1, Rule 2, approval gating, audience filtering, and receipt counts.
3. Write a short `README.md` with startup command, migration/seed command, and a `## TEST ACCOUNTS` heading exactly.
4. Under that heading, include a fenced JSON block with both logins per local, an existing Local 27 announcement ID, a Local 58 member ID, and endpoint/auth information.
5. Add curl examples for member read/acknowledge, cross-local denial, and idempotent retry.
6. Add `AI_CONVERSATION_CODEX.md` and `AI_CONVERSATION_CLAUDE.md` at the repository root. Add native exports too if available.
7. Add scope cuts at the bottom of `DESIGN.md` if they changed.
8. Test a fresh setup using only the README.

### Exit check

```bash
docker compose up --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_callout_data
docker compose exec backend python manage.py test
```

- A reviewer can follow the README without asking for IDs or credentials.
- Required curl proofs succeed.

### Commit

`docs: prepare reviewer setup and verification guide`

---

## Phase 10 - Optional bonus only

**Goal:** Demonstrate Rule 2 across backend processes.

Only start this phase after all Phase 9 checks pass.

### Work

1. Add `nginx/` configuration.
2. Run two backend API instances behind nginx or HAProxy with round-robin routing.
3. Send/retry through the load balancer.
4. Prove the same database constraints prevent duplicate deliveries across instances.
5. Document the command and proof in the README.

### Exit check

- Requests can reach either backend instance.
- Retried send still leaves one `(announcement_id, member_id)` delivery row per eligible member.

---

## Final submission checklist

- [ ] One accessible GitHub repository with normal commit history.
- [ ] `DESIGN.md` at root, including requirements, four design answers, diagram, and scope cuts.
- [ ] `PRD.md` and `BUILD_PLAN.md` at root as implementation context.
- [ ] Working backend and leadership frontend.
- [ ] `docker compose up --build` works.
- [ ] Re-runnable seed data and exact README test-account block.
- [ ] Tests/curl proofs demonstrate Rule 1 and Rule 2.
- [ ] AI conversations included at root.
- [ ] Nginx bonus attempted only if core is solid.
