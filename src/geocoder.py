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
        
        # Učitaj konfiguraciju preko postojećeg sistema u aplikaciji
        config = load_config()
        # Traži GEOLOCATOR_EMAIL u config-u, a ako ga nema, koristi default
        user_email = config.get("GEOLOCATOR_EMAIL", "outage.pipeline.support@proton.me")
        
        # OSM-compliant User-Agent
        user_agent = f"ElectricityOutageScraper/2.0 (BiH Infrastructure Monitor; contact: {user_email})"
        self.geolocator = Nominatim(user_agent=user_agent)
        
        # 15s delay = 4 requests per minute (OSM Compliant)
        self.geocode_limited = RateLimiter(
            self.geolocator.geocode, 
            min_delay_seconds=15,
            error_wait_seconds=15
        )

    def _clean_area(self, area: str) -> str:
        """Strips out massive lists of house numbers and ranges to prevent 400 errors."""
        if not area:
            return ""
        base_area = re.split(r'\d|,', area)[0].strip()
        return base_area if len(base_area) > 2 else area.split(',')[0].strip()

    def get_coordinates(self, municipality: str, area: str) -> Tuple[Optional[float], Optional[float]]:
        """Takes a municipality and area, returns (latitude, longitude)."""
        clean_area_name = self._clean_area(area)
        
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
            
            if not location:
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
                self.db_manager.cache_coordinates(backup_query, location.latitude, location.longitude)
                return (location.latitude, location.longitude)
                
            self.logger.warning(f"Could not geocode: {search_query}")
            self.db_manager.cache_coordinates(search_query, -999.0, -999.0) # Negative cache
            return None, None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            self.logger.error(f"Geocoding service error: {e}")
            return None, None
