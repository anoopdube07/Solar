from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import io
import uuid
import logging
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import Optional, List

from auth import (
    hash_password, verify_password, create_access_token, decode_token, extract_token,
)
import workflow as wf
from extras import ist_today_str, ist_day_bounds, to_csv
from fastapi.responses import Response

# ---- DB ----
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

app = FastAPI()
api = APIRouter(prefix="/api")
logger = logging.getLogger("ecp")
logging.basicConfig(level=logging.INFO)

NO_ID = {"_id": 0}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


# ========================= AUTH =========================
async def get_current_user(request: Request) -> dict:
    token = extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await db.users.find_one({"id": payload.get("sub")}, NO_ID)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Account is deactivated")
    user.pop("password_hash", None)
    return user


def require(user: dict, *roles):
    if user["role"] not in roles:
        raise HTTPException(status_code=403, detail="You do not have permission for this action")


class LoginBody(BaseModel):
    username: str
    password: str


@api.post("/auth/login")
async def login(body: LoginBody):
    user = await db.users.find_one({"username": body.username.strip().lower()})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Account is deactivated")
    token = create_access_token(user["id"], user["username"])
    user.pop("password_hash", None)
    user.pop("_id", None)
    return {"token": token, "user": user}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ========================= USERS (Owner only) =========================
class UserCreate(BaseModel):
    username: str
    password: str
    name: str
    role: str
    phone: str
    team: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    team: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None


def public_user(u: dict):
    u.pop("password_hash", None)
    u.pop("_id", None)
    return u


@api.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    users = await db.users.find({}, NO_ID).to_list(1000)
    for u in users:
        u.pop("password_hash", None)
    return users


@api.get("/users/team/{role}")
async def list_team_users(role: str, user: dict = Depends(get_current_user)):
    require(user, "OWNER", "MANAGER")
    if role not in wf.ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    users = await db.users.find({"role": role, "active": True}, NO_ID).to_list(1000)
    return [{"id": u["id"], "name": u["name"], "username": u["username"], "role": u["role"]} for u in users]


@api.post("/users")
async def create_user(body: UserCreate, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    if body.role not in wf.ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if not (body.phone or "").strip():
        raise HTTPException(status_code=400, detail="Phone number is required")
    username = body.username.strip().lower()
    if await db.users.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="Username already exists")
    doc = {
        "id": new_id(),
        "username": username,
        "password_hash": hash_password(body.password),
        "name": body.name.strip(),
        "role": body.role,
        "team": body.role,  # one user = one role = one team
        "phone": body.phone.strip(),
        "active": True,
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    return public_user(dict(doc))


@api.patch("/users/{user_id}")
async def update_user(user_id: str, body: UserUpdate, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    upd = {}
    if body.name is not None:
        upd["name"] = body.name.strip()
    if body.role is not None:
        if body.role not in wf.ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        upd["role"] = body.role
        upd["team"] = body.role
    if body.active is not None:
        upd["active"] = body.active
    if body.password:
        upd["password_hash"] = hash_password(body.password)
    if body.phone is not None:
        upd["phone"] = body.phone.strip()
    if upd:
        await db.users.update_one({"id": user_id}, {"$set": upd})
    fresh = await db.users.find_one({"id": user_id}, NO_ID)
    fresh.pop("password_hash", None)
    return fresh


# ========================= SLA CONFIG (Owner only to edit) =========================
class SLABody(BaseModel):
    config: dict  # {stage: days}


@api.get("/sla")
async def get_sla(user: dict = Depends(get_current_user)):
    docs = await db.stage_sla_config.find({}, NO_ID).to_list(100)
    cfg = {d["stage"]: d["sla_days"] for d in docs}
    for s in wf.STAGE_ORDER:
        cfg.setdefault(s, 0)
    return cfg


@api.put("/sla")
async def set_sla(body: SLABody, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    for stage, days in body.config.items():
        if stage not in wf.STAGE_ORDER:
            continue
        await db.stage_sla_config.update_one(
            {"stage": stage}, {"$set": {"stage": stage, "sla_days": int(days)}}, upsert=True
        )
    return await get_sla(user)


async def get_sla_map():
    docs = await db.stage_sla_config.find({}, NO_ID).to_list(100)
    return {d["stage"]: d["sla_days"] for d in docs}


# ========================= LEADS =========================
class LeadCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = ""
    address: Optional[str] = ""
    source: Optional[str] = ""
    financing_required: bool = False
    project_price: Optional[float] = 0
    lead_creator_id: Optional[str] = None
    item_id: Optional[str] = None
    quantity: Optional[float] = None
    location_link: Optional[str] = ""
    remarks: Optional[str] = ""


class ProjectPriceBody(BaseModel):
    project_price: float


class LeadAction(BaseModel):
    action: str
    lost_reason: Optional[str] = None
    lost_remarks: Optional[str] = None
    followup_date: Optional[str] = None
    remarks: Optional[str] = None
    reason: Optional[str] = None


def lead_visible_roles():
    return ["OWNER", "MANAGER", "LEAD"]


@api.get("/leads")
async def list_leads(status: Optional[str] = None, followup: Optional[str] = None, user: dict = Depends(get_current_user)):
    if user["role"] not in lead_visible_roles():
        # other teams get read-only limited visibility (qualified leads linked to ECPs they see)
        return []
    q = {}
    if status:
        q["status"] = status
    if followup == "today":
        today = ist_today_str()
        fus = await db.lead_followups.find({}, NO_ID).to_list(10000)
        lead_ids = list({f["lead_id"] for f in fus if (f.get("followup_date") or "")[:10] == today})
        q["id"] = {"$in": lead_ids}
        q["status"] = "FOLLOW_UP"
    leads = await db.leads.find(q, NO_ID).sort("created_at", -1).to_list(2000)
    if user["role"] == "LEAD":
        leads = [l for l in leads if l.get("lead_owner_id") in (user["id"], None)]
    return leads


@api.post("/leads")
async def create_lead(body: LeadCreate, user: dict = Depends(get_current_user)):
    require(user, "LEAD", "OWNER")
    creator_id, creator_name = None, None
    if body.lead_creator_id:
        emp = await db.lead_employees.find_one({"id": body.lead_creator_id}, NO_ID)
        if not emp or not emp.get("active", True):
            raise HTTPException(status_code=400, detail="Invalid or inactive Lead Creator")
        creator_id, creator_name = emp["id"], emp["name"]
    # Duplicate active-lead check (server-side): ACTIVE = any status except LOST
    phone = body.phone.strip()
    dup = await db.leads.find_one({"phone": phone, "status": {"$ne": "LOST"}}, NO_ID)
    if dup:
        raise HTTPException(status_code=409, detail=f"An active lead already exists for {phone} ({dup['name']})")
    item_name, item_unit = None, None
    if body.item_id:
        it = await db.items.find_one({"id": body.item_id}, NO_ID)
        if not it or not it.get("active", True):
            raise HTTPException(status_code=400, detail="Invalid or inactive item")
        item_name, item_unit = it["name"], it["unit"]
    await enforce_lead_mandatory(body, item_name)
    doc = {
        "id": new_id(),
        "name": body.name.strip(),
        "phone": phone,
        "email": (body.email or "").strip(),
        "address": (body.address or "").strip(),
        "source": (body.source or "").strip(),
        "remarks": (body.remarks or "").strip(),
        "item_id": body.item_id,
        "item_name": item_name,
        "item_unit": item_unit,
        "quantity": body.quantity,
        "location_link": (body.location_link or "").strip(),
        "status": "PENDING",
        "current_team": "LEAD",
        "action_required": True,
        "return_reason": None,
        "financing_required": bool(body.financing_required),
        "project_price": float(body.project_price or 0),
        "lead_creator_id": creator_id,
        "lead_creator_name": creator_name,
        "lead_owner_id": user["id"],
        "lead_owner_name": user["name"],
        "lost_reason": None,
        "lost_remarks": None,
        "ecp_id": None,
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.leads.insert_one(doc)
    await log_activity(user, "Lead Created", "LEAD", doc["id"], doc["name"], f"Creator: {creator_name or '—'}")
    d = dict(doc)
    d.pop("_id", None)
    return d


async def _lead_bundle(lead_id: str):
    lead = await db.leads.find_one({"id": lead_id}, NO_ID)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    followups = await db.lead_followups.find({"lead_id": lead_id}, NO_ID).sort("created_at", -1).to_list(500)
    site_visits = await db.lead_site_visits.find({"lead_id": lead_id}, NO_ID).sort("created_at", -1).to_list(500)
    escalations = await db.lead_escalations.find({"lead_id": lead_id}, NO_ID).sort("created_at", -1).to_list(500)
    ecp = None
    if lead.get("ecp_id"):
        ecp = await db.ecps.find_one({"id": lead["ecp_id"]}, NO_ID)
    return {"lead": lead, "followups": followups, "site_visits": site_visits,
            "escalations": escalations, "ecp": ecp}


@api.get("/leads/{lead_id}")
async def get_lead(lead_id: str, user: dict = Depends(get_current_user)):
    require(user, "OWNER", "MANAGER", "LEAD")
    lead = await db.leads.find_one({"id": lead_id}, NO_ID)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if user["role"] == "LEAD" and lead.get("lead_owner_id") not in (user["id"], None):
        raise HTTPException(status_code=403, detail="This lead is not assigned to you")
    return await _lead_bundle(lead_id)


class ReassignLead(BaseModel):
    assigned_user: str


@api.post("/leads/{lead_id}/reassign")
async def reassign_lead(lead_id: str, body: ReassignLead, user: dict = Depends(get_current_user)):
    require(user, "MANAGER", "OWNER")
    lead = await db.leads.find_one({"id": lead_id}, NO_ID)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    emp = await db.users.find_one({"id": body.assigned_user}, NO_ID)
    if not emp or emp["role"] != "LEAD" or not emp.get("active", True):
        raise HTTPException(status_code=400, detail="Assignee must be an active Lead Team user")
    prev = lead.get("lead_owner_name") or "—"
    await db.leads.update_one({"id": lead_id}, {"$set": {
        "lead_owner_id": emp["id"], "lead_owner_name": emp["name"], "updated_at": now_iso()}})
    await log_activity(user, "Lead Reassigned", "LEAD", lead_id, lead["name"], f"{prev} → {emp['name']}")
    return await _lead_bundle(lead_id)


@api.post("/leads/{lead_id}/project-price")
async def set_project_price(lead_id: str, body: ProjectPriceBody, user: dict = Depends(get_current_user)):
    require(user, "LEAD", "OWNER")
    lead = await db.leads.find_one({"id": lead_id}, NO_ID)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.get("ecp_id"):
        raise HTTPException(status_code=400, detail="Lead already handed off. Use a Commercial Change request to modify price.")
    if user["role"] == "LEAD" and lead.get("lead_owner_id") not in (user["id"], None):
        raise HTTPException(status_code=403, detail="This lead is not assigned to you")
    price = float(body.project_price or 0)
    await db.leads.update_one({"id": lead_id}, {"$set": {"project_price": price, "updated_at": now_iso()}})
    return await _lead_bundle(lead_id)


async def create_ecp_from_lead(lead: dict, user: dict):
    financing = bool(lead.get("financing_required"))
    ecp_id = new_id()
    ecp = {
        "id": ecp_id,
        "lead_id": lead["id"],
        "lead_name": lead["name"],
        "customer_phone": lead.get("phone", ""),
        "project_price": float(lead.get("project_price") or 0),
        "lead_creator_id": lead.get("lead_creator_id"),
        "lead_creator_name": lead.get("lead_creator_name"),
        "lead_owner_id": lead.get("lead_owner_id"),
        "lead_owner_name": lead.get("lead_owner_name"),
        "current_stage": "REGISTRATION_1",
        "current_team": wf.STAGE_TEAM["REGISTRATION_1"],
        "responsible_user": None,
        "responsible_user_name": None,
        "financing_required": financing,
        "status": "ACTIVE",
        "dispatch_started": False,
        "install_status": None,
        "stage_entry_date": now_iso(),
        "closed_at": None,
        "closed_by": None,
        "closure_reason": None,
        "closure_remarks": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.ecps.insert_one(ecp)
    # tasks for registration 1
    tasks = list(wf.REG1_BASE_TASKS)
    task_docs = []
    for t in tasks:
        task_docs.append(_make_task(ecp_id, "REGISTRATION_1", t, True))
    for t in wf.REG1_FINANCING_TASKS:
        task_docs.append(_make_task(ecp_id, "REGISTRATION_1", t, financing))
    if task_docs:
        await db.ecp_tasks.insert_many(task_docs)
    await db.ecp_stage_history.insert_one({
        "id": new_id(), "ecp_id": ecp_id, "from_stage": None, "to_stage": "REGISTRATION_1",
        "changed_by": user["id"], "changed_by_name": user["name"], "changed_at": now_iso(),
        "note": "ECP created from qualified lead",
    })
    return ecp_id


def _make_task(ecp_id, stage, name, applicable):
    return {
        "id": new_id(), "ecp_id": ecp_id, "stage": stage, "task_name": name,
        "applicable": applicable, "completed": False, "completed_by": None,
        "completed_by_name": None, "completed_at": None,
    }


@api.post("/leads/{lead_id}/action")
async def lead_action(lead_id: str, body: LeadAction, user: dict = Depends(get_current_user)):
    require(user, "LEAD")  # Only Lead Team decides the 5 actions (Phase 1 spec D)
    lead = await db.leads.find_one({"id": lead_id}, NO_ID)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.get("lead_owner_id") not in (user["id"], None):
        raise HTTPException(status_code=403, detail="This lead is not assigned to you")
    if lead["status"] in ("QUALIFIED", "LOST") and not lead.get("action_required"):
        raise HTTPException(status_code=400, detail="Lead is not currently actionable")
    action = body.action
    if action not in wf.LEAD_ACTIONS:
        raise HTTPException(status_code=400, detail="Invalid action")

    if action == "YES":
        if lead.get("ecp_id"):
            raise HTTPException(status_code=400, detail="Lead already has an ECP")
        ecp_id = await create_ecp_from_lead(lead, user)
        await db.leads.update_one({"id": lead_id}, {"$set": {
            "status": "QUALIFIED", "action_required": False, "current_team": None,
            "return_reason": None, "ecp_id": ecp_id, "updated_at": now_iso()}})

    elif action == "NO":
        if not body.lost_reason:
            raise HTTPException(status_code=400, detail="Lost reason is required")
        if body.lost_reason == "OTHER" and not (body.lost_remarks or "").strip():
            raise HTTPException(status_code=400, detail="Remarks are mandatory when reason is OTHER")
        await db.leads.update_one({"id": lead_id}, {"$set": {
            "status": "LOST", "action_required": False, "current_team": None,
            "lost_reason": body.lost_reason, "lost_remarks": (body.lost_remarks or "").strip(),
            "updated_at": now_iso()}})

    elif action == "FOLLOW_UP":
        if not body.followup_date:
            raise HTTPException(status_code=400, detail="Follow-up date is required")
        if not (body.remarks or "").strip():
            raise HTTPException(status_code=400, detail="Remarks are required")
        try:
            fdate = datetime.fromisoformat(body.followup_date).date()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid follow-up date")
        if fdate < datetime.now(timezone.utc).date():
            raise HTTPException(status_code=400, detail="Follow-up date cannot be in the past")
        await db.lead_followups.insert_one({
            "id": new_id(), "lead_id": lead_id, "followup_date": body.followup_date,
            "remarks": body.remarks.strip(), "created_by": user["id"],
            "created_by_name": user["name"], "created_at": now_iso()})
        await db.leads.update_one({"id": lead_id}, {"$set": {
            "status": "FOLLOW_UP", "action_required": True, "current_team": "LEAD",
            "return_reason": None, "updated_at": now_iso()}})

    elif action == "SITE_VISIT":
        open_sv = await db.lead_site_visits.find_one(
            {"lead_id": lead_id, "status": {"$in": ["REQUESTED", "ASSIGNED"]}})
        if open_sv:
            raise HTTPException(status_code=400, detail="An open site visit already exists for this lead")
        await db.lead_site_visits.insert_one({
            "id": new_id(), "lead_id": lead_id, "lead_name": lead["name"],
            "status": "REQUESTED", "assigned_user": None, "assigned_user_name": None,
            "visit_date": None, "survey_info": None, "requested_remarks": (body.remarks or "").strip(),
            "requested_by": user["id"], "requested_by_name": user["name"],
            "assigned_by": None, "created_at": now_iso(), "completed_at": None})
        await db.leads.update_one({"id": lead_id}, {"$set": {
            "status": "SITE_VISIT", "action_required": False,
            "current_team": "INSTALLATION", "return_reason": None, "updated_at": now_iso()}})

    elif action == "ESCALATION":
        if not (body.reason or "").strip():
            raise HTTPException(status_code=400, detail="Escalation reason is required")
        if not (body.remarks or "").strip():
            raise HTTPException(status_code=400, detail="Escalation remarks are required")
        await db.lead_escalations.insert_one({
            "id": new_id(), "lead_id": lead_id, "lead_name": lead["name"],
            "reason": body.reason.strip(), "remarks": body.remarks.strip(),
            "owner_remarks": None, "status": "OPEN", "created_by": user["id"],
            "created_by_name": user["name"], "created_at": now_iso(), "returned_at": None})
        await db.leads.update_one({"id": lead_id}, {"$set": {
            "status": "ESCALATED", "action_required": False, "current_team": "OWNER",
            "return_reason": None, "updated_at": now_iso()}})

    await log_activity(user, f"Lead Action: {action}", "LEAD", lead_id, lead["name"],
                       body.remarks or body.reason or body.lost_reason or "")
    return await _lead_bundle(lead_id)


@api.post("/leads/{lead_id}/reopen")
async def reopen_lead(lead_id: str, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    lead = await db.leads.find_one({"id": lead_id}, NO_ID)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead["status"] != "LOST":
        raise HTTPException(status_code=400, detail="Only LOST leads can be reopened")
    await db.leads.update_one({"id": lead_id}, {"$set": {
        "status": "PENDING", "action_required": True, "current_team": "LEAD",
        "return_reason": "REOPENED", "lost_reason": None, "lost_remarks": None,
        "updated_at": now_iso()}})
    return await _lead_bundle(lead_id)


class FinancingBody(BaseModel):
    financing_required: bool


@api.post("/leads/{lead_id}/financing")
async def lead_financing(lead_id: str, body: FinancingBody, user: dict = Depends(get_current_user)):
    require(user, "LEAD", "MANAGER", "OWNER")
    lead = await db.leads.find_one({"id": lead_id}, NO_ID)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.leads.update_one({"id": lead_id}, {"$set": {
        "financing_required": bool(body.financing_required), "updated_at": now_iso()}})
    if lead.get("ecp_id"):
        await _apply_ecp_financing(lead["ecp_id"], bool(body.financing_required), user)
    return await _lead_bundle(lead_id)


# ========================= SITE VISITS =========================
@api.get("/site-visits")
async def list_site_visits(user: dict = Depends(get_current_user)):
    if user["role"] in ("OWNER", "MANAGER"):
        visits = await db.lead_site_visits.find({}, NO_ID).sort("created_at", -1).to_list(2000)
    elif user["role"] == "INSTALLATION":
        visits = await db.lead_site_visits.find(
            {"assigned_user": user["id"]}, NO_ID).sort("created_at", -1).to_list(2000)
    else:
        visits = []
    return visits


class AssignSiteVisit(BaseModel):
    assigned_user: str
    visit_date: str


@api.post("/site-visits/{sv_id}/assign")
async def assign_site_visit(sv_id: str, body: AssignSiteVisit, user: dict = Depends(get_current_user)):
    require(user, "MANAGER", "OWNER")
    sv = await db.lead_site_visits.find_one({"id": sv_id}, NO_ID)
    if not sv:
        raise HTTPException(status_code=404, detail="Site visit not found")
    if sv["status"] not in ("REQUESTED", "ASSIGNED"):
        raise HTTPException(status_code=400, detail="Site visit is not open")
    emp = await db.users.find_one({"id": body.assigned_user}, NO_ID)
    if not emp or emp["role"] != "INSTALLATION":
        raise HTTPException(status_code=400, detail="Assignee must be an Installation team member")
    await db.lead_site_visits.update_one({"id": sv_id}, {"$set": {
        "status": "ASSIGNED", "assigned_user": body.assigned_user,
        "assigned_user_name": emp["name"], "visit_date": body.visit_date,
        "assigned_by": user["id"], "assigned_by_name": user["name"]}})
    await log_activity(user, "Site Visit Assigned", "LEAD", sv["lead_id"], sv.get("lead_name", ""), f"To {emp['name']}")
    return await db.lead_site_visits.find_one({"id": sv_id}, NO_ID)


class CompleteSiteVisit(BaseModel):
    survey_info: str


@api.post("/site-visits/{sv_id}/complete")
async def complete_site_visit(sv_id: str, body: CompleteSiteVisit, user: dict = Depends(get_current_user)):
    require(user, "INSTALLATION", "OWNER")
    sv = await db.lead_site_visits.find_one({"id": sv_id}, NO_ID)
    if not sv:
        raise HTTPException(status_code=404, detail="Site visit not found")
    if sv["status"] != "ASSIGNED":
        raise HTTPException(status_code=400, detail="Only assigned site visits can be completed")
    if user["role"] == "INSTALLATION" and sv["assigned_user"] != user["id"]:
        raise HTTPException(status_code=403, detail="This site visit is not assigned to you")
    if not (body.survey_info or "").strip():
        raise HTTPException(status_code=400, detail="Survey information is required")
    await db.lead_site_visits.update_one({"id": sv_id}, {"$set": {
        "status": "DONE", "survey_info": body.survey_info.strip(), "completed_at": now_iso()}})
    # lead returns to Lead Team, action required
    await db.leads.update_one({"id": sv["lead_id"]}, {"$set": {
        "status": "PENDING", "action_required": True, "current_team": "LEAD",
        "return_reason": "SITE_VISIT_COMPLETED", "updated_at": now_iso()}})
    await log_activity(user, "Site Visit Completed", "LEAD", sv["lead_id"], sv.get("lead_name", ""), "")
    return await db.lead_site_visits.find_one({"id": sv_id}, NO_ID)


# ========================= ESCALATIONS =========================
@api.get("/escalations")
async def list_escalations(user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    return await db.lead_escalations.find({}, NO_ID).sort("created_at", -1).to_list(2000)


class ReturnEscalation(BaseModel):
    owner_remarks: str


@api.post("/escalations/{esc_id}/return")
async def return_escalation(esc_id: str, body: ReturnEscalation, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    esc = await db.lead_escalations.find_one({"id": esc_id}, NO_ID)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if esc["status"] != "OPEN":
        raise HTTPException(status_code=400, detail="Escalation already handled")
    if not (body.owner_remarks or "").strip():
        raise HTTPException(status_code=400, detail="Owner remarks are mandatory")
    await db.lead_escalations.update_one({"id": esc_id}, {"$set": {
        "status": "RETURNED", "owner_remarks": body.owner_remarks.strip(), "returned_at": now_iso()}})
    await db.leads.update_one({"id": esc["lead_id"]}, {"$set": {
        "status": "PENDING", "action_required": True, "current_team": "LEAD",
        "return_reason": "OWNER_RETURNED", "updated_at": now_iso()}})
    await log_activity(user, "Escalation Returned", "LEAD", esc["lead_id"], esc.get("lead_name", ""), "Owner remarks added")
    return await db.lead_escalations.find_one({"id": esc_id}, NO_ID)


# ========================= ECP =========================
async def first_payment_confirmed(ecp_id: str) -> bool:
    p = await db.payments.find_one({"ecp_id": ecp_id, "type": "FIRST", "status": "CONFIRMED"})
    return p is not None


async def final_payment_confirmed(ecp_id: str) -> bool:
    p = await db.payments.find_one({"ecp_id": ecp_id, "type": "FINAL", "status": "CONFIRMED"})
    return p is not None


async def enrich_ecp(ecp: dict, sla_map: dict = None):
    if sla_map is None:
        sla_map = await get_sla_map()
    stage = ecp["current_stage"]
    display = wf.STAGE_LABELS.get(stage, stage)
    derived = None
    if ecp["status"] == "CLOSED":
        display = "Closed / Cancelled"
    elif ecp["status"] == "COMPLETED":
        display = "Successfully Completed"
    elif stage == "DISPATCH":
        if not ecp.get("dispatch_started"):
            fp = await first_payment_confirmed(ecp["id"])
            derived = "READY_FOR_DISPATCH" if fp else "PAYMENT_BLOCKED"
        else:
            derived = "DISPATCH_IN_PROCESS"
    elif stage == "INSTALLATION":
        derived = ecp.get("install_status") or "READY_TO_INSTALL"
    # delayed
    delayed = False
    days_in_stage = None
    if ecp["status"] == "ACTIVE" and ecp.get("stage_entry_date"):
        sla_days = sla_map.get(stage, 0)
        entry = datetime.fromisoformat(ecp["stage_entry_date"])
        days_in_stage = (datetime.now(timezone.utc) - entry).days
        if sla_days and sla_days > 0:
            due = entry + timedelta(days=sla_days)
            if datetime.now(timezone.utc) > due:
                delayed = True
    ecp["stage_label"] = wf.STAGE_LABELS.get(stage, stage)
    ecp["display_status"] = display
    ecp["derived_status"] = derived
    ecp["delayed"] = delayed
    ecp["days_in_stage"] = days_in_stage
    ecp["first_payment_confirmed"] = await first_payment_confirmed(ecp["id"])
    ecp["final_payment_confirmed"] = await final_payment_confirmed(ecp["id"])
    return ecp


ALLOWED_STAGES = {
    "REGISTRATION": ["REGISTRATION_1", "REGISTRATION_2"],
    "DISPATCH": ["DISPATCH"],
    "INSTALLATION": ["INSTALLATION", "NET_METERING"],
}


def ecp_filter_for_role(user: dict):
    role = user["role"]
    if role in ("OWNER", "MANAGER", "LEAD", "ACCOUNTS"):
        return {}
    if role == "REGISTRATION":
        return {"current_stage": {"$in": ALLOWED_STAGES["REGISTRATION"]}}
    if role == "DISPATCH":
        return {"current_stage": "DISPATCH"}
    if role == "INSTALLATION":
        return {"current_stage": {"$in": ALLOWED_STAGES["INSTALLATION"]}, "responsible_user": user["id"]}
    return {"id": "__none__"}


def _matches_view(e: dict, view: str) -> bool:
    if view in ("PAYMENT_BLOCKED", "READY_FOR_DISPATCH", "DISPATCH_IN_PROCESS",
                "READY_TO_INSTALL", "IN_PROCESS", "AWAITING_ASSIGNMENT"):
        return e.get("derived_status") == view and e["status"] == "ACTIVE"
    if view == "PAST_DISPATCH":
        return (e["current_stage"] in ("INSTALLATION", "NET_METERING", "REGISTRATION_2", "ACCOUNTS_2")
                or e["status"] in ("COMPLETED", "CLOSED"))
    if view == "DELAYED":
        return bool(e.get("delayed"))
    if view == "CLOSED":
        return e["status"] == "CLOSED"
    if view == "COMPLETED":
        return e["status"] == "COMPLETED"
    return True


@api.get("/ecps")
async def list_ecps(stage: Optional[str] = None, view: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = ecp_filter_for_role(user)
    if stage:
        allowed = ALLOWED_STAGES.get(user["role"])
        if allowed is None or stage in allowed:
            q = {**q, "current_stage": stage}
    ecps = await db.ecps.find(q, NO_ID).sort("created_at", -1).to_list(3000)
    sla_map = await get_sla_map()
    for e in ecps:
        await enrich_ecp(e, sla_map)
    if view:
        ecps = [e for e in ecps if _matches_view(e, view)]
    return ecps


@api.get("/ecps/{ecp_id}")
async def get_ecp(ecp_id: str, user: dict = Depends(get_current_user)):
    ecp = await db.ecps.find_one({"id": ecp_id}, NO_ID)
    if not ecp:
        raise HTTPException(status_code=404, detail="ECP not found")
    await enrich_ecp(ecp)
    tasks = await db.ecp_tasks.find({"ecp_id": ecp_id}, NO_ID).to_list(500)
    history = await db.ecp_stage_history.find({"ecp_id": ecp_id}, NO_ID).sort("changed_at", 1).to_list(500)
    payments = await db.payments.find({"ecp_id": ecp_id}, NO_ID).sort("date", -1).to_list(500)
    return {"ecp": ecp, "tasks": tasks, "history": history, "payments": payments}


async def _advance_stage(ecp: dict, user: dict, note: str = ""):
    target = wf.next_stage(ecp["current_stage"])
    from_stage = ecp["current_stage"]
    upd = {"updated_at": now_iso()}
    if target == "COMPLETED":
        upd.update({"status": "COMPLETED", "current_stage": "ACCOUNTS_2",
                    "current_team": None, "updated_at": now_iso(),
                    "completed_at": now_iso()})
        to_label = "COMPLETED"
    else:
        upd.update({"current_stage": target, "current_team": wf.STAGE_TEAM[target],
                    "stage_entry_date": now_iso(), "responsible_user": None,
                    "responsible_user_name": None})
        to_label = target
        if target == "DISPATCH":
            upd["dispatch_started"] = False
        if target == "INSTALLATION":
            # Dispatch completed -> route to Manager for installation-employee assignment
            upd["install_status"] = "AWAITING_ASSIGNMENT"
            upd["current_team"] = "MANAGER"
        if target == "NET_METERING":
            # keep the assigned installation employee through net metering
            upd["responsible_user"] = ecp.get("responsible_user")
            upd["responsible_user_name"] = ecp.get("responsible_user_name")
        # create tasks for the new stage
        task_names = wf.STAGE_TASKS.get(target, [])
        docs = [_make_task(ecp["id"], target, t, True) for t in task_names]
        if docs:
            await db.ecp_tasks.insert_many(docs)
    await db.ecps.update_one({"id": ecp["id"]}, {"$set": upd})
    await db.ecp_stage_history.insert_one({
        "id": new_id(), "ecp_id": ecp["id"], "from_stage": from_stage, "to_stage": to_label,
        "changed_by": user["id"], "changed_by_name": user["name"], "changed_at": now_iso(),
        "note": note or "Stage advanced"})
    await log_activity(user, "ECP Stage Advanced", "ECP", ecp["id"], ecp.get("lead_name", ""),
                       f"{wf.STAGE_LABELS.get(from_stage, from_stage)} → {wf.STAGE_LABELS.get(to_label, to_label)}")


async def _maybe_advance(ecp_id: str, user: dict):
    ecp = await db.ecps.find_one({"id": ecp_id}, NO_ID)
    if not ecp or ecp["status"] != "ACTIVE":
        return
    stage = ecp["current_stage"]
    tasks = await db.ecp_tasks.find({"ecp_id": ecp_id, "stage": stage, "applicable": True}, NO_ID).to_list(100)

    def all_done():
        return all(t["completed"] for t in tasks) and len(tasks) > 0

    if stage in ("REGISTRATION_1", "ACCOUNTS_1", "NET_METERING", "REGISTRATION_2", "ACCOUNTS_2"):
        if all_done():
            await _advance_stage(ecp, user, note=f"{wf.STAGE_LABELS[stage]} tasks completed")
    elif stage == "DISPATCH":
        if ecp.get("dispatch_started") and all_done():
            await _advance_stage(ecp, user, note="Dispatch completed")


@api.post("/ecps/{ecp_id}/tasks/{task_id}/complete")
async def complete_task(ecp_id: str, task_id: str, user: dict = Depends(get_current_user)):
    ecp = await db.ecps.find_one({"id": ecp_id}, NO_ID)
    if not ecp:
        raise HTTPException(status_code=404, detail="ECP not found")
    if ecp["status"] != "ACTIVE":
        raise HTTPException(status_code=400, detail="ECP is not active")
    task = await db.ecp_tasks.find_one({"id": task_id, "ecp_id": ecp_id}, NO_ID)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    stage_team = wf.STAGE_TEAM.get(task["stage"])
    if user["role"] not in ("OWNER", stage_team):
        raise HTTPException(status_code=403, detail="Only the responsible team can complete this task")
    if user["role"] == "INSTALLATION" and task["stage"] in ("INSTALLATION", "NET_METERING") and ecp.get("responsible_user") != user["id"]:
        raise HTTPException(status_code=403, detail="This project is not assigned to you")
    if task["stage"] != ecp["current_stage"]:
        raise HTTPException(status_code=400, detail="Task does not belong to the current stage")
    if not task["applicable"]:
        raise HTTPException(status_code=400, detail="Task is not applicable")
    if task["stage"] == "DISPATCH" and not ecp.get("dispatch_started"):
        raise HTTPException(status_code=400, detail="Start Dispatch before completing dispatch tasks")
    await db.ecp_tasks.update_one({"id": task_id}, {"$set": {
        "completed": True, "completed_by": user["id"], "completed_by_name": user["name"],
        "completed_at": now_iso()}})
    await _maybe_advance(ecp_id, user)
    return await get_ecp(ecp_id, user)


@api.post("/ecps/{ecp_id}/start-dispatch")
async def start_dispatch(ecp_id: str, user: dict = Depends(get_current_user)):
    require(user, "DISPATCH", "OWNER")
    ecp = await db.ecps.find_one({"id": ecp_id}, NO_ID)
    if not ecp:
        raise HTTPException(status_code=404, detail="ECP not found")
    if ecp["current_stage"] != "DISPATCH":
        raise HTTPException(status_code=400, detail="ECP is not in Dispatch stage")
    if ecp.get("dispatch_started"):
        raise HTTPException(status_code=400, detail="Dispatch already started")
    if not await first_payment_confirmed(ecp_id):
        raise HTTPException(status_code=400, detail="First Payment must be CONFIRMED before starting dispatch")
    await db.ecps.update_one({"id": ecp_id}, {"$set": {"dispatch_started": True, "updated_at": now_iso()}})
    await db.ecp_stage_history.insert_one({
        "id": new_id(), "ecp_id": ecp_id, "from_stage": "DISPATCH", "to_stage": "DISPATCH",
        "changed_by": user["id"], "changed_by_name": user["name"], "changed_at": now_iso(),
        "note": "Dispatch started (First Payment confirmed)"})
    return await get_ecp(ecp_id, user)


class InstallBody(BaseModel):
    action: str  # start | complete


class AssignInstallation(BaseModel):
    assigned_user: str


@api.post("/ecps/{ecp_id}/assign-installation")
async def assign_installation(ecp_id: str, body: AssignInstallation, user: dict = Depends(get_current_user)):
    require(user, "MANAGER", "OWNER")
    ecp = await db.ecps.find_one({"id": ecp_id}, NO_ID)
    if not ecp:
        raise HTTPException(status_code=404, detail="ECP not found")
    if ecp["current_stage"] != "INSTALLATION" or ecp.get("install_status") != "AWAITING_ASSIGNMENT":
        raise HTTPException(status_code=400, detail="ECP is not awaiting installation assignment")
    emp = await db.users.find_one({"id": body.assigned_user}, NO_ID)
    if not emp or emp["role"] != "INSTALLATION" or not emp.get("active", True):
        raise HTTPException(status_code=400, detail="Assignee must be an active Installation team member")
    await db.ecps.update_one({"id": ecp_id}, {"$set": {
        "responsible_user": emp["id"], "responsible_user_name": emp["name"],
        "current_team": "INSTALLATION", "install_status": "READY_TO_INSTALL", "updated_at": now_iso()}})
    await db.ecp_stage_history.insert_one({
        "id": new_id(), "ecp_id": ecp_id, "from_stage": "INSTALLATION", "to_stage": "INSTALLATION",
        "changed_by": user["id"], "changed_by_name": user["name"], "changed_at": now_iso(),
        "note": f"Installation assigned to {emp['name']}"})
    await log_activity(user, "Installation Assigned", "ECP", ecp_id, ecp.get("lead_name", ""), f"To {emp['name']}")
    return await get_ecp(ecp_id, user)


@api.post("/ecps/{ecp_id}/installation")
async def installation_action(ecp_id: str, body: InstallBody, user: dict = Depends(get_current_user)):
    require(user, "INSTALLATION", "OWNER")
    ecp = await db.ecps.find_one({"id": ecp_id}, NO_ID)
    if not ecp:
        raise HTTPException(status_code=404, detail="ECP not found")
    if ecp["current_stage"] != "INSTALLATION":
        raise HTTPException(status_code=400, detail="ECP is not in Installation stage")
    if user["role"] == "INSTALLATION" and ecp.get("responsible_user") != user["id"]:
        raise HTTPException(status_code=403, detail="This installation is not assigned to you")
    if body.action == "start":
        if ecp.get("install_status") != "READY_TO_INSTALL":
            raise HTTPException(status_code=400, detail="Installation is not ready to start")
        await db.ecps.update_one({"id": ecp_id}, {"$set": {"install_status": "IN_PROCESS", "updated_at": now_iso()}})
    elif body.action == "complete":
        if ecp.get("install_status") != "IN_PROCESS":
            raise HTTPException(status_code=400, detail="Installation must be in process to complete")
        await db.ecps.update_one({"id": ecp_id}, {"$set": {"install_status": "COMPLETED", "updated_at": now_iso()}})
        fresh = await db.ecps.find_one({"id": ecp_id}, NO_ID)
        await _advance_stage(fresh, user, note="Installation completed")
    else:
        raise HTTPException(status_code=400, detail="Invalid installation action")
    return await get_ecp(ecp_id, user)


async def _apply_ecp_financing(ecp_id: str, financing: bool, user: dict):
    ecp = await db.ecps.find_one({"id": ecp_id}, NO_ID)
    if not ecp:
        return
    await db.ecps.update_one({"id": ecp_id}, {"$set": {"financing_required": financing, "updated_at": now_iso()}})
    for t in wf.REG1_FINANCING_TASKS:
        existing = await db.ecp_tasks.find_one({"ecp_id": ecp_id, "task_name": t})
        if existing:
            await db.ecp_tasks.update_one({"id": existing["id"]}, {"$set": {"applicable": financing}})
        elif financing:
            await db.ecp_tasks.insert_one(_make_task(ecp_id, "REGISTRATION_1", t, True))


@api.post("/ecps/{ecp_id}/financing")
async def ecp_financing(ecp_id: str, body: FinancingBody, user: dict = Depends(get_current_user)):
    require(user, "LEAD", "MANAGER", "OWNER")
    ecp = await db.ecps.find_one({"id": ecp_id}, NO_ID)
    if not ecp:
        raise HTTPException(status_code=404, detail="ECP not found")
    await _apply_ecp_financing(ecp_id, bool(body.financing_required), user)
    await db.leads.update_one({"id": ecp["lead_id"]}, {"$set": {
        "financing_required": bool(body.financing_required)}})
    return await get_ecp(ecp_id, user)


class CloseBody(BaseModel):
    reason: str
    remarks: Optional[str] = None


@api.post("/ecps/{ecp_id}/close")
async def close_ecp(ecp_id: str, body: CloseBody, user: dict = Depends(get_current_user)):
    require(user, "OWNER", "MANAGER")
    ecp = await db.ecps.find_one({"id": ecp_id}, NO_ID)
    if not ecp:
        raise HTTPException(status_code=404, detail="ECP not found")
    if ecp["status"] in ("CLOSED", "COMPLETED"):
        raise HTTPException(status_code=400, detail="ECP is already closed")
    if not body.reason:
        raise HTTPException(status_code=400, detail="Closure reason is required")
    if body.reason == "OTHER" and not (body.remarks or "").strip():
        raise HTTPException(status_code=400, detail="Remarks are mandatory when reason is OTHER")
    await db.ecps.update_one({"id": ecp_id}, {"$set": {
        "status": "CLOSED", "current_team": None, "closed_at": now_iso(),
        "closed_by": user["id"], "closed_by_name": user["name"],
        "closure_reason": body.reason, "closure_remarks": (body.remarks or "").strip(),
        "updated_at": now_iso()}})
    await db.ecp_stage_history.insert_one({
        "id": new_id(), "ecp_id": ecp_id, "from_stage": ecp["current_stage"], "to_stage": "CLOSED",
        "changed_by": user["id"], "changed_by_name": user["name"], "changed_at": now_iso(),
        "note": f"Manually closed/cancelled: {body.reason}"})
    await log_activity(user, "ECP Closed", "ECP", ecp_id, ecp.get("lead_name", ""), body.reason)
    return await get_ecp(ecp_id, user)


# ========================= PAYMENTS =========================
class PaymentCreate(BaseModel):
    ecp_id: str
    type: str  # FIRST | ADDITIONAL | FINAL
    amount: float
    date: str
    status: str  # PENDING | CONFIRMED
    remarks: Optional[str] = ""


class PaymentUpdate(BaseModel):
    amount: Optional[float] = None
    date: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


@api.post("/payments")
async def create_payment(body: PaymentCreate, user: dict = Depends(get_current_user)):
    require(user, "ACCOUNTS")
    ecp = await db.ecps.find_one({"id": body.ecp_id}, NO_ID)
    if not ecp:
        raise HTTPException(status_code=404, detail="ECP not found")
    if body.type not in ("FIRST", "ADDITIONAL", "FINAL"):
        raise HTTPException(status_code=400, detail="Invalid payment type")
    if body.status not in ("PENDING", "CONFIRMED"):
        raise HTTPException(status_code=400, detail="Invalid payment status")
    if body.type in ("FIRST", "FINAL"):
        exists = await db.payments.find_one({"ecp_id": body.ecp_id, "type": body.type})
        if exists:
            raise HTTPException(status_code=400, detail=f"{body.type} payment already exists for this ECP")
    if (body.date or "")[:10] > ist_today_str():
        raise HTTPException(status_code=400, detail="Payment date cannot be in the future")
    doc = {
        "id": new_id(), "ecp_id": body.ecp_id, "type": body.type, "amount": float(body.amount),
        "date": body.date, "status": body.status, "remarks": (body.remarks or "").strip(),
        "updated_by": user["id"], "updated_by_name": user["name"], "updated_at": now_iso(),
        "created_at": now_iso()}
    await db.payments.insert_one(doc)
    await log_activity(user, "Payment Created", "ECP", body.ecp_id, ecp.get("lead_name", ""),
                       f"{body.type} {body.status} ₹{body.amount}")
    d = dict(doc)
    d.pop("_id", None)
    return d


@api.patch("/payments/{payment_id}")
async def update_payment(payment_id: str, body: PaymentUpdate, user: dict = Depends(get_current_user)):
    require(user, "ACCOUNTS")
    pay = await db.payments.find_one({"id": payment_id}, NO_ID)
    if not pay:
        raise HTTPException(status_code=404, detail="Payment not found")
    upd = {"updated_by": user["id"], "updated_by_name": user["name"], "updated_at": now_iso()}
    if body.amount is not None:
        upd["amount"] = float(body.amount)
    if body.date is not None:
        if (body.date or "")[:10] > ist_today_str():
            raise HTTPException(status_code=400, detail="Payment date cannot be in the future")
        upd["date"] = body.date
    if body.status is not None:
        if body.status not in ("PENDING", "CONFIRMED"):
            raise HTTPException(status_code=400, detail="Invalid status")
        upd["status"] = body.status
    if body.remarks is not None:
        upd["remarks"] = body.remarks.strip()
    await db.payments.update_one({"id": payment_id}, {"$set": upd})
    ecp = await db.ecps.find_one({"id": pay["ecp_id"]}, NO_ID)
    await log_activity(user, "Payment Updated", "ECP", pay["ecp_id"], (ecp or {}).get("lead_name", ""),
                       f"{pay['type']} → {upd.get('status', pay['status'])}")
    return await db.payments.find_one({"id": payment_id}, NO_ID)


def _ecp_receivable(ecp: dict, ecp_payments: list):
    price = float(ecp.get("project_price") or 0)
    first_conf = sum(p["amount"] for p in ecp_payments if p["type"] == "FIRST" and p["status"] == "CONFIRMED")
    sub_conf = sum(p["amount"] for p in ecp_payments if p["type"] == "ADDITIONAL" and p["status"] == "CONFIRMED")
    final_conf = sum(p["amount"] for p in ecp_payments if p["type"] == "FINAL" and p["status"] == "CONFIRMED")
    total_conf = first_conf + sub_conf + final_conf
    receivable = max(price - total_conf, 0)
    first_confirmed = any(p["type"] == "FIRST" and p["status"] == "CONFIRMED" for p in ecp_payments)
    return {
        "project_price": price, "first_confirmed_amount": first_conf,
        "subsequent_confirmed_amount": sub_conf + final_conf, "final_confirmed_amount": final_conf,
        "total_received": total_conf, "total_receivable": receivable,
        "first_payment_confirmed": first_confirmed,
    }


@api.get("/payments/monitor")
async def payment_monitor(user: dict = Depends(get_current_user)):
    require(user, "ACCOUNTS", "OWNER", "MANAGER")
    ecps = await db.ecps.find({}, NO_ID).sort("created_at", -1).to_list(3000)
    payments = await db.payments.find({}, NO_ID).to_list(5000)
    by_ecp = {}
    for p in payments:
        by_ecp.setdefault(p["ecp_id"], []).append(p)
    rows = []
    for e in ecps:
        ps = by_ecp.get(e["id"], [])
        calc = _ecp_receivable(e, ps)
        rows.append({
            "ecp_id": e["id"], "lead_name": e["lead_name"], "customer_phone": e.get("customer_phone", ""),
            "lead_creator_name": e.get("lead_creator_name"),
            "stage": e["current_stage"],
            "stage_label": wf.STAGE_LABELS.get(e["current_stage"], e["current_stage"]),
            "status": e["status"], "payments": ps, **calc})
    return rows


# ========================= DASHBOARD =========================
@api.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    role = user["role"]
    sla_map = await get_sla_map()
    leads = await db.leads.find({}, NO_ID).to_list(5000)
    ecps = await db.ecps.find({}, NO_ID).to_list(5000)
    for e in ecps:
        await enrich_ecp(e, sla_map)
    payments = await db.payments.find({}, NO_ID).to_list(5000)

    def lead_count(status):
        return len([l for l in leads if l["status"] == status])

    def ecp_stage_count(stage):
        return len([e for e in ecps if e["current_stage"] == stage and e["status"] == "ACTIVE"])

    def derived_count(d):
        return len([e for e in ecps if e.get("derived_status") == d and e["status"] == "ACTIVE"])

    active_ecps = [e for e in ecps if e["status"] == "ACTIVE"]
    delayed = [e for e in active_ecps if e.get("delayed")]

    def pay_count(ptype, status):
        return len([p for p in payments if p["type"] == ptype and p["status"] == status])

    today = datetime.now(timezone.utc).date().isoformat()

    async def followups_today():
        fus = await db.lead_followups.find({}, NO_ID).to_list(5000)
        # only count for currently-in-followup leads
        fu_lead_ids = {l["id"] for l in leads if l["status"] == "FOLLOW_UP"}
        return len([f for f in fus if f["lead_id"] in fu_lead_ids and (f.get("followup_date") or "")[:10] == today])

    site_visits = await db.lead_site_visits.find({}, NO_ID).to_list(5000)

    data = {"role": role, "role_label": wf.ROLE_LABELS.get(role, role)}

    if role == "OWNER":
        data["leads"] = {
            "PENDING": lead_count("PENDING"), "FOLLOW_UP": lead_count("FOLLOW_UP"),
            "SITE_VISIT": lead_count("SITE_VISIT"), "ESCALATED": lead_count("ESCALATED"),
            "QUALIFIED": lead_count("QUALIFIED"), "LOST": lead_count("LOST")}
        data["ecp"] = {
            "ACTIVE": len(active_ecps),
            "REGISTRATION_1": ecp_stage_count("REGISTRATION_1"),
            "ACCOUNTS_1": ecp_stage_count("ACCOUNTS_1"),
            "PAYMENT_BLOCKED": derived_count("PAYMENT_BLOCKED"),
            "READY_FOR_DISPATCH": derived_count("READY_FOR_DISPATCH"),
            "DISPATCH_IN_PROCESS": derived_count("DISPATCH_IN_PROCESS"),
            "READY_TO_INSTALL": derived_count("READY_TO_INSTALL"),
            "INSTALLATION_IN_PROCESS": derived_count("IN_PROCESS"),
            "NET_METERING": ecp_stage_count("NET_METERING"),
            "REGISTRATION_2": ecp_stage_count("REGISTRATION_2"),
            "ACCOUNTS_2": ecp_stage_count("ACCOUNTS_2"),
            "DELAYED": len(delayed),
            "COMPLETED": len([e for e in ecps if e["status"] == "COMPLETED"]),
            "CLOSED": len([e for e in ecps if e["status"] == "CLOSED"])}
        data["payments"] = {
            "FIRST_PENDING": pay_count("FIRST", "PENDING"), "FIRST_CONFIRMED": pay_count("FIRST", "CONFIRMED"),
            "FINAL_PENDING": pay_count("FINAL", "PENDING"), "FINAL_CONFIRMED": pay_count("FINAL", "CONFIRMED"),
            "ADDITIONAL": len([p for p in payments if p["type"] == "ADDITIONAL"])}
        data["pending_commercial"] = len([l for l in leads if (l.get("pending_commercial_change") or {}).get("status") == "PENDING"])

    elif role == "MANAGER":
        data["site_visits_to_assign"] = len([s for s in site_visits if s["status"] == "REQUESTED"])
        data["site_visits_today"] = len([s for s in site_visits if s["status"] == "ASSIGNED" and (s.get("visit_date") or "")[:10] == today])
        data["site_visits_upcoming"] = len([s for s in site_visits if s["status"] == "ASSIGNED" and (s.get("visit_date") or "")[:10] > today])
        data["awaiting_install_assignment"] = len([e for e in active_ecps if e["current_stage"] == "INSTALLATION" and e.get("install_status") == "AWAITING_ASSIGNMENT"])
        data["delayed"] = len(delayed)
        data["active_leads"] = len([l for l in leads if l["status"] in ("PENDING", "FOLLOW_UP", "SITE_VISIT", "ESCALATED")])
        data["active_ecps"] = len(active_ecps)

    elif role == "LEAD":
        data["action_required"] = len([l for l in leads if l.get("action_required")])
        data["followups_today"] = await followups_today()
        data["waiting_site_visit"] = lead_count("SITE_VISIT")
        data["escalated"] = lead_count("ESCALATED")
        data["qualified"] = lead_count("QUALIFIED")
        data["lost"] = lead_count("LOST")

    elif role == "ACCOUNTS":
        by_ecp = {}
        for p in payments:
            by_ecp.setdefault(p["ecp_id"], []).append(p)
        first_pending_count = 0
        subsequent_followup_count = 0
        subsequent_amount_pending = 0.0
        total_receivable = 0.0
        for e in active_ecps:
            calc = _ecp_receivable(e, by_ecp.get(e["id"], []))
            total_receivable += calc["total_receivable"]
            if not calc["first_payment_confirmed"]:
                first_pending_count += 1
            elif calc["total_receivable"] > 0:
                subsequent_followup_count += 1
                subsequent_amount_pending += calc["total_receivable"]
        data["first_payment_pending_count"] = first_pending_count
        data["subsequent_followup_count"] = subsequent_followup_count
        data["subsequent_amount_pending"] = subsequent_amount_pending
        data["total_receivable"] = total_receivable

    elif role == "DISPATCH":
        data["payment_blocked"] = derived_count("PAYMENT_BLOCKED")
        data["ready_for_dispatch"] = derived_count("READY_FOR_DISPATCH")
        data["dispatch_in_process"] = derived_count("DISPATCH_IN_PROCESS")
        past_dispatch = ["INSTALLATION", "NET_METERING", "REGISTRATION_2", "ACCOUNTS_2"]
        data["completed"] = len([e for e in ecps if e["current_stage"] in past_dispatch or e["status"] in ("COMPLETED", "CLOSED")])

    elif role == "INSTALLATION":
        mine = [s for s in site_visits if s["assigned_user"] == user["id"]]
        data["sv_upcoming"] = len([s for s in mine if s["status"] == "ASSIGNED" and (s.get("visit_date") or "")[:10] > today])
        data["sv_today"] = len([s for s in mine if s["status"] == "ASSIGNED" and (s.get("visit_date") or "")[:10] == today])
        data["sv_assigned"] = len([s for s in mine if s["status"] == "ASSIGNED"])
        data["sv_completed"] = len([s for s in mine if s["status"] == "DONE"])
        my_ecps = [e for e in active_ecps if e.get("responsible_user") == user["id"]]
        data["ready_to_install"] = len([e for e in my_ecps if e["current_stage"] == "INSTALLATION" and e.get("install_status") == "READY_TO_INSTALL"])
        data["installation_in_process"] = len([e for e in my_ecps if e["current_stage"] == "INSTALLATION" and e.get("install_status") == "IN_PROCESS"])
        data["net_metering"] = len([e for e in my_ecps if e["current_stage"] == "NET_METERING"])

    elif role == "REGISTRATION":
        data["registration_1"] = ecp_stage_count("REGISTRATION_1")
        data["registration_2"] = ecp_stage_count("REGISTRATION_2")
        data["pending"] = ecp_stage_count("REGISTRATION_1") + ecp_stage_count("REGISTRATION_2")

    return data


@api.get("/meta")
async def meta(user: dict = Depends(get_current_user)):
    return {
        "roles": wf.ROLES, "role_labels": wf.ROLE_LABELS,
        "stage_order": wf.STAGE_ORDER, "stage_labels": wf.STAGE_LABELS,
        "lost_reasons": wf.LOST_REASONS, "closure_reasons": wf.CLOSURE_REASONS,
    }


# ========================= ACTIVITIES (lightweight work-done log) =========================
async def log_activity(user, activity, ref_type, ref_id, customer_name="", details=""):
    try:
        await db.activities.insert_one({
            "id": new_id(), "ts": now_iso(), "user_id": user.get("id"),
            "user_name": user.get("name"), "team": user.get("role"),
            "customer_name": customer_name, "ref_type": ref_type, "ref_id": ref_id,
            "activity": activity, "details": details})
    except Exception:
        pass


@api.get("/activities")
async def list_activities(date: Optional[str] = None, activity_user: Optional[str] = None,
                          team: Optional[str] = None, activity: Optional[str] = None,
                          user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    d = date or ist_today_str()
    start, end = ist_day_bounds(d)
    q = {"ts": {"$gte": start, "$lt": end}}
    if activity_user:
        q["user_id"] = activity_user
    if team:
        q["team"] = team
    if activity:
        q["activity"] = activity
    return await db.activities.find(q, NO_ID).sort("ts", -1).to_list(5000)


# ========================= LEAD EMPLOYEE MASTER =========================
class LeadEmpCreate(BaseModel):
    name: str


class LeadEmpUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None


@api.get("/lead-employees")
async def list_lead_employees(active_only: Optional[bool] = False, user: dict = Depends(get_current_user)):
    require(user, "OWNER", "MANAGER", "LEAD", "ACCOUNTS")
    q = {"active": True} if active_only else {}
    return await db.lead_employees.find(q, NO_ID).sort("name", 1).to_list(1000)


@api.post("/lead-employees")
async def create_lead_employee(body: LeadEmpCreate, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    doc = {"id": new_id(), "name": body.name.strip(), "active": True, "created_at": now_iso()}
    await db.lead_employees.insert_one(doc)
    d = dict(doc); d.pop("_id", None)
    return d


@api.patch("/lead-employees/{emp_id}")
async def update_lead_employee(emp_id: str, body: LeadEmpUpdate, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    emp = await db.lead_employees.find_one({"id": emp_id}, NO_ID)
    if not emp:
        raise HTTPException(status_code=404, detail="Lead employee not found")
    upd = {}
    if body.name is not None:
        upd["name"] = body.name.strip()
    if body.active is not None:
        upd["active"] = body.active
    if upd:
        await db.lead_employees.update_one({"id": emp_id}, {"$set": upd})
    return await db.lead_employees.find_one({"id": emp_id}, NO_ID)


# ========================= CSV EXPORT (Owner only) =========================
@api.get("/export/projects")
async def export_projects(include_money: bool = False, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    ecps = await db.ecps.find({}, NO_ID).sort("created_at", -1).to_list(5000)
    payments = await db.payments.find({}, NO_ID).to_list(10000)
    by_ecp = {}
    for p in payments:
        by_ecp.setdefault(p["ecp_id"], []).append(p)
    base_headers = ["Customer", "Phone", "Lead ID", "ECP ID", "Current Stage", "Current Team",
                    "Responsible Employee", "Lead Creator", "Status", "Created At"]
    money_headers = ["Project Price", "First Received", "Subsequent Received", "Total Received", "Total Receivable"]
    headers = base_headers + (money_headers if include_money else [])
    rows = []
    for e in ecps:
        row = [e.get("lead_name", ""), e.get("customer_phone", ""), e.get("lead_id", ""), e["id"],
               wf.STAGE_LABELS.get(e["current_stage"], e["current_stage"]), e.get("current_team") or "",
               e.get("responsible_user_name") or "", e.get("lead_creator_name") or "",
               e.get("status", ""), (e.get("created_at") or "")[:10]]
        if include_money:
            calc = _ecp_receivable(e, by_ecp.get(e["id"], []))
            row += [calc["project_price"], calc["first_confirmed_amount"], calc["subsequent_confirmed_amount"],
                    calc["total_received"], calc["total_receivable"]]
        rows.append(row)
    csv_data = to_csv(headers, rows)
    return Response(content=csv_data, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=projects.csv"})


WORKFLOW_MANDATORY = {"name", "phone"}


async def enforce_lead_mandatory(body, item_name):
    cfg = await db.lead_field_config.find_one({"id": "singleton"}, NO_ID) or {}
    fields = cfg.get("fields", {})
    vals = {"email": body.email, "address": body.address, "location_link": body.location_link,
            "quantity": body.quantity, "project_price": body.project_price, "item": item_name}
    for fld, required in fields.items():
        if not required:
            continue
        v = vals.get(fld)
        if v in (None, "", 0):
            raise HTTPException(status_code=400, detail=f"Field '{fld}' is required")


# ---- Item Master ----
class ItemBody(BaseModel):
    name: str
    unit: str


async def _referenced_item_ids():
    ref = set()
    leads = await db.leads.find({}, {"item_id": 1, "pending_commercial_change": 1, "_id": 0}).to_list(20000)
    for l in leads:
        if l.get("item_id"):
            ref.add(l["item_id"])
        pcc = l.get("pending_commercial_change") or {}
        for side in ("proposed", "current"):
            iid = (pcc.get(side) or {}).get("item_id")
            if iid:
                ref.add(iid)
    return ref


@api.get("/items")
async def list_items(active_only: bool = False, user: dict = Depends(get_current_user)):
    q = {"active": True} if active_only else {}
    items = await db.items.find(q, NO_ID).sort("name", 1).to_list(2000)
    ref = await _referenced_item_ids()
    for it in items:
        it["referenced"] = it["id"] in ref
        it["deletable"] = it["id"] not in ref
    return items


@api.post("/items")
async def create_item(body: ItemBody, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    name, unit = body.name.strip(), body.unit.strip()
    if not name or not unit:
        raise HTTPException(status_code=400, detail="Name and unit are required")
    if await db.items.find_one({"name": name, "unit": unit}):
        raise HTTPException(status_code=409, detail="Item with this Name + Unit already exists")
    doc = {"id": new_id(), "name": name, "unit": unit, "active": True, "created_at": now_iso()}
    await db.items.insert_one(doc)
    d = dict(doc); d.pop("_id", None)
    return d


@api.patch("/items/{item_id}")
async def update_item(item_id: str, body: dict, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    it = await db.items.find_one({"id": item_id}, NO_ID)
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    upd = {}
    if "name" in body or "unit" in body:
        nm = (body.get("name") or it["name"]).strip(); un = (body.get("unit") or it["unit"]).strip()
        other = await db.items.find_one({"name": nm, "unit": un, "id": {"$ne": item_id}})
        if other:
            raise HTTPException(status_code=409, detail="Another item with this Name + Unit exists")
        upd["name"] = nm; upd["unit"] = un
    if "active" in body:
        upd["active"] = bool(body["active"])
    await db.items.update_one({"id": item_id}, {"$set": upd})
    return await db.items.find_one({"id": item_id}, NO_ID)


@api.delete("/items/{item_id}")
async def delete_item(item_id: str, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    it = await db.items.find_one({"id": item_id}, NO_ID)
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    ref = await _referenced_item_ids()
    if item_id in ref:
        raise HTTPException(status_code=409, detail="This item is already used in existing records and cannot be deleted. You can deactivate it instead.")
    await db.items.delete_one({"id": item_id})
    return {"deleted": True}


@api.get("/items/export")
async def export_items(user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    items = await db.items.find({}, NO_ID).sort("name", 1).to_list(5000)
    rows = [[i["name"], i["unit"], "active" if i.get("active", True) else "inactive"] for i in items]
    return Response(content=to_csv(["Item Name", "Unit", "Status"], rows), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=items.csv"})


class ItemCSVBody(BaseModel):
    rows: list  # list of {name, unit}


@api.post("/items/import")
async def import_items(body: ItemCSVBody, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    created, errors = 0, []
    seen = set()
    for idx, r in enumerate(body.rows, 1):
        name = (r.get("name") or "").strip(); unit = (r.get("unit") or "").strip()
        if not name or not unit:
            errors.append(f"Row {idx}: missing name/unit"); continue
        key = (name.lower(), unit.lower())
        if key in seen:
            errors.append(f"Row {idx}: duplicate in file ({name}+{unit})"); continue
        seen.add(key)
        if await db.items.find_one({"name": name, "unit": unit}):
            errors.append(f"Row {idx}: already exists ({name}+{unit})"); continue
        await db.items.insert_one({"id": new_id(), "name": name, "unit": unit, "active": True, "created_at": now_iso()})
        created += 1
    return {"created": created, "errors": errors}


# ---- Lead mandatory-field config ----
@api.get("/lead-field-config")
async def get_field_config(user: dict = Depends(get_current_user)):
    require(user, "OWNER", "LEAD", "MANAGER")
    cfg = await db.lead_field_config.find_one({"id": "singleton"}, NO_ID)
    return cfg or {"id": "singleton", "fields": {}}


@api.put("/lead-field-config")
async def set_field_config(body: dict, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    fields = {k: bool(v) for k, v in (body.get("fields") or {}).items()}
    await db.lead_field_config.update_one({"id": "singleton"}, {"$set": {"id": "singleton", "fields": fields}}, upsert=True)
    return {"id": "singleton", "fields": fields}


# ---- Lead edit after handoff (non-commercial) ----
class LeadEditBody(BaseModel):
    email: Optional[str] = None
    address: Optional[str] = None
    location_link: Optional[str] = None
    remarks: Optional[str] = None


@api.patch("/leads/{lead_id}")
async def edit_lead(lead_id: str, body: LeadEditBody, user: dict = Depends(get_current_user)):
    require(user, "LEAD", "MANAGER", "OWNER")
    lead = await db.leads.find_one({"id": lead_id}, NO_ID)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if user["role"] == "LEAD" and lead.get("lead_owner_id") not in (user["id"], None):
        raise HTTPException(status_code=403, detail="This lead is not assigned to you")
    upd = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.dict().items() if v is not None}
    if upd:
        upd["updated_at"] = now_iso()
        await db.leads.update_one({"id": lead_id}, {"$set": upd})
        await log_activity(user, "Lead Edited", "LEAD", lead_id, lead["name"], ", ".join(upd.keys()))
    return await _lead_bundle(lead_id)


# ---- Commercial change approval ----
class CommercialChange(BaseModel):
    item_id: Optional[str] = None
    quantity: Optional[float] = None
    project_price: Optional[float] = None


@api.post("/leads/{lead_id}/commercial-change")
async def propose_commercial(lead_id: str, body: CommercialChange, user: dict = Depends(get_current_user)):
    require(user, "LEAD")
    lead = await db.leads.find_one({"id": lead_id}, NO_ID)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.get("lead_owner_id") not in (user["id"], None):
        raise HTTPException(status_code=403, detail="This lead is not assigned to you")
    proposed = {}
    if body.item_id is not None:
        it = await db.items.find_one({"id": body.item_id}, NO_ID)
        if not it or not it.get("active", True):
            raise HTTPException(status_code=400, detail="Invalid or inactive item")
        proposed["item_id"] = body.item_id; proposed["item_name"] = it["name"]; proposed["item_unit"] = it["unit"]
    if body.quantity is not None:
        proposed["quantity"] = body.quantity
    if body.project_price is not None:
        proposed["project_price"] = body.project_price
    if not proposed:
        raise HTTPException(status_code=400, detail="No commercial change proposed")
    pcc = {"proposed": proposed,
           "current": {"item_id": lead.get("item_id"), "item_name": lead.get("item_name"),
                       "item_unit": lead.get("item_unit"), "quantity": lead.get("quantity"),
                       "project_price": lead.get("project_price")},
           "requested_by": user["id"], "requested_by_name": user["name"], "requested_at": now_iso(),
           "status": "PENDING"}
    await db.leads.update_one({"id": lead_id}, {"$set": {"pending_commercial_change": pcc, "updated_at": now_iso()}})
    await log_activity(user, "Commercial Change Requested", "LEAD", lead_id, lead["name"], str(proposed))
    return await _lead_bundle(lead_id)


class CommercialDecision(BaseModel):
    remarks: Optional[str] = None


@api.post("/leads/{lead_id}/commercial-change/approve")
async def approve_commercial(lead_id: str, body: CommercialDecision, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    lead = await db.leads.find_one({"id": lead_id}, NO_ID)
    if not lead or not lead.get("pending_commercial_change") or lead["pending_commercial_change"].get("status") != "PENDING":
        raise HTTPException(status_code=400, detail="No pending commercial change")
    pcc = lead["pending_commercial_change"]
    upd = dict(pcc["proposed"]); upd["updated_at"] = now_iso()
    pcc.update({"status": "APPROVED", "decided_by": user["name"], "decided_at": now_iso(), "decision_remarks": (body.remarks or "")})
    upd["pending_commercial_change"] = pcc
    await db.leads.update_one({"id": lead_id}, {"$set": upd})
    if lead.get("ecp_id") and "project_price" in pcc["proposed"]:
        await db.ecps.update_one({"id": lead["ecp_id"]}, {"$set": {"project_price": pcc["proposed"]["project_price"]}})
    await log_activity(user, "Commercial Change Approved", "LEAD", lead_id, lead["name"], str(pcc["proposed"]))
    return await _lead_bundle(lead_id)


@api.post("/leads/{lead_id}/commercial-change/reject")
async def reject_commercial(lead_id: str, body: CommercialDecision, user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    lead = await db.leads.find_one({"id": lead_id}, NO_ID)
    if not lead or not lead.get("pending_commercial_change") or lead["pending_commercial_change"].get("status") != "PENDING":
        raise HTTPException(status_code=400, detail="No pending commercial change")
    if not (body.remarks or "").strip():
        raise HTTPException(status_code=400, detail="Rejection remarks are mandatory")
    pcc = lead["pending_commercial_change"]
    pcc.update({"status": "REJECTED", "decided_by": user["name"], "decided_at": now_iso(), "decision_remarks": body.remarks.strip()})
    await db.leads.update_one({"id": lead_id}, {"$set": {"pending_commercial_change": pcc}})
    await log_activity(user, "Commercial Change Rejected", "LEAD", lead_id, lead["name"], body.remarks.strip())
    return await _lead_bundle(lead_id)


@api.get("/commercial-changes/pending")
async def pending_commercial(user: dict = Depends(get_current_user)):
    require(user, "OWNER")
    leads = await db.leads.find({"pending_commercial_change.status": "PENDING"}, NO_ID).to_list(1000)
    return leads


# ---- Quotation PDF ----
@api.get("/leads/{lead_id}/quotation")
async def quotation_pdf(lead_id: str, user: dict = Depends(get_current_user)):
    require(user, "LEAD", "MANAGER", "OWNER")
    lead = await db.leads.find_one({"id": lead_id}, NO_ID)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if user["role"] == "LEAD" and lead.get("lead_owner_id") not in (user["id"], None):
        raise HTTPException(status_code=403, detail="This lead is not assigned to you")
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 30 * mm
    c.setFont("Helvetica-Bold", 18); c.drawString(20 * mm, y, "Solar Energy Solutions")
    c.setFont("Helvetica", 10); y -= 6 * mm; c.drawString(20 * mm, y, "Internal Quotation")
    y -= 12 * mm; c.setFont("Helvetica-Bold", 12); c.drawString(20 * mm, y, f"Quotation — Lead {lead['id'][:8].upper()}")
    c.setFont("Helvetica", 10)
    lines = [
        f"Date: {ist_today_str()}",
        f"Customer: {lead.get('name','')}",
        f"Mobile: {lead.get('phone','')}",
        f"Address: {lead.get('address','') or '-'}",
        f"Location: {lead.get('location_link','') or '-'}",
        "",
        f"Item: {lead.get('item_name','-') or '-'}",
        f"Quantity: {lead.get('quantity','-')} {lead.get('item_unit','') or ''}",
        f"Agreed / Project Price: Rs. {lead.get('project_price',0):,.0f}",
    ]
    for ln in lines:
        y -= 8 * mm; c.drawString(20 * mm, y, ln)
    y -= 16 * mm; c.setFont("Helvetica-Oblique", 8)
    c.drawString(20 * mm, y, "This is a system-generated quotation for internal use.")
    c.showPage(); c.save(); buf.seek(0)
    return Response(content=buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=quotation_{lead['id'][:8]}.pdf"})


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("username", unique=True)
    await db.leads.create_index("status")
    await db.ecps.create_index("current_stage")
    await db.payments.create_index("ecp_id")
    await seed()


async def seed():
    owner_username = os.environ.get("OWNER_USERNAME", "anoopdube07@gmail.com").strip().lower()
    owner_password = os.environ.get("OWNER_PASSWORD", "Owner@123")
    existing = await db.users.find_one({"username": owner_username})
    if not existing:
        await db.users.insert_one({
            "id": new_id(), "username": owner_username, "password_hash": hash_password(owner_password),
            "name": "Anoop Dube", "role": "OWNER", "team": "OWNER", "active": True, "created_at": now_iso()})
        logger.info("Seeded owner user")
    # demo team users
    demo = [
        ("manager", "Manager@123", "Priya Manager", "MANAGER"),
        ("lead", "Lead@123", "Rahul Lead", "LEAD"),
        ("registration", "Reg@123", "Sunita Reg", "REGISTRATION"),
        ("accounts", "Acct@123", "Vikram Accounts", "ACCOUNTS"),
        ("dispatch", "Disp@123", "Amit Dispatch", "DISPATCH"),
        ("installation", "Install@123", "Ravi Install", "INSTALLATION"),
    ]
    for uname, pwd, name, role in demo:
        if not await db.users.find_one({"username": uname}):
            await db.users.insert_one({
                "id": new_id(), "username": uname, "password_hash": hash_password(pwd),
                "name": name, "role": role, "team": role, "active": True, "created_at": now_iso()})


@app.on_event("shutdown")
async def shutdown():
    client.close()
