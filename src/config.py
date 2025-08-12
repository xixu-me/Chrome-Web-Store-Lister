"""Configuration constants and settings for Chrome Web Store Lister.

This module contains all configuration constants used throughout the application,
including default values, URLs, retry settings, and logging configuration.
"""

# Application default configuration values
DEFAULT_OUTPUT_FILE = "data.json"
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_DELAY_BETWEEN_REQUESTS = 0.1
DEFAULT_MAX_WORKERS = 10
DEFAULT_RETRY_ATTEMPTS = 3

# Chrome Web Store API constants
SITEMAP_NAMESPACE = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
BASE_SITEMAP_URL = "https://chromewebstore.google.com/sitemap"

# HTTP request retry configuration
RETRY_STATUS_FORCELIST = [429, 500, 502, 503, 504]
RETRY_ALLOWED_METHODS = ["HEAD", "GET", "OPTIONS"]
RETRY_BACKOFF_FACTOR = 1

# Application logging configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
GITHUB_ACTIONS_LOG_FORMAT = "%(levelname)s: %(message)s"
