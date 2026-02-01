"""
Lighthouse Performance Analyzer

Runs Google Lighthouse via CLI to collect real performance metrics,
Core Web Vitals, and optimization opportunities.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class LighthouseRunner:
    """Runs Lighthouse audits and parses results."""

    def __init__(
        self,
        chrome_flags: Optional[list[str]] = None,
        timeout: int = 60,
        only_categories: Optional[list[str]] = None,
    ):
        """
        Initialize the Lighthouse runner.

        Args:
            chrome_flags: Additional Chrome flags (e.g., ['--headless'])
            timeout: Timeout for Lighthouse execution in seconds
            only_categories: Specific categories to run (performance, accessibility, best-practices, seo, pwa)
        """
        self.chrome_flags = chrome_flags or ["--headless", "--no-sandbox"]
        self.timeout = timeout
        self.only_categories = only_categories or [
            "performance",
            "accessibility",
            "best-practices",
            "seo",
        ]

    def run_lighthouse(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Run Lighthouse on a URL and return parsed results.

        Args:
            url: The URL to audit

        Returns:
            Dictionary containing Lighthouse results, or None if failed
        """
        try:
            logger.info(f"Running Lighthouse on {url}")

            # Create temporary file for output
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as tmp_file:
                output_path = tmp_file.name

            # Build Lighthouse command
            cmd = [
                "lighthouse",
                url,
                "--output=json",
                f"--output-path={output_path}",
                "--quiet",
                "--chrome-flags=" + " ".join(self.chrome_flags),
            ]

            # Add only-categories if specified
            if self.only_categories:
                for category in self.only_categories:
                    cmd.append(f"--only-categories={category}")

            # Run Lighthouse
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )

            if result.returncode != 0:
                logger.error(f"Lighthouse failed for {url}: {result.stderr}")
                return None

            # Read and parse JSON output
            with open(output_path, "r") as f:
                lighthouse_data = json.load(f)

            # Clean up temp file
            Path(output_path).unlink(missing_ok=True)

            logger.info(f"Lighthouse completed successfully for {url}")
            return self._parse_lighthouse_results(lighthouse_data)

        except subprocess.TimeoutExpired:
            logger.error(f"Lighthouse timeout for {url} after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"Error running Lighthouse on {url}: {e}")
            return None

    def _parse_lighthouse_results(
        self, lhr: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse Lighthouse report and extract key metrics.

        Args:
            lhr: Lighthouse report JSON (lhr = Lighthouse Result)

        Returns:
            Dictionary with parsed metrics
        """
        try:
            # Extract category scores
            categories = lhr.get("categories", {})
            scores = {
                "performance": self._get_score(categories.get("performance")),
                "accessibility": self._get_score(categories.get("accessibility")),
                "best_practices": self._get_score(
                    categories.get("best-practices")
                ),
                "seo": self._get_score(categories.get("seo")),
                "pwa": self._get_score(categories.get("pwa")) if categories.get("pwa") else 0,
            }

            # Extract performance metrics (audits)
            audits = lhr.get("audits", {})

            # Core Web Vitals and performance metrics
            metrics = {
                "fcp": self._get_metric_value(
                    audits.get("first-contentful-paint")
                ),  # First Contentful Paint
                "lcp": self._get_metric_value(
                    audits.get("largest-contentful-paint")
                ),  # Largest Contentful Paint
                "si": self._get_metric_value(
                    audits.get("speed-index")
                ),  # Speed Index
                "tti": self._get_metric_value(
                    audits.get("interactive")
                ),  # Time to Interactive
                "tbt": self._get_metric_value(
                    audits.get("total-blocking-time")
                ),  # Total Blocking Time
                "cls": self._get_metric_value(
                    audits.get("cumulative-layout-shift")
                ),  # Cumulative Layout Shift
                "fmp": self._get_metric_value(
                    audits.get("first-meaningful-paint")
                ),  # First Meaningful Paint
                "max_potential_fid": self._get_metric_value(
                    audits.get("max-potential-fid")
                ),  # Max Potential FID
            }

            # Extract optimization opportunities
            opportunities = self._extract_opportunities(audits)

            # Extract diagnostics
            diagnostics = self._extract_diagnostics(lhr)

            # Screenshot thumbnails (optional, for visual analysis)
            screenshots = self._extract_screenshots(audits)

            return {
                "scores": scores,
                "metrics": metrics,
                "opportunities": opportunities,
                "diagnostics": diagnostics,
                "screenshots": screenshots,
                "fetch_time": datetime.now().isoformat(),
                "user_agent": lhr.get("userAgent", ""),
                "requested_url": lhr.get("requestedUrl", ""),
                "final_url": lhr.get("finalUrl", ""),
            }

        except Exception as e:
            logger.error(f"Error parsing Lighthouse results: {e}")
            return {}

    def _get_score(self, category: Optional[Dict]) -> Optional[float]:
        """Extract score from category (0-1) and convert to 0-100."""
        if not category:
            return None
        score = category.get("score")
        return round(score * 100, 1) if score is not None else None

    def _get_metric_value(self, audit: Optional[Dict]) -> Optional[float]:
        """Extract numeric value from audit."""
        if not audit:
            return None
        return audit.get("numericValue")

    def _extract_opportunities(self, audits: Dict) -> list[Dict[str, Any]]:
        """
        Extract optimization opportunities from audits.

        Returns list of opportunities with potential savings.
        """
        opportunities = []

        # Key performance opportunities to extract
        opportunity_audits = [
            "unused-css-rules",
            "unused-javascript",
            "modern-image-formats",
            "offscreen-images",
            "render-blocking-resources",
            "unminified-css",
            "unminified-javascript",
            "efficient-animated-content",
            "duplicated-javascript",
            "legacy-javascript",
            "total-byte-weight",
            "uses-optimized-images",
            "uses-text-compression",
            "uses-responsive-images",
        ]

        for audit_id in opportunity_audits:
            audit = audits.get(audit_id)
            if audit and audit.get("details"):
                # Extract savings information
                opportunity = {
                    "id": audit_id,
                    "title": audit.get("title", ""),
                    "description": audit.get("description", ""),
                    "score": audit.get("score"),
                }

                # Add savings metrics if available
                if "overallSavingsMs" in audit.get("details", {}):
                    opportunity["savings_ms"] = audit["details"][
                        "overallSavingsMs"
                    ]
                if "overallSavingsBytes" in audit.get("details", {}):
                    opportunity["savings_bytes"] = audit["details"][
                        "overallSavingsBytes"
                    ]

                # Count of items (e.g., number of unoptimized images)
                if "items" in audit.get("details", {}):
                    opportunity["item_count"] = len(
                        audit["details"]["items"]
                    )

                opportunities.append(opportunity)

        return opportunities

    def _extract_diagnostics(self, lhr: Dict) -> Dict[str, Any]:
        """Extract diagnostic information from Lighthouse report."""
        audits = lhr.get("audits", {})

        diagnostics = {
            "dom_size": None,
            "resource_summary": {},
            "network_requests": 0,
            "main_thread_work": None,
        }

        # DOM size
        dom_audit = audits.get("dom-size")
        if dom_audit and dom_audit.get("numericValue"):
            diagnostics["dom_size"] = dom_audit["numericValue"]

        # Resource summary
        resource_audit = audits.get("resource-summary")
        if resource_audit and resource_audit.get("details", {}).get("items"):
            for item in resource_audit["details"]["items"]:
                resource_type = item.get("resourceType", "unknown")
                diagnostics["resource_summary"][resource_type] = {
                    "requests": item.get("requestCount", 0),
                    "transfer_size": item.get("transferSize", 0),
                }

        # Network requests count
        network_audit = audits.get("network-requests")
        if (
            network_audit
            and network_audit.get("details", {}).get("items")
        ):
            diagnostics["network_requests"] = len(
                network_audit["details"]["items"]
            )

        # Main thread work
        main_thread_audit = audits.get("mainthread-work-breakdown")
        if main_thread_audit and main_thread_audit.get("numericValue"):
            diagnostics["main_thread_work"] = main_thread_audit[
                "numericValue"
            ]

        return diagnostics

    def _extract_screenshots(self, audits: Dict) -> list[Dict[str, str]]:
        """Extract screenshot thumbnails if available."""
        screenshot_audit = audits.get("screenshot-thumbnails")
        if (
            screenshot_audit
            and screenshot_audit.get("details", {}).get("items")
        ):
            return screenshot_audit["details"]["items"]
        return []

    def get_metrics_status(
        self, metrics: Dict[str, Optional[float]]
    ) -> Dict[str, str]:
        """
        Categorize metrics into good/needs-improvement/poor based on Google thresholds.

        Args:
            metrics: Dictionary of metric values

        Returns:
            Dictionary with status for each metric
        """
        # Google's Core Web Vitals thresholds (in milliseconds unless noted)
        thresholds = {
            "lcp": {"good": 2500, "poor": 4000},  # ms
            "fcp": {"good": 1800, "poor": 3000},  # ms
            "tbt": {"good": 200, "poor": 600},  # ms
            "cls": {"good": 0.1, "poor": 0.25},  # score (unitless)
            "si": {"good": 3400, "poor": 5800},  # ms
            "tti": {"good": 3800, "poor": 7300},  # ms
        }

        statuses = {}
        for metric, value in metrics.items():
            if value is None or metric not in thresholds:
                statuses[metric] = "unknown"
                continue

            threshold = thresholds[metric]
            if value <= threshold["good"]:
                statuses[metric] = "good"
            elif value <= threshold["poor"]:
                statuses[metric] = "needs-improvement"
            else:
                statuses[metric] = "poor"

        return statuses


def run_lighthouse_for_url(url: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to run Lighthouse on a single URL.

    Args:
        url: URL to audit

    Returns:
        Parsed Lighthouse results or None if failed
    """
    runner = LighthouseRunner()
    return runner.run_lighthouse(url)
