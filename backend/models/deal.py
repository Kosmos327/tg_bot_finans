from pydantic import BaseModel
from typing import Optional


class DealCreate(BaseModel):
    # Section 1: Main
    status: str
    business_direction: str
    client: str
    manager: str

    # Section 2: Finance
    charged_with_vat: float
    vat_type: str
    paid: Optional[float] = None

    # Section 3: Dates
    project_start_date: str
    project_end_date: str
    act_date: Optional[str] = None

    # Section 4: Expenses and bonuses
    variable_expense_1: Optional[float] = None
    variable_expense_2: Optional[float] = None
    manager_bonus_percent: Optional[float] = None
    manager_bonus_paid: Optional[float] = None
    general_production_expense: Optional[float] = None

    # Section 5: Additional
    source: Optional[str] = None
    document_link: Optional[str] = None
    comment: Optional[str] = None


class DealUpdate(BaseModel):
    status: Optional[str] = None
    business_direction: Optional[str] = None
    client: Optional[str] = None
    manager: Optional[str] = None
    charged_with_vat: Optional[float] = None
    vat_type: Optional[str] = None
    paid: Optional[float] = None
    project_start_date: Optional[str] = None
    project_end_date: Optional[str] = None
    act_date: Optional[str] = None
    variable_expense_1: Optional[float] = None
    variable_expense_2: Optional[float] = None
    manager_bonus_percent: Optional[float] = None
    manager_bonus_paid: Optional[float] = None
    general_production_expense: Optional[float] = None
    source: Optional[str] = None
    document_link: Optional[str] = None
    comment: Optional[str] = None


class DealResponse(BaseModel):
    deal_id: str
    status: str
    business_direction: str
    client: str
    manager: str
    charged_with_vat: Optional[float] = None
    vat_type: Optional[str] = None
    paid: Optional[float] = None
    project_start_date: Optional[str] = None
    project_end_date: Optional[str] = None
    act_date: Optional[str] = None
    variable_expense_1: Optional[float] = None
    variable_expense_2: Optional[float] = None
    manager_bonus_percent: Optional[float] = None
    manager_bonus_paid: Optional[float] = None
    general_production_expense: Optional[float] = None
    source: Optional[str] = None
    document_link: Optional[str] = None
    comment: Optional[str] = None
