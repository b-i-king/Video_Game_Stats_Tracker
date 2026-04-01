from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    player_id: int
    username: str
    is_trusted: bool


class AddUserRequest(BaseModel):
    username: str
    password: str
    email: EmailStr | None = None


class AddTrustedUserRequest(BaseModel):
    target_username: str
