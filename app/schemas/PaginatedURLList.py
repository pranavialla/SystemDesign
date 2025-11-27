from app.schemas.URLInfoResponse import URLInfoResponse
from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime
from typing import Optional, List

class PaginatedURLList(BaseModel):
    total: int
    skip: int
    limit: int
    urls: List[URLInfoResponse]
