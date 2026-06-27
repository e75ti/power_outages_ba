"""Scraper for Elektrokrajina outage data."""

import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup

from src.models.outage import Outage
from src.scrapers.base_scraper import BaseScraper


class ElektroKrajinaScraper(BaseScraper):
    """Scraper for Elektrokrajina planned outages."""
    
    PROVIDER_NAME = "Elektrokrajina"
    BASE_URL = "https://www.elektrokrajina.com"
    
    # Regional pages
    REGION_URLS = {
        "Banja Luka": "/banja-luka/?lang=bs",
        "Čelinac": "/celinac/?lang=bs",
        "Gradiška": "/gradiska-isklj/?lang=bs",
        "Kozarska Dubica": "/kozarska-dubica/?lang=bs",
        "Laktaši": "/laktasi/?lang=bs",
        "Mrkonjić Grad": "/mrkonjic-grad/?lang=bs",
        "Novi Grad": "/novi-grad/?lang=bs",
        "Prijedor": "/prijedor/?lang=bs",
        "Prnjavor": "/prnjavor/?lang=bs",
        "Šipovo": "/sipovo/?lang=bs",
        "Srbac": "/srbac/?lang=bs",
    }
    
    def scrape(self) -> List[Outage]:
        """
        Scrape outage data from Elektrokrajina website.
        
        Returns:
            List of Outage objects
        """
        self.logger.info(f"Scraping {self.PROVIDER_NAME}...")
        outages = []
        
        for region, url_path in self.REGION_URLS.items():
            try:
                self.logger.debug(f"Fetching {region}...")
                url = f"{self.BASE_URL}{url_path}"
                region_outages = self._fetch_region_outages(url, region)
                outages.extend(region_outages)
                self._rate_limit(0.3)
            except Exception as e:
                self.logger.warning(f"Error fetching {region}: {e}")
                continue
        
        self.logger.info(f"Found {len(outages)} outages from {self.PROVIDER_NAME}")
        return outages
    
    def parse(self, html: str) -> List[Outage]:
        """
        Parse HTML content and extract outages.
        
        Args:
            html: HTML content to parse
            
        Returns:
            List of Outage objects
        """
        soup = BeautifulSoup(html, 'html.parser')
        outages = []
        
        # Find all outage tables
        tables = soup.find_all('table')
        
        for table in tables:
            outage = self._parse_outage_table(table, "Unknown")
            if outage:
                outages.append(outage)
        
        return outages
    
    def _fetch_region_outages(self, url: str, region: str) -> List[Outage]:
        """
        Fetch outages for a specific region.
        
        Args:
            url: URL of the region's outage page
            region: Region name
            
        Returns:
            List of Outage objects
        """
        response = self._get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        outages = []
        
        # Find all outage tables (each table is one outage)
        tables = soup.find_all('table')
        
        self.logger.debug(f"Found {len(tables)} tables in {region}")
        
        for table in tables:
            outage = self._parse_outage_table(table, region)
            if outage:
                outages.append(outage)
        
        return outages
    
    def _parse_outage_table(self, table, region: str) -> Optional[Outage]:
        """
        Parse an outage table into an Outage object.
        
        The table format is:
        - Row 1: Elektroenergetski objekat | Value (spans 3 cols)
        - Row 2: Datum isključenja | Dan | Vrijeme isključenja | Vrijeme uključenja
        - Row 3: Date value | Day value | Start time | End time
        - Row 4: Razlog isključenja | Reason (spans 3 cols)
        - Row 5: Naselja i ulice | Affected areas (spans 3 cols, highlighted)
        
        Args:
            table: BeautifulSoup table element
            region: Region name
            
        Returns:
            Outage object or None
        """
        try:
            rows = table.find_all('tr')
            if len(rows) < 5:
                return None
            
            # Extract data from rows
            # Row 0: Elektroenergetski objekat (power facility)
            facility_row = rows[0]
            facility_cells = facility_row.find_all('td')
            facility = ""
            if len(facility_cells) >= 2:
                facility = self._clean_text(facility_cells[1].get_text())
            
            # Skip header rows (check if first cell contains header text)
            first_cell = self._clean_text(facility_cells[0].get_text()) if facility_cells else ""
            if not first_cell or "elektroenergetski" not in first_cell.lower():
                return None
            
            # Row 2: Date, day, start time, end time
            data_row = rows[2]
            data_cells = data_row.find_all('td')
            
            if len(data_cells) < 4:
                return None
            
            date_str = self._clean_text(data_cells[0].get_text())
            day_name = self._clean_text(data_cells[1].get_text())
            time_start = self._clean_text(data_cells[2].get_text())
            time_end = self._clean_text(data_cells[3].get_text())
            
            # Row 3: Razlog isključenja (reason)
            reason_row = rows[3]
            reason_cells = reason_row.find_all('td')
            reason = ""
            if len(reason_cells) >= 2:
                reason = self._clean_text(reason_cells[1].get_text())
            
            # Row 4: Naselja i ulice (affected areas) - highlighted row
            areas_row = rows[4]
            areas_cells = areas_row.find_all('td')
            affected_areas = ""
            if len(areas_cells) >= 2:
                affected_areas = self._clean_text(areas_cells[1].get_text())
            
            # Parse date
            date_start = self._parse_date(date_str)
            if not date_start:
                return None
            
            # Normalize times
            time_start = self._parse_time(time_start)
            time_end = self._parse_time(time_end)
            
            return Outage(
                provider=self.PROVIDER_NAME,
                region=region,
                municipality=region,
                area=affected_areas,
                streets=affected_areas,
                date_start=date_start,
                time_start=time_start,
                time_end=time_end,
                reason=reason,
                facility=facility,
                raw_text=f"{facility} - {affected_areas}",
            )
            
        except Exception as e:
            self.logger.debug(f"Error parsing table: {e}")
            return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_str:
            return None
        
        date_str = date_str.strip().rstrip('.')
        
        # Try various formats
        formats = [
            "%d.%m.%Y",
            "%d.%m.%Y.",
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%d-%m-%Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Try regex extraction
        match = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})', date_str)
        if match:
            day, month, year = match.groups()
            if len(year) == 2:
                year = "20" + year
            try:
                return datetime(int(year), int(month), int(day))
            except ValueError:
                pass
        
        return None
    
    def _parse_time(self, time_str: str) -> Optional[str]:
        """
        Parse and normalize time string.
        
        Args:
            time_str: Time string to parse
            
        Returns:
            Normalized time string in HH:MM format or None
        """
        if not time_str:
            return None
        
        time_str = time_str.strip()
        
        # Replace . with :
        time_str = time_str.replace('.', ':')
        
        # Extract time pattern HH:MM
        match = re.search(r'(\d{1,2}):(\d{2})', time_str)
        if match:
            hour, minute = match.groups()
            return f"{int(hour):02d}:{minute}"
        
        # Try just HH format
        match = re.search(r'^(\d{1,2})$', time_str)
        if match:
            return f"{int(match.group(1)):02d}:00"
        
        return None
    
    def _clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace."""
        if not text:
            return ""
        return ' '.join(text.split()).strip()