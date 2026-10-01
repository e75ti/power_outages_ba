import logging
from typing import Tuple, Optional
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from geopy.extra.rate_limiter import RateLimiter

class OutageGeocoder:
    """Geocodes municipality and area text into GPS coordinates using Postgres caching."""
    
    def __init__(self, db_manager, user_email: str = "admin@example.com"):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db_manager = db_manager
        
        # Respectful User-Agent as per OSM Nominatim Policy
        user_agent = f"electricity-outage-scanner/1.0"
        self.geolocator = Nominatim(user_agent=user_agent)
        
        # Strict Rate Limiting (15s delay = 4 requests per minute for bulk jobs)
        self.geocode_limited = RateLimiter(
            self.geolocator.geocode,
            min_delay_seconds=15,
            error_wait_seconds=15
        )

    def get_coordinates(self, municipality: str, area: str) -> Tuple[Optional[float], Optional[float]]:
        """Takes a municipality and area, returns (latitude, longitude)."""
        search_query = f"{area}, {municipality}, Bosnia and Herzegovina"
        backup_query = f"{municipality}, Bosnia and Herzegovina"

        # 1. Check PostgreSQL Cache FIRST
        cached = self.db_manager.get_cached_coordinates(search_query)
        if cached:
            # If the database returns (-999.0, -999.0), it's a negative cache hit
            if cached[0] == -999.0:
                return None, None
            return cached

        try:
            self.logger.info(f"Nominatim API Call (15s delay) for: {search_query}")
            location = self.geocode_limited(search_query, timeout=10)
            
            if not location:
                self.logger.debug(f"Exact area failed, falling back to: {backup_query}")
                
                # Check cache for backup query before hitting API again
                cached_backup = self.db_manager.get_cached_coordinates(backup_query)
                if cached_backup:
                    if cached_backup[0] != -999.0:
                        self.db_manager.cache_coordinates(search_query, cached_backup[0], cached_backup[1])
                        return cached_backup
                else:
                    self.logger.info(f"Nominatim API Call (15s delay) for fallback: {backup_query}")
                    location = self.geocode_limited(backup_query, timeout=10)

            if location:
                # Success! Save to Postgres
                self.db_manager.cache_coordinates(search_query, location.latitude, location.longitude)
                self.db_manager.cache_coordinates(backup_query, location.latitude, location.longitude)
                return (location.latitude, location.longitude)
                
            self.logger.warning(f"Could not geocode: {search_query}")
            # NEGATIVE CACHING: Save fake coordinates (-999, -999) so we don't ask API again!
            self.db_manager.cache_coordinates(search_query, -999.0, -999.0) 
            return None, None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            self.logger.error(f"Geocoding service error: {e}")
            return None, None
