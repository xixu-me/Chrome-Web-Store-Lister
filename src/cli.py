"""Command line interface for Chrome Web Store Lister.

This module provides command line argument parsing and validation for the
Chrome Web Store item data collection application, including parameter validation
and environment variable support.
"""

import argparse
import os
from pathlib import Path

from src.config import (
    DEFAULT_DELAY_BETWEEN_REQUESTS,
    DEFAULT_MAX_WORKERS,
    DEFAULT_OUTPUT_FILE,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_ATTEMPTS,
)
from src.utils import sanitize_filename


def validate_positive_integer(value: str) -> int:
    """
    Validate and convert string to positive integer.

    Ensures the provided value is a valid positive integer greater than zero,
    which is required for various application parameters.

    Args:
        value: String value to validate and convert.

    Returns:
        int: Validated positive integer value.

    Raises:
        argparse.ArgumentTypeError: If value is not a valid positive integer.
    """
    try:
        integer_value = int(value)
        if integer_value <= 0:
            raise argparse.ArgumentTypeError(f"'{value}' must be a positive integer")
        return integer_value
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid integer") from exc


def validate_positive_float(value: str) -> float:
    """
    Validate and convert string to positive float.

    Ensures the provided value is a valid non-negative floating-point number,
    which is required for timing and delay parameters.

    Args:
        value: String value to validate and convert.

    Returns:
        float: Validated non-negative float value.

    Raises:
        argparse.ArgumentTypeError: If value is not a valid non-negative float.
    """
    try:
        float_value = float(value)
        if float_value < 0:
            raise argparse.ArgumentTypeError(f"'{value}' must be non-negative")
        return float_value
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid number") from exc


def validate_output_file(value: str) -> str:
    """
    Validate and sanitize output file path.

    Ensures the output file path is safe, writable, and has the correct
    JSON item for data output.

    Args:
        value: Output file path string to validate.

    Returns:
        str: Validated and sanitized file path with .json item.

    Raises:
        argparse.ArgumentTypeError: If path is invalid, unsafe, or not writable.
    """
    # Validate that the file path is not empty
    if not value:
        raise argparse.ArgumentTypeError("Output file path cannot be empty")

    # Sanitize filename to prevent security issues
    sanitized_path = sanitize_filename(value)

    # Ensure the file has the correct JSON item
    if not sanitized_path.lower().endswith(".json"):
        sanitized_path += ".json"

    # Verify parent directory is writable (if it exists)
    output_path = Path(sanitized_path)
    parent_directory = output_path.parent

    if parent_directory.exists() and not os.access(parent_directory, os.W_OK):
        raise argparse.ArgumentTypeError(
            f"Directory '{parent_directory}' is not writable"
        )

    return sanitized_path


def parse_arguments() -> argparse.Namespace:
    """
    Parse and validate command line arguments.

    Sets up the argument parser with all available options and validates
    the provided arguments for correctness and security.

    Returns:
        argparse.Namespace: Parsed and validated command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Fetch and list all items from Chrome Web Store",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-o",
        "--output",
        type=validate_output_file,
        default=os.getenv("OUTPUT_FILE", DEFAULT_OUTPUT_FILE),
        help="Output JSON file path",
    )

    parser.add_argument(
        "--timeout",
        type=validate_positive_integer,
        default=int(os.getenv("REQUEST_TIMEOUT", DEFAULT_REQUEST_TIMEOUT)),
        help="HTTP request timeout in seconds",
    )

    parser.add_argument(
        "--delay",
        type=validate_positive_float,
        default=float(os.getenv("REQUEST_DELAY", DEFAULT_DELAY_BETWEEN_REQUESTS)),
        help="Delay between requests in seconds",
    )

    parser.add_argument(
        "--max-workers",
        type=validate_positive_integer,
        default=int(os.getenv("MAX_WORKERS", DEFAULT_MAX_WORKERS)),
        help="Maximum number of concurrent workers",
    )

    parser.add_argument(
        "--retry-attempts",
        type=validate_positive_integer,
        default=int(os.getenv("RETRY_ATTEMPTS", DEFAULT_RETRY_ATTEMPTS)),
        help="Number of retry attempts for failed requests",
    )

    parser.add_argument(
        "--no-progress",
        action="store_true",
        default=os.getenv("NO_PROGRESS", "false").lower() == "true",
        help="Disable progress bars (useful for CI/CD environments)",
    )

    parser.add_argument(
        "--version", action="version", version="Chrome Web Store Lister 1.0.0"
    )

    return parser.parse_args()


def main() -> None:
    """
    Main CLI entry point for the application.

    This function parses command line arguments and initializes the
    Chrome Web Store item data collection process with the provided configuration.
    """
    from .core import ChromeWebStoreLister

    # Parse command line arguments
    args = parse_arguments()

    # Create and initialize the Chrome Web Store item data collector
    chrome_store_lister = ChromeWebStoreLister(
        output_file=args.output,
        request_timeout=args.timeout,
        delay=args.delay,
        max_workers=args.max_workers,
        retry_attempts=args.retry_attempts,
        show_progress=not args.no_progress,
    )

    # Execute the data collection process
    chrome_store_lister.run()


if __name__ == "__main__":
    main()
