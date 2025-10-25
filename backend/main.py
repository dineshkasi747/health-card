"""
Enhanced FastAPI Application - Digital Health Card System
With AI-powered prescription analysis, smart chat, hospital finder, and Fitbit integration
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
import uuid
from io import BytesIO
import json
import re

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
import google.generativeai as genai
import requests

# Import from your existing files
from config import settings
from models import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
mongo_client: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None
security = HTTPBearer()

# Configure Gemini AI
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-pro')
else:
    gemini_model = None
    logger.warning("Gemini API key not configured")

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
        await db.audit_logs.create_index("created_at", expireAfterSeconds=7776000)
        await db.prescriptions.create_index([("patient_id", 1), ("uploaded_at", -1)])
        
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
    description="AI-powered digital health with prescription analysis, smart chat, and integrations",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# UTILITIES
# ============================================================================

def hash_password(password: str) -> str:
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

# ============================================================================
# AI HELPER FUNCTIONS
# ============================================================================

async def extract_text_from_image(image: Image.Image) -> str:
    """Extract text from image using OCR"""
    try:
        # Preprocess image for better OCR
        image = image.convert('L')  # Convert to grayscale
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return ""

async def analyze_prescription_with_ai(extracted_text: str) -> Dict[str, Any]:
    """Analyze prescription text using Gemini AI"""
    if not gemini_model:
        return {
            "summary": "AI analysis unavailable - API key not configured",
            "medications": [],
            "dosages": [],
            "instructions": [],
            "warnings": []
        }
    
    try:
        prompt = f"""
        Analyze this prescription text and extract structured information:
        
        {extracted_text}
        
        Provide a JSON response with:
        1. summary: Brief summary of the prescription
        2. medications: List of medication names
        3. dosages: List of dosage information
        4. frequency: How often to take each medication
        5. instructions: Special instructions
        6. warnings: Any warnings or precautions
        7. duration: Treatment duration if mentioned
        
        Return ONLY valid JSON, no additional text.
        """
        
        response = gemini_model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Clean up response to get valid JSON
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        
        result = json.loads(result_text.strip())
        return result
        
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        # Fallback to basic parsing
        return parse_prescription_basic(extracted_text)

def parse_prescription_basic(text: str) -> Dict[str, Any]:
    """Basic prescription parsing without AI"""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    medications = []
    dosages = []
    
    # Common medication patterns
    med_pattern = r'(?:Tab|Cap|Syrup|Inj)\.?\s+([A-Za-z]+)'
    dosage_pattern = r'(\d+\s*(?:mg|ml|g))'
    
    for line in lines:
        med_match = re.search(med_pattern, line, re.IGNORECASE)
        if med_match:
            medications.append(med_match.group(1))
        
        dose_match = re.search(dosage_pattern, line, re.IGNORECASE)
        if dose_match:
            dosages.append(dose_match.group(1))
    
    return {
        "summary": "Prescription contains medications as extracted",
        "medications": medications,
        "dosages": dosages,
        "frequency": [],
        "instructions": [],
        "warnings": ["Please consult your doctor for proper usage"],
        "duration": "As prescribed"
    }

async def chat_with_ai(message: str, conversation_history: List[Dict] = None) -> str:
    """Chat with AI assistant about health queries"""
    if not gemini_model:
        return "AI chat is currently unavailable. Please try again later."
    
    try:
        # Build context from conversation history
        context = ""
        if conversation_history:
            for msg in conversation_history[-5:]:  # Last 5 messages
                context += f"User: {msg.get('message', '')}\nAssistant: {msg.get('response', '')}\n\n"
        
        prompt = f"""
        You are a helpful health assistant. Provide accurate health information while being empathetic.
        Always remind users to consult healthcare professionals for medical advice.
        Never diagnose conditions or prescribe treatments.
        
        Previous conversation:
        {context}
        
        User's question: {message}
        
        Provide a helpful, concise response (max 200 words):
        """
        
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        return "I'm having trouble processing your request. Please try rephrasing your question."

# ============================================================================
# WEBSOCKET MANAGER
# ============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

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

    async def send_personal_message(self, user_id: str, message: dict):
        for websocket in self.active_connections.get(user_id, []):
            try:
                await websocket.send_json(message)
            except Exception:
                logger.warning(f"Failed to send message to {user_id}")

ws_manager = ConnectionManager()

# ============================================================================
# AUTH ROUTES (Keeping existing auth logic)
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
        qr_url = f"{settings.BASE_URL}/emergency/{qr_token}"
        
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

    user_id_str = str(user["_id"])
    access_token = create_access_token({"sub": user_id_str, "role": user["role"]})
    refresh_token = create_refresh_token({"sub": user_id_str})

    user_response = serialize_doc(user)
    user_response.pop("password_hash", None)

    await log_audit(user["_id"], "user_login", "user", user["_id"])

    return {
        "status": "success",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user_response
        },
        "message": "Login successful"
    }

# ============================================================================
# ENHANCED PRESCRIPTION ENDPOINTS
# ============================================================================

@app.post("/prescriptions/upload", response_model=StandardResponse)
async def upload_and_analyze_prescription(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("patient"))
):
    """Upload prescription image, extract text with OCR, and analyze with AI"""
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only image files (JPEG, PNG) are supported")
    
    # Read and validate file size
    contents = await file.read()
    max_size = 10 * 1024 * 1024  # 10MB
    if len(contents) > max_size:
        raise HTTPException(status_code=400, detail="File too large. Maximum 10MB allowed")
    
    try:
        # Open image
        image = Image.open(BytesIO(contents))
        
        # Extract text using OCR
        logger.info("Extracting text from prescription image...")
        extracted_text = await extract_text_from_image(image)
        
        if not extracted_text:
            raise HTTPException(status_code=400, detail="No text could be extracted from the image")
        
        # Analyze with AI
        logger.info("Analyzing prescription with AI...")
        ai_analysis = await analyze_prescription_with_ai(extracted_text)
        
        # Upload to Cloudinary
        file_data = BytesIO(contents)
        upload_result = cloudinary.uploader.upload(
            file_data,
            folder="prescriptions",
            resource_type="image"
        )
        
        # Get patient
        patient = await db.patients.find_one({"user_id": current_user["_id"]})
        
        # Save prescription to database
        prescription_doc = {
            "patient_id": patient["_id"],
            "filename": file.filename,
            "url": upload_result["secure_url"],
            "public_id": upload_result["public_id"],
            "content_type": file.content_type,
            "size_bytes": len(contents),
            "extracted_text": extracted_text,
            "ai_analysis": ai_analysis,
            "uploaded_at": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }
        
        result = await db.prescriptions.insert_one(prescription_doc)
        
        # Also add to patient's prescriptions array for backward compatibility
        await db.patients.update_one(
            {"_id": patient["_id"]},
            {
                "$push": {
                    "prescriptions": {
                        "url": upload_result["secure_url"],
                        "public_id": upload_result["public_id"],
                        "uploaded_at": datetime.utcnow(),
                        "filename": file.filename,
                        "content_type": file.content_type
                    }
                },
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        # Log audit
        await log_audit(current_user["_id"], "prescription_uploaded", "prescription", result.inserted_id)
        
        # Notify assigned doctor
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
        
        logger.info(f"✅ Prescription analyzed and uploaded by: {current_user['email']}")
        
        return {
            "status": "success",
            "data": {
                "prescription_id": str(result.inserted_id),
                "url": upload_result["secure_url"],
                "extracted_text": extracted_text,
                "ai_analysis": ai_analysis
            },
            "message": "Prescription uploaded and analyzed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing prescription: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process prescription: {str(e)}")

@app.get("/prescriptions", response_model=StandardResponse)
async def list_prescriptions(
    current_user: dict = Depends(require_role("patient")),
    limit: int = Query(20, ge=1, le=100)
):
    """List all prescriptions for current patient"""
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    prescriptions = await db.prescriptions.find(
        {"patient_id": patient["_id"]}
    ).sort("uploaded_at", -1).limit(limit).to_list(length=limit)
    
    return {
        "status": "success",
        "data": [serialize_doc(p) for p in prescriptions],
        "message": f"Found {len(prescriptions)} prescriptions"
    }

@app.get("/prescriptions/{prescription_id}", response_model=StandardResponse)
async def get_prescription_details(
    prescription_id: str,
    current_user: dict = Depends(require_role("patient", "doctor"))
):
    """Get detailed information about a specific prescription"""
    try:
        prescription = await db.prescriptions.find_one({"_id": ObjectId(prescription_id)})
        
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")
        
        # Verify access
        if current_user["role"] == "patient":
            patient = await db.patients.find_one({"user_id": current_user["_id"]})
            if prescription["patient_id"] != patient["_id"]:
                raise HTTPException(status_code=403, detail="Access denied")
        
        return {
            "status": "success",
            "data": serialize_doc(prescription),
            "message": "Prescription retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ENHANCED AI CHAT ENDPOINTS
# ============================================================================

@app.post("/ai/chat", response_model=StandardResponse)
async def ai_health_chat(
    chat_data: ChatRequest,
    current_user: dict = Depends(require_role("patient"))
):
    """Enhanced AI health assistant with conversation context"""
    
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    session_id = chat_data.session_id or str(uuid.uuid4())
    
    # Get conversation history
    history = await db.chat_messages.find({
        "patient_id": patient["_id"],
        "session_id": session_id
    }).sort("created_at", -1).limit(10).to_list(length=10)
    
    history.reverse()  # Oldest first
    
    # Get AI response
    response_text = await chat_with_ai(chat_data.message, history)
    
    # Detect intent
    message_lower = chat_data.message.lower()
    intent = "general_inquiry"
    suggestions = []
    
    if any(word in message_lower for word in ["medication", "medicine", "drug", "pill"]):
        intent = "medication_inquiry"
        suggestions = ["View my medications", "Add medication", "Set reminder"]
    elif any(word in message_lower for word in ["symptom", "pain", "fever", "sick"]):
        intent = "symptom_check"
        suggestions = ["Book appointment", "Track symptoms", "Emergency contacts"]
    elif any(word in message_lower for word in ["appointment", "doctor", "visit"]):
        intent = "appointment_booking"
        suggestions = ["Book appointment", "View appointments", "Find doctor"]
    elif any(word in message_lower for word in ["prescription", "rx"]):
        intent = "prescription_inquiry"
        suggestions = ["Upload prescription", "View prescriptions", "Analyze prescription"]
    
    # Save chat message
    chat_doc = {
        "patient_id": patient["_id"],
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

@app.get("/ai/chat/history", response_model=StandardResponse)
async def get_chat_history(
    session_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_role("patient"))
):
    """Get chat history for a session or all sessions"""
    
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    query = {"patient_id": patient["_id"]}
    if session_id:
        query["session_id"] = session_id
    
    messages = await db.chat_messages.find(query).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    return {
        "status": "success",
        "data": [serialize_doc(msg) for msg in messages],
        "message": f"Found {len(messages)} chat messages"
    }

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """Real-time AI chat via WebSocket"""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = None
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

    await ws_manager.connect(user_id, websocket)

    try:
        while True:
            try:
                data = await websocket.receive_json()
                message = data.get("message")
                session_id = data.get("session_id", str(uuid.uuid4()))
                
                if not message:
                    continue

                # Get patient
                patient = await db.patients.find_one({"user_id": ObjectId(user_id)})
                if not patient:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return

                # Get conversation history
                history = await db.chat_messages.find({
                    "patient_id": patient["_id"],
                    "session_id": session_id
                }).sort("created_at", -1).limit(5).to_list(length=5)
                
                history.reverse()

                # Get AI response
                response_text = await chat_with_ai(message, history)

                # Save chat message
                chat_doc = {
                    "patient_id": patient["_id"],
                    "session_id": session_id,
                    "message": message,
                    "response": response_text,
                    "intent": "real_time_chat",
                    "created_at": datetime.utcnow()
                }
                await db.chat_messages.insert_one(chat_doc)

                # Send response
                await ws_manager.send_personal_message(user_id, {
                    "type": "message",
                    "session_id": session_id,
                    "message": message,
                    "response": response_text,
                    "timestamp": datetime.utcnow().isoformat()
                })

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                continue

    finally:
        if user_id:
            ws_manager.disconnect(user_id, websocket)

# ============================================================================
# HOSPITALS NEAR ME - Google Maps Integration
# ============================================================================

@app.get("/hospitals/nearby", response_model=StandardResponse)
async def find_nearby_hospitals(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius: int = Query(5000, ge=100, le=50000, description="Search radius in meters"),
    current_user: dict = Depends(get_current_user)
):
    """Find nearby hospitals using Google Places API"""
    
    if not settings.GOOGLE_MAPS_API_KEY:
        # Return mock data if API key not configured
        return {
            "status": "success",
            "data": {
                "hospitals": [
                    {
                        "name": "City General Hospital",
                        "address": "123 Main St",
                        "distance": "2.3 km",
                        "phone": "+1234567890",
                        "rating": 4.5,
                        "website": "https://cityhospital.com",
                        "emergency": True,
                        "location": {"lat": latitude + 0.01, "lng": longitude + 0.01}
                    },
                    {
                        "name": "Community Medical Center",
                        "address": "456 Oak Ave",
                        "distance": "3.7 km",
                        "phone": "+1234567891",
                        "rating": 4.2,
                        "website": "https://communitymed.com",
                        "emergency": True,
                        "location": {"lat": latitude - 0.01, "lng": longitude - 0.01}
                    }
                ],
                "user_location": {"lat": latitude, "lng": longitude},
                "note": "Demo data - Configure Google Maps API for live data"
            },
            "message": "Nearby hospitals found (demo mode)"
        }
    
    try:
        # Google Places API - Nearby Search
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{latitude},{longitude}",
            "radius": radius,
            "type": "hospital",
            "key": settings.GOOGLE_MAPS_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        hospitals = []
        
        for place in data.get("results", [])[:10]:  # Limit to 10 results
            place_id = place.get("place_id")
            
            # Get detailed information
            details_url = "https://maps.googleapis.com/maps/api/place/details/json"
            details_params = {
                "place_id": place_id,
                "fields": "name,formatted_address,formatted_phone_number,website,rating,opening_hours,geometry",
                "key": settings.GOOGLE_MAPS_API_KEY
            }
            
            details_response = requests.get(details_url, params=details_params, timeout=10)
            details_data = details_response.json().get("result", {})
            
            # Calculate distance
            place_lat = place["geometry"]["location"]["lat"]
            place_lng = place["geometry"]["location"]["lng"]
            distance = calculate_distance(latitude, longitude, place_lat, place_lng)
            
            hospital_info = {
                "place_id": place_id,
                "name": place.get("name", "Unknown Hospital"),
                "address": details_data.get("formatted_address", place.get("vicinity", "N/A")),
                "phone": details_data.get("formatted_phone_number", "N/A"),
                "website": details_data.get("website", None),
                "rating": details_data.get("rating", 0),
                "distance_km": round(distance, 2),
                "location": {
                    "lat": place_lat,
                    "lng": place_lng
                },
                "is_open": details_data.get("opening_hours", {}).get("open_now", None),
                "google_maps_url": f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            }
            
            hospitals.append(hospital_info)
        
        # Sort by distance
        hospitals.sort(key=lambda x: x["distance_km"])
        
        # Log the search
        await log_audit(
            current_user["_id"],
            "hospital_search",
            "hospital",
            details={"location": {"lat": latitude, "lng": longitude}, "count": len(hospitals)}
        )
        
        return {
            "status": "success",
            "data": {
                "hospitals": hospitals,
                "user_location": {"lat": latitude, "lng": longitude},
                "search_radius_km": radius / 1000,
                "total_found": len(hospitals)
            },
            "message": f"Found {len(hospitals)} hospitals nearby"
        }
        
    except requests.RequestException as e:
        logger.error(f"Google Maps API error: {e}")
        raise HTTPException(status_code=503, detail="Unable to fetch hospital data")
    except Exception as e:
        logger.error(f"Error finding hospitals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates in kilometers using Haversine formula"""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    
    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    distance = R * c
    return distance

@app.get("/hospitals/emergency", response_model=StandardResponse)
async def find_emergency_hospitals(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    current_user: dict = Depends(get_current_user)
):
    """Find nearby hospitals with 24/7 emergency services"""
    
    if not settings.GOOGLE_MAPS_API_KEY:
        return {
            "status": "success",
            "data": {
                "emergency_hospitals": [
                    {
                        "name": "City Emergency Hospital",
                        "address": "789 Emergency Blvd",
                        "distance": "1.5 km",
                        "phone": "911",
                        "emergency_phone": "+1234567892",
                        "rating": 4.7,
                        "always_open": True
                    }
                ]
            },
            "message": "Emergency hospitals found (demo mode)"
        }
    
    try:
        # Search specifically for emergency hospitals
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{latitude},{longitude}",
            "radius": 10000,  # 10km radius for emergencies
            "keyword": "emergency hospital",
            "key": settings.GOOGLE_MAPS_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        emergency_hospitals = []
        
        for place in data.get("results", [])[:5]:  # Top 5 emergency hospitals
            place_lat = place["geometry"]["location"]["lat"]
            place_lng = place["geometry"]["location"]["lng"]
            distance = calculate_distance(latitude, longitude, place_lat, place_lng)
            
            hospital = {
                "name": place.get("name"),
                "address": place.get("vicinity"),
                "distance_km": round(distance, 2),
                "rating": place.get("rating", 0),
                "location": {"lat": place_lat, "lng": place_lng},
                "google_maps_url": f"https://www.google.com/maps/place/?q=place_id:{place['place_id']}",
                "call_now": "tel:911"  # Emergency number
            }
            emergency_hospitals.append(hospital)
        
        emergency_hospitals.sort(key=lambda x: x["distance_km"])
        
        return {
            "status": "success",
            "data": {
                "emergency_hospitals": emergency_hospitals,
                "emergency_number": "911",
                "user_location": {"lat": latitude, "lng": longitude}
            },
            "message": "Emergency hospitals found"
        }
        
    except Exception as e:
        logger.error(f"Error finding emergency hospitals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# FITBIT INTEGRATION FOR VITALS
# ============================================================================

@app.post("/fitbit/connect", response_model=StandardResponse)
async def connect_fitbit(
    authorization_code: str,
    current_user: dict = Depends(require_role("patient"))
):
    """Connect Fitbit account using OAuth authorization code"""
    
    if not settings.FITBIT_CLIENT_ID or not settings.FITBIT_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Fitbit integration not configured")
    
    try:
        # Exchange authorization code for access token
        token_url = "https://api.fitbit.com/oauth2/token"
        
        auth = (settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET)
        data = {
            "client_id": settings.FITBIT_CLIENT_ID,
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": f"{settings.BASE_URL}/fitbit/callback"
        }
        
        response = requests.post(token_url, auth=auth, data=data, timeout=10)
        response.raise_for_status()
        token_data = response.json()
        
        # Get patient
        patient = await db.patients.find_one({"user_id": current_user["_id"]})
        
        # Save connection
        connection_doc = {
            "patient_id": patient["_id"],
            "device_type": "fitbit",
            "device_id": token_data.get("user_id"),
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600)),
            "is_active": True,
            "last_sync": None,
            "created_at": datetime.utcnow()
        }
        
        # Update or insert connection
        await db.wearable_connections.update_one(
            {"patient_id": patient["_id"], "device_type": "fitbit"},
            {"$set": connection_doc},
            upsert=True
        )
        
        await log_audit(current_user["_id"], "fitbit_connected", "wearable_connection")
        
        return {
            "status": "success",
            "data": {"connected": True, "device_type": "fitbit"},
            "message": "Fitbit connected successfully"
        }
        
    except requests.RequestException as e:
        logger.error(f"Fitbit connection error: {e}")
        raise HTTPException(status_code=400, detail="Failed to connect Fitbit")
    except Exception as e:
        logger.error(f"Error connecting Fitbit: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fitbit/sync", response_model=StandardResponse)
async def sync_fitbit_data(
    date_str: Optional[str] = Query(None, description="Date in YYYY-MM-DD format, defaults to today"),
    current_user: dict = Depends(require_role("patient"))
):
    """Sync health data from Fitbit (heart rate, steps, sleep, etc.)"""
    
    try:
        # Get patient and Fitbit connection
        patient = await db.patients.find_one({"user_id": current_user["_id"]})
        connection = await db.wearable_connections.find_one({
            "patient_id": patient["_id"],
            "device_type": "fitbit",
            "is_active": True
        })
        
        if not connection:
            raise HTTPException(status_code=404, detail="Fitbit not connected")
        
        # Check if token needs refresh
        if connection["expires_at"] < datetime.utcnow():
            connection = await refresh_fitbit_token(connection)
        
        access_token = connection["access_token"]
        sync_date = date_str or datetime.utcnow().strftime("%Y-%m-%d")
        
        headers = {"Authorization": f"Bearer {access_token}"}
        vitals_synced = 0
        
        # Fetch heart rate data
        hr_url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{sync_date}/1d.json"
        hr_response = requests.get(hr_url, headers=headers, timeout=10)
        
        if hr_response.status_code == 200:
            hr_data = hr_response.json()
            heart_rate_zones = hr_data.get("activities-heart", [])
            
            if heart_rate_zones:
                resting_hr = heart_rate_zones[0].get("value", {}).get("restingHeartRate")
                
                if resting_hr:
                    await db.vitals.insert_one({
                        "patient_id": patient["_id"],
                        "vital_type": "heart_rate",
                        "value": float(resting_hr),
                        "unit": "bpm",
                        "recorded_at": datetime.utcnow(),
                        "source": "fitbit",
                        "device_id": connection["device_id"],
                        "created_at": datetime.utcnow()
                    })
                    vitals_synced += 1
        
        # Fetch blood pressure (if available)
        bp_url = f"https://api.fitbit.com/1/user/-/bp/date/{sync_date}.json"
        bp_response = requests.get(bp_url, headers=headers, timeout=10)
        
        if bp_response.status_code == 200:
            bp_data = bp_response.json()
            bp_readings = bp_data.get("bp", [])
            
            for reading in bp_readings:
                # Systolic
                await db.vitals.insert_one({
                    "patient_id": patient["_id"],
                    "vital_type": "blood_pressure_systolic",
                    "value": float(reading.get("systolic", 0)),
                    "unit": "mmHg",
                    "recorded_at": datetime.fromisoformat(reading.get("time").replace("Z", "+00:00")),
                    "source": "fitbit",
                    "device_id": connection["device_id"],
                    "created_at": datetime.utcnow()
                })
                
                # Diastolic
                await db.vitals.insert_one({
                    "patient_id": patient["_id"],
                    "vital_type": "blood_pressure_diastolic",
                    "value": float(reading.get("diastolic", 0)),
                    "unit": "mmHg",
                    "recorded_at": datetime.fromisoformat(reading.get("time").replace("Z", "+00:00")),
                    "source": "fitbit",
                    "device_id": connection["device_id"],
                    "created_at": datetime.utcnow()
                })
                vitals_synced += 2
        
        # Fetch weight
        weight_url = f"https://api.fitbit.com/1/user/-/body/log/weight/date/{sync_date}.json"
        weight_response = requests.get(weight_url, headers=headers, timeout=10)
        
        if weight_response.status_code == 200:
            weight_data = weight_response.json()
            weight_logs = weight_data.get("weight", [])
            
            for log in weight_logs:
                await db.vitals.insert_one({
                    "patient_id": patient["_id"],
                    "vital_type": "weight",
                    "value": float(log.get("weight", 0)),
                    "unit": "kg",
                    "recorded_at": datetime.fromisoformat(log.get("date") + "T00:00:00"),
                    "source": "fitbit",
                    "device_id": connection["device_id"],
                    "created_at": datetime.utcnow()
                })
                vitals_synced += 1
        
        # Fetch SpO2 (oxygen saturation)
        spo2_url = f"https://api.fitbit.com/1/user/-/spo2/date/{sync_date}.json"
        spo2_response = requests.get(spo2_url, headers=headers, timeout=10)
        
        if spo2_response.status_code == 200:
            spo2_data = spo2_response.json()
            if "value" in spo2_data:
                await db.vitals.insert_one({
                    "patient_id": patient["_id"],
                    "vital_type": "oxygen_saturation",
                    "value": float(spo2_data["value"].get("avg", 0)),
                    "unit": "%",
                    "recorded_at": datetime.utcnow(),
                    "source": "fitbit",
                    "device_id": connection["device_id"],
                    "created_at": datetime.utcnow()
                })
                vitals_synced += 1
        
        # Update last sync time
        await db.wearable_connections.update_one(
            {"_id": connection["_id"]},
            {"$set": {"last_sync": datetime.utcnow()}}
        )
        
        await log_audit(current_user["_id"], "fitbit_sync", "vitals", details={"vitals_count": vitals_synced})
        
        return {
            "status": "success",
            "data": {
                "vitals_synced": vitals_synced,
                "sync_date": sync_date,
                "last_sync": datetime.utcnow().isoformat()
            },
            "message": f"Successfully synced {vitals_synced} vital signs from Fitbit"
        }
        
    except HTTPException:
        raise
    except requests.RequestException as e:
        logger.error(f"Fitbit API error: {e}")
        raise HTTPException(status_code=503, detail="Failed to sync with Fitbit")
    except Exception as e:
        logger.error(f"Error syncing Fitbit data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def refresh_fitbit_token(connection: dict) -> dict:
    """Refresh Fitbit access token"""
    try:
        token_url = "https://api.fitbit.com/oauth2/token"
        
        auth = (settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET)
        data = {
            "grant_type": "refresh_token",
            "refresh_token": connection["refresh_token"]
        }
        
        response = requests.post(token_url, auth=auth, data=data, timeout=10)
        response.raise_for_status()
        token_data = response.json()
        
        # Update connection with new tokens
        updated_connection = {
            **connection,
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
        }
        
        await db.wearable_connections.update_one(
            {"_id": connection["_id"]},
            {"$set": updated_connection}
        )
        
        return updated_connection
        
    except Exception as e:
        logger.error(f"Error refreshing Fitbit token: {e}")
        raise HTTPException(status_code=401, detail="Failed to refresh Fitbit token")

@app.get("/fitbit/status", response_model=StandardResponse)
async def get_fitbit_status(
    current_user: dict = Depends(require_role("patient"))
):
    """Check Fitbit connection status"""
    
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    connection = await db.wearable_connections.find_one({
        "patient_id": patient["_id"],
        "device_type": "fitbit"
    })
    
    if not connection:
        return {
            "status": "success",
            "data": {
                "connected": False,
                "message": "Fitbit not connected"
            },
            "message": "Fitbit status retrieved"
        }
    
    return {
        "status": "success",
        "data": {
            "connected": connection.get("is_active", False),
            "last_sync": connection.get("last_sync"),
            "device_id": connection.get("device_id"),
            "expires_at": connection.get("expires_at")
        },
        "message": "Fitbit status retrieved"
    }

@app.delete("/fitbit/disconnect", response_model=StandardResponse)
async def disconnect_fitbit(
    current_user: dict = Depends(require_role("patient"))
):
    """Disconnect Fitbit account"""
    
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    result = await db.wearable_connections.update_one(
        {"patient_id": patient["_id"], "device_type": "fitbit"},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Fitbit not connected")
    
    await log_audit(current_user["_id"], "fitbit_disconnected", "wearable_connection")
    
    return {
        "status": "success",
        "data": {"disconnected": True},
        "message": "Fitbit disconnected successfully"
    }

# ============================================================================
# ENHANCED VITALS ENDPOINTS
# ============================================================================

@app.get("/vitals/dashboard", response_model=StandardResponse)
async def get_vitals_dashboard(
    days: int = Query(7, ge=1, le=90),
    current_user: dict = Depends(require_role("patient"))
):
    """Get comprehensive vitals dashboard with trends and analytics"""
    
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Fetch all vitals for the period
    vitals = await db.vitals.find({
        "patient_id": patient["_id"],
        "recorded_at": {"$gte": start_date}
    }).sort("recorded_at", -1).to_list(length=1000)
    
    # Group by vital type
    vitals_by_type = {}
    for vital in vitals:
        vtype = vital["vital_type"]
        if vtype not in vitals_by_type:
            vitals_by_type[vtype] = []
        vitals_by_type[vtype].append(vital)
    
    # Calculate statistics for each type
    dashboard_data = {}
    
    for vtype, readings in vitals_by_type.items():
        values = [r["value"] for r in readings]
        
        if values:
            latest = readings[0]
            avg = sum(values) / len(values)
            
            dashboard_data[vtype] = {
                "latest_value": latest["value"],
                "latest_date": latest["recorded_at"],
                "average": round(avg, 2),
                "min": min(values),
                "max": max(values),
                "count": len(values),
                "unit": latest["unit"],
                "trend": calculate_trend(values),
                "readings": [serialize_doc(r) for r in readings[:10]]  # Last 10 readings
            }
    
    return {
        "status": "success",
        "data": {
            "vitals": dashboard_data,
            "period_days": days,
            "last_updated": datetime.utcnow().isoformat()
        },
        "message": "Vitals dashboard retrieved successfully"
    }

def calculate_trend(values: List[float]) -> str:
    """Calculate trend direction from values"""
    if len(values) < 2:
        return "stable"
    
    # Compare first half with second half
    mid = len(values) // 2
    first_half_avg = sum(values[:mid]) / mid
    second_half_avg = sum(values[mid:]) / (len(values) - mid)
    
    change_percent = ((second_half_avg - first_half_avg) / first_half_avg) * 100
    
    if change_percent > 10:
        return "increasing"
    elif change_percent < -10:
        return "decreasing"
    else:
        return "stable"

# ============================================================================
# KEEPING OTHER ESSENTIAL ENDPOINTS FROM ORIGINAL
# ============================================================================

@app.get("/patients/me", response_model=StandardResponse)
async def get_my_patient_info(current_user: dict = Depends(require_role("patient"))):
    patient = await db.patients.find_one({"user_id": current_user["_id"]})
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")
    
    patient_data = serialize_doc(patient)
    
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

@app.get("/appointments")
async def list_appointments(
    doctor_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    upcoming_only: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """List appointments with filters"""
    try:
        query = {}
        
        if doctor_id:
            query["doctor_id"] = ObjectId(doctor_id)
        elif current_user.get("role") == "doctor":
            doctor = await db.doctors.find_one({"user_id": ObjectId(current_user["_id"])})
            if doctor:
                query["doctor_id"] = doctor["_id"]
        
        if patient_id:
            query["patient_id"] = ObjectId(patient_id)
        elif current_user.get("role") == "patient":
            patient = await db.patients.find_one({"user_id": ObjectId(current_user["_id"])})
            if patient:
                query["patient_id"] = patient["_id"]
        
        if upcoming_only:
            query["scheduled_date"] = {"$gte": datetime.now().date().isoformat()}
        
        appointments = []
        cursor = db.appointments.find(query).sort("scheduled_date", 1)
        
        async for appointment in cursor:
            patient = await db.patients.find_one({"_id": appointment.get("patient_id")})
            patient_user = await db.users.find_one({"_id": patient["user_id"]}) if patient else None
            
            doctor = await db.doctors.find_one({"_id": appointment.get("doctor_id")})
            doctor_user = await db.users.find_one({"_id": doctor["user_id"]}) if doctor else None
            
            appointments.append({
                "id": str(appointment["_id"]),
                "patient_id": str(appointment.get("patient_id", "")),
                "patient_name": patient_user["name"] if patient_user else "Unknown",
                "doctor_id": str(appointment.get("doctor_id", "")),
                "doctor_name": doctor_user["name"] if doctor_user else "Unknown",
                "scheduled_date": appointment.get("scheduled_date", ""),
                "scheduled_time": appointment.get("scheduled_time", ""),
                "status": appointment.get("status", "scheduled"),
                "consultation_type": appointment.get("consultation_type", "in_person"),
                "reason": appointment.get("reason", "")
            })
        
        return {
            "status": "success",
            "data": appointments,
            "message": f"Found {len(appointments)} appointments"
        }
    except Exception as e:
        logger.error(f"Error listing appointments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "features": {
            "ai_prescription_analysis": gemini_model is not None,
            "google_maps": settings.GOOGLE_MAPS_API_KEY is not None,
            "fitbit_integration": settings.FITBIT_CLIENT_ID is not None
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)