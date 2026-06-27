"""Firebase Firestore database manager."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import firebase_admin
from firebase_admin import credentials, firestore

from src.models.outage import Outage
from src.models.subscription import Subscription
from src.utils.config import load_config


class DatabaseManager:
    """
    Manages all Firebase Firestore operations.
    
    Collections:
        - outages: Stores all scraped outages
        - subscriptions: Stores user subscriptions
        - notifications_sent: Tracks sent notifications to prevent duplicates
    """
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize the database manager.
        
        Args:
            credentials_path: Path to Firebase credentials JSON file
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = load_config()
        
        if credentials_path is None:
            credentials_path = self.config.get("firebase_credentials_path", "")
        
        self._initialize_firebase(credentials_path)
        self.db = firestore.client()
        
        # Collection references
        self.outages_ref = self.db.collection("outages")
        self.subscriptions_ref = self.db.collection("subscriptions")
        self.notifications_ref = self.db.collection("notifications_sent")
        self.geocache_ref = self.db.collection("geocache")
    
    def _initialize_firebase(self, credentials_path: str) -> None:
        """Initialize Firebase app if not already initialized."""
        try:
            firebase_admin.get_app()
            self.logger.debug("Firebase already initialized")
        except ValueError:
            if credentials_path:
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred)
                self.logger.info("Firebase initialized with credentials")
            else:
                # Use default credentials (for Cloud Run, etc.)
                firebase_admin.initialize_app()
                self.logger.info("Firebase initialized with default credentials")
    
    # ==================== OUTAGE OPERATIONS ====================
    
    def save_outage(self, outage: Outage) -> bool:
        """
        Save an outage to the database.
        
        Args:
            outage: Outage object to save
            
        Returns:
            True if saved (new), False if already exists
        """
        doc_ref = self.outages_ref.document(outage.outage_id)
        doc = doc_ref.get()
        
        if doc.exists:
            self.logger.debug(f"Outage {outage.outage_id} already exists")
            return False
        
        doc_ref.set(outage.to_dict())
        self.logger.info(f"Saved new outage: {outage.outage_id}")
        return True
    
    def save_outages(self, outages: List[Outage]) -> Dict[str, int]:
        """
        Save multiple outages to the database.
        
        Args:
            outages: List of Outage objects
            
        Returns:
            Dictionary with counts: {"new": X, "existing": Y}
        """
        new_count = 0
        existing_count = 0
        
        # Use batch writes for efficiency
        batch = self.db.batch()
        batch_count = 0
        
        for outage in outages:
            doc_ref = self.outages_ref.document(outage.outage_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                batch.set(doc_ref, outage.to_dict())
                new_count += 1
                batch_count += 1
            else:
                existing_count += 1
            
            # Firestore batch limit is 500
            if batch_count >= 400:
                batch.commit()
                batch = self.db.batch()
                batch_count = 0
        
        if batch_count > 0:
            batch.commit()
        
        self.logger.info(f"Saved {new_count} new outages, {existing_count} already existed")
        return {"new": new_count, "existing": existing_count}
    
    def get_outage(self, outage_id: str) -> Optional[Outage]:
        """
        Get an outage by ID.
        
        Args:
            outage_id: Outage ID
            
        Returns:
            Outage object or None
        """
        doc = self.outages_ref.document(outage_id).get()
        if doc.exists:
            return Outage.from_dict(doc.to_dict())
        return None
    
    def get_recent_outages(self, days: int = 7) -> List[Outage]:
        """
        Get outages from the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of Outage objects
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        docs = (
            self.outages_ref
            .where("created_at", ">=", cutoff.isoformat())
            .stream()
        )
        
        return [Outage.from_dict(doc.to_dict()) for doc in docs]
    
    def get_upcoming_outages(self) -> List[Outage]:
        """
        Get outages scheduled for today or future.
        
        Returns:
            List of Outage objects
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        docs = (
            self.outages_ref
            .where("date_start", ">=", today.isoformat())
            .stream()
        )
        
        return [Outage.from_dict(doc.to_dict()) for doc in docs]
    
    def delete_old_outages(self, days: int = 30) -> int:
        """
        Delete outages older than N days.
        
        Args:
            days: Delete outages older than this many days
            
        Returns:
            Number of deleted outages
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        docs = (
            self.outages_ref
            .where("date_start", "<", cutoff.isoformat())
            .stream()
        )
        
        deleted = 0
        batch = self.db.batch()
        batch_count = 0
        
        for doc in docs:
            batch.delete(doc.reference)
            deleted += 1
            batch_count += 1
            
            if batch_count >= 400:
                batch.commit()
                batch = self.db.batch()
                batch_count = 0
        
        if batch_count > 0:
            batch.commit()
        
        self.logger.info(f"Deleted {deleted} old outages")
        return deleted
    
    # ==================== SUBSCRIPTION OPERATIONS ====================
    
    def save_subscription(self, subscription: Subscription) -> bool:
        """
        Save a subscription to the database.
        
        Args:
            subscription: Subscription object
            
        Returns:
            True if saved successfully
        """
        doc_ref = self.subscriptions_ref.document(subscription.subscription_id)
        doc_ref.set(subscription.to_dict())
        self.logger.info(f"Saved subscription: {subscription.subscription_id}")
        return True
    
    def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """
        Get a subscription by ID.
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            Subscription object or None
        """
        doc = self.subscriptions_ref.document(subscription_id).get()
        if doc.exists:
            return Subscription.from_dict(doc.to_dict())
        return None
    
    def get_subscriptions_by_endpoint(self, push_endpoint: str) -> List[Subscription]:
        """
        Get all subscriptions for a push endpoint.
        
        Args:
            push_endpoint: Web Push endpoint URL
            
        Returns:
            List of Subscription objects
        """
        docs = (
            self.subscriptions_ref
            .where("push_endpoint", "==", push_endpoint)
            .where("is_active", "==", True)
            .stream()
        )
        
        return [Subscription.from_dict(doc.to_dict()) for doc in docs]
    
    def get_all_active_subscriptions(self) -> List[Subscription]:
        """
        Get all active subscriptions.
        
        Returns:
            List of Subscription objects
        """
        docs = (
            self.subscriptions_ref
            .where("is_active", "==", True)
            .stream()
        )
        
        return [Subscription.from_dict(doc.to_dict()) for doc in docs]
    
    def get_subscriptions_by_municipality(self, municipality: str) -> List[Subscription]:
        """
        Get subscriptions for a specific municipality.
        
        Args:
            municipality: Municipality name
            
        Returns:
            List of Subscription objects
        """
        docs = (
            self.subscriptions_ref
            .where("municipality", "==", municipality.lower())
            .where("is_active", "==", True)
            .stream()
        )
        
        return [Subscription.from_dict(doc.to_dict()) for doc in docs]
    
    def delete_subscription(self, subscription_id: str) -> bool:
        """
        Delete a subscription.
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            True if deleted
        """
        self.subscriptions_ref.document(subscription_id).delete()
        self.logger.info(f"Deleted subscription: {subscription_id}")
        return True
    
    def deactivate_subscription(self, subscription_id: str) -> bool:
        """
        Deactivate a subscription (soft delete).
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            True if deactivated
        """
        self.subscriptions_ref.document(subscription_id).update({
            "is_active": False,
            "updated_at": datetime.now().isoformat(),
        })
        self.logger.info(f"Deactivated subscription: {subscription_id}")
        return True
    
    # ==================== NOTIFICATION TRACKING ====================
    
    def is_notification_sent(self, outage_id: str, subscription_id: str) -> bool:
        """
        Check if a notification was already sent.
        
        Args:
            outage_id: Outage ID
            subscription_id: Subscription ID
            
        Returns:
            True if already sent
        """
        notification_id = f"{outage_id}_{subscription_id}"
        doc = self.notifications_ref.document(notification_id).get()
        return doc.exists
    
    def record_notification_sent(
        self,
        outage_id: str,
        subscription_id: str,
        success: bool = True,
    ) -> None:
        """
        Record that a notification was sent.
        
        Args:
            outage_id: Outage ID
            subscription_id: Subscription ID
            success: Whether the notification was sent successfully
        """
        notification_id = f"{outage_id}_{subscription_id}"
        self.notifications_ref.document(notification_id).set({
            "outage_id": outage_id,
            "subscription_id": subscription_id,
            "sent_at": datetime.now().isoformat(),
            "success": success,
        })
    
    # ==================== GEOCACHE OPERATIONS ====================
    
    def get_cached_coordinates(self, address: str) -> Optional[tuple]:
        """
        Get cached coordinates for an address.
        
        Args:
            address: Address string
            
        Returns:
            Tuple of (latitude, longitude) or None
        """
        import hashlib
        address_hash = hashlib.md5(address.lower().encode()).hexdigest()
        
        doc = self.geocache_ref.document(address_hash).get()
        if doc.exists:
            data = doc.to_dict()
            return (data["latitude"], data["longitude"])
        return None
    
    def cache_coordinates(self, address: str, latitude: float, longitude: float) -> None:
        """
        Cache coordinates for an address.
        
        Args:
            address: Address string
            latitude: Latitude
            longitude: Longitude
        """
        import hashlib
        address_hash = hashlib.md5(address.lower().encode()).hexdigest()
        
        self.geocache_ref.document(address_hash).set({
            "address": address,
            "latitude": latitude,
            "longitude": longitude,
            "cached_at": datetime.now().isoformat(),
        })