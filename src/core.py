"""Core Chrome Web Store item data fetcher and processor.

This module contains the main application logic for collecting Chrome Web Store
data, including performance monitoring, concurrent processing, and data validation.
"""

import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree as ET

import psutil
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import (
    BASE_SITEMAP_URL,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
    GITHUB_ACTIONS_LOG_FORMAT,
    RETRY_ALLOWED_METHODS,
    RETRY_BACKOFF_FACTOR,
    RETRY_STATUS_FORCELIST,
    SITEMAP_NAMESPACE,
)
from src.utils import extract_item_data, is_valid_chrome_store_url


class PerformanceMonitor:
    """
    Performance monitoring and statistics collection for the application.

    This class tracks application performance metrics including execution time,
    memory usage, CPU utilization, and request statistics to help optimize
    the data collection process.
    """

    def __init__(self):
        """Initialize performance monitoring with baseline metrics."""
        self.start_time = time.time()
        self.process = psutil.Process()
        self.start_memory = self.process.memory_info().rss
        self.request_times = []
        self.processing_times = []

    def record_request_time(self, duration: float) -> None:
        """
        Record HTTP request execution time.

        Args:
            duration: Request duration in seconds.
        """
        self.request_times.append(duration)

    def record_processing_time(self, duration: float) -> None:
        """
        Record data processing execution time.

        Args:
            duration: Processing duration in seconds.
        """
        self.processing_times.append(duration)

    def get_memory_usage(self) -> dict[str, float]:
        """
        Get current memory usage statistics in megabytes.

        Returns:
            dict[str, float]: Memory usage statistics including current,
                peak, and increase from baseline.
        """
        memory_info = self.process.memory_info()
        return {
            "current_mb": memory_info.rss / 1024 / 1024,
            "peak_mb": memory_info.vms / 1024 / 1024,
            "increase_mb": (memory_info.rss - self.start_memory) / 1024 / 1024,
        }

    def get_cpu_usage(self) -> float:
        """
        Get current CPU usage percentage.

        Returns:
            float: Current CPU usage percentage.
        """
        return self.process.cpu_percent()

    def get_request_stats(self) -> dict[str, float]:
        """
        Get HTTP request timing statistics.

        Returns:
            dict[str, float]: Request statistics including count, average,
                minimum, and maximum execution times.
        """
        if not self.request_times:
            return {"count": 0, "avg": 0.0, "min": 0.0, "max": 0.0}

        return {
            "count": len(self.request_times),
            "avg": sum(self.request_times) / len(self.request_times),
            "min": min(self.request_times),
            "max": max(self.request_times),
        }

    def get_elapsed_time(self) -> float:
        """
        Get total elapsed execution time in seconds.

        Returns:
            float: Total elapsed time since monitoring started.
        """
        return time.time() - self.start_time

    def log_performance_summary(self, logger: logging.Logger) -> None:
        """
        Log comprehensive performance summary to the provided logger.

        Args:
            logger: Logger instance to write performance metrics to.
        """
        # Log comprehensive performance and system metrics
        elapsed_time = self.get_elapsed_time()
        memory_usage = self.get_memory_usage()
        cpu_usage = self.get_cpu_usage()
        request_statistics = self.get_request_stats()

        logger.info("=" * 60)
        logger.info("PERFORMANCE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total execution time: {elapsed_time:.2f} seconds")
        logger.info(
            f"Memory usage: {memory_usage['current_mb']:.1f} MB "
            f"(peak: {memory_usage['peak_mb']:.1f} MB)"
        )
        logger.info(f"Memory increase: {memory_usage['increase_mb']:.1f} MB")
        logger.info(f"CPU usage: {cpu_usage:.1f}%")
        logger.info("-" * 40)
        logger.info(f"HTTP requests: {request_statistics['count']}")
        if request_statistics["count"] > 0:
            logger.info(
                f"Request timing - Avg: {request_statistics['avg']:.3f}s, "
                f"Min: {request_statistics['min']:.3f}s, "
                f"Max: {request_statistics['max']:.3f}s"
            )
            logger.info(
                f"Requests per second: {request_statistics['count'] / elapsed_time:.2f}"
            )
        logger.info("=" * 60)


class ChromeWebStoreLister:
    """
    Chrome Web Store item data collection and processing system.

    This class handles the complete process of fetching Chrome Web Store item
    data from sitemaps, processing items concurrently with rate limiting, and
    saving the results to JSON format with comprehensive error handling and
    performance monitoring.
    """

    def __init__(
        self,
        output_file: str,
        request_timeout: int,
        delay: float,
        max_workers: int,
        retry_attempts: int,
    ) -> None:
        """
        Initialize the Chrome Web Store item data collection system.

        Args:
            output_file: Path for the output JSON file containing collected data.
            request_timeout: HTTP request timeout duration in seconds.
            delay: Delay between consecutive requests in seconds (rate limiting).
            max_workers: Maximum number of concurrent worker threads.
            retry_attempts: Number of retry attempts for failed HTTP requests.
        """
        # Store configuration parameters
        self.output_file = output_file
        self.request_timeout = request_timeout
        self.delay = delay
        self.max_workers = max_workers
        self.retry_attempts = retry_attempts

        # Initialize performance monitoring system
        self.performance = PerformanceMonitor()

        # Initialize data collection statistics
        self.statistics = {
            "total_shards": 0,
            "failed_shards": 0,
            "total_urls": 0,
            "invalid_urls": 0,
            "failed_extractions": 0,
            "valid_items": 0,
            "duplicate_items": 0,
            "unique_items": 0,
        }

        # Configure application logging
        self._setup_logging()

        # Create HTTP session with retry strategy
        self.session = self._create_session()

    def _setup_logging(self) -> None:
        """
        Configure application logging for different environments.

        Configures logging with appropriate format and level based on environment
        variables, with special handling for GitHub Actions output formatting.
        """
        # Configure logging level from environment variable
        log_level = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()

        # Configure logging format for different environments
        log_format = DEFAULT_LOG_FORMAT
        if os.getenv("GITHUB_ACTIONS") == "true":
            # Use simplified format for GitHub Actions
            log_format = GITHUB_ACTIONS_LOG_FORMAT

        # Initialize logging configuration
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format=log_format,
            handlers=[logging.StreamHandler(sys.stdout)],
        )

        # Create logger instance for this class
        self.logger = logging.getLogger(__name__)

    def _create_session(self) -> requests.Session:
        """
        Create HTTP session with comprehensive retry strategy.

        Creates a configured requests session with automatic retry handling
        for transient failures and rate limiting scenarios.

        Returns:
            requests.Session: Configured session with retry strategy.
        """
        session = requests.Session()

        # Configure HTTP retry strategy for reliability
        retry_strategy = Retry(
            total=self.retry_attempts,
            backoff_factor=RETRY_BACKOFF_FACTOR,
            status_forcelist=RETRY_STATUS_FORCELIST,
            allowed_methods=RETRY_ALLOWED_METHODS,
        )

        # Apply retry strategy to HTTP and HTTPS adapters
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _fetch_sitemap(self, url: str) -> Optional[ET.Element]:
        """
        Fetch and parse XML sitemap from URL.

        Args:
            url: Sitemap URL.

        Returns:
            Optional[ET.Element]: Parsed XML root element or None if failed.
        """
        start_time = time.time()
        try:
            self.logger.debug(f"Fetching sitemap: {url}")
            response = self.session.get(url, timeout=self.request_timeout)
            response.raise_for_status()

            # Record request time
            request_duration = time.time() - start_time
            self.performance.record_request_time(request_duration)

            return ET.fromstring(response.content)
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch sitemap {url}: {e}")
            # Still record the failed request time
            request_duration = time.time() - start_time
            self.performance.record_request_time(request_duration)
            return None
        except ET.ParseError as e:
            self.logger.error(f"Failed to parse sitemap {url}: {e}")
            return None

    def _extract_shard_urls(self, sitemap_root: ET.Element) -> list[str]:
        """
        Extract shard URLs from main sitemap.

        Args:
            sitemap_root: Parsed sitemap XML root.

        Returns:
            list[str]: List of shard URLs.
        """
        shard_urls = []

        for sitemap in sitemap_root.findall(f"{SITEMAP_NAMESPACE}sitemap"):
            loc = sitemap.find(f"{SITEMAP_NAMESPACE}loc")
            if loc is not None and loc.text and "shard=" in loc.text:
                shard_urls.append(loc.text)

        self.logger.info(f"Found {len(shard_urls)} shard URLs")
        return shard_urls

    def _process_shard(self, shard_url: str) -> dict[str, Any]:
        """
        Process a single shard and extract item data.

        Args:
            shard_url: URL of the shard to process.

        Returns:
            dict[str, any]: Dictionary containing extracted items and statistics.
        """
        result = {
            "items": [],
            "stats": {
                "total_urls": 0,
                "invalid_urls": 0,
                "failed_extractions": 0,
                "valid_items": 0,
            },
        }

        try:
            shard_root = self._fetch_sitemap(shard_url)
            if shard_root is None:
                return result

            for url_elem in shard_root.findall(f"{SITEMAP_NAMESPACE}url"):
                loc = url_elem.find(f"{SITEMAP_NAMESPACE}loc")
                if loc is not None and loc.text:
                    result["stats"]["total_urls"] += 1

                    if is_valid_chrome_store_url(loc.text):
                        item = extract_item_data(loc.text)
                        if item:
                            result["items"].append(item)
                            result["stats"]["valid_items"] += 1
                        else:
                            result["stats"]["failed_extractions"] += 1
                    else:
                        result["stats"]["invalid_urls"] += 1

            # Respect rate limits
            time.sleep(self.delay)

        except Exception as e:
            self.logger.error(f"Error processing shard {shard_url}: {e}")

        return result

    def fetch_all_items(self) -> list[dict[str, str]]:
        """
        Fetch all items from Chrome Web Store sitemap.

        Returns:
            list[dict[str, str]]: List of all items with their metadata.
        """
        self.logger.info("Starting Chrome Web Store item data collection...")

        # Fetch main sitemap
        sitemap_root = self._fetch_sitemap(BASE_SITEMAP_URL)

        if sitemap_root is None:
            self.logger.error("Failed to fetch main sitemap")
            return []

        # Extract shard URLs
        shard_urls = self._extract_shard_urls(sitemap_root)
        if not shard_urls:
            self.logger.error("No shard URLs found")
            return []

        # Initialize statistics
        self.statistics["total_shards"] = len(shard_urls)
        all_items = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all shard processing tasks
            future_to_shard = {
                executor.submit(self._process_shard, shard_url): shard_url
                for shard_url in shard_urls
            }

            # Process completed tasks
            for i, future in enumerate(as_completed(future_to_shard), 1):
                shard_url = future_to_shard[future]
                self.logger.info(f"Processing shard {i}/{len(shard_urls)}")

                try:
                    shard_result = future.result()
                    shard_items = shard_result["items"]
                    shard_stats = shard_result["stats"]

                    # Accumulate items and statistics
                    all_items.extend(shard_items)
                    self.statistics["total_urls"] += shard_stats["total_urls"]
                    self.statistics["invalid_urls"] += shard_stats["invalid_urls"]
                    self.statistics["failed_extractions"] += shard_stats[
                        "failed_extractions"
                    ]
                    self.statistics["valid_items"] += shard_stats["valid_items"]

                    self.logger.debug(
                        f"Shard {shard_url} yielded {len(shard_items)} items "
                        f"({shard_stats['total_urls']} URLs processed, "
                        f"{shard_stats['invalid_urls']} invalid, "
                        f"{shard_stats['failed_extractions']} failed extractions)"
                    )
                except Exception as e:
                    self.statistics["failed_shards"] += 1
                    self.logger.error(f"Shard {shard_url} failed: {e}")

        # Remove duplicates based on item ID
        items_before_dedup = len(all_items)
        unique_items_dict = {item["id"]: item for item in all_items}
        unique_items = list(unique_items_dict.values())

        # Update final statistics
        self.statistics["duplicate_items"] = items_before_dedup - len(unique_items)
        self.statistics["unique_items"] = len(unique_items)

        # Log detailed statistics
        self._log_statistics()

        return unique_items

    def _log_statistics(self) -> None:
        """
        Log detailed data collection statistics and success metrics.
        """
        self.logger.info("=" * 60)
        self.logger.info("COLLECTION STATISTICS")
        self.logger.info("=" * 60)
        self.logger.info(f"Total shards processed: {self.statistics['total_shards']}")
        self.logger.info(f"Failed shards: {self.statistics['failed_shards']}")
        successful_shards = (
            self.statistics["total_shards"] - self.statistics["failed_shards"]
        )
        success_rate = successful_shards / max(self.statistics["total_shards"], 1) * 100
        self.logger.info(f"Success rate: {success_rate:.1f}%")
        self.logger.info("-" * 40)
        self.logger.info(f"Total URLs found: {self.statistics['total_urls']}")
        self.logger.info(f"Invalid URLs: {self.statistics['invalid_urls']}")
        self.logger.info(f"Failed extractions: {self.statistics['failed_extractions']}")
        self.logger.info(f"Valid items extracted: {self.statistics['valid_items']}")
        self.logger.info("-" * 40)
        self.logger.info(
            f"Duplicate items removed: {self.statistics['duplicate_items']}"
        )
        self.logger.info(f"Final unique items: {self.statistics['unique_items']}")
        self.logger.info("=" * 60)

    def save_data(self, data: list[dict[str, str]]) -> None:
        """
        Save data to JSON file with security validation.

        Args:
            data: List of items to save.
        """
        try:
            # Validate and sanitize output file path
            from src.utils import sanitize_filename

            safe_output_file = sanitize_filename(self.output_file)
            output_path = Path(safe_output_file)

            # Ensure parent directory exists and is writable
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Validate data before saving
            if not isinstance(data, list):
                raise ValueError("Data must be a list")

            validated_data = []
            for item in data:
                if isinstance(item, dict) and all(
                    key in item and isinstance(item[key], str)
                    for key in ["id", "name", "page", "file"]
                ):
                    validated_data.append(item)
                else:
                    self.logger.warning(f"Skipping invalid item: {item}")

            if len(validated_data) != len(data):
                self.logger.warning(
                    f"Filtered out {len(data) - len(validated_data)} invalid items"
                )

            # Save with secure settings
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(validated_data, f, indent=2, ensure_ascii=False)

            self.logger.info(
                f"Successfully saved {len(validated_data)} items to {safe_output_file}"
            )

            # Write GitHub Actions output variables for CI/CD integration
            if os.getenv("GITHUB_ACTIONS") == "true":
                github_output = os.getenv("GITHUB_OUTPUT")
                if github_output:
                    with open(github_output, "a", encoding="utf-8") as f:
                        f.write(f"items_count={len(validated_data)}\n")
                        f.write(f"output_file={safe_output_file}\n")
                        f.write(f"total_shards={self.statistics['total_shards']}\n")
                        f.write(f"failed_shards={self.statistics['failed_shards']}\n")
                        f.write(f"total_urls={self.statistics['total_urls']}\n")
                        f.write(f"invalid_urls={self.statistics['invalid_urls']}\n")
                        f.write(
                            f"failed_extractions={self.statistics['failed_extractions']}\n"
                        )
                        f.write(
                            f"duplicate_items={self.statistics['duplicate_items']}\n"
                        )

        except (OSError, ValueError) as e:
            self.logger.error(f"Failed to save data to {self.output_file}: {e}")
            sys.exit(1)

    def run(self) -> None:
        """
        Execute the complete Chrome Web Store item data collection process.

        This method orchestrates the entire workflow including fetching item
        data from sitemaps, processing items concurrently, validating results,
        and saving to output file with comprehensive performance monitoring.
        """
        try:
            self.logger.info("🚀 Starting Chrome Web Store item data collection...")

            # Log initial system state
            memory = self.performance.get_memory_usage()
            self.logger.info(f"Initial memory usage: {memory['current_mb']:.1f} MB")

            items = self.fetch_all_items()

            if not items:
                self.logger.warning("No items collected")
                if os.getenv("GITHUB_ACTIONS") == "true":
                    print("::warning::No items were collected from Chrome Web Store")
                return

            self.save_data(items)

            # Log final performance summary
            self.performance.log_performance_summary(self.logger)

        except KeyboardInterrupt:
            self.logger.info("Process interrupted by user")
            self.performance.log_performance_summary(self.logger)
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.performance.log_performance_summary(self.logger)
            sys.exit(1)
