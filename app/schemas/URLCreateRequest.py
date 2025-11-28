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
    
    @field_validator('original_url')
    def validate_url(cls, v):
        url_str = str(v)
        
        # Length check
        if len(url_str) > 2048:
            raise ValueError('URL must be less than 2048 characters')
        
        # Only allow http/https
        if not (url_str.startswith('http://') or url_str.startswith('https://')):
            raise ValueError('Only HTTP and HTTPS URLs are allowed')
        
        return v