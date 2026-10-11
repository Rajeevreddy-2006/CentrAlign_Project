from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class RiskLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    REVERSIBLE_WRITE = "REVERSIBLE_WRITE"
    IRREVERSIBLE_FINANCIAL_WRITE = "IRREVERSIBLE_FINANCIAL_WRITE"

class VerificationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"

class ActionType(str, Enum):
    NAVIGATE = "NAVIGATE"
    LOGIN = "LOGIN"
    READ_PAGE = "READ_PAGE"
    DOWNLOAD_PDF = "DOWNLOAD_PDF"
    PARSE_PDF = "PARSE_PDF"
    SUBMIT_FORM = "SUBMIT_FORM"
    ASK_USER = "ASK_USER"
    FINISH = "FINISH"

class Action(BaseModel):
    action_type: ActionType
    thought: str = Field(..., description="Reasoning for choosing this action")
    params: Dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = Field(default=RiskLevel.READ_ONLY)

class ActionResult(BaseModel):
    action_type: ActionType
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    is_transient: bool = False
    status_code: Optional[int] = None
    state_hash: Optional[str] = None
    current_url: Optional[str] = None
    error_banner: Optional[str] = None

class VerificationEvidence(BaseModel):
    source_vendor: str
    source_invoice_no: str
    source_amount: float
    source_due_date: str
    destination_payable_id: Optional[int] = None
    destination_vendor: Optional[str] = None
    destination_invoice_no: Optional[str] = None
    destination_amount: Optional[float] = None
    destination_due_date: Optional[str] = None
    destination_status: Optional[str] = None
    discrepancies: List[str] = Field(default_factory=list)

class VerificationReport(BaseModel):
    status: VerificationStatus
    message: str
    evidence: Optional[VerificationEvidence] = None
    verifier_dom_snapshot: Optional[str] = None

class ExecutionStep(BaseModel):
    step_num: int
    action: Action
    result: ActionResult
    retries: int = 0
    timestamp: str

class FinalRunReport(BaseModel):
    task: str
    claimed_summary: str
    claimed_facts: Dict[str, Any]
    verification: VerificationReport
    total_steps: int
    total_retries: int
    remediated_failures: List[str]
    human_interventions: List[str]
    evidence_files: List[str]
    success: bool
