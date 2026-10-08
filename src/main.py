"""Main entry point for the electricity outage scraper application."""

import logging
import sys
import time
from datetime import datetime

import schedule
from prometheus_client import start_http_server
from pythonjsonlogger.json import JsonFormatter

from src.config.settings import load_config
from src.database.db_manager import DatabaseManager, OutageModel
from src.geocoder import OutageGeocoder
from src.scrapers.scraper_manager import ScraperManager
from src.services.subscription_service import SubscriptionService


def setup_logging(level: str = "INFO") -> None:
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper()))
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def run_scrape_job():
    logger = logging.getLogger("ScrapeJob")
    logger.info("=" * 60)
    logger.info(f"Starting scheduled scrape at {datetime.now().isoformat()}")
    logger.info("=" * 60)
    try:
        scraper_manager = ScraperManager()
        db_manager = DatabaseManager()
        subscription_service = SubscriptionService(db_manager)
        geocoder = OutageGeocoder(db_manager)

        outages = scraper_manager.scrape_all(parallel=True)
        save_result = db_manager.save_outages(outages)
        logger.info(
            f"Database: {save_result['new']} new, {save_result['existing']} existing"
        )

        new_outages = save_result.get("new_objects", [])
        if new_outages:
            notification_stats = subscription_service.process_outages(new_outages)
            logger.info(f"Notifications: {notification_stats}")

        logger.info("Geocoding outage locations for the map...")
        for outage in outages:
            if not getattr(outage, "coordinates", None):
                lat, lon = geocoder.get_coordinates(outage.municipality, outage.area)
                if lat and lon:
                    outage.coordinates = (lat, lon)
                    db_manager.save_outages([outage])

        logger.info("Cleanup: Skipped (Historical data retention set to INFINITE)")
        logger.info("=" * 60)
        logger.info("Scrape job completed successfully")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Scrape job failed: {e}", exc_info=True)


def run_reminders_job():
    logger = logging.getLogger("ReminderJob")
    logger.info("Starting T-Minus 2 Hour Reminder Check...")
    try:
        db_manager = DatabaseManager()
        subscription_service = SubscriptionService(db_manager)

        with db_manager.Session() as session:
            today_midnight = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            active_outages = (
                session.query(OutageModel)
                .filter(OutageModel.date_start >= today_midnight)
                .all()
            )

            if active_outages:
                stats = subscription_service.process_reminders(active_outages)
                logger.info(
                    f"Reminders processed. Sent: {stats.get('reminders_sent', 0)}"
                )
            else:
                logger.info("No active outages found for reminders.")
    except Exception as e:
        logger.error(f"Reminder job failed: {e}", exc_info=True)


def main():
    config = load_config()
    setup_logging(config.get("log_level", "INFO"))
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Electricity Outage Scraper Starting")
    logger.info(f"Current time: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    interval_minutes = config.get("scrape_interval_minutes", 120)
    start_http_server(8000, addr="0.0.0.0")
    logger.info("Prometheus metrics server started on port 8000")

    # Run everything immediately on startup
    run_scrape_job()
    run_reminders_job()

    # Schedule recurring runs
    schedule.every(interval_minutes).minutes.do(run_scrape_job)
    schedule.every(30).minutes.do(run_reminders_job)

    logger.info(f"Scraper scheduled every {interval_minutes} minutes.")
    logger.info("Reminders scheduled every 30 minutes.")
    logger.info("Press Ctrl+C to stop.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)


if __name__ == "__main__":
    main()
