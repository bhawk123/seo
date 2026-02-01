#!/usr/bin/env python3
"""Regenerate HTML report from existing crawl data."""

import sys
from pathlib import Path
from seo.report_generator import ReportGenerator

def main():
    if len(sys.argv) < 2:
        print("Usage: python regenerate_report.py <crawl_directory>")
        print("\nExamples:")
        print("  python regenerate_report.py crawls/pinsandaces.com/2025-11-23_131015")
        print("  python regenerate_report.py crawls/pinsandaces.com/latest")
        sys.exit(1)

    crawl_dir = Path(sys.argv[1])

    if not crawl_dir.exists():
        print(f"Error: Directory not found: {crawl_dir}")
        sys.exit(1)

    # Check for required files
    required_files = ['metadata.json', 'technical_issues.json']
    missing_files = [f for f in required_files if not (crawl_dir / f).exists()]

    if missing_files:
        print(f"Error: Missing required files: {', '.join(missing_files)}")
        sys.exit(1)

    print(f"Regenerating report from: {crawl_dir}")

    # Generate report
    generator = ReportGenerator()
    output_path = crawl_dir / "report.html"

    generator.generate_report(crawl_dir, output_path)

    print(f"\n✅ Report regenerated: {output_path}")
    print(f"   Open in browser: open {output_path}")

if __name__ == "__main__":
    main()
