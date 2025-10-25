"""
Data Models for Digital Health Card System
Pydantic models for API requests and responses
"""

from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, field_validator


# ============================================================================
# ENUMS
# ============================================================================

class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    DOCTOR = "doctor"
    PATIENT = "patient"


class MedicationFrequency(str, Enum):
    """Medication frequency enumeration"""
    ONCE_DAILY = "once_daily"
    TWICE_DAILY = "twice_daily"
    THREE_TIMES_DAILY = "three_times_daily"
    FOUR_TIMES_DAILY = "four_times_daily"
    EVERY_4_HOURS = "every_4_hours"
    EVERY_6_HOURS = "every_6_hours"
    EVERY_8_HOURS = "every_8_hours"
    EVERY_12_HOURS = "every_12_hours"
    WEEKLY = "weekly"
    AS_NEEDED = "as_needed"
    CUSTOM = "custom"


class AppointmentStatus(str, Enum):
    """Appointment status enumeration"""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class ConsultationType(str, Enum):
    """Consultation type enumeration"""
    IN_PERSON = "in_person"
    VIDEO_CALL = "video_call"
    PHONE_CALL = "phone_call"
    FOLLOW_UP = "follow_up"
    EMERGENCY = "emergency"


class VitalType(str, Enum):
    """Vital sign type enumeration"""
    HEART_RATE = "heart_rate"
    BLOOD_PRESSURE_SYSTOLIC = "blood_pressure_systolic"
    BLOOD_PRESSURE_DIASTOLIC = "blood_pressure_diastolic"
    TEMPERATURE = "temperature"
    OXYGEN_SATURATION = "oxygen_saturation"
    RESPIRATORY_RATE = "respiratory_rate"
    BLOOD_GLUCOSE = "blood_glucose"
    WEIGHT = "weight"
    HEIGHT = "height"
    BMI = "bmi"


class NotificationType(str, Enum):
    """Notification type enumeration"""
    PRESCRIPTION_UPLOADED = "prescription_uploaded"
    PATIENT_UPDATED = "patient_updated"
    DOCTOR_ASSIGNED = "doctor_assigned"
    APPOINTMENT_REMINDER = "appointment_reminder"
    MEDICATION_REMINDER = "medication_reminder"
    SYSTEM_ALERT = "system_alert"


# ============================================================================
# API REQUEST MODELS
# ============================================================================

class UserCreateRequest(BaseModel):
    """Request schema for user registration"""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    role: UserRole
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v


class UserLoginRequest(BaseModel):
    """Request schema for user login"""
    email: EmailStr
    password: str


class PatientUpdateRequest(BaseModel):
    """Request schema for updating patient profile"""
    blood_group: Optional[str] = None
    allergies: Optional[List[str]] = None
    chronic_conditions: Optional[List[str]] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    medical_summary: Optional[str] = None


class MedicationCreateRequest(BaseModel):
    """Request schema for creating medication"""
    name: str = Field(..., min_length=1, max_length=200)
    dosage: str
    frequency: MedicationFrequency
    custom_frequency: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    times: List[str] = Field(default_factory=list)
    instructions: Optional[str] = None
    reminders_enabled: bool = Field(default=True)


class AppointmentCreateRequest(BaseModel):
    """Request schema for creating appointment"""
    doctor_id: str
    scheduled_date: date
    scheduled_time: str
    consultation_type: ConsultationType
    reason: Optional[str] = None


class VitalRecordRequest(BaseModel):
    """Request schema for vital record"""
    vital_type: VitalType
    value: float
    unit: str
    recorded_at: Optional[datetime] = None
    notes: Optional[str] = None


class ChatRequest(BaseModel):
    """Request schema for AI chat"""
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None


class PrescriptionUploadRequest(BaseModel):
    """Request schema for prescription metadata"""
    notes: Optional[str] = None
    doctor_name: Optional[str] = None
    date_prescribed: Optional[date] = None


# ============================================================================
# API RESPONSE MODELS
# ============================================================================

class UserResponse(BaseModel):
    """Response schema for user data"""
    id: str
    name: str
    email: EmailStr
    role: UserRole
    phone: Optional[str] = None
    profile_image_url: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()}
    }


class StandardResponse(BaseModel):
    """Standard API response wrapper"""
    status: str
    data: Any
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()}
    }


class PaginatedResponse(BaseModel):
    """Paginated API response wrapper"""
    status: str = "success"
    data: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    message: str = "Data retrieved successfully"


class ErrorResponse(BaseModel):
    """Error response schema"""
    status: str = "error"
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()}
    }


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PrescriptionAnalysis(BaseModel):
    """AI analysis result for prescription"""
    summary: str
    medications: List[str]
    dosages: List[str]
    frequency: List[str]
    instructions: List[str]
    warnings: List[str]
    duration: str


class PrescriptionResponse(BaseModel):
    """Prescription response schema"""
    prescription_id: str
    url: str
    extracted_text: str
    ai_analysis: PrescriptionAnalysis


class ChatResponse(BaseModel):
    """Chat response schema"""
    session_id: str
    message: str
    response: str
    intent: str
    suggestions: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()}
    }


class HospitalInfo(BaseModel):
    """Hospital information schema"""
    place_id: Optional[str] = None
    name: str
    address: str
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: float = 0.0
    distance_km: Optional[float] = None
    location: Dict[str, float]
    is_open: Optional[bool] = None
    google_maps_url: Optional[str] = None
    emergency: bool = False


class HospitalsResponse(BaseModel):
    """Hospitals search response"""
    hospitals: List[HospitalInfo]
    user_location: Dict[str, float]
    search_radius_km: Optional[float] = None
    total_found: int
    note: Optional[str] = None


class FitbitStatusResponse(BaseModel):
    """Fitbit connection status"""
    connected: bool
    last_sync: Optional[datetime] = None
    device_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: Optional[str] = None
    
    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()}
    }


class VitalsDashboardResponse(BaseModel):
    """Vitals dashboard data"""
    vitals: Dict[str, Any]
    period_days: int
    last_updated: str


class MedicationResponse(BaseModel):
    """Medication response schema"""
    id: str
    name: str
    dosage: str
    frequency: str
    start_date: str
    end_date: Optional[str] = None
    is_active: bool
    reminders_enabled: bool


class AppointmentResponse(BaseModel):
    """Appointment response schema"""
    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    scheduled_date: str
    scheduled_time: str
    status: str
    consultation_type: str
    reason: Optional[str] = None


# ============================================================================
# EMBEDDED DOCUMENT MODELS
# ============================================================================

class PrescriptionItem(BaseModel):
    """Embedded prescription document"""
    url: str
    public_id: str
    uploaded_at: datetime
    filename: str
    content_type: str
    size_bytes: Optional[int] = None
    
    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()}
    }


class VaccinationRecord(BaseModel):
    """Embedded vaccination record"""
    vaccine_name: str
    dose_number: Optional[int] = None
    administered_date: date
    next_dose_date: Optional[date] = None
    administered_by: Optional[str] = None
    batch_number: Optional[str] = None
    
    model_config = {
        "json_encoders": {date: lambda v: v.isoformat()}
    }


# ============================================================================
# WEBSOCKET MODELS
# ============================================================================

class WebSocketMessage(BaseModel):
    """WebSocket message schema"""
    type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()}
    }


class NotificationMessage(BaseModel):
    """Notification message schema"""
    id: str
    user_id: str
    type: NotificationType
    title: str
    message: str
    is_read: bool = False
    created_at: datetime
    
    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()}
    }


# ============================================================================
# HEALTH CHECK MODEL
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    version: str
    features: Dict[str, bool]


# ============================================================================
# EXPORT ALL MODELS
# ============================================================================

__all__ = [
    # Enums
    "UserRole",
    "MedicationFrequency",
    "AppointmentStatus",
    "ConsultationType",
    "VitalType",
    "NotificationType",
    # Request Models
    "UserCreateRequest",
    "UserLoginRequest",
    "PatientUpdateRequest",
    "MedicationCreateRequest",
    "AppointmentCreateRequest",
    "VitalRecordRequest",
    "ChatRequest",
    "PrescriptionUploadRequest",
    # Response Models
    "UserResponse",
    "StandardResponse",
    "PaginatedResponse",
    "ErrorResponse",
    "TokenResponse",
    "PrescriptionAnalysis",
    "PrescriptionResponse",
    "ChatResponse",
    "HospitalInfo",
    "HospitalsResponse",
    "FitbitStatusResponse",
    "VitalsDashboardResponse",
    "MedicationResponse",
    "AppointmentResponse",
    "HealthCheckResponse",
    # Embedded Models
    "PrescriptionItem",
    "VaccinationRecord",
    # WebSocket Models
    "WebSocketMessage",
    "NotificationMessage",
]