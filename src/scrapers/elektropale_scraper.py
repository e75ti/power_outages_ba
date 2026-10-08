import re
from datetime import datetime
from typing import List

from bs4 import BeautifulSoup

from src.models.outage import Outage
from src.scrapers.base_scraper import BaseScraper


class ElektroPaleScraper(BaseScraper):
    """Scraper for Elektro Pale planned outages."""

    PROVIDER_NAME = "Elektro Pale"
    BASE_URL = "https://www.edbpale.com/planirana-iskljucenja/"

    def scrape(self) -> List[Outage]:
        outages = []
        pages_to_scrape = 2  # Gledamo prve 2 stranice za aktuelna isključenja

        for page in range(1, pages_to_scrape + 1):
            url = self.BASE_URL if page == 1 else f"{self.BASE_URL}page/{page}/"

            try:
                self.logger.info(f"Scraping Elektro Pale - Page {page}...")
                # Koristimo _get iz BaseScrapera koji hendla retries i SSL
                response = self._get(url)

                # Šaljemo HTML u obaveznu parse() metodu
                page_outages = self.parse(response.text)

                if not page_outages:
                    self.logger.info(f"No more outage reports on page {page}.")
                    break

                outages.extend(page_outages)
                self._rate_limit(0.5)  # Dobra praksa, pauza između stranica

            except Exception as e:
                self.logger.error(f"Error while getting page {page} Elektro Pale: {e}")

        self.logger.info(f"Found {len(outages)} outages in Elektro Pale.")
        return outages

    def parse(self, html: str) -> List[Outage]:
        outages = []
        soup = BeautifulSoup(html, "html.parser")

        articles = soup.find_all("article", class_="entry-box")

        for article in articles:
            try:
                # 1. Title
                title_el = article.find("h1", class_="entry-title")
                if not title_el:
                    continue
                title = title_el.text.strip()

                # 2. Text of notification (Summary)
                desc_el = article.find("div", class_="entry-summary")
                description = desc_el.text.strip() if desc_el else ""

                # 3. City / Region (from category)
                cat_el = article.find("li", class_="entry-catagory")
                region = "Pale"
                if cat_el:
                    region = ", ".join([a.text.strip() for a in cat_el.find_all("a")])

                # 4. Time and date of outage
                date_match = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})", description)
                time_match = re.search(
                    r"од\s*(\d{1,2}:\d{2})\s*до\s*(\d{1,2}:\d{2})", description
                )

                date_start = None
                time_start = None
                time_end = None

                if date_match:
                    try:
                        date_start = datetime.strptime(date_match.group(1), "%d.%m.%Y")
                    except ValueError:
                        date_start = datetime.now()
                else:
                    date_start = datetime.now()

                if time_match:
                    time_start = time_match.group(1)
                    time_end = time_match.group(2)

                # Clean up the title to use as the "area"
                area = title
                if "10 kV" in area:
                    area = area.split("воду")[-1].strip()

                # Create Outage using YOUR correct model fields!
                outage = Outage(
                    provider=self.PROVIDER_NAME,
                    region="Pale",
                    municipality=region,
                    area=area,
                    streets=title,
                    date_start=date_start,
                    time_start=time_start,
                    time_end=time_end,
                    reason="Planirani radovi",
                    raw_text=description,
                )
                outages.append(outage)

            except Exception as e:
                self.logger.warning(
                    f"Greška pri parsiranju članka na Elektro Pale: {e}"
                )

        return outages
