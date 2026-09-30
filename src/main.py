# src/main.py
"""Main entry point for the electricity outage scraper application."""

import logging
import sys
import time
from datetime import datetime

import schedule
from pythonjsonlogger.json import JsonFormatter

from src.geocoder import OutageGeocoder
from src.scrapers.scraper_manager import ScraperManager
from src.database.db_manager import DatabaseManager
from src.services.subscription_service import SubscriptionService
from src.config.settings import load_config

from prometheus_client import start_http_server

def setup_logging(level: str = "INFO") -> None:
    """Set up JSON logging configuration for Grafana/Loki integration."""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear any default handlers to prevent duplicate logs
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    handler = logging.StreamHandler(sys.stdout)
    
    # This dictates the structure of the JSON payload sent to stdout
    formatter = JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)


def run_scrape_job():
    """Main scraping job that runs on schedule."""
    logger = logging.getLogger("ScrapeJob")
    
    logger.info("=" * 60)
    logger.info(f"Starting scheduled scrape at {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    try:
        # Initialize components
        scraper_manager = ScraperManager()
        db_manager = DatabaseManager()
        subscription_service = SubscriptionService(db_manager)
        geocoder = OutageGeocoder()
        
        # Scrape all providers
        outages = scraper_manager.scrape_all(parallel=True)
        
        # Geocode

        logger.info("Geocoding outage locations for the map...")
        for outage in outages:
            # Skip if the scraper (like Doboj) already provided exact coordinates
            if not getattr(outage, 'coordinates', None):
                lat, lon = geocoder.get_coordinates(outage.municipality, outage.area)
                if lat and lon:
                    outage.coordinates = (lat, lon)

        # Save to database (now returns exactly the newly inserted objects)
        save_result = db_manager.save_outages(outages)
        logger.info(f"Database: {save_result['new']} new, {save_result['existing']} existing")
        
        new_outages = save_result.get('new_objects', [])

        # Process notifications ONLY for new outages
        if new_outages:
            notification_stats = subscription_service.process_outages(new_outages)
            logger.info(f"Notifications: {notification_stats}")
        
# ----- DISABLED CLEANING UP OLD DATA , HISTORICAL RETENTION PREFERRED -----

        # Cleanup old data (Outages, Notifications, Geocache)
        #deleted_outages = db_manager.delete_old_outages(days=30)
        #deleted_notifs = db_manager.delete_old_notifications(days=7)
        #deleted_cache = db_manager.delete_old_geocache(days=90)

        #logger.info(f"Cleanup: {deleted_outages} outages, {deleted_notifs} notifications, {deleted_cache} geocache entries removed.")
        logger.info("Cleanup: Skipped (Historical data retention set to INFINITE)")

        logger.info("=" * 60)
        logger.info("Scrape job completed successfully")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Scrape job failed: {e}", exc_info=True)


def main():
    """Main entry point."""

    # Load configuration
    config = load_config()
    
    # Setup logging
    setup_logging(config.get("log_level", "INFO"))
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("Electricity Outage Scraper Starting")
    logger.info(f"Current time: {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    # Get scrape interval
    interval_minutes = config.get("scrape_interval_minutes", 120)

    # Prometheus
    start_http_server(8000, addr="0.0.0.0")
    logger.info("Prometheus metrics server started on port 8000")

    # Run immediately on startup
    run_scrape_job()
    
    # Schedule recurring runs
    schedule.every(interval_minutes).minutes.do(run_scrape_job)
    
    logger.info(f"Scheduler started. Running every {interval_minutes} minutes.")
    logger.info("Press Ctrl+C to stop.")
    
    # Keep running
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)


if __name__ == "__main__":
    main()
