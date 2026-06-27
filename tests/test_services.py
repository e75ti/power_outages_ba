import unittest
from src.services.notification_service import NotificationService
from src.services.subscription_service import SubscriptionService
from src.models.subscription import Subscription

class TestNotificationService(unittest.TestCase):
    def setUp(self):
        self.notification_service = NotificationService()
        self.subscription_service = SubscriptionService()

    def test_send_notification(self):
        # Assuming we have a mock subscription
        subscription = Subscription(user_id="user123", street_name="Main St", notification_preferences="email")
        self.subscription_service.add_subscription(subscription)
        
        result = self.notification_service.send_notification(subscription, "Test outage notification")
        self.assertTrue(result)

class TestSubscriptionService(unittest.TestCase):
    def setUp(self):
        self.subscription_service = SubscriptionService()

    def test_add_subscription(self):
        subscription = Subscription(user_id="user123", street_name="Main St", notification_preferences="email")
        self.subscription_service.add_subscription(subscription)
        self.assertIn(subscription, self.subscription_service.subscriptions)

    def test_remove_subscription(self):
        subscription = Subscription(user_id="user123", street_name="Main St", notification_preferences="email")
        self.subscription_service.add_subscription(subscription)
        self.subscription_service.remove_subscription(subscription)
        self.assertNotIn(subscription, self.subscription_service.subscriptions)

if __name__ == '__main__':
    unittest.main()