import re
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from src.scrapers.base import BaseScraper
from src.models import Outage

class ElektroPaleScraper(BaseScraper):
    name = "elektropale"
    base_url = "https://www.edbpale.com/planirana-iskljucenja/"

    def scrape(self):
        outages = []
        pages_to_scrape = 2  # Gledamo prve 2 stranice za aktuelna isključenja
        
        for page in range(1, pages_to_scrape + 1):
            url = self.base_url if page == 1 else f"{self.base_url}page/{page}/"
            
            try:
                self.logger.info(f"Scraping Elektro Pale - Page {page}...")
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Svi članci su unutar article taga sa klasom 'entry-box'
                articles = soup.find_all('article', class_='entry-box')
                
                if not articles:
                    self.logger.info(f"Nema više članaka na stranici {page}.")
                    break
                    
                for article in articles:
                    try:
                        # 1. Naslov
                        title_el = article.find('h1', class_='entry-title')
                        if not title_el:
                            continue
                        title = title_el.text.strip()
                        
                        # 2. Link
                        link_el = article.find('div', class_='entry-header').find('a')
                        link = link_el['href'] if link_el else self.base_url
                        
                        # 3. Tekst obavještenja (Summary)
                        desc_el = article.find('div', class_='entry-summary')
                        description = desc_el.text.strip() if desc_el else ""
                        
                        # 4. Grad / Regija (iz kategorije)
                        cat_el = article.find('li', class_='entry-catagory')
                        region = "Pale (Nepoznato)"
                        if cat_el:
                            # Može biti više gradova odjednom (npr. Istočna Ilidža, Istočno Novo Sarajevo)
                            region = ", ".join([a.text.strip() for a in cat_el.find_all('a')])
                            
                        # 5. Izvlačenje datuma i vremena pomoću Regex-a iz teksta
                        # Traži format tipa: 02.10.2026 ili 24.9.2024
                        date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', description)
                        # Traži format tipa: од 09:00 до 17:00
                        time_match = re.search(r'од\s*(\d{1,2}:\d{2})\s*до\s*(\d{1,2}:\d{2})', description)
                        
                        start_time = None
                        end_time = None
                        
                        if date_match and time_match:
                            date_str = date_match.group(1)
                            start_str = time_match.group(1)
                            end_str = time_match.group(2)
                            
                            try:
                                start_time = datetime.strptime(f"{date_str} {start_str}", "%d.%m.%Y %H:%M")
                                end_time = datetime.strptime(f"{date_str} {end_str}", "%d.%m.%Y %H:%M")
                            except ValueError:
                                pass
                        
                        # Fallback: Ako Regex ne uspije naći datum (rijetko), koristi trenutno vrijeme
                        if not start_time:
                            start_time = datetime.now()
                        if not end_time:
                            end_time = start_time
                            
                        # Kreiranje Outage objekta
                        outage = Outage(
                            title=title,
                            description=description,
                            region=region,
                            start_time=start_time,
                            end_time=end_time,
                            source_url=link,
                            provider=self.name
                        )
                        outages.append(outage)
                        
                    except Exception as e:
                        self.logger.warning(f"Greška pri parsiranju članka na Elektro Pale: {e}")
                        
            except Exception as e:
                self.logger.error(f"Greška pri dohvaćanju stranice {page} Elektro Pale: {e}")
                
        self.logger.info(f"Pronađeno {len(outages)} isključenja sa Elektro Pale.")
        return outages
