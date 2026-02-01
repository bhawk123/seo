"""Example usage of the SEO analyzer - Single page analysis."""

from seo import SEOAnalyzer, TechnicalAnalyzer, Config


def main():
    """Run example SEO analysis."""

    # Initialize the analyzer using .env configuration
    config = Config.from_env()

    if not config.llm_api_key:
        print("Error: LLM_API_KEY not found in .env file")
        print("Please create a .env file with your API key")
        return

    analyzer = SEOAnalyzer(
        llm_api_key=config.llm_api_key,
        llm_model=config.llm_model,
        llm_provider=config.llm_provider
    )

    # Analyze a single URL
    url = "https://example.com"
    print(f"Analyzing {url}...")

    crawl_result, seo_score = analyzer.analyze_url(url)

    if not crawl_result.success:
        print(f"Failed to crawl: {crawl_result.error}")
        return

    # Print results
    print(f"\nOverall Score: {seo_score.overall_score}/100")
    print(f"Title Score: {seo_score.title_score}/100")
    print(f"Description Score: {seo_score.description_score}/100")
    print(f"Content Score: {seo_score.content_score}/100")
    print(f"Technical Score: {seo_score.technical_score}/100")

    print("\nStrengths:")
    for strength in seo_score.strengths:
        print(f"  • {strength}")

    print("\nWeaknesses:")
    for weakness in seo_score.weaknesses:
        print(f"  • {weakness}")

    print("\nRecommendations:")
    for rec in seo_score.recommendations:
        print(f"  • {rec}")

    # Technical analysis
    print("\n" + "=" * 60)
    print("Technical SEO Analysis")
    print("=" * 60)

    technical_analyzer = TechnicalAnalyzer()
    pages = {url: crawl_result.metadata}
    technical_issues = technical_analyzer.analyze(pages)

    report = technical_analyzer.format_issues_report(technical_issues)
    print(report)


if __name__ == "__main__":
    main()
