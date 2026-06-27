"""Base scraper class with common functionality."""

import logging
import ssl
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.ssl_ import create_urllib3_context

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

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
            kwargs['ssl_context'] = self.ssl_context
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
        
        Returns:
            Configured requests Session or cloudscraper instance
        """
        # Use cloudscraper if available, but with SSL fix
        if self.use_cloudscraper:
            self.logger.debug("Using cloudscraper for Cloudflare bypass")
            try:
                # Create cloudscraper with custom SSL context
                session = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'windows',
                        'desktop': True,
                    },
                    delay=5,
                    ssl_context=create_insecure_ssl_context(),
                )
            except TypeError:
                # Older cloudscraper versions don't support ssl_context
                self.logger.debug("Cloudscraper doesn't support ssl_context, using fallback")
                session = self._create_standard_session()
        else:
            session = self._create_standard_session()
        
        # Default headers to mimic a real browser
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "hr-HR,hr;q=0.9,bs;q=0.8,sr;q=0.7,en-US;q=0.6,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })
        
        return session
    
    def _create_standard_session(self) -> requests.Session:
        """
        Create a standard requests session with SSL fix.
        
        Returns:
            Configured requests Session
        """
        self.logger.debug("Using standard requests session with SSL fix")
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "OPTIONS"],
        )
        
        # Use custom SSL adapter for HTTPS
        ssl_context = create_insecure_ssl_context()
        ssl_adapter = SSLAdapter(ssl_context=ssl_context, max_retries=retry_strategy)
        
        session.mount("https://", ssl_adapter)
        session.mount("http://", HTTPAdapter(max_retries=retry_strategy))
        
        return session
    
    def _get(self, url: str, **kwargs) -> requests.Response:
        """
        Make a GET request with error handling and SSL fallback.
        
        Args:
            url: URL to request
            **kwargs: Additional arguments for requests.get()
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: If request fails after retries
        """
        last_error = None
        
        # Remove verify from kwargs if present, we handle it ourselves
        kwargs.pop('verify', None)
        
        for attempt in range(self.max_retries + 1):
            try:
                self.logger.debug(f"GET {url} (attempt {attempt + 1}/{self.max_retries + 1})")
                
                response = self.session.get(
                    url, 
                    timeout=self.timeout, 
                    verify=False,  # Always False, we use custom SSL context
                    **kwargs
                )
                response.raise_for_status()
                return response
                
            except requests.exceptions.SSLError as e:
                self.logger.warning(f"SSL error for {url}: {e}")
                last_error = e
                
                # Try with a fresh session
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
        
        self.logger.error(f"GET request failed for {url} after {self.max_retries + 1} attempts: {last_error}")
        raise last_error
    
    def _post(self, url: str, data: Optional[Dict] = None, json: Optional[Dict] = None, **kwargs) -> requests.Response:
        """
        Make a POST request with error handling and SSL fallback.
        
        Args:
            url: URL to request
            data: Form data to send
            json: JSON data to send
            **kwargs: Additional arguments for requests.post()
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: If request fails after retries
        """
        last_error = None
        
        # Remove verify from kwargs if present
        kwargs.pop('verify', None)
        
        for attempt in range(self.max_retries + 1):
            try:
                self.logger.debug(f"POST {url} (attempt {attempt + 1}/{self.max_retries + 1})")
                
                response = self.session.post(
                    url,
                    data=data,
                    json=json,
                    timeout=self.timeout,
                    verify=False,
                    **kwargs
                )
                response.raise_for_status()
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
        
        self.logger.error(f"POST request failed for {url} after {self.max_retries + 1} attempts: {last_error}")
        raise last_error
    
    def _rate_limit(self, seconds: float = 1.0) -> None:
        """
        Sleep for rate limiting.
        
        Args:
            seconds: Seconds to sleep
        """
        time.sleep(seconds)
    
    @abstractmethod
    def scrape(self) -> List[Outage]:
        """
        Scrape outage data from the provider.
        
        Returns:
            List of Outage objects
            
        Must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    def parse(self, html: str) -> List[Outage]:
        """
        Parse HTML content and extract outages.
        
        Args:
            html: HTML content to parse
            
        Returns:
            List of Outage objects
            
        Must be implemented by subclasses.
        """
        pass
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get information about the current session.
        
        Returns:
            Dictionary with session info
        """
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