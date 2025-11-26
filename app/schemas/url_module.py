from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
from datetime import datetime

class URLBase(BaseModel):
    url: HttpUrl

class URLCreate(URLBase):
    pass

class URLInfo(BaseModel):
    short_code: str
    short_url: Optional[str] = None
    original_url: Optional[HttpUrl] = None
    created_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
    click_count: int = 0

    class Config:
        orm_mode = True

class ConfigUpdate(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

    class Config:
        orm_mode = True
