from pydantic import BaseModel, EmailStr
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    class Config:
        from_attributes = True

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class RoomCreate(BaseModel):
    title: str

class RoomOut(BaseModel):
    id: int
    slug: str
    title: str
    class Config:
        from_attributes = True

class MessageOut(BaseModel):
    id: int
    room_id: int
    sender_id: int | None
    content: str
    created_at: datetime
    class Config:
        from_attributes = True