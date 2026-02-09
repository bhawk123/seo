#!/usr/bin/env python3
"""Regenerate LLM recommendations for an existing crawl report.

This script allows re-running LLM analysis on existing crawl data without
re-crawling the site. Useful when:
- Initial LLM call failed due to API issues
- You want to try a different model or prompt
- You want to refresh recommendations with updated LLM capabilities

Usage:
    python -m seo.regenerate_recommendations /path/to/crawl_dir [options]

Options:
    --output-path PATH    Path for regenerated report (default: overwrite existing)
    --model MODEL         LLM model to use (default: from env or gpt-4)
    --provider PROVIDER   LLM provider: openai, anthropic (default: openai)
    --api-key KEY         API key (or use environment variable)
    --dry-run             Show what would be generated without calling LLM

Examples:
    # Regenerate with default settings
    python -m seo.regenerate_recommendations ./output/crawls/example_com_2024-01-15

    # Use a different model
    python -m seo.regenerate_recommendations ./output/crawls/example_com_2024-01-15 --model gpt-4-turbo

    # Use Anthropic instead
    python -m seo.regenerate_recommendations ./output/crawls/example_com_2024-01-15 --provider anthropic --model claude-3-opus-20240229

CONCURRENCY CONSIDERATIONS
==========================
Current implementation is single-threaded and processes one crawl directory at a time.

For large-scale operations (multiple crawl directories or batch processing):

1. PARALLEL DIRECTORY PROCESSING:
   Use multiprocessing or asyncio to process multiple crawl directories:
   ```python
   from concurrent.futures import ProcessPoolExecutor
   with ProcessPoolExecutor(max_workers=4) as executor:
       futures = [executor.submit(regenerate_recommendations, dir) for dir in crawl_dirs]
   ```

2. RATE LIMITING:
   When processing multiple directories, respect LLM API rate limits:
   - OpenAI: ~10,000 tokens/min for gpt-4, ~90,000 for gpt-4-turbo
   - Anthropic: Varies by tier
   Consider adding --rate-limit flag or using a shared semaphore.

3. BATCH OPERATIONS:
   For enterprise use, consider:
   - A job queue (Redis, RabbitMQ) for distributed processing
   - Progress tracking in a database
   - Resumable operations with checkpointing

4. RESOURCE USAGE:
   LLM calls are I/O-bound (network), so:
   - Asyncio is more efficient than threading
   - ProcessPoolExecutor is useful if doing heavy JSON parsing
   - Monitor memory for very large crawl datasets

Future enhancements may add:
- --parallel N flag for concurrent directory processing
- --batch flag for processing all subdirectories
- Progress bar with estimated completion time
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from seo.analyzer import SEOAnalyzer
from seo.models import TechnicalIssues, PageMetadata, EvidenceRecord, EvidenceCollection, ConfidenceLevel, EvidenceSourceType
from seo.report_generator import ReportGenerator


def load_crawl_data(crawl_dir: Path) -> tuple[dict, dict, dict, list]:
    """Load existing crawl data from directory.

    Args:
        crawl_dir: Path to crawl directory

    Returns:
        Tuple of (metadata, technical_issues, advanced_analysis, site_data_list)
    """
    metadata_path = crawl_dir / "metadata.json"
    technical_issues_path = crawl_dir / "technical_issues.json"
    advanced_analysis_path = crawl_dir / "advanced_analysis.json"

    if not metadata_path.exists():
        raise FileNotFoundError(f"Crawl metadata not found: {metadata_path}")

    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    technical_issues = {}
    if technical_issues_path.exists():
        with open(technical_issues_path, 'r', encoding='utf-8') as f:
            technical_issues = json.load(f)

    advanced_analysis = {}
    if advanced_analysis_path.exists():
        with open(advanced_analysis_path, 'r', encoding='utf-8') as f:
            advanced_analysis = json.load(f)

    # Extract site_data from advanced_analysis if available
    site_data_list = advanced_analysis.get('metadata_list', [])

    return metadata, technical_issues, advanced_analysis, site_data_list


def reconstruct_site_data(site_data_list: list) -> dict:
    """Reconstruct site_data dict from metadata list.

    Args:
        site_data_list: List of page metadata dicts

    Returns:
        Dictionary mapping URL to PageMetadata
    """
    site_data = {}
    for page_dict in site_data_list:
        url = page_dict.get('url', '')
        if url:
            page = PageMetadata(url=url)
            for key, value in page_dict.items():
                if hasattr(page, key):
                    setattr(page, key, value)
            site_data[url] = page
    return site_data


def reconstruct_technical_issues(issues_dict: dict) -> TechnicalIssues:
    """Reconstruct TechnicalIssues from dict.

    Args:
        issues_dict: Technical issues dictionary

    Returns:
        TechnicalIssues object
    """
    issues = TechnicalIssues()

    # Map dict keys to TechnicalIssues attributes
    simple_list_fields = [
        'missing_titles', 'missing_meta_descriptions', 'missing_h1',
        'missing_canonical', 'orphan_pages'
    ]

    for field in simple_list_fields:
        if field in issues_dict:
            setattr(issues, field, issues_dict[field])

    # Handle complex fields
    if 'duplicate_titles' in issues_dict:
        issues.duplicate_titles = issues_dict['duplicate_titles']

    if 'short_meta_descriptions' in issues_dict:
        issues.short_meta_descriptions = issues_dict['short_meta_descriptions']

    if 'long_meta_descriptions' in issues_dict:
        issues.long_meta_descriptions = issues_dict['long_meta_descriptions']

    if 'multiple_h1' in issues_dict:
        issues.multiple_h1 = issues_dict['multiple_h1']

    if 'images_without_alt' in issues_dict:
        issues.images_without_alt = issues_dict['images_without_alt']

    if 'slow_pages' in issues_dict:
        issues.slow_pages = issues_dict['slow_pages']

    if 'thin_content' in issues_dict:
        issues.thin_content = issues_dict['thin_content']

    if 'broken_links' in issues_dict:
        issues.broken_links = issues_dict['broken_links']

    return issues


def regenerate_recommendations(
    crawl_dir: Path,
    api_key: Optional[str] = None,
    model: str = "gpt-4",
    provider: str = "openai",
    dry_run: bool = False,
) -> dict:
    """Regenerate LLM recommendations for existing crawl.

    Args:
        crawl_dir: Path to crawl directory
        api_key: LLM API key (or from env)
        model: LLM model to use
        provider: LLM provider (openai, anthropic)
        dry_run: If True, don't actually call LLM

    Returns:
        Dictionary with new recommendations and evidence
    """
    print(f"\nLoading crawl data from: {crawl_dir}")

    # Load existing data
    metadata, technical_issues_dict, advanced_analysis, site_data_list = load_crawl_data(crawl_dir)

    print(f"  - Start URL: {metadata.get('start_url', 'unknown')}")
    print(f"  - Total pages: {metadata.get('total_pages', 0)}")
    print(f"  - Crawled at: {metadata.get('crawled_at', 'unknown')}")

    # Reconstruct objects
    site_data = reconstruct_site_data(site_data_list)
    technical_issues = reconstruct_technical_issues(technical_issues_dict)

    if dry_run:
        print("\n[DRY RUN] Would regenerate recommendations with:")
        print(f"  - Provider: {provider}")
        print(f"  - Model: {model}")
        print(f"  - Pages: {len(site_data)}")
        print(f"  - Technical issues: {sum(len(v) if isinstance(v, (list, dict)) else 0 for v in technical_issues_dict.values())}")
        return {'dry_run': True, 'would_regenerate': True}

    # Initialize analyzer with LLM
    print(f"\nInitializing LLM ({provider}/{model})...")
    analyzer = SEOAnalyzer(
        llm_api_key=api_key,
        llm_model=model,
        llm_provider=provider,
    )

    # Build crawl summary
    crawl_summary = {
        'total_pages': len(site_data),
        'start_url': metadata.get('start_url', ''),
        'crawled_at': metadata.get('crawled_at', ''),
    }

    # Regenerate recommendations
    print("\nGenerating new LLM recommendations...")
    result = analyzer._generate_site_recommendations(
        site_data=site_data,
        technical_issues=technical_issues,
        crawl_summary=crawl_summary,
        advanced_analysis=advanced_analysis,
    )

    # Add regeneration metadata
    result['regenerated_at'] = datetime.now().isoformat()
    result['regeneration_model'] = model
    result['regeneration_provider'] = provider

    return result


def save_recommendations(crawl_dir: Path, result: dict) -> None:
    """Save regenerated recommendations to crawl directory.

    Args:
        crawl_dir: Path to crawl directory
        result: Regeneration result dict
    """
    # Save recommendations text
    recommendations_path = crawl_dir / "recommendations.txt"
    with open(recommendations_path, 'w', encoding='utf-8') as f:
        f.write(result.get('recommendations', ''))

    # Save full result with evidence
    recommendations_json_path = crawl_dir / "recommendations.json"
    with open(recommendations_json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, default=str)

    print(f"\nSaved recommendations to:")
    print(f"  - {recommendations_path}")
    print(f"  - {recommendations_json_path}")


def regenerate_report(
    crawl_dir: Path,
    output_path: Optional[Path] = None,
) -> None:
    """Regenerate HTML report with new recommendations.

    Args:
        crawl_dir: Path to crawl directory
        output_path: Output path for report (default: crawl_dir/report.html)
    """
    if output_path is None:
        output_path = crawl_dir / "report.html"

    print(f"\nRegenerating HTML report: {output_path}")

    generator = ReportGenerator()
    generator.generate_report(crawl_dir, output_path)

    print(f"Report regenerated: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate LLM recommendations for an existing crawl report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        'crawl_dir',
        type=Path,
        help="Path to crawl directory containing metadata.json",
    )
    parser.add_argument(
        '--output-path',
        type=Path,
        default=None,
        help="Path for regenerated report (default: overwrite existing)",
    )
    parser.add_argument(
        '--model',
        default=os.environ.get('LLM_MODEL', 'gpt-4'),
        help="LLM model to use (default: gpt-4 or LLM_MODEL env var)",
    )
    parser.add_argument(
        '--provider',
        default=os.environ.get('LLM_PROVIDER', 'openai'),
        choices=['openai', 'anthropic'],
        help="LLM provider (default: openai or LLM_PROVIDER env var)",
    )
    parser.add_argument(
        '--api-key',
        default=None,
        help="API key (or use OPENAI_API_KEY/ANTHROPIC_API_KEY env var)",
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Show what would be generated without calling LLM",
    )
    parser.add_argument(
        '--skip-report',
        action='store_true',
        help="Only regenerate recommendations, don't update HTML report",
    )

    args = parser.parse_args()

    # Validate crawl directory
    if not args.crawl_dir.exists():
        print(f"Error: Crawl directory not found: {args.crawl_dir}", file=sys.stderr)
        sys.exit(1)

    if not (args.crawl_dir / "metadata.json").exists():
        print(f"Error: Not a valid crawl directory (missing metadata.json): {args.crawl_dir}", file=sys.stderr)
        sys.exit(1)

    # Get API key
    api_key = args.api_key
    if not api_key:
        if args.provider == 'openai':
            api_key = os.environ.get('OPENAI_API_KEY')
        elif args.provider == 'anthropic':
            api_key = os.environ.get('ANTHROPIC_API_KEY')

    if not api_key and not args.dry_run:
        print(f"Error: No API key provided. Set --api-key or {args.provider.upper()}_API_KEY env var", file=sys.stderr)
        sys.exit(1)

    try:
        # Regenerate recommendations
        result = regenerate_recommendations(
            crawl_dir=args.crawl_dir,
            api_key=api_key,
            model=args.model,
            provider=args.provider,
            dry_run=args.dry_run,
        )

        if args.dry_run:
            print("\n[DRY RUN] Complete. No changes made.")
            return

        # Save recommendations
        save_recommendations(args.crawl_dir, result)

        # Regenerate report
        if not args.skip_report:
            regenerate_report(args.crawl_dir, args.output_path)

        print("\nRegeneration complete!")

        # Print summary
        parsed = result.get('parsed_recommendations', [])
        if parsed:
            print(f"\nGenerated {len(parsed)} ICE-scored recommendations")
            print("Top 3 recommendations:")
            for i, rec in enumerate(parsed[:3], 1):
                print(f"  {i}. [ICE:{rec.ice_score:.2f}] {rec.action[:60]}...")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
