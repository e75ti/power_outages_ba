from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from src.database.db_manager import DatabaseManager, OutageModel
from src.models.subscription import Subscription

# 1. Initialize Database
db_manager = DatabaseManager()

# 2. Define Pydantic Schemas (The "FastAPI" way)
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

# 3. Initialize FastAPI App
app = FastAPI(
    title="BiH Electricity Outage API",
    description="REST API for active electricity outages in Bosnia and Herzegovina",
    version="1.0.0"
)

def get_db():
    with db_manager.Session() as session:
        yield session

# 4. API Endpoints
@app.get("/health")
def health_check():
    """SRE Health Check endpoint for Docker/Kubernetes."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/v1/outages/active", response_model=List[OutageResponse])
def get_active_outages(db: Session = Depends(get_db)):
    """Returns all outages happening today or in the future."""
    today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    outages = db.query(OutageModel).filter(
        (OutageModel.date_end >= today_midnight) | (OutageModel.date_end.is_(None))
    ).all()
    return outages

@app.post("/api/v1/subscribe", status_code=201)
def create_subscription(sub_req: SubscriptionRequest):
    """Creates a new user subscription for outage alerts."""
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
        raise HTTPException(status_code=500, detail="Failed to save subscription")
        
    return {
        "status": "success", 
        "message": "Subscription created", 
        "subscription_id": new_sub.subscription_id
    }
