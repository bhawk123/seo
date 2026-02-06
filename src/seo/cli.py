"""Command-line interface for SEO analyzer."""

import asyncio
import sys
import json
from typing import Optional
from datetime import datetime

from seo.analyzer import SEOAnalyzer
from seo.async_site_crawler import AsyncSiteCrawler
from seo.config import settings
from seo.database import get_db_client
from seo.logging_config import setup_logging


async def _async_crawl(
    start_url: str,
    max_pages: int,
    rate_limit: float,
    max_concurrent: int,
    user_agent: Optional[str] = None,
):
    """Run async site crawl.

    Args:
        start_url: URL to start crawling from
        max_pages: Maximum pages to crawl
        rate_limit: Seconds between requests
        max_concurrent: Maximum concurrent requests
        user_agent: Optional user agent string

    Returns:
        Dictionary of URL to PageMetadata
    """
    crawler = AsyncSiteCrawler(
        max_pages=max_pages,
        rate_limit=rate_limit,
        max_concurrent=max_concurrent,
        user_agent=user_agent,
    )
    return await crawler.crawl_site(start_url)


def print_seo_score(url: str, score):
    """Print SEO score in a formatted way.

    Args:
        url: The analyzed URL
        score: SEOScore object
    """
    if score is None:
        print(f"\n❌ Failed to analyze {url}")
        return

    print(f"\n{'=' * 60}")
    print(f"SEO Analysis for: {url}")
    print(f"{'=' * 60}")
    print(f"\n📊 Overall Score: {score.overall_score}/100")
    print(f"\nDetailed Scores:")
    print(f"  • Title: {score.title_score}/100")
    print(f"  • Description: {score.description_score}/100")
    print(f"  • Content: {score.content_score}/100")
    print(f"  • Technical: {score.technical_score}/100")

    if score.strengths:
        print(f"\n✅ Strengths:")
        for strength in score.strengths:
            print(f"  • {strength}")

    if score.weaknesses:
        print(f"\n⚠️  Weaknesses:")
        for weakness in score.weaknesses:
            print(f"  • {weakness}")

    if score.recommendations:
        print(f"\n💡 Recommendations:")
        for rec in score.recommendations:
            print(f"  • {rec}")

    print(f"\n{'=' * 60}\n")


def analyze_command(args):
    """Analyze one or more URLs for SEO."""
    if not settings.GOOGLE_API_KEY: # Using settings directly
        print(
            "Error: LLM API key is required. Set LLM_API_KEY in .env file, environment variable, or use --api-key"
        )
        sys.exit(1)

    try:
        analyzer = SEOAnalyzer(
            llm_api_key=settings.GOOGLE_API_KEY, # Using settings directly
            llm_model=settings.LLM_MODEL, # Using settings directly
            llm_provider=settings.LLM_PROVIDER, # Using settings directly
            user_agent=settings.USER_AGENT, # Using settings directly
        )

        # Site crawl mode
        if args.site_crawl:
            if len(args.urls) > 1:
                print("Warning: Site crawl mode only uses the first URL")

            start_url = args.urls[0]

            # Use async crawler if --async flag is set
            if getattr(args, 'use_async', False):
                print(f"Using async crawler (max_concurrent={args.max_concurrent})...")
                site_data = asyncio.run(_async_crawl(
                    start_url=start_url,
                    max_pages=args.max_pages,
                    rate_limit=args.rate_limit,
                    max_concurrent=args.max_concurrent,
                    user_agent=settings.USER_AGENT,
                ))

                # Run analysis on async-crawled data
                from seo.technical import TechnicalAnalyzer
                technical_analyzer = TechnicalAnalyzer()
                technical_result = technical_analyzer.analyze(site_data)
                if isinstance(technical_result, tuple):
                    technical_issues, _ = technical_result
                else:
                    technical_issues = technical_result

                # Run advanced analysis
                advanced_analysis = analyzer._run_advanced_analysis(site_data)

                # Generate LLM recommendations
                from seo.site_crawler import SiteCrawler
                temp_crawler = SiteCrawler(max_pages=args.max_pages)
                temp_crawler.pages = site_data
                llm_recommendations = analyzer._generate_site_recommendations(
                    site_data, technical_issues, temp_crawler.get_crawl_summary(), advanced_analysis
                )
            else:
                # Use sync crawler (original behavior)
                result = analyzer.analyze_site(
                    start_url=start_url,
                    max_pages=args.max_pages,
                    rate_limit=args.rate_limit,
                )
                # Handle 5-tuple return value
                site_data, technical_issues, llm_recommendations, advanced_analysis, _ = result

            # Output site crawl results
            if args.output == "json":
                result = {
                    "start_url": start_url,
                    "total_pages": len(site_data),
                    "pages": {
                        url: {
                            "title": page.title,
                            "description": page.description,
                            "word_count": page.word_count,
                            "load_time": page.load_time,
                            "h1_tags": page.h1_tags,
                            "internal_links": page.internal_links,
                            "external_links": page.external_links,
                        }
                        for url, page in site_data.items()
                    },
                    "technical_issues": { # Updated to include new issues
                        "missing_titles": technical_issues.missing_titles,
                        "duplicate_titles": technical_issues.duplicate_titles,
                        "missing_meta_descriptions": technical_issues.missing_meta_descriptions,
                        "missing_h1": technical_issues.missing_h1,
                        "images_without_alt": [
                            {"url": url, "missing": count, "total": total}
                            for url, count, total in technical_issues.images_without_alt
                        ],
                        "slow_pages": [
                            {"url": url, "load_time": time}
                            for url, time in technical_issues.slow_pages
                        ],
                        "thin_content": [
                            {"url": url, "word_count": count}
                            for url, count in technical_issues.thin_content
                        ],
                        "broken_links": [
                            {"source": src, "broken": bl}
                            for src, bl in technical_issues.broken_links
                        ],
                        "orphan_pages": technical_issues.orphan_pages,
                    },
                    "recommendations": llm_recommendations,
                    "advanced_analysis": advanced_analysis, # Included advanced analysis
                }

                output = json.dumps(result, indent=2, default=str) # default=str to handle datetime objects
                if args.output_file:
                    with open(args.output_file, "w") as f:
                        f.write(output)
                    print(f"\nResults written to {args.output_file}")
                else:
                    print(output)

        # Single page mode
        else:
            results = []
            for url in args.urls:
                print(f"Analyzing {url}...")
                crawl_result, seo_score = analyzer.analyze_url(url)

                if args.output == "text":
                    print_seo_score(url, seo_score)
                else:
                    results.append(
                        {
                            "url": url,
                            "success": crawl_result.success,
                            "score": (
                                {
                                    "overall": seo_score.overall_score,
                                    "title": seo_score.title_score,
                                    "description": seo_score.description_score,
                                    "content": seo_score.content_score,
                                    "technical": seo_score.technical_score,
                                    "strengths": seo_score.strengths,
                                    "weaknesses": seo_score.weaknesses,
                                    "recommendations": seo_score.recommendations,
                                }
                                if seo_score
                                else None
                            ),
                            "error": crawl_result.error if not crawl_result.success else None,
                        }
                    )

            if args.output == "json":
                output = json.dumps(results, indent=2, default=str)
                if args.output_file:
                    with open(args.output_file, "w") as f:
                        f.write(output)
                    print(f"Results written to {args.output_file}")
                else:
                    print(output)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def report_command(args):
    """Generate a historical report for a domain."""
    db = get_db_client()
    snapshots = db.get_snapshots_for_domain(args.domain)
    db.close()

    if not snapshots:
        print(f"No historical data found for domain: {args.domain}")
        sys.exit(0)
    
    if args.output == "json":
        output = json.dumps(snapshots, indent=2, default=str)
        if args.output_file:
            with open(args.output_file, "w") as f:
                f.write(output)
            print(f"\nReport written to {args.output_file}")
        else:
            print(output)
    else: # text format
        print(f"\n{'=' * 60}")
        print(f"Historical SEO Report for: {args.domain}")
        print(f"{'=' * 60}\n")
        
        for snapshot in snapshots:
            print(f"Crawl Date: {snapshot['crawl_date']}")
            print(f"  Technical Score: {snapshot.get('technical_score', 'N/A')}")
            print(f"  Total Issues: {snapshot.get('total_issues', 'N/A')}")
            print(f"  Crawlable Pages: {snapshot.get('crawlable_pages', 'N/A')}")
            print(f"  Avg Load Time: {snapshot.get('avg_load_time', 'N/A'):.2f}s")
            # Add more fields as needed
            print("-" * 30)


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SEO Analyzer - Crawl and analyze websites for SEO quality using LLM"
    )

    # Global flags (before subcommands)
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        help="Write logs to file in addition to console",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Analyze command parser
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze one or more URLs for SEO."
    )
    analyze_parser.add_argument(
        "urls", nargs="+", help="URLs to analyze (one or more)"
    )
    analyze_parser.add_argument(
        "--output",
        "-o",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    analyze_parser.add_argument(
        "--output-file",
        "-f",
        help="Write output to file (only for json format)",
    )
    analyze_parser.add_argument(
        "--site-crawl",
        action="store_true",
        help="Enable site crawling mode (crawls entire site using BFS)",
    )
    analyze_parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Maximum pages to crawl in site mode (default: 50)",
    )
    analyze_parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.5,
        help="Seconds to wait between requests in site mode (default: 0.5)",
    )
    analyze_parser.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="Use high-performance async crawler (5-10x faster)",
    )
    analyze_parser.add_argument(
        "--max-concurrent",
        type=int,
        default=10,
        help="Maximum concurrent requests for async crawler (default: 10)",
    )
    analyze_parser.set_defaults(func=analyze_command)

    # Report command parser
    report_parser = subparsers.add_parser(
        "report", help="Generate a historical report for a domain."
    )
    report_parser.add_argument(
        "domain", help="The domain for which to generate the report (e.g., example.com)"
    )
    report_parser.add_argument(
        "--output",
        "-o",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    report_parser.add_argument(
        "--output-file",
        "-f",
        help="Write output to file (only for json format)",
    )
    report_parser.set_defaults(func=report_command)

    args = parser.parse_args()

    # Configure logging based on flags
    setup_logging(
        level=args.log_level,
        log_file=getattr(args, 'log_file', None),
    )

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
