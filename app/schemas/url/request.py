from pydantic import BaseModel, HttpUrl

class URLCreateRequest(BaseModel):
    url: HttpUrl