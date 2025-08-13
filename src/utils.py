"""Utility functions for Chrome Web Store item data processing.

This module provides utility functions for data validation, sanitization,
URL processing, and security checks used throughout the application.
"""

import re
import urllib.parse
from pathlib import Path
from typing import Optional

import requests
import validators


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and invalid characters.

    Removes potentially dangerous characters and ensures the filename is safe
    for use on common filesystems while preventing directory traversal attacks.

    Args:
        filename: Raw filename string to sanitize.

    Returns:
        str: Sanitized filename safe for filesystem use.
    """
    # Remove directory traversal attempts
    filename = Path(filename).name

    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")

    # Remove control characters
    filename = "".join(char for char in filename if ord(char) >= 32)

    # Limit length and ensure not empty
    filename = filename[:255].strip()
    if not filename:
        filename = "output"

    return filename


def validate_url(url: str) -> bool:
    """
    Validate URL format and security compliance.

    Checks if the provided URL is valid, properly formatted, and safe to use.
    Blocks localhost and private IP addresses for security reasons.

    Args:
        url: URL string to validate.

    Returns:
        bool: True if URL is valid and safe to use, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False

    # Check basic URL format
    if not validators.url(url):
        return False

    # Parse URL to check components
    try:
        parsed = urllib.parse.urlparse(url)

        # Only allow HTTP/HTTPS
        if parsed.scheme not in ("http", "https"):
            return False

        # Block localhost and private IPs for security
        hostname = parsed.hostname
        if hostname:
            hostname = hostname.lower()
            if (
                hostname in ("localhost", "127.0.0.1", "::1")
                or hostname.startswith("192.168.")
                or hostname.startswith("10.")
                or hostname.startswith("172.")
            ):
                return False

        return True
    except Exception:
        return False


def sanitize_item_data(item_data: dict) -> Optional[dict]:
    """
    Sanitize and validate Chrome Web Store item data.

    Validates and cleans item data to ensure it meets security requirements
    and contains all necessary fields with proper formatting.

    Args:
        item_data: Raw item data dictionary from Chrome Web Store.

    Returns:
        Optional[dict]: Sanitized item data dictionary if valid, None if invalid.
    """
    if not isinstance(item_data, dict):
        return None

    sanitized = {}

    # Validate and sanitize item ID (must be 32 alphanumeric characters)
    item_id = item_data.get("id", "").strip()
    if not re.match(r"^[a-zA-Z0-9]+$", item_id) or len(item_id) != 32:
        return None
    sanitized["id"] = item_id

    # Validate and sanitize item name (remove HTML tags, limit length)
    item_name = item_data.get("name", "").strip()
    # Remove HTML tags and decode HTML entities
    item_name = re.sub(r"<[^>]+>", "", item_name)
    item_name = urllib.parse.unquote(item_name)
    if len(item_name) > 200:  # Reasonable limit for item names
        item_name = item_name[:200].strip()
    if not item_name:
        return None
    sanitized["name"] = item_name

    # Validate Chrome Web Store page URL
    page_url = item_data.get("page", "")
    if not validate_url(page_url) or not is_valid_chrome_store_url(page_url):
        return None
    sanitized["page"] = page_url

    # Validate Chrome item file download URL
    file_url = item_data.get("file", "")
    if not validate_url(file_url):
        return None
    sanitized["file"] = file_url

    return sanitized


def _extract_name_from_title(url: str, timeout: int = 30) -> Optional[str]:
    """
    Extract item name from Chrome Web Store page title.
    
    Fetches the page and extracts the name from the title tag,
    removing the " - Chrome Web Store" suffix.
    
    Args:
        url: Chrome Web Store item detail URL.
        timeout: Request timeout in seconds.
        
    Returns:
        Optional[str]: Extracted item name or None if extraction failed.
    """
    try:
        # Make HTTP request to fetch the page
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        
        # Extract title from HTML using regex
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', response.text, re.IGNORECASE)
        
        if title_match:
            full_title = title_match.group(1).strip()
            
            # Remove the " - Chrome Web Store" suffix
            chrome_store_suffix = " - Chrome Web Store"
            if full_title.endswith(chrome_store_suffix):
                return full_title[:-len(chrome_store_suffix)].strip()
                
    except Exception:
        # If any error occurs, return None to fall back to URL-based extraction
        pass
        
    return None


def extract_item_data(url: str) -> Optional[dict[str, str]]:
    """
    Extract Chrome Web Store item data from URL.

    Parses Chrome Web Store detail URLs to extract item information
    including ID, name, and download links. Attempts to fetch the actual
    page title for more accurate name extraction, with fallback to URL-based
    name extraction.

    Args:
        url: Chrome Web Store item detail URL.

    Returns:
        Optional[dict[str, str]]: Dictionary containing item data
            (id, name, page, file) if extraction successful, None otherwise.
    """
    # Validate URL first
    if not validate_url(url) or not is_valid_chrome_store_url(url):
        return None

    # Chrome Web Store URL format: https://chromewebstore.google.com/detail/{name}/{id}
    url_match = re.search(r"/detail/([^/]+)/([^/?]+)", url)
    if not url_match:
        return None

    raw_item_name = url_match.group(1)
    item_id = url_match.group(2)

    try:
        # First, try to extract name from page title
        item_name = _extract_name_from_title(url)
        
        # If title extraction failed, fall back to URL-based extraction
        if item_name is None:
            item_name = urllib.parse.unquote(raw_item_name).replace("-", " ")

        # Generate Chrome item download URL
        crx_download_url = f"https://clients2.google.com/service/update2/crx?response=redirect&prodversion=138&acceptformat=crx2,crx3&x=id%3D{item_id}%26uc"

        item_data = {
            "id": item_id,
            "name": item_name,
            "page": url,
            "file": crx_download_url,
        }

        # Validate and sanitize the extracted data before returning
        return sanitize_item_data(item_data)
    except Exception:
        return None


def is_valid_chrome_store_url(url: str) -> bool:
    """
    Validate Chrome Web Store detail URL format.

    Checks if the provided URL matches the expected Chrome Web Store
    detail page URL pattern and points to a valid store page.

    Args:
        url: URL string to validate.

    Returns:
        bool: True if URL is a valid Chrome Web Store detail URL, False otherwise.
    """
    if not validate_url(url):
        return False

    parsed = urllib.parse.urlparse(url)
    return (
        parsed.hostname == "chromewebstore.google.com"
        and "/detail/" in parsed.path
    )
