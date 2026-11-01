from pydantic import BaseModel, EmailStr, Field


class OwnerSetupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class MfaEnableResponse(BaseModel):
    secret: str
    qr_uri: str


class MfaVerifyRequest(BaseModel):
    totp_code: str


class CurrentUserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    totp_enabled: bool
    csrf_token: str

    class Config:
        from_attributes = True
