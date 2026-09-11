# AI conversation record — Claude

**Tool:** Claude (Anthropic)
**Exercise:** Avialdo Solutions · Software Engineer · Member Callout
**Scope of this file:** a project-focused record of the working conversation for this exercise.

This is a condensed record of the conversation, not a raw transcript. It excludes system prompts,
tool output, and unrelated chat. Nothing here is invented: where the conversation reached a
direction but not a finished decision, that is stated explicitly rather than written up as if it
were settled.

**Status at time of writing:** Part 0 requirements drafted. Part A design prompts, the Part B
build, and the README are not yet started.

---

## 1. Understanding the problem

The exercise supplies a deliberately messy Slack message from Denise Okafor, business manager of
the fictional Local 27, rather than a spec. The message complains that callouts are missing
people, asks for a way to know who is attending before she leaves the hall, and raises — almost as
an aside — whether members outside the local can see the wireman apprentices' contact info.

The system underneath that ask is a mass-notification tool for labour unions, with receipts.
Leadership composes one announcement and targets a local; the system produces an individual
delivery record per member and tracks each independently, so leadership can watch sent, read and
acknowledged counts move.

The numbers that shape the design:

| Figure | Value |
| --- | --- |
| Locals on the platform | 43 |
| Members total | 187,000 |
| Largest local (single callout audience) | 22,400 |
| Push notifications that fail silently | 5–10% |
| Typical member offline window | Hours, sometimes days |

The offline window is the important one. Members work in basements, elevator shafts, underground
transit and rural highway. A phone off the network for a day is normal, not an edge case, so a
callout has to be a durable item waiting for the member rather than a push that either lands or is
lost. Push is a nudge; it is not the delivery mechanism.

### The two rules

**Rule 1 — isolation.** Nobody sees or touches data outside their own access. Two boundaries: one
local's data must never reach another local, and a member must never act with leadership
permissions. Union membership is sensitive enough that a leak can cost someone their job. The
brief specifically asks what happens when someone adds a new endpoint next year and forgets about
the rule.

**Rule 2 — no double delivery.** A retry or a process restart must not deliver twice to the same
member. Leadership will retry a send that looks stuck, and a crashed process will restart
mid-send. The brief rules out "we disable the button" as an answer and asks what in the *system*
makes the same member unreachable twice. The optional DevOps bonus sharpens this: an in-memory
"have we already sent this?" check stops working the moment a second process exists behind a load
balancer.

---

## 2. Interpretation of the deliverables

One GitHub repository, submitted by email, with normal commit history. Inside it:

1. **`DESIGN.md`** at the repo root — Part 0 requirements, then the four Part A design prompts
   (data model; send path; the two rules by design; a diagram), capped at 1,500 words for the four
   prompts. Plus a note at the bottom on what was cut. This is the main deliverable.
2. **Part B code** — Django + DRF + Postgres backend, and one leadership screen in Next.js.
3. **A re-runnable seed script** — two locals (~2,000 and 200 members), 3–4 classifications, one
   leadership and one member login per local, plus one already-sent announcement in the larger
   local with its recipient rows.
4. **`README`**, 15–20 lines — how to run, the logins, curl examples for member read/ack, a curl
   example showing a Local 27 login cannot read another local's data, and how Rule 2 was verified.
   Must contain a `## TEST ACCOUNTS` section with that exact heading and a fenced JSON block.
5. **Exported AI chat sessions** at the repo root — this file is part of that.

Reading notes that affected planning:

- The weighting is explicit: Part 0 and Part A carry the most weight, and the brief warns against
  letting the build crowd out design time.
- Unstyled frontend is explicitly acceptable. A member-facing UI is not required. Real push
  notifications are not required — logging them or writing them to a table is enough.
- The starter schema supplies `locals`, `members` and `announcements`, and pointedly omits the
  recipient/status table and the leadership-vs-member distinction. Those omissions are the
  decisions being assessed.
- The reviewers will run requests against the running API themselves using the `TEST ACCOUNTS`
  block, so that section is functional, not decorative.
- The AI feature is assessed on integration, not prompt quality: what happens when the provider is
  slow or down, and whether generated text can reach 22,400 members without a human approving it.
- RSVP is Part A design only and is not required in the build.

---

## 3. Stack decisions

| Decision | Choice | Reason |
| --- | --- | --- |
| Backend | Django + DRF + Postgres | The brief's stated preference; what the reviewers read fastest |
| Frontend | Next.js | Same slice and same scoring as Flutter; chosen on familiarity |
| Time budget | Full ~5.5 hours | Leaves room to attempt the DevOps bonus |

---

## 4. Part 0 — requirements, assumptions, concerns, questions

Drafted in conversation. The substance below is what was agreed; the wording in `DESIGN.md` may
differ.

### Restatement

Leadership composes one announcement, targets a local (optionally narrowed by classification), and
sends. The system creates an individual delivery record for every member in that audience and
tracks each independently: delivered, read, acknowledged, RSVP. Leadership sees live counts on a
status screen so that before leaving the hall, Denise can see who has confirmed. Because members
are routinely offline, the callout waits durably for the member.

### Assumptions

- **Audience** is every member of one local with status `active`. Retired and suspended members are
  excluded by default.
- **"Immediately"** means the send request returns in under a second with the send *accepted*.
  Fan-out to 22,400 members happens in the background and completes within a few minutes. Delivery
  is guaranteed eventually, not instantly.
- **Acknowledgment is optional per announcement**, controlled by the existing `needs_ack` flag.
  RSVP is a separate axis: acknowledging means "I saw this," RSVP means "here is my answer."
- **Done** means every active member in the audience has a recipient record in a terminal state —
  delivered or failed — and no member has more than one, regardless of retries or restarts.
- **Leadership** is a role held per local, with authority only over that local. No cross-local or
  platform-wide role exists in this slice.

The third assumption was flagged in conversation as a genuine judgment call rather than an obvious
one. It is arguable that for meeting callouts the RSVP *is* the acknowledgment, since Denise's
underlying need is a headcount. The two-axis model was kept, but the alternative was noted as
worth deciding deliberately rather than by default.

### Concern raised

The contact-info line is the thing the brief hints is worth flagging. It is not a feature request.
"Can members outside our local see the wireman apprentices' contact info?" describes a possible
active cross-tenant data exposure, reported second-hand from an onboarding conversation and buried
at the end of a Slack message. Given the stated consequence — members can lose their jobs — it
should be verified against production immediately and triaged as a security incident if confirmed,
before any new code ships. It doubles as the first concrete test of Rule 1: a query against live
data confirming whether member records have ever been readable across local boundaries, and audit
logs showing whether it actually happened.

Two smaller flags:

- There is no real deadline. "Before the next round of contract talks, whenever that ends up being
  scheduled" is an open date, so the work is scoped to a shippable slice rather than to a date.
- The complaint conflates two different failures — members who received nothing, and members who
  received something too late. Different causes, different fixes. Both assumed in scope.

### Questions for Denise, and what was assumed instead

1. *When acknowledgment is on, do you need to chase the people who haven't acknowledged, or is the
   count enough?* — **Assumed:** the count is enough for now, but the data model records enough to
   add chasing later without a migration.
2. *Should retired or suspended members receive callouts?* — **Assumed:** no, active only. Sending
   meeting notices to suspended members has consequences that can't be judged from the brief.
3. *Who besides you can send to the whole local?* — **Assumed:** a single leadership role scoped to
   one local, with no approval chain above it.

---

## 5. Data model — direction agreed, detail still open

Not yet designed. The direction established in conversation:

- The core modelling idea is that a send is **not** one message addressed to a group. It is N
  individual recipient rows, one per member — 22,400 for the largest local. That per-recipient row
  is what makes independent status tracking, resumable sends and idempotency possible at all.
- Each recipient row carries that member's own state: nothing yet, delivered, read, acknowledged,
  and separately their RSVP.
- The recipient table and the leadership-vs-member distinction are the two things the starter
  schema deliberately leaves out, so they are the two things most worth getting right.

Still to decide: exact fields and state representation (status enum versus timestamp columns),
where RSVP lives relative to acknowledgment, and how the leadership role is represented.

---

## 6. Idempotency (Rule 2) — direction agreed, mechanism still open

Not yet designed. What was established:

- The failure mode is concrete. Sending to 22,400 people takes minutes. Denise clicks Send, the
  screen appears stuck, she clicks again. Or the process crashes at member 14,000 and restarts.
  Naive code double-sends in both cases.
- The system must be able to answer "have I already handled this member for this announcement?"
  in a way that survives both a retry and a restart.
- Any check held in one process's memory is disqualified. The DevOps bonus exists to expose
  exactly that: it stops working the moment there is a second instance behind the load balancer.
  The brief states this will be raised in the interview whether or not the compose file is built,
  so it is worth reasoning through regardless.

Still to decide: the specific mechanism, and how it is demonstrated — a test, or a curl sequence
showing a retried send does not double-deliver.

---

## 7. Isolation (Rule 1) — direction agreed, mechanism still open

Not yet designed. What was established:

- Two distinct boundaries to enforce: between locals, and between a member and leadership.
- The brief's "someone adds a new endpoint next year and forgets" framing means per-view manual
  checks are the wrong answer. The enforcement needs to be a default-deny layer, so that a
  forgotten endpoint fails closed rather than open.
- A third requirement is separate from enforcement: how you would find out **in production** that
  either rule had already been broken. That is a detection and audit question, not an access
  control one.

Still to decide: where the layer sits, how it is expressed in Django/DRF, and what the detection
story is.

---

## 8. Build order

Agreed sequence, chosen so each step feeds the next and so design work is not crowded out:

1. Part 0 requirements — done in draft.
2. Data model — recipient table and the leadership/member distinction.
3. Send path and the Rule 2 mechanism — settle this on paper before writing the backend, since
   getting it wrong means a rewrite.
4. Rule 1 enforcement plus the production detection story.
5. Diagram — load balancer, both instances, database, worker, AI provider. Mermaid, so it lives in
   the repo as text.
6. Build: models and migrations → seed script → send endpoint → member read/ack → AI draft with
   its failure handling → the single leadership screen. Seed early, because a careless query
   cannot be caught against three rows.
7. README, `TEST ACCOUNTS` block, the "what I cut" note, and export of AI sessions.
8. Optional bonus, only if the rest is solid.

Commit in normal-sized increments throughout, since commit history is reviewed and a single
initial commit containing everything reads poorly.

---

## 9. Scope cuts and optional work

Cuts taken from the brief's own scope relief:

- **RSVP** is designed in Part A but not built.
- **No member-facing UI.** A read/acknowledge endpoint only.
- **No real push delivery.** Notifications are logged or written to a table; no FCM credentials.
- **Unstyled frontend.** One leadership screen — compose, pick a local, send, watch counts.
- **Local only.** Deployment is not attempted.

Optional, attempted only if the rest is solid:

- **DevOps bonus** — `docker-compose.yml` running two backend instances behind nginx or HAProxy,
  round-robin, demonstrating that Rule 2 still holds when requests hit either instance at random.

A full account of what was cut and what would come next belongs at the bottom of `DESIGN.md`.