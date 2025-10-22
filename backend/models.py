"""
Extended Database and Pydantic Models for Digital Health Card System
Includes models for medications, appointments, vitals, lab results, AI chat, and more
"""

from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, validator, HttpUrl
from bson import ObjectId


# ============================================================================
# CUSTOM TYPES AND ENUMS
# ============================================================================

class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema):
        from pydantic import core_schema
        return core_schema.json_schema(core_schema.str_schema())


class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    DOCTOR = "doctor"
    PATIENT = "patient"


class NotificationType(str, Enum):
    """Notification type enumeration"""
    PRESCRIPTION_UPLOADED = "prescription_uploaded"
    PATIENT_UPDATED = "patient_updated"
    DOCTOR_ASSIGNED = "doctor_assigned"
    APPOINTMENT_REMINDER = "appointment_reminder"
    MEDICATION_REMINDER = "medication_reminder"
    SYSTEM_ALERT = "system_alert"


class FileType(str, Enum):
    """File type enumeration"""
    PDF = "application/pdf"
    JPEG = "image/jpeg"
    JPG = "image/jpg"
    PNG = "image/png"


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


class ConsentType(str, Enum):
    """Consent type enumeration"""
    DATA_SHARING = "data_sharing"
    RESEARCH = "research"
    MARKETING = "marketing"
    EMERGENCY_ACCESS = "emergency_access"
    FAMILY_ACCESS = "family_access"


# ============================================================================
# DATABASE MODELS (MongoDB Documents)
# ============================================================================

class UserDocument(BaseModel):
    """User document schema for MongoDB"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password_hash: str
    role: UserRole
    phone: Optional[str] = None
    profile_image_url: Optional[HttpUrl] = None
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class PrescriptionItem(BaseModel):
    """Embedded prescription document"""
    url: HttpUrl
    public_id: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    filename: str
    content_type: FileType
    size_bytes: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class VaccinationRecord(BaseModel):
    """Embedded vaccination record"""
    vaccine_name: str
    dose_number: Optional[int] = None
    administered_date: date
    next_dose_date: Optional[date] = None
    administered_by: Optional[str] = None
    batch_number: Optional[str] = None


class PatientDocument(BaseModel):
    """Patient document schema for MongoDB"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    qr_token: str = Field(..., min_length=32)
    qr_image_url: HttpUrl
    prescriptions: List[PrescriptionItem] = Field(default_factory=list)
    vaccinations: List[VaccinationRecord] = Field(default_factory=list)
    assigned_doctor_id: Optional[PyObjectId] = None
    medical_summary: Optional[str] = Field(None, max_length=5000)
    blood_group: Optional[str] = Field(None, pattern="^(A|B|AB|O)[+-]$")
    allergies: List[str] = Field(default_factory=list)
    chronic_conditions: List[str] = Field(default_factory=list)
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat(), date: lambda v: v.isoformat()}


class DoctorDocument(BaseModel):
    """Doctor document schema for MongoDB"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    specialization: str = Field(..., min_length=2, max_length=100)
    license_number: Optional[str] = None
    clinic_info: Optional[str] = Field(None, max_length=500)
    consultation_fee: Optional[float] = None
    experience_years: Optional[int] = Field(None, ge=0)
    education: List[str] = Field(default_factory=list)
    patients: List[PyObjectId] = Field(default_factory=list)
    available_days: List[str] = Field(default_factory=list)
    consultation_hours: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class MedicationDocument(BaseModel):
    """Medication document schema for MongoDB"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    patient_id: PyObjectId
    name: str = Field(..., min_length=1, max_length=200)
    dosage: str
    frequency: MedicationFrequency
    custom_frequency: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    times: List[time] = Field(default_factory=list)
    instructions: Optional[str] = None
    is_active: bool = Field(default=True)
    reminders_enabled: bool = Field(default=True)
    interaction_warnings: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            time: lambda v: v.isoformat()
        }


class MedicationLogDocument(BaseModel):
    """Medication log document schema"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    medication_id: PyObjectId
    patient_id: PyObjectId
    taken_at: datetime
    was_taken: bool
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class AppointmentDocument(BaseModel):
    """Appointment document schema for MongoDB"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    patient_id: PyObjectId
    doctor_id: PyObjectId
    scheduled_date: date
    scheduled_time: time
    consultation_type: ConsultationType
    status: AppointmentStatus = Field(default=AppointmentStatus.SCHEDULED)
    reason: Optional[str] = None
    notes: Optional[str] = None
    prescription_url: Optional[HttpUrl] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            time: lambda v: v.isoformat()
        }


class VitalRecordDocument(BaseModel):
    """Vital record document schema"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    patient_id: PyObjectId
    vital_type: VitalType
    value: float
    unit: str
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="manual")  # manual, wearable, clinic
    device_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class LabTestResult(BaseModel):
    """Embedded lab test result"""
    test_name: str
    value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    status: Optional[str] = None  # normal, high, low


class LabResultDocument(BaseModel):
    """Lab result document schema"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    patient_id: PyObjectId
    test_date: date
    lab_name: str
    report_url: Optional[HttpUrl] = None
    tests: List[LabTestResult]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat(), date: lambda v: v.isoformat()}


class ChatMessageDocument(BaseModel):
    """Chat message document for AI assistant"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    patient_id: PyObjectId
    session_id: str
    message: str
    response: str
    intent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class WearableConnectionDocument(BaseModel):
    """Wearable device connection document"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    patient_id: PyObjectId
    device_type: str  # fitbit, apple_watch, garmin, etc.
    device_id: str
    access_token: str
    refresh_token: Optional[str] = None
    is_active: bool = Field(default=True)
    last_sync: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class InsurancePolicyDocument(BaseModel):
    """Insurance policy document"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    patient_id: PyObjectId
    provider_name: str
    policy_number: str
    coverage_type: str
    coverage_amount: Optional[float] = None
    start_date: date
    end_date: Optional[date] = None
    is_active: bool = Field(default=True)
    documents: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat(), date: lambda v: v.isoformat()}


class ConsentDocument(BaseModel):
    """Consent document schema"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    patient_id: PyObjectId
    consent_type: ConsentType
    granted: bool
    granted_to: Optional[PyObjectId] = None  # User ID of doctor/entity
    granted_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    revoked: bool = Field(default=False)
    revoked_at: Optional[datetime] = None
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class FamilyMemberDocument(BaseModel):
    """Family member document"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    primary_user_id: PyObjectId
    member_user_id: Optional[PyObjectId] = None  # If they have an account
    name: str
    relationship: str
    date_of_birth: Optional[date] = None
    can_view_records: bool = Field(default=True)
    can_edit_records: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat(), date: lambda v: v.isoformat()}


class AuditLogDocument(BaseModel):
    """Audit log document"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    action: str
    resource_type: str
    resource_id: Optional[PyObjectId] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


# ============================================================================
# API REQUEST MODELS (Input Schemas)
# ============================================================================

class UserCreateRequest(BaseModel):
    """Request schema for user registration"""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    role: UserRole
    phone: Optional[str] = Field(None, pattern=r'^\+?[\d\s\-()]{10,20}$')
    
    @validator('password')
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


class MedicationCreateRequest(BaseModel):
    """Request schema for creating medication"""
    name: str = Field(..., min_length=1, max_length=200)
    dosage: str
    frequency: MedicationFrequency
    custom_frequency: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    times: List[time] = Field(default_factory=list)
    instructions: Optional[str] = None
    reminders_enabled: bool = Field(default=True)


class AppointmentCreateRequest(BaseModel):
    """Request schema for creating appointment"""
    doctor_id: str
    scheduled_date: date
    scheduled_time: time
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


class InsurancePolicyRequest(BaseModel):
    """Request schema for insurance policy"""
    provider_name: str
    policy_number: str
    coverage_type: str
    coverage_amount: Optional[float] = None
    start_date: date
    end_date: Optional[date] = None


class ConsentRequest(BaseModel):
    """Request schema for consent"""
    consent_type: ConsentType
    granted: bool
    granted_to: Optional[str] = None  # User ID
    expires_at: Optional[datetime] = None


# ============================================================================
# API RESPONSE MODELS (Output Schemas)
# ============================================================================

class UserResponse(BaseModel):
    """Response schema for user data"""
    id: str
    name: str
    email: EmailStr
    role: UserRole
    phone: Optional[str] = None
    profile_image_url: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class StandardResponse(BaseModel):
    """Standard API response wrapper"""
    status: str = Field(..., pattern="^(success|error|warning)$")
    data: Any
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


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
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============================================================================
# EXPORT ALL MODELS
# ============================================================================

__all__ = [
    # Enums
    "UserRole", "NotificationType", "FileType", "MedicationFrequency",
    "AppointmentStatus", "ConsultationType", "VitalType", "ConsentType",
    # Database Models
    "UserDocument", "PatientDocument", "DoctorDocument", "MedicationDocument",
    "MedicationLogDocument", "AppointmentDocument", "VitalRecordDocument",
    "LabResultDocument", "ChatMessageDocument", "WearableConnectionDocument",
    "InsurancePolicyDocument", "ConsentDocument", "FamilyMemberDocument",
    "AuditLogDocument", "PrescriptionItem", "VaccinationRecord", "LabTestResult",
    # Request Models
    "UserCreateRequest", "UserLoginRequest", "MedicationCreateRequest",
    "AppointmentCreateRequest", "VitalRecordRequest", "ChatRequest",
    "InsurancePolicyRequest", "ConsentRequest",
    # Response Models
    "UserResponse", "StandardResponse", "PaginatedResponse", "ErrorResponse",
]
# """
# Extended Database and Pydantic Models for Digital Health Card System
# Complete and error-free version
# """

# from datetime import datetime, date, time
# from typing import Optional, List, Dict, Any
# from enum import Enum
# from pydantic import BaseModel, EmailStr, Field, field_validator
# from bson import ObjectId


# # ============================================================================
# # CUSTOM TYPES AND ENUMS
# # ============================================================================

# class PyObjectId(ObjectId):
#     """Custom ObjectId type for Pydantic"""
    
#     @classmethod
#     def __get_validators__(cls):
#         yield cls.validate
    
#     @classmethod
#     def validate(cls, v):
#         if not ObjectId.is_valid(v):
#             raise ValueError("Invalid ObjectId")
#         return ObjectId(v)
    
#     @classmethod
#     def __get_pydantic_core_schema__(cls, source_type, handler):
#         return {"type": "str"}


# class UserRole(str, Enum):
#     """User role enumeration"""
#     ADMIN = "admin"
#     DOCTOR = "doctor"
#     PATIENT = "patient"


# class NotificationType(str, Enum):
#     """Notification type enumeration"""
#     PRESCRIPTION_UPLOADED = "prescription_uploaded"
#     PATIENT_UPDATED = "patient_updated"
#     DOCTOR_ASSIGNED = "doctor_assigned"
#     APPOINTMENT_REMINDER = "appointment_reminder"
#     MEDICATION_REMINDER = "medication_reminder"
#     SYSTEM_ALERT = "system_alert"


# class FileType(str, Enum):
#     """File type enumeration"""
#     PDF = "application/pdf"
#     JPEG = "image/jpeg"
#     JPG = "image/jpg"
#     PNG = "image/png"


# class MedicationFrequency(str, Enum):
#     """Medication frequency enumeration"""
#     ONCE_DAILY = "once_daily"
#     TWICE_DAILY = "twice_daily"
#     THREE_TIMES_DAILY = "three_times_daily"
#     FOUR_TIMES_DAILY = "four_times_daily"
#     EVERY_4_HOURS = "every_4_hours"
#     EVERY_6_HOURS = "every_6_hours"
#     EVERY_8_HOURS = "every_8_hours"
#     EVERY_12_HOURS = "every_12_hours"
#     WEEKLY = "weekly"
#     AS_NEEDED = "as_needed"
#     CUSTOM = "custom"


# class AppointmentStatus(str, Enum):
#     """Appointment status enumeration"""
#     SCHEDULED = "scheduled"
#     CONFIRMED = "confirmed"
#     RESCHEDULED = "rescheduled"
#     CANCELLED = "cancelled"
#     COMPLETED = "completed"
#     NO_SHOW = "no_show"


# class ConsultationType(str, Enum):
#     """Consultation type enumeration"""
#     IN_PERSON = "in_person"
#     VIDEO_CALL = "video_call"
#     PHONE_CALL = "phone_call"
#     FOLLOW_UP = "follow_up"
#     EMERGENCY = "emergency"


# class VitalType(str, Enum):
#     """Vital sign type enumeration"""
#     HEART_RATE = "heart_rate"
#     BLOOD_PRESSURE_SYSTOLIC = "blood_pressure_systolic"
#     BLOOD_PRESSURE_DIASTOLIC = "blood_pressure_diastolic"
#     TEMPERATURE = "temperature"
#     OXYGEN_SATURATION = "oxygen_saturation"
#     RESPIRATORY_RATE = "respiratory_rate"
#     BLOOD_GLUCOSE = "blood_glucose"
#     WEIGHT = "weight"
#     HEIGHT = "height"
#     BMI = "bmi"


# class ConsentType(str, Enum):
#     """Consent type enumeration"""
#     DATA_SHARING = "data_sharing"
#     RESEARCH = "research"
#     MARKETING = "marketing"
#     EMERGENCY_ACCESS = "emergency_access"
#     FAMILY_ACCESS = "family_access"


# # ============================================================================
# # API REQUEST MODELS (Input Schemas)
# # ============================================================================

# class UserCreateRequest(BaseModel):
#     """Request schema for user registration"""
#     name: str = Field(..., min_length=2, max_length=100)
#     email: EmailStr
#     password: str = Field(..., min_length=8, max_length=100)
#     role: UserRole
#     phone: Optional[str] = None
#     date_of_birth: Optional[date] = None
#     gender: Optional[str] = None
    
#     @field_validator('password')
#     @classmethod
#     def validate_password(cls, v):
#         if len(v) < 8:
#             raise ValueError('Password must be at least 8 characters')
#         if not any(c.isupper() for c in v):
#             raise ValueError('Password must contain uppercase letter')
#         if not any(c.islower() for c in v):
#             raise ValueError('Password must contain lowercase letter')
#         if not any(c.isdigit() for c in v):
#             raise ValueError('Password must contain digit')
#         return v


# class UserLoginRequest(BaseModel):
#     """Request schema for user login"""
#     email: EmailStr
#     password: str


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


# class MedicationCreateRequest(BaseModel):
#     """Request schema for creating medication"""
#     name: str = Field(..., min_length=1, max_length=200)
#     dosage: str
#     frequency: MedicationFrequency
#     custom_frequency: Optional[str] = None
#     start_date: date
#     end_date: Optional[date] = None
#     times: List[str] = Field(default_factory=list)
#     instructions: Optional[str] = None
#     reminders_enabled: bool = Field(default=True)


# class AppointmentCreateRequest(BaseModel):
#     """Request schema for creating appointment"""
#     doctor_id: str
#     scheduled_date: date
#     scheduled_time: str
#     consultation_type: ConsultationType
#     reason: Optional[str] = None


# class VitalRecordRequest(BaseModel):
#     """Request schema for vital record"""
#     vital_type: VitalType
#     value: float
#     unit: str
#     recorded_at: Optional[datetime] = None
#     notes: Optional[str] = None


# class ChatRequest(BaseModel):
#     """Request schema for AI chat"""
#     message: str = Field(..., min_length=1, max_length=1000)
#     session_id: Optional[str] = None


# class InsurancePolicyRequest(BaseModel):
#     """Request schema for insurance policy"""
#     provider_name: str
#     policy_number: str
#     coverage_type: str
#     coverage_amount: Optional[float] = None
#     start_date: date
#     end_date: Optional[date] = None


# class ConsentRequest(BaseModel):
#     """Request schema for consent"""
#     consent_type: ConsentType
#     granted: bool
#     granted_to: Optional[str] = None
#     expires_at: Optional[datetime] = None


# # ============================================================================
# # API RESPONSE MODELS (Output Schemas)
# # ============================================================================

# class UserResponse(BaseModel):
#     """Response schema for user data"""
#     id: str
#     name: str
#     email: EmailStr
#     role: UserRole
#     phone: Optional[str] = None
#     profile_image_url: Optional[str] = None
#     is_active: bool
#     is_verified: bool
#     created_at: datetime
#     updated_at: datetime
    
#     class Config:
#         json_encoders = {datetime: lambda v: v.isoformat()}


# class StandardResponse(BaseModel):
#     """Standard API response wrapper"""
#     status: str
#     data: Any
#     message: str
#     timestamp: datetime = Field(default_factory=datetime.utcnow)
    
#     class Config:
#         json_encoders = {datetime: lambda v: v.isoformat()}


# class PaginatedResponse(BaseModel):
#     """Paginated API response wrapper"""
#     status: str = "success"
#     data: List[Any]
#     total: int
#     page: int
#     page_size: int
#     total_pages: int
#     message: str = "Data retrieved successfully"


# class ErrorResponse(BaseModel):
#     """Error response schema"""
#     status: str = "error"
#     error: str
#     detail: Optional[str] = None
#     timestamp: datetime = Field(default_factory=datetime.utcnow)
    
#     class Config:
#         json_encoders = {datetime: lambda v: v.isoformat()}


# # ============================================================================
# # EXPORT ALL MODELS
# # ============================================================================

# __all__ = [
#     # Enums
#     "UserRole", "NotificationType", "FileType", "MedicationFrequency",
#     "AppointmentStatus", "ConsultationType", "VitalType", "ConsentType",
#     # Request Models
#     "UserCreateRequest", "UserLoginRequest", "MedicationCreateRequest",
#     "AppointmentCreateRequest", "VitalRecordRequest", "ChatRequest",
#     "InsurancePolicyRequest", "ConsentRequest", "PatientUpdateRequest",
#     # Response Models
#     "UserResponse", "StandardResponse", "PaginatedResponse", "ErrorResponse",
# ]