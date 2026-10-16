import logging
import re
from typing import Optional, Tuple

from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

from src.config.settings import load_config


class OutageGeocoder:
    """Geocodes municipality and area text into GPS coordinates using Postgres caching."""

    def __init__(self, db_manager):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db_manager = db_manager

        config = load_config()
        user_email = config.get("geolocator_email") or "wrongconfig@checkyourlogs"

        self.logger.info(
            f"Initialized Nominatim Geocoder v3.1 with email: {user_email}"
        )

        if user_email == "wrongconfig@checkyourlogs":
            self.logger.error(
                "Huge issue! Email is set to default! Please check your .env file."
            )

        user_agent = f"ElectricityOutageScraper/3.1 (BiH Infrastructure Monitor; contact: {user_email})"
        self.geolocator = Nominatim(user_agent=user_agent)

        # Neomatim 5s wait
        self.geocode_limited = RateLimiter(
            self.geolocator.geocode, min_delay_seconds=5, error_wait_seconds=10
        )

    def _clean_area(self, area: str) -> str:
        """Strips out house numbers, ranges, and utility jargon ONLY for OSM API."""
        if not area:
            return ""

        # 0. Clean "DV" / '"DV'
        area = re.sub(r"^[\-\"\'\s]+", "", area)

        # 1. Rm useless words
        garbage_keywords = [
            "TS ",
            "KV",
            "NN IZLAZ",
            "JEDAN NN",
            "DV 10",
            "DV 35",
            "LR 10",
            "DUNRS",
            "DV,",
            " DV ",
        ]
        if any(x in area.upper() for x in garbage_keywords) or area.upper().startswith(
            "DV"
        ):
            return "GARBAGE_IGNORE"

        # 2. Rm ()
        clean = re.sub(r"\(.*?\)", "", area)

        # 3. Rm badwords
        prefixes = r"(?i)^(sela:|naselja:|naseljena mjesta:|naselje|dio naselja:|ulica|ul\.|насеља:|дио насеља:|дијелови насеља:|дијелови улица:)\s*"
        clean = re.sub(prefixes, "", clean).strip()

        # 4. Take only 1st village
        clean = clean.split(",")[0].strip()
        clean = clean.split("-")[0].strip()

        # 6. Cut to first numb only
        clean = re.split(r"\d", clean)[0].strip()

        clean = re.sub(r"(?i)\b(bb|do|iza|ispod|bb\.|b\.b\.)\b", "", clean).strip()
        clean = clean.strip(" ,.-/")

        if len(clean) < 3:
            return "GARBAGE_IGNORE"

        return clean

    def get_coordinates(
        self, municipality: str, area: str
    ) -> Tuple[Optional[float], Optional[float]]:
        clean_area_name = self._clean_area(area)

        is_unknown_muni = not municipality or municipality.lower() in [
            "nepoznato",
            "unknown",
            "n/a",
            "",
        ]

        if is_unknown_muni:
            search_query = f"{clean_area_name}, Bosnia and Herzegovina"
        else:
            search_query = f"{clean_area_name}, {municipality}, Bosnia and Herzegovina"

        # If garbage, skip
        if clean_area_name == "GARBAGE_IGNORE" or len(clean_area_name) < 3:
            self.logger.info(f"Skipping garbage/short address: {area}")
            self.db_manager.cache_coordinates(search_query, -999.0, -999.0)
            return None, None

        # 1. Check PostgreSQL Cache
        cached = self.db_manager.get_cached_coordinates(search_query)
        if cached:
            if cached[0] == -999.0:
                return None, None
            return cached

        try:
            self.logger.info(f"Nominatim API Call for: {search_query}")
            location = self.geocode_limited(search_query, timeout=10)

            # No fallback to municipality. If not found, mark -999.0
            if location:
                self.db_manager.cache_coordinates(
                    search_query, location.latitude, location.longitude
                )
                return (location.latitude, location.longitude)
            else:
                self.logger.info(
                    f"Location not found on map, negative caching: {search_query}"
                )
                self.db_manager.cache_coordinates(search_query, -999.0, -999.0)
                return None, None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            self.logger.error(f"Geocoding service error: {e}")
            return None, None
