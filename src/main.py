"""Main entry point for the electricity outage scraper application."""

import logging
import sys
import time
from datetime import datetime

import schedule

from src.scrapers.scraper_manager import ScraperManager
from src.database.db_manager import DatabaseManager
from src.services.subscription_service import SubscriptionService
from src.utils.config import load_config


def setup_logging(level: str = "INFO") -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


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
        
        # Scrape all providers
        outages = scraper_manager.scrape_all(parallel=True)
        
        # Save to database
        save_result = db_manager.save_outages(outages)
        logger.info(f"Database: {save_result['new']} new, {save_result['existing']} existing")
        
        # Process notifications for new outages
        if save_result['new'] > 0:
            # Get only the new outages (those that were just saved)
            new_outages = [o for o in outages if db_manager.get_outage(o.outage_id)]
            notification_stats = subscription_service.process_outages(new_outages)
            logger.info(f"Notifications: {notification_stats}")
        
        # Cleanup old data
        deleted = db_manager.delete_old_outages(days=30)
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old outages")
        
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
    interval_minutes = config.get("scrape_interval_minutes", 30)
    
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