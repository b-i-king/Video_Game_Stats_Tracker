from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr


class LoginResponse(BaseModel):
    token: str
    user_id: int
    is_trusted: bool
    is_owner: bool
    role: str  # "owner" | "trusted" | "premium" | "free"


class AddUserRequest(BaseModel):
    email: EmailStr


class AddTrustedUserRequest(BaseModel):
    email: EmailStr
    is_trusted: bool = True
