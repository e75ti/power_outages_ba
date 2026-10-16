import re
from datetime import datetime, timezone
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.models.outage import Outage
from src.scrapers.base_scraper import BaseScraper


class ElektroHercegovinaScraper(BaseScraper):
    """Scraper for Elektro Hercegovina planned outages."""

    PROVIDER_NAME = "Elektro Hercegovina"
    BASE_URL = "https://www.elektrohercegovina.com/index.php/obavjestenja"
    DOMAIN = "https://www.elektrohercegovina.com"

    def scrape(self) -> List[Outage]:
        outages = []

        try:
            self.logger.info(f"Scraping {self.PROVIDER_NAME} main page...")
            response = self._get(self.BASE_URL)
            soup = BeautifulSoup(response.text, "html.parser")

            article_links = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # Look for /index.php/obavjestenja/2117
                if "/obavjestenja/" in href and any(c.isdigit() for c in href):
                    full_url = urljoin(self.DOMAIN, href)
                    article_links.add(full_url)

            sorted_links = sorted(list(article_links), reverse=True)
            self.logger.info(f"Found {len(sorted_links)} links. Scanning last 20...")

            for url in sorted_links[:20]:
                try:
                    article_resp = self._get(url)
                    page_outages = self.parse(article_resp.text, url)
                    outages.extend(page_outages)
                    self._rate_limit(0.5)
                except Exception as e:
                    self.logger.error(f"Error while getting link {url}: {e}")

        except Exception as e:
            self.logger.error(
                f"Error while getting main page {self.PROVIDER_NAME}: {e}"
            )

        self.logger.info(f"Found {len(outages)} outages with {self.PROVIDER_NAME}.")
        return outages

    def parse(self, html: str, source_url: str = "") -> List[Outage]:
        outages = []
        soup = BeautifulSoup(html, "html.parser")

        # Tekst se nalazi u sekciji article-content
        article_body = soup.find("section", class_="article-content") or soup.find(
            itemprop="articleBody"
        )

        if not article_body:
            return outages

        paragraphs = article_body.find_all("p")
        if not paragraphs:
            full_text = article_body.text.strip()
        else:
            full_text = " ".join([p.text.strip() for p in paragraphs if p.text.strip()])

        if "napajanj" not in full_text.lower():
            return outages

        try:
            region = "Nepoznato"

            region_match = re.search(
                r'TJ\s*["“”\']?Elektro-([A-Za-zšđčćžŠĐČĆŽ]+)["“”\']?',
                full_text,
                re.IGNORECASE,
            )
            if not region_match:
                region_match = re.search(
                    r"(?:opštin[eu]|grad[a]?)\s+([A-Za-zšđčćžŠĐČĆŽ]+)",
                    full_text,
                    re.IGNORECASE,
                )
            if not region_match:
                region_match = re.search(
                    r"TJ\s+([A-Za-zšđčćžŠĐČĆŽ]+)", full_text, re.IGNORECASE
                )

            if region_match:
                region = region_match.group(1).capitalize()

            date_match = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})", full_text)

            time_match = re.search(
                r"(\d{1,2}[:.]\d{2})\s*do\s*(\d{1,2}[:.]\d{2})", full_text
            )

            date_start = None
            time_start = None
            time_end = None

            if date_match:
                try:
                    date_start = datetime.strptime(date_match.group(1), "%d.%m.%Y")
                except ValueError:
                    date_start = datetime.now(timezone.utc)
            else:
                date_start = datetime.now(timezone.utc)

            if time_match:
                time_start = time_match.group(1).replace(".", ":")
                time_end = time_match.group(2).replace(".", ":")

            area = "Lokalno područje"
            area_match = re.search(
                r"(?:napajaju preko|snadbijevaju sa|radova na)\s+(.*?)(?:,|da će)",
                full_text,
                re.IGNORECASE,
            )
            if area_match:
                area = area_match.group(1).strip()

            outage = Outage(
                provider=self.PROVIDER_NAME,
                region="Hercegovina",
                municipality=region,
                area=area,
                streets=area,
                date_start=date_start,
                time_start=time_start,
                time_end=time_end,
                reason="Planirani radovi",
                raw_text=full_text,
            )
            outages.append(outage)

        except Exception as e:
            self.logger.warning(f"Error while parsing text at Elektro Hercegovina: {e}")

        return outages
