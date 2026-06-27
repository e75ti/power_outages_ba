import unittest
from src.models.outage import Outage
from src.models.subscription import Subscription

class TestOutageModel(unittest.TestCase):
    def test_outage_creation(self):
        outage = Outage(location="123 Main St", start_time="2023-10-01T12:00:00", end_time="2023-10-01T14:00:00", description="Power outage due to maintenance.")
        self.assertEqual(outage.location, "123 Main St")
        self.assertEqual(outage.start_time, "2023-10-01T12:00:00")
        self.assertEqual(outage.end_time, "2023-10-01T14:00:00")
        self.assertEqual(outage.description, "Power outage due to maintenance.")

class TestSubscriptionModel(unittest.TestCase):
    def test_subscription_creation(self):
        subscription = Subscription(user_id="user123", street_name="123 Main St", notification_preferences="email")
        self.assertEqual(subscription.user_id, "user123")
        self.assertEqual(subscription.street_name, "123 Main St")
        self.assertEqual(subscription.notification_preferences, "email")

if __name__ == '__main__':
    unittest.main()