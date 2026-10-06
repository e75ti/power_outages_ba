"""Multi-channel notification service."""

import os
import json
import logging
import requests
from enum import Enum
from pywebpush import webpush, WebPushException

from src.models.outage import Outage
from src.models.subscription import Subscription
from src.config.settings import load_config


class NotificationStatus(Enum):
    SUCCESS = "success"
    EXPIRED = "expired"  # Indicates token/subscription is dead and should be deleted
    ERROR = "error"


class NotificationService:
    """Service for dispatching notifications across multiple channels."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = load_config()
        
        # VAPID (Web Push) config
        self.vapid_private_key = self.config.get("vapid_private_key", "")
        self.vapid_claims = {"sub": f"mailto:{self.config.get('vapid_claims_email', 'admin@example.com')}"}
        
        # Telegram config
        self.telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        
        # TODO: Load Viber Bot Token / FCM Credentials here when ready
    
    def send_outage_notification(self, subscription: Subscription, outage: Outage) -> NotificationStatus:
        """Determines the best channel and sends the notification."""
        
        payload = self._build_outage_payload(outage)
        
        # --- THE CHANNEL ROUTER ---
        
        # 1. Telegram
        if subscription.push_endpoint and subscription.push_endpoint.startswith("telegram:"):
            return self._send_telegram_message(subscription, payload)
            
        # 2. Web Push
        elif subscription.push_endpoint:
            return self._send_web_push(subscription, payload)
        
        # 3. Viber (Future)
        # elif subscription.viber_id:
        #     return self._send_viber_message(subscription, payload)
            
        return NotificationStatus.ERROR
    
    def _build_outage_payload(self, outage: Outage) -> dict:
        time_str = f"{outage.time_start} - {outage.time_end}" if (outage.time_start and outage.time_end) else f"od {outage.time_start or 'nepoznato'}"
        date_str = outage.date_start.strftime("%d.%m.%Y") if outage.date_start else ""
        
        body_parts = [p for p in [f"📍 {outage.municipality}", f"📅 {date_str}", f"⏰ {time_str}"] if p]
        
        return {
            "title": "⚡ Nestanak struje",
            "body": "\n".join(body_parts),
            "icon": "/icons/bolt-192.png",
            "tag": outage.outage_id,
            "data": {
                "outage_id": outage.outage_id,
                "provider": outage.provider,
                "area": outage.area[:200],
                "url": f"/outage/{outage.outage_id}",
            }
        }

    def _send_telegram_message(self, subscription: Subscription, payload: dict) -> NotificationStatus:
        if not self.telegram_token:
            self.logger.error("Telegram token missing.")
            return NotificationStatus.ERROR
            
        chat_id = subscription.push_endpoint.replace("telegram:", "")
        text = f"*{payload['title']}*\n\n{payload['body']}"
        
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        
        try:
            response = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
            if response.status_code == 200:
                self.logger.info(f"Telegram notification sent to {chat_id}")
                return NotificationStatus.SUCCESS
            elif response.status_code in (400, 403):
                self.logger.warning(f"Telegram user {chat_id} blocked the bot.")
                return NotificationStatus.EXPIRED  # Auto-cleans the database!
            else:
                self.logger.error(f"Telegram API Error: {response.text}")
                return NotificationStatus.ERROR
        except Exception as e:
            self.logger.error(f"Telegram Network Error: {e}")
            return NotificationStatus.ERROR
    
    def _send_web_push(self, subscription: Subscription, payload: dict) -> NotificationStatus:
        if not self.vapid_private_key:
            self.logger.error("VAPID key missing.")
            return NotificationStatus.ERROR
            
        sub_info = {"endpoint": subscription.push_endpoint, "keys": subscription.push_keys}
        
        try:
            webpush(
                subscription_info=sub_info,
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims,
            )
            return NotificationStatus.SUCCESS
            
        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                self.logger.warning(f"Push token expired for {subscription.subscription_id}")
                return NotificationStatus.EXPIRED
            self.logger.error(f"Push failed: {e}")
            return NotificationStatus.ERROR
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return NotificationStatus.ERROR
