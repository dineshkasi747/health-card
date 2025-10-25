"""
Configuration Module for Digital Health Card System
Handles all environment variables and application settings
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


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
    
    # CORS
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:5173,http://localhost:8080")
    
    # AI Configuration - Gemini
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    AI_MODEL: str = Field(default="gemini-pro")
    AI_MAX_TOKENS: int = Field(default=500)
    AI_TEMPERATURE: float = Field(default=0.7)
    
    # Google Maps API
    GOOGLE_MAPS_API_KEY: Optional[str] = Field(default=None)
    
    # Fitbit Integration
    FITBIT_CLIENT_ID: Optional[str] = Field(default=None)
    FITBIT_CLIENT_SECRET: Optional[str] = Field(default=None)
    
    # File Upload
    MAX_FILE_SIZE_MB: int = Field(default=10)
    ALLOWED_FILE_TYPES: str = Field(default="application/pdf,image/jpeg,image/png")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    
    # Medication Settings
    MEDICATION_REMINDER_ADVANCE_MINUTES: int = Field(default=15)
    MEDICATION_ADHERENCE_THRESHOLD: float = Field(default=80.0)
    
    # Appointment Settings
    APPOINTMENT_REMINDER_HOURS: int = Field(default=24)
    APPOINTMENT_CANCELLATION_HOURS: int = Field(default=24)
    
    # Email Configuration
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
    
    # Data Retention
    AUDIT_LOG_RETENTION_DAYS: int = Field(default=90)
    CHAT_HISTORY_RETENTION_DAYS: int = Field(default=180)
    
    # Notification Settings
    ENABLE_EMAIL_NOTIFICATIONS: bool = Field(default=False)
    ENABLE_SMS_NOTIFICATIONS: bool = Field(default=False)
    ENABLE_PUSH_NOTIFICATIONS: bool = Field(default=True)
    
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
    PRESCRIPTIONS_COLLECTION = "prescriptions"
    CHAT_MESSAGES_COLLECTION = "chat_messages"
    WEARABLE_CONNECTIONS_COLLECTION = "wearable_connections"
    NOTIFICATIONS_COLLECTION = "notifications"
    AUDIT_LOGS_COLLECTION = "audit_logs"


db_config = DatabaseConfig()


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
    
    # Allowed roles
    ROLES = ["admin", "doctor", "patient"]


security_config = SecurityConfig()


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


vitals_config = VitalsConfig()


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
    "security_config",
    "vitals_config",
    "validate_email",
    "validate_password",
    "validate_phone",
]