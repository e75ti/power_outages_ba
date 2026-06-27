"""Subscription data model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict
import hashlib


@dataclass
class Subscription:
    """Represents a user's subscription to outage notifications."""
    
    # Required fields
    street_name: str
    municipality: str
    
    # Web Push fields
    push_endpoint: str = ""
    push_keys: Dict[str, str] = field(default_factory=dict)  # p256dh, auth
    
    # Location fields
    coordinates: Optional[tuple] = None  # (latitude, longitude)
    is_rural: bool = False  # Enable area-based geo matching
    
    # Subscription settings
    notify_radius_km: float = 5.0  # For rural area matching
    is_active: bool = True
    
    # Metadata
    subscription_id: str = field(default="", init=False)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Notification tracking
    last_notified_at: Optional[datetime] = None
    notification_count: int = 0
    
    def __post_init__(self):
        """Generate unique ID after initialization."""
        self.subscription_id = self._generate_id()
    
    def _generate_id(self) -> str:
        """
        Generate a unique ID for this subscription.
        
        Returns:
            Unique hash string
        """
        key_parts = [
            self.push_endpoint,
            self.street_name.lower(),
            self.municipality.lower(),
        ]
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    def to_dict(self) -> dict:
        """
        Convert subscription to dictionary for storage.
        
        Returns:
            Dictionary representation
        """
        return {
            "subscription_id": self.subscription_id,
            "street_name": self.street_name,
            "municipality": self.municipality,
            "push_endpoint": self.push_endpoint,
            "push_keys": self.push_keys,
            "coordinates": list(self.coordinates) if self.coordinates else None,
            "is_rural": self.is_rural,
            "notify_radius_km": self.notify_radius_km,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_notified_at": self.last_notified_at.isoformat() if self.last_notified_at else None,
            "notification_count": self.notification_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Subscription":
        """
        Create a Subscription from a dictionary.
        
        Args:
            data: Dictionary with subscription data
            
        Returns:
            Subscription object
        """
        # Parse datetime fields
        created_at = datetime.now()
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        
        updated_at = datetime.now()
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"])
        
        last_notified_at = None
        if data.get("last_notified_at"):
            last_notified_at = datetime.fromisoformat(data["last_notified_at"])
        
        # Parse coordinates
        coordinates = None
        if data.get("coordinates"):
            coordinates = tuple(data["coordinates"])
        
        sub = cls(
            street_name=data.get("street_name", ""),
            municipality=data.get("municipality", ""),
            push_endpoint=data.get("push_endpoint", ""),
            push_keys=data.get("push_keys", {}),
            coordinates=coordinates,
            is_rural=data.get("is_rural", False),
            notify_radius_km=data.get("notify_radius_km", 5.0),
            is_active=data.get("is_active", True),
            created_at=created_at,
            updated_at=updated_at,
            last_notified_at=last_notified_at,
            notification_count=data.get("notification_count", 0),
        )
        
        # Override generated ID if provided
        if data.get("subscription_id"):
            sub.subscription_id = data["subscription_id"]
        
        return sub
    
    def get_normalized_street(self) -> str:
        """
        Get normalized street name for matching.
        
        Returns:
            Lowercase, stripped street name
        """
        return self.street_name.lower().strip()
    
    def get_normalized_municipality(self) -> str:
        """
        Get normalized municipality name for matching.
        
        Returns:
            Lowercase, stripped municipality name
        """
        return self.municipality.lower().strip()
    
    def record_notification(self) -> None:
        """Record that a notification was sent."""
        self.last_notified_at = datetime.now()
        self.notification_count += 1
        self.updated_at = datetime.now()
    
    def __str__(self) -> str:
        """String representation."""
        status = "🟢" if self.is_active else "🔴"
        rural = " (rural)" if self.is_rural else ""
        return f"{status} {self.street_name}, {self.municipality}{rural}"
    
    def __repr__(self) -> str:
        """Debug representation."""
        return f"Subscription(id={self.subscription_id}, street={self.street_name})"