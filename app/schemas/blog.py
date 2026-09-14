from pydantic import BaseModel
from datetime import datetime


class BlogQACreate(BaseModel):
    question: str


class BlogQAUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None


class BlogQAOut(BaseModel):
    id: str
    question: str
    answer: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
