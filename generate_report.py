"""Generate HTML report from crawl results."""

import sys
from pathlib import Path
from seo.report_generator import ReportGenerator
from seo.output_manager import OutputManager
from seo.database import MetricsDatabase # New import
from urllib.parse import urlparse # New import


def main():
    """Generate HTML report from crawl directory."""
    if len(sys.argv) < 2:
        print("Usage: python generate_report.py <domain> [timestamp]")
        print("\nExamples:")
        print("  python generate_report.py example.com")
        print("  python generate_report.py example.com 2025-11-23_143022")
        print("\nGenerate report from the latest or specific crawl.")
        sys.exit(1)

    domain = sys.argv[1]
    timestamp = sys.argv[2] if len(sys.argv) > 2 else None

    # Find crawl directory
    output_mgr = OutputManager()
    base_dir = output_mgr.base_output_dir / domain

    if not base_dir.exists():
        print(f"Error: No crawls found for domain '{domain}'")
        print(f"Expected directory: {base_dir}")
        sys.exit(1)

    # Use latest or specific timestamp
    if timestamp:
        crawl_dir = base_dir / timestamp
        if not crawl_dir.exists():
            print(f"Error: Crawl not found: {crawl_dir}")
            print("\nAvailable crawls:")
            for d in sorted(base_dir.iterdir()):
                if d.is_dir() and d.name != 'latest':
                    print(f"  {d.name}")
            sys.exit(1)
    else:
        # Find the latest crawl directory that is not a symlink
        crawls = sorted([d for d in base_dir.iterdir() if d.is_dir() and not d.is_symlink()], reverse=True)
        if not crawls:
            print(f"Error: No crawl directories found in {base_dir}")
            sys.exit(1)
        crawl_dir = crawls[0]

    print(f"Generating report from: {crawl_dir}")

    # --- Fetch historical data ---
    try:
        print("Fetching historical data for trend charts...")
        db = MetricsDatabase()
        # The domain argument might be a full URL, so parse it
        parsed_domain = urlparse(domain).netloc or domain
        historical_snapshots = db.get_snapshots_for_domain(parsed_domain)
        db.close()
        print(f"Found {len(historical_snapshots)} historical snapshots.")
    except Exception as e:
        print(f"\n⚠️  Warning: Could not fetch historical data: {e}")
        historical_snapshots = []
    # -----------------------------

    # Generate report
    report_gen = ReportGenerator()
    output_path = crawl_dir / "report.html"

    try:
        report_gen.generate_report(crawl_dir, output_path, historical_snapshots=historical_snapshots)
        print(f"\n✅ Report generated successfully!")
        print(f"   {output_path}")
        print(f"\nOpen in browser:")
        print(f"   open {output_path}")
    except Exception as e:
        print(f"\n❌ Error generating report: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
