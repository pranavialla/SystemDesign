from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime
from typing import Optional, List

# Request DTOs
class URLCreateRequest(BaseModel):
    # original_url is the Python field, 'url' is the JSON key
    original_url: HttpUrl = Field(..., alias="url")
    custom_alias: Optional[str] = None # Bonus feature