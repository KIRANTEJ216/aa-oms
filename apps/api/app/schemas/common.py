from pydantic import BaseModel
from typing import Optional

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
