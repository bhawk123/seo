"""Site crawler script - Crawl and analyze entire websites for SEO."""

import sys
import signal
import argparse
from pathlib import Path

# Global reference for signal handling
_crawler = None
_crawl_dir = None
_output_manager = None


def handle_interrupt(signum, frame):
    """Handle Ctrl+C gracefully by saving state."""
    global _crawler, _crawl_dir, _output_manager
    print("\n\n⚠️  Crawl interrupted by user.")

    if _crawler and _output_manager and _crawl_dir:
        print("Saving crawl state...")
        state = _crawler.get_state(status="paused")
        _output_manager.save_crawl_state(_crawl_dir, state)
        pages_crawled = len(_crawler.visited_urls)
        print(f"Crawl paused at {pages_crawled}/{_crawler.max_pages} pages.")
        print(f"Resume with: python crawl.py --resume {_crawl_dir}")

    sys.exit(0)


signal.signal(signal.SIGINT, handle_interrupt)
signal.signal(signal.SIGTERM, handle_interrupt)
from datetime import datetime
from seo import SEOAnalyzer
from seo.config import Config
from seo.output_manager import OutputManager


def main():
    """Run site crawl and analysis."""
    global _crawler, _crawl_dir, _output_manager

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Crawl and analyze websites for SEO')
    parser.add_argument('url', nargs='?', help='URL to crawl (not required when using --resume)')
    parser.add_argument('max_pages', nargs='?', type=int, default=50,
                       help='Maximum number of pages to crawl (default: 50)')
    parser.add_argument('rate_limit', nargs='?', type=float, default=0.5,
                       help='Rate limit in seconds between requests (default: 0.5)')

    # Local Lighthouse CLI options
    parser.add_argument('--no-lighthouse', action='store_true',
                       help='Disable local Lighthouse performance audits (enabled by default)')
    parser.add_argument('--lighthouse-sample', type=float, default=0.1,
                       help='Fraction of pages to audit with Lighthouse (0.0-1.0, default: 0.1 = 10%%)')

    # Google PageSpeed Insights API options
    parser.add_argument('--enable-psi', action='store_true',
                       help='Enable Google PageSpeed Insights API for CrUX real user data (requires GOOGLE_PSI_API_KEY)')
    parser.add_argument('--psi-strategy', choices=['mobile', 'desktop'], default='mobile',
                       help='PageSpeed Insights strategy: mobile or desktop (default: mobile)')

    # Stealth mode options
    parser.add_argument('--stealth', action='store_true',
                       help='Use browser-like headers to bypass bot detection (use for sites that block crawlers)')

    # Browser-based rendering options
    parser.add_argument('--render-js', action='store_true',
                       help='Enable JavaScript rendering using a headless browser (requires: poetry install -E browser)')
    parser.add_argument('--browser-type', choices=['chromium', 'firefox', 'webkit'], default='chromium',
                       help='Browser engine to use with --render-js (default: chromium)')

    # Sitemap seeding options
    parser.add_argument('--sitemap', type=str, default=None,
                       help='URL or local file path to sitemap.xml to seed the crawl queue (useful for bot-protected sites)')
    parser.add_argument('--sitemap-file', type=str, default=None,
                       help='Local file path to sitemap.xml (alternative to --sitemap for manually downloaded sitemaps)')

    # Resume option
    parser.add_argument('--resume', type=str, metavar='PATH',
                       help='Resume from existing crawl directory')

    args = parser.parse_args()

    max_pages = args.max_pages
    rate_limit = args.rate_limit

    # Initialize output manager
    output_mgr = OutputManager()
    _output_manager = output_mgr

    resume_state = None
    crawl_dir = None

    # Handle resume mode
    if args.resume:
        crawl_dir = Path(args.resume)
        if not crawl_dir.exists():
            print(f"Error: Crawl directory not found: {crawl_dir}")
            sys.exit(1)

        resume_state = output_mgr.load_crawl_state(crawl_dir)
        if not resume_state:
            print(f"Error: No resumable state found in {crawl_dir}")
            sys.exit(1)

        if resume_state.get("status") == "completed":
            print(f"Crawl already completed. Start a new crawl instead.")
            sys.exit(0)

        start_url = resume_state["config"]["start_url"]
        pages_already_crawled = resume_state["progress"]["pages_crawled"]

        print("Resuming crawl...")
        print(f"  Start URL: {start_url}")
        print(f"  Pages already crawled: {pages_already_crawled}")
        print(f"  Target max pages: {max_pages}")
        print()
    else:
        # Require URL for new crawl
        if not args.url:
            print("Error: URL is required (or use --resume to continue a previous crawl)")
            sys.exit(1)
        start_url = args.url

    _crawl_dir = crawl_dir

    # Load configuration from .env
    config = Config.from_env()

    if not config.llm_api_key:
        print("Error: LLM_API_KEY not found in .env file")
        print("Please create a .env file with your API key:")
        print("  cp .env.example .env")
        print("  # Edit .env and add your LLM_API_KEY")
        sys.exit(1)

    # Check for PageSpeed Insights API key if --enable-psi is used
    if args.enable_psi and not config.google_psi_api_key:
        print("Error: --enable-psi requires GOOGLE_PSI_API_KEY in .env file")
        print("Get your API key at: https://console.cloud.google.com/")
        print("Then add it to .env: GOOGLE_PSI_API_KEY=your_key_here")
        sys.exit(1)

    # Check for browser dependencies if --render-js is used
    if args.render_js:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("Error: --render-js requires Playwright to be installed")
            print("Install browser dependencies with: poetry install -E browser")
            print("Then run: playwright install chromium")
            sys.exit(1)

    # Determine Lighthouse settings
    enable_lighthouse = not args.no_lighthouse
    lighthouse_sample_rate = args.lighthouse_sample if enable_lighthouse else 0.0

    # Initialize analyzer
    print("Initializing SEO Analyzer...")
    print(f"Provider: {config.llm_provider}")
    print(f"Model: {config.llm_model}")
    if enable_lighthouse:
        print(f"Local Lighthouse: ENABLED ({lighthouse_sample_rate * 100:.0f}% sample rate)")
    else:
        print(f"Local Lighthouse: DISABLED")
    if args.enable_psi:
        print(f"PageSpeed Insights API: ENABLED ({args.psi_strategy})")
    if args.stealth:
        print(f"Stealth Mode: ENABLED (using browser-like headers)")
    if args.render_js:
        print(f"JavaScript Rendering: ENABLED (browser: {args.browser_type})")

    # Parse sitemap if provided
    seed_urls = []
    sitemap_source = args.sitemap_file or args.sitemap
    if sitemap_source:
        print(f"Sitemap: {sitemap_source}")
        print("Parsing sitemap for URL seeding...")

        # Check if it's a local file
        import os
        if os.path.isfile(sitemap_source):
            # Parse local sitemap file
            from seo.sitemap_parser import SitemapParser
            try:
                with open(sitemap_source, 'r') as f:
                    sitemap_content = f.read()
                parser = SitemapParser()
                parser._parse_sitemap_content(sitemap_content, start_url, max_pages * 2)
                seed_urls = list(parser._urls)[:max_pages * 2]
                print(f"  Found {len(seed_urls)} URLs in local sitemap")
            except Exception as e:
                print(f"  ⚠️ Failed to parse local sitemap: {e}")
                print("  Continuing without sitemap seeding...")
        else:
            # Parse remote sitemap URL
            from seo.sitemap_parser import parse_sitemap
            try:
                seed_urls = parse_sitemap(
                    sitemap_source,
                    max_urls=max_pages * 2,  # Get more URLs than needed to allow filtering
                    use_browser=args.render_js,  # Use browser if JS rendering is enabled
                    browser_type=args.browser_type,
                )
                print(f"  Found {len(seed_urls)} URLs in sitemap")
            except Exception as e:
                print(f"  ⚠️ Failed to parse sitemap: {e}")
                print("  Continuing without sitemap seeding...")

    print()

    analyzer = SEOAnalyzer(
        llm_api_key=config.llm_api_key,
        llm_model=config.llm_model,
        llm_provider=config.llm_provider
    )

    # Create crawl directory if not resuming
    if not crawl_dir:
        crawl_dir = output_mgr.create_crawl_directory(start_url)
    _crawl_dir = crawl_dir

    # Crawl the site
    print(f"Starting site crawl...")
    print(f"URL: {start_url}")
    print(f"Max pages: {max_pages}")
    print(f"Rate limit: {rate_limit}s between requests\n")

    site_data, technical_issues, llm_recommendations, advanced_analysis, site_crawler = analyzer.analyze_site(
        start_url=start_url,
        max_pages=max_pages,
        rate_limit=rate_limit,
        enable_lighthouse=enable_lighthouse,
        lighthouse_sample_rate=lighthouse_sample_rate,
        enable_psi=args.enable_psi,
        psi_api_key=config.google_psi_api_key if args.enable_psi else None,
        psi_strategy=args.psi_strategy,
        stealth_mode=args.stealth,
        render_js=args.render_js,
        browser_type=args.browser_type,
        seed_urls=seed_urls if seed_urls else None,
        resume_state=resume_state,
        output_manager=output_mgr,
        crawl_dir=crawl_dir,
    )

    # Store crawler reference for signal handling
    _crawler = site_crawler

    # Save results to crawl directory
    crawl_stats = {
        "total_pages": len(site_data),
        "total_words": sum(p.word_count for p in site_data.values()),
        "total_images": sum(p.total_images for p in site_data.values()),
        "avg_words_per_page": sum(p.word_count for p in site_data.values()) // len(site_data) if site_data else 0,
    }

    output_mgr.save_crawl_results(
        crawl_dir=crawl_dir,
        start_url=start_url,
        site_data=site_data,
        technical_issues=technical_issues,
        llm_recommendations=llm_recommendations,
        crawl_stats=crawl_stats,
        advanced_analysis=advanced_analysis,
    )

    # Generate HTML report
    print("\n" + "=" * 60)
    print("Generating HTML Report...")
    print("=" * 60 + "\n")

    from seo.report_generator import ReportGenerator
    report_gen = ReportGenerator()
    report_path = crawl_dir / "report.html"

    try:
        report_gen.generate_report(crawl_dir, report_path)
        print(f"✅ HTML Report generated: {report_path}")
        print(f"   Open in browser: open {report_path}\n")
    except Exception as e:
        print(f"⚠️  Failed to generate HTML report: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n✅ Results saved to: {crawl_dir}")
    print(f"   View files: ls {crawl_dir}\n")

    # Print summary
    print("\n" + "=" * 60)
    print("CRAWL SUMMARY")
    print("=" * 60)
    print(f"Total pages crawled: {len(site_data)}")

    if site_data:
        total_words = sum(page.word_count for page in site_data.values())
        avg_words = total_words // len(site_data)
        total_images = sum(page.total_images for page in site_data.values())

        print(f"Total words: {total_words:,}")
        print(f"Average words per page: {avg_words:,}")
        print(f"Total images: {total_images}")

    print("\n" + "=" * 60)
    print("TECHNICAL ISSUES SUMMARY")
    print("=" * 60)
    print(f"Missing titles: {len(technical_issues.missing_titles)}")
    print(f"Duplicate titles: {len(technical_issues.duplicate_titles)}")
    print(f"Missing meta descriptions: {len(technical_issues.missing_meta_descriptions)}")
    print(f"Missing H1 tags: {len(technical_issues.missing_h1)}")
    print(f"Images without alt text: {len(technical_issues.images_without_alt)}")
    print(f"Slow pages (>3s): {len(technical_issues.slow_pages)}")
    print(f"Thin content (<300 words): {len(technical_issues.thin_content)}")
    print(f"Missing canonical URLs: {len(technical_issues.missing_canonical)}")

    print("\n" + "=" * 60)
    print("AI-POWERED RECOMMENDATIONS")
    print("=" * 60)
    print(llm_recommendations)

    # List all crawled URLs
    print("\n" + "=" * 60)
    print("CRAWLED PAGES")
    print("=" * 60)
    for i, (url, page) in enumerate(site_data.items(), 1):
        status = "✓"
        issues = []

        if not page.title:
            issues.append("no title")
        if not page.description:
            issues.append("no description")
        if not page.h1_tags:
            issues.append("no H1")
        if page.word_count < 300:
            issues.append(f"{page.word_count}w")

        issue_str = f" [{', '.join(issues)}]" if issues else ""
        print(f"{i:3d}. {status} {url}{issue_str}")

    print("\n" + "=" * 60)
    print("Crawl complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
