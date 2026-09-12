"""Business workflow constants for ECP Project Management & Lead Tracking (Phase 1 spec)."""

# ---- Roles / Teams (V1: one user = one role = one team) ----
ROLES = ["OWNER", "MANAGER", "LEAD", "REGISTRATION", "ACCOUNTS", "DISPATCH", "INSTALLATION",
         "INSTALLATION_MANAGER", "INSTALLATION_MEMBER", "COMPLAINT"]

ROLE_LABELS = {
    "OWNER": "Owner",
    "MANAGER": "Process Owner / Manager",
    "LEAD": "Lead Team",
    "REGISTRATION": "Registration Team",
    "ACCOUNTS": "Accounts Team",
    "DISPATCH": "Dispatch Team",
    "INSTALLATION": "Installation Team",
    "INSTALLATION_MANAGER": "Installation Team Manager",
    "INSTALLATION_MEMBER": "Installation Team Member",
    "COMPLAINT": "Complaint Registration Team",
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
    "PENDING_DOCUMENTS": "Pending Documents",
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
    "PENDING_DOCUMENTS": "LEAD",
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

# ---- Phase 3: Documents ----
# Single required document types
DOC_REQUIRED_SINGLE = ["PAN", "AADHAAR", "ELECTRICITY_BILL"]
# Bank proof group — at least one of these is required
DOC_BANK_GROUP = ["BANK_PASSBOOK", "BANK_STATEMENT", "CANCELLED_CHEQUE"]
# Finance group — at least one required ONLY when financing_required is True
DOC_FINANCE_GROUP = ["PROPERTY_PAPER", "TAX_RECEIPT"]

DOC_TYPES = DOC_REQUIRED_SINGLE + DOC_BANK_GROUP + DOC_FINANCE_GROUP

DOC_LABELS = {
    "PAN": "PAN Card",
    "AADHAAR": "Aadhaar Card",
    "ELECTRICITY_BILL": "Electricity Bill",
    "BANK_PASSBOOK": "Bank Passbook Photo",
    "BANK_STATEMENT": "3-Month Bank Statement",
    "CANCELLED_CHEQUE": "Cancelled Cheque",
    "PROPERTY_PAPER": "Property Paper",
    "TAX_RECEIPT": "Tax Receipt",
}

DOC_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}
DOC_ALLOWED_EXT = {"jpg", "jpeg", "png", "pdf"}
DOC_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def documents_complete(current_types: set, financing: bool) -> bool:
    if not all(t in current_types for t in DOC_REQUIRED_SINGLE):
        return False
    if not any(t in current_types for t in DOC_BANK_GROUP):
        return False
    if financing and not any(t in current_types for t in DOC_FINANCE_GROUP):
        return False
    return True


LOST_REASONS = ["PRICE", "COMPETITOR", "NOT_INTERESTED", "UNREACHABLE", "OTHER"]
CLOSURE_REASONS = ["CUSTOMER_CANCELLED", "DUPLICATE", "NOT_FEASIBLE", "OTHER"]


def next_stage(stage: str):
    if stage not in STAGE_ORDER:
        return None
    idx = STAGE_ORDER.index(stage)
    if idx + 1 < len(STAGE_ORDER):
        return STAGE_ORDER[idx + 1]
    return "COMPLETED"
