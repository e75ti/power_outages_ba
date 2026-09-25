# src/services/subscription_service.py
"""Subscription management service."""

import logging
from typing import List, Dict, Optional

from src.models.outage import Outage
from src.models.subscription import Subscription
from src.database.db_manager import DatabaseManager
from src.services.geo_service import GeoService
from src.services.notification_service import NotificationService, NotificationStatus


class SubscriptionService:
    """Manages subscriptions, geo-matching, and auto-cleanup of dead tokens."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = db_manager
        # Inject db into GeoService so it can access the cache
        self.geo_service = GeoService(db_manager=self.db)
        self.notification_service = NotificationService()
    
    def process_outages(self, new_outages: List[Outage]) -> Dict[str, int]:
        stats = {
            "processed": len(new_outages),
            "sent": 0,
            "failed": 0,
            "expired_cleaned": 0,
        }
        
        subscriptions = self.db.get_all_active_subscriptions()
        if not subscriptions or not new_outages:
            return stats
            
        for outage in new_outages:
            matches = self.geo_service.find_matching_subscriptions(outage, subscriptions)
            
            for subscription in matches:
                # Prevent duplicates
                if self.db.is_notification_sent(outage.outage_id, subscription.subscription_id):
                    continue
                
                status = self.notification_service.send_outage_notification(subscription, outage)
                
                if status == NotificationStatus.SUCCESS:
                    stats["sent"] += 1
                    self.db.record_notification_sent(outage.outage_id, subscription.subscription_id, success=True)
                    subscription.record_notification()
                    self.db.save_subscription(subscription)
                    
                elif status == NotificationStatus.EXPIRED:
                    # FIX: Auto-clean dead subscriptions (e.g., user uninstalled the app / revoked permissions)
                    self.db.deactivate_subscription(subscription.subscription_id)
                    stats["expired_cleaned"] += 1
                    
                else:
                    stats["failed"] += 1
                    self.db.record_notification_sent(outage.outage_id, subscription.subscription_id, success=False)
                    
        return stats
