# re-export common schemas for simpler imports
from .url.request import URLCreateRequest
from .url.response import URLInfoResponse
from .config import ConfigUpdateRequest, ConfigResponse

__all__ = [
    "URLCreateRequest",
    "URLInfoResponse",
    "ConfigUpdateRequest",
    "ConfigResponse",
]