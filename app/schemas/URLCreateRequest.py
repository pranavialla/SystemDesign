from pydantic import BaseModel, HttpUrl, Field, field_validator
from datetime import datetime
from typing import Optional, List

# Request DTOs
class URLCreateRequest(BaseModel):
    # original_url is the Python field, 'url' is the JSON key
    original_url: HttpUrl = Field(..., alias="url")
    custom_alias: Optional[str] = None # Bonus feature

    @field_validator('custom_alias')
    def validate_custom_alias(cls, v):
        if v is None:
            return v
        if len(v) > 10:
            raise ValueError('custom_alias must be 10 characters or less')
        return v