"""Scrapers package for electricity outage data collection."""

from .base_scraper import BaseScraper
from .epbih_scraper import EPBiHScraper
from .ephzhb_scraper import EPHZHBScraper
from .elektrokrajina_scraper import ElektroKrajinaScraper
from .elektrodoboj_scraper import ElektroDobojScraper
from .elektrobijeljina_scraper import ElektroBijeljinaScraper
from .elektropale_scraper import ElektroPaleScraper
from .scraper_manager import ScraperManager

__all__ = [
    'BaseScraper',
    'EPBiHScraper',
    'EPHZHBScraper',
    'ElektroKrajinaScraper',
    'ElektroDobojScraper',
    'ElektroBijeljinaScraper',
    'ElektroPaleScraper',
    'ScraperManager',
]
