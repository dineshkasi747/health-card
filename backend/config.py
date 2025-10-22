"""
Extended Configuration Module for Digital Health Card System
Handles all environment variables and application settings including
medication tracking, appointments, vitals, wearables, and AI features
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
# from dotenv import load_dotenv

# load_dotenv()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    
    # Application
    APP_NAME: str = "Digital Health Card System"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = Field(default=False)
    BASE_URL: str = Field(default="http://localhost:8000")
    
    # Database
    MONGO_URI: str = Field(default="mongodb://localhost:27017/health_card_db")
    DB_NAME: str = Field(default="health_card_db")
    
    # JWT Authentication
    JWT_SECRET: str = Field(default="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    
    # Cloudinary
    CLOUD_NAME: str = Field(default="")
    CLOUD_API_KEY: str = Field(default="")
    CLOUD_API_SECRET: str = Field(default="")
    
    # CORS - stored as string, parsed to list via property
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:5173,http://localhost:8080")
    
    # File Upload
    MAX_FILE_SIZE_MB: int = Field(default=10)
    ALLOWED_FILE_TYPES: str = Field(default="application/pdf,image/jpeg,image/png")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    
    # Admin Credentials (for seeding)
    ADMIN_EMAIL: Optional[str] = Field(default=None)
    ADMIN_PASSWORD: Optional[str] = Field(default=None)
    ADMIN_NAME: Optional[str] = Field(default="System Admin")
    
    # AI/OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    CLAUDE_API_KEY: Optional[str] = Field(default=None)
    AI_MODEL: str = Field(default="gpt-3.5-turbo")
    AI_MAX_TOKENS: int = Field(default=500)
    AI_TEMPERATURE: float = Field(default=0.7)
    
    # Medication Reminder Settings
    MEDICATION_REMINDER_ADVANCE_MINUTES: int = Field(default=15)
    MEDICATION_ADHERENCE_THRESHOLD: float = Field(default=80.0)
    
    # Appointment Settings
    APPOINTMENT_REMINDER_HOURS: int = Field(default=24)
    APPOINTMENT_CANCELLATION_HOURS: int = Field(default=24)
    
    # Wearable Integration
    FITBIT_CLIENT_ID: Optional[str] = Field(default=None)
    FITBIT_CLIENT_SECRET: Optional[str] = Field(default=None)
    APPLE_HEALTH_CLIENT_ID: Optional[str] = Field(default=None)
    GARMIN_API_KEY: Optional[str] = Field(default=None)
    
    # Google Maps API (for hospital search)
    GOOGLE_MAPS_API_KEY: Optional[str] = Field(default=None)
    
    # Notification Settings
    ENABLE_EMAIL_NOTIFICATIONS: bool = Field(default=False)
    ENABLE_SMS_NOTIFICATIONS: bool = Field(default=False)
    ENABLE_PUSH_NOTIFICATIONS: bool = Field(default=True)
    
    # Email Configuration (for notifications)
    SMTP_HOST: Optional[str] = Field(default=None)
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: Optional[str] = Field(default=None)
    SMTP_PASSWORD: Optional[str] = Field(default=None)
    SMTP_FROM_EMAIL: Optional[str] = Field(default=None)
    
    # SMS Configuration (Twilio)
    TWILIO_ACCOUNT_SID: Optional[str] = Field(default=None)
    TWILIO_AUTH_TOKEN: Optional[str] = Field(default=None)
    TWILIO_PHONE_NUMBER: Optional[str] = Field(default=None)
    
    # OCR Configuration
    TESSERACT_PATH: Optional[str] = Field(default=None)
    OCR_LANGUAGE: str = Field(default="eng")
    
    # Analytics & Monitoring
    ENABLE_ANALYTICS: bool = Field(default=True)
    SENTRY_DSN: Optional[str] = Field(default=None)
    
    # Data Retention
    AUDIT_LOG_RETENTION_DAYS: int = Field(default=90)
    CHAT_HISTORY_RETENTION_DAYS: int = Field(default=180)
    NOTIFICATION_RETENTION_DAYS: int = Field(default=30)
    
    # Emergency Access
    EMERGENCY_QR_EXPIRY_HOURS: Optional[int] = Field(default=None)  # None = never expires
    EMERGENCY_ACCESS_LOG_RETENTION_DAYS: int = Field(default=365)
    
    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Ensure JWT secret is strong enough"""
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long")
        return v
    
    @field_validator("BASE_URL")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure BASE_URL doesn't end with slash"""
        return v.rstrip("/")
    
    @field_validator("MEDICATION_ADHERENCE_THRESHOLD")
    @classmethod
    def validate_adherence_threshold(cls, v: float) -> float:
        """Ensure adherence threshold is between 0 and 100"""
        if not 0 <= v <= 100:
            raise ValueError("Adherence threshold must be between 0 and 100")
        return v
    
    @field_validator("AI_TEMPERATURE")
    @classmethod
    def validate_ai_temperature(cls, v: float) -> float:
        """Ensure AI temperature is valid"""
        if not 0 <= v <= 2:
            raise ValueError("AI temperature must be between 0 and 2")
        return v
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list"""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return []
    
    @property
    def allowed_file_types_list(self) -> List[str]:
        """Get allowed file types as a list"""
        if isinstance(self.ALLOWED_FILE_TYPES, str):
            return [ft.strip() for ft in self.ALLOWED_FILE_TYPES.split(",") if ft.strip()]
        return []
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "allow"
    }


# Create global settings instance
settings = Settings()


# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

class DatabaseConfig:
    """Database-specific configuration"""
    
    # Collection names
    USERS_COLLECTION = "users"
    PATIENTS_COLLECTION = "patients"
    DOCTORS_COLLECTION = "doctors"
    MEDICATIONS_COLLECTION = "medications"
    MEDICATION_LOGS_COLLECTION = "medication_logs"
    APPOINTMENTS_COLLECTION = "appointments"
    VITALS_COLLECTION = "vitals"
    LAB_RESULTS_COLLECTION = "lab_results"
    CHAT_MESSAGES_COLLECTION = "chat_messages"
    WEARABLE_CONNECTIONS_COLLECTION = "wearable_connections"
    INSURANCE_POLICIES_COLLECTION = "insurance_policies"
    CONSENTS_COLLECTION = "consents"
    FAMILY_MEMBERS_COLLECTION = "family_members"
    NOTIFICATIONS_COLLECTION = "notifications"
    AUDIT_LOGS_COLLECTION = "audit_logs"
    
    # Index definitions
    INDEXES = {
        USERS_COLLECTION: [
            {"keys": [("email", 1)], "unique": True},
            {"keys": [("role", 1)]},
            {"keys": [("created_at", -1)]},
        ],
        PATIENTS_COLLECTION: [
            {"keys": [("user_id", 1)], "unique": True},
            {"keys": [("qr_token", 1)], "unique": True},
            {"keys": [("assigned_doctor_id", 1)]},
        ],
        DOCTORS_COLLECTION: [
            {"keys": [("user_id", 1)], "unique": True},
            {"keys": [("specialization", 1)]},
        ],
        MEDICATIONS_COLLECTION: [
            {"keys": [("patient_id", 1), ("is_active", 1)]},
            {"keys": [("start_date", -1)]},
        ],
        MEDICATION_LOGS_COLLECTION: [
            {"keys": [("medication_id", 1), ("created_at", -1)]},
            {"keys": [("patient_id", 1), ("created_at", -1)]},
        ],
        APPOINTMENTS_COLLECTION: [
            {"keys": [("patient_id", 1), ("scheduled_date", -1)]},
            {"keys": [("doctor_id", 1), ("scheduled_date", -1)]},
            {"keys": [("status", 1)]},
        ],
        VITALS_COLLECTION: [
            {"keys": [("patient_id", 1), ("recorded_at", -1)]},
            {"keys": [("vital_type", 1)]},
        ],
        LAB_RESULTS_COLLECTION: [
            {"keys": [("patient_id", 1), ("test_date", -1)]},
        ],
        CHAT_MESSAGES_COLLECTION: [
            {"keys": [("patient_id", 1), ("session_id", 1)]},
            {"keys": [("created_at", -1)]},
        ],
        WEARABLE_CONNECTIONS_COLLECTION: [
            {"keys": [("patient_id", 1), ("is_active", 1)]},
            {"keys": [("device_id", 1)], "unique": True},
        ],
        INSURANCE_POLICIES_COLLECTION: [
            {"keys": [("patient_id", 1), ("is_active", 1)]},
        ],
        CONSENTS_COLLECTION: [
            {"keys": [("patient_id", 1), ("consent_type", 1)]},
            {"keys": [("granted_to", 1)]},
        ],
        FAMILY_MEMBERS_COLLECTION: [
            {"keys": [("primary_user_id", 1)]},
        ],
        NOTIFICATIONS_COLLECTION: [
            {"keys": [("user_id", 1), ("is_read", 1)]},
            {"keys": [("created_at", -1)]},
        ],
        AUDIT_LOGS_COLLECTION: [
            {"keys": [("user_id", 1)]},
            {"keys": [("created_at", -1)]},
            {"keys": [("action", 1)]},
        ],
    }


db_config = DatabaseConfig()


# ============================================================================
# CLOUDINARY CONFIGURATION
# ============================================================================

class CloudinaryConfig:
    """Cloudinary-specific configuration"""
    
    # Folder structure
    QR_CODES_FOLDER = "health_card/qr_codes"
    PRESCRIPTIONS_FOLDER = "health_card/prescriptions"
    PROFILE_IMAGES_FOLDER = "health_card/profiles"
    LAB_RESULTS_FOLDER = "health_card/lab_results"
    INSURANCE_DOCS_FOLDER = "health_card/insurance"
    
    # Upload presets
    IMAGE_UPLOAD_PRESET = {
        "quality": "auto:good",
        "fetch_format": "auto",
        "flags": "progressive",
    }
    
    PDF_UPLOAD_PRESET = {
        "resource_type": "raw",
        "flags": "attachment",
    }
    
    QR_UPLOAD_PRESET = {
        "quality": "auto:best",
        "format": "png",
        "transformation": [
            {"width": 400, "height": 400, "crop": "fit"}
        ],
    }


cloudinary_config = CloudinaryConfig()


# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

class SecurityConfig:
    """Security-related configuration"""
    
    # Password policy
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL_CHAR = False
    
    # Password hashing
    BCRYPT_ROUNDS = 12
    
    # Token configuration
    TOKEN_URL = "/auth/login"
    
    # Allowed roles
    ROLES = ["admin", "doctor", "patient"]
    
    # Role permissions matrix
    PERMISSIONS = {
        "admin": [
            "users:read", "users:write", "users:delete",
            "patients:read", "patients:write",
            "doctors:read", "doctors:write",
            "medications:read", "appointments:read",
            "vitals:read", "lab_results:read",
            "audit_logs:read", "notifications:read",
        ],
        "doctor": [
            "patients:read", "prescriptions:read", "prescriptions:write",
            "medications:read", "appointments:read", "appointments:write",
            "vitals:read", "lab_results:read", "lab_results:write",
            "qr:scan", "notifications:read",
        ],
        "patient": [
            "patients:read_own", "patients:write_own",
            "prescriptions:read_own", "prescriptions:write_own",
            "medications:read_own", "medications:write_own",
            "appointments:read_own", "appointments:write_own",
            "vitals:read_own", "vitals:write_own",
            "lab_results:read_own",
            "qr:read_own", "notifications:read_own",
        ],
    }


security_config = SecurityConfig()


# ============================================================================
# FILE UPLOAD CONFIGURATION
# ============================================================================

class FileUploadConfig:
    """File upload configuration"""
    
    # File size limits (in bytes)
    MAX_PRESCRIPTION_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_PROFILE_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_LAB_RESULT_SIZE = 15 * 1024 * 1024  # 15MB
    
    # Allowed MIME types
    PRESCRIPTION_MIME_TYPES = [
        "application/pdf",
        "image/jpeg",
        "image/jpg",
        "image/png",
    ]
    
    PROFILE_IMAGE_MIME_TYPES = [
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    ]
    
    LAB_RESULT_MIME_TYPES = [
        "application/pdf",
        "image/jpeg",
        "image/jpg",
        "image/png",
    ]
    
    # File extensions
    PRESCRIPTION_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"]
    PROFILE_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]
    LAB_RESULT_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"]


file_upload_config = FileUploadConfig()


# ============================================================================
# QR CODE CONFIGURATION
# ============================================================================

class QRConfig:
    """QR code generation configuration"""
    
    # QR code parameters
    VERSION = 1  # Size of QR code
    BOX_SIZE = 10  # Size of each box in pixels
    BORDER = 5  # Border size in boxes
    
    # Colors
    FILL_COLOR = "black"
    BACK_COLOR = "white"
    
    # Token settings
    TOKEN_LENGTH = 36  # UUID length
    TOKEN_EXPIRY_DAYS = None  # Never expire (or set to a number)
    
    # QR code URL format
    @staticmethod
    def get_qr_url(base_url: str, token: str) -> str:
        """Generate QR code URL"""
        return f"{base_url}/api/qr/resolve/{token}"
    
    @staticmethod
    def get_emergency_qr_url(base_url: str, token: str) -> str:
        """Generate emergency QR code URL"""
        return f"{base_url}/emergency/{token}"


qr_config = QRConfig()


# ============================================================================
# MEDICATION CONFIGURATION
# ============================================================================

class MedicationConfig:
    """Medication tracking configuration"""
    
    # Reminder settings
    DEFAULT_REMINDER_ADVANCE_MINUTES = 15
    MAX_REMINDERS_PER_DAY = 10
    
    # Adherence calculation
    ADHERENCE_EXCELLENT = 90.0
    ADHERENCE_GOOD = 80.0
    ADHERENCE_FAIR = 70.0
    ADHERENCE_POOR = 70.0  # Below this
    
    # Interaction checking
    ENABLE_DRUG_INTERACTION_CHECK = True
    
    # Common medication frequencies (times per day)
    FREQUENCY_TIMES = {
        "once_daily": ["09:00"],
        "twice_daily": ["09:00", "21:00"],
        "three_times_daily": ["08:00", "14:00", "20:00"],
        "four_times_daily": ["08:00", "12:00", "16:00", "20:00"],
    }


medication_config = MedicationConfig()


# ============================================================================
# APPOINTMENT CONFIGURATION
# ============================================================================

class AppointmentConfig:
    """Appointment management configuration"""
    
    # Reminder settings
    REMINDER_HOURS_BEFORE = [24, 2]  # Send reminders 24h and 2h before
    
    # Scheduling constraints
    MIN_ADVANCE_BOOKING_HOURS = 2
    MAX_ADVANCE_BOOKING_DAYS = 90
    APPOINTMENT_DURATION_MINUTES = 30
    
    # Cancellation policy
    MIN_CANCELLATION_HOURS = 24
    
    # Status transitions
    ALLOWED_STATUS_TRANSITIONS = {
        "scheduled": ["confirmed", "rescheduled", "cancelled"],
        "confirmed": ["completed", "rescheduled", "cancelled", "no_show"],
        "rescheduled": ["confirmed", "cancelled"],
        "cancelled": [],
        "completed": [],
        "no_show": [],
    }


appointment_config = AppointmentConfig()


# ============================================================================
# VITALS CONFIGURATION
# ============================================================================

class VitalsConfig:
    """Vital signs configuration"""
    
    # Normal ranges (for alerts)
    NORMAL_RANGES = {
        "heart_rate": {"min": 60, "max": 100, "unit": "bpm"},
        "blood_pressure_systolic": {"min": 90, "max": 140, "unit": "mmHg"},
        "blood_pressure_diastolic": {"min": 60, "max": 90, "unit": "mmHg"},
        "temperature": {"min": 36.1, "max": 37.2, "unit": "°C"},
        "oxygen_saturation": {"min": 95, "max": 100, "unit": "%"},
        "respiratory_rate": {"min": 12, "max": 20, "unit": "breaths/min"},
        "blood_glucose": {"min": 70, "max": 140, "unit": "mg/dL"},
    }
    
    # Sync frequency from wearables
    WEARABLE_SYNC_INTERVAL_MINUTES = 60


vitals_config = VitalsConfig()


# ============================================================================
# AI ASSISTANT CONFIGURATION
# ============================================================================

class AIConfig:
    """AI health assistant configuration"""
    
    # Model settings
    DEFAULT_MODEL = "gpt-3.5-turbo"
    MAX_TOKENS = 500
    TEMPERATURE = 0.7
    
    # Intent categories
    INTENTS = [
        "medication_inquiry",
        "symptom_check",
        "appointment_booking",
        "health_advice",
        "emergency",
        "general_inquiry",
    ]
    
    # Emergency keywords
    EMERGENCY_KEYWORDS = [
        "emergency", "urgent", "chest pain", "breathing difficulty",
        "severe pain", "unconscious", "bleeding heavily", "heart attack",
        "stroke", "seizure",
    ]
    
    # System prompt
    SYSTEM_PROMPT = """You are a helpful health assistant. Provide general health information 
    and guidance, but always remind users to consult healthcare professionals for medical advice. 
    Never diagnose conditions or prescribe treatments. Be empathetic and supportive."""
    
    # Session settings
    SESSION_TIMEOUT_MINUTES = 30
    MAX_MESSAGES_PER_SESSION = 50


ai_config = AIConfig()


# ============================================================================
# NOTIFICATION CONFIGURATION
# ============================================================================

class NotificationConfig:
    """Notification system configuration"""
    
    # Notification types
    PRESCRIPTION_UPLOADED = "prescription_uploaded"
    PATIENT_UPDATED = "patient_updated"
    DOCTOR_ASSIGNED = "doctor_assigned"
    APPOINTMENT_REMINDER = "appointment_reminder"
    MEDICATION_REMINDER = "medication_reminder"
    LAB_RESULT_AVAILABLE = "lab_result_available"
    HEALTH_ALERT = "health_alert"
    
    # Notification retention
    RETENTION_DAYS = 30
    
    # WebSocket settings
    WS_HEARTBEAT_INTERVAL = 30  # seconds
    WS_MAX_CONNECTIONS_PER_USER = 5
    
    # Delivery channels
    CHANNELS = ["in_app", "email", "sms", "push"]


notification_config = NotificationConfig()


# ============================================================================
# API RESPONSE CONFIGURATION
# ============================================================================

class APIResponseConfig:
    """Standard API response configuration"""
    
    # Response status codes
    STATUS_SUCCESS = "success"
    STATUS_ERROR = "error"
    STATUS_WARNING = "warning"
    
    # Standard messages
    MESSAGES = {
        "user_created": "User created successfully",
        "user_updated": "User updated successfully",
        "login_success": "Login successful",
        "medication_added": "Medication added successfully",
        "appointment_booked": "Appointment booked successfully",
        "vital_recorded": "Vital sign recorded successfully",
        "unauthorized": "Unauthorized access",
        "forbidden": "Access forbidden",
        "not_found": "Resource not found",
        "validation_error": "Validation error",
        "server_error": "Internal server error",
    }


api_response_config = APIResponseConfig()


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

class LoggingConfig:
    """Logging configuration"""
    
    # Log format
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    # Log levels
    LOG_LEVELS = {
        "development": "DEBUG",
        "staging": "INFO",
        "production": "WARNING",
    }
    
    # Log file settings
    LOG_FILE = "health_card.log"
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5


logging_config = LoggingConfig()


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def validate_email(email: str) -> bool:
    """Validate email format"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return bool(re.match(pattern, email))


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password against security policy"""
    if len(password) < security_config.MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {security_config.MIN_PASSWORD_LENGTH} characters"
    
    if security_config.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        return False, "Password must contain uppercase letter"
    
    if security_config.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        return False, "Password must contain lowercase letter"
    
    if security_config.REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        return False, "Password must contain digit"
    
    if security_config.REQUIRE_SPECIAL_CHAR:
        import re
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain special character"
    
    return True, ""


def validate_phone(phone: str) -> bool:
    """Validate phone number format"""
    import re
    pattern = r'^\+?[\d\s\-()]{10,20}'
    return bool(re.match(pattern, phone))


# ============================================================================
# EXPORT ALL CONFIGURATIONS
# ============================================================================

__all__ = [
    "settings",
    "db_config",
    "cloudinary_config",
    "security_config",
    "file_upload_config",
    "qr_config",
    "medication_config",
    "appointment_config",
    "vitals_config",
    "ai_config",
    "notification_config",
    "api_response_config",
    "logging_config",
    "validate_email",
    "validate_password",
    "validate_phone",
]