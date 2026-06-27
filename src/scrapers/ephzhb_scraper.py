"""Scraper for EPHZHB (Elektroprivreda HZ Herceg-Bosne) outage data."""

import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from src.models.outage import Outage
from src.scrapers.base_scraper import BaseScraper


class EPHZHBScraper(BaseScraper):
    """Scraper for EPHZHB planned outages."""
    
    PROVIDER_NAME = "EPHZHB"
    BASE_URL = "https://korisnicka.ephzhb.ba/EPHZHBSrvNew/GetDistOneUnsigned"
    
    # Area codes mapped to region names (extracted from API response)
    AREA_CODES = {
        "652d1f24-74de-43bb-bef7-3b4fdbef2914": "Poslovnica Elektro Čitluk",
        "2352d80a-cea1-4299-8a74-dcd7d577812e": "Poslovnica Elektro Neum",
        "faa2f623-22a7-4b15-84cc-106d5b78571f": "Poslovnica Elektro Stolac",
        "2d526df0-274b-468b-b2fb-632565128fdf": "Poslovnica Elektro Rama",
        "30a5cf07-92ef-4367-bc3d-c4540716f541": "Poslovnica Elektro Mostar",
        "9b0fa6d8-c50a-49be-971a-e12f0d7c5e8d": "Poslovnica Elektro Čapljina",
        "3e51788a-a903-4dcf-956b-a540a2f9917a": "Poslovnica Elektro Ravno",
        "9ea06ea2-51c4-46da-90b1-ab965f92d0a3": "Poslovnica Elektro Doljani",
        "9dda54da-43fe-43c9-90c3-32cbcadc33d4": "Poslovnica Elektro Široki Brijeg",
        "874cc237-f33c-46fe-9cb9-20b0f1f65fd3": "Poslovnica Elektro Grude",
        "6a156b39-2e15-4ed8-8df0-012c4f59cba3": "Poslovnica Elektro Posušje",
        "0ad88b9f-ea1e-42de-ae6f-5c9d9f96dba8": "Poslovnica Elektro Ljubuški",
        "17ff1531-8381-4763-948e-74970ac21a54": "Poslovnica Elektro Livno",
        "dd1e4299-cfb6-4320-b67d-d3930145ad51": "Poslovnica Elektro Tomislavgrad",
        "b940700f-b391-4fc6-b3a9-353e462400fb": "Poslovnica Elektro Kupres",
        "4a3d9ac1-df0e-4875-9683-1647165316b1": "Poslovnica Elektro Glamoč",
        "a854b59c-eaed-44cf-8413-c1bde5f1e1e5": "Poslovnica Elektro Grahovo",
        "698ec0c5-b832-4cc4-8a2f-9769f4420a79": "Poslovnica Elektro Drvar",
        "1ff81e44-8aa2-4f8c-b244-9c8ee14be8c8": "Poslovnica Elektro Orašje",
        "bbd58ec4-1a4d-4290-bb00-8677001409a2": "Poslovnica Elektro Domaljevac",
        "24589548-927a-456e-91a8-450c040aa9c0": "Poslovnica Elektro Odžak",
        "41f5b665-cf03-4f88-85b7-8119b358d088": "Poslovnica Elektro Novi Travnik",
        "fcd980f7-6f86-4909-b0ca-c4d734756a0b": "Poslovnica Elektro Busovača",
        "8d18fb5d-e8a1-4c92-80cc-eb9ecfd17814": "Poslovnica Elektro Vitez",
        "4d03f1af-9224-494f-a70c-e45168a6dbb0": "Poslovnica Elektro Nova Bila",
        "a7e9dde6-805b-4168-8c67-40778c82baf8": "Poslovnica Elektro Uskoplje",
        "afd61533-3b34-4c9b-b38c-b8bf19c4cddf": "Poslovnica Elektro Kiseljak",
        "cec5ad45-1d5a-4f71-9036-929d9cf141fb": "Poslovnica Elektro Kreševo",
        "dd293a7a-fb82-4cc7-b4d4-8b3fb8da8d34": "Poslovnica Elektro Fojnica",
        "86ad96ae-4a91-4710-a300-5e0737986870": "Poslovnica Elektro Vareš",
        "2d22e4f5-e37a-444f-93d9-c0f652f4825a": "Poslovnica Elektro Žepče",
        "1aca1283-e410-44e5-a7ad-e2b5b5e61170": "Poslovnica Elektro Novi Šeher",
        "16b47856-19e4-4361-9ba5-81ace6342c5c": "Poslovnica Elektro Usora",
        "d018ebab-0ed6-44fb-b27b-e79b271b4b19": "Poslovnica Elektro Jajce",
        "b8edde3a-0c0e-4c89-a741-15f142cd1252": "Poslovnica Elektro Dobretići",
    }
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """Initialize the EPHZHB scraper."""
        super().__init__(timeout=timeout, max_retries=max_retries)
        # Update headers for JSON API
        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Origin': 'https://korisnicka.ephzhb.ba',
            'Referer': 'https://korisnicka.ephzhb.ba/',
        })
    
    def scrape(self) -> List[Outage]:
        """
        Scrape outage data from EPHZHB API.
        
        Query each area code separately to get all outages.
        
        Returns:
            List of Outage objects
        """
        self.logger.info(f"Scraping {self.PROVIDER_NAME}...")
        outages = []
        seen_outages = set()  # Track unique outages to avoid duplicates
        
        # Query each area code
        for area_code, area_name in self.AREA_CODES.items():
            try:
                self.logger.debug(f"Fetching outages for {area_name}...")
                
                payload = {
                    "data": {
                        "platform": "3",
                        "version": "0.1",
                        "appId": "",
                        "areaCode": area_code
                    }
                }
                
                response = self._post(self.BASE_URL, json=payload)
                
                # Parse JSON response
                try:
                    json_data = response.json()
                except Exception as e:
                    self.logger.warning(f"Failed to parse JSON for {area_name}: {e}")
                    continue
                
                # Extract outages from distList
                dist_list = json_data.get('distList', [])
                
                if dist_list:
                    self.logger.debug(f"Found {len(dist_list)} items in distList for {area_name}")
                
                for item in dist_list:
                    outage = self._parse_dist_item(item)
                    if outage:
                        # Create unique key to avoid duplicates
                        unique_key = f"{outage.area}|{outage.date_start}|{outage.time_start}"
                        if unique_key not in seen_outages:
                            seen_outages.add(unique_key)
                            outages.append(outage)
                
                # Rate limit between requests
                self._rate_limit(0.3)
                
            except Exception as e:
                self.logger.warning(f"Error fetching {area_name}: {e}")
                continue
        
        self.logger.info(f"Found {len(outages)} outages from {self.PROVIDER_NAME}")
        return outages
    
    def parse(self, html: str) -> List[Outage]:
        """
        Parse method for compatibility with base class.
        EPHZHB uses JSON API, so this is not the primary parsing method.
        
        Args:
            html: HTML/JSON content to parse
            
        Returns:
            List of Outage objects
        """
        # Try to parse as JSON first
        try:
            import json
            json_data = json.loads(html)
            outages = []
            for item in json_data.get('distList', []):
                outage = self._parse_dist_item(item)
                if outage:
                    outages.append(outage)
            return outages
        except:
            return []
    
    def _parse_dist_item(self, item: Dict) -> Optional[Outage]:
        """
        Parse a single item from the distList array.
        
        JSON structure:
        {
            "areaName": "Poslovnica Elektro Neum",
            "areaCode": "2352d80a-cea1-4299-8a74-dcd7d577812e",
            "actDesc": "DV 10 kV Hutovo (naselja Vranjevo Selo, Meteriz, ...)",
            "start": "02.02.2026 10:00",
            "end": "02.02.2026 14:00"
        }
        
        Args:
            item: Dictionary containing outage data
            
        Returns:
            Outage object or None if parsing fails
        """
        try:
            area_name = item.get('areaName', '')
            area_code = item.get('areaCode', '')
            description = item.get('actDesc', '')
            start_str = item.get('start', '')
            end_str = item.get('end', '')
            
            if not description or not start_str:
                self.logger.debug(f"Skipping item with missing data: {item}")
                return None
            
            # Parse start datetime
            date_start, time_start = self._parse_datetime_string(start_str)
            
            # Parse end datetime
            _, time_end = self._parse_datetime_string(end_str)
            
            if not date_start:
                self.logger.debug(f"Could not parse start date from: {start_str}")
                return None
            
            # Extract municipality from area name
            municipality = area_name.replace("Poslovnica Elektro ", "")
            
            # Extract facility/line name and affected areas from description
            # Format: "DV 10 kV Hutovo (naselja Vranjevo Selo, Meteriz, ...)"
            facility = ""
            streets = description
            
            # Try to extract facility name (before parenthesis)
            paren_match = re.match(r'^([^(]+)\((.+)\)$', description)
            if paren_match:
                facility = paren_match.group(1).strip()
                streets = paren_match.group(2).strip()
                # Remove "naselja" prefix if present
                streets = re.sub(r'^naselja\s+', '', streets, flags=re.IGNORECASE)
            
            return Outage(
                provider=self.PROVIDER_NAME,
                region=area_name,
                municipality=municipality,
                area=description,
                streets=streets,
                date_start=date_start,
                time_start=time_start,
                time_end=time_end,
                reason=facility,  # Use facility as reason
                raw_text=f"{area_name}: {description} ({start_str} - {end_str})",
            )
            
        except Exception as e:
            self.logger.debug(f"Error parsing dist item: {e} - Item: {item}")
            return None
    
    def _parse_datetime_string(self, datetime_str: str) -> Tuple[Optional[datetime], Optional[str]]:
        """
        Parse a datetime string like "02.02.2026 10:00".
        
        Args:
            datetime_str: Datetime string in format "DD.MM.YYYY HH:MM"
            
        Returns:
            Tuple of (datetime object, time string "HH:MM")
        """
        if not datetime_str:
            return None, None
        
        datetime_str = datetime_str.strip()
        
        # Pattern: DD.MM.YYYY HH:MM
        pattern = r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})'
        match = re.match(pattern, datetime_str)
        
        if match:
            day, month, year, hour, minute = match.groups()
            try:
                date_obj = datetime(int(year), int(month), int(day))
                time_str = f"{int(hour):02d}:{minute}"
                return date_obj, time_str
            except ValueError as e:
                self.logger.debug(f"Invalid date values: {e}")
                return None, None
        
        # Try alternative pattern without time
        date_pattern = r'(\d{1,2})\.(\d{1,2})\.(\d{4})'
        date_match = re.match(date_pattern, datetime_str)
        
        if date_match:
            day, month, year = date_match.groups()
            try:
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj, None
            except ValueError:
                pass
        
        return None, None
    
    def _clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace."""
        if not text:
            return ""
        return ' '.join(text.split()).strip()