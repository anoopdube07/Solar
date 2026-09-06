"""Business workflow constants for ECP Project Management & Lead Tracking (Phase 1 spec)."""

# ---- Roles / Teams (V1: one user = one role = one team) ----
ROLES = ["OWNER", "MANAGER", "LEAD", "REGISTRATION", "ACCOUNTS", "DISPATCH", "INSTALLATION"]

ROLE_LABELS = {
    "OWNER": "Owner",
    "MANAGER": "Process Owner / Manager",
    "LEAD": "Lead Team",
    "REGISTRATION": "Registration Team",
    "ACCOUNTS": "Accounts Team",
    "DISPATCH": "Dispatch Team",
    "INSTALLATION": "Installation Team",
}

# ---- ECP stages (ordered) ----
STAGE_ORDER = [
    "REGISTRATION_1",
    "ACCOUNTS_1",
    "DISPATCH",
    "INSTALLATION",
    "NET_METERING",
    "REGISTRATION_2",
    "ACCOUNTS_2",
]

STAGE_LABELS = {
    "REGISTRATION_1": "Registration 1",
    "ACCOUNTS_1": "Accounts 1",
    "DISPATCH": "Dispatch",
    "INSTALLATION": "Installation",
    "NET_METERING": "Net Metering",
    "REGISTRATION_2": "Registration 2",
    "ACCOUNTS_2": "Accounts 2",
    "COMPLETED": "Successfully Completed",
    "CLOSED": "Closed / Cancelled",
}

# Team responsible for each stage
STAGE_TEAM = {
    "REGISTRATION_1": "REGISTRATION",
    "ACCOUNTS_1": "ACCOUNTS",
    "DISPATCH": "DISPATCH",
    "INSTALLATION": "INSTALLATION",
    "NET_METERING": "INSTALLATION",
    "REGISTRATION_2": "REGISTRATION",
    "ACCOUNTS_2": "ACCOUNTS",
}

# Mandatory operational tasks per stage (exact spec names)
REG1_BASE_TASKS = ["CSPDCL Registration", "PPA Preparation", "Cover Letter", "CVA"]
REG1_FINANCING_TASKS = ["Loan Documentation", "Loan Filing", "Bank Submission"]

STAGE_TASKS = {
    "REGISTRATION_1": REG1_BASE_TASKS,  # financing tasks appended dynamically
    "ACCOUNTS_1": ["Advance Verification"],
    "DISPATCH": ["Delivery Challan", "Material Dispatch Confirmation", "Dispatch Completed"],
    "INSTALLATION": [],  # handled via install_status
    "NET_METERING": ["Net Metering"],
    "REGISTRATION_2": ["Asset Creation", "Completion Certificate"],
    "ACCOUNTS_2": ["Final Payment Follow-up"],
}

LEAD_ACTIONS = ["YES", "NO", "FOLLOW_UP", "SITE_VISIT", "ESCALATION"]

LOST_REASONS = ["PRICE", "COMPETITOR", "NOT_INTERESTED", "UNREACHABLE", "OTHER"]
CLOSURE_REASONS = ["CUSTOMER_CANCELLED", "DUPLICATE", "NOT_FEASIBLE", "OTHER"]


def next_stage(stage: str):
    if stage not in STAGE_ORDER:
        return None
    idx = STAGE_ORDER.index(stage)
    if idx + 1 < len(STAGE_ORDER):
        return STAGE_ORDER[idx + 1]
    return "COMPLETED"
