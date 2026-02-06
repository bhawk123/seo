#!/usr/bin/env python3
"""Regenerate LLM recommendations from existing crawl data."""

import json
import os
import sys
from pathlib import Path

# Load .env file
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from seo.llm import LLMClient
from seo.models import TechnicalIssues, PageMetadata


def load_crawl_data(crawl_dir: Path):
    """Load crawl data from saved files."""
    # Load technical issues
    technical_issues_path = crawl_dir / "technical_issues.json"
    with open(technical_issues_path) as f:
        technical_data = json.load(f)

    # Load crawl state for summary
    crawl_state_path = crawl_dir / "crawl_state.json"
    with open(crawl_state_path) as f:
        crawl_state = json.load(f)

    # Load page data
    pages_dir = crawl_dir / "pages"
    site_data = {}
    for page_file in pages_dir.glob("*.json"):
        with open(page_file) as f:
            page_data = json.load(f)
            url = page_data.get("url", "")
            if url:
                site_data[url] = page_data

    # Load advanced analysis (summary only, skip large data)
    advanced_path = crawl_dir / "advanced_analysis.json"
    advanced_summary = {}
    if advanced_path.exists():
        try:
            with open(advanced_path) as f:
                # Read just first part of file to get summary info
                content = f.read(50000)  # First 50KB
                advanced_data = json.loads(content + ']}')  # Try to close JSON
        except:
            advanced_summary = {}

    return technical_data, crawl_state, site_data, advanced_summary


def build_prompt(technical_issues, crawl_summary, site_data, advanced_summary):
    """Build the LLM prompt for recommendations."""
    # Prepare issues summary
    issues_summary = {
        "missing_titles": len(technical_issues.get("missing_titles", [])),
        "duplicate_titles": len(technical_issues.get("duplicate_titles", {})),
        "missing_meta_descriptions": len(technical_issues.get("missing_meta_descriptions", [])),
        "short_meta_descriptions": len(technical_issues.get("short_meta_descriptions", [])),
        "long_meta_descriptions": len(technical_issues.get("long_meta_descriptions", [])),
        "missing_h1": len(technical_issues.get("missing_h1", [])),
        "multiple_h1": len(technical_issues.get("multiple_h1", [])),
        "images_without_alt": len(technical_issues.get("images_without_alt", [])),
        "slow_pages": len(technical_issues.get("slow_pages", [])),
        "thin_content": len(technical_issues.get("thin_content", [])),
        "missing_canonical": len(technical_issues.get("missing_canonical", [])),
    }

    # Sample pages
    sample_pages = []
    for url, page in list(site_data.items())[:5]:
        sample_pages.append({
            "url": url,
            "title": page.get("title", ""),
            "description": page.get("description", ""),
            "h1_tags": page.get("h1_tags", []),
            "word_count": page.get("word_count", 0),
        })

    prompt = f"""
As an SEO expert, analyze this website and provide comprehensive SEO recommendations using the ICE framework for prioritization.

ICE Framework:
- Impact (1-10): How much will this improve SEO/traffic?
- Confidence (1-10): How confident are you this will work?
- Ease (1-10): How easy is this to implement?
- ICE Score = (Impact × Confidence × Ease) / 100

SITE CRAWL SUMMARY:
{json.dumps(crawl_summary, indent=2)}

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
    return prompt


def main():
    """Main function to regenerate recommendations."""
    if len(sys.argv) < 2:
        print("Usage: python regenerate_recommendations.py <crawl_dir>")
        sys.exit(1)

    crawl_dir = Path(sys.argv[1])
    if not crawl_dir.exists():
        print(f"Error: Crawl directory not found: {crawl_dir}")
        sys.exit(1)

    print(f"Loading crawl data from: {crawl_dir}")

    # Load data
    technical_issues, crawl_state, site_data, advanced_summary = load_crawl_data(crawl_dir)

    # Build crawl summary
    progress = crawl_state.get("progress", {})
    crawl_summary = {
        "total_pages": progress.get("pages_crawled", len(site_data)),
        "start_url": crawl_state.get("config", {}).get("start_url", ""),
    }

    print(f"Loaded {len(site_data)} pages")
    print(f"Technical issues loaded: {len(technical_issues)} categories")

    # Build prompt
    prompt = build_prompt(technical_issues, crawl_summary, site_data, advanced_summary)

    print("\nCalling LLM to generate recommendations...")

    # Initialize LLM client with env settings
    llm = LLMClient(
        api_key=os.getenv("LLM_API_KEY"),
        provider=os.getenv("LLM_PROVIDER", "anthropic"),
        model=os.getenv("LLM_MODEL", "claude-sonnet-4-5"),
    )

    # Generate recommendations
    try:
        response = llm._call_llm(prompt)
        print("\nRecommendations generated successfully!")

        # Save recommendations
        rec_path = crawl_dir / "recommendations.txt"
        with open(rec_path, "w") as f:
            f.write(response)
        print(f"Saved to: {rec_path}")

        # Preview
        print("\n" + "=" * 60)
        print("PREVIEW (first 1000 chars):")
        print("=" * 60)
        print(response[:1000])
        print("...")

        return True
    except Exception as e:
        print(f"\nError generating recommendations: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
