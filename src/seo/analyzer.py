"""SEO analyzer that combines crawling and LLM analysis."""

from pathlib import Path
from typing import Callable, Optional, Dict, List
import json
import requests
from urllib.parse import urlparse

from seo.crawler import WebCrawler
from seo.site_crawler import SiteCrawler
from seo.technical import TechnicalAnalyzer
from seo.llm import LLMClient
from seo.models import (
    SEOScore,
    CrawlResult,
    PageMetadata,
    TechnicalIssues,
    ContentQualityMetrics,
    SecurityAnalysis,
    URLStructureAnalysis,
)
from seo.content_quality import ContentQualityAnalyzer
from seo.advanced_analyzer import (
    SecurityAnalyzer,
    URLStructureAnalyzer,
    MobileSEOAnalyzer,
    InternationalSEOAnalyzer,
)
from seo.crawlability import CrawlabilityAnalyzer


class SEOAnalyzer:
    """Analyzes websites for SEO quality using crawling and LLM."""

    def __init__(
        self,
        llm_api_key: Optional[str] = None,
        llm_model: str = "gpt-4",
        llm_provider: str = "openai",
        user_agent: Optional[str] = None,
    ):
        """Initialize the SEO analyzer.

        Args:
            llm_api_key: API key for LLM provider
            llm_model: LLM model to use
            llm_provider: LLM provider (openai, anthropic)
            user_agent: Custom user agent for crawling
        """
        self.crawler = WebCrawler(user_agent=user_agent)
        self.llm = LLMClient(
            api_key=llm_api_key, model=llm_model, provider=llm_provider
        )

    def analyze_url(self, url: str) -> tuple[CrawlResult, Optional[SEOScore]]:
        """Analyze a URL for SEO quality.

        Args:
            url: The URL to analyze

        Returns:
            Tuple of (CrawlResult, SEOScore or None if analysis failed)
        """
        crawl_result = self.crawler.crawl(url)

        if not crawl_result.success:
            print(f"Failed to crawl {url}: {crawl_result.error}")
            return crawl_result, None

        seo_score = self._analyze_with_llm(crawl_result)

        return crawl_result, seo_score

    def _analyze_with_llm(self, crawl_result: CrawlResult) -> SEOScore:
        """Analyze crawl results using LLM.

        Args:
            crawl_result: The crawl result to analyze

        Returns:
            SEOScore with analysis results
        """
        metadata_dict = {
            "title": crawl_result.metadata.title,
            "description": crawl_result.metadata.description,
            "h1_tags": crawl_result.metadata.h1_tags,
            "h2_tags": crawl_result.metadata.h2_tags,
            "word_count": crawl_result.metadata.word_count,
            "keywords": crawl_result.metadata.keywords,
        }

        analysis = self.llm.analyze_seo(
            content=crawl_result.html,
            metadata=metadata_dict,
            url=crawl_result.url,
        )

        return SEOScore(
            url=crawl_result.url,
            overall_score=analysis.get("overall_score", 0),
            title_score=analysis.get("title_score", 0),
            description_score=analysis.get("description_score", 0),
            content_score=analysis.get("content_score", 0),
            technical_score=analysis.get("technical_score", 0),
            recommendations=analysis.get("recommendations", []),
            strengths=analysis.get("strengths", []),
            weaknesses=analysis.get("weaknesses", []),
        )

    def analyze_multiple_urls(
        self, urls: list[str]
    ) -> list[tuple[CrawlResult, Optional[SEOScore]]]:
        """Analyze multiple URLs.

        Args:
            urls: List of URLs to analyze

        Returns:
            List of tuples (CrawlResult, SEOScore or None)
        """
        results = []
        for url in urls:
            print(f"Analyzing {url}...")
            result = self.analyze_url(url)
            results.append(result)
        return results

    def analyze_site(
        self,
        start_url: str,
        max_pages: int = 50,
        rate_limit: float = 0.5,
        enable_lighthouse: bool = True,
        lighthouse_sample_rate: float = 0.1,
        enable_psi: bool = False,
        psi_api_key: Optional[str] = None,
        psi_strategy: str = "mobile",
        stealth_mode: bool = False,
        render_js: bool = False,
        browser_type: str = "chromium",
        seed_urls: Optional[list[str]] = None,
        resume_state: Optional[dict] = None,
        output_manager: Optional["OutputManager"] = None,
        crawl_dir: Optional[Path] = None,
    ) -> tuple[Dict[str, PageMetadata], TechnicalIssues, str, Dict, Optional[SiteCrawler]]:
        """Analyze an entire site using breadth-first crawling.

        Args:
            start_url: The URL to start crawling from
            max_pages: Maximum number of pages to crawl
            rate_limit: Seconds to wait between requests
            enable_lighthouse: Run local Lighthouse CLI audits during crawl (default: True)
            lighthouse_sample_rate: Fraction of pages to audit (0.0-1.0, default: 0.1 = 10%)
            enable_psi: Enable Google PageSpeed Insights API for CrUX real user data
            psi_api_key: Google PageSpeed Insights API key (required if enable_psi=True)
            psi_strategy: 'mobile' or 'desktop' analysis strategy for PSI
            stealth_mode: Use browser-like headers to avoid bot detection (default: False)
            render_js: Use browser-based crawling with JavaScript rendering (default: False)
            browser_type: Browser engine to use when render_js=True (chromium, firefox, webkit)
            seed_urls: Optional list of URLs to seed the crawl queue (from sitemap, etc.)
            resume_state: Optional state dict to resume from a previous crawl
            output_manager: OutputManager instance for saving checkpoints
            crawl_dir: Directory to save checkpoints to

        Returns:
            Tuple of (site_data, technical_issues, llm_recommendations, advanced_analysis, site_crawler)
        """
        # Crawl the site
        site_crawler = SiteCrawler(
            max_pages=max_pages,
            rate_limit=rate_limit,
            user_agent=self.crawler.user_agent,
            enable_lighthouse=enable_lighthouse,
            lighthouse_sample_rate=lighthouse_sample_rate,
            stealth_mode=stealth_mode,
            render_js=render_js,
            browser_type=browser_type,
            seed_urls=seed_urls,
            resume_state=resume_state,
            output_manager=output_manager,
            crawl_dir=crawl_dir,
        )

        site_data = site_crawler.crawl_site(start_url)

        if not site_data:
            print("No pages were successfully crawled")
            return {}, TechnicalIssues(), "", {}

        # Analyze technical issues
        print("\n" + "=" * 60)
        print("Analyzing Technical SEO Issues...")
        print("=" * 60 + "\n")

        technical_analyzer = TechnicalAnalyzer()
        technical_issues = technical_analyzer.analyze(site_data)

        # Print technical report
        tech_report = technical_analyzer.format_issues_report(technical_issues)
        print(tech_report)

        # Run advanced analyzers
        print("\n" + "=" * 60)
        print("Running Advanced SEO Analysis...")
        print("=" * 60 + "\n")

        advanced_analysis = self._run_advanced_analysis(site_data)

        # Print advanced analysis summary
        self._print_advanced_summary(advanced_analysis)

        # Run PageSpeed Insights analysis if enabled
        if enable_psi and psi_api_key:
            print("\n" + "=" * 60)
            print("Running Google PageSpeed Insights Analysis...")
            print("=" * 60 + "\n")

            import asyncio
            asyncio.run(self._run_pagespeed_insights(
                site_data,
                psi_api_key,
                psi_strategy
            ))

        # Generate LLM recommendations
        print("\n" + "=" * 60)
        print("Generating AI-Powered Recommendations...")
        print("=" * 60 + "\n")

        llm_recommendations = self._generate_site_recommendations(
            site_data, technical_issues, site_crawler.get_crawl_summary(), advanced_analysis
        )

        print(llm_recommendations)

        # Save snapshot to database
        try:
            print("\n" + "=" * 60)
            print("Saving analysis snapshot to database...")
            print("=" * 60 + "\n")
            self._save_metrics_snapshot(start_url, site_data, technical_issues)
            print("Snapshot saved successfully.")
        except Exception as e:
            print(f"Error saving snapshot to database: {e}")

        return site_data, technical_issues, llm_recommendations, advanced_analysis, site_crawler

    def _save_metrics_snapshot(self, domain_url: str, site_data: Dict, technical_issues: TechnicalIssues):
        """Compiles and saves the metrics snapshot to the database."""
        from .database import MetricsDatabase
        from datetime import datetime
        from urllib.parse import urlparse

        db = MetricsDatabase()
        
        domain = urlparse(domain_url).netloc or domain_url

        # This is a basic mapping, more advanced metrics would be aggregated here
        metrics = {
            "domain": domain,
            "crawl_date": datetime.now(),
            "crawlable_pages": len(site_data),
            "total_issues": (
                len(technical_issues.missing_titles) +
                len(technical_issues.duplicate_titles) +
                len(technical_issues.missing_meta_descriptions) +
                len(technical_issues.short_meta_descriptions) +
                len(technical_issues.long_meta_descriptions) +
                len(technical_issues.missing_h1) +
                len(technical_issues.multiple_h1) +
                len(technical_issues.images_without_alt) +
                len(technical_issues.slow_pages) +
                len(technical_issues.thin_content) +
                len(technical_issues.missing_canonical) +
                len(technical_issues.broken_links) +
                len(technical_issues.orphan_pages)
            ),
            "thin_content_count": len(technical_issues.thin_content),
            "avg_load_time": sum(p.load_time for p in site_data.values()) / len(site_data) if site_data else 0,
        }

        db.save_snapshot(metrics)
        db.close()

    def _run_advanced_analysis(self, site_data: Dict[str, PageMetadata]) -> Dict:
        """Run advanced analyzers on all pages.

        Args:
            site_data: Dictionary of URL to PageMetadata

        Returns:
            Dictionary with advanced analysis results
        """
        content_analyzer = ContentQualityAnalyzer()
        security_analyzer = SecurityAnalyzer()
        url_analyzer = URLStructureAnalyzer()
        mobile_analyzer = MobileSEOAnalyzer()
        international_analyzer = InternationalSEOAnalyzer()

        # TODO: Import new modular checkers when implemented
        # from seo.accessibility import check_accessibility
        # from seo.social import check_social_meta_tags
        # from seo.schema import check_structured_data

        results = {
            'content_quality': [],
            'security': [],
            'url_structure': [],
            'mobile': [],
            'international': [],
            # 'accessibility': [],  # TODO: Implement
            # 'social_meta': [],    # TODO: Implement
            # 'structured_data': [], # TODO: Implement
        }

        for url, page_metadata in site_data.items():

            # Content quality analysis
            if page_metadata.content_text:
                content_metrics = content_analyzer.analyze(url, page_metadata.content_text)
                results['content_quality'].append(content_metrics)

            # Security analysis
            security_analysis = security_analyzer.analyze(
                url,
                page_metadata,
                page_metadata.security_headers
            )
            results['security'].append(security_analysis)

            # URL structure analysis
            url_analysis = url_analyzer.analyze(url)
            results['url_structure'].append(url_analysis)

            # Mobile SEO analysis
            mobile_analysis = mobile_analyzer.analyze(page_metadata)
            results['mobile'].append(mobile_analysis)

            # International SEO analysis
            international_analysis = international_analyzer.analyze(page_metadata)
            results['international'].append(international_analysis)

            # TODO: New modular analysis - implement these modules
            # accessibility_issues = check_accessibility(page_metadata)
            # if accessibility_issues:
            #     results['accessibility'].extend(accessibility_issues)
            #
            # social_issues = check_social_meta_tags(page_metadata)
            # if social_issues:
            #     results['social_meta'].extend(social_issues)
            #
            # schema_issues = check_structured_data(page_metadata)
            # if schema_issues:
            #     results['structured_data'].extend(schema_issues)

        # Add crawlability analysis (site-wide)
        results['crawlability'] = self._analyze_crawlability(site_data)

        # Add technology stack analysis (site-wide)
        from seo.advanced_analyzer import TechnologyAnalyzer
        technology_analyzer = TechnologyAnalyzer()
        results['technology'] = technology_analyzer.analyze_site_technologies(site_data)

        # Add metadata_list for Lighthouse/CWV analysis in reports
        from dataclasses import asdict
        import json

        # Convert metadata to dicts with proper datetime serialization
        metadata_list = []
        for page_metadata in site_data.values():
            page_dict = asdict(page_metadata)
            # Convert datetime to ISO string
            if 'crawled_at' in page_dict and page_dict['crawled_at']:
                page_dict['crawled_at'] = page_dict['crawled_at'].isoformat()
            metadata_list.append(page_dict)

        results['metadata_list'] = metadata_list

        return results

    def _analyze_crawlability(self, site_data: Dict[str, PageMetadata]) -> Dict:
        """Analyze site crawlability.

        Args:
            site_data: Dictionary of crawled pages

        Returns:
            Crawlability analysis results
        """
        if not site_data:
            return {}

        # Extract URLs and broken links
        crawled_urls = list(site_data.keys())
        all_discovered_urls = set()
        broken_links = []

        # Collect all links and broken links from pages
        for url, page in site_data.items():
            all_discovered_urls.update(page.links)
            broken_links.extend(page.broken_links)

        # Get base URL for analysis
        first_url = crawled_urls[0]
        parsed = urlparse(first_url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        # Fetch robots.txt
        robots_txt_content = None
        try:
            robots_url = f"{domain}/robots.txt"
            response = requests.get(
                robots_url,
                timeout=10,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; SEO-Analyzer/1.0)",
                    "Accept": "text/plain,*/*",
                }
            )
            if response.status_code == 200:
                robots_txt_content = response.text
        except requests.RequestException:
            pass  # robots.txt not accessible

        # Create crawlability analyzer
        analyzer = CrawlabilityAnalyzer(first_url, robots_txt_content=robots_txt_content)

        # Run analysis
        crawl_score = analyzer.analyze(crawled_urls, all_discovered_urls, broken_links)

        # Convert to dict for JSON serialization
        return {
            'has_robots_txt': crawl_score.has_robots_txt,
            'robots_txt_url': crawl_score.robots_txt_url,
            'robots_txt_errors': crawl_score.robots_txt_errors,
            'robots_txt_warnings': crawl_score.robots_txt_warnings,
            'disallowed_rules': crawl_score.disallowed_rules,
            'sitemap_urls_in_robots': crawl_score.sitemap_urls_in_robots,
            'has_xml_sitemap': crawl_score.has_xml_sitemap,
            'sitemap_urls': crawl_score.sitemap_urls,
            'sitemap_errors': crawl_score.sitemap_errors,
            'sitemap_warnings': crawl_score.sitemap_warnings,
            'total_urls_in_sitemaps': crawl_score.total_urls_in_sitemaps,
            'orphan_pages': crawl_score.orphan_pages,
            'pages_crawled': crawl_score.pages_crawled,
            'pages_not_in_sitemap': crawl_score.pages_not_in_sitemap,
            'broken_links_count': crawl_score.broken_links_count,
            'crawl_efficiency_score': crawl_score.crawl_efficiency_score,
            'overall_score': crawl_score.overall_score,
            'recommendations': analyzer.get_recommendations(crawl_score),
        }

    async def _run_pagespeed_insights(
        self,
        site_data: Dict[str, PageMetadata],
        api_key: str,
        strategy: str = "mobile"
    ) -> None:
        """
        Run PageSpeed Insights analysis on crawled pages.

        Updates PageMetadata objects in-place with Lighthouse and CrUX data.

        Args:
            site_data: Dictionary of crawled pages
            api_key: Google PageSpeed Insights API key
            strategy: 'mobile' or 'desktop'
        """
        from seo.external.pagespeed_insights import PageSpeedInsightsAPI

        psi_api = PageSpeedInsightsAPI(api_key=api_key, strategy=strategy)

        # Analyze all pages (or limit to first N for large crawls)
        urls_to_analyze = list(site_data.keys())

        print(f"Analyzing {len(urls_to_analyze)} pages with PageSpeed Insights ({strategy})...")
        print("This may take several minutes due to API rate limits.\n")

        for i, url in enumerate(urls_to_analyze, 1):
            try:
                # Run PSI analysis
                psi_data = await psi_api.analyze(url, strategy=strategy)

                # Get the PageMetadata object
                page_metadata = site_data[url]

                # Update with Lighthouse scores
                page_metadata.lighthouse_performance_score = psi_data.get('performance_score')
                page_metadata.lighthouse_accessibility_score = psi_data.get('accessibility_score')
                page_metadata.lighthouse_best_practices_score = psi_data.get('best_practices_score')
                page_metadata.lighthouse_seo_score = psi_data.get('seo_score')
                page_metadata.lighthouse_pwa_score = psi_data.get('pwa_score')

                # Update with performance metrics
                page_metadata.lighthouse_fcp = psi_data.get('fcp')
                page_metadata.lighthouse_lcp = psi_data.get('lcp')
                page_metadata.lighthouse_si = psi_data.get('si')
                page_metadata.lighthouse_tti = psi_data.get('tti')
                page_metadata.lighthouse_tbt = psi_data.get('tbt')
                page_metadata.lighthouse_cls = psi_data.get('cls')
                page_metadata.lighthouse_fetch_time = psi_data.get('fetch_time')

                # Update with opportunities
                page_metadata.lighthouse_opportunities = psi_data.get('opportunities', [])

                # Update with CrUX data if available
                crux_data = psi_data.get('crux_data')
                if crux_data:
                    if 'lcp' in crux_data:
                        page_metadata.crux_lcp_percentile = crux_data['lcp'].get('percentile')
                        page_metadata.crux_lcp_category = crux_data['lcp'].get('category')
                    if 'fid' in crux_data:
                        page_metadata.crux_fid_percentile = crux_data['fid'].get('percentile')
                        page_metadata.crux_fid_category = crux_data['fid'].get('category')
                    if 'cls' in crux_data:
                        page_metadata.crux_cls_percentile = crux_data['cls'].get('percentile')
                        page_metadata.crux_cls_category = crux_data['cls'].get('category')
                    page_metadata.crux_overall_category = crux_data.get('overall_category')

                print(f"  [{i}/{len(urls_to_analyze)}] ✓ {url}")

            except Exception as e:
                print(f"  [{i}/{len(urls_to_analyze)}] ✗ {url}: {e}")
                continue

        # Print stats
        stats = psi_api.get_stats()
        print(f"\nPageSpeed Insights Complete:")
        print(f"  Total requests: {stats['total_requests']}")
        print(f"  Failed: {stats['failed_requests']}")
        print(f"  Success rate: {stats['success_rate']}%")

    def _print_advanced_summary(self, advanced_analysis: Dict) -> None:
        """Print summary of advanced analysis results.

        Args:
            advanced_analysis: Advanced analysis results
        """
        # Content Quality Summary
        content_quality = advanced_analysis['content_quality']
        if content_quality:
            avg_readability = sum(c.readability_score for c in content_quality) / len(content_quality)
            print(f"Content Quality:")
            print(f"  Average Readability Score: {avg_readability:.1f}/100")
            print(f"  Pages Analyzed: {len(content_quality)}")

        # Security Summary
        security = advanced_analysis['security']
        if security:
            https_count = sum(1 for s in security if s.has_https)
            avg_security_score = sum(s.security_score for s in security) / len(security)
            print(f"\nSecurity:")
            print(f"  HTTPS Pages: {https_count}/{len(security)}")
            print(f"  Average Security Score: {avg_security_score:.1f}/100")

        # URL Structure Summary
        url_structure = advanced_analysis['url_structure']
        if url_structure:
            total_issues = sum(len(u.issues) for u in url_structure)
            pages_with_keywords = sum(1 for u in url_structure if u.has_keywords)
            print(f"\nURL Structure:")
            print(f"  Pages with Keywords: {pages_with_keywords}/{len(url_structure)}")
            print(f"  Total URL Issues: {total_issues}")

        # Mobile Summary
        mobile = advanced_analysis['mobile']
        if mobile:
            has_viewport = sum(1 for m in mobile if m.get('has_viewport', False))
            avg_mobile_score = sum(m.get('mobile_score', 0) for m in mobile) / len(mobile)
            print(f"\nMobile SEO:")
            print(f"  Pages with Viewport: {has_viewport}/{len(mobile)}")
            print(f"  Average Mobile Score: {avg_mobile_score:.1f}/100")

        # International Summary
        international = advanced_analysis['international']
        if international:
            has_lang = sum(1 for i in international if i.get('has_lang_attribute', False))
            has_hreflang = sum(1 for i in international if i.get('has_hreflang', False))
            print(f"\nInternational SEO:")
            print(f"  Pages with Lang Attribute: {has_lang}/{len(international)}")
            print(f"  Pages with Hreflang: {has_hreflang}/{len(international)}")

        # New modular summaries
        accessibility_issues = advanced_analysis.get('accessibility', [])
        if accessibility_issues:
            print(f"\nAccessibility:")
            print(f"  Total Issues Found: {len(accessibility_issues)}")

        social_issues = advanced_analysis.get('social_meta', [])
        if social_issues:
            print(f"\nSocial Meta Tags:")
            print(f"  Total Issues Found: {len(social_issues)}")
        
        schema_issues = advanced_analysis.get('structured_data', [])
        if schema_issues:
            print(f"\nStructured Data:")
            print(f"  Total Issues Found: {len(schema_issues)}")

    def _generate_site_recommendations(
        self,
        site_data: Dict[str, PageMetadata],
        technical_issues: TechnicalIssues,
        crawl_summary: dict,
        advanced_analysis: Dict = None,
    ) -> str:
        """Generate LLM-powered recommendations for entire site.

        Args:
            site_data: Dictionary of URL to PageMetadata
            technical_issues: Technical issues found
            crawl_summary: Summary statistics from crawl

        Returns:
            LLM-generated recommendations
        """
        # Prepare summary for LLM
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

        # Prepare advanced analysis summary for LLM
        advanced_summary = {}
        if advanced_analysis:
            # Content quality summary
            content_quality = advanced_analysis.get('content_quality', [])
            if content_quality:
                avg_readability = sum(c.readability_score for c in content_quality) / len(content_quality)
                advanced_summary['content_quality'] = {
                    'avg_readability_score': round(avg_readability, 1),
                    'pages_analyzed': len(content_quality),
                }

            # Security summary
            security = advanced_analysis.get('security', [])
            if security:
                https_count = sum(1 for s in security if s.has_https)
                avg_security_score = sum(s.security_score for s in security) / len(security)
                advanced_summary['security'] = {
                    'https_pages': https_count,
                    'total_pages': len(security),
                    'avg_security_score': round(avg_security_score, 1),
                }

            # URL structure summary
            url_structure = advanced_analysis.get('url_structure', [])
            if url_structure:
                total_issues = sum(len(u.issues) for u in url_structure)
                pages_with_keywords = sum(1 for u in url_structure if u.has_keywords)
                advanced_summary['url_structure'] = {
                    'pages_with_keywords': pages_with_keywords,
                    'total_pages': len(url_structure),
                    'total_url_issues': total_issues,
                }

            # Mobile summary
            mobile = advanced_analysis.get('mobile', [])
            if mobile:
                has_viewport = sum(1 for m in mobile if m.get('has_viewport', False))
                avg_mobile_score = sum(m.get('mobile_score', 0) for m in mobile) / len(mobile)
                advanced_summary['mobile'] = {
                    'pages_with_viewport': has_viewport,
                    'total_pages': len(mobile),
                    'avg_mobile_score': round(avg_mobile_score, 1),
                }

            # International summary
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

        try:
            response = self.llm._call_llm(prompt)
            return response
        except Exception as e:
            return f"Failed to generate LLM recommendations: {e}"
