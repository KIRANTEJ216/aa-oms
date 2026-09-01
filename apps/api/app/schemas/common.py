from datetime import datetime
from pydantic import BaseModel, model_validator
from typing import Optional

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


def _coerce_datetimes(value):
    """Recursively convert datetime objects to ISO strings (Firestore returns datetimes)."""
    if isinstance(value, dict):
        return {k: _coerce_datetimes(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce_datetimes(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class FirestoreOut(BaseModel):
    """Base response model that tolerates Firestore datetime values in dicts."""

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, value):
        return _coerce_datetimes(value)
