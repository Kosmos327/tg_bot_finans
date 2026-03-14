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


# ---------------------------------------------------------------------------
# CRUD models for reference data management
# ---------------------------------------------------------------------------

class ClientItem(BaseModel):
    client_id: Optional[str] = None
    client_name: str
    created_at: Optional[str] = None


class ClientCreate(BaseModel):
    client_name: str


class ClientUpdate(BaseModel):
    client_name: str


class ManagerItem(BaseModel):
    manager_id: Optional[str] = None
    manager_name: str
    role: Optional[str] = "manager"
    created_at: Optional[str] = None


class ManagerCreate(BaseModel):
    manager_name: str
    role: Optional[str] = "manager"


class ManagerUpdate(BaseModel):
    manager_name: Optional[str] = None
    role: Optional[str] = None


class DirectionItem(BaseModel):
    value: str


class StatusItem(BaseModel):
    value: str
