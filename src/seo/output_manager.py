"""Output manager for organizing crawl results with timestamps."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from seo.models import PageMetadata, TechnicalIssues

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class OutputManager:
    """Manages organized output of crawl results with timestamps and directories."""

    def __init__(self, base_output_dir: str = "crawls"):
        """Initialize output manager.

        Args:
            base_output_dir: Base directory for all crawl outputs
        """
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(exist_ok=True)

    def create_crawl_directory(self, start_url: str, timestamp: Optional[datetime] = None) -> Path:
        """Create a timestamped directory for this crawl.

        Args:
            start_url: The starting URL that was crawled
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Path to the created directory

        Example structure:
            crawls/
            └── example.com/
                ├── 2025-11-23_143022/
                │   ├── metadata.json
                │   ├── technical_issues.json
                │   ├── recommendations.txt
                │   ├── summary.txt
                │   └── pages/
                │       ├── index.json
                │       ├── about.json
                │       └── contact.json
                └── 2025-11-23_150845/
                    └── ...
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Extract domain from URL
        domain = urlparse(start_url).netloc
        # Clean domain for filesystem
        domain = domain.replace(":", "_").replace("/", "_")

        # Create timestamp string: YYYY-MM-DD_HHMMSS
        timestamp_str = timestamp.strftime("%Y-%m-%d_%H%M%S")

        # Create directory structure
        crawl_dir = self.base_output_dir / domain / timestamp_str
        crawl_dir.mkdir(parents=True, exist_ok=True)

        # Create pages subdirectory
        (crawl_dir / "pages").mkdir(exist_ok=True)

        return crawl_dir

    def save_crawl_results(
        self,
        crawl_dir: Path,
        start_url: str,
        site_data: Dict[str, PageMetadata],
        technical_issues: TechnicalIssues,
        llm_recommendations: str,
        crawl_stats: Optional[Dict] = None,
        advanced_analysis: Optional[Dict] = None,
    ) -> None:
        """Save complete crawl results to the directory.

        Args:
            crawl_dir: Directory to save to
            start_url: Starting URL
            site_data: Dictionary of URL -> PageMetadata
            technical_issues: Technical issues found
            llm_recommendations: LLM-generated recommendations
            crawl_stats: Optional crawl statistics
            advanced_analysis: Optional advanced analysis results
        """
        # 1. Save metadata.json (overall crawl info)
        metadata = {
            "start_url": start_url,
            "crawled_at": datetime.now().isoformat(),
            "total_pages": len(site_data),
            "urls_crawled": list(site_data.keys()),
            "stats": crawl_stats or {},
        }
        self._save_json(crawl_dir / "metadata.json", metadata)

        # 2. Save technical_issues.json
        issues_dict = {
            "missing_titles": technical_issues.missing_titles,
            "duplicate_titles": technical_issues.duplicate_titles,
            "short_titles": [
                {"url": url, "length": length}
                for url, length in technical_issues.short_titles
            ],
            "long_titles": [
                {"url": url, "length": length}
                for url, length in technical_issues.long_titles
            ],
            "missing_meta_descriptions": technical_issues.missing_meta_descriptions,
            "short_meta_descriptions": [
                {"url": url, "length": length}
                for url, length in technical_issues.short_meta_descriptions
            ],
            "long_meta_descriptions": [
                {"url": url, "length": length}
                for url, length in technical_issues.long_meta_descriptions
            ],
            "missing_h1": technical_issues.missing_h1,
            "multiple_h1": [
                {"url": url, "count": count}
                for url, count in technical_issues.multiple_h1
            ],
            "images_without_alt": [
                {"url": url, "missing": missing, "total": total}
                for url, missing, total in technical_issues.images_without_alt
            ],
            "slow_pages": [
                {"url": url, "load_time": time}
                for url, time in technical_issues.slow_pages
            ],
            "thin_content": [
                {"url": url, "word_count": count}
                for url, count in technical_issues.thin_content
            ],
            "missing_canonical": technical_issues.missing_canonical,
            "missing_viewport": technical_issues.missing_viewport,
            "missing_lang": technical_issues.missing_lang,
            "non_https": technical_issues.non_https,
        }
        self._save_json(crawl_dir / "technical_issues.json", issues_dict)

        # 3. Save recommendations.txt
        with open(crawl_dir / "recommendations.txt", "w", encoding="utf-8") as f:
            f.write(llm_recommendations)

        # 3.5. Save advanced_analysis.json (if available)
        if advanced_analysis:
            # Convert advanced analysis to JSON-serializable format
            advanced_dict = self._serialize_advanced_analysis(advanced_analysis)
            self._save_json(crawl_dir / "advanced_analysis.json", advanced_dict)

        # 4. Save individual page data
        pages_dir = crawl_dir / "pages"
        for url, page in site_data.items():
            page_data = self._page_metadata_to_dict(page)
            # Create safe filename from URL
            filename = self._url_to_filename(url)
            self._save_json(pages_dir / f"{filename}.json", page_data)

        # 5. Save summary.txt (human-readable)
        self._save_summary(crawl_dir / "summary.txt", start_url, site_data, technical_issues, crawl_stats)

        # 6. Create latest.txt symlink (so you can always find the latest crawl)
        self._create_latest_link(crawl_dir)

    def save_lighthouse_reports(
        self,
        crawl_dir: Path,
        psi_results: dict,
    ) -> None:
        """Save individual PageSpeed Insights reports to lighthouse/ subdirectory.

        Args:
            crawl_dir: Directory to save reports in
            psi_results: Dictionary mapping URL to raw PSI result data
        """
        if not psi_results:
            return

        lighthouse_dir = crawl_dir / "lighthouse"
        lighthouse_dir.mkdir(exist_ok=True)

        for url, psi_data in psi_results.items():
            # Create safe filename from URL
            filename = self._url_to_filename(url)
            report_path = lighthouse_dir / f"{filename}.json"

            # Add URL to data for reference
            # Include Lighthouse metadata for full provenance (Epic 3)
            report_data = {
                "url": url,
                "strategy": psi_data.get("strategy", "mobile"),
                "fetch_time": psi_data.get("fetch_time"),
                "lighthouse_metadata": {
                    "version": psi_data.get("lighthouse_version"),
                    "user_agent": psi_data.get("user_agent"),
                    "final_url": psi_data.get("final_url"),
                    "run_warnings": psi_data.get("run_warnings", []),
                },
                "scores": {
                    "performance": psi_data.get("performance_score"),
                    "accessibility": psi_data.get("accessibility_score"),
                    "best_practices": psi_data.get("best_practices_score"),
                    "seo": psi_data.get("seo_score"),
                    "pwa": psi_data.get("pwa_score"),
                },
                "metrics": {
                    "fcp": psi_data.get("fcp"),
                    "lcp": psi_data.get("lcp"),
                    "cls": psi_data.get("cls"),
                    "tbt": psi_data.get("tbt"),
                    "si": psi_data.get("si"),
                    "tti": psi_data.get("tti"),
                },
                "opportunities": psi_data.get("opportunities", []),
                "crux_data": psi_data.get("crux_data"),
            }

            self._save_json(report_path, report_data)

        # Copy the viewer HTML template
        viewer_src = Path(__file__).parent.parent.parent / "templates" / "lighthouse_viewer.html"
        viewer_dst = lighthouse_dir / "viewer.html"
        if viewer_src.exists() and not viewer_dst.exists():
            import shutil
            shutil.copy(viewer_src, viewer_dst)

    def save_psi_coverage(
        self,
        crawl_dir: Path,
        coverage_stats: dict,
    ) -> None:
        """Save PSI coverage statistics for evidence and reporting.

        Args:
            crawl_dir: Directory to save stats in
            coverage_stats: Coverage statistics from crawler.get_psi_coverage()
        """
        if not coverage_stats:
            return

        lighthouse_dir = crawl_dir / "lighthouse"
        lighthouse_dir.mkdir(exist_ok=True)

        coverage_path = lighthouse_dir / "_coverage.json"

        # Add timestamp for evidence trail
        coverage_data = {
            'timestamp': datetime.now().isoformat(),
            **coverage_stats,
        }

        with open(coverage_path, "w") as f:
            json.dump(coverage_data, f, indent=2)

        logger.info(f"PSI coverage stats saved to {coverage_path}")

        # Log warning if coverage is below threshold
        if not coverage_stats.get('meets_threshold', True):
            threshold = coverage_stats.get('threshold', 90.0)
            logger.warning(
                f"PSI coverage ({coverage_stats.get('coverage_percentage', 0):.1f}%) "
                f"is below {threshold}% threshold"
            )

    def _page_metadata_to_dict(self, page: PageMetadata) -> dict:
        """Convert PageMetadata to dictionary for JSON serialization.

        Args:
            page: PageMetadata object

        Returns:
            Dictionary representation
        """
        from dataclasses import asdict

        data = asdict(page)

        # Convert datetime to ISO format
        if data.get("crawled_at"):
            data["crawled_at"] = page.crawled_at.isoformat()

        # Remove large content_text to keep files smaller
        if "content_text" in data:
            data["content_text_length"] = len(data.get("content_text", ""))
            del data["content_text"]

        return data

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to safe filename.

        Args:
            url: URL to convert

        Returns:
            Safe filename string

        Examples:
            https://example.com -> example.com_index
            https://example.com/about -> example.com_about
            https://example.com/blog/post-1 -> example.com_blog_post-1
        """
        parsed = urlparse(url)
        domain = parsed.netloc.replace(":", "_")
        path = parsed.path.strip("/").replace("/", "_").replace(".", "_")

        if not path:
            path = "index"

        # Limit length
        filename = f"{domain}_{path}"[:200]

        # Remove any remaining unsafe characters
        filename = "".join(c if c.isalnum() or c in "_-" else "_" for c in filename)

        return filename

    def _save_json(self, filepath: Path, data: dict) -> None:
        """Save data as formatted JSON.

        Args:
            filepath: Path to save to
            data: Data to save
        """
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, cls=DateTimeEncoder)

    def _save_summary(
        self,
        filepath: Path,
        start_url: str,
        site_data: Dict[str, PageMetadata],
        technical_issues: TechnicalIssues,
        crawl_stats: Optional[Dict],
    ) -> None:
        """Save human-readable summary.

        Args:
            filepath: Path to save to
            start_url: Starting URL
            site_data: Site data
            technical_issues: Technical issues
            crawl_stats: Crawl statistics
        """
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("SEO CRAWL SUMMARY\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"Start URL: {start_url}\n")
            f.write(f"Crawled at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total pages: {len(site_data)}\n\n")

            if crawl_stats:
                f.write("CRAWL STATISTICS\n")
                f.write("-" * 60 + "\n")
                for key, value in crawl_stats.items():
                    f.write(f"{key}: {value}\n")
                f.write("\n")

            f.write("TECHNICAL ISSUES\n")
            f.write("-" * 60 + "\n")
            f.write(f"Missing titles: {len(technical_issues.missing_titles)}\n")
            f.write(f"Duplicate titles: {len(technical_issues.duplicate_titles)}\n")
            f.write(f"Missing meta descriptions: {len(technical_issues.missing_meta_descriptions)}\n")
            f.write(f"Short meta descriptions: {len(technical_issues.short_meta_descriptions)}\n")
            f.write(f"Missing H1 tags: {len(technical_issues.missing_h1)}\n")
            f.write(f"Images without alt: {len(technical_issues.images_without_alt)}\n")
            f.write(f"Slow pages (>3s): {len(technical_issues.slow_pages)}\n")
            f.write(f"Thin content (<300w): {len(technical_issues.thin_content)}\n")
            f.write(f"Missing canonical: {len(technical_issues.missing_canonical)}\n")
            f.write(f"Missing viewport: {len(technical_issues.missing_viewport)}\n")
            f.write(f"Non-HTTPS pages: {len(technical_issues.non_https)}\n")
            f.write("\n")

            f.write("PAGES CRAWLED\n")
            f.write("-" * 60 + "\n")
            for i, url in enumerate(site_data.keys(), 1):
                f.write(f"{i:3d}. {url}\n")

    def _create_latest_link(self, crawl_dir: Path) -> None:
        """Create/update 'latest' symlink to this crawl.

        Args:
            crawl_dir: Directory for this crawl
        """
        latest_link = crawl_dir.parent / "latest"

        # Remove old symlink if exists
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()

        # Create new symlink (relative)
        try:
            latest_link.symlink_to(crawl_dir.name)
        except (OSError, NotImplementedError):
            # Symlinks might not work on all systems (Windows)
            # Create a text file instead
            with open(crawl_dir.parent / "latest.txt", "w") as f:
                f.write(str(crawl_dir.name))

    def get_previous_crawls(self, domain: str) -> list[Path]:
        """Get list of previous crawl directories for a domain.

        Args:
            domain: Domain name

        Returns:
            List of crawl directories, sorted by timestamp (newest first)
        """
        domain_dir = self.base_output_dir / domain
        if not domain_dir.exists():
            return []

        crawl_dirs = [
            d for d in domain_dir.iterdir()
            if d.is_dir() and d.name != "latest"
        ]

        # Sort by timestamp (directory name)
        return sorted(crawl_dirs, reverse=True)

    def compare_crawls(self, domain: str, crawl1: str, crawl2: str) -> dict:
        """Compare two crawls for the same domain.

        Args:
            domain: Domain name
            crawl1: First crawl timestamp directory name
            crawl2: Second crawl timestamp directory name

        Returns:
            Dictionary with comparison results
        """
        dir1 = self.base_output_dir / domain / crawl1
        dir2 = self.base_output_dir / domain / crawl2

        # Load metadata
        meta1 = self._load_json(dir1 / "metadata.json")
        meta2 = self._load_json(dir2 / "metadata.json")

        # Load technical issues
        issues1 = self._load_json(dir1 / "technical_issues.json")
        issues2 = self._load_json(dir2 / "technical_issues.json")

        return {
            "crawl1": crawl1,
            "crawl2": crawl2,
            "pages_diff": meta2["total_pages"] - meta1["total_pages"],
            "new_pages": list(set(meta2["urls_crawled"]) - set(meta1["urls_crawled"])),
            "removed_pages": list(set(meta1["urls_crawled"]) - set(meta2["urls_crawled"])),
            "issues_diff": {
                "missing_titles": len(issues2["missing_titles"]) - len(issues1["missing_titles"]),
                "missing_descriptions": len(issues2["missing_meta_descriptions"]) - len(issues1["missing_meta_descriptions"]),
                "slow_pages": len(issues2["slow_pages"]) - len(issues1["slow_pages"]),
                "thin_content": len(issues2["thin_content"]) - len(issues1["thin_content"]),
            },
        }

    def _serialize_advanced_analysis(self, advanced_analysis: Dict) -> dict:
        """Convert advanced analysis objects to JSON-serializable format.

        Args:
            advanced_analysis: Advanced analysis results

        Returns:
            JSON-serializable dictionary
        """
        from dataclasses import asdict, is_dataclass

        def to_dict(item):
            """Convert item to dict, handling both dataclasses and dicts."""
            if is_dataclass(item) and not isinstance(item, type):
                return asdict(item)
            return item

        result = {}

        # Serialize content quality metrics
        if 'content_quality' in advanced_analysis:
            result['content_quality'] = [
                to_dict(item) for item in advanced_analysis['content_quality']
            ]

        # Serialize security analysis
        if 'security' in advanced_analysis:
            result['security'] = [
                to_dict(item) for item in advanced_analysis['security']
            ]

        # Serialize URL structure analysis
        if 'url_structure' in advanced_analysis:
            result['url_structure'] = [
                to_dict(item) for item in advanced_analysis['url_structure']
            ]

        # Mobile and international are already dicts
        if 'mobile' in advanced_analysis:
            result['mobile'] = advanced_analysis['mobile']

        if 'international' in advanced_analysis:
            result['international'] = advanced_analysis['international']

        # Add metadata_list for Lighthouse and CWV data
        if 'metadata_list' in advanced_analysis:
            result['metadata_list'] = advanced_analysis['metadata_list']

        # Add crawlability analysis
        if 'crawlability' in advanced_analysis:
            result['crawlability'] = advanced_analysis['crawlability']

        # Add technology analysis
        if 'technology' in advanced_analysis:
            result['technology'] = advanced_analysis['technology']

        # Add LLM evidence (Epic 1)
        if 'llm_evidence' in advanced_analysis:
            result['llm_evidence'] = advanced_analysis['llm_evidence']

        # Add CWV evidence (Epic 3)
        if 'cwv_evidence' in advanced_analysis:
            result['cwv_evidence'] = advanced_analysis['cwv_evidence']

        return result

    def _load_json(self, filepath: Path) -> dict:
        """Load JSON file.

        Args:
            filepath: Path to JSON file

        Returns:
            Loaded data
        """
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_crawl_state(self, crawl_dir: Path, state: dict) -> None:
        """Save crawl state for resume capability.

        Args:
            crawl_dir: Directory to save state to
            state: State dictionary containing:
                - version: State format version
                - status: "running", "paused", or "completed"
                - config: Crawl configuration (start_url, max_pages, rate_limit)
                - progress: Progress info (pages_crawled, started_at, last_updated)
                - visited_urls: List of already crawled URLs
                - queue: List of queued URLs with depths
        """
        state_file = crawl_dir / "crawl_state.json"
        state["progress"]["last_updated"] = datetime.now().isoformat()
        self._save_json(state_file, state)

    def load_crawl_state(self, crawl_dir: Path) -> Optional[dict]:
        """Load existing crawl state if available.

        Args:
            crawl_dir: Directory to load state from

        Returns:
            State dictionary if found and valid, None otherwise
        """
        state_file = crawl_dir / "crawl_state.json"
        if not state_file.exists():
            return None

        try:
            state = self._load_json(state_file)
            # Validate state has required fields
            required_fields = ["version", "status", "config", "progress", "visited_urls", "queue"]
            if all(field in state for field in required_fields):
                return state
            return None
        except (json.JSONDecodeError, KeyError):
            return None

    def find_latest_crawl(self, domain: str) -> Optional[Path]:
        """Find most recent crawl directory for a domain.

        Args:
            domain: Domain name (e.g., "www.example.com")

        Returns:
            Path to most recent crawl directory, or None if not found
        """
        domain_dir = self.base_output_dir / domain
        if not domain_dir.exists():
            return None

        # Get all timestamp directories
        crawl_dirs = [
            d for d in domain_dir.iterdir()
            if d.is_dir() and d.name != "latest"
        ]

        if not crawl_dirs:
            return None

        # Sort by timestamp (directory name) and return the latest
        return sorted(crawl_dirs, reverse=True)[0]

    def find_resumable_crawls(self, domain: str) -> List[Path]:
        """Find all crawl directories for a domain that can be resumed.

        Args:
            domain: Domain name (e.g., "www.example.com")

        Returns:
            List of crawl directories with "paused" status, sorted newest first
        """
        domain_dir = self.base_output_dir / domain
        if not domain_dir.exists():
            return []

        resumable = []
        for d in domain_dir.iterdir():
            if d.is_dir() and d.name != "latest":
                state = self.load_crawl_state(d)
                if state and state.get("status") == "paused":
                    resumable.append(d)

        return sorted(resumable, reverse=True)
