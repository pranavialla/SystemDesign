from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class URLInfoResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: HttpUrl
    created_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
    click_count: int = 0
    is_active: bool = True

    model_config = {"from_attributes": True}