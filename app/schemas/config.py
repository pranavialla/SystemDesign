from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ConfigUpdateRequest(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

class ConfigResponse(BaseModel):
    key: str
    value: str
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}