from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime
from typing import Optional, List

# Response DTOs
class URLInfoResponse(BaseModel):
    # original_url is the Python field, 'url' is the JSON key
    original_url: HttpUrl = Field(..., alias="url")
    short_code: str
    short_url: str
    created_at: datetime
    last_accessed_at: datetime
    click_count: int

    # Pydantic v2 configuration
    model_config = {"from_attributes": True, "populate_by_name": True}
