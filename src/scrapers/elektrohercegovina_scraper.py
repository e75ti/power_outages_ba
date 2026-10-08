import re
from datetime import datetime
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

            # Pronađi sve linkove ka pojedinačnim obavještenjima
            article_links = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # Tražimo linkove oblika /index.php/obavjestenja/2117
                if "/obavjestenja/" in href and any(c.isdigit() for c in href):
                    full_url = urljoin(self.DOMAIN, href)
                    article_links.add(full_url)

            # Sortiramo unazad da prvo gledamo najveće ID-jeve (najnovije)
            sorted_links = sorted(list(article_links), reverse=True)
            self.logger.info(f"Found {len(sorted_links)} links. Scanning last 20...")

            # Ograničavamo na zadnjih 10 da ne spamamo server
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

        # Spoji sve paragrafe u jedan veliki tekst
        paragraphs = article_body.find_all("p")
        if not paragraphs:
            # Ponekad ne koriste <p> tagove
            full_text = article_body.text.strip()
        else:
            full_text = " ".join([p.text.strip() for p in paragraphs if p.text.strip()])

        # Ignoriši obavještenja koja nisu o isključenjima
        if "napajanj" not in full_text.lower():
            return outages

        try:
            # 1. Pokušaj naći regiju/Opštinu pametnim Regex-om
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

            # 2. Izvlačenje datuma
            date_match = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})", full_text)

            # 3. Izvlačenje vremena (gađa "08:00 do 10:00" ili "9:30 do 12:00")
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
                    date_start = datetime.now()
            else:
                date_start = datetime.now()

            if time_match:
                time_start = time_match.group(1).replace(".", ":")
                time_end = time_match.group(2).replace(".", ":")

            # 4. Izvlačenje područja (hvata sve iza 'preko', 'sa', ili 'radova na')
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
