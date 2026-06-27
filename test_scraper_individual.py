"""
Individual scraper testing script.

Usage:
    python test_scraper_individual.py <scraper_name> [options]

Scraper names:
    epbih, ephzhb, elektrokrajina, elektrodoboj, elektrobijeljina, all

Options:
    --save, -s     Save results to Firebase database
    --export, -e   Export results to JSON file
    --verbose, -v  Show detailed output

Examples:
    python test_scraper_individual.py epbih
    python test_scraper_individual.py ephzhb --export
    python test_scraper_individual.py all --save
    python test_scraper_individual.py elektrokrajina -v -e
"""

import sys
import os
import json
import logging
from datetime import datetime
from typing import List

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging
def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger(__name__)


def get_scraper_class(name: str):
    """Import and return scraper class by name."""
    scrapers = {}
    
    try:
        from src.scrapers.epbih_scraper import EPBiHScraper
        scrapers['epbih'] = EPBiHScraper
    except ImportError as e:
        logger.warning(f"Could not import EPBiHScraper: {e}")
    
    try:
        from src.scrapers.ephzhb_scraper import EPHZHBScraper
        scrapers['ephzhb'] = EPHZHBScraper
    except ImportError as e:
        logger.warning(f"Could not import EPHZHBScraper: {e}")
    
    try:
        from src.scrapers.elektrokrajina_scraper import ElektroKrajinaScraper
        scrapers['elektrokrajina'] = ElektroKrajinaScraper
    except ImportError as e:
        logger.warning(f"Could not import ElektroKrajinaScraper: {e}")
    
    try:
        from src.scrapers.elektrodoboj_scraper import ElektroDobojScraper
        scrapers['elektrodoboj'] = ElektroDobojScraper
    except ImportError as e:
        logger.warning(f"Could not import ElektroDobojScraper: {e}")
    
    try:
        from src.scrapers.elektrobijeljina_scraper import ElektroBijeljinaScraper
        scrapers['elektrobijeljina'] = ElektroBijeljinaScraper
    except ImportError as e:
        logger.warning(f"Could not import ElektroBijeljinaScraper: {e}")
    
    return scrapers.get(name), scrapers


def print_outage_details(outage, index: int):
    """Print formatted outage details."""
    print(f"\n{'─' * 50}")
    print(f"  [{index}] {outage.provider}")
    print(f"{'─' * 50}")
    print(f"  📍 Municipality: {outage.municipality}")
    print(f"  📍 Region:       {outage.region}")
    print(f"  🏠 Area:         {outage.area[:100]}{'...' if len(outage.area) > 100 else ''}")
    if outage.streets:
        print(f"  🛣️  Streets:      {outage.streets[:100]}{'...' if len(outage.streets) > 100 else ''}")
    print(f"  📅 Date:         {outage.date_start.strftime('%d.%m.%Y') if outage.date_start else 'N/A'}")
    print(f"  ⏰ Time:         {outage.time_start or 'N/A'} - {outage.time_end or 'N/A'}")
    if outage.reason:
        print(f"  📝 Reason:       {outage.reason[:80]}{'...' if len(outage.reason) > 80 else ''}")
    print(f"  🔑 ID:           {outage.outage_id}")


def test_scraper(name: str, save_to_db: bool = False, verbose: bool = False) -> List:
    """Test a single scraper."""
    scraper_class, all_scrapers = get_scraper_class(name)
    
    if scraper_class is None:
        logger.error(f"❌ Unknown scraper: {name}")
        logger.info(f"Available scrapers: {list(all_scrapers.keys())}")
        return []
    
    print("\n" + "=" * 60)
    print(f"🔍 TESTING: {name.upper()}")
    print("=" * 60)
    
    # Initialize scraper
    scraper = scraper_class(timeout=30, max_retries=3)
    
    try:
        start_time = datetime.now()
        outages = scraper.scrape()
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print(f"\n✅ Scraping completed in {elapsed:.2f} seconds")
        print(f"📊 Found {len(outages)} outages")
        
        # Show outages
        if outages:
            show_count = min(5, len(outages)) if not verbose else len(outages)
            print(f"\n--- Showing {show_count} of {len(outages)} outages ---")
            
            for i, outage in enumerate(outages[:show_count], 1):
                print_outage_details(outage, i)
            
            if len(outages) > show_count:
                print(f"\n... and {len(outages) - show_count} more outages")
        
        # Save to database
        if save_to_db and outages:
            print("\n" + "-" * 40)
            print("💾 SAVING TO DATABASE...")
            print("-" * 40)
            
            try:
                from src.database.db_manager import DatabaseManager
                db = DatabaseManager()
                result = db.save_outages(outages)
                print(f"✅ New: {result['new']}, Already existed: {result['existing']}")
            except Exception as e:
                print(f"❌ Database error: {e}")
                logger.error(f"Database save failed: {e}", exc_info=True)
        
        return outages
        
    except Exception as e:
        print(f"\n❌ SCRAPER FAILED: {e}")
        logger.error(f"Scraper {name} failed", exc_info=True)
        return []


def test_all_scrapers(save_to_db: bool = False, verbose: bool = False):
    """Test all available scrapers."""
    _, all_scrapers = get_scraper_class("dummy")
    
    results = {}
    all_outages = []
    
    for name in all_scrapers.keys():
        outages = test_scraper(name, save_to_db=False, verbose=verbose)
        results[name] = len(outages)
        all_outages.extend(outages)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    
    for name, count in results.items():
        status = "✅" if count > 0 else "⚠️ "
        print(f"  {status} {name:20} : {count:4} outages")
    
    print("-" * 40)
    total = sum(results.values())
    print(f"  📊 TOTAL: {total} outages from {len(results)} providers")
    
    # Save all to database
    if save_to_db and total > 0:
        print("\n" + "-" * 40)
        print("💾 SAVING ALL TO DATABASE...")
        print("-" * 40)
        
        try:
            from src.database.db_manager import DatabaseManager
            db = DatabaseManager()
            result = db.save_outages(all_outages)
            print(f"✅ New: {result['new']}, Already existed: {result['existing']}")
        except Exception as e:
            print(f"❌ Database error: {e}")
    
    return results


def export_to_json(outages: List, filename: str):
    """Export outages to JSON file."""
    if not outages:
        print("⚠️  No outages to export")
        return
    
    data = [o.to_dict() for o in outages]
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n📁 Exported {len(outages)} outages to: {filename}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    # Parse arguments
    args = sys.argv[1:]
    scraper_name = args[0].lower()
    
    save_to_db = "--save" in args or "-s" in args
    export_json = "--export" in args or "-e" in args
    verbose = "--verbose" in args or "-v" in args
    
    # Setup logging
    setup_logging(verbose)
    
    print("\n" + "🔌" * 30)
    print("  ELECTRICITY OUTAGE SCRAPER - TEST MODE")
    print("🔌" * 30)
    print(f"\n  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Target: {scraper_name.upper()}")
    print(f"  Save to DB: {'Yes' if save_to_db else 'No'}")
    print(f"  Export JSON: {'Yes' if export_json else 'No'}")
    
    # Run tests
    if scraper_name == "all":
        results = test_all_scrapers(save_to_db=save_to_db, verbose=verbose)
        
        if export_json:
            # Re-scrape to get all outages for export
            _, all_scrapers = get_scraper_class("dummy")
            all_outages = []
            for name in all_scrapers.keys():
                scraper = all_scrapers[name](timeout=30, max_retries=3)
                try:
                    all_outages.extend(scraper.scrape())
                except:
                    pass
            export_to_json(all_outages, "outages_all.json")
    else:
        outages = test_scraper(scraper_name, save_to_db=save_to_db, verbose=verbose)
        
        if export_json and outages:
            export_to_json(outages, f"outages_{scraper_name}.json")
    
    print("\n" + "=" * 60)
    print("✅ TEST COMPLETE")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()