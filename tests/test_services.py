# tests/test_services.py
import unittest
from datetime import datetime
from unittest.mock import MagicMock

from src.models.outage import Outage
from src.models.subscription import Subscription
from src.services.notification_service import NotificationStatus
from src.services.subscription_service import SubscriptionService


class TestSubscriptionService(unittest.TestCase):
    def setUp(self):
        # Mock the database
        self.mock_db = MagicMock()
        self.service = SubscriptionService(db_manager=self.mock_db)

    def test_process_outages_success(self):
        # Setup mock data
        outage = Outage(
            provider="EPBiH",
            region="SA",
            municipality="Ilidža",
            area="Unska",
            date_start=datetime.now(),
        )
        sub = Subscription(
            street_name="Unska", municipality="Ilidža", push_endpoint="mock_url"
        )

        # Mock DB returns
        self.mock_db.get_all_active_subscriptions.return_value = [sub]
        self.mock_db.is_notification_sent.return_value = False

        # Mock Notification sending success
        self.service.notification_service.send_outage_notification = MagicMock(
            return_value=NotificationStatus.SUCCESS
        )

        # Execute
        stats = self.service.process_outages([outage])

        self.assertEqual(stats["sent"], 1)
        self.assertEqual(stats["expired_cleaned"], 0)
        self.mock_db.record_notification_sent.assert_called_once()
        self.mock_db.save_subscription.assert_called_once()

    def test_process_outages_auto_cleanup(self):
        outage = Outage(
            provider="EPBiH",
            region="SA",
            municipality="Ilidža",
            area="Unska",
            date_start=datetime.now(),
        )
        sub = Subscription(
            street_name="Unska", municipality="Ilidža", push_endpoint="mock_url"
        )

        self.mock_db.get_all_active_subscriptions.return_value = [sub]
        self.mock_db.is_notification_sent.return_value = False

        # Mock Notification expiring (user revoked permission)
        self.service.notification_service.send_outage_notification = MagicMock(
            return_value=NotificationStatus.EXPIRED
        )

        # Execute
        stats = self.service.process_outages([outage])

        self.assertEqual(stats["sent"], 0)
        self.assertEqual(stats["expired_cleaned"], 1)

        # Verify the DB was told to deactivate this user
        self.mock_db.deactivate_subscription.assert_called_once_with(
            sub.subscription_id
        )


if __name__ == "__main__":
    unittest.main()
