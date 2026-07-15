from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class CaseBase(BaseModel):
    pick_location: str
    drop_location: str
    cargo_weight: float
    vehicle_type: str
    freight_rate: float
    pickup_date: str
    pickup_time: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None

class CaseCreate(CaseBase):
    pass

class Case(CaseBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class PostingHistoryBase(BaseModel):
    case_id: int
    platform: str
    status: str = "pending"
    error_message: Optional[str] = None

class PostingHistory(PostingHistoryBase):
    id: int
    posted_at: datetime

    class Config:
        from_attributes = True

class CaseWithPostingHistory(Case):
    posting_history: list[PostingHistory] = []
