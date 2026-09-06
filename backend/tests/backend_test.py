"""End-to-end backend tests for ECP Project Management & Lead Tracking (Phase 1)."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fallback to frontend env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "owner":        ("anoopdube07@gmail.com", "Owner@123",   "OWNER"),
    "manager":      ("manager",               "Manager@123", "MANAGER"),
    "lead":         ("lead",                  "Lead@123",    "LEAD"),
    "registration": ("registration",          "Reg@123",     "REGISTRATION"),
    "accounts":     ("accounts",              "Acct@123",    "ACCOUNTS"),
    "dispatch":     ("dispatch",              "Disp@123",    "DISPATCH"),
    "installation": ("installation",          "Install@123", "INSTALLATION"),
}


def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {username}: {r.status_code} {r.text}"
    return r.json()


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def tokens():
    t = {}
    for k, (u, p, role) in CREDS.items():
        j = _login(u, p)
        assert j["user"]["role"] == role, f"role mismatch for {k}: got {j['user']['role']}"
        t[k] = j["token"]
    return t


# --------------- AUTH ---------------
class TestAuth:
    def test_login_all_seeded(self):
        for k, (u, p, role) in CREDS.items():
            j = _login(u, p)
            assert j["user"]["role"] == role
            assert isinstance(j["token"], str) and len(j["token"]) > 10

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"username": "lead", "password": "bad"})
        assert r.status_code == 401

    def test_me(self, tokens):
        r = requests.get(f"{API}/auth/me", headers=_hdr(tokens["lead"]))
        assert r.status_code == 200
        assert r.json()["role"] == "LEAD"


# --------------- LEAD CREATION RBAC ---------------
class TestLeadRBAC:
    def test_non_lead_forbidden(self, tokens):
        payload = {"name": "TEST_RBAC", "phone": "9999900000"}
        for role in ["manager", "registration", "accounts", "dispatch", "installation"]:
            r = requests.post(f"{API}/leads", json=payload, headers=_hdr(tokens[role]))
            assert r.status_code == 403, f"{role} should not create lead: {r.status_code}"

    def test_lead_creates_pending(self, tokens):
        r = requests.post(f"{API}/leads",
            json={"name": f"TEST_L_{uuid.uuid4().hex[:6]}", "phone": "9998887777"},
            headers=_hdr(tokens["lead"]))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "PENDING"
        assert d["action_required"] is True
        assert d["current_team"] == "LEAD"


def _new_lead(tokens, financing=False, name_prefix="TEST_L"):
    r = requests.post(f"{API}/leads",
        json={"name": f"{name_prefix}_{uuid.uuid4().hex[:6]}", "phone": "9990000000",
              "financing_required": financing},
        headers=_hdr(tokens["lead"]))
    assert r.status_code == 200, r.text
    return r.json()["id"]


# --------------- LEAD ACTIONS ---------------
class TestLeadActions:
    def test_yes_creates_ecp_reg1_and_second_yes_rejected(self, tokens):
        lid = _new_lead(tokens)
        r = requests.post(f"{API}/leads/{lid}/action", json={"action": "YES"}, headers=_hdr(tokens["lead"]))
        assert r.status_code == 200, r.text
        bundle = r.json()
        assert bundle["lead"]["status"] == "QUALIFIED"
        assert bundle["ecp"] is not None
        assert bundle["ecp"]["current_stage"] == "REGISTRATION_1"
        assert bundle["ecp"]["current_team"] == "REGISTRATION"
        # Second YES rejected
        r2 = requests.post(f"{API}/leads/{lid}/action", json={"action": "YES"}, headers=_hdr(tokens["lead"]))
        assert r2.status_code == 400

    def test_no_requires_reason_and_other_requires_remarks(self, tokens):
        lid = _new_lead(tokens)
        r = requests.post(f"{API}/leads/{lid}/action", json={"action": "NO"}, headers=_hdr(tokens["lead"]))
        assert r.status_code == 400
        r = requests.post(f"{API}/leads/{lid}/action",
            json={"action": "NO", "lost_reason": "OTHER"}, headers=_hdr(tokens["lead"]))
        assert r.status_code == 400
        r = requests.post(f"{API}/leads/{lid}/action",
            json={"action": "NO", "lost_reason": "OTHER", "lost_remarks": "Something"},
            headers=_hdr(tokens["lead"]))
        assert r.status_code == 200
        assert r.json()["lead"]["status"] == "LOST"

    def test_followup_past_rejected_future_ok(self, tokens):
        lid = _new_lead(tokens)
        r = requests.post(f"{API}/leads/{lid}/action",
            json={"action": "FOLLOW_UP", "followup_date": "2020-01-01", "remarks": "x"},
            headers=_hdr(tokens["lead"]))
        assert r.status_code == 400
        r = requests.post(f"{API}/leads/{lid}/action",
            json={"action": "FOLLOW_UP", "followup_date": "2027-06-15", "remarks": "call back"},
            headers=_hdr(tokens["lead"]))
        assert r.status_code == 200
        assert r.json()["lead"]["status"] == "FOLLOW_UP"
        assert r.json()["lead"]["action_required"] is True

    def test_site_visit_flow(self, tokens):
        lid = _new_lead(tokens)
        r = requests.post(f"{API}/leads/{lid}/action",
            json={"action": "SITE_VISIT", "remarks": "please visit"},
            headers=_hdr(tokens["lead"]))
        assert r.status_code == 200
        # second open site visit rejected
        r2 = requests.post(f"{API}/leads/{lid}/action",
            json={"action": "SITE_VISIT", "remarks": "again"}, headers=_hdr(tokens["lead"]))
        assert r2.status_code == 400
        # find open site visit
        vs = requests.get(f"{API}/site-visits", headers=_hdr(tokens["manager"])).json()
        sv = next(v for v in vs if v["lead_id"] == lid and v["status"] == "REQUESTED")
        # need install user id
        users = requests.get(f"{API}/users", headers=_hdr(tokens["owner"])).json()
        install_user = next(u for u in users if u["role"] == "INSTALLATION")
        # non-manager cannot assign
        r = requests.post(f"{API}/site-visits/{sv['id']}/assign",
            json={"assigned_user": install_user["id"], "visit_date": "2027-01-20"},
            headers=_hdr(tokens["lead"]))
        assert r.status_code == 403
        # non-INSTALLATION assignee rejected
        lead_user = next(u for u in users if u["role"] == "LEAD")
        r = requests.post(f"{API}/site-visits/{sv['id']}/assign",
            json={"assigned_user": lead_user["id"], "visit_date": "2027-01-20"},
            headers=_hdr(tokens["manager"]))
        assert r.status_code == 400
        # manager assigns correctly
        r = requests.post(f"{API}/site-visits/{sv['id']}/assign",
            json={"assigned_user": install_user["id"], "visit_date": "2027-01-20"},
            headers=_hdr(tokens["manager"]))
        assert r.status_code == 200
        # complete without survey rejected
        r = requests.post(f"{API}/site-visits/{sv['id']}/complete",
            json={"survey_info": ""}, headers=_hdr(tokens["installation"]))
        assert r.status_code == 400
        # complete with survey
        r = requests.post(f"{API}/site-visits/{sv['id']}/complete",
            json={"survey_info": "Roof OK, 5kW"}, headers=_hdr(tokens["installation"]))
        assert r.status_code == 200
        # Lead returned to LEAD team with return_reason SITE_VISIT_COMPLETED
        lead = requests.get(f"{API}/leads/{lid}", headers=_hdr(tokens["lead"])).json()["lead"]
        assert lead["current_team"] == "LEAD"
        assert lead["action_required"] is True
        assert lead["return_reason"] == "SITE_VISIT_COMPLETED"

    def test_escalation_and_owner_return(self, tokens):
        lid = _new_lead(tokens)
        r = requests.post(f"{API}/leads/{lid}/action",
            json={"action": "ESCALATION"}, headers=_hdr(tokens["lead"]))
        assert r.status_code == 400
        r = requests.post(f"{API}/leads/{lid}/action",
            json={"action": "ESCALATION", "reason": "pricing", "remarks": "need help"},
            headers=_hdr(tokens["lead"]))
        assert r.status_code == 200
        # non-owner cannot return
        escs = requests.get(f"{API}/escalations", headers=_hdr(tokens["owner"])).json()
        esc = next(e for e in escs if e["lead_id"] == lid and e["status"] == "OPEN")
        r = requests.post(f"{API}/escalations/{esc['id']}/return",
            json={"owner_remarks": ""}, headers=_hdr(tokens["owner"]))
        assert r.status_code == 400
        r = requests.post(f"{API}/escalations/{esc['id']}/return",
            json={"owner_remarks": "please proceed"}, headers=_hdr(tokens["manager"]))
        assert r.status_code == 403
        r = requests.post(f"{API}/escalations/{esc['id']}/return",
            json={"owner_remarks": "please proceed"}, headers=_hdr(tokens["owner"]))
        assert r.status_code == 200
        lead = requests.get(f"{API}/leads/{lid}", headers=_hdr(tokens["lead"])).json()["lead"]
        assert lead["return_reason"] == "OWNER_RETURNED"
        assert lead["action_required"] is True

    def test_only_owner_reopen_lost(self, tokens):
        lid = _new_lead(tokens)
        requests.post(f"{API}/leads/{lid}/action",
            json={"action": "NO", "lost_reason": "PRICE"}, headers=_hdr(tokens["lead"]))
        r = requests.post(f"{API}/leads/{lid}/reopen", headers=_hdr(tokens["lead"]))
        assert r.status_code == 403
        r = requests.post(f"{API}/leads/{lid}/reopen", headers=_hdr(tokens["manager"]))
        assert r.status_code == 403
        r = requests.post(f"{API}/leads/{lid}/reopen", headers=_hdr(tokens["owner"]))
        assert r.status_code == 200
        lead = r.json()["lead"]
        assert lead["status"] == "PENDING"
        assert lead["return_reason"] == "REOPENED"
        assert lead["action_required"] is True


# --------------- ECP FLOW ---------------
def _qualify_and_get_ecp(tokens, financing=False):
    lid = _new_lead(tokens, financing=financing)
    r = requests.post(f"{API}/leads/{lid}/action", json={"action": "YES"}, headers=_hdr(tokens["lead"]))
    assert r.status_code == 200
    return lid, r.json()["ecp"]["id"]


def _tasks_for_stage(ecp_id, stage, token):
    r = requests.get(f"{API}/ecps/{ecp_id}", headers=_hdr(token))
    assert r.status_code == 200
    d = r.json()
    return [t for t in d["tasks"] if t["stage"] == stage]


def _complete_all_applicable(ecp_id, stage, token):
    tasks = _tasks_for_stage(ecp_id, stage, token)
    for t in tasks:
        if t["applicable"] and not t["completed"]:
            r = requests.post(f"{API}/ecps/{ecp_id}/tasks/{t['id']}/complete", headers=_hdr(token))
            assert r.status_code == 200, f"complete {t['task_name']} failed: {r.text}"


class TestECPFlow:
    def test_reg1_financing_tasks_block_and_autoadvance(self, tokens):
        _, ecp_id = _qualify_and_get_ecp(tokens, financing=True)
        # Verify 7 applicable tasks
        tasks = _tasks_for_stage(ecp_id, "REGISTRATION_1", tokens["registration"])
        applicable = [t for t in tasks if t["applicable"]]
        assert len(applicable) == 7, f"expected 7 (4 base + 3 loan), got {len(applicable)}"
        # complete base first, ensure not advanced yet
        base = ["CSPDCL Registration", "PPA Preparation", "Cover Letter", "CVA"]
        for name in base:
            t = next(x for x in tasks if x["task_name"] == name)
            requests.post(f"{API}/ecps/{ecp_id}/tasks/{t['id']}/complete", headers=_hdr(tokens["registration"]))
        e = requests.get(f"{API}/ecps/{ecp_id}", headers=_hdr(tokens["registration"])).json()["ecp"]
        assert e["current_stage"] == "REGISTRATION_1", "should still be in reg1 with financing loan tasks pending"
        # complete loan tasks
        _complete_all_applicable(ecp_id, "REGISTRATION_1", tokens["registration"])
        e = requests.get(f"{API}/ecps/{ecp_id}", headers=_hdr(tokens["registration"])).json()["ecp"]
        assert e["current_stage"] == "ACCOUNTS_1"

    def test_full_pipeline_no_financing(self, tokens):
        _, ecp_id = _qualify_and_get_ecp(tokens, financing=False)
        # REG1
        _complete_all_applicable(ecp_id, "REGISTRATION_1", tokens["registration"])
        e = requests.get(f"{API}/ecps/{ecp_id}", headers=_hdr(tokens["owner"])).json()["ecp"]
        assert e["current_stage"] == "ACCOUNTS_1"
        # ACCOUNTS_1 -> auto to DISPATCH without first payment
        _complete_all_applicable(ecp_id, "ACCOUNTS_1", tokens["accounts"])
        e = requests.get(f"{API}/ecps/{ecp_id}", headers=_hdr(tokens["owner"])).json()["ecp"]
        assert e["current_stage"] == "DISPATCH"
        assert e["derived_status"] == "PAYMENT_BLOCKED"

        # start-dispatch rejected without first payment CONFIRMED
        r = requests.post(f"{API}/ecps/{ecp_id}/start-dispatch", headers=_hdr(tokens["dispatch"]))
        assert r.status_code == 400

        # completing dispatch tasks before start rejected
        tasks = _tasks_for_stage(ecp_id, "DISPATCH", tokens["dispatch"])
        r = requests.post(f"{API}/ecps/{ecp_id}/tasks/{tasks[0]['id']}/complete",
            headers=_hdr(tokens["dispatch"]))
        assert r.status_code == 400

        # Accounts creates FIRST payment CONFIRMED
        r = requests.post(f"{API}/payments",
            json={"ecp_id": ecp_id, "type": "FIRST", "amount": 100000, "date": "2026-09-10",
                  "status": "CONFIRMED"}, headers=_hdr(tokens["accounts"]))
        assert r.status_code == 200, r.text
        # duplicate FIRST rejected
        r2 = requests.post(f"{API}/payments",
            json={"ecp_id": ecp_id, "type": "FIRST", "amount": 100, "date": "2026-09-11",
                  "status": "PENDING"}, headers=_hdr(tokens["accounts"]))
        assert r2.status_code == 400

        # start dispatch OK
        r = requests.post(f"{API}/ecps/{ecp_id}/start-dispatch", headers=_hdr(tokens["dispatch"]))
        assert r.status_code == 200
        # dispatch tasks completion -> INSTALLATION
        _complete_all_applicable(ecp_id, "DISPATCH", tokens["dispatch"])
        e = requests.get(f"{API}/ecps/{ecp_id}", headers=_hdr(tokens["owner"])).json()["ecp"]
        assert e["current_stage"] == "INSTALLATION"
        assert e["install_status"] == "READY_TO_INSTALL"
        # install start -> IN_PROCESS
        r = requests.post(f"{API}/ecps/{ecp_id}/installation",
            json={"action": "start"}, headers=_hdr(tokens["installation"]))
        assert r.status_code == 200
        r = requests.post(f"{API}/ecps/{ecp_id}/installation",
            json={"action": "complete"}, headers=_hdr(tokens["installation"]))
        assert r.status_code == 200
        e = requests.get(f"{API}/ecps/{ecp_id}", headers=_hdr(tokens["owner"])).json()["ecp"]
        assert e["current_stage"] == "NET_METERING"
        _complete_all_applicable(ecp_id, "NET_METERING", tokens["installation"])
        e = requests.get(f"{API}/ecps/{ecp_id}", headers=_hdr(tokens["owner"])).json()["ecp"]
        assert e["current_stage"] == "REGISTRATION_2"
        _complete_all_applicable(ecp_id, "REGISTRATION_2", tokens["registration"])
        e = requests.get(f"{API}/ecps/{ecp_id}", headers=_hdr(tokens["owner"])).json()["ecp"]
        assert e["current_stage"] == "ACCOUNTS_2"
        # Complete ACCOUNTS_2 even without FINAL payment
        _complete_all_applicable(ecp_id, "ACCOUNTS_2", tokens["accounts"])
        e = requests.get(f"{API}/ecps/{ecp_id}", headers=_hdr(tokens["owner"])).json()["ecp"]
        assert e["status"] == "COMPLETED"


# --------------- PAYMENTS RBAC ---------------
class TestPayments:
    def test_only_accounts_creates(self, tokens):
        _, ecp_id = _qualify_and_get_ecp(tokens)
        payload = {"ecp_id": ecp_id, "type": "ADDITIONAL", "amount": 10, "date": "2026-09-01",
                   "status": "PENDING"}
        for role in ["owner", "manager", "lead", "registration", "dispatch", "installation"]:
            r = requests.post(f"{API}/payments", json=payload, headers=_hdr(tokens[role]))
            assert r.status_code == 403, f"{role} should not create payment"
        r = requests.post(f"{API}/payments", json=payload, headers=_hdr(tokens["accounts"]))
        assert r.status_code == 200

    def test_additional_multiple_allowed(self, tokens):
        _, ecp_id = _qualify_and_get_ecp(tokens)
        payload = {"ecp_id": ecp_id, "type": "ADDITIONAL", "amount": 5, "date": "2026-09-01",
                   "status": "PENDING"}
        r1 = requests.post(f"{API}/payments", json=payload, headers=_hdr(tokens["accounts"]))
        r2 = requests.post(f"{API}/payments", json=payload, headers=_hdr(tokens["accounts"]))
        assert r1.status_code == 200 and r2.status_code == 200

    def test_monitor_rbac(self, tokens):
        for role in ["accounts", "owner", "manager"]:
            r = requests.get(f"{API}/payments/monitor", headers=_hdr(tokens[role]))
            assert r.status_code == 200
        for role in ["lead", "dispatch", "installation", "registration"]:
            r = requests.get(f"{API}/payments/monitor", headers=_hdr(tokens[role]))
            assert r.status_code == 403


# --------------- FINANCING TOGGLE ---------------
class TestFinancingToggle:
    def test_toggle_no_regress(self, tokens):
        _, ecp_id = _qualify_and_get_ecp(tokens, financing=False)
        # advance to ACCOUNTS_1
        _complete_all_applicable(ecp_id, "REGISTRATION_1", tokens["registration"])
        e = requests.get(f"{API}/ecps/{ecp_id}", headers=_hdr(tokens["owner"])).json()["ecp"]
        assert e["current_stage"] == "ACCOUNTS_1"
        # Toggle financing ON
        r = requests.post(f"{API}/ecps/{ecp_id}/financing",
            json={"financing_required": True}, headers=_hdr(tokens["manager"]))
        assert r.status_code == 200
        e = r.json()["ecp"]
        assert e["current_stage"] == "ACCOUNTS_1", "financing toggle must not regress"
        # loan tasks now applicable
        loan_tasks = [t for t in r.json()["tasks"]
                      if t["task_name"] in ("Loan Documentation", "Loan Filing", "Bank Submission")]
        assert len(loan_tasks) == 3
        assert all(t["applicable"] for t in loan_tasks)
        # RBAC: accounts cannot toggle
        r = requests.post(f"{API}/ecps/{ecp_id}/financing",
            json={"financing_required": False}, headers=_hdr(tokens["accounts"]))
        assert r.status_code == 403


# --------------- CLOSURE ---------------
class TestClosure:
    def test_only_owner_manager_close(self, tokens):
        _, ecp_id = _qualify_and_get_ecp(tokens)
        for role in ["lead", "registration", "accounts", "dispatch", "installation"]:
            r = requests.post(f"{API}/ecps/{ecp_id}/close",
                json={"reason": "DUPLICATE"}, headers=_hdr(tokens[role]))
            assert r.status_code == 403
        # OTHER requires remarks
        r = requests.post(f"{API}/ecps/{ecp_id}/close",
            json={"reason": "OTHER"}, headers=_hdr(tokens["manager"]))
        assert r.status_code == 400
        r = requests.post(f"{API}/ecps/{ecp_id}/close",
            json={"reason": "OTHER", "remarks": "not feasible"}, headers=_hdr(tokens["manager"]))
        assert r.status_code == 200
        # re-close rejected
        r = requests.post(f"{API}/ecps/{ecp_id}/close",
            json={"reason": "DUPLICATE"}, headers=_hdr(tokens["owner"]))
        assert r.status_code == 400


# --------------- SLA ---------------
class TestSLA:
    def test_sla_owner_only(self, tokens):
        r = requests.get(f"{API}/sla", headers=_hdr(tokens["manager"]))
        assert r.status_code == 200
        r = requests.put(f"{API}/sla", json={"config": {"REGISTRATION_1": 5}}, headers=_hdr(tokens["manager"]))
        assert r.status_code == 403
        r = requests.put(f"{API}/sla", json={"config": {"REGISTRATION_1": 5}}, headers=_hdr(tokens["owner"]))
        assert r.status_code == 200
        assert r.json()["REGISTRATION_1"] == 5
        # reset
        requests.put(f"{API}/sla", json={"config": {"REGISTRATION_1": 0}}, headers=_hdr(tokens["owner"]))


# --------------- DASHBOARD ---------------
class TestDashboard:
    def test_each_role_dashboard(self, tokens):
        for role in ["owner", "manager", "lead", "accounts", "dispatch", "installation", "registration"]:
            r = requests.get(f"{API}/dashboard", headers=_hdr(tokens[role]))
            assert r.status_code == 200, f"{role} dashboard failed"
            assert r.json()["role"] == CREDS[role][2]
