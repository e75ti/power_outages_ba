"""Configuration utilities."""

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv


def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables.

    Returns:
        Dictionary with configuration values
    """
    # Load .env file if it exists
    load_dotenv()

    return {
        # Firebase
        "firebase_credentials_path": os.getenv("FIREBASE_CREDENTIALS_PATH", ""),
        "firebase_project_id": os.getenv("FIREBASE_PROJECT_ID", ""),
        # Scraping
        "scrape_interval_minutes": int(os.getenv("SCRAPE_INTERVAL_MINUTES", "30")),
        "request_timeout": int(os.getenv("REQUEST_TIMEOUT", "30")),
        "max_retries": int(os.getenv("MAX_RETRIES", "3")),
        # Web Push (VAPID)
        "vapid_public_key": os.getenv("VAPID_PUBLIC_KEY", ""),
        "vapid_private_key": os.getenv("VAPID_PRIVATE_KEY", ""),
        "vapid_claims_email": os.getenv("VAPID_CLAIMS_EMAIL", "admin@example.com"),
        # Geocoding
        "nominatim_user_agent": os.getenv(
            "NOMINATIM_USER_AGENT", "electricity-outage-scraper"
        ),
        # Geo Matching
        "enable_geo_matching": os.getenv("ENABLE_GEO_MATCHING", "true").lower()
        == "true",
        "geo_match_radius_km": float(os.getenv("GEO_MATCH_RADIUS_KM", "5.0")),
        # Logging
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get an environment variable."""
    return os.getenv(key, default)


def get_env_bool(key: str, default: bool = False) -> bool:
    """Get an environment variable as boolean."""
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def get_env_int(key: str, default: int = 0) -> int:
    """Get an environment variable as integer."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def get_env_float(key: str, default: float = 0.0) -> float:
    """Get an environment variable as float."""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default
