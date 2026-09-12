# CHANGELOG

## Phases 4–10 (2026-06) — one coordinated build

### Phase 4 — Registration rework
- REGISTRATION_1 tasks: Consumer Request, CVA Print & Sign, Feasibility Report Upload (+ finance: Loan Documentation, Loan Filing, Bank Submission).
- REGISTRATION_2 tasks: Asset Creation, Completion Certificate (requires Asset Creation), Bank Submission 2nd (finance only, else N/A).
- NET_METERING now a shared stage: Registration does Upload Installation Photos to CSPDCL Portal → DCR Issuance → Consumer Approval & Submit → Request Net Metering from CSPDCL (chained), then INSTALLATION_MEMBER does Close Net Metering (requires the Request task). Server-side `requires` gating + per-task team enforcement. Photo-upload task gated on manager-approved photos existing.
- Task specs centralized in workflow.STAGE_TASK_SPECS (name, team, financing_only, requires); tasks carry team+requires. Historical ECPs untouched (their old task docs remain).

### Phase 5 — Dispatch + Delivery Challan
- Dispatch financial segregation enforced server-side: `_scrub_dispatch` removes project_price from GET /ecps and /ecps/{id}; payments returned empty for DISPATCH.
- Start Dispatch remains gated by FIRST payment CONFIRMED.
- Delivery Challan: delivery_challans collection; POST /ecps/{id}/challan (dispatch/owner, active Item Master), /challan/finalize; GET /challans (accounts/manager/owner). No invoice generation; no partial dispatch.

### Phase 6 — Installation Manager → Member + photos + acceptance
- New roles INSTALLATION_MANAGER, INSTALLATION_MEMBER (legacy INSTALLATION works as member). Seeded: instmgr/instmem.
- Flow: AWAITING_ASSIGNMENT (team INSTALLATION_MANAGER) → assign member → start → 5 mandatory photos (ecp_photos, object storage) → submit (all 5 required) → PENDING_ACCEPTANCE → manager accept (photos approved, advance) / reject (remarks mandatory → REJECTED → re-upload).
- Registration sees install photos only when approved (RBAC on list/download).

### Phase 7 — Site Visit survey
- INSTALLATION_MANAGER (not process Manager) + Owner assign an INSTALLATION_MEMBER; member submits structured survey (structure_height, earthing/dc/ac cable lengths, surveyor_name required; extra_materials via active Item Master). Lead returns to Lead Team with 5 actions. No ECP/installation created.

### Phase 8 — Complaint Portal
- Role COMPLAINT (seeded complaint/Comp@123). Owner-managed categories (dup 409) + SLA config by category|priority (IST). Workflow REGISTERED→ASSIGNED→IN_PROGRESS→RESOLVED→CLOSED (member resolves, manager/owner closes). Optional lead/ecp link. Attachments jpg/png/pdf (object storage) + RBAC. Overdue = IST today > due & not resolved/closed. History tracked.

### Phase 9 — Mobile
- New surfaces use responsive shadcn dialogs/cards; photo inputs use capture="environment"; overflow-y on tall dialogs.

### Phase 10 — Tests
- test_phase4_10.py (6 journey/security tests) PASS. Full backend regression: 159 tests pass (backend_test, test_issues_1_to_6, test_issues_7_to_19, test_audit_spec, test_phase2, test_phase2_final, test_phase3_documents, test_phase4_10). Legacy pipeline/financing/dispatch tests updated to the new rules.

## Final Audit (2026-06) — confirmed-gap fixes + new-role dashboards
- Fixed: Owner user-creation dropdown now lists all 10 roles incl. INSTALLATION_MANAGER, INSTALLATION_MEMBER, COMPLAINT (Users.jsx ROLES + ROLE_LABELS). Backend wf.ROLES already accepted them; create is Owner-only (non-owner 403).
- Added role-specific dashboard data + UI for the 3 new roles (were blank): INSTALLATION_MANAGER (Installation + Site Visit supervision queues), INSTALLATION_MEMBER (my installations / my site visits), COMPLAINT (register + status + SLA overdue/due-today).
- COMPLAINT dashboard has a prominent "+ Register Complaint" CTA deep-linking to /complaints?new=1 (auto-opens the register dialog).
- Verified by testing agent iteration_8: 8/8 targeted backend tests + live UI smoke, no functional bugs. Existing 159-suite untouched.
- NOTE: The broad "operations command-center" redesign of the EXISTING role dashboards (Owner/Manager/Lead/Registration/Accounts/Dispatch) and Site-Visit geo-photo/extra-material capture UI were NOT done in this pass (budget) — existing dashboards remain functional; these are deferred.

## Prior note: Frontend compiles clean (HTTP 200); Phase 4-10 new-flow UI is wired (Complaints page, InstallationWork, DeliveryChallanPanel, Site Visit survey) but visual QA via the screenshot harness was blocked by an auth-persistence quirk in the preview automation; backend behavior fully verified via automated tests.
