"""
Extended FastAPI Application - Digital Health Card System
Includes AI, medication tracking, appointments, wearables, and advanced features
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
import uuid
from io import BytesIO

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, status, File, UploadFile, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import EmailStr
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from passlib.context import CryptContext
from jose import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import cloudinary
import cloudinary.uploader
import qrcode
from bson import ObjectId
import pytesseract
from PIL import Image

# Import from your existing files
from config import settings
from models import *
from models import PatientUpdateRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
mongo_client: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None
security = HTTPBearer()

# ============================================================================
# LIFESPAN & APP INITIALIZATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo_client, db
    try:
        mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
        db = mongo_client[settings.DB_NAME]
        
        cloudinary.config(
            cloud_name=settings.CLOUD_NAME,
            api_key=settings.CLOUD_API_KEY,
            api_secret=settings.CLOUD_API_SECRET
        )
        
        # Create indexes
        await db.users.create_index("email", unique=True)
        await db.patients.create_index("qr_token", unique=True)
        await db.patients.create_index("user_id", unique=True)
        await db.doctors.create_index("user_id", unique=True)
        await db.medications.create_index([("patient_id", 1), ("is_active", 1)])
        await db.appointments.create_index([("patient_id", 1), ("scheduled_date", -1)])
        await db.vitals.create_index([("patient_id", 1), ("recorded_at", -1)])
        await db.lab_results.create_index([("patient_id", 1), ("test_date", -1)])
        await db.audit_logs.create_index("created_at", expireAfterSeconds=7776000)  # 90 days
        
        logger.info("Database connected and indexes created")
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise
    
    yield
    
    if mongo_client:
        mongo_client.close()
        logger.info("Database connection closed")

app = FastAPI(
    title="Digital Health Card System",
    version="2.0.0",
    description="Complete digital health card with AI, medication tracking, and integrations",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# UTILITIES
# ============================================================================
def hash_password(password: str) -> str:
    # truncate to 72 bytes (bcrypt limit)
    truncated_password = password[:72]
    return pwd_context.hash(truncated_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    truncated_password = plain_password[:72]
    return pwd_context.verify(truncated_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_role(*roles: str):
    async def role_checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker

def serialize_doc(doc: dict) -> dict:
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            doc[key] = value.isoformat()
        elif isinstance(value, date):
            doc[key] = value.isoformat()
    return doc

async def log_audit(user_id: ObjectId, action: str, resource_type: str, 
                   resource_id: Optional[ObjectId] = None, details: dict = {}):
    """Log action to audit trail"""
    await db.audit_logs.insert_one({
        "user_id": user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "created_at": datetime.utcnow()
    })

# ============================================================================ #
# WEBSOCKET MANAGER
# ============================================================================ #

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}  # user_id -> list of websockets

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)
        logger.info(f"WebSocket connected: {user_id}")

    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id] = [
                ws for ws in self.active_connections[user_id] if ws != websocket
            ]
            if not self.active_connections[user_id]:
                self.active_connections.pop(user_id)
        logger.info(f"WebSocket disconnected: {user_id}")

    async def send_personal_message(self, message: str, user_id: str):
        for websocket in self.active_connections.get(user_id, []):
            try:
                await websocket.send_json({"message": message})
            except Exception:
                logger.warning(f"Failed to send message to {user_id}")

    async def broadcast(self, message: str):
        for websockets in self.active_connections.values():
            for websocket in websockets:
                try:
                    await websocket.send_json({"message": message})
                except Exception:
                    pass

ws_manager = ConnectionManager()


# ============================================================================
# AUTH ROUTES (Using existing auth from your code)
# ============================================================================

@app.post("/auth/signup", response_model=StandardResponse, status_code=201)
async def signup(user_data: UserCreateRequest):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_doc = {
        "name": user_data.name,
        "email": user_data.email,
        "password_hash": hash_password(user_data.password),
        "role": user_data.role,
        "phone": user_data.phone,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_doc)
    user_id = result.inserted_id
    
    if user_data.role == "patient":
        qr_token = str(uuid.uuid4())
        qr_url = f"{settings.BASE_URL}/api/qr/resolve/{qr_token}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        upload_result = cloudinary.uploader.upload(buffer, folder="qr_codes")
        
        patient_doc = {
            "user_id": user_id,
            "qr_token": qr_token,
            "qr_image_url": upload_result["secure_url"],
            "prescriptions": [],
            "vaccinations": [],
            "allergies": [],
            "chronic_conditions": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        await db.patients.insert_one(patient_doc)
    
    access_token = create_access_token({"sub": str(user_id), "role": user_data.role})
    refresh_token = create_refresh_token({"sub": str(user_id)})
    
    user = await db.users.find_one({"_id": user_id})
    user_response = serialize_doc(user)
    user_response.pop("password_hash", None)
    
    await log_audit(user_id, "user_signup", "user", user_id)
    
    return {
        "status": "success",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user_response
        },
        "message": "User registered successfully"
    }

@app.post("/auth/login", response_model=StandardResponse)
async def login(credentials: UserLoginRequest):
    user = await db.users.find_one({"email": credentials.email})
    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id = user.get("_id")  # Save _id safely

    # Convert ObjectId to string for JWT payload (JSON serializable)
    user_id_str = str(user_id)

    access_token = create_access_token({"sub": user_id_str, "role": user["role"]})
    refresh_token = create_refresh_token({"sub": user_id_str})

    user_response = serialize_doc(user)
    user_response.pop("password_hash", None)  # Remove sensitive info

    await log_audit(user_id, "user_login", "user", user_id)

    return {
        "status": "success",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user_response
        },
        "message": "Login successful"
    }

@app.get("/patients/me", response_model=StandardResponse)
async def get_my_patient_info(current_user: dict = Depends(require_role("patient"))):
    """Get current patient's information including QR code"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")
    
    patient_data = serialize_doc(patient)
    
    # Get assigned doctor info if exists
    if patient.get("assigned_doctor_id"):
        doctor = await db.doctors.find_one({"_id": patient["assigned_doctor_id"]})
        if doctor:
            doctor_user = await db.users.find_one({"_id": doctor["user_id"]})
            patient_data["assigned_doctor"] = {
                "id": str(doctor["_id"]),
                "name": doctor_user["name"],
                "specialization": doctor.get("specialization")
            }
    
    return {
        "status": "success",
        "data": patient_data,
        "message": "Patient info retrieved successfully"
    }

@app.patch("/patients/me", response_model=StandardResponse)
async def update_my_patient_info(
    update_data: PatientUpdateRequest,
    current_user: dict = Depends(require_role("patient"))
):
    """Update current patient's information"""
    update_dict = update_data.model_dump(exclude_unset=True)
    
    if update_dict:
        update_dict["updated_at"] = datetime.utcnow()
        
        result = await db.patients.update_one(
            {"user_id": current_user["_id"]},
            {"$set": update_dict}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Patient record not found")
    
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    return {
        "status": "success",
        "data": serialize_doc(patient),
        "message": "Patient info updated successfully"
    }



@app.post("/patients/me/prescriptions", response_model=StandardResponse)
async def upload_prescription(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("patient"))
):
    """Upload a prescription file"""
    allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    contents = await file.read()
    if len(contents) > settings.max_file_size_bytes:
        raise HTTPException(status_code=400, detail=f"File too large. Max {settings.MAX_FILE_SIZE_MB}MB")
    
    file_data = BytesIO(contents)
    resource_type = "image" if "image" in file.content_type else "raw"
    upload_result = cloudinary.uploader.upload(file_data, folder="prescriptions", resource_type=resource_type)
    
    prescription_doc = {
        "url": upload_result["secure_url"],
        "public_id": upload_result["public_id"],
        "uploaded_at": datetime.utcnow(),
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(contents)
    }
    
    await db.patients.update_one(
        {"user_id": current_user["_id"]},
        {"$push": {"prescriptions": prescription_doc}, "$set": {"updated_at": datetime.utcnow()}}
    )
    
    # Notify assigned doctor
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    if patient.get("assigned_doctor_id"):
        notification_doc = {
            "user_id": patient["assigned_doctor_id"],
            "type": "prescription_uploaded",
            "title": "New Prescription Uploaded",
            "message": f"Patient {current_user['name']} uploaded a new prescription",
            "is_read": False,
            "created_at": datetime.utcnow()
        }
        await db.notifications.insert_one(notification_doc)
        
        # Send WebSocket notification
        await manager.send_personal_message(
            str(patient["assigned_doctor_id"]),
            {"type": "prescription_uploaded", "message": notification_doc["message"]}
        )
    
    logger.info(f"✅ Prescription uploaded by: {current_user['email']}")
    
    return {
        "status": "success",
        "data": prescription_doc,
        "message": "Prescription uploaded successfully"
    }


#  websockets wendpinys 

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        # Close immediately if no token
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = None
    # Decode token BEFORE accepting the connection
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception as e:
        logger.warning(f"Token decode failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Accept and register the WebSocket connection
    await ws_manager.connect(user_id, websocket)

    try:
        while True:
            try:
                data = await websocket.receive_json()
                message = data.get("message")
                if not message:
                    continue

                response_text = f"AI Response: You said '{message}'"

                # Validate ObjectId
                try:
                    obj_user_id = ObjectId(user_id)
                except Exception:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return

                # Save chat message
                patient = await db.patients.find_one({"user_id": obj_user_id})
                if not patient:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return

                chat_doc = {
                    "patient_id": patient["_id"],
                    "session_id": str(uuid.uuid4()),
                    "message": message,
                    "response": response_text,
                    "intent": "real_time_chat",
                    "created_at": datetime.utcnow()
                }
                await db.chat_messages.insert_one(chat_doc)

                await ws_manager.send_personal_message(response_text, user_id)

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                continue

    finally:
        # Properly disconnect only this websocket
        if user_id:
            ws_manager.disconnect(user_id, websocket)

@app.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket, token: str = Query(...)):
    """WebSocket endpoint for real-time notifications"""
    user_id = None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        await ws_manager.connect(user_id, websocket)
        
        try:
            while True:
                data = await websocket.receive_text()
                # Keep connection alive
        except WebSocketDisconnect:
            pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if user_id:
            ws_manager.disconnect(user_id, websocket)

# @app.websocket("/ws/chat")
# async def websocket_chat(websocket: WebSocket, token: str = Query(...)):
#     """WebSocket endpoint for real-time chat"""
#     user_id = None
#     try:
#         payload = decode_token(token)
#         user_id = payload.get("sub")
        
#         if not user_id:
#             await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
#             return
        
#         await manager.connect(user_id, websocket)
        
#         try:
#             while True:
#                 data = await websocket.receive_json()
#                 message = data.get("message")
                
#                 if message:
#                     response = f"AI Response: You said '{message}'"
#                     await manager.send_personal_message(user_id, {"response": response})
#         except WebSocketDisconnect:
#             pass
#     except Exception as e:
#         logger.error(f"WebSocket chat error: {e}")
#     finally:
#         if user_id:
#             manager.disconnect(user_id, websocket)

# ============================================================================
# MEDICATION TRACKING
# ============================================================================

@app.post("/medications", response_model=StandardResponse)
async def create_medication(
    med_data: MedicationCreateRequest,
    current_user: dict = Depends(require_role("patient"))
):
    """Add a new medication"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    medication_doc = {
        "patient_id": patient["_id"],
        "name": med_data.name,
        "dosage": med_data.dosage,
        "frequency": med_data.frequency,
        "custom_frequency": med_data.custom_frequency,
        "start_date": med_data.start_date,
        "end_date": med_data.end_date,
        "times": med_data.times,
        "instructions": med_data.instructions,
        "is_active": True,
        "reminders_enabled": med_data.reminders_enabled,
        "interaction_warnings": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.medications.insert_one(medication_doc)
    
    await log_audit(current_user["_id"], "medication_created", "medication", result.inserted_id)
    
    return {
        "status": "success",
        "data": {"id": str(result.inserted_id)},
        "message": "Medication added successfully"
    }

@app.get("/medications", response_model=StandardResponse)
async def list_medications(
    current_user: dict = Depends(require_role("patient")),
    active_only: bool = Query(True)
):
    """List all medications for current patient"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    query = {"patient_id": patient["_id"]}
    if active_only:
        query["is_active"] = True
    
    medications = await db.medications.find(query).to_list(length=100)
    
    return {
        "status": "success",
        "data": [serialize_doc(m) for m in medications],
        "message": "Medications retrieved successfully"
    }

@app.post("/medications/{med_id}/log", response_model=StandardResponse)
async def log_medication_intake(
    med_id: str,
    was_taken: bool,
    notes: Optional[str] = None,
    current_user: dict = Depends(require_role("patient"))
):
    """Log medication intake"""
    medication = await db.medications.find_one({"_id": ObjectId(med_id)})
    if not medication:
        raise HTTPException(status_code=404, detail="Medication not found")
    
    log_doc = {
        "medication_id": ObjectId(med_id),
        "patient_id": medication["patient_id"],
        "taken_at": datetime.utcnow(),
        "was_taken": was_taken,
        "notes": notes,
        "created_at": datetime.utcnow()
    }
    
    await db.medication_logs.insert_one(log_doc)
    
    return {
        "status": "success",
        "data": {"logged": True},
        "message": "Medication intake logged"
    }

@app.get("/medications/adherence", response_model=StandardResponse)
async def get_medication_adherence(
    current_user: dict = Depends(require_role("patient")),
    days: int = Query(30, ge=1, le=90)
):
    """Calculate medication adherence rate"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    logs = await db.medication_logs.find({
        "patient_id": patient["_id"],
        "created_at": {"$gte": start_date}
    }).to_list(length=1000)
    
    total = len(logs)
    taken = sum(1 for log in logs if log["was_taken"])
    adherence_rate = (taken / total * 100) if total > 0 else 0
    
    return {
        "status": "success",
        "data": {
            "adherence_rate": round(adherence_rate, 2),
            "total_doses": total,
            "taken_doses": taken,
            "missed_doses": total - taken,
            "period_days": days
        },
        "message": "Adherence calculated successfully"
    }

# ============================================================================
# APPOINTMENTS
# ============================================================================

@app.post("/appointments", response_model=StandardResponse)
async def create_appointment(
    appt_data: AppointmentCreateRequest,
    current_user: dict = Depends(require_role("patient"))
):
    """Book an appointment"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    doctor = await db.doctors.find_one({"_id": ObjectId(appt_data.doctor_id)})
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    appointment_doc = {
        "patient_id": patient["_id"],
        "doctor_id": doctor["_id"],
        "scheduled_date": appt_data.scheduled_date,
        "scheduled_time": appt_data.scheduled_time,
        "consultation_type": appt_data.consultation_type,
        "status": AppointmentStatus.SCHEDULED,
        "reason": appt_data.reason,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.appointments.insert_one(appointment_doc)
    
    await log_audit(current_user["_id"], "appointment_created", "appointment", result.inserted_id)
    
    return {
        "status": "success",
        "data": {"id": str(result.inserted_id)},
        "message": "Appointment booked successfully"
    }

@app.get("/appointments", response_model=StandardResponse)
async def list_appointments(
    current_user: dict = Depends(get_current_user),
    upcoming_only: bool = Query(True)
):
    """List appointments"""
    if current_user["role"] == "patient":
        patient = await db.patients.find_one({"user_id": current_user["_id"]})
        query = {"patient_id": patient["_id"]}
    elif current_user["role"] == "doctor":
        doctor = await db.doctors.find_one({"user_id": current_user["_id"]})
        query = {"doctor_id": doctor["_id"]}
    else:
        query = {}
    
    if upcoming_only:
        query["scheduled_date"] = {"$gte": date.today()}
        query["status"] = {"$in": ["scheduled", "rescheduled"]}
    
    appointments = await db.appointments.find(query).sort("scheduled_date", 1).to_list(length=100)
    
    result = []
    for appt in appointments:
        appt_data = serialize_doc(appt)
        
        # Add doctor/patient details
        if current_user["role"] == "patient":
            doctor = await db.doctors.find_one({"_id": appt["doctor_id"]})
            doctor_user = await db.users.find_one({"_id": doctor["user_id"]})
            appt_data["doctor_name"] = doctor_user["name"]
        else:
            patient = await db.patients.find_one({"_id": appt["patient_id"]})
            patient_user = await db.users.find_one({"_id": patient["user_id"]})
            appt_data["patient_name"] = patient_user["name"]
        
        result.append(appt_data)
    
    return {
        "status": "success",
        "data": result,
        "message": "Appointments retrieved successfully"
    }

@app.patch("/appointments/{appt_id}/status", response_model=StandardResponse)
async def update_appointment_status(
    appt_id: str,
    status: AppointmentStatus,
    current_user: dict = Depends(require_role("doctor", "patient"))
):
    """Update appointment status"""
    result = await db.appointments.update_one(
        {"_id": ObjectId(appt_id)},
        {"$set": {"status": status, "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    await log_audit(current_user["_id"], "appointment_updated", "appointment", ObjectId(appt_id))
    
    return {
        "status": "success",
        "data": {"updated": True},
        "message": "Appointment status updated"
    }

# ============================================================================
# VITALS TRACKING
# ============================================================================

@app.post("/vitals", response_model=StandardResponse)
async def add_vital_record(
    vital_data: VitalRecordRequest,
    current_user: dict = Depends(require_role("patient"))
):
    """Add a vital record"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    vital_doc = {
        "patient_id": patient["_id"],
        "vital_type": vital_data.vital_type,
        "value": vital_data.value,
        "unit": vital_data.unit,
        "recorded_at": vital_data.recorded_at or datetime.utcnow(),
        "source": "manual",
        "notes": vital_data.notes,
        "created_at": datetime.utcnow()
    }
    
    result = await db.vitals.insert_one(vital_doc)
    
    return {
        "status": "success",
        "data": {"id": str(result.inserted_id)},
        "message": "Vital record added successfully"
    }

@app.get("/vitals/{vital_type}/trend", response_model=StandardResponse)
async def get_vital_trend(
    vital_type: VitalType,
    current_user: dict = Depends(require_role("patient")),
    days: int = Query(30, ge=1, le=365)
):
    """Get trend for a specific vital"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    records = await db.vitals.find({
        "patient_id": patient["_id"],
        "vital_type": vital_type,
        "recorded_at": {"$gte": start_date}
    }).sort("recorded_at", 1).to_list(length=1000)
    
    if not records:
        return {
            "status": "success",
            "data": {"records": [], "average": 0, "trend": "no_data"},
            "message": "No records found"
        }
    
    values = [r["value"] for r in records]
    avg = sum(values) / len(values)
    
    # Simple trend calculation
    if len(values) >= 2:
        first_half_avg = sum(values[:len(values)//2]) / (len(values)//2)
        second_half_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
        
        if second_half_avg > first_half_avg * 1.1:
            trend = "increasing"
        elif second_half_avg < first_half_avg * 0.9:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"
    
    return {
        "status": "success",
        "data": {
            "vital_type": vital_type,
            "records": [serialize_doc(r) for r in records],
            "average": round(avg, 2),
            "min_value": min(values),
            "max_value": max(values),
            "trend": trend,
            "period_days": days
        },
        "message": "Vital trend retrieved successfully"
    }

# ============================================================================
# LAB RESULTS
# ============================================================================

@app.post("/lab-results", response_model=StandardResponse)
async def add_lab_result(
    test_date: date,
    lab_name: str,
    tests: List[Dict[str, Any]],
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(require_role("patient", "doctor"))
):
    """Add lab test results"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    report_url = None
    if file:
        contents = await file.read()
        buffer = BytesIO(contents)
        upload_result = cloudinary.uploader.upload(buffer, folder="lab_results", resource_type="auto")
        report_url = upload_result["secure_url"]
    
    lab_result_doc = {
        "patient_id": patient["_id"],
        "test_date": test_date,
        "lab_name": lab_name,
        "report_url": report_url,
        "tests": tests,
        "created_at": datetime.utcnow()
    }
    
    result = await db.lab_results.insert_one(lab_result_doc)
    
    return {
        "status": "success",
        "data": {"id": str(result.inserted_id)},
        "message": "Lab result added successfully"
    }

@app.get("/lab-results", response_model=StandardResponse)
async def list_lab_results(
    current_user: dict = Depends(require_role("patient")),
    limit: int = Query(10, ge=1, le=50)
):
    """List lab results"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    results = await db.lab_results.find(
        {"patient_id": patient["_id"]}
    ).sort("test_date", -1).limit(limit).to_list(length=limit)
    
    return {
        "status": "success",
        "data": [serialize_doc(r) for r in results],
        "message": "Lab results retrieved successfully"
    }

# ============================================================================
# AI HEALTH ASSISTANT / CHATBOT
# ============================================================================

@app.post("/ai/chat", response_model=StandardResponse)
async def ai_health_chat(
    chat_data: ChatRequest,
    current_user: dict = Depends(require_role("patient"))
):
    """AI health assistant chatbot endpoint"""
    session_id = chat_data.session_id or str(uuid.uuid4())
    
    # Simple mock AI response - integrate with OpenAI/Claude API in production
    response_text = f"Thank you for your question about: {chat_data.message}. "
    
    # Basic intent detection
    message_lower = chat_data.message.lower()
    intent = None
    suggestions = []
    
    if any(word in message_lower for word in ["medication", "medicine", "drug"]):
        intent = "medication_inquiry"
        response_text += "I can help you with medication information. Please consult your doctor for specific advice."
        suggestions = ["View my medications", "Check drug interactions", "Set medication reminder"]
    
    elif any(word in message_lower for word in ["symptom", "pain", "fever", "headache"]):
        intent = "symptom_check"
        response_text += "I'm not a doctor, but I recommend tracking your symptoms and consulting a healthcare professional if they persist."
        suggestions = ["Book an appointment", "View nearby hospitals", "Emergency contacts"]
    
    elif any(word in message_lower for word in ["appointment", "book", "schedule"]):
        intent = "appointment_booking"
        response_text += "I can help you book an appointment with your doctor."
        suggestions = ["View available slots", "My appointments", "Find a doctor"]
    
    else:
        intent = "general_inquiry"
        response_text += "How else can I assist you with your health today?"
        suggestions = ["View my health records", "Track vitals", "Medication reminders"]
    
    # Store chat message
    chat_doc = {
        "patient_id": (await db.patients.find_one({"user_id": current_user["_id"]}))["_id"],
        "session_id": session_id,
        "message": chat_data.message,
        "response": response_text,
        "intent": intent,
        "created_at": datetime.utcnow()
    }
    
    await db.chat_messages.insert_one(chat_doc)
    
    return {
        "status": "success",
        "data": {
            "session_id": session_id,
            "message": chat_data.message,
            "response": response_text,
            "intent": intent,
            "suggestions": suggestions
        },
        "message": "Chat response generated"
    }

# ============================================================================
# OCR PRESCRIPTION EXTRACTION
# ============================================================================

@app.post("/prescriptions/extract", response_model=StandardResponse)
async def extract_prescription_text(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("patient", "doctor"))
):
    """Extract text from prescription image using OCR"""
    if file.content_type not in ["image/jpeg", "image/png", "image/jpg"]:
        raise HTTPException(status_code=400, detail="Only image files supported")
    
    contents = await file.read()
    image = Image.open(BytesIO(contents))
    
    # Perform OCR - requires tesseract installed
    try:
        extracted_text = pytesseract.image_to_string(image)
        
        # Basic parsing (enhance with NLP in production)
        lines = [line.strip() for line in extracted_text.split('\n') if line.strip()]
        
        medications = []
        for line in lines:
            if any(keyword in line.lower() for keyword in ['tab', 'cap', 'syrup', 'mg', 'ml']):
                medications.append(line)
        
        return {
            "status": "success",
            "data": {
                "raw_text": extracted_text,
                "medications": medications,
                "confidence": "medium"
            },
            "message": "Prescription text extracted"
        }
    
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return {
            "status": "error",
            "data": {"error": str(e)},
            "message": "OCR extraction failed"
        }

# ============================================================================
# HEALTH ANALYTICS
# ============================================================================

@app.get("/analytics/health-score", response_model=StandardResponse)
async def get_health_analytics(
    current_user: dict = Depends(require_role("patient"))
):
    """Get comprehensive health analytics"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    # Get recent vitals
    recent_vitals = await db.vitals.find(
        {"patient_id": patient["_id"]}
    ).sort("recorded_at", -1).limit(50).to_list(length=50)
    
    # Get medication adherence
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    med_logs = await db.medication_logs.find({
        "patient_id": patient["_id"],
        "created_at": {"$gte": thirty_days_ago}
    }).to_list(length=1000)
    
    adherence = (sum(1 for log in med_logs if log["was_taken"]) / len(med_logs) * 100) if med_logs else 0
    
    # Get upcoming appointments
    upcoming_appts = await db.appointments.count_documents({
        "patient_id": patient["_id"],
        "scheduled_date": {"$gte": date.today()},
        "status": "scheduled"
    })
    
    # Calculate simple health score (0-100)
    health_score = 70  # Base score
    
    if adherence > 80:
        health_score += 15
    elif adherence > 60:
        health_score += 10
    
    if len(recent_vitals) > 10:
        health_score += 10
    
    if upcoming_appts > 0:
        health_score += 5
    
    # Generate recommendations
    recommendations = []
    if adherence < 80:
        recommendations.append("Improve medication adherence - currently at {:.1f}%".format(adherence))
    if len(recent_vitals) < 5:
        recommendations.append("Track your vitals more regularly")
    if upcoming_appts == 0:
        recommendations.append("Schedule a regular checkup with your doctor")
    
    vitals_summary = {}
    for vital in recent_vitals:
        vtype = vital["vital_type"]
        if vtype not in vitals_summary:
            vitals_summary[vtype] = {"count": 0, "latest": None}
        vitals_summary[vtype]["count"] += 1
        if vitals_summary[vtype]["latest"] is None:
            vitals_summary[vtype]["latest"] = {
                "value": vital["value"],
                "unit": vital["unit"],
                "date": vital["recorded_at"]
            }
    
    return {
        "status": "success",
        "data": {
            "health_score": min(health_score, 100),
            "medication_adherence": round(adherence, 1),
            "upcoming_appointments": upcoming_appts,
            "vitals_summary": vitals_summary,
            "recommendations": recommendations
        },
        "message": "Health analytics retrieved"
    }

# ============================================================================
# WEARABLE DEVICE INTEGRATION
# ============================================================================

@app.post("/wearables/connect", response_model=StandardResponse)
async def connect_wearable(
    device_type: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    current_user: dict = Depends(require_role("patient"))
):
    """Connect a wearable device"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    connection_doc = {
        "patient_id": patient["_id"],
        "device_type": device_type,
        "device_id": str(uuid.uuid4()),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    
    result = await db.wearable_connections.insert_one(connection_doc)
    
    return {
        "status": "success",
        "data": {"id": str(result.inserted_id)},
        "message": f"{device_type} connected successfully"
    }

@app.post("/wearables/sync", response_model=StandardResponse)
async def sync_wearable_data(
    device_id: str,
    data: List[Dict[str, Any]],
    current_user: dict = Depends(require_role("patient"))
):
    """Sync data from wearable device"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    # Store vitals from wearable
    vitals_to_insert = []
    for item in data:
        vital_doc = {
            "patient_id": patient["_id"],
            "vital_type": item.get("type"),
            "value": item.get("value"),
            "unit": item.get("unit"),
            "recorded_at": item.get("timestamp", datetime.utcnow()),
            "source": "wearable",
            "device_id": device_id,
            "created_at": datetime.utcnow()
        }
        vitals_to_insert.append(vital_doc)
    
    if vitals_to_insert:
        await db.vitals.insert_many(vitals_to_insert)
    
    # Update last sync time
    await db.wearable_connections.update_one(
        {"device_id": device_id},
        {"$set": {"last_sync": datetime.utcnow()}}
    )
    
    return {
        "status": "success",
        "data": {"synced_records": len(vitals_to_insert)},
        "message": "Wearable data synced successfully"
    }

# ============================================================================
# INSURANCE & POLICY
# ============================================================================

@app.post("/insurance/policies", response_model=StandardResponse)
async def add_insurance_policy(
    policy_data: InsurancePolicyRequest,
    current_user: dict = Depends(require_role("patient"))
):
    """Add insurance policy"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    policy_doc = {
        "patient_id": patient["_id"],
        "provider_name": policy_data.provider_name,
        "policy_number": policy_data.policy_number,
        "coverage_type": policy_data.coverage_type,
        "coverage_amount": policy_data.coverage_amount,
        "start_date": policy_data.start_date,
        "end_date": policy_data.end_date,
        "is_active": True,
        "documents": [],
        "created_at": datetime.utcnow()
    }
    
    result = await db.insurance_policies.insert_one(policy_doc)
    
    return {
        "status": "success",
        "data": {"id": str(result.inserted_id)},
        "message": "Insurance policy added"
    }

@app.get("/insurance/policies", response_model=StandardResponse)
async def list_insurance_policies(
    current_user: dict = Depends(require_role("patient"))
):
    """List insurance policies"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    policies = await db.insurance_policies.find(
        {"patient_id": patient["_id"]}
    ).to_list(length=100)
    
    return {
        "status": "success",
        "data": [serialize_doc(p) for p in policies],
        "message": "Insurance policies retrieved"
    }

# ============================================================================
# CONSENT MANAGEMENT
# ============================================================================

@app.post("/consent", response_model=StandardResponse)
async def manage_consent(
    consent_data: ConsentRequest,
    current_user: dict = Depends(require_role("patient"))
):
    """Grant or revoke consent"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    consent_doc = {
        "patient_id": patient["_id"],
        "consent_type": consent_data.consent_type,
        "granted": consent_data.granted,
        "granted_to": ObjectId(consent_data.granted_to) if consent_data.granted_to else None,
        "granted_at": datetime.utcnow(),
        "expires_at": consent_data.expires_at,
        "revoked": False
    }
    
    result = await db.consents.insert_one(consent_doc)
    
    return {
        "status": "success",
        "data": {"id": str(result.inserted_id)},
        "message": "Consent recorded successfully"
    }

@app.get("/consent", response_model=StandardResponse)
async def list_consents(
    current_user: dict = Depends(require_role("patient"))
):
    """List all consents"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    consents = await db.consents.find(
        {"patient_id": patient["_id"]}
    ).to_list(length=100)
    
    return {
        "status": "success",
        "data": [serialize_doc(c) for c in consents],
        "message": "Consents retrieved"
    }

# ============================================================================
# FAMILY ACCOUNTS
# ============================================================================

@app.post("/family/members", response_model=StandardResponse)
async def add_family_member(
    name: str,
    relationship: str,
    date_of_birth: Optional[date] = None,
    member_email: Optional[EmailStr] = None,
    current_user: dict = Depends(require_role("patient"))
):
    """Add family member to account"""
    member_user_id = None
    
    if member_email:
        member_user = await db.users.find_one({"email": member_email})
        if member_user:
            member_user_id = member_user["_id"]
    
    family_member_doc = {
        "primary_user_id": current_user["_id"],
        "member_user_id": member_user_id,
        "name": name,
        "relationship": relationship,
        "date_of_birth": date_of_birth,
        "can_view_records": True,
        "can_edit_records": False,
        "created_at": datetime.utcnow()
    }
    
    result = await db.family_members.insert_one(family_member_doc)
    
    return {
        "status": "success",
        "data": {"id": str(result.inserted_id)},
        "message": "Family member added"
    }

@app.get("/family/members", response_model=StandardResponse)
async def list_family_members(
    current_user: dict = Depends(require_role("patient"))
):
    """List family members"""
    members = await db.family_members.find(
        {"primary_user_id": current_user["_id"]}
    ).to_list(length=100)
    
    return {
        "status": "success",
        "data": [serialize_doc(m) for m in members],
        "message": "Family members retrieved"
    }

# ============================================================================
# EMERGENCY QR CODE ACCESS
# ============================================================================

@app.get("/emergency/{qr_token}", response_model=StandardResponse)
async def emergency_access(qr_token: str):
    """Public endpoint for emergency QR code access - no auth required"""
    patient = await db.patients.find_one({"qr_token": qr_token})
    
    if not patient:
        raise HTTPException(status_code=404, detail="Invalid QR code")
    
    user = await db.users.find_one({"_id": patient["user_id"]})
    
    # Return only critical emergency information
    emergency_data = {
        "name": user["name"],
        "blood_group": patient.get("blood_group"),
        "allergies": patient.get("allergies", []),
        "chronic_conditions": patient.get("chronic_conditions", []),
        "emergency_contact_name": patient.get("emergency_contact_name"),
        "emergency_contact_phone": patient.get("emergency_contact_phone"),
        "date_of_birth": patient.get("date_of_birth")
    }
    
    # Log emergency access
    await db.audit_logs.insert_one({
        "user_id": patient["user_id"],
        "action": "emergency_access",
        "resource_type": "patient",
        "resource_id": patient["_id"],
        "details": {"qr_token": qr_token},
        "created_at": datetime.utcnow()
    })
    
    return {
        "status": "success",
        "data": emergency_data,
        "message": "Emergency information accessed"
    }

# ============================================================================
# HOSPITAL/CLINIC SEARCH (Maps Integration)
# ============================================================================

@app.get("/hospitals/nearby", response_model=StandardResponse)
async def search_nearby_hospitals(
    latitude: float,
    longitude: float,
    radius_km: int = Query(5, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """Search nearby hospitals using coordinates"""
    # Mock response - integrate with Google Places API in production
    # Example: Use requests library to call Google Places API
    
    mock_hospitals = [
        {
            "id": "hosp1",
            "name": "City General Hospital",
            "address": "123 Main St",
            "distance_km": 2.3,
            "rating": 4.5,
            "phone": "+1234567890",
            "emergency_services": True
        },
        {
            "id": "hosp2",
            "name": "Community Health Center",
            "address": "456 Oak Ave",
            "distance_km": 3.7,
            "rating": 4.2,
            "phone": "+1234567891",
            "emergency_services": False
        }
    ]
    
    return {
        "status": "success",
        "data": {
            "hospitals": mock_hospitals,
            "search_location": {"lat": latitude, "lon": longitude},
            "radius_km": radius_km
        },
        "message": "Nearby hospitals found"
    }

# ============================================================================
# AUDIT LOGS (Admin)
# ============================================================================

@app.get("/audit/logs", response_model=StandardResponse)
async def get_audit_logs(
    current_user: dict = Depends(require_role("admin")),
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100)
):
    """Get audit logs"""
    query = {}
    
    if user_id:
        query["user_id"] = ObjectId(user_id)
    if action:
        query["action"] = action
    
    logs = await db.audit_logs.find(query).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    return {
        "status": "success",
        "data": [serialize_doc(log) for log in logs],
        "message": "Audit logs retrieved"
    }

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)












# """
# Complete Digital Health Card Backend - FastAPI Application
# All features including auth, patients, doctors, medications, appointments, etc.
# """

# import logging
# from contextlib import asynccontextmanager
# from datetime import datetime, timedelta, date
# from typing import Optional, List, Dict, Any
# import uuid
# from io import BytesIO

# from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, status, File, UploadFile, Query
# from fastapi.middleware.cors import CORSMiddleware
# from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
# from passlib.context import CryptContext
# from jose import jwt, JWTError
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# import cloudinary
# import cloudinary.uploader
# import qrcode
# from bson import ObjectId

# # Local imports
# from config import settings
# from models import *

# # Logging setup
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# # Security
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# security = HTTPBearer()

# # Database
# mongo_client: Optional[AsyncIOMotorClient] = None
# db: Optional[AsyncIOMotorDatabase] = None

# # ============================================================================
# # WEBSOCKET MANAGER
# # ============================================================================

# class ConnectionManager:
#     def __init__(self):
#         self.active_connections: Dict[str, List[WebSocket]] = {}
    
#     async def connect(self, user_id: str, websocket: WebSocket):
#         await websocket.accept()
#         if user_id not in self.active_connections:
#             self.active_connections[user_id] = []
#         self.active_connections[user_id].append(websocket)
#         logger.info(f"WebSocket connected: {user_id}")
    
#     def disconnect(self, user_id: str, websocket: WebSocket):
#         if user_id in self.active_connections:
#             self.active_connections[user_id] = [ws for ws in self.active_connections[user_id] if ws != websocket]
#             if not self.active_connections[user_id]:
#                 del self.active_connections[user_id]
#         logger.info(f"WebSocket disconnected: {user_id}")
    
#     async def send_personal_message(self, user_id: str, message: dict):
#         if user_id in self.active_connections:
#             for websocket in self.active_connections[user_id]:
#                 try:
#                     await websocket.send_json(message)
#                 except Exception as e:
#                     logger.error(f"Error sending message to {user_id}: {e}")

# manager = ConnectionManager()

# # ============================================================================
# # LIFESPAN & APP INITIALIZATION
# # ============================================================================

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     global mongo_client, db
#     try:
#         mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
#         db = mongo_client[settings.DB_NAME]
        
#         cloudinary.config(
#             cloud_name=settings.CLOUD_NAME,
#             api_key=settings.CLOUD_API_KEY,
#             api_secret=settings.CLOUD_API_SECRET
#         )
        
#         # Create indexes
#         await db.users.create_index("email", unique=True)
#         await db.patients.create_index("qr_token", unique=True)
#         await db.patients.create_index("user_id", unique=True)
#         await db.doctors.create_index("user_id", unique=True)
        
#         logger.info("✅ Database connected and indexes created")
#     except Exception as e:
#         logger.error(f"❌ Startup error: {e}")
#         raise
    
#     yield
    
#     if mongo_client:
#         mongo_client.close()
#         logger.info("Database connection closed")

# app = FastAPI(
#     title="Digital Health Card System",
#     version="2.0.0",
#     description="Complete digital health card with AI, medication tracking, and integrations",
#     lifespan=lifespan
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.cors_origins_list,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ============================================================================
# # UTILITY FUNCTIONS
# # ============================================================================

# def hash_password(password: str) -> str:
#     return pwd_context.hash(password[:72])

# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     return pwd_context.verify(plain_password[:72], hashed_password)

# def create_access_token(data: dict) -> str:
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)

# def create_refresh_token(data: dict) -> str:
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)

# def decode_token(token: str) -> dict:
#     try:
#         return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
#     except jwt.ExpiredSignatureError:
#         raise HTTPException(status_code=401, detail="Token expired")
#     except JWTError:
#         raise HTTPException(status_code=401, detail="Invalid token")

# async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
#     payload = decode_token(credentials.credentials)
#     user_id = payload.get("sub")
#     if not user_id:
#         raise HTTPException(status_code=401, detail="Invalid token")
    
#     user = await db.users.find_one({"_id": ObjectId(user_id)})
#     if not user:
#         raise HTTPException(status_code=401, detail="User not found")
#     return user

# def require_role(*roles: str):
#     async def role_checker(user: dict = Depends(get_current_user)) -> dict:
#         if user["role"] not in roles:
#             raise HTTPException(status_code=403, detail="Insufficient permissions")
#         return user
#     return role_checker

# def serialize_doc(doc: dict) -> dict:
#     if doc is None:
#         return None
#     doc["id"] = str(doc.pop("_id"))
#     for key, value in doc.items():
#         if isinstance(value, ObjectId):
#             doc[key] = str(value)
#         elif isinstance(value, datetime):
#             doc[key] = value.isoformat()
#         elif isinstance(value, date):
#             doc[key] = value.isoformat()
#     return doc

# # ============================================================================
# # AUTHENTICATION ENDPOINTS
# # ============================================================================

# @app.post("/auth/signup", response_model=StandardResponse, status_code=201)
# async def signup(user_data: UserCreateRequest):
#     """Register a new user"""
#     existing = await db.users.find_one({"email": user_data.email})
#     if existing:
#         raise HTTPException(status_code=400, detail="Email already registered")
    
#     user_doc = {
#         "name": user_data.name,
#         "email": user_data.email,
#         "password_hash": hash_password(user_data.password),
#         "role": user_data.role,
#         "phone": user_data.phone,
#         "profile_image_url": None,
#         "is_active": True,
#         "is_verified": False,
#         "created_at": datetime.utcnow(),
#         "updated_at": datetime.utcnow(),
#         "last_login": None
#     }
    
#     result = await db.users.insert_one(user_doc)
#     user_id = result.inserted_id
    
#     # Create role-specific records
#     if user_data.role == "patient":
#         qr_token = str(uuid.uuid4())
#         qr_url = f"{settings.BASE_URL}/emergency/{qr_token}"
        
#         # Generate QR code
#         qr = qrcode.QRCode(version=1, box_size=10, border=5)
#         qr.add_data(qr_url)
#         qr.make(fit=True)
#         img = qr.make_image(fill_color="black", back_color="white")
        
#         buffer = BytesIO()
#         img.save(buffer, format='PNG')
#         buffer.seek(0)
        
#         upload_result = cloudinary.uploader.upload(buffer, folder="qr_codes")
        
#         patient_doc = {
#             "user_id": user_id,
#             "qr_token": qr_token,
#             "qr_image_url": upload_result["secure_url"],
#             "prescriptions": [],
#             "medications": [],
#             "vitals": [],
#             "vaccinations": [],
#             "allergies": [],
#             "chronic_conditions": [],
#             "assigned_doctor_id": None,
#             "medical_summary": None,
#             "blood_group": None,
#             "emergency_contact_name": None,
#             "emergency_contact_phone": None,
#             "date_of_birth": None,
#             "gender": None,
#             "address": None,
#             "created_at": datetime.utcnow(),
#             "updated_at": datetime.utcnow()
#         }
#         await db.patients.insert_one(patient_doc)
    
#     elif user_data.role == "doctor":
#         doctor_doc = {
#             "user_id": user_id,
#             "specialization": "General",
#             "license_number": None,
#             "clinic_info": None,
#             "patients": [],
#             "education": [],
#             "available_days": [],
#             "consultation_hours": None,
#             "created_at": datetime.utcnow(),
#             "updated_at": datetime.utcnow()
#         }
#         await db.doctors.insert_one(doctor_doc)
    
#     # Generate tokens
#     access_token = create_access_token({"sub": str(user_id), "role": user_data.role})
#     refresh_token = create_refresh_token({"sub": str(user_id)})
    
#     user = await db.users.find_one({"_id": user_id})
#     user_response = serialize_doc(user)
#     user_response.pop("password_hash", None)
    
#     logger.info(f"✅ User registered: {user_data.email}")
    
#     return {
#         "status": "success",
#         "data": {
#             "access_token": access_token,
#             "refresh_token": refresh_token,
#             "token_type": "bearer",
#             "user": user_response
#         },
#         "message": "User registered successfully"
#     }

# @app.post("/auth/login", response_model=StandardResponse)
# async def login(credentials: UserLoginRequest):
#     """User login"""
#     user = await db.users.find_one({"email": credentials.email})
#     if not user or not verify_password(credentials.password, user["password_hash"]):
#         raise HTTPException(status_code=401, detail="Invalid credentials")
    
#     # Update last login
#     await db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login": datetime.utcnow()}})
    
#     access_token = create_access_token({"sub": str(user["_id"]), "role": user["role"]})
#     refresh_token = create_refresh_token({"sub": str(user["_id"])})
    
#     user_response = serialize_doc(user)
#     user_response.pop("password_hash", None)
    
#     logger.info(f"✅ User logged in: {credentials.email}")
    
#     return {
#         "status": "success",
#         "data": {
#             "access_token": access_token,
#             "refresh_token": refresh_token,
#             "token_type": "bearer",
#             "user": user_response
#         },
#         "message": "Login successful"
#     }

# @app.get("/auth/me", response_model=StandardResponse)
# async def get_me(current_user: dict = Depends(get_current_user)):
#     """Get current user info"""
#     user_response = serialize_doc(current_user)
#     user_response.pop("password_hash", None)
    
#     return {
#         "status": "success",
#         "data": user_response,
#         "message": "User retrieved successfully"
#     }

# # ============================================================================
# # PATIENT ENDPOINTS
# # ============================================================================

# @app.get("/patients/me", response_model=StandardResponse)
# async def get_my_patient_info(current_user: dict = Depends(require_role("patient"))):
#     """Get current patient's information including QR code"""
#     patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
#     if not patient:
#         raise HTTPException(status_code=404, detail="Patient record not found")
    
#     patient_data = serialize_doc(patient)
    
#     # Get assigned doctor info if exists
#     if patient.get("assigned_doctor_id"):
#         doctor = await db.doctors.find_one({"_id": patient["assigned_doctor_id"]})
#         if doctor:
#             doctor_user = await db.users.find_one({"_id": doctor["user_id"]})
#             patient_data["assigned_doctor"] = {
#                 "id": str(doctor["_id"]),
#                 "name": doctor_user["name"],
#                 "specialization": doctor.get("specialization")
#             }
    
#     return {
#         "status": "success",
#         "data": patient_data,
#         "message": "Patient info retrieved successfully"
#     }

# @app.patch("/patients/me", response_model=StandardResponse)
# async def update_my_patient_info(
#     update_data: PatientUpdateRequest,
#     current_user: dict = Depends(require_role("patient"))
# ):
#     """Update current patient's information"""
#     update_dict = update_data.model_dump(exclude_unset=True)
    
#     if update_dict:
#         update_dict["updated_at"] = datetime.utcnow()
        
#         result = await db.patients.update_one(
#             {"user_id": current_user["_id"]},
#             {"$set": update_dict}
#         )
        
#         if result.matched_count == 0:
#             raise HTTPException(status_code=404, detail="Patient record not found")
    
#     patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
#     return {
#         "status": "success",
#         "data": serialize_doc(patient),
#         "message": "Patient info updated successfully"
#     }

# @app.post("/patients/me/prescriptions", response_model=StandardResponse)
# async def upload_prescription(
#     file: UploadFile = File(...),
#     current_user: dict = Depends(require_role("patient"))
# ):
#     """Upload a prescription file"""
#     allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/jpg"]
#     if file.content_type not in allowed_types:
#         raise HTTPException(status_code=400, detail="Invalid file type")
    
#     contents = await file.read()
#     if len(contents) > settings.max_file_size_bytes:
#         raise HTTPException(status_code=400, detail=f"File too large. Max {settings.MAX_FILE_SIZE_MB}MB")
    
#     file_data = BytesIO(contents)
#     resource_type = "image" if "image" in file.content_type else "raw"
#     upload_result = cloudinary.uploader.upload(file_data, folder="prescriptions", resource_type=resource_type)
    
#     prescription_doc = {
#         "url": upload_result["secure_url"],
#         "public_id": upload_result["public_id"],
#         "uploaded_at": datetime.utcnow(),
#         "filename": file.filename,
#         "content_type": file.content_type,
#         "size_bytes": len(contents)
#     }
    
#     await db.patients.update_one(
#         {"user_id": current_user["_id"]},
#         {"$push": {"prescriptions": prescription_doc}, "$set": {"updated_at": datetime.utcnow()}}
#     )
    
#     # Notify assigned doctor
#     patient = await db.patients.find_one({"user_id": current_user["_id"]})
#     if patient.get("assigned_doctor_id"):
#         notification_doc = {
#             "user_id": patient["assigned_doctor_id"],
#             "type": "prescription_uploaded",
#             "title": "New Prescription Uploaded",
#             "message": f"Patient {current_user['name']} uploaded a new prescription",
#             "is_read": False,
#             "created_at": datetime.utcnow()
#         }
#         await db.notifications.insert_one(notification_doc)
        
#         # Send WebSocket notification
#         await manager.send_personal_message(
#             str(patient["assigned_doctor_id"]),
#             {"type": "prescription_uploaded", "message": notification_doc["message"]}
#         )
    
#     logger.info(f"✅ Prescription uploaded by: {current_user['email']}")
    
#     return {
#         "status": "success",
#         "data": prescription_doc,
#         "message": "Prescription uploaded successfully"
#     }

# # ============================================================================
# # DOCTOR ENDPOINTS
# # ============================================================================

# @app.get("/doctors/me", response_model=StandardResponse)
# async def get_my_doctor_info(current_user: dict = Depends(require_role("doctor"))):
#     """Get current doctor's information"""
#     doctor = await db.doctors.find_one({"user_id": current_user["_id"]})
    
#     if not doctor:
#         raise HTTPException(status_code=404, detail="Doctor record not found")
    
#     return {
#         "status": "success",
#         "data": serialize_doc(doctor),
#         "message": "Doctor info retrieved successfully"
#     }

# @app.get("/doctors/me/patients", response_model=StandardResponse)
# async def get_my_patients(current_user: dict = Depends(require_role("doctor"))):
#     """Get list of patients assigned to current doctor"""
#     doctor = await db.doctors.find_one({"user_id": current_user["_id"]})
    
#     if not doctor:
#         raise HTTPException(status_code=404, detail="Doctor record not found")
    
#     patients = await db.patients.find({"assigned_doctor_id": doctor["_id"]}).to_list(length=100)
    
#     patient_list = []
#     for patient in patients:
#         user = await db.users.find_one({"_id": patient["user_id"]})
#         patient_data = serialize_doc(patient)
#         patient_data["user"] = {
#             "name": user["name"],
#             "email": user["email"],
#             "phone": user.get("phone")
#         }
#         patient_list.append(patient_data)
    
#     return {
#         "status": "success",
#         "data": patient_list,
#         "message": "Patients retrieved successfully"
#     }

# # ============================================================================
# # QR CODE ENDPOINTS
# # ============================================================================

# @app.get("/qr/resolve/{token}", response_model=StandardResponse)
# async def resolve_qr_token(
#     token: str,
#     current_user: dict = Depends(require_role("doctor", "admin"))
# ):
#     """Resolve QR token to patient information"""
#     patient = await db.patients.find_one({"qr_token": token})
    
#     if not patient:
#         raise HTTPException(status_code=404, detail="Invalid QR token")
    
#     user = await db.users.find_one({"_id": patient["user_id"]})
    
#     patient_data = serialize_doc(patient)
#     patient_data["user"] = serialize_doc(user)
#     patient_data["user"].pop("password_hash", None)
    
#     return {
#         "status": "success",
#         "data": patient_data,
#         "message": "Patient info retrieved via QR"
#     }

# @app.get("/emergency/{qr_token}", response_model=StandardResponse)
# async def emergency_access(qr_token: str):
#     """Public endpoint for emergency QR code access - no auth required"""
#     patient = await db.patients.find_one({"qr_token": qr_token})
    
#     if not patient:
#         raise HTTPException(status_code=404, detail="Invalid QR code")
    
#     user = await db.users.find_one({"_id": patient["user_id"]})
    
#     emergency_data = {
#         "name": user["name"],
#         "blood_group": patient.get("blood_group"),
#         "allergies": patient.get("allergies", []),
#         "chronic_conditions": patient.get("chronic_conditions", []),
#         "emergency_contact_name": patient.get("emergency_contact_name"),
#         "emergency_contact_phone": patient.get("emergency_contact_phone"),
#         "date_of_birth": patient.get("date_of_birth")
#     }
    
#     return {
#         "status": "success",
#         "data": emergency_data,
#         "message": "Emergency information accessed"
#     }

# # ============================================================================
# # MEDICATION ENDPOINTS
# # ============================================================================

# @app.post("/medications", response_model=StandardResponse)
# async def create_medication(
#     med_data: MedicationCreateRequest,
#     current_user: dict = Depends(require_role("patient"))
# ):
#     """Add a new medication"""
#     patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
#     medication_doc = {
#         "patient_id": patient["_id"],
#         "name": med_data.name,
#         "dosage": med_data.dosage,
#         "frequency": med_data.frequency,
#         "custom_frequency": med_data.custom_frequency,
#         "start_date": med_data.start_date,
#         "end_date": med_data.end_date,
#         "times": med_data.times,
#         "instructions": med_data.instructions,
#         "is_active": True,
#         "reminders_enabled": med_data.reminders_enabled,
#         "created_at": datetime.utcnow(),
#         "updated_at": datetime.utcnow()
#     }
    
#     result = await db.medications.insert_one(medication_doc)
    
#     logger.info(f"✅ Medication created: {med_data.name}")
    
#     return {
#         "status": "success",
#         "data": {"id": str(result.inserted_id)},
#         "message": "Medication added successfully"
#     }

# @app.get("/medications", response_model=StandardResponse)
# async def list_medications(
#     current_user: dict = Depends(require_role("patient")),
#     active_only: bool = Query(True)
# ):
#     """List all medications for current patient"""
#     patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
#     query = {"patient_id": patient["_id"]}
#     if active_only:
#         query["is_active"] = True
    
#     medications = await db.medications.find(query).to_list(length=100)
    
#     return {
#         "status": "success",
#         "data": [serialize_doc(m) for m in medications],
#         "message": "Medications retrieved successfully"
#     }

# @app.patch("/medications/{med_id}", response_model=StandardResponse)
# async def update_medication(
#     med_id: str,
#     is_active: Optional[bool] = None,
#     current_user: dict = Depends(require_role("patient"))
# ):
#     """Update medication"""
#     update_dict = {}
#     if is_active is not None:
#         update_dict["is_active"] = is_active
#     update_dict["updated_at"] = datetime.utcnow()
    
#     result = await db.medications.update_one(
#         {"_id": ObjectId(med_id)},
#         {"$set": update_dict}
#     )
    
#     if result.matched_count == 0:
#         raise HTTPException(status_code=404, detail="Medication not found")
    
#     return {
#         "status": "success",
#         "data": {"updated": True},
#         "message": "Medication updated successfully"
#     }

# # ============================================================================
# # APPOINTMENTS
# # ============================================================================

# @app.post("/appointments", response_model=StandardResponse)
# async def create_appointment(
#     appt_data: AppointmentCreateRequest,
#     current_user: dict = Depends(require_role("patient"))
# ):
#     """Book an appointment"""
#     patient = await db.patients.find_one({"user_id": current_user["_id"]})
#     doctor = await db.doctors.find_one({"_id": ObjectId(appt_data.doctor_id)})
    
#     if not doctor:
#         raise HTTPException(status_code=404, detail="Doctor not found")
    
#     appointment_doc = {
#         "patient_id": patient["_id"],
#         "doctor_id": doctor["_id"],
#         "scheduled_date": appt_data.scheduled_date,
#         "scheduled_time": appt_data.scheduled_time,
#         "consultation_type": appt_data.consultation_type,
#         "status": AppointmentStatus.SCHEDULED,
#         "reason": appt_data.reason,
#         "created_at": datetime.utcnow(),
#         "updated_at": datetime.utcnow()
#     }
    
#     result = await db.appointments.insert_one(appointment_doc)
    
#     logger.info(f"✅ Appointment created for patient: {current_user['email']}")
    
#     return {
#         "status": "success",
#         "data": {"id": str(result.inserted_id)},
#         "message": "Appointment booked successfully"
#     }

# @app.get("/appointments", response_model=StandardResponse)
# async def list_appointments(
#     current_user: dict = Depends(get_current_user),
#     upcoming_only: bool = Query(True)
# ):
#     """List appointments"""
#     if current_user["role"] == "patient":
#         patient = await db.patients.find_one({"user_id": current_user["_id"]})
#         query = {"patient_id": patient["_id"]}
#     elif current_user["role"] == "doctor":
#         doctor = await db.doctors.find_one({"user_id": current_user["_id"]})
#         query = {"doctor_id": doctor["_id"]}
#     else:
#         query = {}
    
#     if upcoming_only:
#         query["scheduled_date"] = {"$gte": date.today()}
    
#     appointments = await db.appointments.find(query).sort("scheduled_date", 1).to_list(length=100)
    
#     return {
#         "status": "success",
#         "data": [serialize_doc(a) for a in appointments],
#         "message": "Appointments retrieved successfully"
#     }

# # ============================================================================
# # VITALS TRACKING
# # ============================================================================

# @app.post("/vitals", response_model=StandardResponse)
# async def add_vital_record(
#     vital_data: VitalRecordRequest,
#     current_user: dict = Depends(require_role("patient"))
# ):
#     """Add a vital record"""
#     patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
#     vital_doc = {
#         "patient_id": patient["_id"],
#         "vital_type": vital_data.vital_type,
#         "value": vital_data.value,
#         "unit": vital_data.unit,
#         "recorded_at": vital_data.recorded_at or datetime.utcnow(),
#         "notes": vital_data.notes,
#         "created_at": datetime.utcnow()
#     }
    
#     result = await db.vitals.insert_one(vital_doc)
    
#     return {
#         "status": "success",
#         "data": {"id": str(result.inserted_id)},
#         "message": "Vital record added successfully"
#     }

# @app.get("/vitals", response_model=StandardResponse)
# async def list_vitals(
#     current_user: dict = Depends(require_role("patient")),
#     vital_type: Optional[VitalType] = None,
#     limit: int = Query(50, ge=1, le=200)
# ):
#     """List vital records"""
#     patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
#     query = {"patient_id": patient["_id"]}
#     if vital_type:
#         query["vital_type"] = vital_type
    
#     vitals = await db.vitals.find(query).sort("recorded_at", -1).limit(limit).to_list(length=limit)
    
#     return {
#         "status": "success",
#         "data": [serialize_doc(v) for v in vitals],
#         "message": "Vitals retrieved successfully"
#     }

# # ============================================================================
# # AI HEALTH ASSISTANT
# # ============================================================================

# @app.post("/ai/chat", response_model=StandardResponse)
# async def ai_health_chat(
#     chat_data: ChatRequest,
#     current_user: dict = Depends(require_role("patient"))
# ):
#     """AI health assistant chatbot endpoint"""
#     session_id = chat_data.session_id or str(uuid.uuid4())
    
#     # Simple mock AI response
#     message_lower = chat_data.message.lower()
    
#     if any(word in message_lower for word in ["medication", "medicine", "drug"]):
#         response_text = "I can help you with medication information. Would you like to view your medications or set a reminder?"
#         intent = "medication_inquiry"
#     elif any(word in message_lower for word in ["symptom", "pain", "fever"]):
#         response_text = "I recommend tracking your symptoms and consulting a healthcare professional if they persist."
#         intent = "symptom_check"
#     elif any(word in message_lower for word in ["appointment", "book"]):
#         response_text = "I can help you book an appointment with your doctor. Would you like to see available slots?"
#         intent = "appointment_booking"
#     else:
#         response_text = f"Thank you for your message. How else can I assist you with your health today?"
#         intent = "general_inquiry"
    
#     patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
#     chat_doc = {
#         "patient_id": patient["_id"],
#         "session_id": session_id,
#         "message": chat_data.message,
#         "response": response_text,
#         "intent": intent,
#         "created_at": datetime.utcnow()
#     }
    
#     await db.chat_messages.insert_one(chat_doc)
    
#     return {
#         "status": "success",
#         "data": {
#             "session_id": session_id,
#             "response": response_text,
#             "intent": intent
#         },
#         "message": "Chat response generated"
#     }

# # ============================================================================
# # WEBSOCKET ENDPOINTS
# # ============================================================================

# @app.websocket("/ws/notifications")
# async def websocket_notifications(websocket: WebSocket, token: str = Query(...)):
#     """WebSocket endpoint for real-time notifications"""
#     user_id = None
#     try:
#         payload = decode_token(token)
#         user_id = payload.get("sub")
        
#         if not user_id:
#             await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
#             return
        
#         await manager.connect(user_id, websocket)
        
#         try:
#             while True:
#                 data = await websocket.receive_text()
#                 # Keep connection alive
#         except WebSocketDisconnect:
#             pass
#     except Exception as e:
#         logger.error(f"WebSocket error: {e}")
#     finally:
#         if user_id:
#             manager.disconnect(user_id, websocket)

# @app.websocket("/ws/chat")
# async def websocket_chat(websocket: WebSocket, token: str = Query(...)):
#     """WebSocket endpoint for real-time chat"""
#     user_id = None
#     try:
#         payload = decode_token(token)
#         user_id = payload.get("sub")
        
#         if not user_id:
#             await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
#             return
        
#         await manager.connect(user_id, websocket)
        
#         try:
#             while True:
#                 data = await websocket.receive_json()
#                 message = data.get("message")
                
#                 if message:
#                     response = f"AI Response: You said '{message}'"
#                     await manager.send_personal_message(user_id, {"response": response})
#         except WebSocketDisconnect:
#             pass
#     except Exception as e:
#         logger.error(f"WebSocket chat error: {e}")
#     finally:
#         if user_id:
#             manager.disconnect(user_id, websocket)

# # ============================================================================
# # ADMIN ENDPOINTS
# # ============================================================================

# @app.get("/admin/users", response_model=StandardResponse)
# async def list_all_users(
#     current_user: dict = Depends(require_role("admin")),
#     skip: int = Query(0, ge=0),
#     limit: int = Query(50, ge=1, le=100)
# ):
#     """List all users (admin only)"""
#     users = await db.users.find().skip(skip).limit(limit).to_list(length=limit)
    
#     users_data = []
#     for user in users:
#         user_data = serialize_doc(user)
#         user_data.pop("password_hash", None)
#         users_data.append(user_data)
    
#     return {
#         "status": "success",
#         "data": users_data,
#         "message": "Users retrieved successfully"
#     }

# @app.get("/admin/stats", response_model=StandardResponse)
# async def get_admin_stats(current_user: dict = Depends(require_role("admin"))):
#     """Get system statistics"""
#     total_users = await db.users.count_documents({})
#     total_patients = await db.patients.count_documents({})
#     total_doctors = await db.doctors.count_documents({})
#     total_appointments = await db.appointments.count_documents({})
    
#     return {
#         "status": "success",
#         "data": {
#             "total_users": total_users,
#             "total_patients": total_patients,
#             "total_doctors": total_doctors,
#             "total_appointments": total_appointments
#         },
#         "message": "Statistics retrieved successfully"
#     }

# # ============================================================================
# # INSURANCE ENDPOINTS
# # ============================================================================

# @app.post("/insurance/policies", response_model=StandardResponse)
# async def add_insurance_policy(
#     policy_data: InsurancePolicyRequest,
#     current_user: dict = Depends(require_role("patient"))
# ):
#     """Add insurance policy"""
#     patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
#     policy_doc = {
#         "patient_id": patient["_id"],
#         "provider_name": policy_data.provider_name,
#         "policy_number": policy_data.policy_number,
#         "coverage_type": policy_data.coverage_type,
#         "coverage_amount": policy_data.coverage_amount,
#         "start_date": policy_data.start_date,
#         "end_date": policy_data.end_date,
#         "is_active": True,
#         "created_at": datetime.utcnow()
#     }
    
#     result = await db.insurance_policies.insert_one(policy_doc)
    
#     return {
#         "status": "success",
#         "data": {"id": str(result.inserted_id)},
#         "message": "Insurance policy added"
#     }

# @app.get("/insurance/policies", response_model=StandardResponse)
# async def list_insurance_policies(current_user: dict = Depends(require_role("patient"))):
#     """List insurance policies"""
#     patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
#     policies = await db.insurance_policies.find({"patient_id": patient["_id"]}).to_list(length=100)
    
#     return {
#         "status": "success",
#         "data": [serialize_doc(p) for p in policies],
#         "message": "Insurance policies retrieved"
#     }

# # ============================================================================
# # HEALTH CHECK
# # ============================================================================

# @app.get("/health")
# async def health_check():
#     """Health check endpoint"""
#     return {
#         "status": "healthy",
#         "timestamp": datetime.utcnow().isoformat(),
#         "version": "2.0.0"
#     }

# @app.get("/")
# async def root():
#     """Root endpoint"""
#     return {
#         "message": "Digital Health Card API",
#         "version": "2.0.0",
#         "docs": "/docs",
#         "health": "/health"
#     }

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)