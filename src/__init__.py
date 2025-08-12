"""Package initialization for Chrome Web Store Lister.

This module initializes the Chrome Web Store Lister package and exports
the main application components for easy importing and usage.
"""

from src.cli import parse_arguments
from src.core import ChromeWebStoreLister

__author__ = "Xi Xu"

__all__ = ["ChromeWebStoreLister", "parse_arguments"]
