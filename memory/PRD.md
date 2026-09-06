# PRD — ECP Project Management & Lead Tracking System

## Original Problem Statement
Internal employee web app for a solar company so the OWNER can see the status of every Lead and ECP project — where it is, which team/person owns the next action, and which projects are stuck/delayed. Two separate workflows: Lead Qualification and ECP Execution. Full finalized business spec: `/app/memory/PHASE1_SPEC.md`.

## Architecture
- Backend: FastAPI (`/app/backend/server.py`, `auth.py`, `workflow.py`), MongoDB (UUID string ids), JWT username+password auth (Bearer token in login body, stored in localStorage).
- Frontend: React + Tailwind + shadcn/ui; role-based sidebar layout; sonner toasts. Design tokens from `/app/design_guidelines.json`.

## User Personas / Roles (V1: one user = one role = one team)
OWNER, MANAGER (Process Owner), LEAD, REGISTRATION, ACCOUNTS, DISPATCH, INSTALLATION.

## Core Requirements (static — from Phase 1 spec)
- Lead: PENDING + 5 actions (YES/NO/FOLLOW_UP/SITE_VISIT/ESCALATION). Only Lead Team decides.
- YES auto-creates exactly one ECP (max 1 per lead lifetime) at REGISTRATION_1.
- ECP pipeline: REGISTRATION_1 → ACCOUNTS_1 → DISPATCH → INSTALLATION → NET_METERING → REGISTRATION_2 → ACCOUNTS_2 → COMPLETED, with automatic handoffs.
- START DISPATCH gated server-side on FIRST payment CONFIRMED; final payment never blocks; closure ignores payments.
- Derived statuses (Payment Blocked / Ready for Dispatch / Dispatch In Process / Delayed) — never workflow stages.
- SLA per stage (0 = never delayed).
- RBAC per role & permission matrix; only Owner manages users & SLA & reopens LOST & returns escalations.

## Implemented (2026-09-06)
- Username/password JWT auth + owner + 6 demo team users seeded.
- Full Lead workflow: create, 5 actions with all server-side validations, follow-up/site-visit/escalation history, LOST reopen (owner), return-to-lead-team with return reasons.
- Site Visits: request → manager/owner assign to Installation → complete with survey → auto-return to Lead Team.
- Escalations: to Owner → return with mandatory remarks.
- Full ECP workflow with mandatory-task gating, automatic handoffs, dispatch payment gate, installation status transitions, financing toggle (no regress/no duplicate), manual closure (owner/manager).
- Payments: FIRST/ADDITIONAL/FINAL, uniqueness rules, Accounts-only writes, payment monitor.
- Role-based dashboards with clickable drill-down counters; Leads/ECP list + detail; Users mgmt; SLA config.
- Verified: backend 20/20 tests pass; owner cannot perform lead-team actions (spec §D enforced).

## Backlog (not built — V1 exclusions or future)
- P2: WhatsApp/bot, QA/QC, formal audit trail, inventory, accounting, customer portal, payment gateway (explicitly excluded in V1).
- P1 (nice-to-have): pagination on list endpoints; split backend into routers; dedicated COMPLETED stage flag; friendlier empty-states.

## Iteration 2 (2026-09-06) — Approved UX fixes (Issues 1-6)
- Issue 1: ECP Projects now has a working role-aware filter (Registration: Reg 1 / Reg 2). Backend `list_ecps` honors `stage` within each role's scope.
- Issue 2/2B/3: Added `project_price` on Lead (Lead Team enters, carries to ECP; Accounts read-only). Accounts dashboard simplified to 3 receivable metrics (First Payment Pending count, Subsequent Follow-up count + amount, Total Receivable). Payments page is now one row per project with `+Payment`; single entry route. ADDITIONAL relabeled "Subsequent" in UI only.
- Issue 4: Dispatch dashboard tiles + ECP filter use derived `view` param (PAYMENT_BLOCKED / READY_FOR_DISPATCH / DISPATCH_IN_PROCESS / PAST_DISPATCH) that actually filters.
- Issue 5: Dispatch completion routes to Manager (`install_status=AWAITING_ASSIGNMENT`, current_team=MANAGER). New `POST /ecps/{id}/assign-installation` (Manager/Owner). Installers only see/act on their own assigned projects.
- Issue 6: New `GET /users/team/{role}` (Manager/Owner) populates the installer dropdown for Lead Site Visit assignment (Site Visit workflow otherwise untouched).
- Verified: 48/48 backend tests pass (backend_test.py + test_audit_spec.py + test_issues_1_to_6.py); frontend smoke 7/7. No Phase 1 regressions.

## Next Tasks
- Await user feedback; optional: Manager team-workload matrix, delayed-projects report.
