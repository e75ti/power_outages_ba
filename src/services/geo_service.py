"""Geolocation matching service."""

import logging
import re
from typing import List, Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from src.models.outage import Outage
from src.models.subscription import Subscription
from src.utils.config import load_config


class GeoService:
    """
    Service for geolocation-based matching between outages and subscriptions.
    
    Two-tier matching strategy:
    1. Direct Match: String matching of street names (all users)
    2. Area Match: Geographic proximity matching (rural users only)
    """
    
    # Major cities where area matching should be disabled
    MAJOR_CITIES = [
        "sarajevo", "banja luka", "banjaluka", "tuzla", "zenica", "mostar",
        "bijeljina", "prijedor", "brčko", "brcko", "doboj", "trebinje",
        "bihać", "bihac", "cazin", "gradiška", "gradiska", "zvornik",
    ]
    
    def __init__(self):
        """Initialize the geo service."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = load_config()
        
        user_agent = self.config.get("nominatim_user_agent", "electricity-outage-scraper")
        self.geolocator = Nominatim(user_agent=user_agent, timeout=10)
        
        self.enable_geo_matching = self.config.get("enable_geo_matching", True)
        self.default_radius_km = self.config.get("geo_match_radius_km", 5.0)
    
    def find_matching_subscriptions(
        self,
        outage: Outage,
        subscriptions: List[Subscription],
    ) -> List[Subscription]:
        """
        Find all subscriptions that match an outage.
        
        Args:
            outage: Outage to match against
            subscriptions: List of subscriptions to check
            
        Returns:
            List of matching subscriptions
        """
        matches = []
        
        for subscription in subscriptions:
            if self.matches(outage, subscription):
                matches.append(subscription)
        
        return matches
    
    def matches(self, outage: Outage, subscription: Subscription) -> bool:
        """
        Check if an outage matches a subscription.
        
        Args:
            outage: Outage to check
            subscription: Subscription to check against
            
        Returns:
            True if the outage affects the subscribed location
        """
        # Tier 1: Direct string matching (always enabled)
        if self._direct_match(outage, subscription):
            self.logger.debug(f"Direct match: {subscription.street_name} in {outage.area}")
            return True
        
        # Tier 2: Area-based geo matching (only for rural subscriptions)
        if subscription.is_rural and self.enable_geo_matching:
            if not self._is_major_city(subscription.municipality):
                if self._area_match(outage, subscription):
                    self.logger.debug(f"Area match: {subscription.street_name} near {outage.area}")
                    return True
        
        return False
    
    def _direct_match(self, outage: Outage, subscription: Subscription) -> bool:
        """
        Check for direct string match between subscription and outage.
        
        Args:
            outage: Outage to check
            subscription: Subscription to check against
            
        Returns:
            True if street name matches
        """
        street = self._normalize_text(subscription.street_name)
        municipality = self._normalize_text(subscription.municipality)
        
        # Check in various outage fields
        outage_texts = [
            self._normalize_text(outage.area),
            self._normalize_text(outage.streets),
            self._normalize_text(outage.municipality),
            self._normalize_text(outage.region),
            self._normalize_text(outage.raw_text),
        ]
        
        # First check municipality match
        municipality_match = any(municipality in text for text in outage_texts)
        
        if not municipality_match:
            # Check if outage municipality matches subscription
            outage_municipality = self._normalize_text(outage.municipality)
            if municipality != outage_municipality:
                return False
        
        # Then check street match
        for text in outage_texts:
            if street in text:
                return True
        
        # Try fuzzy matching for common variations
        if self._fuzzy_street_match(street, outage_texts):
            return True
        
        return False
    
    def _fuzzy_street_match(self, street: str, texts: List[str]) -> bool:
        """
        Perform fuzzy matching for street names.
        
        Handles common variations like:
        - "ul." vs "ulica"
        - Missing diacritics
        - Word order differences
        
        Args:
            street: Street name to find
            texts: List of texts to search in
            
        Returns:
            True if fuzzy match found
        """
        # Remove common prefixes
        street_clean = re.sub(r'^(ul\.?|ulica)\s*', '', street)
        
        for text in texts:
            text_clean = re.sub(r'(ul\.?|ulica)\s*', '', text)
            
            if street_clean in text_clean:
                return True
            
            # Check if all words from street appear in text
            street_words = street_clean.split()
            if len(street_words) >= 2:
                if all(word in text_clean for word in street_words):
                    return True
        
        return False
    
    def _area_match(self, outage: Outage, subscription: Subscription) -> bool:
        """
        Check if outage area is geographically close to subscription location.
        
        Args:
            outage: Outage to check
            subscription: Subscription to check against
            
        Returns:
            True if within radius
        """
        # Get subscription coordinates
        sub_coords = subscription.coordinates
        if not sub_coords:
            sub_coords = self._geocode_location(
                subscription.street_name,
                subscription.municipality,
            )
            if not sub_coords:
                return False
        
        # Get outage coordinates
        outage_coords = outage.coordinates
        if not outage_coords:
            outage_coords = self._geocode_location(
                outage.area,
                outage.municipality,
            )
            if not outage_coords:
                return False
        
        # Calculate distance
        distance = geodesic(sub_coords, outage_coords).kilometers
        radius = subscription.notify_radius_km or self.default_radius_km
        
        return distance <= radius
    
    def _geocode_location(
        self,
        street: str,
        municipality: str,
    ) -> Optional[Tuple[float, float]]:
        """
        Geocode a location to coordinates.
        
        Args:
            street: Street name
            municipality: Municipality name
            
        Returns:
            Tuple of (latitude, longitude) or None
        """
        # Build query
        query = f"{street}, {municipality}, Bosnia and Herzegovina"
        
        try:
            location = self.geolocator.geocode(query)
            if location:
                return (location.latitude, location.longitude)
            
            # Try with just municipality
            location = self.geolocator.geocode(f"{municipality}, Bosnia and Herzegovina")
            if location:
                return (location.latitude, location.longitude)
                
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            self.logger.warning(f"Geocoding failed for {query}: {e}")
        
        return None
    
    def _is_major_city(self, municipality: str) -> bool:
        """
        Check if a municipality is a major city.
        
        Args:
            municipality: Municipality name
            
        Returns:
            True if major city (area matching disabled)
        """
        normalized = self._normalize_text(municipality)
        return normalized in self.MAJOR_CITIES
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        
        # Convert Cyrillic to Latin (basic)
        cyrillic_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'ђ': 'đ',
            'е': 'e', 'ж': 'ž', 'з': 'z', 'и': 'i', 'ј': 'j', 'к': 'k',
            'л': 'l', 'љ': 'lj', 'м': 'm', 'н': 'n', 'њ': 'nj', 'о': 'o',
            'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'ћ': 'ć', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'č', 'џ': 'dž', 'ш': 'š',
        }
        
        for cyr, lat in cyrillic_map.items():
            text = text.replace(cyr, lat)
        
        # Remove diacritics for matching
        diacritic_map = {
            'č': 'c', 'ć': 'c', 'š': 's', 'ž': 'z', 'đ': 'd',
        }
        
        normalized = text
        for char, replacement in diacritic_map.items():
            normalized = normalized.replace(char, replacement)
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def geocode_address(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Public method to geocode an address.
        
        Args:
            address: Full address string
            
        Returns:
            Tuple of (latitude, longitude) or None
        """
        try:
            location = self.geolocator.geocode(f"{address}, Bosnia and Herzegovina")
            if location:
                return (location.latitude, location.longitude)
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            self.logger.warning(f"Geocoding failed for {address}: {e}")
        
        return None