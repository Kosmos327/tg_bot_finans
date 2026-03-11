from pydantic import BaseModel
from typing import List


class SettingsResponse(BaseModel):
    statuses: List[str]
    business_directions: List[str]
    clients: List[str]
    managers: List[str]
    vat_types: List[str]
    sources: List[str]
