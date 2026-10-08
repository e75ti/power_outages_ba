"""Scraper for Elektro Bijeljina outage data."""

import re
from datetime import datetime
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from src.models.outage import Outage
from src.scrapers.base_scraper import BaseScraper


class ElektroBijeljinaScraper(BaseScraper):
    """Scraper for Elektro Bijeljina planned outages."""

    PROVIDER_NAME = "Elektro Bijeljina"
    BASE_URL = "https://www.elektrobijeljina.com/lt/podrska/iskljucenja/index.php"

    REGIONAL_UNITS = {
        "41": "TJ Bijeljina",
        "46": "TJ Ugljevik",
        "38": "TJ Zvornik",
        "42": "TJ Bratunac",
        "44": "TJ Vlasenica",
    }

    def scrape(self) -> List[Outage]:
        """Scrape outage data from all regional units."""
        self.logger.info(f"Scraping {self.PROVIDER_NAME}...")
        outages = []

        for rj_code, unit_name in self.REGIONAL_UNITS.items():
            try:
                url = f"{self.BASE_URL}?rj={rj_code}"
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                unit_outages = self.parse(response.text, unit_name)
                outages.extend(unit_outages)
                self._rate_limit(0.3)

            except Exception as e:
                self.logger.warning(f"Error fetching {unit_name}: {e}")
                continue

        self.logger.info(f"Found {len(outages)} outages from {self.PROVIDER_NAME}")
        return outages

    def parse(self, html: str, unit_name: str = "Unknown") -> List[Outage]:
        """Parse HTML and extract outages."""
        soup = BeautifulSoup(html, "html.parser")
        outages = []

        # Check for no outages message
        if "Nema planiranih" in html:
            return outages

        # Find all date headers (p tags with color:#BF2626)
        all_elements = soup.find_all(["p", "table"])
        current_date = None

        for elem in all_elements:
            if elem.name == "p":
                # Check if this is a date header
                style = elem.get("style", "")
                if "BF2626" in style:
                    text = elem.get_text().strip()
                    # Extract date like "04-02-2026"
                    match = re.search(r"(\d{2}-\d{2}-\d{4})", text)
                    if match:
                        current_date = self._parse_date(match.group(1))

            elif elem.name == "table" and current_date:
                # Parse outage table
                rows = elem.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 6:
                        continue

                    # Skip header rows (background-color:#333)
                    if "#333" in cells[0].get("style", ""):
                        continue

                    try:
                        outage = Outage(
                            provider=self.PROVIDER_NAME,
                            region=unit_name,
                            municipality=cells[0].get_text().strip(),
                            area=cells[2].get_text().strip(),
                            streets=cells[2].get_text().strip(),
                            date_start=current_date,
                            time_start=self._parse_time(cells[4].get_text().strip()),
                            time_end=self._parse_time(cells[5].get_text().strip()),
                            reason=cells[3].get_text().strip(),
                            facility=cells[1].get_text().strip(),
                            raw_text=f"{cells[1].get_text().strip()} - {cells[2].get_text().strip()}",
                        )
                        outages.append(outage)
                    except Exception as e:
                        self.logger.debug(f"Failed to parse row: {e}")
                        continue

        return outages

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse DD-MM-YYYY date format."""
        try:
            return datetime.strptime(date_str, "%d-%m-%Y")
        except Exception as e:
            self.logger.debug(f"Failed to parse date {date_str}: {e}")
            return None

    def _parse_time(self, time_str: str) -> Optional[str]:
        """Parse HH:MM time format."""
        match = re.search(r"(\d{1,2}):(\d{2})", time_str)
        if match:
            return f"{int(match.group(1)):02d}:{match.group(2)}"
        return None
