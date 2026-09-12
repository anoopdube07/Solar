# PRD — ECP Project Management & Lead Tracking System

## Original Problem Statement
Internal employee web app for a solar company so the OWNER can see the status of every Lead and ECP project — where it is, which team/person owns the next action, and which projects are stuck/delayed. Two separate workflows: Lead Qualification and ECP Execution. Full finalized business spec: `/app/memory/PHASE1_SPEC.md`.

## Architecture
- Backend: FastAPI (`/app/backend/server.py`, `auth.py`, `workflow.py`, `extras.py`), MongoDB (UUID string ids), JWT username+password auth (Bearer token in login body, stored in localStorage as `ecp_token`).
- Frontend: React + Tailwind + shadcn/ui; role-based sidebar layout; sonner toasts. AuthContext bootstraps via `/api/auth/me`.
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
- Phase 1: full auth, lead + ECP workflows, site visits, escalations, payments, dashboards, users, SLA.
- Issues 1-6: role-aware filters, dispatch derived-status filters, manager install assignment, site-visit installer dropdown, lead project price → ECP, accounts payments page.
- Issues 7-19: Lead Employee master, lead_creator snapshots, filters + drilldowns, IST follow-up, phone required, work-done report, owner CSV export, mobile drawer.
- Master Spec Phase 1: new roles, lead_owner + ownership scoping + reassign, duplicate-phone 409, payment future-date reject, Subsequent folding.

## Master Spec Phase 2 — DONE & verified (2026-09-12)
- **Item Master** (Owner-only): `/api/items` list/create/patch(active toggle)/**delete**, `/api/items/export` + `/api/items/import` CSV (dup key = normalized Name+Unit). Frontend `/items` page with ACTIVE/INACTIVE badges, "In use" marker, Edit / Deactivate / Delete.
  - **Delete data-integrity**: `DELETE /api/items/{id}` Owner-only; blocked (409, "used in existing records… deactivate instead") if the item is referenced by any lead `item_id` or by a `pending_commercial_change` (proposed/current). List response includes `referenced`/`deletable` flags; UI disables delete for non-deletable items.
  - Deactivated items: excluded from `active_only` list, rejected on new lead creation (400 "Invalid or inactive item"), historical leads keep `item_name`/`item_unit` snapshot so records still display.
- **Lead item fields**: `item_id` + snapshot `item_name`/`item_unit`, `quantity`, `location_link` (+ existing `project_price`). Server validates item active/exists.
- **Owner-configurable mandatory fields**: `/api/lead-field-config`. Toggleable: email, address, location_link, item, quantity, project_price. Name & Phone always mandatory. Server-side `enforce_lead_mandatory` (400). Owner page `/lead-fields`.
- **Post-handoff Lead editing**: `PATCH /api/leads/{id}` (LEAD owner / OWNER) for non-commercial fields. Direct `project-price` POST returns 400 once handed off.
- **Commercial change approval**: propose (LEAD owner) → Owner approve/reject; reject remarks mandatory. Approve applies to lead + syncs ECP price. Owner dashboard banner + `pending_commercial` count. RBAC enforced.
- **Quotation PDF**: `GET /api/leads/{id}/quotation` (LEAD owner / MANAGER / OWNER; non-owner LEAD → 403). Frontend Web Share + download fallback.
- Verified: `/app/backend/tests/test_phase2.py` 25/25 PASS (iteration_5.json) + Playwright UI smoke. Item DELETE additions re-verified via curl (owner delete unused 200, non-owner 403, referenced 409, deactivated-selection 400).

## REMAINING PHASES (pending, in order) — DO NOT START P3 UNTIL PHASE 2 USER-VERIFIED
- P3 Documents: object-storage integration + YES→PENDING_DOCUMENTS gate before Registration 1.
- P4 Registration 1/2 rework + task-set versioning + CSPDCL/DCR/NM sequencing.
- P5 Dispatch financial-field stripping + Delivery Challan (finalize→Accounts). NOTE: challans will reference items → include in item reference-check when built.
- P6 Installation Manager→Member assignment, 5 mandatory photos, submit→acceptance/rework.
- P7 Site Visit structured survey + geo photos + extra materials. NOTE: extra-materials will reference items → include in reference-check.
- P8 Complaint module. P9 Mobile passes. P10 Full regression + security tests.

## Known test hygiene note
Legacy Phase-1 pytest files use hardcoded phones that now collide with duplicate-active-phone 409 (correct behaviour). Refactor to uuid-based phones like test_phase2.py if re-running that suite.

## Next Tasks
- Await user verification of Phase 2 (incl. Item delete rules), then start Phase 3 (Documents / object storage) — fetch object-storage playbook via integration_expert.
