# Graph Report - .  (2026-09-11)

## Corpus Check
- Corpus is ~9,053 words - fits in a single context window. You may not need a graph.

## Summary
- 113 nodes · 92 edges · 20 communities detected
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 14 edges (avg confidence: 0.71)
- Token cost: 0 input · 0 output
- Edge kinds: references: 29 · conceptually_related_to: 25 · implements: 13 · contains: 11 · rationale_for: 5 · semantically_similar_to: 4 · inherits: 3 · shares_data_with: 2

## God Nodes (most connected - your core abstractions)
1. `Rule 1: Isolation and Role Control` - 8 edges
2. `Rule 2: Retry and Restart Safety` - 8 edges
3. `Design Data Model (locals/members/users/announcements/deliveries/delivery_events/outbox_events/notification_attempts)` - 5 edges
4. `Design Send Path` - 5 edges
5. `Design Part 0 Requirements` - 4 edges
6. `Build Plan Ground Rules` - 4 edges
7. `CrewLink Callout Purpose` - 3 edges
8. `Technical Shape (frontend/backend layout)` - 3 edges
9. `PRD Delivery Checklist` - 3 edges
10. `Phase 1: Docker and Local Runtime` - 3 edges

## Surprising Connections (you probably didn't know these)
- `Claude Notes: Build Order` --semantically_similar_to--> `Build Plan Ground Rules`  [INFERRED] [semantically similar]
  AI_CONVERSATION_CLAUDE.md → BUILD_PLAN.md
- `Codex Notes: Architecture Discussion` --semantically_similar_to--> `Claude Notes: Isolation Direction`  [INFERRED] [semantically similar]
  AI_CONVERSATION_CODEX.md → AI_CONVERSATION_CLAUDE.md
- `Codex Notes: Planned Build Order` --semantically_similar_to--> `Build Plan Ground Rules`  [INFERRED] [semantically similar]
  AI_CONVERSATION_CODEX.md → BUILD_PLAN.md
- `Codex Notes: Planned Build Order` --semantically_similar_to--> `Claude Notes: Build Order`  [INFERRED] [semantically similar]
  AI_CONVERSATION_CODEX.md → AI_CONVERSATION_CLAUDE.md
- `Claude Notes: Data Model Direction` --conceptually_related_to--> `Design Data Model (locals/members/users/announcements/deliveries/delivery_events/outbox_events/notification_attempts)`  [EXTRACTED]
  AI_CONVERSATION_CLAUDE.md → DESIGN.md

## Hyperedges (group relationships)
- **Isolation and Idempotency as Shared Design Pattern Across Docs** — design_rule1_isolation, design_rule2_retry_safety, prd_authorization_rules, prd_required_checks, buildplan_phase4, buildplan_phase6 [EXTRACTED 0.90]
- **Independent Convergence of Claude and Codex on Architecture and Security Concern** — claude_two_rules, codex_problem_framing, design_concern_privacy, codex_brief_review [INFERRED 0.80]
- **Idempotent Send and Fan-out Flow** — design_send_path, design_data_model, buildplan_phase6, prd_endpoints [EXTRACTED 0.85]

## Communities

### Community 0 - "Security & Idempotency Rules"
Cohesion: 0.15
Nodes (18): AI Conversation Record - Codex, Phase 4: Authorization Boundary, Phase 5: Announcement Draft and AI Review Flow, Phase 6: Idempotent Send and Fan-out, Phase 7: Member Receipts and Leadership Statistics, Claude Notes: Idempotency Direction, Claude Notes: Isolation Direction, Codex Notes: Architecture Discussion (+10 more)

### Community 1 - "Stack Decisions & Build Order"
Cohesion: 0.18
Nodes (13): AI Conversation Record - Claude, Build Plan Ground Rules, Phase 0: Baseline and Decisions, Phase 1: Docker and Local Runtime, Claude Notes: Build Order, Claude Notes: Stack Decisions, Claude Notes: The Two Rules, Codex Notes: Planned Build Order (+5 more)

### Community 2 - "Delivery Checklist & Frontend Scope"
Cohesion: 0.22
Nodes (9): Build Plan Final Submission Checklist, Phase 10: Optional Bonus (nginx multi-instance), Phase 8: Leadership Frontend, Phase 9: Tests, README, and Review Readiness, Codex Notes: Assignment Brief Reviewed, Cross-Local Contact Info Privacy Concern, frontend/README.md (create-next-app default), PRD Delivery Checklist (+1 more)

### Community 3 - "Project Purpose & Scope"
Cohesion: 0.29
Nodes (8): Claude Notes: Deliverables Interpretation, Claude Notes: Part 0 Requirements Draft, Claude Notes: Scope Cuts and Optional Work, Codex Notes: Documents Created (DESIGN.md, PRD.md), Design Part 0 Requirements, Design Scope Cuts and Next Steps, CrewLink Callout Purpose, PRD Scope

### Community 4 - "Django App Configs"
Cohesion: 0.29
Nodes (4): AccountsConfig, AppConfig, CalloutsConfig, CoreConfig

### Community 5 - "Data Model & Seed Data"
Cohesion: 0.29
Nodes (7): Phase 2: Data Model and Migrations, Phase 3: Seed Data and Authentication, Claude Notes: Data Model Direction, Design Assumptions, Design Data Model (locals/members/users/announcements/deliveries/delivery_events/outbox_events/notification_attempts), Core Models (Local, Member, User, Announcement, Delivery, DeliveryEvent, NotificationAttempt, OutboxEvent), PRD Seed and Verification Data

### Community 6 - "Frontend Starter Icons"
Cohesion: 0.33
Nodes (6): File Icon (file.svg), Frontend Next.js Application, Globe Icon (globe.svg), Next.js Logo (next.svg), Vercel Logo (vercel.svg), Window Icon (window.svg)

### Community 7 - "Next.js Root Layout"
Cohesion: 0.40
Nodes (3): geistMono, geistSans, metadata

### Community 8 - "Django manage.py Entrypoint"
Cohesion: 0.67
Nodes (2): main(), Run administrative tasks.

### Community 10 - "Django ASGI Config"
Cohesion: 1.00
Nodes (1): ASGI config for config project.  It exposes the ASGI callable as a module-leve

### Community 11 - "Django Settings"
Cohesion: 1.00
Nodes (1): Django settings for config project.  Generated by 'django-admin startproject'

### Community 12 - "Django URL Routing"
Cohesion: 1.00
Nodes (1): URL configuration for config project.  The `urlpatterns` list routes URLs to v

### Community 13 - "Django WSGI Config"
Cohesion: 1.00
Nodes (1): WSGI config for config project.  It exposes the WSGI callable as a module-leve

### Community 14 - "Frontend Agent Instructions"
Cohesion: 1.00
Nodes (2): frontend/AGENTS.md (Next.js agent rules), frontend/CLAUDE.md

### Community 15 - "Next.js Build Config"
Cohesion: 1.00
Nodes (1): nextConfig

### Community 16 - "PostCSS Config"
Cohesion: 1.00
Nodes (1): config

### Community 27 - "Codex Exercise Interpretation"
Cohesion: 1.00
Nodes (1): Codex Notes: Exercise Interpretation

### Community 34 - "Open Questions for Denise"
Cohesion: 1.00
Nodes (1): Questions for Denise

### Community 36 - "PRD Goals"
Cohesion: 1.00
Nodes (1): PRD Goals and Success Criteria

### Community 37 - "Root README Placeholder"
Cohesion: 1.00
Nodes (1): README.md (root, placeholder)

## Knowledge Gaps
- **34 isolated node(s):** `ASGI config for config project.  It exposes the ASGI callable as a module-leve`, `Django settings for config project.  Generated by 'django-admin startproject'`, `URL configuration for config project.  The `urlpatterns` list routes URLs to v`, `WSGI config for config project.  It exposes the WSGI callable as a module-leve`, `Run administrative tasks.` (+29 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Django manage.py Entrypoint`** (2 nodes): `main()`, `Run administrative tasks.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Django ASGI Config`** (1 nodes): `ASGI config for config project.  It exposes the ASGI callable as a module-leve`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Django Settings`** (1 nodes): `Django settings for config project.  Generated by 'django-admin startproject'`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Django URL Routing`** (1 nodes): `URL configuration for config project.  The `urlpatterns` list routes URLs to v`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Django WSGI Config`** (1 nodes): `WSGI config for config project.  It exposes the WSGI callable as a module-leve`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Frontend Agent Instructions`** (2 nodes): `frontend/AGENTS.md (Next.js agent rules)`, `frontend/CLAUDE.md`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Next.js Build Config`** (1 nodes): `nextConfig`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `PostCSS Config`** (1 nodes): `config`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Codex Exercise Interpretation`** (1 nodes): `Codex Notes: Exercise Interpretation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Open Questions for Denise`** (1 nodes): `Questions for Denise`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `PRD Goals`** (1 nodes): `PRD Goals and Success Criteria`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Root README Placeholder`** (1 nodes): `README.md (root, placeholder)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Phase 3: Seed Data and Authentication` connect `Data Model & Seed Data` to `Security & Idempotency Rules`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `Rule 2: Retry and Restart Safety` connect `Security & Idempotency Rules` to `Stack Decisions & Build Order`, `Data Model & Seed Data`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Why does `Rule 1: Isolation and Role Control` connect `Security & Idempotency Rules` to `Stack Decisions & Build Order`, `Delivery Checklist & Frontend Scope`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Frontend Next.js Application` (e.g. with `File Icon (file.svg)` and `Globe Icon (globe.svg)`) actually correct?**
  _`Frontend Next.js Application` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ASGI config for config project.  It exposes the ASGI callable as a module-leve`, `Django settings for config project.  Generated by 'django-admin startproject'`, `URL configuration for config project.  The `urlpatterns` list routes URLs to v` to the rest of the system?**
  _34 weakly-connected nodes found - possible documentation gaps or missing edges._