from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional

class URLBase(BaseModel):
    url: HttpUrl

class URLCreate(URLBase):
    pass

class URLInfo(URLBase):
    short_code: str
    short_url: str
    created_at: datetime
    last_accessed_at: datetime
    click_count: int

    class Config:
        from_attributes = True

# NEW: Schema for Config updates
class ConfigUpdate(BaseModel):
    key: str
    value: str
    description: Optional[str] = None
