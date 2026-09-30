"""Main scraper orchestrator that coordinates all provider scrapers."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Type, Optional

from src.models.outage import Outage
from src.scrapers.base_scraper import BaseScraper
from src.scrapers.epbih_scraper import EPBiHScraper
from src.scrapers.ephzhb_scraper import EPHZHBScraper
from src.scrapers.elektrokrajina_scraper import ElektroKrajinaScraper
from src.scrapers.elektrodoboj_scraper import ElektroDobojScraper
from src.scrapers.elektrobijeljina_scraper import ElektroBijeljinaScraper
from src.scrapers.elektropale_scraper import ElektroPaleScraper

from src.metrics import OUTAGES_FOUND, SCRAPE_DURATION

class ScraperManager:
    """
    Main scraper orchestrator that coordinates all electricity provider scrapers.
    
    This class manages multiple scrapers and provides a unified interface
    for collecting outage data from all providers.
    """
    
    # Registry of available scrapers
    SCRAPERS: Dict[str, Type[BaseScraper]] = {
        "epbih": EPBiHScraper,
        "ephzhb": EPHZHBScraper,
        "elektrokrajina": ElektroKrajinaScraper,
        "elektrodoboj": ElektroDobojScraper,
        "elektrobijeljina": ElektroBijeljinaScraper,
        "elektropale": ElektroPaleScraper,
    }
    
    def __init__(
        self,
        enabled_scrapers: Optional[List[str]] = None,
        max_workers: int = 5,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize the scraper manager.
        
        Args:
            enabled_scrapers: List of scraper names to enable (None = all)
            max_workers: Maximum number of concurrent scraper threads
            timeout: Request timeout for each scraper
            max_retries: Maximum retry attempts for failed requests
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.max_workers = max_workers
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Initialize enabled scrapers
        if enabled_scrapers is None:
            enabled_scrapers = list(self.SCRAPERS.keys())
        
        self.scrapers: Dict[str, BaseScraper] = {}
        for name in enabled_scrapers:
            if name in self.SCRAPERS:
                self.scrapers[name] = self.SCRAPERS[name](
                    timeout=timeout,
                    max_retries=max_retries,
                )
            else:
                self.logger.warning(f"Unknown scraper: {name}")
    
    def scrape_all(self, parallel: bool = True) -> List[Outage]:
        """
        Run all enabled scrapers and collect outages.
        
        Args:
            parallel: If True, run scrapers in parallel
            
        Returns:
            List of all collected Outage objects
        """
        self.logger.info(f"Starting scrape of {len(self.scrapers)} providers...")
        
        if parallel:
            return self._scrape_parallel()
        else:
            return self._scrape_sequential()
    
    def _scrape_parallel(self) -> List[Outage]:
        """Run scrapers in parallel using ThreadPoolExecutor."""
        import time  # Ensure time is imported for metrics
        
        all_outages = []
        errors = []
        start_times = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all scraping tasks and record their start times
            future_to_name = {}
            for name, scraper in self.scrapers.items():
                start_times[name] = time.time()
                future_to_name[executor.submit(scraper.scrape)] = name
                
            # Collect results as they complete
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                scraper = self.scrapers[name]
                
                try:
                    outages = future.result()
                    all_outages.extend(outages)
                    self.logger.info(f"✅ {name}: {len(outages)} outages found")
                    
                    # --- SRE METRICS: Outages Found ---
                    OUTAGES_FOUND.labels(provider=scraper.PROVIDER_NAME).set(len(outages))
                    
                except Exception as e:
                    self.logger.error(f"❌ {name}: Scraping failed - {e}")
                    errors.append((name, str(e)))
                    
                finally:
                    # --- SRE METRICS: Execution Duration ---
                    duration = time.time() - start_times[name]
                    SCRAPE_DURATION.labels(provider=scraper.PROVIDER_NAME).observe(duration)
                    
        self.logger.info(f"Total outages collected: {len(all_outages)}")
        if errors:
            self.logger.warning(f"Failed scrapers: {[e[0] for e in errors]}")
            
        return all_outages

    def _scrape_sequential(self) -> List[Outage]:
        """Run scrapers sequentially."""
        all_outages = []
        errors = []
        
        for name, scraper in self.scrapers.items():
            start_time = time.time()
            try:
                self.logger.info(f"Scraping {name}...")
                outages = scraper.scrape()
                all_outages.extend(outages)
                self.logger.info(f"✅ {name}: {len(outages)} outages found")
                OUTAGES_FOUND.labels(provider=scraper.PROVIDER_NAME).set(len(outages))
            except Exception as e:
                self.logger.error(f"❌ {name}: Scraping failed - {e}")
                errors.append((name, str(e)))
            finally:
                # Record exactly how long it took in the Histogram
                duration = time.time() - start_time
                SCRAPE_DURATION.labels(provider=scraper.PROVIDER_NAME).observe(duration)

        self.logger.info(f"Total outages collected: {len(all_outages)}")
        if errors:
            self.logger.warning(f"Failed scrapers: {[e[0] for e in errors]}")
        
        return all_outages
    
    def scrape_provider(self, provider_name: str) -> List[Outage]:
        """
        Run a specific provider scraper.
        
        Args:
            provider_name: Name of the provider to scrape
            
        Returns:
            List of Outage objects from that provider
        """
        if provider_name not in self.scrapers:
            available = list(self.scrapers.keys())
            raise ValueError(f"Unknown provider: {provider_name}. Available: {available}")
        
        return self.scrapers[provider_name].scrape()
    
    def get_enabled_scrapers(self) -> List[str]:
        """Get list of enabled scraper names."""
        return list(self.scrapers.keys())
    
    def get_available_scrapers(self) -> List[str]:
        """Get list of all available scraper names."""
        return list(self.SCRAPERS.keys())
    
    def get_scraper_status(self) -> Dict[str, str]:
        """Get status of all scrapers."""
        return {
            name: "enabled" if name in self.scrapers else "disabled"
            for name in self.SCRAPERS.keys()
        }
