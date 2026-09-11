# Codex Conversation Record - CrewLink Member Callout

**Date:** 2026-09-11  
**Tool:** Codex  
**Purpose:** Project-focused record of the architecture, requirements, and implementation-planning conversation used to develop this submission.

> Note: This is a faithful project-focused record prepared for the exercise. It omits platform system instructions, tool output, and unrelated conversation context. If a native full-chat export is available at submission time, include it alongside this file.

---

## 1. Initial problem framing

**User:** Described CrewLink as a mass-notification system for labour unions. Leadership needs to announce an emergency meeting to a local with up to 22,400 members. The system must create an individual delivery record for each member, track delivery/read/acknowledgement/attendance states, and work when members are offline for hours or days. The user highlighted duplicate sends, strict local/role privacy, and AI-assisted message cleanup requiring human review.

**Codex:** Confirmed the core system model:

- A leader creates an announcement for an authorized local and audience.
- Sending expands the audience into one durable per-member delivery record.
- Receipt state is tracked per person and aggregated for leadership.
- Push is only an alert; a durable member inbox is the source of truth for offline users.
- Tenant isolation and idempotent fan-out are the two principal architectural constraints.

Codex identified the key idempotency invariant as a unique delivery record for each `(announcement_id, member_id)` pair.

## 2. Senior-architecture approach

**User:** Asked how a senior architect would solve the problem.

**Codex:** Proposed beginning with non-negotiable invariants rather than screens or infrastructure:

1. Local/tenant isolation and role-based authorization.
2. Exactly one logical recipient record per announcement/member.
3. Durable, asynchronous fan-out rather than looping through 22,400 recipients inside one HTTP request.
4. Offline-safe inbox synchronization, with push treated as best effort.
5. Human approval before AI-generated material may be sent.

## 3. Architecture discussion

**User:** Asked for the architecture and an explanation.

**Codex:** Described a system containing:

- leadership web application;
- member mobile/inbox client;
- authenticated API service;
- relational database for locals, members, announcements, deliveries, receipt events, and audits;
- durable queue and background workers for audience expansion and notifications;
- push provider as a non-authoritative alert channel;
- metrics, audit, and dead-letter monitoring.

The proposed send path was:

1. Leadership drafts and explicitly approves a message.
2. The API stores the send state and transactional outbox event atomically.
3. A worker expands the audience in batches.
4. The worker inserts one delivery record per member with a database uniqueness constraint.
5. Notification attempts are queued/logged and retried safely.
6. The member app synchronizes its inbox when it reconnects.
7. Member read/acknowledge/RSVP events update the delivery row and leadership counts.

Codex made an important distinction: no design can guarantee that a phone visually displays a push alert exactly once. The practical guarantee is exactly one **logical delivery/inbox item and receipt record** per member/announcement. If an underlying push provider duplicates an alert, the client deduplicates by delivery ID.

## 4. Interpretation of the technical exercise

**User:** Asked what the exercise expected.

**Codex:** Explained that the brief prioritizes architecture and reasoning over a fully featured product. Expected evidence includes:

- a design document explaining data model, send workflow, authorization, idempotency, and failure handling;
- a thin, working vertical slice with leader send flow, per-recipient records, member read/acknowledge, and status counts;
- demonstrable enforcement of local/role boundaries and retry-safe fan-out;
- a human-in-the-loop AI draft flow;
- tests or curl evidence for cross-local denial and no duplicate deliveries;
- clear tradeoff and scope-cut discussion.

## 5. Assignment brief reviewed

**User:** Supplied `Member-Callout-Exercise.pdf` and asked for the actual requirements.

**Codex:** Reviewed the full brief and confirmed these explicit deliverables:

- One accessible GitHub repository, submitted by email.
- `DESIGN.md` at repository root, with Part 0 requirements and Part A design answers. The four Part A answers are capped at 1,500 words and require a diagram including a load balancer and instances.
- Part B backend plus one small leadership screen.
- Preferred stack: Django + DRF + PostgreSQL. Next.js or Flutter for the frontend.
- Re-runnable seed data with approximately 2,000 members in one local, 200 in another, classifications, leader/member test accounts, and an already-sent announcement.
- Short `README.md` with the exact `## TEST ACCOUNTS` heading and a fenced JSON block.
- Curl/test proof of member read/ack, local isolation, and retry-safe send behavior.
- Exported AI conversations at the repository root.

Codex also identified the hidden security concern in Denise's message: the apprentice contact-information question may describe an existing cross-local data exposure and should be treated as a potential security incident, not a deferred feature.

## 6. Review of parallel Claude notes

**User:** Added a pasted Claude conversation and asked Codex to synchronize with it.

**Codex:** Compared Claude's notes against the assignment PDF and found them aligned. The agreed priority order was:

1. Write Part 0 requirements.
2. Decide the delivery/recipient model and local-scoped leadership model.
3. Design idempotent send/fan-out.
4. Describe Rule 1 enforcement and production detection.
5. Add the load-balancer diagram.
6. Build the vertical slice.
7. Finish README, test accounts, scope cuts, and conversation exports.
8. Attempt two-instance/nginx bonus only after the core passes.

## 7. Documents created for the project

**User:** Asked to begin with `DESIGN.md`, then requested a separate PRD to guide implementation in Cursor.

**Codex:** Created these repository-root documents:

- `DESIGN.md` - requirements, assumptions, risk flag, questions, data model, send path, authorization/idempotency design, monitoring, Mermaid architecture diagram, and scope cuts. The Part A content is below the 1,500-word limit.
- `PRD.md` - implementation contract for Cursor: scope, success criteria, technical shape, API requirements, frontend requirements, seed requirements, automated checks, and delivery checklist.

## 8. Agreed implementation scope

The project will use this layout:

```text
/
├── DESIGN.md
├── PRD.md
├── README.md
├── docker-compose.yml
├── frontend/               # Next.js leadership screen
└── backend/                # Django + DRF + PostgreSQL + worker
```

`docker-compose-dev.yml` may be added for local development convenience, but it is not required by the exercise. A root `nginx/` directory is also optional: it is only needed for the two-backend-instance load-balancer bonus and should be deferred until the core slice is complete.

The initial implementation will deliberately exclude real push credentials, member UI, RSVP UI, styling work, production hosting, and nginx bonus work. The core proof is correct authorization and database-enforced idempotency.

## 9. Planned build order

1. Scaffold Django/DRF/PostgreSQL and Next.js.
2. Implement models, migrations, and repeatable seed command.
3. Implement local-scoped authentication/authorization and isolation tests.
4. Implement draft, AI cleanup, explicit approval, idempotent send, and per-member delivery fan-out.
5. Implement member read/acknowledge APIs and status aggregation.
6. Build the single leadership page.
7. Add Docker Compose, README, test accounts, curl examples, and automated verification.
8. Add the optional multi-instance/nginx configuration only if time remains.

