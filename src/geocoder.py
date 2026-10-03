import logging
import re
from typing import Tuple, Optional
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from geopy.extra.rate_limiter import RateLimiter

from src.config.settings import load_config

class OutageGeocoder:
    """Geocodes municipality and area text into GPS coordinates using Postgres caching."""
    
    def __init__(self, db_manager):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db_manager = db_manager
        
        config = load_config()
        user_email = config.get("geolocator_email") or "wrongconfig@checkyourlogs"
        
        self.logger.info(f"Initialized Nominatim Geocoder v3.1 with email: {user_email}")
	if user_email == 'wrongconfig@checkyourlogs':
            self.logger.error("Huge issue! Email is set to not what it should be! Abort!")
        user_agent = f"ElectricityOutageScraper/3.1 (BiH Infrastructure Monitor; contact: {user_email})"
        self.geolocator = Nominatim(user_agent=user_agent)

        # 15s delay = 4 requests per minute (OSM Compliant)
        self.geocode_limited = RateLimiter(
            self.geolocator.geocode,
            min_delay_seconds=15,
            error_wait_seconds=15
        )

    def _clean_area(self, area: str) -> str:
        """Strips out house numbers, ranges, and utility jargon (TS, DV 10kV, etc.) to get real locations."""
        if not area:
            return ""
        
        # 1. Remove common electrical infrastructure prefixes (TS, DV, NNM, etc.)
        cleaned = re.sub(r'^(TS|DV\s*\d+\s*kV|NNM|Kbr|Br\.)\s*', '', area, flags=IGNORECASE if 'IGNORECASE' in globals() else re.IGNORECASE).strip()
        
        # 2. Strip out house numbers and ranges
        base_area = re.split(r'\d|,', cleaned)[0].strip()
        return base_area if len(base_area) > 2 else cleaned.split(',')[0].strip()

    def get_coordinates(self, municipality: str, area: str) -> Tuple[Optional[float], Optional[float]]:
        """Takes a municipality and area, returns (latitude, longitude)."""
        clean_area_name = self._clean_area(area)
        
        # Handle "Nepoznato" or empty municipalities gracefully
        is_unknown_muni = not municipality or municipality.lower() in ["nepoznato", "unknown", "n/a", ""]
        
        if is_unknown_muni:
            search_query = f"{clean_area_name}, Bosnia and Herzegovina"
            backup_query = "Bosnia and Herzegovina"
        else:
            search_query = f"{clean_area_name}, {municipality}, Bosnia and Herzegovina"
            backup_query = f"{municipality}, Bosnia and Herzegovina"

        # 1. Check PostgreSQL Cache FIRST
        cached = self.db_manager.get_cached_coordinates(search_query)
        if cached:
            if cached[0] == -999.0:
                return None, None
            return cached

        try:
            self.logger.info(f"Nominatim API Call for: {search_query}")
            location = self.geocode_limited(search_query, timeout=10)
            
            if not location and not is_unknown_muni:
                # Try fallback without the specific area name (just municipality)
                cached_backup = self.db_manager.get_cached_coordinates(backup_query)
                if cached_backup:
                    if cached_backup[0] != -999.0:
                        self.db_manager.cache_coordinates(search_query, cached_backup[0], cached_backup[1])
                        return cached_backup
                else:
                    self.logger.info(f"Nominatim API Fallback for: {backup_query}")
                    location = self.geocode_limited(backup_query, timeout=10)

            if location:
                self.db_manager.cache_coordinates(search_query, location.latitude, location.longitude)
                if not is_unknown_muni:
                    self.db_manager.cache_coordinates(backup_query, location.latitude, location.longitude)
                return (location.latitude, location.longitude)
                
            self.logger.warning(f"Could not geocode: {search_query}")
            self.db_manager.cache_coordinates(search_query, -999.0, -999.0) # Negative cache
            return None, None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            self.logger.error(f"Geocoding service error: {e}")
            return None, None
