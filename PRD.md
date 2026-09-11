# CrewLink Member Callout - Product Requirements

## 1. Purpose

Build a small, runnable demonstration of CrewLink's callout workflow. A leader sends an approved announcement to active members of only their own union local, optionally filtered by classification. The system creates one durable delivery record per recipient, supports member read and acknowledgement actions, and shows the leader live sent/read/acknowledged counts.

`DESIGN.md` is the architectural authority. This document turns that design into the narrow Part B implementation scope.

## 2. Goals and success criteria

The completed application must prove:

1. A local leader can draft, AI-clean, approve, and send an announcement to their own local or one classification.
2. Sending produces one `Delivery` row per eligible member.
3. A member can read and acknowledge only their own delivery.
4. A leader sees sent, read, and acknowledged counts for an announcement in their own local.
5. A Local 27 account cannot read or act on Local 58 data, even when it supplies another local's or member's ID.
6. Retrying the same send or running the same fan-out work twice cannot create duplicate `(announcement, member)` deliveries.
7. A reviewer can run the stack and verify the above in ten minutes using `README.md`.

## 3. Scope

### In scope

- Leader and member authentication with a local-scoped role.
- Two seeded locals, classifications, active/retired/suspended members, and test accounts.
- Leadership announcement form: title/body or messy source text, local/classification selector, AI draft preview, explicit approval, and Send.
- Backend announcement creation, approval, idempotent send, per-member delivery creation, notification-attempt logging, status counts, read, and acknowledge endpoints.
- A real AI-provider adapter with short timeout/error handling. Generated copy remains a draft; failed generation never blocks manually authored copy or sends anything.
- A small leadership-only Next.js screen that updates aggregate counts without reloading the page.
- Docker Compose, migrations, re-runnable seed data, focused tests, and reviewer documentation.

### Deliberately out of scope

- Real FCM/APNs credentials, SMS/email, device-token management, and mobile app UI. Notification attempts are stored/logged.
- RSVP endpoint/UI. The model may retain the field because it is in the design.
- Reminder workflows, scheduling, cancellation, editing an already-sent announcement, attachments, analytics, and cross-local administration.
- Production deployment, horizontal auto-scaling, and the two-instance/nginx bonus until the core acceptance checks pass.

## 4. Technical shape

```text
frontend/        Next.js leadership UI
backend/         Django project, DRF API, Celery worker, migrations, seed command, tests
docker-compose.yml
docker-compose-dev.yml  optional developer override
README.md
DESIGN.md
PRD.md
```

The production-like local stack is Next.js, Django + DRF, PostgreSQL, Redis, and a Celery worker. `docker-compose.yml` must be the simple default path for reviewers. The frontend talks only to the API; it never directly accesses PostgreSQL. The backend owns authentication, tenant scope, role checks, fan-out, and all state transitions.

## 5. Backend requirements

### Core models

- `Local`, `Member`, `User`, `Announcement`, `Delivery`, `DeliveryEvent`, `NotificationAttempt`, and `OutboxEvent` or an equivalent durable task model.
- Every tenant-owned record has `local_id`.
- `Delivery` has database uniqueness on `(announcement_id, member_id)`.
- The send command accepts an idempotency key and uses a unique local-scoped key so a retried client request resolves to the original announcement/send.

### Authorization rules

- Tokens/sessions identify the user, role, and local server-side. Never trust browser-provided role or local identifiers.
- Only leadership may create, generate AI drafts, approve, send, or view announcement aggregates.
- Leaders may only target/read their own local. Members may only read and acknowledge deliveries belonging to themselves.
- All querysets are tenant-scoped before an object lookup. Add tests for Local 27 attempts to access Local 58.

### Endpoints

Exact paths may vary, but the README must publish them.

- `POST /api/auth/login/` - receive credentials and return authentication token/session.
- `POST /api/announcements/` - leader creates a draft.
- `POST /api/announcements/{id}/ai-draft/` - leader submits messy text; returns title, body, and <=120-character push preview, or a clear provider error/timeout response.
- `POST /api/announcements/{id}/approve/` - records explicit approval of displayed content.
- `POST /api/announcements/{id}/send/` - leader sends with an `Idempotency-Key`; returns `202` and an announcement ID/status.
- `GET /api/announcements/{id}/stats/` - leader receives sent/read/acknowledged totals for their own local.
- `GET /api/me/deliveries/` - member inbox (useful for curl verification).
- `POST /api/deliveries/{id}/read/` and `POST /api/deliveries/{id}/acknowledge/` - member-owned state changes.

The worker owns recipient expansion and notification logging. In the seed-scale build, count updates may be exposed by a small aggregate endpoint polled at a restrained interval or by SSE; avoid a browser query per row or per second.

## 6. Frontend requirements

Build exactly one leadership page. It must provide:

1. Login as a seeded leader.
2. Message input: either title/body or messy source text.
3. “Improve with AI” action that visibly returns a reviewable title, body, and push preview; timeout/error is understandable and leaves editing available.
4. Audience selection limited to the signed-in leader's local, with an optional classification filter.
5. An explicit approval action before Send is enabled.
6. Send feedback and a status area showing sent, read, and acknowledged totals.

Plain HTML/form styling is sufficient. Do not build member-facing pages unless the core slice is complete.

## 7. Seed and verification data

Create a re-runnable Django management command that creates:

- Local 27 with approximately 2,000 members;
- Local 58 with approximately 200 members;
- 3-4 classifications and active/retired/suspended member states;
- one leader and one member account per local;
- one previously sent Local 27 announcement with its delivery rows.

The seed output or deterministic fixtures must provide the IDs needed by the README's exact `## TEST ACCOUNTS` JSON block.

## 8. Required automated checks

- Leader fan-out creates one row for every eligible member and honors classification/status.
- Replaying a send with the same idempotency key creates no second announcement or recipient rows.
- Re-running fan-out, including concurrent calls, creates no duplicate delivery rows.
- Local 27 leader cannot fetch a Local 58 announcement or stats.
- Local 27 member cannot read/acknowledge Local 58 member delivery.
- Member read then acknowledge transitions update the announcement statistics.
- AI output stays draft-only; send rejects an unapproved draft.

## 9. Delivery checklist

- `DESIGN.md` and this `PRD.md` at repository root.
- `README.md` with startup steps, curl examples, and the exact `## TEST ACCOUNTS` heading plus a fenced JSON block.
- `docker compose up` starts all required services, or README states the one additional command needed.
- Normal, incremental git commits.
- Exported AI conversation files included at the repository root or an `ai-conversations/` directory.

