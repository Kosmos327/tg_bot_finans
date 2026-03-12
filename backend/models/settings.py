from pydantic import BaseModel
from typing import List, Optional


class SettingsResponse(BaseModel):
    statuses: List[str]
    business_directions: List[str]
    clients: List[str]
    managers: List[str]
    vat_types: List[str]
    sources: List[str]


class UserRoleInfo(BaseModel):
    telegram_user_id: str
    full_name: str
    role: str
    active: bool


class UserAccessResponse(BaseModel):
    telegram_user_id: str
    full_name: Optional[str] = None
    role: str
    active: bool
    editable_fields: List[str]
