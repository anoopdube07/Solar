# PRD — ECP Project Management & Lead Tracking System

## Original Problem Statement
Internal employee web app for a solar company so the OWNER can see the status of every Lead and ECP project — where it is, which team/person owns the next action, and which projects are stuck/delayed. Two separate workflows: Lead Qualification and ECP Execution. Full finalized business spec: `/app/memory/PHASE1_SPEC.md`.

## Architecture
- Backend: FastAPI (`/app/backend/server.py`, `auth.py`, `workflow.py`, `extras.py`), MongoDB (UUID string ids), JWT username+password auth (Bearer token in login body, stored in localStorage).
- Frontend: React + Tailwind + shadcn/ui; role-based sidebar layout; sonner toasts. Design tokens from `/app/design_guidelines.json`.
- PDF: ReportLab (quotation generation).

## User Personas / Roles (V1: one user = one role = one team)
OWNER, MANAGER (Process Owner), LEAD, REGISTRATION, ACCOUNTS, DISPATCH, INSTALLATION (+ future INSTALLATION_MANAGER, INSTALLATION_MEMBER, COMPLAINT roles seeded).

## Core Requirements (static — from Phase 1 spec)
- Lead: PENDING + 5 actions (YES/NO/FOLLOW_UP/SITE_VISIT/ESCALATION). Only Lead Team decides.
- YES auto-creates exactly one ECP (max 1 per lead lifetime) at REGISTRATION_1.
- ECP pipeline REGISTRATION_1 → ACCOUNTS_1 → DISPATCH → INSTALLATION → NET_METERING → REGISTRATION_2 → ACCOUNTS_2 → COMPLETED, with automatic handoffs.
- START DISPATCH gated server-side on FIRST payment CONFIRMED; final payment never blocks; closure ignores payments.
- Derived statuses (Payment Blocked / Ready for Dispatch / Dispatch In Process / Delayed) — never workflow stages.
- SLA per stage (0 = never delayed). RBAC per role; only Owner manages users, SLA, reopens LOST.

## Implemented Phases (summary)
- Phase 1 (2026-09-06): full auth, lead + ECP workflows, site visits, escalations, payments, dashboards, users, SLA. 20/20 backend pass.
- Issues 1-6: role-aware filters, dispatch derived-status filters, manager install assignment, site-visit installer dropdown, lead project price → ECP, accounts payments page. 48/48 pass.
- Issues 7-19: Lead Employee master, lead_creator snapshots, filters + drilldowns, IST follow-up, phone required, work-done report, owner CSV export, mobile drawer. 76/77 pass (payment_monitor lead_creator_name fixed via API).
- Master Spec Phase 1: new roles (INSTALLATION_MANAGER/MEMBER, COMPLAINT), lead_owner + ownership scoping + reassign, duplicate-phone 409, payment future-date reject, Subsequent folding.

## Master Spec Phase 2 — DONE & verified (2026-09-12)
- **Item Master** (Owner-only): `/api/items` list/create/patch(active toggle), `/api/items/export` CSV, `/api/items/import` CSV (dup key = normalized Name+Unit; in-file + existing dup rows skipped/reported). Frontend `/items` page.
- **Lead item fields**: `item_id` + snapshot `item_name`/`item_unit`, `quantity`, `location_link` (+ existing `project_price`). Server validates item is active/exists (400 otherwise). Fields on Lead create form (active-item dropdown) + shown on Lead detail.
- **Owner-configurable mandatory fields**: `/api/lead-field-config` (Owner PUT; LEAD/MANAGER/OWNER GET). Toggleable: email, address, location_link, item, quantity, project_price. Name & Phone always mandatory (workflow-integrity). Backend `enforce_lead_mandatory` enforces server-side (400) independent of UI. Owner page `/lead-fields`.
- **Post-handoff Lead editing**: `PATCH /api/leads/{id}` (LEAD owner / OWNER) for non-commercial fields (email/address/location_link). Direct `project-price` POST now returns 400 once handed off (ecp_id present).
- **Commercial change approval**: `POST /api/leads/{id}/commercial-change` (LEAD owner) proposes item/quantity/project_price → pending_commercial_change (PENDING). Owner approve/reject (`/approve`, `/reject`); reject remarks mandatory (400 if missing). Approve applies proposed values to lead + syncs ECP project_price. Owner dashboard banner + `pending_commercial` count. RBAC enforced (non-owner approve/reject/pending → 403).
- **Quotation PDF**: `GET /api/leads/{id}/quotation` (LEAD owner / MANAGER / OWNER; non-owner LEAD → 403) → application/pdf. Frontend button uses Web Share API with download fallback.
- Verified: new `/app/backend/tests/test_phase2.py` 25/25 PASS + Playwright UI smoke. No Phase 2 functional bugs (iteration_5.json).

## REMAINING PHASES (pending, in order)
- P3 Documents: object-storage integration + YES→PENDING_DOCUMENTS gate before Registration 1. (needs object storage playbook)
- P4 Registration 1 rework (Consumer Request; Vendor Acceptance; conditional loan tasks) + task-set versioning; Registration 2 + conditional Bank Submission; CSPDCL/DCR/NM sequencing.
- P5 Dispatch financial-field stripping + Delivery Challan (finalize→Accounts).
- P6 Installation Manager→Member assignment, 5 mandatory photos, submit→manager acceptance/rework, Registration photo access.
- P7 Site Visit structured survey + ≤3 geo photos + extra materials.
- P8 Complaint module (categories master, priority, SLA cat+priority, assignment routing, RESOLVED→CLOSED, dashboards, attachments, RBAC).
- P9 Mobile passes on new screens. P10 Full regression + automated suites + direct-API security tests.

## Known test hygiene note
Legacy Phase-1 pytest files (backend_test.py, test_issues_*.py, test_audit_spec.py) use hardcoded phone numbers that now collide with duplicate-active-phone 409 (correct app behaviour). Refactor to uuid-based phones like test_phase2.py if re-running the legacy regression suite.

## Next Tasks
- Await user verification of Phase 2, then start Phase 3 (Documents / object storage) — fetch object-storage playbook via integration_expert.
