from pydantic import BaseModel
from typing import Optional


class DealCreate(BaseModel):
    # Section 1: Main
    status: str
    business_direction: str
    client: str
    manager: str

    # Section 2: Finance (legacy)
    charged_with_vat: float
    vat_type: str
    paid: Optional[float] = None

    # Section 2a: VAT breakdown (new)
    vat_rate: Optional[float] = None
    vat_amount: Optional[float] = None
    amount_without_vat: Optional[float] = None

    # Section 3: Dates
    project_start_date: str
    project_end_date: str
    act_date: Optional[str] = None

    # Section 4: Expenses and bonuses (legacy)
    variable_expense_1: Optional[float] = None
    variable_expense_2: Optional[float] = None
    manager_bonus_percent: Optional[float] = None
    manager_bonus_paid: Optional[float] = None
    general_production_expense: Optional[float] = None

    # Section 4a: Variable expense 1 with VAT breakdown (new)
    variable_expense_1_with_vat: Optional[float] = None
    variable_expense_1_vat: Optional[float] = None
    variable_expense_1_without_vat: Optional[float] = None

    # Section 4b: Variable expense 2 with VAT breakdown (new)
    variable_expense_2_with_vat: Optional[float] = None
    variable_expense_2_vat: Optional[float] = None
    variable_expense_2_without_vat: Optional[float] = None

    # Section 4c: Production expense with VAT breakdown (new)
    production_expense_with_vat: Optional[float] = None
    production_expense_vat: Optional[float] = None
    production_expense_without_vat: Optional[float] = None

    # Section 4d: Calculated profitability (new)
    manager_bonus_amount: Optional[float] = None
    marginal_income: Optional[float] = None
    gross_profit: Optional[float] = None

    # Section 5: Additional
    source: Optional[str] = None
    document_link: Optional[str] = None
    comment: Optional[str] = None

    # Metadata (new)
    created_at: Optional[str] = None


class DealUpdate(BaseModel):
    status: Optional[str] = None
    business_direction: Optional[str] = None
    client: Optional[str] = None
    manager: Optional[str] = None
    charged_with_vat: Optional[float] = None
    vat_type: Optional[str] = None
    paid: Optional[float] = None

    # VAT breakdown (new)
    vat_rate: Optional[float] = None
    vat_amount: Optional[float] = None
    amount_without_vat: Optional[float] = None

    project_start_date: Optional[str] = None
    project_end_date: Optional[str] = None
    act_date: Optional[str] = None

    # Legacy expense fields
    variable_expense_1: Optional[float] = None
    variable_expense_2: Optional[float] = None
    manager_bonus_percent: Optional[float] = None
    manager_bonus_paid: Optional[float] = None
    general_production_expense: Optional[float] = None

    # Variable expense 1 with VAT breakdown (new)
    variable_expense_1_with_vat: Optional[float] = None
    variable_expense_1_vat: Optional[float] = None
    variable_expense_1_without_vat: Optional[float] = None

    # Variable expense 2 with VAT breakdown (new)
    variable_expense_2_with_vat: Optional[float] = None
    variable_expense_2_vat: Optional[float] = None
    variable_expense_2_without_vat: Optional[float] = None

    # Production expense with VAT breakdown (new)
    production_expense_with_vat: Optional[float] = None
    production_expense_vat: Optional[float] = None
    production_expense_without_vat: Optional[float] = None

    # Calculated profitability (new)
    manager_bonus_amount: Optional[float] = None
    marginal_income: Optional[float] = None
    gross_profit: Optional[float] = None

    source: Optional[str] = None
    document_link: Optional[str] = None
    comment: Optional[str] = None
    created_at: Optional[str] = None


class DealResponse(BaseModel):
    deal_id: str
    status: str
    business_direction: str
    client: str
    manager: str
    charged_with_vat: Optional[float] = None
    vat_type: Optional[str] = None
    paid: Optional[float] = None

    # VAT breakdown (new)
    vat_rate: Optional[float] = None
    vat_amount: Optional[float] = None
    amount_without_vat: Optional[float] = None

    project_start_date: Optional[str] = None
    project_end_date: Optional[str] = None
    act_date: Optional[str] = None

    # Legacy expense fields
    variable_expense_1: Optional[float] = None
    variable_expense_2: Optional[float] = None
    manager_bonus_percent: Optional[float] = None
    manager_bonus_paid: Optional[float] = None
    general_production_expense: Optional[float] = None

    # Variable expense 1 with VAT breakdown (new)
    variable_expense_1_with_vat: Optional[float] = None
    variable_expense_1_vat: Optional[float] = None
    variable_expense_1_without_vat: Optional[float] = None

    # Variable expense 2 with VAT breakdown (new)
    variable_expense_2_with_vat: Optional[float] = None
    variable_expense_2_vat: Optional[float] = None
    variable_expense_2_without_vat: Optional[float] = None

    # Production expense with VAT breakdown (new)
    production_expense_with_vat: Optional[float] = None
    production_expense_vat: Optional[float] = None
    production_expense_without_vat: Optional[float] = None

    # Calculated profitability (new)
    manager_bonus_amount: Optional[float] = None
    marginal_income: Optional[float] = None
    gross_profit: Optional[float] = None

    source: Optional[str] = None
    document_link: Optional[str] = None
    comment: Optional[str] = None
    created_at: Optional[str] = None
