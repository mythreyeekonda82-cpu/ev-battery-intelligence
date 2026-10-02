from typing import Optional

from pydantic import BaseModel, EmailStr


# ============================================================
# AUTHENTICATION
# ============================================================

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "user"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "user"


class LoginResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[int] = None
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None


# ============================================================
# BATTERY ANALYSIS
# ============================================================

class BatteryAnalysisRequest(BaseModel):
    voltage: float
    current: float
    temperature: float
    soc: float
    cycles: int = 0
    remaining_ah: float = 0.0


class BatteryAnalysisResponse(BaseModel):
    soc: float
    health: str
    runtime_hours: Optional[float] = None
    protection: list = []


# ============================================================
# NOTIFICATIONS
# ============================================================

class NotificationRequest(BaseModel):
    message: str
    email: Optional[EmailStr] = None
    whatsapp: Optional[str] = None


# ============================================================
# SETTINGS
# ============================================================

class SettingsUpdate(BaseModel):
    temperature_warning: float = 40.0
    temperature_critical: float = 45.0
    soc_warning: float = 20.0
    soh_warning: float = 85.0

    email_enabled: bool = True
    whatsapp_enabled: bool = False
    weekly_reports: bool = True


class SettingsResponse(BaseModel):
    success: bool
    message: str
    settings: Optional[dict] = None


# ============================================================
# ALERTS
# ============================================================

class AlertResponse(BaseModel):
    id: int
    battery_id: Optional[str] = None
    alert_type: str
    severity: str
    message: str
    is_read: bool


# ============================================================
# API RESPONSE
# ============================================================

class MessageResponse(BaseModel):
    success: bool
    message: str