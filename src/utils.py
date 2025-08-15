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
from bs4 import BeautifulSoup


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


def get_chrome_store_item_name(url: str) -> Optional[str]:
    """
    Fetch the actual item name from Chrome Web Store page title.

    Fetches the page and extracts the title, then removes the " - Chrome Web Store"
    suffix to get the clean item name.

    Args:
        url: The Chrome Web Store item URL.

    Returns:
        The clean item name as a string, or None if the title
        cannot be retrieved or processed.
    """
    try:
        # Set a timeout to prevent the request from hanging indefinitely
        response = requests.get(url, timeout=10)
        # Raise an HTTPError for bad responses (4xx or 5xx)
        response.raise_for_status()

        # Parse the HTML content
        soup = BeautifulSoup(response.content, "html.parser")

        # Find the title tag and return its string content
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

            # Remove the " - Chrome Web Store" suffix if present
            chrome_store_suffix = " - Chrome Web Store"
            if title.endswith(chrome_store_suffix):
                title = title[: -len(chrome_store_suffix)].strip()

            return title if title else None
        else:
            return None  # No title tag was found

    except requests.exceptions.RequestException as e:
        # Handle connection errors, timeouts, etc.
        print(f"An error occurred while fetching the URL: {e}")
        return None
    except Exception as e:
        # Handle any other errors (parsing, etc.)
        print(f"An error occurred while processing the page: {e}")
        return None


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

    # Mark item as invalid if name is "Chrome Web Store"
    if item_name == "Chrome Web Store":
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


def extract_item_data(url: str) -> Optional[dict[str, str]]:
    """
    Extract Chrome Web Store item data from URL.

    Parses Chrome Web Store detail URLs to extract item information
    including ID, name, and download links.

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
    url_match = re.search(r"/detail/[^/]+/([^/?]+)", url)
    if not url_match:
        return None

    item_id = url_match.group(1)

    try:
        # Get the item name from the page title
        item_name = get_chrome_store_item_name(url)

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
    return parsed.hostname == "chromewebstore.google.com" and "/detail/" in parsed.path
