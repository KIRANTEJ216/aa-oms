from pydantic import BaseModel, EmailStr, Field

class RegisterRequest(BaseModel):
    name: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=8)
    mobile: str = Field(min_length=10)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class MfaVerifyRequest(BaseModel):
    temp_token: str
    code: str = Field(min_length=6, max_length=6)

class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    qr_data_uri: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class ForgotPasswordRequest(BaseModel):
    email: EmailStr
