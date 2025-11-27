from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime
from typing import Optional, List

class ConfigUpdate(BaseModel):
    key: str
    value: str
    description: Optional[str] = None
