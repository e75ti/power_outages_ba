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
    
    def _fetch_region_outages(self, url: str, region: str) -> List[Outage]:
        response = self._get(url)
        
        # FIX: Decode bytes manually to guarantee UTF-8 Bosnian characters
        decoded_html = response.content.decode('utf-8', errors='replace')
        soup = BeautifulSoup(decoded_html, 'html.parser')
        
        outages = []
        tables = soup.find_all('table')
        self.logger.debug(f"Found {len(tables)} tables in {region}")
        
        for table in tables:
            outage = self._parse_outage_table(table, region)
            if outage:
                outages.append(outage)
        
        return outages
    
    def _parse_outage_table(self, table, region: str) -> Optional[Outage]:
        """
        Dynamically parse an outage table by hunting for keywords, 
        ignoring strict row indexing so it won't break on HTML changes.
        """
        facility = ""
        date_str = ""
        time_start = ""
        time_end = ""
        reason = ""
        affected_areas = ""
        
        try:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue
                
                # Clean up the text for all cells in the row
                cell_texts = [self._clean_text(c.get_text()) for c in cells]
                first_cell_lower = cell_texts[0].lower()
                
                # Hunt for specific labels
                if "elektroenergetski" in first_cell_lower and len(cell_texts) >= 2:
                    facility = cell_texts[1]
                elif "razlog" in first_cell_lower and len(cell_texts) >= 2:
                    reason = cell_texts[1]
                elif ("naselja" in first_cell_lower or "ulice" in first_cell_lower) and len(cell_texts) >= 2:
                    affected_areas = cell_texts[1]
                elif len(cell_texts) >= 4:
                    # Look for a date string in the first cell (e.g. 06.07.2026.)
                    if re.search(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', cell_texts[0]):
                        date_str = cell_texts[0]
                        time_start = cell_texts[2]  # Vrijeme isključenja
                        time_end = cell_texts[3]    # Vrijeme uključenja

            # If we didn't extract the bare minimum, this isn't a valid outage table
            if not facility and not affected_areas:
                return None
            
            date_start = self._parse_date(date_str)
            if not date_start:
                return None
            
            time_start = self._parse_time(time_start)
            time_end = self._parse_time(time_end)
            
            return Outage(
                provider=self.PROVIDER_NAME,
                region=region,
                municipality=region,
                area=affected_areas or facility,
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
    
    def parse(self, html: str) -> List[Outage]:
        """Fallback for base compatibility."""
        soup = BeautifulSoup(html, 'html.parser')
        outages = []
        tables = soup.find_all('table')
        for table in tables:
            outage = self._parse_outage_table(table, "Unknown")
            if outage:
                outages.append(outage)
        return outages

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        
        date_str = date_str.strip().rstrip('.')
        
        formats = ["%d.%m.%Y", "%d.%m.%Y.", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    
    def _parse_time(self, time_str: str) -> Optional[str]:
        if not time_str:
            return None
        
        time_str = time_str.strip().replace('.', ':')
        match = re.search(r'(\d{1,2}):(\d{2})', time_str)
        if match:
            hour, minute = match.groups()
            return f"{int(hour):02d}:{minute}"
        
        match = re.search(r'^(\d{1,2})$', time_str)
        if match:
            return f"{int(match.group(1)):02d}:00"
        
        return None
    
    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        return ' '.join(text.split()).strip()
