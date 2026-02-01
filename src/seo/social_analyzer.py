"""Social meta tag analyzer for Open Graph and Twitter Cards."""

from typing import Dict, List, Optional, Set
from collections import Counter

from seo.models import PageMetadata, SocialMetaAnalysis, SocialMetaPageResult
from seo.config import AnalysisThresholds, default_thresholds


class SocialMetaAnalyzer:
    """Analyzes Open Graph and Twitter Card meta tags."""

    # Default required Open Graph properties
    DEFAULT_REQUIRED_OG: List[str] = [
        'og:title', 'og:description', 'og:image', 'og:url', 'og:type'
    ]

    # Default recommended Open Graph properties
    DEFAULT_RECOMMENDED_OG: List[str] = ['og:site_name', 'og:locale']

    # Default required Twitter Card properties
    DEFAULT_REQUIRED_TWITTER: List[str] = [
        'twitter:card', 'twitter:title', 'twitter:description'
    ]

    # Default recommended Twitter properties
    DEFAULT_RECOMMENDED_TWITTER: List[str] = ['twitter:image', 'twitter:site']

    # Valid twitter:card types
    VALID_TWITTER_CARDS: Set[str] = {'summary', 'summary_large_image', 'app', 'player'}

    # Default scoring weights
    DEFAULT_OG_REQUIRED_POINTS: int = 15
    DEFAULT_OG_RECOMMENDED_POINTS: int = 5
    DEFAULT_TWITTER_REQUIRED_POINTS: int = 25
    DEFAULT_TWITTER_RECOMMENDED_POINTS: int = 10

    def __init__(
        self,
        thresholds: Optional[AnalysisThresholds] = None,
        required_og: Optional[List[str]] = None,
        recommended_og: Optional[List[str]] = None,
        required_twitter: Optional[List[str]] = None,
        recommended_twitter: Optional[List[str]] = None,
    ):
        """Initialize analyzer with configurable settings.

        Args:
            thresholds: Analysis thresholds configuration
            required_og: Required Open Graph properties
            recommended_og: Recommended Open Graph properties
            required_twitter: Required Twitter Card properties
            recommended_twitter: Recommended Twitter Card properties
        """
        self.thresholds = thresholds or default_thresholds
        self.required_og = required_og or self.DEFAULT_REQUIRED_OG
        self.recommended_og = recommended_og or self.DEFAULT_RECOMMENDED_OG
        self.required_twitter = required_twitter or self.DEFAULT_REQUIRED_TWITTER
        self.recommended_twitter = recommended_twitter or self.DEFAULT_RECOMMENDED_TWITTER

    @property
    def og_coverage_target(self) -> float:
        """Target OG coverage percentage."""
        return self.thresholds.social_og_coverage_target

    @property
    def twitter_coverage_target(self) -> float:
        """Target Twitter coverage percentage."""
        return self.thresholds.social_twitter_coverage_target

    def analyze(self, pages: Dict[str, PageMetadata]) -> SocialMetaAnalysis:
        """Analyze social meta tags across all pages.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            SocialMetaAnalysis with social meta metrics
        """
        if not pages:
            return SocialMetaAnalysis()

        analysis = SocialMetaAnalysis(total_pages=len(pages))

        all_missing_og: List[str] = []
        all_missing_twitter: List[str] = []
        page_results: List[SocialMetaPageResult] = []

        for url, page in pages.items():
            result = self._analyze_page(url, page)
            page_results.append(result)

            if result.og_present:
                analysis.pages_with_og += 1
            else:
                analysis.pages_missing_og.append(url)

            if result.twitter_present:
                analysis.pages_with_twitter += 1
            else:
                analysis.pages_missing_twitter.append(url)

            all_missing_og.extend(result.og_missing)
            all_missing_twitter.extend(result.twitter_missing)

            if result.issues:
                analysis.pages_with_issues.append({
                    'url': url,
                    'issues': result.issues,
                    'og_score': result.og_score,
                    'twitter_score': result.twitter_score
                })

        # Calculate coverage percentages
        if analysis.total_pages > 0:
            analysis.og_coverage_percentage = round(
                analysis.pages_with_og / analysis.total_pages * 100, 1
            )
            analysis.twitter_coverage_percentage = round(
                analysis.pages_with_twitter / analysis.total_pages * 100, 1
            )

        # Calculate average scores
        og_scores = [r.og_score for r in page_results if r.og_present]
        twitter_scores = [r.twitter_score for r in page_results if r.twitter_present]

        if og_scores:
            analysis.avg_og_score = round(sum(og_scores) / len(og_scores), 1)
        if twitter_scores:
            analysis.avg_twitter_score = round(sum(twitter_scores) / len(twitter_scores), 1)

        # Count common missing properties
        analysis.common_missing_og = dict(Counter(all_missing_og).most_common(10))
        analysis.common_missing_twitter = dict(Counter(all_missing_twitter).most_common(10))

        # Sort pages by combined score
        page_results_sorted = sorted(
            page_results,
            key=lambda x: x.og_score + x.twitter_score,
            reverse=True
        )
        analysis.best_pages = [
            {'url': r.url, 'og_score': r.og_score, 'twitter_score': r.twitter_score}
            for r in page_results_sorted[:5] if r.og_score + r.twitter_score > 0
        ]

        page_results_sorted_asc = sorted(
            page_results,
            key=lambda x: x.og_score + x.twitter_score
        )
        analysis.worst_pages = [
            {'url': r.url, 'og_score': r.og_score, 'twitter_score': r.twitter_score,
             'issues': r.issues[:3]}
            for r in page_results_sorted_asc[:10]
        ]

        analysis.page_results = page_results

        return analysis

    def _analyze_page(self, url: str, page: PageMetadata) -> SocialMetaPageResult:
        """Analyze social meta tags for a single page."""
        result = SocialMetaPageResult(url=url)

        # Analyze Open Graph
        og = page.open_graph or {}
        result.og_properties = og
        result.og_present = len(og) > 0

        og_score = 0
        for prop in self.required_og:
            prop_key = prop.replace('og:', '')
            if prop in og or prop_key in og:
                og_score += self.DEFAULT_OG_REQUIRED_POINTS
            else:
                result.og_missing.append(prop)
                result.issues.append(f"Missing required OG property: {prop}")

        for prop in self.recommended_og:
            prop_key = prop.replace('og:', '')
            if prop in og or prop_key in og:
                og_score += self.DEFAULT_OG_RECOMMENDED_POINTS

        # Validate og:image if present
        og_image = og.get('og:image') or og.get('image')
        if og_image:
            og_score += 5
            if not og_image.startswith('http'):
                result.issues.append("og:image should be an absolute URL")

        result.og_score = min(og_score, 100)

        # Analyze Twitter Card
        twitter = page.twitter_card or {}
        result.twitter_properties = twitter
        result.twitter_present = len(twitter) > 0

        twitter_score = 0
        for prop in self.required_twitter:
            prop_name = prop.replace('twitter:', '')
            if prop in twitter or prop_name in twitter:
                twitter_score += self.DEFAULT_TWITTER_REQUIRED_POINTS
            else:
                result.twitter_missing.append(prop)
                result.issues.append(f"Missing required Twitter property: {prop}")

        for prop in self.recommended_twitter:
            prop_name = prop.replace('twitter:', '')
            if prop in twitter or prop_name in twitter:
                twitter_score += self.DEFAULT_TWITTER_RECOMMENDED_POINTS

        # Validate twitter:card value
        card_type = twitter.get('twitter:card') or twitter.get('card')
        if card_type and card_type not in self.VALID_TWITTER_CARDS:
            result.issues.append(f"Invalid twitter:card value: {card_type}")
            twitter_score -= 10

        result.twitter_score = max(0, min(twitter_score, 100))

        return result
