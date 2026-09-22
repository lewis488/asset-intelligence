from typing import Literal, Optional
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    authority_name: str
    region: Optional[str] = None
    role: Literal["admin", "analyst", "viewer"] = "analyst"


class UserOut(BaseModel):
    id: int
    email: str
    authority_id: int
    role: str
    is_admin: bool
    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserOut
