import unittest
from src.scrapers.outage_scraper import OutageScraper

class TestOutageScraper(unittest.TestCase):

    def setUp(self):
        self.scraper = OutageScraper()

    def test_scrape_outages(self):
        outages = self.scraper.scrape_outages()
        self.assertIsInstance(outages, list)
        for outage in outages:
            self.assertIn('location', outage)
            self.assertIn('start_time', outage)
            self.assertIn('end_time', outage)
            self.assertIn('description', outage)

    def test_handle_empty_response(self):
        self.scraper.get_html_content = lambda url: ""
        outages = self.scraper.scrape_outages()
        self.assertEqual(outages, [])

    def test_handle_invalid_url(self):
        with self.assertRaises(Exception):
            self.scraper.scrape_outages(url="http://invalid-url.com")

if __name__ == '__main__':
    unittest.main()