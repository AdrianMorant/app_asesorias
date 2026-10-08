from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

class TrafficLightStatus(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"

class RuleCheckDetail(BaseModel):
    rule_name: str
    severity: TrafficLightStatus  # RED o YELLOW
    passed: bool
    message: str

class RulesEvaluationResult(BaseModel):
    status: TrafficLightStatus
    passed: bool  # True si es GREEN, False si es RED o YELLOW
    reasons: List[str]
    rule_details: List[RuleCheckDetail]
    arithmetic_difference: float = 0.0
    supplier_found: bool = False
    supplier_id: Optional[str] = None
    suggested_supplier_account: Optional[str] = None
    suggested_expense_account: Optional[str] = None
    is_duplicate: bool = False
    duplicate_of_id: Optional[str] = None
    cif_valid: bool = True
    math_valid: bool = True
    adjusted_fecha_contable: Optional[str] = None
    date_lock_applied: bool = False
