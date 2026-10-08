"""Scraper for Elektro Doboj outage data."""

import json
import re
from datetime import datetime
from typing import List

from bs4 import BeautifulSoup

from src.models.outage import Outage
from src.scrapers.base_scraper import BaseScraper


class ElektroDobojScraper(BaseScraper):
    """Scraper for Elektro Doboj planned outages using embedded JSON bypass."""

    PROVIDER_NAME = "Elektro Doboj"
    BASE_URL = "https://www.elektrodoboj.net/UsluzniCentar/PlaniraniPrekidi"

    def __init__(self, timeout: int = 45, max_retries: int = 3):
        """Initialize the Elektro Doboj scraper with a higher timeout."""
        super().__init__(timeout=timeout, max_retries=max_retries)
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
            }
        )

    def scrape(self) -> List[Outage]:
        self.logger.info(f"Scraping {self.PROVIDER_NAME}...")
        outages = []

        try:
            response = self._get(self.BASE_URL)
            # FIX: Safely decode bytes to UTF-8 before hunting for the JSON
            decoded_html = response.content.decode("utf-8", errors="replace")
            outages = self.parse(decoded_html)
            self.logger.info(
                f"Found {len(outages)} outages from {self.PROVIDER_NAME} via Map JSON"
            )

        except Exception as e:
            self.logger.error(f"Error scraping {self.PROVIDER_NAME}: {e}")
            raise

        return outages

    def parse(self, html: str) -> List[Outage]:
        """
        Parse HTML content and extract outages by hunting for the Telerik RadMap JSON.
        Bypasses ASP.NET pagination completely.
        """
        outages = []

        # Extract the Telerik RadMap JSON array containing all pages' outages
        match = re.search(r'"markers":\s*(\[.*?\])\s*,"zoom"', html)
        if not match:
            self.logger.warning("Could not find JSON map data in Elektro Doboj HTML.")
            return outages

        try:
            markers = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON map data: {e}")
            return outages

        for marker in markers:
            # Skip the dummy empty markers often left by Telerik [0,0]
            location = marker.get("location")
            if not location or location == [0, 0]:
                continue

            tooltip_html = marker.get("tooltip", {}).get("content", "")
            if not tooltip_html:
                continue

            # Parse the mini-HTML popup window embedded in the map JSON
            soup = BeautifulSoup(tooltip_html, "html.parser")
            divs = soup.find_all("div", class_="col")

            # Ensure the tooltip contains all required fields
            if len(divs) >= 4:
                facility = self._clean_text(divs[0].text)
                reason = self._clean_text(divs[1].text)

                # Clean up "од 25.09.2026. 09.00.00" string
                start_str = self._clean_text(divs[2].text).replace("од", "").strip()
                end_str = self._clean_text(divs[3].text).replace("до", "").strip()

                try:
                    # Format matching "25.09.2026. 09.00.00"
                    start_dt = datetime.strptime(start_str, "%d.%m.%Y. %H.%M.%S")
                    end_dt = datetime.strptime(end_str, "%d.%m.%Y. %H.%M.%S")

                    outage = Outage(
                        provider=self.PROVIDER_NAME,
                        region="Doboj",
                        municipality="Doboj",
                        area=facility,
                        streets=facility,  # Facility name stands in for streets in Doboj's map data
                        reason=reason,
                        date_start=start_dt,
                        date_end=end_dt,
                        time_start=start_dt.strftime("%H:%M"),
                        time_end=end_dt.strftime("%H:%M"),
                        facility=facility,
                        raw_text=f"{facility} - {reason}",
                        coordinates=tuple(location),
                    )
                    outages.append(outage)
                except ValueError as e:
                    self.logger.debug(
                        f"Date parsing failed for Doboj: {start_str} - {e}"
                    )

        return outages

    def _clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace."""
        if not text:
            return ""
        return " ".join(text.split()).strip()
