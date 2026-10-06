import os
import logging
import sys
import json
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from src.database.db_manager import DatabaseManager, OutageModel
from src.models.subscription import Subscription

# 1. The Best of Both Worlds: Working sys.stdout + JSON Formatting
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "asctime": self.formatTime(record),
            "name": record.name,
            "levelname": record.levelname,
            "message": record.getMessage()
        }
        for key in ["http_method", "url_path", "status_code", "duration_seconds", "client_ip", "allowed_origins", "endpoint", "municipality", "street"]:
            if hasattr(record, key):
                log_record[key] = getattr(record, key)
        return json.dumps(log_record)

logger = logging.getLogger("OutageAPI")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())

if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(handler)

logger.info("Outage API Boot Sequence Initiated", extra={"allowed_origins": os.environ.get("FRONTEND_URL", "*")})

# 2. Initialize Database
db_manager = DatabaseManager()

# 3. Define Pydantic Schemas
class OutageResponse(BaseModel):
    id: str
    provider: str
    municipality: Optional[str]
    area: Optional[str]
    reason: Optional[str]
    date_start: Optional[datetime]
    date_end: Optional[datetime]
    time_start: Optional[str]
    time_end: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    
    @model_validator(mode='after')
    def clean_coordinates(self) -> 'OutageResponse':
        if self.lat == -999.0 or self.lng == -999.0:
            self.lat = None
            self.lng = None
        return self
    
    class Config:
        from_attributes = True

class SubscriptionRequest(BaseModel):
    street_name: str
    municipality: str
    house_number: Optional[str] = ""
    push_endpoint: str
    push_keys: dict
    is_rural: Optional[bool] = False
    notify_radius_km: Optional[float] = 5.0
    provider_preference: Optional[List[str]] = []

# 4. Initialize FastAPI App
app = FastAPI(
    title="BiH Electricity Outage API",
    description="REST API for active electricity outages in Bosnia and Herzegovina",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("FRONTEND_URL", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# SRE Structured Access Logs (Middleware)
# ==========================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    duration = (datetime.now() - start_time).total_seconds()
    
    if request.url.path != "/health":
        client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
        logger.info(
            f"API Request: {request.method} {request.url.path}",
            extra={
                "http_method": request.method,
                "url_path": request.url.path,
                "status_code": response.status_code,
                "duration_seconds": duration,
                "client_ip": client_ip
            }
        )
    return response

def get_db():
    with db_manager.Session() as session:
        yield session

# 5. API Endpoints
@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/v1/outages/active", response_model=List[OutageResponse])
def get_active_outages(db: Session = Depends(get_db)):
    today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    outages = db.query(OutageModel).filter(
        (OutageModel.date_end >= today_midnight) | (OutageModel.date_end.is_(None))
    ).all()
    return outages

@app.post("/api/v1/subscribe", status_code=201)
def create_subscription(sub_req: SubscriptionRequest):
    new_sub = Subscription(
        street_name=sub_req.street_name,
        municipality=sub_req.municipality,
        house_number=sub_req.house_number,
        push_endpoint=sub_req.push_endpoint,
        push_keys=sub_req.push_keys,
        is_rural=sub_req.is_rural,
        notify_radius_km=sub_req.notify_radius_km,
        provider_preference=sub_req.provider_preference
    )
    
    success = db_manager.save_subscription(new_sub)
    if not success:
        logger.error("Failed to save subscription", extra={"endpoint": sub_req.push_endpoint})
        raise HTTPException(status_code=500, detail="Failed to save subscription")
        
    logger.info("New Web Push Subscription Created", extra={"municipality": sub_req.municipality, "street": sub_req.street_name})
    
    return {
        "status": "success",  
        "message": "Subscription created",  
        "subscription_id": new_sub.subscription_id
    }
