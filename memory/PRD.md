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

## Iteration 3 (2026-09-06) — Issues 7-19
- 7: Lead Employee master (`lead_employees`, Owner-managed); Lead create has Lead Creator dropdown; `lead_creator_id`+snapshot `lead_creator_name` stored on lead and copied to ECP (history-safe).
- 8/9/10/11: Lead Team Leads status filter + ECP stage filter; Action Required→`?status=PENDING`; Follow Up Today→`?followup=today` (IST, date-based via `lead_followups`).
- 12/13: Accounts tiles drill into project-wise Payments with `view=first_pending|subsequent|receivable`; formulas match dashboard; PENDING never counts.
- 14: Lead Creator shown in Payments monitor + ECP detail (read-only).
- 15: `phone` added to user model; mandatory on create (FE+BE); existing users unaffected.
- 16: Lightweight `activities` collection + Owner-only `/work-done` report (IST today default; filters date/user/team/activity).
- 17: Owner-only CSV export `/api/export/projects?include_money=` (money columns toggle).
- 18: Manager Leads/Site Visits/ECP filters + dashboard tile drill-downs.
- 19: Responsive Layout (hamburger drawer on mobile, fixed sidebar on desktop); tables scroll; dialogs fit.
- New: `extras.py` (IST helpers, CSV). Schema additive: users.phone, leads/ecps.lead_creator_*, collections `lead_employees`, `activities`.
- Verified: 77 backend cases (76 pass; the 1 failure — payment_monitor missing lead_creator_name — was then FIXED and re-verified via API). Frontend smoke incl. mobile drawer all pass. No Phase 1 / Issues 1-6 regressions.

## Master Spec — phased delivery (2026-09-06)
DECISIONS LOCKED: YES→ECP held PENDING_DOCUMENTS; Installation Manager→Member; Site Visit performed by Installation Members (confirmed); Item dup key = Name+Unit; commercial-reject remarks mandatory; app finalizes Delivery Challan (Accounts invoices outside); no partial dispatch V1; complaints RESOLVED→(manager)→CLOSED, priority LOW/MED/HIGH/CRITICAL, SLA by category+priority (IST), category master owner-managed, assignment Registration→team→Manager→member, complaint allowed w/o ECP, attachments JPG/PNG/PDF.

### Phase 1 DONE & verified (roles + lead security + payments)
- New roles added: INSTALLATION_MANAGER, INSTALLATION_MEMBER, COMPLAINT (INSTALLATION kept for back-compat; ECP stage logic still uses INSTALLATION team until Phase 6 rewires it).
- Lead: `lead_owner_id/name` (default = creator's login user), server-side ownership scoping (LEAD sees/acts only on own leads; `get_lead` guarded), `POST /leads/{id}/reassign` (Manager/Owner) with immediate access revocation + activity log. Reassign UI on Lead detail.
- Duplicate active-lead check on phone (ACTIVE = any status except LOST) → 409.
- Payments: future-date (IST) rejected on create+update; FINAL+ADDITIONAL folded into "Subsequent" for display (`subsequent_confirmed_amount = ADDITIONAL+FINAL`); historical records untouched.
- Accounts dashboard UI trimmed to First Payment Pending (count) + Total Receivable (subsequent counters hidden).
- Verified via API: 409 duplicate, 403 LEAD reassign, 403/200 reassign revocation, 400 future-date, dashboards + Registration filter intact.

### REMAINING PHASES (pending, in order)
- P2 Lead: item fields + Item Master (Name+Unit dup, CSV import/export), owner-config mandatory fields, edit-after-handoff + commercial-change approval, quotation PDF. (needs PDF lib)
- P3 Documents: object-storage integration + YES→PENDING_DOCUMENTS gate before Registration 1. (needs object storage)
- P4 Registration 1 rework (Consumer Request; Vendor Acceptance=CVA Print&Sign+Feasibility Upload; conditional loan tasks) + task-set versioning; Registration 2 + conditional Bank Submission 2nd; CSPDCL/DCR/Consumer-Approval/NM-request + NM sequencing.
- P5 Dispatch financial-field stripping + Delivery Challan (finalize→Accounts).
- P6 Installation Manager→Member assignment, 5 mandatory photos, submit→manager acceptance/rework, Registration photo access.
- P7 Site Visit structured survey (heights/cables/name) + ≤3 geo photos + extra materials.
- P8 Complaint module (categories master, priority, SLA cat+priority, assignment routing, RESOLVED→CLOSED, dashboards, attachments, RBAC).
- P9 Mobile passes on new screens. P10 Full regression + new automated test suites + direct-API security tests.

## Next Tasks
- Build Phase 2 (Item Master + lead item fields + commercial-change approval + quotation) next; fetch object-storage & PDF playbooks when P2/P3 reached.
