"""Scraper for Elektro Doboj outage data."""

import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup

from src.models.outage import Outage
from src.scrapers.base_scraper import BaseScraper


class ElektroDobojScraper(BaseScraper):
    """Scraper for Elektro Doboj planned outages."""
    
    PROVIDER_NAME = "Elektro Doboj"
    BASE_URL = "https://www.elektrodoboj.net/UsluzniCentar/PlaniraniPrekidi"
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """Initialize the Elektro Doboj scraper."""
        super().__init__(timeout=timeout, max_retries=max_retries)
        # This site uses ASP.NET with AJAX
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
    
    def scrape(self) -> List[Outage]:
        """
        Scrape outage data from Elektro Doboj website.
        
        Returns:
            List of Outage objects
        """
        self.logger.info(f"Scraping {self.PROVIDER_NAME}...")
        outages = []
        
        try:
            # Make GET request first to get the page
            response = self._get(self.BASE_URL)
            outages = self.parse(response.text)
            
            self.logger.info(f"Found {len(outages)} outages from {self.PROVIDER_NAME}")
            
        except Exception as e:
            self.logger.error(f"Error scraping {self.PROVIDER_NAME}: {e}")
            raise
        
        return outages
    
    def parse(self, html: str) -> List[Outage]:
        """
        Parse HTML content and extract outages.
        
        Args:
            html: HTML content to parse
            
        Returns:
            List of Outage objects
        """
        outages = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all outage cards - they have both col-md-6 and col-sm-6 classes
        outage_cards = soup.find_all('div', class_='col-md-6')
        
        self.logger.debug(f"Found {len(outage_cards)} potential outage cards")
        
        for i, card in enumerate(outage_cards):
            # Skip cards that don't have the right structure
            if not card.find('span', id=re.compile(r'Label2')):
                continue
                
            outage = self._parse_outage_card(card)
            if outage:
                outages.append(outage)
        
        return outages
    
    def _parse_outage_card(self, card) -> Optional[Outage]:
        """
        Parse a single outage card.
        
        Args:
            card: BeautifulSoup div element representing one outage
            
        Returns:
            Outage object or None if parsing fails
        """
        try:
            # Find specific span elements by ID patterns
            unit_span = card.find('span', id=re.compile(r'Label1'))
            transformer_span = card.find('span', id=re.compile(r'lblPrikaz'))
            start_span = card.find('span', id=re.compile(r'Label2'))
            end_span = card.find('span', id=re.compile(r'Label3'))
            
            # Extract text content
            unit = ""
            transformer = ""
            start_datetime = ""
            end_datetime = ""
            
            if unit_span:
                text = unit_span.get_text()
                if "Теренска јединица:" in text:
                    unit = text.split("Теренска јединица:")[-1].strip()
            
            if transformer_span:
                text = transformer_span.get_text()
                if "Трафо станица:" in text:
                    transformer = text.split("Трафо станица:")[-1].strip()
            
            if start_span:
                text = start_span.get_text()
                if "Вријеме почетка" in text:
                    # Extract everything after the last colon
                    parts = text.split(":")
                    if len(parts) >= 2:
                        start_datetime = ":".join(parts[-2:]).strip()
            
            if end_span:
                text = end_span.get_text()
                if "Вријеме завршетка:" in text:
                    parts = text.split(":")
                    if len(parts) >= 2:
                        end_datetime = ":".join(parts[-2:]).strip()
            
            # Extract reason and description from links
            links = card.find_all('a')
            reason = ""
            description = ""
            affected_areas = ""
            
            for link in links:
                link_text = self._clean_text(link.get_text())
                
                # First short link is usually the reason
                if len(link_text) < 50 and not reason:
                    reason = link_text
                
                # Second longer link contains full description
                elif len(link_text) > 50:
                    description = link_text
                    
                    # Extract affected areas from description
                    area_match = re.search(r'следећим локацијама\s+([^,]+(?:\([^)]+\))?)', description)
                    if area_match:
                        affected_areas = area_match.group(1).strip()
            
            # Parse date from start_datetime (format: "06-02-26 09:00")
            if not start_datetime:
                self.logger.debug(f"No start datetime found in card")
                return None
            
            # Extract date part
            date_match = re.search(r'(\d{2}[-/]\d{2}[-/]\d{2,4})', start_datetime)
            if not date_match:
                self.logger.debug(f"Could not extract date from: {start_datetime}")
                return None
            
            date_str = date_match.group(1)
            date_start = self._parse_date(date_str)
            
            if not date_start:
                self.logger.debug(f"Could not parse date: {date_str}")
                return None
            
            # Extract time parts
            start_time_str = self._extract_time(start_datetime)
            end_time_str = self._extract_time(end_datetime)
            
            # Use affected_areas if available, otherwise use transformer info
            area_info = affected_areas if affected_areas else transformer
            
            return Outage(
                provider=self.PROVIDER_NAME,
                region=unit,
                municipality=unit,
                area=area_info,
                streets=affected_areas,
                date_start=date_start,
                time_start=start_time_str,
                time_end=end_time_str,
                reason=reason,
                facility=transformer,
                raw_text=f"{unit} - {transformer}: {description[:100]}..." if description else f"{unit} - {transformer}",
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing outage card: {e}", exc_info=True)
            return None
    
    def _extract_time(self, time_str: str) -> Optional[str]:
        """
        Extract time from a string like "06-02-26 09:00".
        
        Args:
            time_str: String containing date and time
            
        Returns:
            Time string in HH:MM format or None
        """
        if not time_str:
            return None
        
        # Look for time pattern HH:MM
        time_match = re.search(r'(\d{1,2}):(\d{2})', time_str)
        if time_match:
            hour, minute = time_match.groups()
            return f"{int(hour):02d}:{minute}"
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        # Handle DD-MM-YY format (06-02-26)
        match = re.match(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', date_str)
        if match:
            day, month, year = match.groups()
            
            # Convert 2-digit year to 4-digit
            if len(year) == 2:
                year_int = int(year)
                if year_int <= 50:  # Assume 00-50 means 20xx
                    year = f"20{year}"
                else:  # 51-99 means 19xx
                    year = f"19{year}"
            
            try:
                return datetime(int(year), int(month), int(day))
            except ValueError:
                pass
        
        return None
    
    def _clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace."""
        if not text:
            return ""
        return ' '.join(text.split()).strip()