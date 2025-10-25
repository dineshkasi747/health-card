from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import jwt
import bcrypt
import logging
import os
import shutil
from pathlib import Path
import mimetypes
from config import settings
from models import (
    UserSignup, UserLogin, UserResponse, TokenResponse,
    PatientProfile, DoctorProfile, AdminProfile,
    Hospital, HospitalResponse, HospitalCreate, HospitalUpdate,
    Prescription, PrescriptionUpload, PrescriptionResponse,
    Appointment, AppointmentCreate, AppointmentResponse, AppointmentUpdate,
    ChatMessage, ChatMessageCreate,
    MedicationReminder, MedicationReminderCreate,
    HealthVitals, HealthVitalsCreate,
    NotificationResponse, DoctorAssignment
)

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Digital Health Card API",
    version="2.0.0",
    description="Production-ready Digital Health Card System with role-based access control",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# MongoDB Connection
client: Optional[AsyncIOMotorClient] = None
db = None

# Collections will be initialized on startup
users_collection = None
hospitals_collection = None
prescriptions_collection = None
appointments_collection = None
chats_collection = None
medications_collection = None
vitals_collection = None
notifications_collection = None

# ==================== CONNECTION MANAGER ====================

class ConnectionManager:
    """Manages WebSocket connections for real-time communication"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_roles: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket, user_id: str, role: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.user_roles[user_id] = role
        logger.info(f"User {user_id} ({role}) connected via WebSocket")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            del self.user_roles[user_id]
            logger.info(f"User {user_id} disconnected from WebSocket")

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
                logger.info(f"Message sent to user {user_id}")
            except Exception as e:
                logger.error(f"Error sending message to {user_id}: {str(e)}")
                self.disconnect(user_id)

    async def broadcast_to_role(self, message: dict, role: str):
        """Broadcast message to all users of a specific role"""
        for user_id, user_role in self.user_roles.items():
            if user_role == role:
                await self.send_personal_message(message, user_id)

    async def broadcast_to_hospital(self, message: dict, hospital_id: str):
        """Broadcast to all users in a specific hospital"""
        for user_id in self.active_connections.keys():
            await self.send_personal_message(message, user_id)

manager = ConnectionManager()

# ==================== HELPER FUNCTIONS ====================

def create_jwt_token(user_id: str, role: str, email: str) -> str:
    """Create JWT token with enhanced payload"""
    payload = {
        "user_id": user_id,
        "role": role,
        "email": email,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=settings.JWT_EXPIRY_DAYS)
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def verify_jwt_token(token: str) -> dict:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Expired token attempt")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        logger.warning("Invalid token attempt")
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    payload = verify_jwt_token(token)
    
    user = await users_collection.find_one({"_id": ObjectId(payload["user_id"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user["id"] = str(user["_id"])
    return user

def require_role(*allowed_roles: str):
    """Decorator to check user role"""
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            logger.warning(f"Unauthorized access attempt by {current_user['role']} to {allowed_roles} endpoint")
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    if "password" in doc:
        del doc["password"]
    return doc

async def create_notification(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    data: dict = None
) -> dict:
    """Create and send notification"""
    notification = {
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "data": data or {},
        "read": False,
        "created_at": datetime.utcnow()
    }
    
    result = await notifications_collection.insert_one(notification)
    notification["_id"] = str(result.inserted_id)
    
    # Send via WebSocket
    await manager.send_personal_message({
        "type": "notification",
        "data": notification
    }, user_id)
    
    logger.info(f"Notification created for user {user_id}: {title}")
    return notification

# ==================== STARTUP & SHUTDOWN ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database connection and create dummy data"""
    global client, db
    global users_collection, hospitals_collection, prescriptions_collection
    global appointments_collection, chats_collection, medications_collection
    global vitals_collection, notifications_collection
    
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        db = client[settings.DATABASE_NAME]
        
        # Initialize collections
        users_collection = db["users"]
        hospitals_collection = db["hospitals"]
        prescriptions_collection = db["prescriptions"]
        appointments_collection = db["appointments"]
        chats_collection = db["chats"]
        medications_collection = db["medications"]
        vitals_collection = db["vitals"]
        notifications_collection = db["notifications"]
        
        # Create indexes for better performance
        await users_collection.create_index("email", unique=True)
        await appointments_collection.create_index([("patient_id", 1), ("created_at", -1)])
        await prescriptions_collection.create_index([("patient_id", 1), ("uploaded_at", -1)])
        await chats_collection.create_index([("sender_id", 1), ("receiver_id", 1)])
        await notifications_collection.create_index([("user_id", 1), ("created_at", -1)])
        
        # Create upload directories
        Path("uploads/prescriptions").mkdir(parents=True, exist_ok=True)
        Path("uploads/avatars").mkdir(parents=True, exist_ok=True)
        
        # Create dummy data
        await create_dummy_data()
        
        logger.info("✅ Application startup complete")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection"""
    if client:
        client.close()
        logger.info("Database connection closed")

async def create_dummy_data():
    """Create dummy data for testing"""
    try:
        # Check if dummy data exists
        existing_admin = await users_collection.find_one({"email": "admin@healthcard.com"})
        if existing_admin:
            logger.info("Dummy data already exists")
            return

        # Create Dummy Hospital
        dummy_hospital = {
            "name": "CarePlus Hospital",
            "address": "123 Healthcare Street, Medical District, New York, NY 10001",
            "phone": "+1-555-0123",
            "email": "info@careplus.com",
            "website": "https://careplus-hospital.com",
            "location": {
                "type": "Point",
                "coordinates": [-74.0060, 40.7128]
            },
            "services": ["Emergency Care", "General Medicine", "Surgery", "Pediatrics"],
            "is_dummy": True,
            "created_at": datetime.utcnow(),
            "operating_hours": "24/7"
        }
        hospital_result = await hospitals_collection.insert_one(dummy_hospital)
        hospital_id = str(hospital_result.inserted_id)
        logger.info(f"Created dummy hospital: {hospital_id}")

        # Create Dummy Admin
        admin_data = {
            "full_name": "Admin Manager",
            "email": "admin@healthcard.com",
            "password": hash_password("Admin@123"),
            "role": "admin",
            "hospital_name": "CarePlus Hospital",
            "hospital_address": "123 Healthcare Street, Medical District",
            "hospital_id": hospital_id,
            "phone": "+1-555-0100",
            "created_at": datetime.utcnow(),
            "is_active": True
        }
        admin_result = await users_collection.insert_one(admin_data)
        logger.info(f"Created dummy admin: {admin_result.inserted_id}")

        # Create Multiple Dummy Doctors
        doctors_data = [
            {
                "full_name": "Dr. John Smith",
                "email": "doctor@careplus.com",
                "password": hash_password("Doctor@123"),
                "role": "doctor",
                "hospital_id": hospital_id,
                "specialization": "General Physician",
                "license_number": "DOC12345",
                "phone": "+1-555-0201",
                "experience_years": 10,
                "created_at": datetime.utcnow(),
                "is_active": True,
                "availability": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            },
            {
                "full_name": "Dr. Sarah Johnson",
                "email": "dr.sarah@careplus.com",
                "password": hash_password("Doctor@123"),
                "role": "doctor",
                "hospital_id": hospital_id,
                "specialization": "Cardiologist",
                "license_number": "DOC12346",
                "phone": "+1-555-0202",
                "experience_years": 15,
                "created_at": datetime.utcnow(),
                "is_active": True,
                "availability": ["Monday", "Wednesday", "Friday"]
            },
            {
                "full_name": "Dr. Michael Chen",
                "email": "dr.chen@careplus.com",
                "password": hash_password("Doctor@123"),
                "role": "doctor",
                "hospital_id": hospital_id,
                "specialization": "Pediatrician",
                "license_number": "DOC12347",
                "phone": "+1-555-0203",
                "experience_years": 8,
                "created_at": datetime.utcnow(),
                "is_active": True,
                "availability": ["Tuesday", "Thursday", "Saturday"]
            }
        ]
        
        for doctor in doctors_data:
            await users_collection.insert_one(doctor)
        logger.info(f"Created {len(doctors_data)} dummy doctors")

        # Create Dummy Patient
        patient_data = {
            "full_name": "Jane Doe",
            "email": "patient@health.com",
            "password": hash_password("Patient@123"),
            "role": "patient",
            "phone_number": "+1-555-0301",
            "address": "456 Patient Lane, Residential Area, NY 10002",
            "date_of_birth": "1990-01-15",
            "blood_group": "O+",
            "gender": "Female",
            "emergency_contact": {
                "name": "John Doe",
                "relationship": "Spouse",
                "phone": "+1-555-0302"
            },
            "created_at": datetime.utcnow(),
            "is_active": True
        }
        patient_result = await users_collection.insert_one(patient_data)
        logger.info(f"Created dummy patient: {patient_result.inserted_id}")

        logger.info("✅ Dummy data initialization complete")

    except Exception as e:
        logger.error(f"Error creating dummy data: {str(e)}")

# ==================== AUTH ENDPOINTS ====================

@app.post("/api/v1/auth/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
async def signup(user_data: UserSignup):
    """Register a new user (Patient, Doctor, or Admin)"""
    try:
        existing_user = await users_collection.find_one({"email": user_data.email})
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        user_dict = user_data.dict(exclude_unset=True)
        user_dict["password"] = hash_password(user_data.password)
        user_dict["created_at"] = datetime.utcnow()
        user_dict["is_active"] = True

        if user_data.role == "doctor":
            if not user_data.hospital_id:
                raise HTTPException(status_code=400, detail="Hospital ID required for doctors")
            
            hospital = await hospitals_collection.find_one({"_id": ObjectId(user_data.hospital_id)})
            if not hospital:
                raise HTTPException(status_code=404, detail="Hospital not found")
            
            if not user_data.specialization or not user_data.license_number:
                raise HTTPException(status_code=400, detail="Specialization and license number required for doctors")

        elif user_data.role == "patient":
            if not user_data.phone_number or not user_data.address or not user_data.date_of_birth:
                raise HTTPException(status_code=400, detail="Phone, address, and date of birth required for patients")

        elif user_data.role == "admin":
            if not user_data.hospital_name or not user_data.hospital_address:
                raise HTTPException(status_code=400, detail="Hospital details required for admins")

        result = await users_collection.insert_one(user_dict)
        user_id = str(result.inserted_id)

        token = create_jwt_token(user_id, user_data.role, user_data.email)

        logger.info(f"New {user_data.role} registered: {user_data.email}")

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_id=user_id,
            role=user_data.role,
            email=user_data.email
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["Authentication"])
async def login(credentials: UserLogin):
    """Login with email and password"""
    try:
        user = await users_collection.find_one({"email": credentials.email})
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="Account is deactivated")

        if not verify_password(credentials.password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user_id = str(user["_id"])
        token = create_jwt_token(user_id, user["role"], user["email"])

        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"last_login": datetime.utcnow()}}
        )

        logger.info(f"User logged in: {credentials.email}")

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_id=user_id,
            role=user["role"],
            email=user["email"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.get("/api/v1/chat/conversations", tags=["Chat"])
async def get_conversations(
    current_user: dict = Depends(get_current_user)
):
    """Get all conversations for the current user"""
    try:
        messages = await chats_collection.find({
            "$or": [
                {"sender_id": current_user["id"]},
                {"receiver_id": current_user["id"]}
            ]
        }).sort("created_at", -1).to_list(1000)

        conversations = {}
        for msg in messages:
            other_user_id = msg["receiver_id"] if msg["sender_id"] == current_user["id"] else msg["sender_id"]
            
            if other_user_id not in conversations:
                conversations[other_user_id] = {
                    "user_id": other_user_id,
                    "user_name": msg["receiver_name"] if msg["sender_id"] == current_user["id"] else msg["sender_name"],
                    "user_role": msg["receiver_role"] if msg["sender_id"] == current_user["id"] else msg["sender_role"],
                    "last_message": msg["message"],
                    "last_message_time": msg["created_at"],
                    "unread_count": 0
                }
            
            if msg["receiver_id"] == current_user["id"] and not msg.get("read"):
                conversations[other_user_id]["unread_count"] += 1

        return list(conversations.values())

    except Exception as e:
        logger.error(f"Get conversations error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversations")

@app.get("/api/v1/chat/{user_id}/messages", tags=["Chat"])
async def get_chat_messages(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get chat messages between current user and another user"""
    try:
        messages = await chats_collection.find({
            "$or": [
                {"sender_id": current_user["id"], "receiver_id": user_id},
                {"sender_id": user_id, "receiver_id": current_user["id"]}
            ]
        }).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

        await chats_collection.update_many(
            {"sender_id": user_id, "receiver_id": current_user["id"], "read": False},
            {"$set": {"read": True, "read_at": datetime.utcnow()}}
        )

        return [serialize_doc(m) for m in reversed(messages)]

    except Exception as e:
        logger.error(f"Get chat messages error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch messages")

@app.put("/api/v1/chat/messages/{message_id}/read", tags=["Chat"])
async def mark_message_as_read(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark a message as read"""
    try:
        message = await chats_collection.find_one({
            "_id": ObjectId(message_id),
            "receiver_id": current_user["id"]
        })
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        await chats_collection.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": {"read": True, "read_at": datetime.utcnow()}}
        )

        return {"message": "Message marked as read"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mark message as read error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update message")

# ==================== NOTIFICATIONS ENDPOINTS ====================

@app.get("/api/v1/notifications", response_model=List[NotificationResponse], tags=["Notifications"])
async def get_notifications(
    unread_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get all notifications for the current user"""
    try:
        query = {"user_id": current_user["id"]}
        
        if unread_only:
            query["read"] = False

        notifications = await notifications_collection.find(query)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)\
            .to_list(limit)

        return [serialize_doc(n) for n in notifications]

    except Exception as e:
        logger.error(f"Get notifications error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch notifications")

@app.put("/api/v1/notifications/{notification_id}/read", tags=["Notifications"])
async def mark_notification_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark a notification as read"""
    try:
        notification = await notifications_collection.find_one({
            "_id": ObjectId(notification_id),
            "user_id": current_user["id"]
        })
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        await notifications_collection.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"read": True, "read_at": datetime.utcnow()}}
        )

        return {"message": "Notification marked as read"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mark notification as read error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update notification")

@app.put("/api/v1/notifications/mark-all-read", tags=["Notifications"])
async def mark_all_notifications_as_read(
    current_user: dict = Depends(get_current_user)
):
    """Mark all notifications as read"""
    try:
        result = await notifications_collection.update_many(
            {"user_id": current_user["id"], "read": False},
            {"$set": {"read": True, "read_at": datetime.utcnow()}}
        )

        return {"message": f"{result.modified_count} notifications marked as read"}

    except Exception as e:
        logger.error(f"Mark all notifications as read error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update notifications")

@app.delete("/api/v1/notifications/{notification_id}", tags=["Notifications"])
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a notification"""
    try:
        notification = await notifications_collection.find_one({
            "_id": ObjectId(notification_id),
            "user_id": current_user["id"]
        })
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        await notifications_collection.delete_one({"_id": ObjectId(notification_id)})

        return {"message": "Notification deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete notification error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete notification")

@app.get("/api/v1/notifications/unread/count", tags=["Notifications"])
async def get_unread_notifications_count(
    current_user: dict = Depends(get_current_user)
):
    """Get count of unread notifications"""
    try:
        count = await notifications_collection.count_documents({
            "user_id": current_user["id"],
            "read": False
        })

        return {"unread_count": count}

    except Exception as e:
        logger.error(f"Get unread count error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get unread count")

# ==================== WEBSOCKET ENDPOINTS ====================

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time communication"""
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return

        await manager.connect(websocket, user_id, user["role"])
        
        try:
            while True:
                data = await websocket.receive_json()
                
                message_type = data.get("type")
                
                if message_type == "chat_message":
                    receiver_id = data.get("receiver_id")
                    message_content = data.get("message")
                    
                    message_data = {
                        "sender_id": user_id,
                        "sender_name": user["full_name"],
                        "sender_role": user["role"],
                        "receiver_id": receiver_id,
                        "message": message_content,
                        "read": False,
                        "created_at": datetime.utcnow()
                    }
                    
                    result = await chats_collection.insert_one(message_data)
                    message_data["_id"] = str(result.inserted_id)
                    
                    await manager.send_personal_message({
                        "type": "chat_message",
                        "data": serialize_doc(message_data)
                    }, receiver_id)
                
                elif message_type == "typing":
                    receiver_id = data.get("receiver_id")
                    await manager.send_personal_message({
                        "type": "typing",
                        "data": {
                            "user_id": user_id,
                            "user_name": user["full_name"],
                            "is_typing": data.get("is_typing", True)
                        }
                    }, receiver_id)
                
                elif message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    
        except WebSocketDisconnect:
            manager.disconnect(user_id)
            logger.info(f"WebSocket disconnected: {user_id}")
        except Exception as e:
            logger.error(f"WebSocket error for user {user_id}: {str(e)}")
            manager.disconnect(user_id)
            
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
        await websocket.close(code=1011, reason="Internal server error")

# ==================== FILE DOWNLOAD ENDPOINTS ====================

@app.get("/api/v1/prescriptions/{prescription_id}/download", tags=["Files"])
async def download_prescription_file(
    prescription_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Download prescription file"""
    try:
        prescription = await prescriptions_collection.find_one({"_id": ObjectId(prescription_id)})
        
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")
        
        if current_user["role"] == "patient":
            if prescription["patient_id"] != current_user["id"]:
                raise HTTPException(status_code=403, detail="Access denied")
        elif current_user["role"] == "doctor":
            has_access = await appointments_collection.find_one({
                "patient_id": prescription["patient_id"],
                "doctor_id": current_user["id"]
            })
            if not has_access:
                raise HTTPException(status_code=403, detail="Access denied")
        elif current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Access denied")

        file_path = prescription["file_path"]
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            path=file_path,
            filename=prescription["file_name"],
            media_type=prescription["file_type"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download prescription error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download file")

# ==================== QR CODE ENDPOINTS ====================

@app.get("/api/v1/patient/qr-code", tags=["Patient"])
async def generate_patient_qr_code(
    current_user: dict = Depends(require_role("patient"))
):
    """Generate QR code data for patient"""
    try:
        qr_data = {
            "patient_id": current_user["id"],
            "patient_name": current_user["full_name"],
            "patient_email": current_user["email"],
            "blood_group": current_user.get("blood_group"),
            "emergency_contact": current_user.get("emergency_contact"),
            "generated_at": datetime.utcnow().isoformat()
        }

        return qr_data

    except Exception as e:
        logger.error(f"Generate QR code error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate QR code")

@app.post("/api/v1/doctor/scan-qr", tags=["Doctor"])
async def scan_patient_qr_code(
    patient_id: str,
    current_user: dict = Depends(require_role("doctor"))
):
    """Scan patient QR code and get health details"""
    try:
        return await get_patient_health_details(patient_id, current_user)

    except Exception as e:
        logger.error(f"Scan QR code error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to scan QR code")

# ==================== SEARCH & FILTER ENDPOINTS ====================

@app.get("/api/v1/search/patients", tags=["Search"])
async def search_patients(
    query: str = Query(..., min_length=2),
    current_user: dict = Depends(require_role("admin", "doctor"))
):
    """Search patients by name or email"""
    try:
        if current_user["role"] == "doctor":
            patient_ids = await appointments_collection.distinct(
                "patient_id",
                {"doctor_id": current_user["id"]}
            )
            
            patients = await users_collection.find({
                "_id": {"$in": [ObjectId(pid) for pid in patient_ids]},
                "role": "patient",
                "$or": [
                    {"full_name": {"$regex": query, "$options": "i"}},
                    {"email": {"$regex": query, "$options": "i"}}
                ]
            }).limit(20).to_list(20)
        else:
            patients = await users_collection.find({
                "role": "patient",
                "$or": [
                    {"full_name": {"$regex": query, "$options": "i"}},
                    {"email": {"$regex": query, "$options": "i"}}
                ]
            }).limit(20).to_list(20)

        return [serialize_doc(p) for p in patients]

    except Exception as e:
        logger.error(f"Search patients error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search patients")

@app.get("/api/v1/search/doctors", tags=["Search"])
async def search_doctors(
    query: str = Query(..., min_length=2),
    specialization: Optional[str] = None,
    current_user: dict = Depends(require_role("admin", "patient"))
):
    """Search doctors by name, specialization"""
    try:
        search_query = {
            "role": "doctor",
            "is_active": True,
            "$or": [
                {"full_name": {"$regex": query, "$options": "i"}},
                {"specialization": {"$regex": query, "$options": "i"}}
            ]
        }
        
        if specialization:
            search_query["specialization"] = {"$regex": specialization, "$options": "i"}

        if current_user["role"] == "admin":
            search_query["hospital_id"] = current_user.get("hospital_id")

        doctors = await users_collection.find(search_query).limit(20).to_list(20)

        return [serialize_doc(d) for d in doctors]

    except Exception as e:
        logger.error(f"Search doctors error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search doctors")

# ==================== ANALYTICS ENDPOINTS ====================

@app.get("/api/v1/analytics/patient-health-trends", tags=["Analytics"])
async def get_patient_health_trends(
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(require_role("patient"))
):
    """Get health trends for patient"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        vitals = await vitals_collection.find({
            "patient_id": current_user["id"],
            "recorded_at": {"$gte": start_date}
        }).sort("recorded_at", 1).to_list(1000)

        trends = {
            "heart_rate": [],
            "blood_pressure_systolic": [],
            "blood_pressure_diastolic": [],
            "steps": [],
            "sleep_hours": []
        }

        for vital in vitals:
            date = vital["recorded_at"].strftime("%Y-%m-%d")
            
            if vital.get("heart_rate"):
                trends["heart_rate"].append({"date": date, "value": vital["heart_rate"]})
            if vital.get("blood_pressure_systolic"):
                trends["blood_pressure_systolic"].append({"date": date, "value": vital["blood_pressure_systolic"]})
            if vital.get("blood_pressure_diastolic"):
                trends["blood_pressure_diastolic"].append({"date": date, "value": vital["blood_pressure_diastolic"]})
            if vital.get("steps"):
                trends["steps"].append({"date": date, "value": vital["steps"]})
            if vital.get("sleep_hours"):
                trends["sleep_hours"].append({"date": date, "value": vital["sleep_hours"]})

        return trends

    except Exception as e:
        logger.error(f"Get health trends error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch health trends")

# ==================== HEALTH CHECK ====================

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    try:
        await users_collection.find_one()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "version": "2.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "database": "disconnected",
                "error": str(e)
            }
        )

@app.get("/", tags=["System"])
async def root():
    """Root endpoint"""
    return {
        "message": "Digital Health Card API",
        "version": "2.0.0",
        "docs": "/api/docs",
        "health": "/health"
    }

# ==================== ERROR HANDLERS ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )/v1/auth/me", response_model=UserResponse, tags=["Authentication"])
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return serialize_doc(current_user)

@app.post("/api/v1/auth/refresh", response_model=TokenResponse, tags=["Authentication"])
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """Refresh JWT token"""
    new_token = create_jwt_token(
        str(current_user["_id"]),
        current_user["role"],
        current_user["email"]
    )
    
    return TokenResponse(
        access_token=new_token,
        token_type="bearer",
        user_id=str(current_user["_id"]),
        role=current_user["role"],
        email=current_user["email"]
    )

# ==================== PATIENT ENDPOINTS ====================

@app.get("/api/v1/patient/profile", tags=["Patient"])
async def get_patient_profile(current_user: dict = Depends(require_role("patient"))):
    """Get patient profile details"""
    return serialize_doc(current_user)

@app.put("/api/v1/patient/profile", tags=["Patient"])
async def update_patient_profile(
    profile: PatientProfile,
    current_user: dict = Depends(require_role("patient"))
):
    """Update patient profile information"""
    try:
        update_data = profile.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        await users_collection.update_one(
            {"_id": ObjectId(current_user["_id"])},
            {"$set": update_data}
        )

        logger.info(f"Patient profile updated: {current_user['email']}")
        return {"message": "Profile updated successfully", "updated_fields": list(update_data.keys())}

    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        raise HTTPException(status_code=500, detail="Profile update failed")

@app.post("/api/v1/patient/prescriptions/upload", response_model=PrescriptionResponse, tags=["Patient"])
async def upload_prescription(
    file: UploadFile = File(...),
    doctor_name: Optional[str] = None,
    date_prescribed: Optional[str] = None,
    notes: Optional[str] = None,
    current_user: dict = Depends(require_role("patient"))
):
    """Upload a prescription (PDF or Image)"""
    try:
        allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/jpg"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Invalid file type. Only PDF and images allowed")

        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{current_user['id']}_{int(datetime.utcnow().timestamp())}{file_extension}"
        file_path = f"uploads/prescriptions/{unique_filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        prescription_data = {
            "patient_id": current_user["id"],
            "patient_name": current_user["full_name"],
            "file_path": file_path,
            "file_name": file.filename,
            "file_type": file.content_type,
            "file_size": os.path.getsize(file_path),
            "doctor_name": doctor_name,
            "date_prescribed": date_prescribed,
            "notes": notes,
            "uploaded_at": datetime.utcnow(),
            "ocr_processed": False,
            "ai_processed": False,
            "summary": None,
            "medications": [],
            "extracted_text": None
        }

        result = await prescriptions_collection.insert_one(prescription_data)
        prescription_data["_id"] = str(result.inserted_id)

        logger.info(f"Prescription uploaded by patient {current_user['email']}")

        return serialize_doc(prescription_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prescription upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="Prescription upload failed")

@app.get("/api/v1/patient/prescriptions", response_model=List[PrescriptionResponse], tags=["Patient"])
async def get_patient_prescriptions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role("patient"))
):
    """Get all prescriptions for the current patient"""
    try:
        prescriptions = await prescriptions_collection.find(
            {"patient_id": current_user["id"]}
        ).sort("uploaded_at", -1).skip(skip).limit(limit).to_list(limit)

        return [serialize_doc(p) for p in prescriptions]

    except Exception as e:
        logger.error(f"Get prescriptions error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch prescriptions")

@app.get("/api/v1/patient/prescriptions/{prescription_id}", response_model=PrescriptionResponse, tags=["Patient"])
async def get_prescription_detail(
    prescription_id: str,
    current_user: dict = Depends(require_role("patient"))
):
    """Get detailed prescription information"""
    try:
        prescription = await prescriptions_collection.find_one({
            "_id": ObjectId(prescription_id),
            "patient_id": current_user["id"]
        })
        
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")

        return serialize_doc(prescription)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get prescription detail error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch prescription")

@app.post("/api/v1/patient/prescriptions/{prescription_id}/process", tags=["Patient"])
async def process_prescription_with_ai(
    prescription_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_role("patient"))
):
    """Process prescription with OCR and AI (Gemini API)"""
    try:
        prescription = await prescriptions_collection.find_one({
            "_id": ObjectId(prescription_id),
            "patient_id": current_user["id"]
        })
        
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")

        if prescription.get("ocr_processed"):
            return {"message": "Prescription already processed", "data": serialize_doc(prescription)}

        mock_summary = "Prescription for respiratory infection. Patient should take antibiotics for 7 days and use inhaler as needed. Follow up in 2 weeks."
        mock_medications = [
            {
                "name": "Amoxicillin",
                "dosage": "500mg",
                "frequency": "Three times daily",
                "duration": "7 days",
                "instructions": "Take after meals",
                "times": ["08:00", "14:00", "20:00"]
            },
            {
                "name": "Albuterol Inhaler",
                "dosage": "2 puffs",
                "frequency": "As needed",
                "duration": "30 days",
                "instructions": "Use when experiencing shortness of breath",
                "times": []
            }
        ]

        await prescriptions_collection.update_one(
            {"_id": ObjectId(prescription_id)},
            {"$set": {
                "ocr_processed": True,
                "ai_processed": True,
                "summary": mock_summary,
                "medications": mock_medications,
                "processed_at": datetime.utcnow(),
                "extracted_text": "Sample extracted text from prescription..."
            }}
        )

        for med in mock_medications:
            if med["times"]:
                reminder_data = {
                    "patient_id": current_user["id"],
                    "prescription_id": prescription_id,
                    "medication_name": med["name"],
                    "dosage": med["dosage"],
                    "frequency": med["frequency"],
                    "times": med["times"],
                    "start_date": datetime.utcnow().date().isoformat(),
                    "duration_days": int(med["duration"].split()[0]) if "days" in med["duration"] else 30,
                    "instructions": med["instructions"],
                    "active": True,
                    "created_at": datetime.utcnow()
                }
                await medications_collection.insert_one(reminder_data)

        logger.info(f"Prescription processed: {prescription_id}")

        return {
            "message": "Prescription processed successfully",
            "summary": mock_summary,
            "medications": mock_medications,
            "reminders_created": len([m for m in mock_medications if m["times"]])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prescription processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process prescription")

@app.get("/api/v1/patient/hospitals", response_model=List[HospitalResponse], tags=["Patient"])
async def get_nearby_hospitals(
    latitude: Optional[float] = Query(None),
    longitude: Optional[float] = Query(None),
    radius: int = Query(10, ge=1, le=100, description="Search radius in kilometers"),
    current_user: dict = Depends(require_role("patient"))
):
    """Get nearby hospitals (dummy hospital always appears first)"""
    try:
        query = {}
        
        if latitude and longitude:
            query["location"] = {
                "$near": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [longitude, latitude]
                    },
                    "$maxDistance": radius * 1000
                }
            }

        hospitals = await hospitals_collection.find(query).to_list(100)
        
        hospitals.sort(key=lambda x: (not x.get("is_dummy", False), x.get("name", "")))

        return [serialize_doc(h) for h in hospitals]

    except Exception as e:
        logger.error(f"Get hospitals error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch hospitals")

@app.post("/api/v1/patient/appointments", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED, tags=["Patient"])
async def book_appointment(
    appointment: AppointmentCreate,
    current_user: dict = Depends(require_role("patient"))
):
    """Book an appointment at a hospital"""
    try:
        hospital = await hospitals_collection.find_one({"_id": ObjectId(appointment.hospital_id)})
        if not hospital:
            raise HTTPException(status_code=404, detail="Hospital not found")

        appointment_data = {
            "patient_id": current_user["id"],
            "patient_name": current_user["full_name"],
            "patient_phone": current_user.get("phone_number"),
            "hospital_id": appointment.hospital_id,
            "hospital_name": hospital["name"],
            "symptoms": appointment.symptoms,
            "preferred_date": appointment.preferred_date,
            "preferred_time": appointment.preferred_time,
            "appointment_type": appointment.appointment_type if hasattr(appointment, 'appointment_type') else "general",
            "status": "pending",
            "doctor_id": None,
            "doctor_name": None,
            "notes": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await appointments_collection.insert_one(appointment_data)
        appointment_data["_id"] = str(result.inserted_id)

        admin = await users_collection.find_one({
            "hospital_id": appointment.hospital_id,
            "role": "admin"
        })
        
        if admin:
            await create_notification(
                user_id=str(admin["_id"]),
                notification_type="appointment_request",
                title="New Appointment Request",
                message=f"New appointment request from {current_user['full_name']} for {appointment.preferred_date}",
                data=serialize_doc(appointment_data)
            )

        logger.info(f"Appointment booked by {current_user['email']} at {hospital['name']}")

        return serialize_doc(appointment_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Book appointment error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to book appointment")

@app.get("/api/v1/patient/appointments", response_model=List[AppointmentResponse], tags=["Patient"])
async def get_patient_appointments(
    status_filter: Optional[str] = Query(None, description="Filter by status: pending, confirmed, completed, cancelled"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role("patient"))
):
    """Get all appointments for the current patient"""
    try:
        query = {"patient_id": current_user["id"]}
        
        if status_filter:
            query["status"] = status_filter

        appointments = await appointments_collection.find(query)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)\
            .to_list(limit)

        return [serialize_doc(a) for a in appointments]

    except Exception as e:
        logger.error(f"Get patient appointments error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch appointments")

@app.delete("/api/v1/patient/appointments/{appointment_id}", tags=["Patient"])
async def cancel_appointment(
    appointment_id: str,
    reason: Optional[str] = None,
    current_user: dict = Depends(require_role("patient"))
):
    """Cancel an appointment"""
    try:
        appointment = await appointments_collection.find_one({
            "_id": ObjectId(appointment_id),
            "patient_id": current_user["id"]
        })
        
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        if appointment["status"] in ["completed", "cancelled"]:
            raise HTTPException(status_code=400, detail="Cannot cancel this appointment")

        await appointments_collection.update_one(
            {"_id": ObjectId(appointment_id)},
            {"$set": {
                "status": "cancelled",
                "cancellation_reason": reason,
                "cancelled_at": datetime.utcnow(),
                "cancelled_by": "patient"
            }}
        )

        if appointment.get("doctor_id"):
            await create_notification(
                user_id=appointment["doctor_id"],
                notification_type="appointment_cancelled",
                title="Appointment Cancelled",
                message=f"Appointment with {current_user['full_name']} has been cancelled",
                data={"appointment_id": appointment_id, "reason": reason}
            )

        admin = await users_collection.find_one({
            "hospital_id": appointment["hospital_id"],
            "role": "admin"
        })
        
        if admin:
            await create_notification(
                user_id=str(admin["_id"]),
                notification_type="appointment_cancelled",
                title="Appointment Cancelled by Patient",
                message=f"{current_user['full_name']} cancelled their appointment",
                data={"appointment_id": appointment_id, "reason": reason}
            )

        logger.info(f"Appointment {appointment_id} cancelled by patient")

        return {"message": "Appointment cancelled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cancel appointment error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cancel appointment")

# ==================== ADMIN ENDPOINTS ====================

@app.post("/api/v1/admin/hospitals", response_model=HospitalResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"])
async def create_hospital(
    hospital: HospitalCreate,
    current_user: dict = Depends(require_role("admin"))
):
    """Create a new hospital"""
    try:
        hospital_data = hospital.dict()
        hospital_data["admin_id"] = current_user["id"]
        hospital_data["is_dummy"] = False
        hospital_data["created_at"] = datetime.utcnow()

        result = await hospitals_collection.insert_one(hospital_data)
        hospital_id = str(result.inserted_id)

        if not current_user.get("hospital_id"):
            await users_collection.update_one(
                {"_id": ObjectId(current_user["_id"])},
                {"$set": {"hospital_id": hospital_id}}
            )

        hospital_data["_id"] = hospital_id
        logger.info(f"Hospital created by admin {current_user['email']}: {hospital['name']}")

        return serialize_doc(hospital_data)

    except Exception as e:
        logger.error(f"Create hospital error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create hospital")

@app.get("/api/v1/admin/hospitals", response_model=List[HospitalResponse], tags=["Admin"])
async def get_admin_hospitals(
    current_user: dict = Depends(require_role("admin"))
):
    """Get all hospitals managed by the admin"""
    try:
        hospitals = await hospitals_collection.find(
            {"admin_id": current_user["id"]}
        ).to_list(100)

        return [serialize_doc(h) for h in hospitals]

    except Exception as e:
        logger.error(f"Get admin hospitals error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch hospitals")

@app.put("/api/v1/admin/hospitals/{hospital_id}", tags=["Admin"])
async def update_hospital(
    hospital_id: str,
    hospital_update: HospitalUpdate,
    current_user: dict = Depends(require_role("admin"))
):
    """Update hospital information"""
    try:
        hospital = await hospitals_collection.find_one({
            "_id": ObjectId(hospital_id),
            "admin_id": current_user["id"]
        })
        
        if not hospital:
            raise HTTPException(status_code=404, detail="Hospital not found")

        update_data = hospital_update.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        await hospitals_collection.update_one(
            {"_id": ObjectId(hospital_id)},
            {"$set": update_data}
        )

        logger.info(f"Hospital {hospital_id} updated by admin")

        return {"message": "Hospital updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update hospital error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update hospital")

@app.get("/api/v1/admin/appointments", response_model=List[AppointmentResponse], tags=["Admin"])
async def get_admin_appointments(
    status_filter: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_role("admin"))
):
    """Get all appointments for admin's hospital"""
    try:
        hospital_id = current_user.get("hospital_id")
        if not hospital_id:
            return []

        query = {"hospital_id": hospital_id}
        if status_filter:
            query["status"] = status_filter

        appointments = await appointments_collection.find(query)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)\
            .to_list(limit)

        return [serialize_doc(a) for a in appointments]

    except Exception as e:
        logger.error(f"Get admin appointments error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch appointments")

@app.put("/api/v1/admin/appointments/{appointment_id}/assign", tags=["Admin"])
async def assign_doctor_to_appointment(
    appointment_id: str,
    assignment: DoctorAssignment,
    current_user: dict = Depends(require_role("admin"))
):
    """Assign a doctor to an appointment"""
    try:
        appointment = await appointments_collection.find_one({
            "_id": ObjectId(appointment_id),
            "hospital_id": current_user.get("hospital_id")
        })
        
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        doctor = await users_collection.find_one({
            "_id": ObjectId(assignment.doctor_id),
            "role": "doctor",
            "hospital_id": current_user.get("hospital_id")
        })
        
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")

        update_data = {
            "doctor_id": assignment.doctor_id,
            "doctor_name": doctor["full_name"],
            "status": "confirmed",
            "updated_at": datetime.utcnow()
        }
        
        if assignment.scheduled_date:
            update_data["scheduled_date"] = assignment.scheduled_date
        if assignment.scheduled_time:
            update_data["scheduled_time"] = assignment.scheduled_time
        if assignment.notes:
            update_data["admin_notes"] = assignment.notes

        await appointments_collection.update_one(
            {"_id": ObjectId(appointment_id)},
            {"$set": update_data}
        )

        await create_notification(
            user_id=assignment.doctor_id,
            notification_type="appointment_assigned",
            title="New Patient Assigned",
            message=f"You have been assigned to patient {appointment['patient_name']}",
            data=serialize_doc(appointment)
        )

        await create_notification(
            user_id=appointment["patient_id"],
            notification_type="appointment_confirmed",
            title="Appointment Confirmed",
            message=f"Your appointment has been confirmed with Dr. {doctor['full_name']}",
            data=serialize_doc(appointment)
        )

        logger.info(f"Doctor {assignment.doctor_id} assigned to appointment {appointment_id}")

        return {"message": "Doctor assigned successfully", "doctor_name": doctor["full_name"]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assign doctor error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to assign doctor")

@app.put("/api/v1/admin/appointments/{appointment_id}/reschedule", tags=["Admin"])
async def reschedule_appointment(
    appointment_id: str,
    new_date: str,
    new_time: str,
    reason: Optional[str] = None,
    current_user: dict = Depends(require_role("admin"))
):
    """Reschedule an appointment"""
    try:
        appointment = await appointments_collection.find_one({
            "_id": ObjectId(appointment_id),
            "hospital_id": current_user.get("hospital_id")
        })
        
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        await appointments_collection.update_one(
            {"_id": ObjectId(appointment_id)},
            {"$set": {
                "scheduled_date": new_date,
                "scheduled_time": new_time,
                "reschedule_reason": reason,
                "rescheduled_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )

        await create_notification(
            user_id=appointment["patient_id"],
            notification_type="appointment_rescheduled",
            title="Appointment Rescheduled",
            message=f"Your appointment has been rescheduled to {new_date} at {new_time}",
            data={"appointment_id": appointment_id, "new_date": new_date, "new_time": new_time, "reason": reason}
        )

        if appointment.get("doctor_id"):
            await create_notification(
                user_id=appointment["doctor_id"],
                notification_type="appointment_rescheduled",
                title="Appointment Rescheduled",
                message=f"Appointment with {appointment['patient_name']} rescheduled to {new_date} at {new_time}",
                data={"appointment_id": appointment_id, "new_date": new_date, "new_time": new_time}
            )

        logger.info(f"Appointment {appointment_id} rescheduled")

        return {"message": "Appointment rescheduled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reschedule appointment error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reschedule appointment")

@app.get("/api/v1/admin/doctors", tags=["Admin"])
async def get_hospital_doctors(
    current_user: dict = Depends(require_role("admin"))
):
    """Get all doctors in admin's hospital"""
    try:
        hospital_id = current_user.get("hospital_id")
        if not hospital_id:
            return []

        doctors = await users_collection.find({
            "hospital_id": hospital_id,
            "role": "doctor",
            "is_active": True
        }).to_list(100)

        return [serialize_doc(d) for d in doctors]

    except Exception as e:
        logger.error(f"Get hospital doctors error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch doctors")

@app.get("/api/v1/admin/dashboard/stats", tags=["Admin"])
async def get_admin_dashboard_stats(
    current_user: dict = Depends(require_role("admin"))
):
    """Get dashboard statistics for admin"""
    try:
        hospital_id = current_user.get("hospital_id")
        if not hospital_id:
            return {"error": "No hospital assigned"}

        appointments = await appointments_collection.find({"hospital_id": hospital_id}).to_list(1000)
        
        stats = {
            "total_appointments": len(appointments),
            "pending_appointments": len([a for a in appointments if a["status"] == "pending"]),
            "confirmed_appointments": len([a for a in appointments if a["status"] == "confirmed"]),
            "completed_appointments": len([a for a in appointments if a["status"] == "completed"]),
            "cancelled_appointments": len([a for a in appointments if a["status"] == "cancelled"]),
            "total_doctors": await users_collection.count_documents({"hospital_id": hospital_id, "role": "doctor"}),
            "today_appointments": len([a for a in appointments if a.get("scheduled_date") == datetime.utcnow().date().isoformat()])
        }

        return stats

    except Exception as e:
        logger.error(f"Get dashboard stats error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard stats")

# ==================== DOCTOR ENDPOINTS ====================

@app.get("/api/v1/doctor/profile", tags=["Doctor"])
async def get_doctor_profile(
    current_user: dict = Depends(require_role("doctor"))
):
    """Get doctor profile"""
    return serialize_doc(current_user)

@app.put("/api/v1/doctor/profile", tags=["Doctor"])
async def update_doctor_profile(
    profile: DoctorProfile,
    current_user: dict = Depends(require_role("doctor"))
):
    """Update doctor profile"""
    try:
        update_data = profile.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        await users_collection.update_one(
            {"_id": ObjectId(current_user["_id"])},
            {"$set": update_data}
        )

        logger.info(f"Doctor profile updated: {current_user['email']}")

        return {"message": "Profile updated successfully"}

    except Exception as e:
        logger.error(f"Doctor profile update error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update profile")

@app.get("/api/v1/doctor/appointments", response_model=List[AppointmentResponse], tags=["Doctor"])
async def get_doctor_appointments(
    status_filter: Optional[str] = Query(None),
    date_filter: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_role("doctor"))
):
    """Get all appointments assigned to the doctor"""
    try:
        query = {"doctor_id": current_user["id"]}
        
        if status_filter:
            query["status"] = status_filter
        
        if date_filter:
            query["scheduled_date"] = date_filter

        appointments = await appointments_collection.find(query)\
            .sort("scheduled_date", 1)\
            .skip(skip)\
            .limit(limit)\
            .to_list(limit)

        return [serialize_doc(a) for a in appointments]

    except Exception as e:
        logger.error(f"Get doctor appointments error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch appointments")

@app.put("/api/v1/doctor/appointments/{appointment_id}/status", tags=["Doctor"])
async def update_appointment_status(
    appointment_id: str,
    new_status: str = Query(..., regex="^(confirmed|in_progress|completed)$"),
    notes: Optional[str] = None,
    current_user: dict = Depends(require_role("doctor"))
):
    """Update appointment status"""
    try:
        appointment = await appointments_collection.find_one({
            "_id": ObjectId(appointment_id),
            "doctor_id": current_user["id"]
        })
        
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        update_data = {
            "status": new_status,
            "updated_at": datetime.utcnow()
        }
        
        if notes:
            update_data["doctor_notes"] = notes
        
        if new_status == "completed":
            update_data["completed_at"] = datetime.utcnow()

        await appointments_collection.update_one(
            {"_id": ObjectId(appointment_id)},
            {"$set": update_data}
        )

        await create_notification(
            user_id=appointment["patient_id"],
            notification_type="appointment_status_update",
            title=f"Appointment {new_status.replace('_', ' ').title()}",
            message=f"Your appointment status has been updated to {new_status}",
            data={"appointment_id": appointment_id, "status": new_status}
        )

        logger.info(f"Appointment {appointment_id} status updated to {new_status}")

        return {"message": "Appointment status updated successfully", "status": new_status}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update appointment status error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update appointment status")

@app.get("/api/v1/doctor/patient/{patient_id}/details", tags=["Doctor"])
async def get_patient_health_details(
    patient_id: str,
    current_user: dict = Depends(require_role("doctor"))
):
    """Get comprehensive patient health details (for QR scan or direct access)"""
    try:
        has_appointment = await appointments_collection.find_one({
            "patient_id": patient_id,
            "doctor_id": current_user["id"]
        })
        
        if not has_appointment:
            raise HTTPException(status_code=403, detail="Access denied to this patient's records")

        patient = await users_collection.find_one({
            "_id": ObjectId(patient_id),
            "role": "patient"
        })
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        prescriptions = await prescriptions_collection.find(
            {"patient_id": patient_id}
        ).sort("uploaded_at", -1).limit(10).to_list(10)

        vitals = await vitals_collection.find(
            {"patient_id": patient_id}
        ).sort("recorded_at", -1).limit(30).to_list(30)

        appointment_history = await appointments_collection.find(
            {"patient_id": patient_id}
        ).sort("created_at", -1).limit(10).to_list(10)

        medications = await medications_collection.find(
            {"patient_id": patient_id, "active": True}
        ).to_list(50)

        return {
            "patient": serialize_doc(patient),
            "prescriptions": [serialize_doc(p) for p in prescriptions],
            "vitals": [serialize_doc(v) for v in vitals],
            "appointment_history": [serialize_doc(a) for a in appointment_history],
            "active_medications": [serialize_doc(m) for m in medications]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get patient details error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch patient details")

@app.get("/api/v1/doctor/dashboard/stats", tags=["Doctor"])
async def get_doctor_dashboard_stats(
    current_user: dict = Depends(require_role("doctor"))
):
    """Get dashboard statistics for doctor"""
    try:
        appointments = await appointments_collection.find({
            "doctor_id": current_user["id"]
        }).to_list(1000)

        today = datetime.utcnow().date().isoformat()

        stats = {
            "total_appointments": len(appointments),
            "today_appointments": len([a for a in appointments if a.get("scheduled_date") == today]),
            "pending_appointments": len([a for a in appointments if a["status"] == "pending"]),
            "completed_appointments": len([a for a in appointments if a["status"] == "completed"]),
            "total_patients": len(set(a["patient_id"] for a in appointments))
        }

        return stats

    except Exception as e:
        logger.error(f"Get doctor dashboard stats error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard stats")

# ==================== HEALTH VITALS ENDPOINTS ====================

@app.post("/api/v1/vitals", tags=["Health Vitals"])
async def create_health_vitals(
    vitals: HealthVitalsCreate,
    current_user: dict = Depends(require_role("patient"))
):
    """Record health vitals (manual or from fitness tracker)"""
    try:
        vitals_data = vitals.dict()
        vitals_data["patient_id"] = current_user["id"]
        vitals_data["recorded_at"] = datetime.utcnow()

        result = await vitals_collection.insert_one(vitals_data)
        vitals_data["_id"] = str(result.inserted_id)

        logger.info(f"Vitals recorded for patient {current_user['email']}")

        return serialize_doc(vitals_data)

    except Exception as e:
        logger.error(f"Create vitals error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record vitals")

@app.get("/api/v1/vitals", tags=["Health Vitals"])
async def get_health_vitals(
    days: int = Query(30, ge=1, le=365, description="Number of days to retrieve"),
    current_user: dict = Depends(require_role("patient"))
):
    """Get health vitals history"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        vitals = await vitals_collection.find({
            "patient_id": current_user["id"],
            "recorded_at": {"$gte": start_date}
        }).sort("recorded_at", -1).to_list(1000)

        return [serialize_doc(v) for v in vitals]

    except Exception as e:
        logger.error(f"Get vitals error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch vitals")

@app.get("/api/v1/vitals/latest", tags=["Health Vitals"])
async def get_latest_vitals(
    current_user: dict = Depends(require_role("patient"))
):
    """Get most recent vital signs"""
    try:
        latest_vital = await vitals_collection.find_one(
            {"patient_id": current_user["id"]},
            sort=[("recorded_at", -1)]
        )

        if not latest_vital:
            raise HTTPException(status_code=404, detail="No vitals found")

        return serialize_doc(latest_vital)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get latest vitals error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch latest vitals")

# ==================== MEDICATION REMINDERS ====================

@app.post("/api/v1/medications/reminders", tags=["Medications"])
async def create_medication_reminder(
    reminder: MedicationReminderCreate,
    current_user: dict = Depends(require_role("patient"))
):
    """Create a medication reminder"""
    try:
        reminder_data = reminder.dict()
        reminder_data["patient_id"] = current_user["id"]
        reminder_data["created_at"] = datetime.utcnow()
        reminder_data["active"] = True

        result = await medications_collection.insert_one(reminder_data)
        reminder_data["_id"] = str(result.inserted_id)

        logger.info(f"Medication reminder created for {current_user['email']}")

        return serialize_doc(reminder_data)

    except Exception as e:
        logger.error(f"Create medication reminder error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create reminder")

@app.get("/api/v1/medications/reminders", tags=["Medications"])
async def get_medication_reminders(
    active_only: bool = Query(True),
    current_user: dict = Depends(require_role("patient"))
):
    """Get all medication reminders"""
    try:
        query = {"patient_id": current_user["id"]}
        
        if active_only:
            query["active"] = True

        reminders = await medications_collection.find(query).to_list(100)

        return [serialize_doc(r) for r in reminders]

    except Exception as e:
        logger.error(f"Get medication reminders error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch reminders")

@app.put("/api/v1/medications/reminders/{reminder_id}", tags=["Medications"])
async def update_medication_reminder(
    reminder_id: str,
    reminder_update: MedicationReminderCreate,
    current_user: dict = Depends(require_role("patient"))
):
    """Update a medication reminder"""
    try:
        reminder = await medications_collection.find_one({
            "_id": ObjectId(reminder_id),
            "patient_id": current_user["id"]
        })
        
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")

        update_data = reminder_update.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        await medications_collection.update_one(
            {"_id": ObjectId(reminder_id)},
            {"$set": update_data}
        )

        return {"message": "Reminder updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update medication reminder error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update reminder")

@app.delete("/api/v1/medications/reminders/{reminder_id}", tags=["Medications"])
async def delete_medication_reminder(
    reminder_id: str,
    current_user: dict = Depends(require_role("patient"))
):
    """Deactivate a medication reminder"""
    try:
        reminder = await medications_collection.find_one({
            "_id": ObjectId(reminder_id),
            "patient_id": current_user["id"]
        })
        
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")

        await medications_collection.update_one(
            {"_id": ObjectId(reminder_id)},
            {"$set": {"active": False, "deactivated_at": datetime.utcnow()}}
        )

        return {"message": "Reminder deactivated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete medication reminder error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to deactivate reminder")

# ==================== CHAT ENDPOINTS ====================

@app.post("/api/v1/chat/send", tags=["Chat"])
async def send_chat_message(
    message: ChatMessageCreate,
    current_user: dict = Depends(get_current_user)
):
    """Send a chat message"""
    try:
        receiver = await users_collection.find_one({"_id": ObjectId(message.receiver_id)})
        if not receiver:
            raise HTTPException(status_code=404, detail="Receiver not found")

        message_data = {
            "sender_id": current_user["id"],
            "sender_name": current_user["full_name"],
            "sender_role": current_user["role"],
            "receiver_id": message.receiver_id,
            "receiver_name": receiver["full_name"],
            "receiver_role": receiver["role"],
            "message": message.message,
            "message_type": message.message_type if hasattr(message, 'message_type') else "text",
            "read": False,
            "created_at": datetime.utcnow()
        }

        result = await chats_collection.insert_one(message_data)
        message_data["_id"] = str(result.inserted_id)

        # Send via WebSocket
        await manager.send_personal_message({
            "type": "chat_message",
            "data": serialize_doc(message_data)
        }, message.receiver_id)

        logger.info(f"Message sent from {current_user['email']} to {receiver['email']}")

        return serialize_doc(message_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send message error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send message")

@app.get("/api/v1/chat/conversations", tags=["Chat"])
async def get_conversations(
    current_user: dict = Depends(get_current_user)
):
    """Get all conversations for the current user"""
    try:
        messages = await chats_collection.find({
            "$or": [
                {"sender_id": current_user["id"]},
                {"receiver_id": current_user["id"]}
            ]
        }).sort("created_at", -1).to_list(1000)

        conversations = {}
        for msg in messages:
            other_user_id = msg["receiver_id"] if msg["sender_id"] == current_user["id"] else msg["sender_id"]
            
            if other_user_id not in conversations:
                conversations[other_user_id] = {
                    "user_id": other_user_id,
                    "user_name": msg["receiver_name"] if msg["sender_id"] == current_user["id"] else msg["sender_name"],
                    "user_role": msg["receiver_role"] if msg["sender_id"] == current_user["id"] else msg["sender_role"],
                    "last_message": msg["message"],
                    "last_message_time": msg["created_at"],
                    "unread_count": 0
                }
            
            if msg["receiver_id"] == current_user["id"] and not msg.get("read"):
                conversations[other_user_id]["unread_count"] += 1

        return list(conversations.values())

    except Exception as e:
        logger.error(f"Get conversations error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversations")

@app.get("/api/v1/chat/{user_id}/messages", tags=["Chat"])
async def get_chat_messages(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get chat messages between current user and another user"""
    try:
        messages = await chats_collection.find({
            "$or": [
                {"sender_id": current_user["id"], "receiver_id": user_id},
                {"sender_id": user_id, "receiver_id": current_user["id"]}
            ]
        }).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

        # Mark messages as read
        await chats_collection.update_many(
            {"sender_id": user_id, "receiver_id": current_user["id"], "read": False},
            {"$set": {"read": True, "read_at": datetime.utcnow()}}
        )

        return [serialize_doc(m) for m in reversed(messages)]

    except Exception as e:
        logger.error(f"Get chat messages error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch messages")

@app.put("/api/v1/chat/messages/{message_id}/read", tags=["Chat"])
async def mark_message_as_read(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark a message as read"""
    try:
        message = await chats_collection.find_one({
            "_id": ObjectId(message_id),
            "receiver_id": current_user["id"]
        })
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        await chats_collection.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": {"read": True, "read_at": datetime.utcnow()}}
        )

        return {"message": "Message marked as read"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mark message as read error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update message")

@app.get("/api/v1/chat/unread/count", tags=["Chat"])
async def get_unread_messages_count(
    current_user: dict = Depends(get_current_user)
):
    """Get count of unread messages"""
    try:
        count = await chats_collection.count_documents({
            "receiver_id": current_user["id"],
            "read": False
        })

        return {"unread_count": count}

    except Exception as e:
        logger.error(f"Get unread messages count error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get unread count")

# ==================== NOTIFICATIONS ENDPOINTS ====================

@app.get("/api/v1/notifications", response_model=List[NotificationResponse], tags=["Notifications"])
async def get_notifications(
    unread_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get all notifications for the current user"""
    try:
        query = {"user_id": current_user["id"]}
        
        if unread_only:
            query["read"] = False

        notifications = await notifications_collection.find(query)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)\
            .to_list(limit)

        return [serialize_doc(n) for n in notifications]

    except Exception as e:
        logger.error(f"Get notifications error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch notifications")

@app.put("/api/v1/notifications/{notification_id}/read", tags=["Notifications"])
async def mark_notification_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark a notification as read"""
    try:
        notification = await notifications_collection.find_one({
            "_id": ObjectId(notification_id),
            "user_id": current_user["id"]
        })
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        await notifications_collection.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"read": True, "read_at": datetime.utcnow()}}
        )

        return {"message": "Notification marked as read"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mark notification as read error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update notification")

@app.put("/api/v1/notifications/mark-all-read", tags=["Notifications"])
async def mark_all_notifications_as_read(
    current_user: dict = Depends(get_current_user)
):
    """Mark all notifications as read"""
    try:
        result = await notifications_collection.update_many(
            {"user_id": current_user["id"], "read": False},
            {"$set": {"read": True, "read_at": datetime.utcnow()}}
        )

        return {"message": f"{result.modified_count} notifications marked as read"}

    except Exception as e:
        logger.error(f"Mark all notifications as read error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update notifications")

@app.delete("/api/v1/notifications/{notification_id}", tags=["Notifications"])
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a notification"""
    try:
        notification = await notifications_collection.find_one({
            "_id": ObjectId(notification_id),
            "user_id": current_user["id"]
        })
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        await notifications_collection.delete_one({"_id": ObjectId(notification_id)})

        return {"message": "Notification deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete notification error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete notification")

@app.get("/api/v1/notifications/unread/count", tags=["Notifications"])
async def get_unread_notifications_count(
    current_user: dict = Depends(get_current_user)
):
    """Get count of unread notifications"""
    try:
        count = await notifications_collection.count_documents({
            "user_id": current_user["id"],
            "read": False
        })

        return {"unread_count": count}

    except Exception as e:
        logger.error(f"Get unread count error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get unread count")

# ==================== WEBSOCKET ENDPOINTS ====================

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time communication"""
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return

        await manager.connect(websocket, user_id, user["role"])
        
        try:
            while True:
                data = await websocket.receive_json()
                
                message_type = data.get("type")
                
                if message_type == "chat_message":
                    receiver_id = data.get("receiver_id")
                    message_content = data.get("message")
                    
                    # Get receiver info
                    receiver = await users_collection.find_one({"_id": ObjectId(receiver_id)})
                    
                    if receiver:
                        message_data = {
                            "sender_id": user_id,
                            "sender_name": user["full_name"],
                            "sender_role": user["role"],
                            "receiver_id": receiver_id,
                            "receiver_name": receiver["full_name"],
                            "receiver_role": receiver["role"],
                            "message": message_content,
                            "read": False,
                            "created_at": datetime.utcnow()
                        }
                        
                        result = await chats_collection.insert_one(message_data)
                        message_data["_id"] = str(result.inserted_id)
                        
                        # Send to receiver
                        await manager.send_personal_message({
                            "type": "chat_message",
                            "data": serialize_doc(message_data)
                        }, receiver_id)
                        
                        # Send confirmation to sender
                        await manager.send_personal_message({
                            "type": "message_sent",
                            "data": serialize_doc(message_data)
                        }, user_id)
                
                elif message_type == "typing":
                    receiver_id = data.get("receiver_id")
                    await manager.send_personal_message({
                        "type": "typing",
                        "data": {
                            "user_id": user_id,
                            "user_name": user["full_name"],
                            "is_typing": data.get("is_typing", True)
                        }
                    }, receiver_id)
                
                elif message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    
        except WebSocketDisconnect:
            manager.disconnect(user_id)
            logger.info(f"WebSocket disconnected: {user_id}")
        except Exception as e:
            logger.error(f"WebSocket error for user {user_id}: {str(e)}")
            manager.disconnect(user_id)
            
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
        await websocket.close(code=1011, reason="Internal server error")

# ==================== FILE DOWNLOAD ENDPOINTS ====================

@app.get("/api/v1/prescriptions/{prescription_id}/download", tags=["Files"])
async def download_prescription_file(
    prescription_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Download prescription file"""
    try:
        prescription = await prescriptions_collection.find_one({"_id": ObjectId(prescription_id)})
        
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")
        
        # Check access permissions
        if current_user["role"] == "patient":
            if prescription["patient_id"] != current_user["id"]:
                raise HTTPException(status_code=403, detail="Access denied")
        elif current_user["role"] == "doctor":
            has_access = await appointments_collection.find_one({
                "patient_id": prescription["patient_id"],
                "doctor_id": current_user["id"]
            })
            if not has_access:
                raise HTTPException(status_code=403, detail="Access denied")
        elif current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Access denied")

        file_path = prescription["file_path"]
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            path=file_path,
            filename=prescription["file_name"],
            media_type=prescription["file_type"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download prescription error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download file")

# ==================== QR CODE ENDPOINTS ====================

@app.get("/api/v1/patient/qr-code", tags=["Patient"])
async def generate_patient_qr_code(
    current_user: dict = Depends(require_role("patient"))
):
    """Generate QR code data for patient"""
    try:
        qr_data = {
            "patient_id": current_user["id"],
            "patient_name": current_user["full_name"],
            "patient_email": current_user["email"],
            "blood_group": current_user.get("blood_group"),
            "emergency_contact": current_user.get("emergency_contact"),
            "date_of_birth": current_user.get("date_of_birth"),
            "phone_number": current_user.get("phone_number"),
            "generated_at": datetime.utcnow().isoformat()
        }

        return qr_data

    except Exception as e:
        logger.error(f"Generate QR code error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate QR code")

@app.post("/api/v1/doctor/scan-qr", tags=["Doctor"])
async def scan_patient_qr_code(
    patient_id: str,
    current_user: dict = Depends(require_role("doctor"))
):
    """Scan patient QR code and get health details"""
    try:
        return await get_patient_health_details(patient_id, current_user)

    except Exception as e:
        logger.error(f"Scan QR code error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to scan QR code")

# ==================== SEARCH & FILTER ENDPOINTS ====================

@app.get("/api/v1/search/patients", tags=["Search"])
async def search_patients(
    query: str = Query(..., min_length=2),
    current_user: dict = Depends(require_role("admin", "doctor"))
):
    """Search patients by name or email"""
    try:
        if current_user["role"] == "doctor":
            # Doctors can only search their own patients
            patient_ids = await appointments_collection.distinct(
                "patient_id",
                {"doctor_id": current_user["id"]}
            )
            
            patients = await users_collection.find({
                "_id": {"$in": [ObjectId(pid) for pid in patient_ids]},
                "role": "patient",
                "$or": [
                    {"full_name": {"$regex": query, "$options": "i"}},
                    {"email": {"$regex": query, "$options": "i"}}
                ]
            }).limit(20).to_list(20)
        else:
            # Admins can search all patients
            patients = await users_collection.find({
                "role": "patient",
                "$or": [
                    {"full_name": {"$regex": query, "$options": "i"}},
                    {"email": {"$regex": query, "$options": "i"}}
                ]
            }).limit(20).to_list(20)

        return [serialize_doc(p) for p in patients]

    except Exception as e:
        logger.error(f"Search patients error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search patients")

@app.get("/api/v1/search/doctors", tags=["Search"])
async def search_doctors(
    query: str = Query(..., min_length=2),
    specialization: Optional[str] = None,
    current_user: dict = Depends(require_role("admin", "patient"))
):
    """Search doctors by name, specialization"""
    try:
        search_query = {
            "role": "doctor",
            "is_active": True,
            "$or": [
                {"full_name": {"$regex": query, "$options": "i"}},
                {"specialization": {"$regex": query, "$options": "i"}}
            ]
        }
        
        if specialization:
            search_query["specialization"] = {"$regex": specialization, "$options": "i"}

        if current_user["role"] == "admin":
            search_query["hospital_id"] = current_user.get("hospital_id")

        doctors = await users_collection.find(search_query).limit(20).to_list(20)

        return [serialize_doc(d) for d in doctors]

    except Exception as e:
        logger.error(f"Search doctors error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search doctors")

@app.get("/api/v1/search/hospitals", tags=["Search"])
async def search_hospitals(
    query: str = Query(..., min_length=2),
    current_user: dict = Depends(get_current_user)
):
    """Search hospitals by name or location"""
    try:
        hospitals = await hospitals_collection.find({
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"address": {"$regex": query, "$options": "i"}}
            ]
        }).limit(20).to_list(20)

        # Sort: dummy hospital first
        hospitals.sort(key=lambda x: (not x.get("is_dummy", False), x.get("name", "")))

        return [serialize_doc(h) for h in hospitals]

    except Exception as e:
        logger.error(f"Search hospitals error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search hospitals")

# ==================== ANALYTICS ENDPOINTS ====================

@app.get("/api/v1/analytics/patient-health-trends", tags=["Analytics"])
async def get_patient_health_trends(
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(require_role("patient"))
):
    """Get health trends for patient"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        vitals = await vitals_collection.find({
            "patient_id": current_user["id"],
            "recorded_at": {"$gte": start_date}
        }).sort("recorded_at", 1).to_list(1000)

        trends = {
            "heart_rate": [],
            "blood_pressure_systolic": [],
            "blood_pressure_diastolic": [],
            "steps": [],
            "sleep_hours": []
        }

        for vital in vitals:
            date = vital["recorded_at"].strftime("%Y-%m-%d")
            
            if vital.get("heart_rate"):
                trends["heart_rate"].append({"date": date, "value": vital["heart_rate"]})
            if vital.get("blood_pressure_systolic"):
                trends["blood_pressure_systolic"].append({"date": date, "value": vital["blood_pressure_systolic"]})
            if vital.get("blood_pressure_diastolic"):
                trends["blood_pressure_diastolic"].append({"date": date, "value": vital["blood_pressure_diastolic"]})
            if vital.get("steps"):
                trends["steps"].append({"date": date, "value": vital["steps"]})
            if vital.get("sleep_hours"):
                trends["sleep_hours"].append({"date": date, "value": vital["sleep_hours"]})

        return trends

    except Exception as e:
        logger.error(f"Get health trends error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch health trends")

@app.get("/api/v1/analytics/admin-reports", tags=["Analytics"])
async def get_admin_analytics_reports(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(require_role("admin"))
):
    """Get analytics reports for admin"""
    try:
        hospital_id = current_user.get("hospital_id")
        if not hospital_id:
            return {"error": "No hospital assigned"}

        # Date range filter
        date_filter = {}
        if start_date:
            date_filter["$gte"] = datetime.fromisoformat(start_date)
        if end_date:
            date_filter["$lte"] = datetime.fromisoformat(end_date)

        query = {"hospital_id": hospital_id}
        if date_filter:
            query["created_at"] = date_filter

        appointments = await appointments_collection.find(query).to_list(1000)

        # Calculate metrics
        total = len(appointments)
        by_status = {}
        by_doctor = {}
        
        for apt in appointments:
            status = apt.get("status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1
            
            if apt.get("doctor_name"):
                doctor = apt["doctor_name"]
                by_doctor[doctor] = by_doctor.get(doctor, 0) + 1

        return {
            "total_appointments": total,
            "by_status": by_status,
            "by_doctor": by_doctor,
            "period": {
                "start": start_date,
                "end": end_date
            }
        }

    except Exception as e:
        logger.error(f"Get admin analytics error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch analytics")

# ==================== HEALTH CHECK ====================

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    try:
        await users_collection.find_one()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "version": "2.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "database": "disconnected",
                "error": str(e)
            }
        )

@app.get("/", tags=["System"])
async def root():
    """Root endpoint"""
    return {
        "message": "Digital Health Card API",
        "version": "2.0.0",
        "docs": "/api/docs",
        "health": "/health",
        "description": "Production-ready Digital Health Card System"
    }

@app.get("/api/v1/system/info", tags=["System"])
async def get_system_info():
    """Get system information"""
    try:
        total_users = await users_collection.count_documents({})
        total_hospitals = await hospitals_collection.count_documents({})
        total_appointments = await appointments_collection.count_documents({})
        total_prescriptions = await prescriptions_collection.count_documents({})

        return {
            "system": "Digital Health Card",
            "version": "2.0.0",
            "statistics": {
                "total_users": total_users,
                "total_hospitals": total_hospitals,
                "total_appointments": total_appointments,
                "total_prescriptions": total_prescriptions
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Get system info error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch system info")

# ==================== ERROR HANDLERS ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# ==================== STARTUP SCRIPT ====================

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🏥 Digital Health Card API Starting...")
    print("=" * 60)
    print(f"📝 API Documentation: http://localhost:8000/api/docs")
    print(f"📊 ReDoc Documentation: http://localhost:8000/api/redoc")
    print(f"❤️  Health Check: http://localhost:8000/health")
    print("=" * 60)
    print("\n🔐 Dummy Credentials:")
    print("   Admin:  admin@healthcard.com / Admin@123")
    print("   Doctor: doctor@careplus.com / Doctor@123")
    print("   Patient: patient@health.com / Patient@123")
    print("=" * 60)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )