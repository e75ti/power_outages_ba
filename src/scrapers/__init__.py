"""Scrapers package for electricity outage data collection."""

from .base_scraper import BaseScraper
from .elektrobijeljina_scraper import ElektroBijeljinaScraper
from .elektrodoboj_scraper import ElektroDobojScraper
from .elektrohercegovina_scraper import ElektroHercegovinaScraper
from .elektrokrajina_scraper import ElektroKrajinaScraper
from .elektropale_scraper import ElektroPaleScraper
from .epbih_scraper import EPBiHScraper
from .ephzhb_scraper import EPHZHBScraper
from .scraper_manager import ScraperManager

__all__ = [
    "BaseScraper",
    "EPBiHScraper",
    "EPHZHBScraper",
    "ElektroKrajinaScraper",
    "ElektroDobojScraper",
    "ElektroBijeljinaScraper",
    "ElektroPaleScraper",
    "ElektroHercegovinaScraper",
    "ScraperManager",
]
