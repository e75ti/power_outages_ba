import logging
import time
from typing import Tuple, Optional
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

class OutageGeocoder:
    """Geocodes municipality and area text into GPS coordinates."""
    
    def __init__(self, user_agent: str = "electricity-outage-scraper"):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.geolocator = Nominatim(user_agent=user_agent)
        
        # Cache to prevent spamming the API for the same towns
        self._cache = {}

    def get_coordinates(self, municipality: str, area: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Takes a municipality and area, returns (latitude, longitude).
        """
        # Clean up the search string
        search_query = f"{area}, {municipality}, Bosnia and Herzegovina"
        backup_query = f"{municipality}, Bosnia and Herzegovina"

        if search_query in self._cache:
            return self._cache[search_query]

        try:
            # Respect Nominatim's strict rate limit (1 request per second)
            time.sleep(1.1) 
            
            # 1. Try exact area first
            location = self.geolocator.geocode(search_query, timeout=10)
            
            # 2. Fallback to just the municipality/city if specific street fails
            if not location:
                self.logger.debug(f"Could not find exact area '{area}', falling back to '{municipality}'")
                time.sleep(1.1)
                location = self.geolocator.geocode(backup_query, timeout=10)

            if location:
                coords = (location.latitude, location.longitude)
                self._cache[search_query] = coords
                return coords
                
            self.logger.warning(f"Could not geocode: {search_query}")
            return None, None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            self.logger.error(f"Geocoding service error: {e}")
            return None, None
