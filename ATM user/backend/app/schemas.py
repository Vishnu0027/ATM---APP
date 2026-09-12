import re
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

INDIAN_MOBILE_REGEX = re.compile(r"^(?:\+91|91|0)?[6-9]\d{8,9}$")

class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Full Name of user")
    email: str = Field(..., description="User email address")
    mobile: str = Field(..., description="Indian mobile number")
    password: str = Field(..., min_length=4, max_length=128, description="PIN or Password")
    confirm_password: str = Field(..., description="PIN confirmation")
    terms_accepted: bool = Field(..., description="Must accept Terms & Conditions")

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters long")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Email address is required.")
        v = v.strip().lower()
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", v):
            raise ValueError("Please provide a valid email address.")
        return v

    @field_validator("mobile")
    @classmethod
    def validate_indian_mobile(cls, v: str) -> str:
        # Normalize: remove spaces, dashes, parentheses
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not INDIAN_MOBILE_REGEX.match(cleaned):
            raise ValueError("Invalid Indian mobile number. Must be 9 or 10 digits starting with 6, 7, 8, or 9.")
        # Normalize to 9 or 10 digits
        if cleaned.startswith("+91"):
            cleaned = cleaned[3:]
        elif cleaned.startswith("91") and len(cleaned) >= 11:
            cleaned = cleaned[2:]
        elif cleaned.startswith("0") and len(cleaned) >= 10:
            cleaned = cleaned[1:]
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_pin_or_password(cls, v: str) -> str:
        v = v.strip()
        if v.isdigit():
            if len(v) < 4 or len(v) > 8:
                raise ValueError("PIN must be between 4 and 8 digits containing only numbers")
            return v
        if len(v) < 4:
            raise ValueError("PIN must be at least 4 characters long")
        return v

    @field_validator("terms_accepted")
    @classmethod
    def validate_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the Terms & Conditions to register")
        return v

    @model_validator(mode="after")
    def check_passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("PINs do not match")
        return self

class UserLogin(BaseModel):
    user_name: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    identifier: Optional[str] = None
    password: str = Field(..., min_length=1, description="PIN or password")

class UserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    mobile: str
    is_active: bool = True
    created_at: Optional[datetime] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class LinkedBankResponse(BaseModel):
    id: str
    bank_name: str
    bank_code: str
    account_masked: str
    status: str
    withdrawal_limit: float
    currency: str
    theme_gradient: str

class DashboardSummaryResponse(BaseModel):
    user: UserResponse
    linked_banks_count: int
    active_accounts_count: int
    today_transactions_count: int
    security_status: str
    banks: List[LinkedBankResponse]

class UpdateEmailPayload(BaseModel):
    email: str = Field(..., description="New email address")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Email address is required.")
        v = v.strip().lower()
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", v):
            raise ValueError("Please provide a valid email address.")
        return v

# ============================================================================
# ATM MACHINE & OTP SCHEMAS
# ============================================================================
class ATMSessionResponse(BaseModel):
    session_id: str
    atm_id: str = "ATM-BLR-042"
    status: str = "ACTIVE"
    current_step: str = "MOBILE_ENTRY"
    user_id: Optional[str] = None
    masked_mobile: Optional[str] = None
    user_name: Optional[str] = None
    otp_verified: bool = False
    demo_otp: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

class ATMMobileRequest(BaseModel):
    session_id: str
    mobile: str

class ATMPinRequest(BaseModel):
    session_id: str
    pin: str

class OTPSendRequest(BaseModel):
    session_id: str
    user_id: Optional[str] = None

class OTPVerifyRequest(BaseModel):
    session_id: str
    otp: str

class OTPResendRequest(BaseModel):
    session_id: str

class ATMWithdrawRequest(BaseModel):
    session_id: str
    bank_id: str
    bank_pin: str
    amount: float

class ATMTransactionResponse(BaseModel):
    status: str
    transaction_id: str
    session_id: str
    amount: float
    bank_name: str
    account_masked: str
    atm_id: str
    timestamp: datetime
    message: str

class OTPVerifyResponse(BaseModel):
    status: str
    message: str
    session_id: str
    current_step: str = "BANK_SELECTION"
    otp_verified: bool = True
    user_id: Optional[str] = None
    masked_mobile: Optional[str] = None

class OTPResendResponse(BaseModel):
    status: str
    message: str
    resend_cooldown: int = 30
    demo_otp: Optional[str] = None
    expires_in: int = 300


class ActiveOTPDetails(BaseModel):
    session_id: str
    atm_id: str
    otp_code: str
    expires_in_seconds: int
    created_at: str
    expires_at: str


class ActiveOTPResponse(BaseModel):
    has_active_otp: bool
    otp: Optional[ActiveOTPDetails] = None



