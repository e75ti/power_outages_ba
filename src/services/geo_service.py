# src/services/geo_service.py
"""Geolocation matching service."""

import logging
import re
import time
from typing import List, Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from src.models.outage import Outage
from src.models.subscription import Subscription
from src.config.settings import load_config


class GeoService:
    """Service for geolocation-based matching between outages and subscriptions."""
    
    MAJOR_CITIES = [
        "sarajevo", "banja luka", "banjaluka", "tuzla", "zenica", "mostar",
        "bijeljina", "prijedor", "brčko", "brcko", "doboj", "trebinje",
        "bihać", "bihac", "cazin", "gradiška", "gradiska", "zvornik",
    ]
    
    def __init__(self, db_manager=None):
        """
        Initialize the geo service.
        Args:
            db_manager: Database manager instance for caching coordinates.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = load_config()
        self.db = db_manager
        
        user_agent = self.config.get("nominatim_user_agent", "electricity-outage-scraper-ba")
        self.geolocator = Nominatim(user_agent=user_agent, timeout=10)
        
        self.enable_geo_matching = self.config.get("enable_geo_matching", True)
        self.default_radius_km = self.config.get("geo_match_radius_km", 5.0)
    
    def find_matching_subscriptions(self, outage: Outage, subscriptions: List[Subscription]) -> List[Subscription]:
        return [sub for sub in subscriptions if self.matches(outage, sub)]
    
    def matches(self, outage: Outage, subscription: Subscription) -> bool:
        # Tier 0: Provider preference check
        if subscription.provider_preference and outage.provider not in subscription.provider_preference:
            return False

        # Tier 1: Direct string matching
        if self._direct_match(outage, subscription):
            return True
        
        # Tier 2: Area-based geo matching
        if subscription.is_rural and self.enable_geo_matching:
            if not self._is_major_city(subscription.municipality):
                if self._area_match(outage, subscription):
                    return True
        
        return False
    
    def _direct_match(self, outage: Outage, subscription: Subscription) -> bool:
        street = self._normalize_text(subscription.street_name)
        municipality = self._normalize_text(subscription.municipality)
        
        outage_texts = [
            self._normalize_text(outage.area),
            self._normalize_text(outage.streets),
            self._normalize_text(outage.municipality),
            self._normalize_text(outage.region),
            self._normalize_text(outage.raw_text),
        ]
        
        municipality_match = any(municipality in text for text in outage_texts)
        if not municipality_match and municipality != self._normalize_text(outage.municipality):
            return False
            
        for text in outage_texts:
            if street in text:
                return True
                
        return self._fuzzy_street_match(street, outage_texts)
    
    def _fuzzy_street_match(self, street: str, texts: List[str]) -> bool:
        street_clean = re.sub(r'^(ul\.?|ulica)\s*', '', street)
        for text in texts:
            text_clean = re.sub(r'(ul\.?|ulica)\s*', '', text)
            if street_clean in text_clean:
                return True
            street_words = street_clean.split()
            if len(street_words) >= 2 and all(word in text_clean for word in street_words):
                return True
        return False
    
    def _area_match(self, outage: Outage, subscription: Subscription) -> bool:
        sub_coords = subscription.coordinates or self._geocode_location(subscription.street_name, subscription.municipality)
        if not sub_coords: return False
        
        outage_coords = outage.coordinates or self._geocode_location(outage.area, outage.municipality)
        if not outage_coords: return False
        
        distance = geodesic(sub_coords, outage_coords).kilometers
        radius = subscription.notify_radius_km or self.default_radius_km
        return distance <= radius
    
    def _geocode_location(self, street: str, municipality: str) -> Optional[Tuple[float, float]]:
        query = f"{street}, {municipality}, Bosnia and Herzegovina"
        
        # Check Database Cache First
        if self.db:
            cached = self.db.get_cached_coordinates(query)
            if cached:
                self.logger.debug(f"Geocache hit for: {query}")
                return cached

        # Strict OpenStreetMap Rate Limit (1 req / sec)
        time.sleep(1.1)
        
        try:
            self.logger.debug(f"Geocache miss, querying API for: {query}")
            location = self.geolocator.geocode(query) or self.geolocator.geocode(f"{municipality}, Bosnia and Herzegovina")
            
            if location:
                coords = (location.latitude, location.longitude)
                if self.db:
                    self.db.cache_coordinates(query, coords[0], coords[1])
                return coords
                
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            self.logger.warning(f"Geocoding failed for {query}: {e}")
        
        return None
    
    def _is_major_city(self, municipality: str) -> bool:
        return self._normalize_text(municipality) in self.MAJOR_CITIES
    
    def _normalize_text(self, text: str) -> str:
        if not text: return ""
        text = text.lower()
        
        cyrillic_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'ђ': 'đ', 'е': 'e', 'ж': 'ž', 'з': 'z', 'и': 'i', 'ј': 'j', 'к': 'k', 'л': 'l', 'љ': 'lj', 'м': 'm', 'н': 'n', 'њ': 'nj', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'ћ': 'ć', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'č', 'џ': 'dž', 'ш': 'š',
        }
        for cyr, lat in cyrillic_map.items(): text = text.replace(cyr, lat)
        
        diacritic_map = {'č': 'c', 'ć': 'c', 'š': 's', 'ž': 'z', 'đ': 'd'}
        for char, replacement in diacritic_map.items(): text = text.replace(char, replacement)
        
        return ' '.join(text.split())
