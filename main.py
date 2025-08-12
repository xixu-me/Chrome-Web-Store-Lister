#!/usr/bin/env python3
"""Main entry point for Chrome Web Store Lister application.

This module serves as the primary entry point for the Chrome Web Store item data
collection application, providing a simple interface to the CLI functionality
with comprehensive error handling and user feedback.
"""

import sys

from src import ChromeWebStoreLister, parse_arguments


def main() -> None:
    """
    Main entry point for the Chrome Web Store item data collection application.

    This function provides a wrapper around the CLI module with enhanced error
    handling and user-friendly feedback for various failure scenarios.
    """
    try:
        # Parse command line arguments
        args = parse_arguments()

        # Create and initialize the Chrome Web Store item data collector
        chrome_store_lister = ChromeWebStoreLister(
            output_file=args.output,
            request_timeout=args.timeout,
            delay=args.delay,
            max_workers=args.max_workers,
            retry_attempts=args.retry_attempts,
        )

        # Execute the data collection process
        chrome_store_lister.run()

    except KeyboardInterrupt:
        print("\n⚠️ Operation interrupted by user", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Invalid configuration: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
