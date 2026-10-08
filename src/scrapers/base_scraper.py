"""Base scraper class with common functionality."""

import logging
import ssl
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.ssl_ import create_urllib3_context

try:
    import cloudscraper

    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

from src.metrics import NETWORK_ERRORS
from src.models.outage import Outage


class SSLAdapter(HTTPAdapter):
    """
    Custom HTTP Adapter that allows disabling SSL verification properly.
    Fixes the Python 3.13 issue with check_hostname and verify_mode.
    """

    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        if self.ssl_context:
            kwargs["ssl_context"] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)


def create_insecure_ssl_context():
    """
    Create an SSL context that doesn't verify certificates.
    Properly handles Python 3.13's stricter SSL requirements.
    """
    ctx = create_urllib3_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class BaseScraper(ABC):
    """
    Abstract base class for all electricity outage scrapers.

    Provides common functionality:
    - HTTP session management with retry logic
    - Cloudflare bypass using cloudscraper
    - SSL certificate handling (some sites have invalid certs)
    - Request/response logging
    - Error handling
    - Encoding correction for legacy Bosnian sites
    """

    # Override in subclasses
    PROVIDER_NAME: str = "Unknown"
    BASE_URL: str = ""

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        verify_ssl: bool = False,  # Default to False for problematic sites
        use_cloudscraper: bool = True,
    ):
        """
        Initialize the scraper.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            verify_ssl: Whether to verify SSL certificates
            use_cloudscraper: Whether to use cloudscraper for Cloudflare bypass
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl
        self.use_cloudscraper = use_cloudscraper and CLOUDSCRAPER_AVAILABLE
        self.logger = logging.getLogger(self.__class__.__name__)

        # Suppress SSL warnings
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Setup session
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """
        Create a requests session with retry logic and proper headers.
        Uses cloudscraper if available and enabled.
        """
        if self.use_cloudscraper:
            self.logger.debug("Using cloudscraper for Cloudflare bypass")
            try:
                session = cloudscraper.create_scraper(
                    browser={
                        "browser": "chrome",
                        "platform": "windows",
                        "desktop": True,
                    },
                    delay=5,
                    ssl_context=create_insecure_ssl_context(),
                )
            except TypeError:
                self.logger.debug(
                    "Cloudscraper doesn't support ssl_context, using fallback"
                )
                session = self._create_standard_session()
        else:
            session = self._create_standard_session()

        # Default headers to mimic a real browser
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "bs-BA,bs;q=0.9,hr-HR;q=0.8,sr;q=0.7,en-US;q=0.6,en;q=0.5",
                "Accept-Encoding": "identity",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            }
        )

        return session

    def _create_standard_session(self) -> requests.Session:
        """
        Create a standard requests session with SSL fix.
        """
        self.logger.debug("Using standard requests session with SSL fix")
        session = requests.Session()

        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "OPTIONS"],
        )

        ssl_context = create_insecure_ssl_context()
        ssl_adapter = SSLAdapter(ssl_context=ssl_context, max_retries=retry_strategy)

        session.mount("https://", ssl_adapter)
        session.mount("http://", HTTPAdapter(max_retries=retry_strategy))

        return session

    def _get(self, url: str, **kwargs) -> requests.Response:
        last_error = None
        kwargs.pop("verify", None)

        for attempt in range(self.max_retries + 1):
            try:
                self.logger.debug(
                    f"GET {url} (attempt {attempt + 1}/{self.max_retries + 1})"
                )

                # THE HACK: If the URL contains lowercase hex, stop Python from ruining it
                if "%" in url:
                    req = requests.Request("GET", url)
                    prep = self.session.prepare_request(req)
                    prep.url = url  # Force overwrite the normalized URL
                    response = self.session.send(
                        prep, timeout=self.timeout, verify=False
                    )
                else:
                    response = self.session.get(
                        url, timeout=self.timeout, verify=False, **kwargs
                    )

                # Fast fail for 404s
                if response.status_code == 404:
                    self.logger.debug(f"Page missing (404), skipping: {url}")
                    return response

                response.raise_for_status()

                if response.encoding and response.encoding.lower() in [
                    "iso-8859-1",
                    "windows-1250",
                    "iso-8859-2",
                ]:
                    response.encoding = response.apparent_encoding or "utf-8"

                return response

            except requests.exceptions.SSLError as e:
                self.logger.warning(f"SSL error for {url}: {e}")
                last_error = e

                if attempt < self.max_retries:
                    self.logger.debug("Recreating session...")
                    self.use_cloudscraper = False
                    self.session = self._create_standard_session()
                    time.sleep(1)

            except requests.exceptions.RequestException as e:
                NETWORK_ERRORS.labels(provider=self.PROVIDER_NAME).inc()
                self.logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                last_error = e

                if attempt < self.max_retries:
                    wait_time = (attempt + 1) * 2
                    self.logger.debug(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)

        self.logger.error(
            f"GET request failed for {url} after {self.max_retries + 1} attempts: {last_error}"
        )
        raise last_error

    def _post(
        self,
        url: str,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Make a POST request with error handling, SSL fallback, and encoding fixes.
        """
        last_error = None
        kwargs.pop("verify", None)

        for attempt in range(self.max_retries + 1):
            try:
                self.logger.debug(
                    f"POST {url} (attempt {attempt + 1}/{self.max_retries + 1})"
                )

                response = self.session.post(
                    url,
                    data=data,
                    json=json,
                    timeout=self.timeout,
                    verify=False,
                    **kwargs,
                )
                response.raise_for_status()

                # FIX: Force correct encoding for Bosnian Cyrillic/Latin sites
                if response.encoding and response.encoding.lower() in [
                    "iso-8859-1",
                    "windows-1250",
                    "iso-8859-2",
                ]:
                    response.encoding = response.apparent_encoding or "utf-8"

                return response

            except requests.exceptions.SSLError as e:
                self.logger.warning(f"SSL error for {url}: {e}")
                last_error = e

                if attempt < self.max_retries:
                    self.logger.debug("Recreating session...")
                    self.use_cloudscraper = False
                    self.session = self._create_standard_session()
                    time.sleep(1)

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                last_error = e

                if attempt < self.max_retries:
                    wait_time = (attempt + 1) * 2
                    self.logger.debug(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)

        self.logger.error(
            f"POST request failed for {url} after {self.max_retries + 1} attempts: {last_error}"
        )
        raise last_error

    def _rate_limit(self, seconds: float = 1.0) -> None:
        time.sleep(seconds)

    @abstractmethod
    def scrape(self) -> List[Outage]:
        pass

    @abstractmethod
    def parse(self, html: str) -> List[Outage]:
        pass

    def get_session_info(self) -> Dict[str, Any]:
        return {
            "provider": self.PROVIDER_NAME,
            "using_cloudscraper": self.use_cloudscraper,
            "cloudscraper_available": CLOUDSCRAPER_AVAILABLE,
            "verify_ssl": self.verify_ssl,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }

    def __repr__(self) -> str:
        cs = " +cloudscraper" if self.use_cloudscraper else ""
        return f"{self.__class__.__name__}(provider={self.PROVIDER_NAME}{cs})"
