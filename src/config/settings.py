# src/config/settings.py
"""Configuration utilities and settings."""

import os
from typing import Any, Dict
from dotenv import load_dotenv

def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables.
    Single source of truth for the application config.
    """
    load_dotenv()
    
    return {
        # Database (Supports SQLite locally or PostgreSQL via Docker)
        "DATABASE_URI": os.getenv("DATABASE_URI", "sqlite:///outages.db"),
        
        # Scraping Settings
        "scrape_interval_minutes": int(os.getenv("SCRAPE_INTERVAL_MINUTES", "30")),
        "request_timeout": int(os.getenv("REQUEST_TIMEOUT", "30")),
        "max_retries": int(os.getenv("MAX_RETRIES", "3")),
        
        # Web Push (VAPID) Settings
        "vapid_public_key": os.getenv("VAPID_PUBLIC_KEY", ""),
        "vapid_private_key": os.getenv("VAPID_PRIVATE_KEY", ""),
        "vapid_claims_email": os.getenv("VAPID_CLAIMS_EMAIL", "admin@example.com"),
        
        # Geocoding & Matching
        "nominatim_user_agent": os.getenv("NOMINATIM_USER_AGENT", "electricity-outage-scraper-ba"),
        "enable_geo_matching": os.getenv("ENABLE_GEO_MATCHING", "true").lower() == "true",
        "geo_match_radius_km": float(os.getenv("GEO_MATCH_RADIUS_KM", "5.0")),
        
        # Logging
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }
