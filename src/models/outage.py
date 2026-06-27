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
        
        Returns:
            Unique hash string
        """
        # Create a unique key from provider, date, location, and time
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
        """
        Convert outage to dictionary for storage.
        
        Returns:
            Dictionary representation
        """
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
        """
        Create an Outage from a dictionary.
        
        Args:
            data: Dictionary with outage data
            
        Returns:
            Outage object
        """
        # Parse datetime fields
        date_start = None
        if data.get("date_start"):
            date_start = datetime.fromisoformat(data["date_start"])
        
        date_end = None
        if data.get("date_end"):
            date_end = datetime.fromisoformat(data["date_end"])
        
        created_at = datetime.now()
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        
        return cls(
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
    
    def get_full_datetime_start(self) -> Optional[datetime]:
        """
        Get the full start datetime combining date and time.
        
        Returns:
            Combined datetime or just date
        """
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
        """
        Get the full end datetime combining date and time.
        
        Returns:
            Combined datetime or None
        """
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
        """
        Check if the outage is currently active.
        
        Args:
            current_time: Time to check against (defaults to now)
            
        Returns:
            True if outage is active
        """
        if current_time is None:
            current_time = datetime.now()
        
        start = self.get_full_datetime_start()
        end = self.get_full_datetime_end()
        
        if not start:
            return False
        
        if end:
            return start <= current_time <= end
        
        # If no end time, check if it's the same day
        return start.date() == current_time.date() and current_time >= start
    
    def matches_location(self, search_term: str) -> bool:
        """
        Check if the outage matches a location search term.
        
        Args:
            search_term: Location to search for
            
        Returns:
            True if there's a match
        """
        search_lower = search_term.lower()
        
        return (
            search_lower in self.region.lower() or
            search_lower in self.municipality.lower() or
            search_lower in self.area.lower() or
            search_lower in self.streets.lower()
        )
    
    def __str__(self) -> str:
        """String representation of the outage."""
        time_str = ""
        if self.time_start and self.time_end:
            time_str = f" ({self.time_start} - {self.time_end})"
        elif self.time_start:
            time_str = f" ({self.time_start})"
        
        date_str = self.date_start.strftime("%d.%m.%Y") if self.date_start else "Unknown date"
        
        return f"[{self.provider}] {date_str}{time_str}: {self.municipality} - {self.area[:50]}"
    
    def __repr__(self) -> str:
        """Debug representation."""
        return f"Outage(id={self.outage_id}, provider={self.provider}, date={self.date_start})"