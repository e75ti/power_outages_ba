# tests/test_models.py
import unittest
from datetime import datetime

from src.models.outage import Outage
from src.models.subscription import Subscription


class TestOutageModel(unittest.TestCase):
    def test_outage_creation(self):
        dt = datetime(2026, 2, 4, 8, 0)
        outage = Outage(
            provider="EPBiH",
            region="Sarajevo",
            municipality="Ilidža",
            area="Unska 1,3",
            streets="Unska",
            date_start=dt,
            time_start="08:00",
            time_end="14:00",
        )
        self.assertEqual(outage.provider, "EPBiH")
        self.assertEqual(outage.municipality, "Ilidža")

        # Test hash generation consistency
        outage_id_1 = outage.outage_id
        self.assertTrue(len(outage_id_1) > 0)

    def test_is_active(self):
        dt = datetime(2026, 2, 4, 8, 0)
        outage = Outage(
            provider="EPBiH",
            region="SA",
            date_start=dt,
            time_start="08:00",
            time_end="12:00",
        )

        # Active case
        test_time_active = datetime(2026, 2, 4, 10, 0)
        self.assertTrue(outage.is_active(current_time=test_time_active))

        # Past case
        test_time_past = datetime(2026, 2, 4, 13, 0)
        self.assertFalse(outage.is_active(current_time=test_time_past))


class TestSubscriptionModel(unittest.TestCase):
    def test_subscription_creation(self):
        sub = Subscription(
            street_name="Unska",
            municipality="Ilidža",
            push_endpoint="https://fcm.googleapis.com/fcm/send/...",
            provider_preference=["EPBiH"],
        )
        self.assertEqual(sub.street_name, "Unska")
        self.assertEqual(sub.municipality, "Ilidža")
        self.assertEqual(sub.provider_preference, ["EPBiH"])
        self.assertTrue(sub.is_active)


if __name__ == "__main__":
    unittest.main()
