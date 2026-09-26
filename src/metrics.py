"""Prometheus metrics definitions."""

from prometheus_client import Counter, Gauge, Histogram

# Track how many outages were found per provider
OUTAGES_FOUND = Gauge(
    'scraper_outages_found', 
    'Number of outages found in the most recent run', 
    ['provider']
)

# Track exactly how long each provider takes to scrape
SCRAPE_DURATION = Histogram(
    'scraper_execution_duration_seconds', 
    'Time spent scraping a provider', 
    ['provider']
)

# Track how many network failures happen
NETWORK_ERRORS = Counter(
    'scraper_network_errors_total', 
    'Total network errors encountered during scraping', 
    ['provider']
)
