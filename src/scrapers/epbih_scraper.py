"""Scraper for EPBiH (Elektroprivreda BiH) outage data."""

import re
from datetime import datetime
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup

from src.models.outage import Outage
from src.scrapers.base_scraper import BaseScraper


class EPBiHScraper(BaseScraper):
    """Scraper for EPBiH planned outages."""

    PROVIDER_NAME = "EPBiH"
    BASE_URL = "https://www.epbih.ba/stranica/servisne-informacije"

    # ED (Elektrodistribucija) regions mapping from data-ed attribute
    ED_REGIONS = {
        "edsa": "Sarajevo",
        "edbihac": "Bihać",
        "edtuzla": "Tuzla",
        "edzenica": "Zenica",
        "edmostar": "Mostar",
        "edgorazde": "Goražde",
    }

    def scrape(self) -> List[Outage]:
        """
        Scrape outage data from EPBiH website.

        Returns:
            List of Outage objects
        """
        self.logger.info(f"Scraping {self.PROVIDER_NAME}...")

        try:
            response = self._get(self.BASE_URL)
            outages = self.parse(response.text)
            self.logger.info(f"Found {len(outages)} outages from {self.PROVIDER_NAME}")
            return outages

        except Exception as e:
            self.logger.error(f"Error scraping {self.PROVIDER_NAME}: {e}")
            raise

    def parse(self, html: str) -> List[Outage]:
        """
        Parse HTML content and extract outages.

        EPBiH table structure:
        <tr class="item" data-ed="edsa" data-opcina="ilidza">
            <td>Ilidža</td>          <!-- Municipality -->
            <td class="ulica">Unska</td>  <!-- Street -->
            <td>1, 3, 5-26...</td>   <!-- House numbers -->
            <td>03.02.2026</td>      <!-- Date -->
            <td>11:00-12:00</td>     <!-- Time -->
        </tr>

        Args:
            html: HTML content to parse

        Returns:
            List of Outage objects
        """
        outages = []
        soup = BeautifulSoup(html, "html.parser")

        # Find all table rows with class "item"
        rows = soup.find_all("tr", class_="item")

        self.logger.debug(f"Found {len(rows)} table rows with class 'item'")

        for row in rows:
            outage = self._parse_row(row)
            if outage:
                outages.append(outage)

        # If no rows found with class "item", try other approaches
        if not outages:
            self.logger.debug("No 'item' rows found, trying alternative parsing...")
            outages = self._parse_alternative(soup)

        return outages

    def _parse_row(self, row) -> Optional[Outage]:
        """
        Parse a table row into an Outage object.

        Expected structure:
        <tr class="item" data-ed="edsa" data-opcina="ilidza">
            <td>Ilidža</td>
            <td class="ulica">Unska</td>
            <td>1, 3, 5-26, 28-29...</td>
            <td>03.02.2026</td>
            <td>11:00-12:00</td>
        </tr>
        """
        try:
            cells = row.find_all("td")

            if len(cells) < 5:
                self.logger.debug(f"Row has only {len(cells)} cells, expected 5")
                return None

            # Extract data from cells
            municipality = self._clean_text(cells[0].get_text())
            street = self._clean_text(cells[1].get_text())
            house_numbers = self._clean_text(cells[2].get_text())
            date_str = self._clean_text(cells[3].get_text())
            time_str = self._clean_text(cells[4].get_text())

            # Get region from data-ed attribute
            data_ed = row.get("data-ed", "")
            region = self.ED_REGIONS.get(data_ed, "Unknown")

            # Parse date
            date_start = self._parse_date(date_str)
            if not date_start:
                self.logger.debug(f"Could not parse date: {date_str}")
                return None

            # Parse time range
            time_start, time_end = self._parse_time_range(time_str)

            # Build full address/area
            if house_numbers:
                area = f"{street} {house_numbers}"
            else:
                area = street

            return Outage(
                provider=self.PROVIDER_NAME,
                region=region,
                municipality=municipality,
                area=area,
                streets=street,
                date_start=date_start,
                date_end=date_start,  # <--- THE FIX: Single pure date for both
                time_start=time_start,
                time_end=time_end,
                reason="Planirani radovi",  # EPBiH doesn't provide specific reasons
                raw_text=f"{municipality}, {street} {house_numbers}, {date_str} {time_str}",
            )

        except Exception as e:
            self.logger.debug(f"Error parsing row: {e}")
            return None

    def _parse_alternative(self, soup) -> List[Outage]:
        """
        Alternative parsing method for different table structures.
        """
        outages = []

        # Try to find tables
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")

            for row in rows:
                cells = row.find_all("td")

                # Skip header rows or rows with insufficient cells
                if len(cells) < 4:
                    continue

                # Try to detect structure by looking for date patterns
                for i, cell in enumerate(cells):
                    cell_text = self._clean_text(cell.get_text())
                    date = self._parse_date(cell_text)

                    if date and i >= 1:
                        # Found a date, try to parse based on position
                        outage = self._parse_row_by_date_position(cells, i)
                        if outage:
                            outages.append(outage)
                        break

        return outages

    def _parse_row_by_date_position(self, cells, date_index: int) -> Optional[Outage]:
        """Parse row when we know which cell contains the date."""
        try:
            # If date is at index 3 (4th column), structure is:
            # Municipality | Street | House Numbers | Date | Time
            if date_index == 3 and len(cells) >= 5:
                municipality = self._clean_text(cells[0].get_text())
                street = self._clean_text(cells[1].get_text())
                house_numbers = self._clean_text(cells[2].get_text())
                date_str = self._clean_text(cells[3].get_text())
                time_str = self._clean_text(cells[4].get_text())

                date_start = self._parse_date(date_str)
                if not date_start:
                    return None

                time_start, time_end = self._parse_time_range(time_str)

                area = f"{street} {house_numbers}" if house_numbers else street

                return Outage(
                    provider=self.PROVIDER_NAME,
                    region="Unknown",
                    municipality=municipality,
                    area=area,
                    streets=street,
                    date_start=date_start,
                    date_end=date_start,  # <--- THE FIX: Single pure date for both
                    time_start=time_start,
                    time_end=time_end,
                    reason="Planirani radovi",
                    raw_text=f"{municipality}, {street}, {date_str} {time_str}",
                )

        except Exception as e:
            self.logger.debug(f"Error in _parse_row_by_date_position: {e}")

        return None

    def _parse_time_range(self, time_str: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse a time range string (e.g., '11:00-12:00' or '08:00 - 14:00').

        Returns:
            Tuple of (time_start, time_end)
        """
        if not time_str:
            return None, None

        time_start = None
        time_end = None

        # Common patterns: "11:00-12:00", "08:00 - 14:00", "9-15"
        # Try to split by common separators
        for sep in ["-", "–", "—", " - ", " do ", " DO "]:
            if sep in time_str:
                parts = time_str.split(sep, 1)
                if len(parts) == 2:
                    time_start = self._normalize_time(parts[0].strip())
                    time_end = self._normalize_time(parts[1].strip())
                    if time_start and time_end:
                        break

        # If no separator found, try regex
        if not time_start:
            match = re.search(
                r"(\d{1,2}[:.]\d{2})\s*[-–—]\s*(\d{1,2}[:.]\d{2})", time_str
            )
            if match:
                time_start = self._normalize_time(match.group(1))
                time_end = self._normalize_time(match.group(2))

        return time_start, time_end

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_str:
            return None

        # Clean the string
        date_str = date_str.strip().rstrip(".")

        # Try various formats
        formats = [
            "%d.%m.%Y",
            "%d.%m.%Y.",
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d. %m. %Y",
            "%d.%m.%y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Try regex extraction
        match = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", date_str)
        if match:
            day, month, year = match.groups()
            if len(year) == 2:
                year = "20" + year
            try:
                return datetime(int(year), int(month), int(day))
            except ValueError:
                pass

        return None

    def _normalize_time(self, time_str: str) -> Optional[str]:
        """Normalize time string to HH:MM format."""
        if not time_str:
            return None

        time_str = time_str.strip()

        # Replace . with :
        time_str = time_str.replace(".", ":")

        # Remove any non-digit/colon characters
        time_str = re.sub(r"[^\d:]", "", time_str)

        # Extract time pattern HH:MM
        match = re.search(r"(\d{1,2}):(\d{2})", time_str)
        if match:
            hour, minute = match.groups()
            return f"{int(hour):02d}:{minute}"

        # Try just HH format
        match = re.search(r"^(\d{1,2})$", time_str)
        if match:
            return f"{int(match.group(1)):02d}:00"

        return None

    def _clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace and special characters."""
        if not text:
            return ""

        # Remove extra whitespace
        text = " ".join(text.split())

        # Strip leading/trailing whitespace
        text = text.strip()

        return text
