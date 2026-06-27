"""Web Push notification service."""

import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

from pywebpush import webpush, WebPushException

from src.models.outage import Outage
from src.models.subscription import Subscription
from src.utils.config import load_config


class NotificationService:
    """
    Service for sending Web Push notifications.
    
    Uses VAPID (Voluntary Application Server Identification) for authentication.
    """
    
    def __init__(self):
        """Initialize the notification service."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = load_config()
        
        self.vapid_private_key = self.config.get("vapid_private_key", "")
        self.vapid_claims = {
            "sub": f"mailto:{self.config.get('vapid_claims_email', 'admin@example.com')}"
        }
        
        if not self.vapid_private_key:
            self.logger.warning("VAPID private key not configured!")
    
    def send_outage_notification(
        self,
        subscription: Subscription,
        outage: Outage,
    ) -> bool:
        """
        Send a notification about an outage to a subscriber.
        
        Args:
            subscription: Subscription to notify
            outage: Outage information
            
        Returns:
            True if notification sent successfully
        """
        if not subscription.push_endpoint or not subscription.push_keys:
            self.logger.warning(f"Subscription {subscription.subscription_id} missing push info")
            return False
        
        # Build notification payload
        payload = self._build_outage_payload(outage, subscription)
        
        return self._send_push(subscription, payload)
    
    def send_bulk_notifications(
        self,
        subscriptions: List[Subscription],
        outage: Outage,
    ) -> Dict[str, int]:
        """
        Send notifications to multiple subscribers.
        
        Args:
            subscriptions: List of subscriptions to notify
            outage: Outage information
            
        Returns:
            Dictionary with counts: {"success": X, "failed": Y}
        """
        success = 0
        failed = 0
        
        for subscription in subscriptions:
            if self.send_outage_notification(subscription, outage):
                success += 1
            else:
                failed += 1
        
        self.logger.info(f"Notifications sent: {success} success, {failed} failed")
        return {"success": success, "failed": failed}
    
    def _build_outage_payload(
        self,
        outage: Outage,
        subscription: Subscription,
    ) -> dict:
        """
        Build the notification payload.
        
        Args:
            outage: Outage information
            subscription: Subscription (for context)
            
        Returns:
            Notification payload dictionary
        """
        # Format time range
        time_str = ""
        if outage.time_start and outage.time_end:
            time_str = f"{outage.time_start} - {outage.time_end}"
        elif outage.time_start:
            time_str = f"od {outage.time_start}"
        
        # Format date
        date_str = ""
        if outage.date_start:
            date_str = outage.date_start.strftime("%d.%m.%Y")
        
        # Build title and body
        title = "⚡ Nestanak struje"
        
        body_parts = []
        if outage.municipality:
            body_parts.append(f"📍 {outage.municipality}")
        if date_str:
            body_parts.append(f"📅 {date_str}")
        if time_str:
            body_parts.append(f"⏰ {time_str}")
        
        body = "\n".join(body_parts)
        
        # Full data for the notification
        return {
            "title": title,
            "body": body,
            "icon": "/icons/bolt-192.png",
            "badge": "/icons/bolt-72.png",
            "tag": outage.outage_id,  # Prevents duplicate notifications
            "data": {
                "outage_id": outage.outage_id,
                "provider": outage.provider,
                "municipality": outage.municipality,
                "area": outage.area[:200],  # Truncate for payload size
                "date": date_str,
                "time": time_str,
                "url": f"/outage/{outage.outage_id}",
            },
            "actions": [
                {
                    "action": "view",
                    "title": "Pogledaj detalje",
                },
                {
                    "action": "dismiss",
                    "title": "Odbaci",
                },
            ],
        }
    
    def _send_push(self, subscription: Subscription, payload: dict) -> bool:
        """
        Send a Web Push notification.
        
        Args:
            subscription: Subscription with push endpoint and keys
            payload: Notification payload
            
        Returns:
            True if sent successfully
        """
        if not self.vapid_private_key:
            self.logger.error("Cannot send push: VAPID key not configured")
            return False
        
        subscription_info = {
            "endpoint": subscription.push_endpoint,
            "keys": subscription.push_keys,
        }
        
        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims,
            )
            self.logger.debug(f"Push sent to {subscription.subscription_id}")
            return True
            
        except WebPushException as e:
            self.logger.error(f"Push failed for {subscription.subscription_id}: {e}")
            
            # Check if subscription is expired/invalid
            if e.response and e.response.status_code in (404, 410):
                self.logger.warning(f"Subscription {subscription.subscription_id} expired")
                # TODO: Mark subscription as inactive in database
            
            return False
        
        except Exception as e:
            self.logger.error(f"Unexpected error sending push: {e}")
            return False
    
    def send_test_notification(self, subscription: Subscription) -> bool:
        """
        Send a test notification to verify subscription.
        
        Args:
            subscription: Subscription to test
            
        Returns:
            True if sent successfully
        """
        payload = {
            "title": "✅ Test notifikacija",
            "body": f"Uspješno ste se pretplatili na obavijesti za {subscription.street_name}, {subscription.municipality}",
            "icon": "/icons/bolt-192.png",
            "tag": "test-notification",
        }
        
        return self._send_push(subscription, payload)