from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime
from typing import Optional, List

# Request DTOs
class URLCreateRequest(BaseModel):
    # original_url is the Python field, 'url' is the JSON key
    original_url: HttpUrl = Field(..., alias="url")
    custom_alias: Optional[str] = None # Bonus feature

# Response DTOs
class URLInfoResponse(BaseModel):
    # original_url is the Python field, 'url' is the JSON key
    original_url: HttpUrl = Field(..., alias="url")
    short_code: str
    short_url: str
    created_at: datetime
    last_accessed_at: datetime
    click_count: int

    class Config:
        from_attributes = True
        # CRITICAL FIX for Pydantic V2: Allows instantiation using the Python field name 'original_url'
        # even though it has an alias 'url'.
        populate_by_name = True 

class ConfigUpdate(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

class PaginatedURLList(BaseModel):
    total: int
    skip: int
    limit: int
    urls: List[URLInfoResponse]
