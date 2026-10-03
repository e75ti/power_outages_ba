# src/database/db_manager.py
"""SQLAlchemy database manager (PostgreSQL / SQLite)."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, Integer, Text
from sqlalchemy.orm import sessionmaker, declarative_base

from src.models.outage import Outage
from src.models.subscription import Subscription
from src.config.settings import load_config

Base = declarative_base()

def utc_now():
    """Helper to enforce timezone-aware UTC default timestamps."""
    return datetime.now(timezone.utc)

class OutageModel(Base):
    __tablename__ = 'outages'
    id = Column(String, primary_key=True)
    provider = Column(String, nullable=False)
    region = Column(String)
    municipality = Column(String)
    area = Column(Text)
    streets = Column(Text)
    date_start = Column(DateTime(timezone=True), index=True) # Added Timezone & Index
    date_end = Column(DateTime(timezone=True), nullable=True)
    time_start = Column(String, nullable=True)
    time_end = Column(String, nullable=True)
    reason = Column(Text)
    facility = Column(String)
    raw_text = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

class SubscriptionModel(Base):
    __tablename__ = 'subscriptions'
    id = Column(String, primary_key=True)
    street_name = Column(String, nullable=False)
    house_number = Column(String, nullable=True)
    municipality = Column(String, nullable=False)
    push_endpoint = Column(String, nullable=False)
    push_keys = Column(Text) # Stored as JSON string
    is_rural = Column(Boolean, default=False)
    notify_radius_km = Column(Float, default=5.0)
    is_active = Column(Boolean, default=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    last_notified_at = Column(DateTime(timezone=True), nullable=True)
    notification_count = Column(Integer, default=0)
    provider_preference = Column(Text) # Stored as JSON string

class NotificationSentModel(Base):
    __tablename__ = 'notifications_sent'
    id = Column(String, primary_key=True) # outage_id + "_" + subscription_id
    outage_id = Column(String, nullable=False)
    subscription_id = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), default=utc_now, index=True) # Added Index
    success = Column(Boolean, default=True)

class GeocacheModel(Base):
    __tablename__ = 'geocache'
    address_hash = Column(String, primary_key=True)
    address = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    cached_at = Column(DateTime(timezone=True), default=utc_now, index=True) # Added Index


class DatabaseManager:
    """Manages all Database operations via SQLAlchemy."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = load_config()
        
        db_uri = self.config.get("DATABASE_URI", "sqlite:///outages.db")
        self.engine = create_engine(db_uri, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    # ==================== OUTAGE OPERATIONS ====================
    
    def save_outage(self, outage: Outage) -> bool:
        with self.Session() as session:
            existing = session.query(OutageModel).filter_by(id=outage.outage_id).first()
            if existing:
                return False
                
            model = self._outage_to_model(outage)
            session.add(model)
            session.commit()
            return True

    def save_outages(self, outages: List[Outage]) -> Dict[str, Any]:
        new_count = 0
        existing_count = 0
        new_objects = []
        
        with self.Session() as session:
            for outage in outages:
                existing = session.query(OutageModel).filter_by(id=outage.outage_id).first()
                if not existing:
                    model = self._outage_to_model(outage)
                    session.add(model)
                    new_count += 1
                    new_objects.append(outage)
                else:
                    existing_count += 1
                    # --- NEW FIX: Update coordinates if they were missing! ---
                    if outage.coordinates and (existing.lat is None or existing.lat == -999.0):
                        existing.lat = outage.coordinates[0]
                        existing.lng = outage.coordinates[1]
                    # ---------------------------------------------------------
            session.commit()
            
        return {"new": new_count, "existing": existing_count, "new_objects": new_objects}

    def get_outage(self, outage_id: str) -> Optional[Outage]:
        with self.Session() as session:
            model = session.query(OutageModel).filter_by(id=outage_id).first()
            return self._model_to_outage(model) if model else None

    def get_recent_outages(self, days: int = 7) -> List[Outage]:
        cutoff = utc_now() - timedelta(days=days)
        with self.Session() as session:
            models = session.query(OutageModel).filter(OutageModel.created_at >= cutoff).all()
            return [self._model_to_outage(m) for m in models]

    def get_upcoming_outages(self) -> List[Outage]:
        today = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        with self.Session() as session:
            models = session.query(OutageModel).filter(OutageModel.date_start >= today).all()
            return [self._model_to_outage(m) for m in models]

    def delete_old_outages(self, days: int = 30) -> int:
        cutoff = utc_now() - timedelta(days=days)
        with self.Session() as session:
            deleted = session.query(OutageModel).filter(OutageModel.date_start < cutoff).delete()
            session.commit()
            return deleted

    # ==================== SUBSCRIPTION OPERATIONS ====================

    def save_subscription(self, subscription: Subscription) -> bool:
        with self.Session() as session:
            existing = session.query(SubscriptionModel).filter_by(id=subscription.subscription_id).first()
            if existing:
                session.delete(existing)
            model = self._subscription_to_model(subscription)
            session.add(model)
            session.commit()
            return True

    def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        with self.Session() as session:
            model = session.query(SubscriptionModel).filter_by(id=subscription_id).first()
            return self._model_to_subscription(model) if model else None

    def get_subscriptions_by_endpoint(self, push_endpoint: str) -> List[Subscription]:
        with self.Session() as session:
            models = session.query(SubscriptionModel).filter_by(push_endpoint=push_endpoint, is_active=True).all()
            return [self._model_to_subscription(m) for m in models]

    def get_all_active_subscriptions(self) -> List[Subscription]:
        with self.Session() as session:
            models = session.query(SubscriptionModel).filter_by(is_active=True).all()
            return [self._model_to_subscription(m) for m in models]

    def delete_subscription(self, subscription_id: str) -> bool:
        with self.Session() as session:
            deleted = session.query(SubscriptionModel).filter_by(id=subscription_id).delete()
            session.commit()
            return deleted > 0

    def deactivate_subscription(self, subscription_id: str) -> bool:
        with self.Session() as session:
            sub = session.query(SubscriptionModel).filter_by(id=subscription_id).first()
            if sub:
                sub.is_active = False
                session.commit()
                return True
            return False

    # ==================== NOTIFICATION TRACKING ====================

    def is_notification_sent(self, outage_id: str, subscription_id: str) -> bool:
        notif_id = f"{outage_id}_{subscription_id}"
        with self.Session() as session:
            return session.query(NotificationSentModel).filter_by(id=notif_id).first() is not None

    def record_notification_sent(self, outage_id: str, subscription_id: str, success: bool = True) -> None:
        notif_id = f"{outage_id}_{subscription_id}"
        with self.Session() as session:
            notif = NotificationSentModel(
                id=notif_id,
                outage_id=outage_id,
                subscription_id=subscription_id,
                success=success
            )
            session.add(notif)
            session.commit()
            
    def delete_old_notifications(self, days: int = 7) -> int:
        cutoff = utc_now() - timedelta(days=days)
        with self.Session() as session:
            deleted = session.query(NotificationSentModel).filter(NotificationSentModel.sent_at < cutoff).delete()
            session.commit()
            return deleted

    # ==================== GEOCACHE OPERATIONS ====================

    def get_cached_coordinates(self, address: str) -> Optional[tuple]:
        import hashlib
        address_hash = hashlib.md5(address.lower().encode()).hexdigest()
        with self.Session() as session:
            model = session.query(GeocacheModel).filter_by(address_hash=address_hash).first()
            if model:
                return (model.latitude, model.longitude)
        return None

    def cache_coordinates(self, address: str, latitude: float, longitude: float) -> None:
        import hashlib
        address_hash = hashlib.md5(address.lower().encode()).hexdigest()
        with self.Session() as session:
            if not session.query(GeocacheModel).filter_by(address_hash=address_hash).first():
                cache = GeocacheModel(
                    address_hash=address_hash,
                    address=address,
                    latitude=latitude,
                    longitude=longitude
                )
                session.add(cache)
                session.commit()
                
    def delete_old_geocache(self, days: int = 90) -> int:
        cutoff = utc_now() - timedelta(days=days)
        with self.Session() as session:
            deleted = session.query(GeocacheModel).filter(GeocacheModel.cached_at < cutoff).delete()
            session.commit()
            return deleted

    # ==================== HELPERS ====================

    def _outage_to_model(self, outage: Outage) -> OutageModel:
        return OutageModel(
            id=outage.outage_id,
            provider=outage.provider,
            region=outage.region,
            municipality=outage.municipality,
            area=outage.area,
            streets=outage.streets,
            date_start=outage.date_start,
            date_end=outage.date_end or outage.date_start,
            time_start=outage.time_start,
            time_end=outage.time_end,
            reason=outage.reason,
            facility=outage.facility,
            raw_text=outage.raw_text,
            created_at=outage.created_at,
            lat=outage.coordinates[0] if outage.coordinates else None,
            lng=outage.coordinates[1] if outage.coordinates else None,
        )

    def _model_to_outage(self, model: OutageModel) -> Outage:
        data = {
            "outage_id": model.id,
            "provider": model.provider,
            "region": model.region,
            "municipality": model.municipality,
            "area": model.area,
            "streets": model.streets,
            "date_start": model.date_start.isoformat() if model.date_start else None,
            "date_end": model.date_end.isoformat() if model.date_end else None,
            "time_start": model.time_start,
            "time_end": model.time_end,
            "reason": model.reason,
            "facility": model.facility,
            "raw_text": model.raw_text,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "coordinates": (model.lat, model.lng) if model.lat and model.lng else None,
        }
        return Outage.from_dict(data)

    def _subscription_to_model(self, sub: Subscription) -> SubscriptionModel:
        return SubscriptionModel(
            id=sub.subscription_id,
            street_name=sub.street_name,
            house_number=sub.house_number,
            municipality=sub.municipality,
            push_endpoint=sub.push_endpoint,
            push_keys=json.dumps(sub.push_keys),
            is_rural=sub.is_rural,
            notify_radius_km=sub.notify_radius_km,
            is_active=sub.is_active,
            lat=sub.coordinates[0] if sub.coordinates else None,
            lng=sub.coordinates[1] if sub.coordinates else None,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
            last_notified_at=sub.last_notified_at,
            notification_count=sub.notification_count,
            provider_preference=json.dumps(sub.provider_preference)
        )

    def _model_to_subscription(self, model: SubscriptionModel) -> Subscription:
        data = {
            "subscription_id": model.id,
            "street_name": model.street_name,
            "house_number": model.house_number,
            "municipality": model.municipality,
            "push_endpoint": model.push_endpoint,
            "push_keys": json.loads(model.push_keys) if model.push_keys else {},
            "coordinates": (model.lat, model.lng) if model.lat and model.lng else None,
            "is_rural": model.is_rural,
            "notify_radius_km": model.notify_radius_km,
            "is_active": model.is_active,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
            "last_notified_at": model.last_notified_at.isoformat() if model.last_notified_at else None,
            "notification_count": model.notification_count,
            "provider_preference": json.loads(model.provider_preference) if model.provider_preference else [],
        }
        return Subscription.from_dict(data)
