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
    
    # Check both the legacy Latin paths and the active Cyrillic paths
    REGION_URLS = {
        # Legacy Latin
        "Banja Luka (L)": "/banja-luka/?lang=bs",
        "Čelinac (L)": "/celinac/?lang=bs",
        "Gradiška (L)": "/gradiska-isklj/?lang=bs",
        
        # Active Cyrillic (Lowercase hex forced bypass)
        "Banja Luka": "/%d0%b1%d0%b0%d1%9a%d0%b0-3/",
        "Gradiška": "/gradiska-isklj/",
        "Kozarska Dubica": "/%d0%ba%d0%be%d0%b7%d0%b0%d1%80%d1%81%d0%ba%d0%b0-%d0%b4%d1%83%d0%b1%d0%b8%d1%86%d0%b0/",
        "Laktaši": "/%d0%bb%d0%b0%d0%ba%d1%82%d0%b0%d1%88%d0%b8/",
        "Mrkonjić Grad": "/%d0%bc%d1%80%d0%ba%d0%be%d1%9a%d0%b8%d1%9b-%d0%b3%d1%80%d0%b0%d0%b4/",
        "Novi Grad": "/%d0%bd%d0%be%d0%b2%d0%b8-%d0%b3%d1%80%d0%b0%d0%b4/",
        "Prnjavor": "/%d0%bf%d1%80%d1%9a%d0%b0%d0%b2%d0%be%d1%80/",
        "Prijedor": "/%d0%bf%d1%80%d0%b8%d1%98%d0%b5%d0%b4%d0%be%d1%80/",
        "Srbac": "/%d1%81%d1%80%d0%b1%d0%b0%d1%86/",
        "Čelinac": "/celinac/",
        "Šipovo": "/sipovo/"
    }
    
    def scrape(self) -> List[Outage]:
        self.logger.info(f"Scraping {self.PROVIDER_NAME}...")
        outages = []
        
        for region_key, url_path in self.REGION_URLS.items():
            try:
                # Strip the Cyrillic marker for clean database insertion
                clean_region = region_key.replace(" (Ћ)", "")
                
                self.logger.debug(f"Fetching {region_key}...")
                url = f"{self.BASE_URL}{url_path}"
                region_outages = self._fetch_region_outages(url, clean_region)
                outages.extend(region_outages)
                self._rate_limit(0.3)
            except Exception as e:
                self.logger.warning(f"Error fetching {region_key}: {e}")
                continue
        
        self.logger.info(f"Found {len(outages)} outages from {self.PROVIDER_NAME}")
        return outages
    
    def _fetch_region_outages(self, url: str, region: str) -> List[Outage]:
        response = self._get(url)
        
        # If it's a 404, parsing it will just yield 0 tables anyway, which is safe
        decoded_html = response.content.decode('utf-8', errors='replace')
        soup = BeautifulSoup(decoded_html, 'html.parser')
        
        outages = []
        tables = soup.find_all('table')
        
        if tables:
            self.logger.debug(f"Found {len(tables)} tables in {region}")
        
        for table in tables:
            outage = self._parse_outage_table(table, region)
            if outage:
                outages.append(outage)
        
        return outages
    
    def _parse_outage_table(self, table, region: str) -> Optional[Outage]:
        """
        Dynamically parse an outage table by hunting for keywords in BOTH
        Latin and Cyrillic, ignoring strict row indexing.
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
                
                cell_texts = [self._clean_text(c.get_text()) for c in cells]
                first_cell_lower = cell_texts[0].lower()
                
                if ("elektroenergetski" in first_cell_lower or "електроенергетски" in first_cell_lower) and len(cell_texts) >= 2:
                    facility = cell_texts[1]
                elif ("razlog" in first_cell_lower or "разлог" in first_cell_lower) and len(cell_texts) >= 2:
                    reason = cell_texts[1]
                elif ("naselja" in first_cell_lower or "ulice" in first_cell_lower or "насеља" in first_cell_lower or "улице" in first_cell_lower) and len(cell_texts) >= 2:
                    affected_areas = cell_texts[1]
                elif len(cell_texts) >= 4:
                    if re.search(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', cell_texts[0]):
                        date_str = cell_texts[0]
                        time_start = cell_texts[2]  
                        time_end = cell_texts[3]    

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
