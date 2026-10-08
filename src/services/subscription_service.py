"""Subscription management service."""

import logging
from typing import Dict, List

from src.database.db_manager import DatabaseManager
from src.models.outage import Outage
from src.services.geo_service import GeoService
from src.services.notification_service import NotificationService, NotificationStatus


class SubscriptionService:
    """Manages subscriptions, geo-matching, and auto-cleanup of dead tokens."""

    def __init__(self, db_manager: DatabaseManager):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = db_manager
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
            matches = self.geo_service.find_matching_subscriptions(
                outage, subscriptions
            )
            for subscription in matches:
                if self.db.is_notification_sent(
                    outage.outage_id, subscription.subscription_id
                ):
                    continue

                status = self.notification_service.send_outage_notification(
                    subscription, outage
                )

                if status == NotificationStatus.SUCCESS:
                    stats["sent"] += 1
                    self.db.record_notification_sent(
                        outage.outage_id, subscription.subscription_id, success=True
                    )
                    subscription.record_notification()
                    self.db.save_subscription(subscription)
                elif status == NotificationStatus.EXPIRED:
                    self.db.deactivate_subscription(subscription.subscription_id)
                    stats["expired_cleaned"] += 1
                else:
                    stats["failed"] += 1
                    self.db.record_notification_sent(
                        outage.outage_id, subscription.subscription_id, success=False
                    )

        return stats

    def process_reminders(self, all_active_outages) -> Dict[str, int]:
        """Runs periodically to warn users of outages starting in the next 2 hours."""
        import re
        from datetime import datetime, timedelta

        stats = {"reminders_sent": 0}
        subscriptions = self.db.get_all_active_subscriptions()
        if not subscriptions or not all_active_outages:
            return stats

        now = datetime.now()

        for outage in all_active_outages:
            if not getattr(outage, "date_start", None) or not getattr(
                outage, "time_start", None
            ):
                continue

            match = re.search(r"(\d{1,2})[:.](\d{2})", outage.time_start)
            if not match:
                continue

            hour, minute = int(match.group(1)), int(match.group(2))

            try:
                start_dt = outage.date_start.replace(hour=hour, minute=minute)
                time_until_outage = start_dt - now

                # IS IT STARTING IN THE NEXT 2 HOURS?
                if timedelta(hours=0) < time_until_outage <= timedelta(hours=2):
                    reminder_id = f"{outage.outage_id}_reminder"
                    matches = self.geo_service.find_matching_subscriptions(
                        outage, subscriptions
                    )

                    for sub in matches:
                        if not self.db.is_notification_sent(
                            reminder_id, sub.subscription_id
                        ):
                            original_area = outage.area
                            outage.area = f"⚠️ PODSJETNIK: Struja nestaje uskoro! ⚠️\n{original_area}"

                            status = self.notification_service.send_outage_notification(
                                sub, outage
                            )

                            if status == NotificationStatus.SUCCESS:
                                self.db.record_notification_sent(
                                    reminder_id, sub.subscription_id, success=True
                                )
                                stats["reminders_sent"] += 1

                            outage.area = original_area
            except Exception as e:
                self.logger.error(
                    f"Error processing reminder for {outage.outage_id}: {e}"
                )
                continue

        return stats
