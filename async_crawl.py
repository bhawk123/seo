"""Async site crawler script - High-performance crawling for large sites."""

import argparse
import asyncio
import signal
import sys
import time
import yaml
from pathlib import Path
from seo.async_site_crawler import AsyncSiteCrawler
from seo.config import Config
from seo.logging_config import setup_logging
from seo.output_manager import OutputManager
from seo.models import TechnicalIssues
import json

# Global reference to crawler for signal handling
_crawler = None
_crawl_dir = None
_output_manager = None


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Async SEO crawler with undetected chromium"
    )
    parser.add_argument("url", nargs="?", help="URL to crawl (not required when using --resume)")
    parser.add_argument(
        "--max-pages", type=int, default=50,
        help="Maximum number of pages to crawl (default: 50)"
    )
    parser.add_argument(
        "--max-depth", type=int, default=None,
        help="Maximum depth to crawl (default: unlimited)"
    )
    parser.add_argument(
        "--rate-limit", type=float, default=0.5,
        help="Delay between requests in seconds (default: 0.5)"
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run in headless mode (less stealthy)"
    )
    parser.add_argument(
        "--timeout", type=int, default=60,
        help="Page load timeout in seconds (default: 60)"
    )
    parser.add_argument(
        "--resume", type=str, metavar="PATH",
        help="Resume from existing crawl directory"
    )

    # PageSpeed Insights API options (for Lighthouse/CrUX data)
    parser.add_argument(
        "--enable-psi", action="store_true", default=True,
        help="Enable PageSpeed Insights API for Lighthouse/CrUX data (default: enabled)"
    )
    parser.add_argument(
        "--no-psi", action="store_true",
        help="Disable PageSpeed Insights API"
    )
    parser.add_argument(
        "--psi-strategy", choices=["mobile", "desktop"], default="mobile",
        help="PageSpeed Insights strategy: mobile or desktop (default: mobile)"
    )
    parser.add_argument(
        "--psi-sample", type=float, default=1.0,
        help="Fraction of pages to analyze with PSI (0.0-1.0, default: 1.0 = all pages)"
    )
    parser.add_argument(
        "--address-config", type=str, default="address.yaml",
        help="YAML file with address config (default: address.yaml)"
    )
    parser.add_argument(
        "--address-key", type=str, default="serviceable",
        help="Key in YAML to use for address (default: serviceable)"
    )
    parser.add_argument(
        "--max-concurrent", type=int, default=1,
        help="Maximum concurrent browser pages (default: 1 for stealth)"
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Disable LLM-powered recommendations"
    )
    parser.add_argument(
        "--ignore-robots", action="store_true",
        help="Ignore robots.txt restrictions (use with caution)"
    )
    parser.add_argument(
        "--no-open", action="store_true",
        help="Don't open report in browser after crawl (for headless environments)"
    )
    parser.add_argument(
        "--report-only", action="store_true",
        help="Skip crawling, just regenerate report from existing page data (use with --resume)"
    )
    return parser.parse_args()


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
        print(f"Resume with: python async_crawl.py --resume {_crawl_dir}")

    sys.exit(0)


def generate_llm_recommendations(
    site_data,
    technical_issues,
    crawl_stats,
    advanced_analysis,
    config,
):
    """Generate LLM-powered SEO recommendations.

    Args:
        site_data: Dictionary of URL to PageMetadata
        technical_issues: TechnicalIssues object
        crawl_stats: Crawl statistics dict
        advanced_analysis: Advanced analysis dict (already serialized to dicts)
        config: Config object with LLM settings

    Returns:
        LLM-generated recommendations string
    """
    from seo.llm import LLMClient

    if not config.llm_api_key:
        return "Error: LLM_API_KEY not set in .env file"

    try:
        llm = LLMClient(
            api_key=config.llm_api_key,
            model=config.llm_model,
            provider=config.llm_provider,
        )
    except Exception as e:
        return f"Error initializing LLM client: {e}"

    # Prepare issues summary
    issues_summary = {
        "missing_titles": len(technical_issues.missing_titles),
        "duplicate_titles": len(technical_issues.duplicate_titles),
        "missing_meta_descriptions": len(technical_issues.missing_meta_descriptions),
        "short_meta_descriptions": len(technical_issues.short_meta_descriptions),
        "long_meta_descriptions": len(technical_issues.long_meta_descriptions),
        "missing_h1": len(technical_issues.missing_h1),
        "multiple_h1": len(technical_issues.multiple_h1),
        "images_without_alt": len(technical_issues.images_without_alt),
        "slow_pages": len(technical_issues.slow_pages),
        "thin_content": len(technical_issues.thin_content),
        "missing_canonical": len(technical_issues.missing_canonical),
    }

    # Sample pages for context
    sample_pages = []
    for url, page in list(site_data.items())[:5]:
        sample_pages.append({
            "url": url,
            "title": page.title,
            "description": page.description,
            "h1_tags": page.h1_tags,
            "word_count": page.word_count,
            "load_time": page.load_time,
            "internal_links": page.internal_links,
            "external_links": page.external_links,
        })

    # Prepare advanced analysis summary (data is already dicts)
    advanced_summary = {}

    content_quality = advanced_analysis.get('content_quality', [])
    if content_quality:
        avg_readability = sum(c['readability_score'] for c in content_quality) / len(content_quality)
        advanced_summary['content_quality'] = {
            'avg_readability_score': round(avg_readability, 1),
            'pages_analyzed': len(content_quality),
        }

    security = advanced_analysis.get('security', [])
    if security:
        https_count = sum(1 for s in security if s.get('has_https'))
        avg_security_score = sum(s.get('security_score', 0) for s in security) / len(security)
        advanced_summary['security'] = {
            'https_pages': https_count,
            'total_pages': len(security),
            'avg_security_score': round(avg_security_score, 1),
        }

    url_structure = advanced_analysis.get('url_structure', [])
    if url_structure:
        total_issues = sum(len(u.get('issues', [])) for u in url_structure)
        pages_with_keywords = sum(1 for u in url_structure if u.get('has_keywords'))
        advanced_summary['url_structure'] = {
            'pages_with_keywords': pages_with_keywords,
            'total_pages': len(url_structure),
            'total_url_issues': total_issues,
        }

    mobile = advanced_analysis.get('mobile', [])
    if mobile:
        has_viewport = sum(1 for m in mobile if m.get('has_viewport', False))
        avg_mobile_score = sum(m.get('mobile_score', 0) for m in mobile) / len(mobile)
        advanced_summary['mobile'] = {
            'pages_with_viewport': has_viewport,
            'total_pages': len(mobile),
            'avg_mobile_score': round(avg_mobile_score, 1),
        }

    international = advanced_analysis.get('international', [])
    if international:
        has_lang = sum(1 for i in international if i.get('has_lang_attribute', False))
        has_hreflang = sum(1 for i in international if i.get('has_hreflang', False))
        advanced_summary['international'] = {
            'pages_with_lang': has_lang,
            'pages_with_hreflang': has_hreflang,
            'total_pages': len(international),
        }

    prompt = f"""
As an SEO expert, analyze this website and provide comprehensive SEO recommendations using the ICE framework for prioritization.

ICE Framework:
- Impact (1-10): How much will this improve SEO/traffic?
- Confidence (1-10): How confident are you this will work?
- Ease (1-10): How easy is this to implement?
- ICE Score = (Impact × Confidence × Ease) / 100

SITE CRAWL SUMMARY:
{json.dumps(crawl_stats, indent=2)}

TECHNICAL ISSUES SUMMARY:
{json.dumps(issues_summary, indent=2)}

ADVANCED ANALYSIS SUMMARY:
{json.dumps(advanced_summary, indent=2)}

SAMPLE PAGES (first 5):
{json.dumps(sample_pages, indent=2)}

Please provide:

1. **Critical Issues** (Priority 1 - Fix Immediately)
   - List the most critical SEO problems that need immediate attention
   - For each issue, provide ICE scores (Impact, Confidence, Ease)
   - Explain the impact of each issue
   - Calculate and show the ICE score for each recommendation

2. **Quick Wins** (Priority 2 - Easy fixes with high impact)
   - Identify easy-to-fix issues (Ease >= 7) that will have significant impact (Impact >= 7)
   - For each, provide ICE scores
   - Provide specific action items
   - Sort by ICE score (highest first)

3. **Content Optimization**
   - Recommendations for improving content quality and structure
   - Keyword and topic suggestions based on readability scores and keyword density analysis
   - Include ICE scores for each recommendation
   - Prioritize recommendations by ICE score

4. **Technical SEO Improvements**
   - Site architecture recommendations
   - Performance optimization tips
   - Internal linking strategies
   - Security improvements (HTTPS, headers)
   - Mobile optimization
   - International SEO considerations
   - For each recommendation, provide ICE scores

5. **Prioritized 30-Day Action Plan**
   - Week 1 priorities: Focus on highest ICE scores (8.0+)
   - Week 2 priorities: Next tier ICE scores (6.0-7.9)
   - Week 3 priorities: Medium ICE scores (4.0-5.9)
   - Week 4 priorities: Lower ICE scores (2.0-3.9)
   - For each task, show the ICE score and estimated effort

Format your response clearly with headers, bullet points, and ICE scores in brackets [I:X C:X E:X = ICE:X.X] for easy prioritization.

Example format:
- [I:9 C:8 E:7 = ICE:5.04] Fix missing meta descriptions on 15 pages
  Impact: Improves CTR from search results
  Action: Write unique descriptions for each page
  Estimated effort: 2-3 hours

IMPORTANT: Do NOT include any closing questions, offers for further assistance, or phrases like "Would you like me to..." at the end of your response. End with the actionable recommendations only.
"""

    try:
        print("Generating LLM recommendations...")
        response = llm._call_llm(prompt)
        return response
    except Exception as e:
        return f"Failed to generate LLM recommendations: {e}"


async def main():
    """Run async site crawl."""
    global _crawler, _crawl_dir, _output_manager

    args = parse_args()

    # Load configuration and setup logging
    config = Config.from_env()
    setup_logging(level=config.log_level)

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
            # Check if we have page data saved - if so, offer to regenerate report
            pages_dir = crawl_dir / "pages"
            page_files = list(pages_dir.glob("*.json")) if pages_dir.exists() else []
            if page_files:
                print(f"Crawl already completed with {len(page_files)} pages saved.")
                print(f"Regenerating report from saved data...")
                # Continue to load data and regenerate report
            else:
                print(f"Crawl marked as completed but no page data found.")
                print(f"Start a new crawl instead.")
                sys.exit(0)

        start_url = resume_state["config"]["start_url"]
        pages_already_crawled = resume_state["progress"]["pages_crawled"]

        # Use stored config values unless overridden by command line
        stored_config = resume_state.get("config", {})
        if stored_config.get("max_pages") and args.max_pages == 50:  # 50 is default
            args.max_pages = stored_config["max_pages"]
        if stored_config.get("max_depth") and args.max_depth is None:
            args.max_depth = stored_config["max_depth"]
        if stored_config.get("rate_limit") and args.rate_limit == 0.5:  # 0.5 is default
            args.rate_limit = stored_config["rate_limit"]

        print("Resuming crawl...")
        print(f"  Start URL: {start_url}")
        print(f"  Pages already crawled: {pages_already_crawled}")
        print(f"  Target max pages: {args.max_pages}")
        if args.max_depth:
            print(f"  Max depth: {args.max_depth}")
        print()
    else:
        # Require URL for new crawl
        if not args.url:
            print("Error: URL is required (or use --resume to continue a previous crawl)")
            sys.exit(1)

        # Ensure URL has scheme
        start_url = args.url
        if not start_url.startswith("http"):
            start_url = f"https://{start_url}"

        # Create new crawl directory
        crawl_dir = output_mgr.create_crawl_directory(start_url)

    _crawl_dir = crawl_dir

    # Determine PSI settings
    enable_psi = args.enable_psi and not args.no_psi
    psi_api_key = None
    if enable_psi:
        psi_api_key = config.google_psi_api_key
        if not psi_api_key:
            print("⚠️  PageSpeed Insights disabled: GOOGLE_PSI_API_KEY not found in .env")
            print("   Get an API key at: https://console.cloud.google.com/")
            print("   Add to .env: GOOGLE_PSI_API_KEY=your_key_here\n")
            enable_psi = False

    # Load address config if available
    address_config = None
    address_file = Path(args.address_config)
    if address_file.exists():
        with open(address_file) as f:
            addr_data = yaml.safe_load(f)
            if addr_data and args.address_key in addr_data:
                entries = addr_data[args.address_key]
                if entries and len(entries) > 0:
                    address_config = entries[0]  # Use first entry

    # Initialize async crawler
    print("Initializing Async SEO Crawler...")
    print(f"Max pages: {args.max_pages}")
    print(f"Max depth: {args.max_depth or 'unlimited'}")
    print(f"Max concurrent: {args.max_concurrent}")
    print(f"Rate limit: {args.rate_limit}s")
    if enable_psi:
        print(f"PageSpeed Insights: ENABLED ({args.psi_strategy}, {args.psi_sample*100:.0f}% sample)")
    else:
        print(f"PageSpeed Insights: DISABLED")
    if address_config:
        print(f"Address: {address_config.get('address')}, {address_config.get('city', '')}, {address_config.get('zip')}")
    if args.ignore_robots:
        print(f"Robots.txt: IGNORED")
    print()

    crawler = AsyncSiteCrawler(
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        rate_limit=args.rate_limit,
        user_agent=None,  # Use default Chrome UA
        max_concurrent=args.max_concurrent,
        timeout=args.timeout,
        headless=args.headless,
        resume_state=resume_state,
        output_manager=output_mgr,
        crawl_dir=crawl_dir,
        enable_psi=enable_psi,
        psi_api_key=psi_api_key,
        psi_strategy=args.psi_strategy,
        psi_sample_rate=args.psi_sample,
        address_config=address_config,
        ignore_robots=args.ignore_robots,
    )
    _crawler = crawler

    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)

    if not args.headless:
        print("Running in visible browser mode (use --headless for headless)")

    # Handle --report-only: skip crawling, just use existing data
    if args.report_only:
        if not args.resume:
            print("Error: --report-only requires --resume to specify crawl directory")
            sys.exit(1)
        print(f"\n📊 Report-only mode: Loading saved page data...")
        site_data = crawler.site_data  # Already loaded in __init__
        if not site_data:
            print("Error: No page data found. Run a crawl first.")
            sys.exit(1)
        print(f"Loaded {len(site_data)} pages from disk.")
        elapsed = 0
    else:
        # Crawl the site
        print(f"Starting async crawl of {start_url}...\n")
        start_time = time.time()

        site_data = await crawler.crawl_site(start_url)

        elapsed = time.time() - start_time

    crawl_stats = {
        "total_pages": len(site_data),
        "total_words": sum(p.word_count for p in site_data.values()) if site_data else 0,
        "total_images": sum(p.total_images for p in site_data.values()) if site_data else 0,
        "avg_words_per_page": sum(p.word_count for p in site_data.values()) // len(site_data) if site_data else 0,
        "total_time": elapsed,
        "avg_time_per_page": elapsed / len(site_data) if site_data else 0,
    }

    # Run advanced analysis
    print("\n" + "=" * 60)
    print("Running Advanced Analysis...")
    print("=" * 60)

    from dataclasses import asdict
    from seo.technical import TechnicalAnalyzer
    from seo.content_quality import ContentQualityAnalyzer
    from seo.advanced_analyzer import (
        SecurityAnalyzer,
        URLStructureAnalyzer,
        MobileSEOAnalyzer,
        InternationalSEOAnalyzer,
        TechnologyAnalyzer,
    )

    # Technical analysis
    technical_analyzer = TechnicalAnalyzer()
    technical_issues = technical_analyzer.analyze(site_data)

    # Advanced analyzers
    content_analyzer = ContentQualityAnalyzer()
    security_analyzer = SecurityAnalyzer()
    url_analyzer = URLStructureAnalyzer()
    mobile_analyzer = MobileSEOAnalyzer()
    international_analyzer = InternationalSEOAnalyzer()
    technology_analyzer = TechnologyAnalyzer()

    advanced_analysis = {
        'content_quality': [],
        'security': [],
        'url_structure': [],
        'mobile': [],
        'international': [],
    }

    for url, page in site_data.items():
        # Content quality
        if page.content_text:
            content_metrics = content_analyzer.analyze(url, page.content_text)
            advanced_analysis['content_quality'].append(asdict(content_metrics))

        # Security
        security_result = security_analyzer.analyze(url, page, page.security_headers)
        advanced_analysis['security'].append(asdict(security_result))

        # URL structure
        url_result = url_analyzer.analyze(url)
        advanced_analysis['url_structure'].append(asdict(url_result))

        # Mobile
        mobile_result = mobile_analyzer.analyze(page)
        advanced_analysis['mobile'].append(mobile_result)

        # International
        intl_result = international_analyzer.analyze(page)
        advanced_analysis['international'].append(intl_result)

    # Technology analysis (site-wide)
    advanced_analysis['technology'] = technology_analyzer.analyze_site_technologies(site_data)

    # Build metadata_list for report generation
    metadata_list = []
    for url, page in site_data.items():
        page_dict = asdict(page)
        # Convert datetime to ISO string
        if page_dict.get("crawled_at"):
            page_dict["crawled_at"] = page_dict["crawled_at"].isoformat()
        # Remove large content_text
        if "content_text" in page_dict:
            page_dict["content_text_length"] = len(page_dict.get("content_text", ""))
            del page_dict["content_text"]
        metadata_list.append(page_dict)

    advanced_analysis["metadata_list"] = metadata_list

    print("Advanced analysis complete.")

    # Generate LLM recommendations (enabled by default)
    if not args.no_llm and config.llm_api_key:
        print("\n" + "=" * 60)
        print("Generating LLM Recommendations...")
        print("=" * 60)
        llm_recommendations = generate_llm_recommendations(
            site_data=site_data,
            technical_issues=technical_issues,
            crawl_stats=crawl_stats,
            advanced_analysis=advanced_analysis,
            config=config,
        )
        print("LLM recommendations generated.")
    elif args.no_llm:
        llm_recommendations = "LLM recommendations disabled (--no-llm flag)."
    else:
        llm_recommendations = "Note: Set LLM_API_KEY in .env to enable AI-powered recommendations."

    # Save crawl results with advanced_analysis for reports
    output_mgr.save_crawl_results(
        crawl_dir=crawl_dir,
        start_url=start_url,
        site_data=site_data,
        technical_issues=technical_issues,
        llm_recommendations=llm_recommendations,
        crawl_stats=crawl_stats,
        advanced_analysis=advanced_analysis,
    )

    # Save individual Lighthouse reports
    psi_results = crawler.get_psi_results()
    if psi_results:
        output_mgr.save_lighthouse_reports(crawl_dir, psi_results)
        print(f"✅ Saved {len(psi_results)} Lighthouse reports to {crawl_dir}/lighthouse/")

    # Generate HTML report
    print("\n" + "=" * 60)
    print("Generating HTML Report...")
    print("=" * 60)
    from seo.report_generator import ReportGenerator
    report_gen = ReportGenerator()
    report_path = crawl_dir / "report.html"
    try:
        report_gen.generate_report(crawl_dir, report_path)
        print(f"✅ HTML Report: {report_path}")
    except Exception as e:
        print(f"⚠️ Failed to generate report: {e}")

    print(f"\n✅ Results saved to: {crawl_dir}")
    print(f"   View files: ls {crawl_dir}\n")

    # Print summary
    print("\n" + "=" * 60)
    print("CRAWL SUMMARY")
    print("=" * 60)
    print(f"Total pages crawled: {len(site_data)}")
    print(f"Total time: {elapsed:.2f} seconds")
    print(f"Average time per page: {elapsed/len(site_data):.2f}s" if site_data else "N/A")

    if site_data:
        total_words = sum(page.word_count for page in site_data.values())
        avg_words = total_words // len(site_data)
        total_images = sum(page.total_images for page in site_data.values())
        avg_load_time = sum(page.load_time for page in site_data.values()) / len(site_data)

        print(f"Total words: {total_words:,}")
        print(f"Average words per page: {avg_words:,}")
        print(f"Total images: {total_images}")
        print(f"Average page load time: {avg_load_time:.2f}s")

        # Count pages with issues
        missing_titles = sum(1 for page in site_data.values() if not page.title)
        missing_desc = sum(1 for page in site_data.values() if not page.description)
        missing_h1 = sum(1 for page in site_data.values() if not page.h1_tags)
        thin_content = sum(1 for page in site_data.values() if page.word_count < 300)
        no_https = sum(1 for page in site_data.values() if not page.has_https)

        print("\n" + "=" * 60)
        print("QUICK ISSUES SUMMARY")
        print("=" * 60)
        print(f"Missing titles: {missing_titles}")
        print(f"Missing meta descriptions: {missing_desc}")
        print(f"Missing H1 tags: {missing_h1}")
        print(f"Thin content (<300 words): {thin_content}")
        print(f"Non-HTTPS pages: {no_https}")

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
            issues.append("no desc")
        if not page.h1_tags:
            issues.append("no H1")
        if page.word_count < 300:
            issues.append(f"{page.word_count}w")
        if not page.has_https:
            issues.append("HTTP")
        if not page.viewport_meta:
            issues.append("no viewport")

        issue_str = f" [{', '.join(issues)}]" if issues else ""
        print(f"{i:3d}. {status} {url}{issue_str}")

    print("\n" + "=" * 60)
    print(f"⚡ Async crawl complete in {elapsed:.2f}s!")
    print("=" * 60)

    # Open report in browser (unless --no-open or headless server)
    if not args.no_open:
        import subprocess
        report_file = crawl_dir / "report.html"
        if report_file.exists():
            print(f"\n📊 Opening report in browser...")
            subprocess.run(["open", str(report_file)], check=False)


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())
