# tests/test_scrapers.py
import unittest
from unittest.mock import patch, MagicMock
from src.scrapers.epbih_scraper import EPBiHScraper

class TestEPBiHScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = EPBiHScraper(use_cloudscraper=False)

    @patch('src.scrapers.base_scraper.BaseScraper._get')
    def test_scrape_outages(self, mock_get):
        # Mock HTML response
        mock_html = """
        <table>
            <tr class="item" data-ed="edsa" data-opcina="ilidza">
                <td>Ilidža</td>
                <td class="ulica">Unska</td>
                <td>1, 3, 5</td>
                <td>03.02.2026</td>
                <td>11:00-12:00</td>
            </tr>
        </table>
        """
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_get.return_value = mock_response

        # Execute
        outages = self.scraper.scrape()
        
        # Assertions
        self.assertEqual(len(outages), 1)
        outage = outages[0]
        self.assertEqual(outage.municipality, "Ilidža")
        self.assertEqual(outage.streets, "Unska")
        self.assertEqual(outage.time_start, "11:00")
        self.assertEqual(outage.time_end, "12:00")

    @patch('src.scrapers.base_scraper.BaseScraper._get')
    def test_handle_empty_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "<html><body>No data</body></html>"
        mock_get.return_value = mock_response

        outages = self.scraper.scrape()
        self.assertEqual(outages, [])

if __name__ == '__main__':
    unittest.main()
