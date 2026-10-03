from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from src.database.db_manager import DatabaseManager, OutageModel

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
    lat: Optional[float]
    lng: Optional[float]
    
    # SRE Data Cleaning: Intercept negative cache and turn to NULL for the API
    @model_validator(mode='after')
    def clean_coordinates(self) -> 'OutageResponse':
        if self.lat == -999.0 or self.lng == -999.0:
            self.lat = None
            self.lng = None
        return self
    
    class Config:
        from_attributes = True

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
    now = datetime.now()
    # Robust querying: include future outages OR outages with unknown end times
    outages = db.query(OutageModel).filter(
        (OutageModel.date_end >= now) | (OutageModel.date_end.is_(None))
    ).all()
    return outages
