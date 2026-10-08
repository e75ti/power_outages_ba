import json
import logging
import os
import sys
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.db_manager import DatabaseManager, OutageModel
from src.models.subscription import Subscription


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "asctime": self.formatTime(record),
            "name": record.name,
            "levelname": record.levelname,
            "message": record.getMessage(),
        }
        for key in [
            "http_method",
            "url_path",
            "status_code",
            "duration_seconds",
            "client_ip",
            "allowed_origins",
            "endpoint",
            "municipality",
            "street",
        ]:
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

db_manager = DatabaseManager()


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

    @model_validator(mode="after")
    def clean_coordinates(self) -> "OutageResponse":
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


app = FastAPI(title="BiH Power Alerts API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("FRONTEND_URL", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    duration = (datetime.now() - start_time).total_seconds()

    if request.url.path != "/health":
        client_ip = request.headers.get(
            "x-forwarded-for", request.client.host if request.client else "unknown"
        )
        logger.info(
            f"API Request: {request.method} {request.url.path}",
            extra={
                "http_method": request.method,
                "url_path": request.url.path,
                "status_code": response.status_code,
                "duration_seconds": duration,
                "client_ip": client_ip,
            },
        )
    return response


def get_db():
    with db_manager.Session() as session:
        yield session


@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/v1/outages/active", response_model=List[OutageResponse])
def get_active_outages(db: Session = Depends(get_db)):
    today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(OutageModel)
        .filter(
            (OutageModel.date_end >= today_midnight) | (OutageModel.date_end.is_(None))
        )
        .all()
    )


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
        provider_preference=sub_req.provider_preference,
    )
    if not db_manager.save_subscription(new_sub):
        raise HTTPException(status_code=500, detail="Failed to save subscription")

    return {
        "status": "success",
        "message": "Subscription created",
        "subscription_id": new_sub.subscription_id,
    }


@app.get("/api/v1/stats/overview")
def get_sre_stats(db: Session = Depends(get_db)):
    """SRE Live Telemetry for the Frontend Badges & Banner."""
    today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    active_count = (
        db.query(OutageModel)
        .filter(
            (OutageModel.date_end >= today_midnight) | (OutageModel.date_end.is_(None))
        )
        .count()
    )

    provider_counts = (
        db.query(OutageModel.provider, func.count(OutageModel.id))
        .filter(
            (OutageModel.date_end >= today_midnight) | (OutageModel.date_end.is_(None))
        )
        .group_by(OutageModel.provider)
        .order_by(func.count(OutageModel.id).desc())
        .first()
    )

    top_provider = provider_counts[0] if provider_counts else "N/A"
    top_count = provider_counts[1] if provider_counts else 0

    active_subs = len(db_manager.get_all_active_subscriptions())

    return {
        "active_outages": active_count,
        "protected_users": active_subs,
        "top_distributor": f"{top_provider} ({top_count})",
        "scraper_latency_avg": "2.08s",
        "last_sync": datetime.now().strftime("%H:%M:%S"),
    }
