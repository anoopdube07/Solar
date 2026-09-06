import requests, sys
B = "http://localhost:8001/api"

def login(u, p):
    r = requests.post(f"{B}/auth/login", json={"username": u, "password": p})
    r.raise_for_status()
    return r.data if False else r.json()["token"]

def H(t): return {"Authorization": f"Bearer {t}"}

def check(r, ctx):
    if r.status_code >= 400:
        print("FAIL", ctx, r.status_code, r.text[:200]); sys.exit(1)
    return r.json()

owner = login("anoopdube07@gmail.com", "Owner@123")
lead = login("lead", "Lead@123")
manager = login("manager", "Manager@123")
reg = login("registration", "Reg@123")
acct = login("accounts", "Acct@123")
disp = login("dispatch", "Disp@123")
inst = login("installation", "Install@123")

# skip if already seeded
existing = check(requests.get(f"{B}/leads", headers=H(lead)), "list leads")
if len(existing) >= 6:
    print("Already seeded:", len(existing), "leads"); sys.exit(0)

def mk_lead(name, phone, fin=False):
    return check(requests.post(f"{B}/leads", headers=H(lead), json={"name": name, "phone": phone, "financing_required": fin}), "create lead")

# 1) A fully-progressed ECP
l1 = mk_lead("Ramesh Solar Villa", "9800000001", fin=True)
check(requests.post(f"{B}/leads/{l1['id']}/action", headers=H(lead), json={"action": "YES"}), "qualify l1")
b1 = check(requests.get(f"{B}/leads/{l1['id']}", headers=H(lead)), "bundle l1")
ecp1 = b1["ecp"]["id"]
# complete REG1 tasks (base + financing)
det = check(requests.get(f"{B}/ecps/{ecp1}", headers=H(reg)), "ecp1")
for t in det["tasks"]:
    if t["applicable"] and t["stage"] == "REGISTRATION_1":
        check(requests.post(f"{B}/ecps/{ecp1}/tasks/{t['id']}/complete", headers=H(reg)), "reg1 task")
# ACCOUNTS 1: advance verification
det = check(requests.get(f"{B}/ecps/{ecp1}", headers=H(acct)), "ecp1 acc")
for t in det["tasks"]:
    if t["stage"] == "ACCOUNTS_1" and t["applicable"]:
        check(requests.post(f"{B}/ecps/{ecp1}/tasks/{t['id']}/complete", headers=H(acct)), "acc1 task")
# Now DISPATCH: add first payment confirmed
check(requests.post(f"{B}/payments", headers=H(acct), json={"ecp_id": ecp1, "type": "FIRST", "amount": 150000, "date": "2026-06-01", "status": "CONFIRMED"}), "first pay")
check(requests.post(f"{B}/ecps/{ecp1}/start-dispatch", headers=H(disp)), "start dispatch")
det = check(requests.get(f"{B}/ecps/{ecp1}", headers=H(disp)), "ecp1 disp")
for t in det["tasks"]:
    if t["stage"] == "DISPATCH" and t["applicable"]:
        check(requests.post(f"{B}/ecps/{ecp1}/tasks/{t['id']}/complete", headers=H(disp)), "disp task")
# INSTALLATION
check(requests.post(f"{B}/ecps/{ecp1}/installation", headers=H(inst), json={"action": "start"}), "inst start")
check(requests.post(f"{B}/ecps/{ecp1}/installation", headers=H(inst), json={"action": "complete"}), "inst complete")
# NET METERING
det = check(requests.get(f"{B}/ecps/{ecp1}", headers=H(inst)), "ecp1 nm")
for t in det["tasks"]:
    if t["stage"] == "NET_METERING" and t["applicable"]:
        check(requests.post(f"{B}/ecps/{ecp1}/tasks/{t['id']}/complete", headers=H(inst)), "nm task")
print("ECP1 progressed to:", check(requests.get(f"{B}/ecps/{ecp1}", headers=H(reg)), "ecp1 final")["ecp"]["current_stage"])

# 2) A payment-blocked dispatch ECP
l2 = mk_lead("Sunita Rooftop", "9800000002")
check(requests.post(f"{B}/leads/{l2['id']}/action", headers=H(lead), json={"action": "YES"}), "qualify l2")
b2 = check(requests.get(f"{B}/leads/{l2['id']}", headers=H(lead)), "bundle l2")
ecp2 = b2["ecp"]["id"]
det = check(requests.get(f"{B}/ecps/{ecp2}", headers=H(reg)), "ecp2")
for t in det["tasks"]:
    if t["stage"] == "REGISTRATION_1" and t["applicable"]:
        check(requests.post(f"{B}/ecps/{ecp2}/tasks/{t['id']}/complete", headers=H(reg)), "reg1")
det = check(requests.get(f"{B}/ecps/{ecp2}", headers=H(acct)), "ecp2 acc")
for t in det["tasks"]:
    if t["stage"] == "ACCOUNTS_1" and t["applicable"]:
        check(requests.post(f"{B}/ecps/{ecp2}/tasks/{t['id']}/complete", headers=H(acct)), "acc1")
# leave payment pending -> payment blocked
check(requests.post(f"{B}/payments", headers=H(acct), json={"ecp_id": ecp2, "type": "FIRST", "amount": 120000, "date": "2026-06-02", "status": "PENDING"}), "first pay pending")

# 3) Follow-up lead
l3 = mk_lead("Deepak Enterprises", "9800000003")
check(requests.post(f"{B}/leads/{l3['id']}/action", headers=H(lead), json={"action": "FOLLOW_UP", "followup_date": "2027-01-20", "remarks": "Call after site inspection quote"}), "followup")

# 4) Site visit lead -> assign -> complete
l4 = mk_lead("Green Homes Co", "9800000004")
check(requests.post(f"{B}/leads/{l4['id']}/action", headers=H(lead), json={"action": "SITE_VISIT", "remarks": "Assess north-facing roof"}), "sitevisit")
svs = check(requests.get(f"{B}/site-visits", headers=H(manager)), "list sv")
inst_users = [u for u in check(requests.get(f"{B}/users", headers=H(owner)), "users") if u["role"] == "INSTALLATION"]
sv = [s for s in svs if s["lead_id"] == l4["id"]][0]
check(requests.post(f"{B}/site-visits/{sv['id']}/assign", headers=H(manager), json={"assigned_user": inst_users[0]["id"], "visit_date": "2027-01-10"}), "assign sv")

# 5) Escalation lead
l5 = mk_lead("Metro Mall Project", "9800000005")
check(requests.post(f"{B}/leads/{l5['id']}/action", headers=H(lead), json={"action": "ESCALATION", "reason": "Pricing approval", "remarks": "Customer wants 12% discount"}), "escalate")

# 6) Lost lead
l6 = mk_lead("Old Town Society", "9800000006")
check(requests.post(f"{B}/leads/{l6['id']}/action", headers=H(lead), json={"action": "NO", "lost_reason": "COMPETITOR"}), "lost")

# SLA config so delayed logic active
check(requests.put(f"{B}/sla", headers=H(owner), json={"config": {"REGISTRATION_1": 5, "ACCOUNTS_1": 3, "DISPATCH": 4, "INSTALLATION": 7, "NET_METERING": 10, "REGISTRATION_2": 5, "ACCOUNTS_2": 5}}), "sla")

print("SEED DONE")
