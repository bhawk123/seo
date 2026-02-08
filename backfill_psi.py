#!/usr/bin/env python3
"""
Backfill PageSpeed Insights data for pages missing Lighthouse scores.

This script identifies pages in a crawl directory that don't have PSI/Lighthouse
data and fetches it from the Google PageSpeed Insights API.

Usage:
    python backfill_psi.py <crawl_dir> [--dry-run] [--max-pages N]

Examples:
    python backfill_psi.py crawls/rsmus.com/2026-02-06_093152/
    python backfill_psi.py crawls/rsmus.com/2026-02-06_093152/ --dry-run
    python backfill_psi.py crawls/rsmus.com/2026-02-06_093152/ --max-pages 10
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Load .env file
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from seo.external.pagespeed_insights import PageSpeedInsightsAPI


def get_missing_psi_pages(crawl_dir: Path) -> list[tuple[str, str]]:
    """
    Find pages that are missing PSI/Lighthouse data.

    Returns:
        List of (url, page_filename) tuples for pages missing PSI data
    """
    pages_dir = crawl_dir / "pages"
    lighthouse_dir = crawl_dir / "lighthouse"

    if not pages_dir.exists():
        print(f"Error: Pages directory not found: {pages_dir}")
        return []

    # Get all page files
    page_files = list(pages_dir.glob("*.json"))

    # Get existing lighthouse files
    existing_lighthouse = set()
    if lighthouse_dir.exists():
        for f in lighthouse_dir.glob("*.json"):
            if f.name != "viewer.html":
                existing_lighthouse.add(f.stem)

    missing = []
    for page_file in page_files:
        page_id = page_file.stem

        # Check if lighthouse data exists
        if page_id not in existing_lighthouse:
            # Load page to get URL
            try:
                with open(page_file) as f:
                    page_data = json.load(f)
                    url = page_data.get("url", "")
                    if url:
                        missing.append((url, page_id))
            except Exception as e:
                print(f"Warning: Could not read {page_file}: {e}")

    return missing


def save_psi_result(crawl_dir: Path, page_id: str, psi_data: dict) -> None:
    """Save PSI result to lighthouse directory."""
    lighthouse_dir = crawl_dir / "lighthouse"
    lighthouse_dir.mkdir(exist_ok=True)

    output_file = lighthouse_dir / f"{page_id}.json"
    with open(output_file, "w") as f:
        json.dump(psi_data, f, indent=2)

    print(f"  Saved: {output_file.name}")


def update_page_metadata(crawl_dir: Path, page_id: str, psi_data: dict) -> None:
    """Update the page JSON file with Lighthouse scores."""
    page_file = crawl_dir / "pages" / f"{page_id}.json"

    if not page_file.exists():
        return

    try:
        with open(page_file) as f:
            page_data = json.load(f)

        # Update with Lighthouse scores
        page_data["lighthouse_performance_score"] = psi_data.get("performance_score")
        page_data["lighthouse_accessibility_score"] = psi_data.get("accessibility_score")
        page_data["lighthouse_best_practices_score"] = psi_data.get("best_practices_score")
        page_data["lighthouse_seo_score"] = psi_data.get("seo_score")
        page_data["lighthouse_pwa_score"] = psi_data.get("pwa_score")

        # Core Web Vitals
        page_data["lighthouse_fcp"] = psi_data.get("fcp")
        page_data["lighthouse_lcp"] = psi_data.get("lcp")
        page_data["lighthouse_cls"] = psi_data.get("cls")
        page_data["lighthouse_tbt"] = psi_data.get("tbt")
        page_data["lighthouse_si"] = psi_data.get("si")
        page_data["lighthouse_tti"] = psi_data.get("tti")

        with open(page_file, "w") as f:
            json.dump(page_data, f, indent=2)

        print(f"  Updated page metadata: {page_id}")

    except Exception as e:
        print(f"  Warning: Could not update page metadata: {e}")


def sync_advanced_analysis(crawl_dir: Path) -> int:
    """
    Sync lighthouse data from page files to advanced_analysis.json.

    This is necessary because the report generator reads from advanced_analysis.json,
    not from individual page files.

    Returns:
        Number of fields updated
    """
    pages_dir = crawl_dir / "pages"
    advanced_file = crawl_dir / "advanced_analysis.json"

    if not advanced_file.exists():
        print("  Warning: advanced_analysis.json not found, skipping sync")
        return 0

    try:
        with open(advanced_file) as f:
            advanced = json.load(f)

        metadata_list = advanced.get('metadata_list', [])

        # Build URL to page data mapping
        page_data = {}
        for page_file in pages_dir.glob('*.json'):
            with open(page_file) as f:
                data = json.load(f)
                url = data.get('url', '')
                if url:
                    page_data[url] = data

        # Lighthouse fields to sync
        lh_fields = [
            'lighthouse_performance_score', 'lighthouse_accessibility_score',
            'lighthouse_best_practices_score', 'lighthouse_seo_score',
            'lighthouse_pwa_score', 'lighthouse_fcp', 'lighthouse_lcp',
            'lighthouse_cls', 'lighthouse_tbt', 'lighthouse_si', 'lighthouse_tti'
        ]

        # Update metadata_list
        updated = 0
        for entry in metadata_list:
            url = entry.get('url', '')
            if url in page_data:
                page = page_data[url]
                for field in lh_fields:
                    if page.get(field) is not None and entry.get(field) is None:
                        entry[field] = page[field]
                        updated += 1

        if updated > 0:
            with open(advanced_file, 'w') as f:
                json.dump(advanced, f, indent=2)

        return updated

    except Exception as e:
        print(f"  Warning: Could not sync advanced_analysis.json: {e}")
        return 0


async def backfill_psi(
    crawl_dir: Path,
    api_key: str,
    strategy: str = "mobile",
    max_pages: int = None,
    dry_run: bool = False
) -> dict:
    """
    Backfill PSI data for pages missing Lighthouse scores.

    Returns:
        Statistics about the backfill operation
    """
    missing_pages = get_missing_psi_pages(crawl_dir)

    if not missing_pages:
        print("All pages have PSI data. Nothing to backfill.")
        return {"total": 0, "success": 0, "failed": 0}

    # Limit pages if specified
    if max_pages and max_pages < len(missing_pages):
        missing_pages = missing_pages[:max_pages]

    print(f"\nFound {len(missing_pages)} pages missing PSI data:")
    for url, page_id in missing_pages:
        print(f"  - {url}")

    if dry_run:
        print("\n[DRY RUN] Would fetch PSI data for the above pages.")
        return {"total": len(missing_pages), "success": 0, "failed": 0, "dry_run": True}

    print(f"\nFetching PSI data for {len(missing_pages)} pages...")
    print("=" * 60)

    # Initialize PSI API
    psi_api = PageSpeedInsightsAPI(api_key=api_key, strategy=strategy)

    stats = {"total": len(missing_pages), "success": 0, "failed": 0}

    for i, (url, page_id) in enumerate(missing_pages, 1):
        print(f"\n[{i}/{len(missing_pages)}] {url}")

        try:
            psi_data = await psi_api.analyze(url)

            if psi_data:
                # Save to lighthouse directory
                save_psi_result(crawl_dir, page_id, psi_data)

                # Update page metadata
                update_page_metadata(crawl_dir, page_id, psi_data)

                perf = psi_data.get("performance_score", "N/A")
                a11y = psi_data.get("accessibility_score", "N/A")
                seo = psi_data.get("seo_score", "N/A")
                print(f"  Performance: {perf}, Accessibility: {a11y}, SEO: {seo}")

                stats["success"] += 1
            else:
                print("  No data returned")
                stats["failed"] += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            stats["failed"] += 1

    print("\n" + "=" * 60)
    print(f"Backfill complete: {stats['success']} success, {stats['failed']} failed")

    # Show API stats
    api_stats = psi_api.get_stats()
    print(f"API requests: {api_stats['total_requests']} total, {api_stats['success_rate']}% success rate")

    # Sync lighthouse data to advanced_analysis.json for report generation
    if stats["success"] > 0:
        print("\nSyncing lighthouse data to advanced_analysis.json...")
        synced = sync_advanced_analysis(crawl_dir)
        if synced > 0:
            print(f"  Synced {synced} lighthouse fields")
            print("\nTo regenerate the report, run:")
            print(f"  python regenerate_report.py {crawl_dir}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Backfill PageSpeed Insights data for pages missing Lighthouse scores"
    )
    parser.add_argument(
        "crawl_dir",
        type=Path,
        help="Path to the crawl directory"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making API calls"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum number of pages to backfill"
    )
    parser.add_argument(
        "--strategy",
        choices=["mobile", "desktop"],
        default="mobile",
        help="PSI analysis strategy (default: mobile)"
    )

    args = parser.parse_args()

    # Validate crawl directory
    if not args.crawl_dir.exists():
        print(f"Error: Crawl directory not found: {args.crawl_dir}")
        sys.exit(1)

    # Check API key
    api_key = os.getenv("GOOGLE_PSI_API_KEY")
    if not api_key and not args.dry_run:
        print("Error: GOOGLE_PSI_API_KEY not found in environment")
        print("Add to .env: GOOGLE_PSI_API_KEY=your_key_here")
        sys.exit(1)

    print(f"Crawl directory: {args.crawl_dir}")
    print(f"Strategy: {args.strategy}")
    if args.max_pages:
        print(f"Max pages: {args.max_pages}")
    if args.dry_run:
        print("Mode: DRY RUN")

    # Run backfill
    stats = asyncio.run(backfill_psi(
        crawl_dir=args.crawl_dir,
        api_key=api_key or "",
        strategy=args.strategy,
        max_pages=args.max_pages,
        dry_run=args.dry_run
    ))

    # Exit with error if any failures
    if stats.get("failed", 0) > 0 and not args.dry_run:
        sys.exit(1)


if __name__ == "__main__":
    main()
