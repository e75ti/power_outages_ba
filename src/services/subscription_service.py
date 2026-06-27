"""Subscription management service."""

import logging
from typing import List, Optional, Dict, Tuple

from src.models.outage import Outage
from src.models.subscription import Subscription
from src.database.db_manager import DatabaseManager
from src.services.geo_service import GeoService
from src.services.notification_service import NotificationService


class SubscriptionService:
    """
    Service for managing subscriptions and matching outages.
    
    Handles:
    - Creating/updating/deleting subscriptions
    - Finding matching subscriptions for outages
    - Sending notifications
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        Initialize the subscription service.
        
        Args:
            db_manager: Database manager instance (creates one if not provided)
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = db_manager or DatabaseManager()
        self.geo_service = GeoService()
        self.notification_service = NotificationService()
    
    def create_subscription(
        self,
        street_name: str,
        municipality: str,
        push_endpoint: str,
        push_keys: Dict[str, str],
        is_rural: bool = False,
        coordinates: Optional[Tuple[float, float]] = None,
    ) -> Subscription:
        """
        Create a new subscription.
        
        Args:
            street_name: Street name to monitor
            municipality: Municipality name
            push_endpoint: Web Push endpoint URL
            push_keys: Web Push keys (p256dh, auth)
            is_rural: Enable area-based matching
            coordinates: Optional coordinates for geo matching
            
        Returns:
            Created Subscription object
        """
        # Geocode if coordinates not provided and is_rural
        if is_rural and not coordinates:
            coordinates = self.geo_service.geocode_address(
                f"{street_name}, {municipality}"
            )
        
        subscription = Subscription(
            street_name=street_name,
            municipality=municipality,
            push_endpoint=push_endpoint,
            push_keys=push_keys,
            is_rural=is_rural,
            coordinates=coordinates,
        )
        
        self.db.save_subscription(subscription)
        
        # Send confirmation notification
        self.notification_service.send_test_notification(subscription)
        
        self.logger.info(f"Created subscription: {subscription}")
        return subscription
    
    def update_subscription(
        self,
        subscription_id: str,
        **updates,
    ) -> Optional[Subscription]:
        """
        Update an existing subscription.
        
        Args:
            subscription_id: Subscription ID
            **updates: Fields to update
            
        Returns:
            Updated Subscription or None if not found
        """
        subscription = self.db.get_subscription(subscription_id)
        if not subscription:
            return None
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(subscription, key):
                setattr(subscription, key, value)
        
        subscription.updated_at = __import__('datetime').datetime.now()
        self.db.save_subscription(subscription)
        
        return subscription
    
    def delete_subscription(self, subscription_id: str) -> bool:
        """
        Delete a subscription.
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            True if deleted
        """
        return self.db.delete_subscription(subscription_id)
    
    def get_subscriptions_for_endpoint(self, push_endpoint: str) -> List[Subscription]:
        """
        Get all subscriptions for a push endpoint.
        
        Args:
            push_endpoint: Web Push endpoint URL
            
        Returns:
            List of subscriptions
        """
        return self.db.get_subscriptions_by_endpoint(push_endpoint)
    
    def process_outages(self, outages: List[Outage]) -> Dict[str, int]:
        """
        Process outages and send notifications to matching subscriptions.
        
        Args:
            outages: List of outages to process
            
        Returns:
            Statistics dictionary
        """
        stats = {
            "outages_processed": 0,
            "notifications_sent": 0,
            "notifications_failed": 0,
            "already_notified": 0,
        }
        
        # Get all active subscriptions
        subscriptions = self.db.get_all_active_subscriptions()
        self.logger.info(f"Processing {len(outages)} outages against {len(subscriptions)} subscriptions")
        
        for outage in outages:
            stats["outages_processed"] += 1
            
            # Find matching subscriptions
            matches = self.geo_service.find_matching_subscriptions(outage, subscriptions)
            
            for subscription in matches:
                # Check if already notified
                if self.db.is_notification_sent(outage.outage_id, subscription.subscription_id):
                    stats["already_notified"] += 1
                    continue
                
                # Send notification
                success = self.notification_service.send_outage_notification(
                    subscription,
                    outage,
                )
                
                # Record the notification attempt
                self.db.record_notification_sent(
                    outage.outage_id,
                    subscription.subscription_id,
                    success=success,
                )
                
                if success:
                    stats["notifications_sent"] += 1
                    subscription.record_notification()
                    self.db.save_subscription(subscription)
                else:
                    stats["notifications_failed"] += 1
        
        self.logger.info(f"Processing complete: {stats}")
        return stats
    
    def find_outages_for_subscription(
        self,
        subscription: Subscription,
    ) -> List[Outage]:
        """
        Find upcoming outages that affect a subscription.
        
        Args:
            subscription: Subscription to check
            
        Returns:
            List of matching outages
        """
        upcoming = self.db.get_upcoming_outages()
        
        matches = []
        for outage in upcoming:
            if self.geo_service.matches(outage, subscription):
                matches.append(outage)
        
        return matches