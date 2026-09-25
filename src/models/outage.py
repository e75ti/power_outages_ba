# src/models/outage.py
"""Outage data model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib


@dataclass
class Outage:
    """Represents an electricity outage event."""
    
    # Required fields
    provider: str
    region: str
    date_start: datetime
    
    # Location fields
    municipality: str = ""
    area: str = ""
    streets: str = ""
    
    # Time fields
    date_end: Optional[datetime] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    
    # Additional info
    reason: str = ""
    facility: str = ""
    raw_text: str = ""
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    coordinates: Optional[tuple] = None  # (latitude, longitude)
    
    # Computed fields
    outage_id: str = field(default="", init=False)
    
    def __post_init__(self):
        """Generate unique ID after initialization."""
        self.outage_id = self._generate_id()
    
    def _generate_id(self) -> str:
        """
        Generate a unique ID for this outage based on key fields.
        """
        key_parts = [
            self.provider,
            self.region,
            self.date_start.strftime("%Y-%m-%d") if self.date_start else "",
            self.time_start or "",
            self.area[:50] if self.area else "",
            self.streets[:50] if self.streets else "",
        ]
        
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    def to_dict(self) -> dict:
        return {
            "outage_id": self.outage_id,
            "provider": self.provider,
            "region": self.region,
            "municipality": self.municipality,
            "area": self.area,
            "streets": self.streets,
            "date_start": self.date_start.isoformat() if self.date_start else None,
            "date_end": self.date_end.isoformat() if self.date_end else None,
            "time_start": self.time_start,
            "time_end": self.time_end,
            "reason": self.reason,
            "facility": self.facility,
            "raw_text": self.raw_text,
            "created_at": self.created_at.isoformat(),
            "coordinates": self.coordinates,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Outage":
        date_start = None
        if data.get("date_start"):
            date_start = datetime.fromisoformat(data["date_start"])
        
        date_end = None
        if data.get("date_end"):
            date_end = datetime.fromisoformat(data["date_end"])
        
        created_at = datetime.now()
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        
        obj = cls(
            provider=data.get("provider", ""),
            region=data.get("region", ""),
            municipality=data.get("municipality", ""),
            area=data.get("area", ""),
            streets=data.get("streets", ""),
            date_start=date_start,
            date_end=date_end,
            time_start=data.get("time_start"),
            time_end=data.get("time_end"),
            reason=data.get("reason", ""),
            facility=data.get("facility", ""),
            raw_text=data.get("raw_text", ""),
            created_at=created_at,
            coordinates=data.get("coordinates"),
        )
        
        # Override generated ID if loading from database
        if data.get("outage_id"):
            obj.outage_id = data["outage_id"]
            
        return obj
    
    def get_full_datetime_start(self) -> Optional[datetime]:
        if not self.date_start:
            return None
        if self.time_start:
            try:
                hour, minute = map(int, self.time_start.split(':'))
                return self.date_start.replace(hour=hour, minute=minute)
            except (ValueError, AttributeError):
                pass
        return self.date_start
    
    def get_full_datetime_end(self) -> Optional[datetime]:
        end_date = self.date_end or self.date_start
        if not end_date:
            return None
        if self.time_end:
            try:
                hour, minute = map(int, self.time_end.split(':'))
                return end_date.replace(hour=hour, minute=minute)
            except (ValueError, AttributeError):
                pass
        return None
    
    def is_active(self, current_time: Optional[datetime] = None) -> bool:
        if current_time is None:
            current_time = datetime.now()
        start = self.get_full_datetime_start()
        end = self.get_full_datetime_end()
        if not start:
            return False
        if end:
            return start <= current_time <= end
        return start.date() == current_time.date() and current_time >= start
    
    def matches_location(self, search_term: str) -> bool:
        search_lower = search_term.lower()
        return (
            search_lower in self.region.lower() or
            search_lower in self.municipality.lower() or
            search_lower in self.area.lower() or
            search_lower in self.streets.lower()
        )
    
    def __str__(self) -> str:
        time_str = ""
        if self.time_start and self.time_end:
            time_str = f" ({self.time_start} - {self.time_end})"
        elif self.time_start:
            time_str = f" ({self.time_start})"
        date_str = self.date_start.strftime("%d.%m.%Y") if self.date_start else "Unknown date"
        return f"[{self.provider}] {date_str}{time_str}: {self.municipality} - {self.area[:50]}"
    
    def __repr__(self) -> str:
        return f"Outage(id={self.outage_id}, provider={self.provider}, date={self.date_start})"
