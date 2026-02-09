#!/usr/bin/env python3
"""
Test script for Spectrum.com SEO analysis.

Crawls spectrum.com and runs PageSpeed Insights analysis on all pages.

Usage:
    python test_spectrum.py                    # Crawl 50 pages (default)
    python test_spectrum.py --max-pages 100    # Crawl 100 pages
    python test_spectrum.py --urls-only        # Just list discovered URLs
    python test_spectrum.py --psi-only         # Run PSI on existing crawl
"""

import argparse
import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Load environment
from dotenv import load_dotenv
load_dotenv()


def get_latest_crawl(base_dir: Path) -> Path:
    """Get the most recent crawl directory."""
    crawl_dirs = sorted(base_dir.glob("*/"), key=lambda x: x.stat().st_mtime, reverse=True)
    return crawl_dirs[0] if crawl_dirs else None


def run_crawl(start_url: str, max_pages: int, output_dir: Path) -> Path:
    """Run the async crawler on the target URL."""
    print(f"\nStarting crawl of {start_url}...")
    print(f"Max pages: {max_pages}")
    print("=" * 60)

    cmd = [
        sys.executable, "async_crawl.py", start_url,
        "--max-pages", str(max_pages),
        "--enable-psi",
        "--psi-sample", "1.0",
        "--psi-strategy", "mobile",
        "--rate-limit", "1.0",
    ]

    result = subprocess.run(cmd, check=True)

    # Find the crawl directory that was just created
    return get_latest_crawl(output_dir)


def run_psi_backfill(crawl_dir: Path) -> None:
    """Run PSI backfill for any missing pages."""
    print("\nChecking PSI coverage...")

    lighthouse_dir = crawl_dir / "lighthouse"
    pages_dir = crawl_dir / "pages"

    psi_count = len(list(lighthouse_dir.glob("*.json"))) if lighthouse_dir.exists() else 0
    page_count = len(list(pages_dir.glob("*.json"))) if pages_dir.exists() else 0

    print(f"Pages crawled: {page_count}")
    print(f"PSI analyses: {psi_count}")

    if psi_count < page_count:
        missing = page_count - psi_count
        print(f"\n{missing} pages missing PSI data. Running backfill...")
        subprocess.run([sys.executable, "backfill_psi.py", str(crawl_dir)], check=True)
    else:
        print("All pages have PSI data.")


def regenerate_report(crawl_dir: Path) -> None:
    """Regenerate the HTML report."""
    print("\nRegenerating report...")
    subprocess.run([sys.executable, "regenerate_report.py", str(crawl_dir)], check=True)


def list_urls(crawl_dir: Path) -> None:
    """List all crawled URLs."""
    import json

    pages_dir = crawl_dir / "pages"
    if not pages_dir.exists():
        print("No pages directory found")
        return

    urls = []
    for page_file in sorted(pages_dir.glob("*.json")):
        with open(page_file) as f:
            data = json.load(f)
            urls.append(data.get("url", ""))

    print(f"\nDiscovered {len(urls)} URLs:")
    print("-" * 60)
    for url in urls:
        print(url)


def main():
    parser = argparse.ArgumentParser(
        description="Test Spectrum.com with SEO analysis and PageSpeed Insights"
    )
    parser.add_argument(
        "--max-pages", type=int, default=50,
        help="Maximum pages to crawl (default: 50)"
    )
    parser.add_argument(
        "--urls-only", action="store_true",
        help="Just list discovered URLs from existing crawl"
    )
    parser.add_argument(
        "--psi-only", action="store_true",
        help="Only run PSI backfill on existing crawl (no new crawl)"
    )
    parser.add_argument(
        "--report-only", action="store_true",
        help="Only regenerate report from existing crawl"
    )
    parser.add_argument(
        "--crawl-dir", type=Path,
        help="Use specific crawl directory instead of latest"
    )

    args = parser.parse_args()

    start_url = "https://www.spectrum.com"
    output_dir = Path("crawls/www.spectrum.com")

    print("=" * 60)
    print("Spectrum.com SEO Analysis")
    print("=" * 60)
    print(f"Target: {start_url}")

    # Check API key
    if not os.getenv("GOOGLE_PSI_API_KEY"):
        print("\nWarning: GOOGLE_PSI_API_KEY not set.")
        print("PSI analysis may be limited or skipped.")
        print("Add to .env: GOOGLE_PSI_API_KEY=your_key_here\n")

    # Determine crawl directory
    if args.crawl_dir:
        crawl_dir = args.crawl_dir
    elif args.urls_only or args.psi_only or args.report_only:
        crawl_dir = get_latest_crawl(output_dir)
        if not crawl_dir:
            print(f"Error: No existing crawl found in {output_dir}")
            sys.exit(1)
        print(f"Using existing crawl: {crawl_dir}")
    else:
        crawl_dir = None

    # Execute requested operations
    if args.urls_only:
        list_urls(crawl_dir)
        return

    if args.psi_only:
        run_psi_backfill(crawl_dir)
        regenerate_report(crawl_dir)
        print(f"\nReport: {crawl_dir}/report.html")
        return

    if args.report_only:
        regenerate_report(crawl_dir)
        print(f"\nReport: {crawl_dir}/report.html")
        return

    # Full crawl
    crawl_dir = run_crawl(start_url, args.max_pages, output_dir)

    if not crawl_dir:
        print("Error: Crawl did not create output directory")
        sys.exit(1)

    print(f"\nCrawl complete: {crawl_dir}")

    # Backfill any missing PSI data
    run_psi_backfill(crawl_dir)

    # Regenerate report
    regenerate_report(crawl_dir)

    # Summary
    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)
    print(f"Report: {crawl_dir}/report.html")
    print(f"\nTo open: open {crawl_dir}/report.html")


if __name__ == "__main__":
    main()
