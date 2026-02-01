"""Redirect chain analyzer for crawl efficiency assessment."""

from typing import Dict, List, Optional

from seo.models import PageMetadata, RedirectAnalysis, RedirectChain
from seo.config import AnalysisThresholds, default_thresholds


class RedirectAnalyzer:
    """Analyzes redirect chains and their performance impact."""

    def __init__(self, thresholds: Optional[AnalysisThresholds] = None):
        """Initialize analyzer with configurable thresholds.

        Args:
            thresholds: Analysis thresholds configuration
        """
        self.thresholds = thresholds or default_thresholds

    @property
    def ms_per_redirect(self) -> int:
        """Estimated milliseconds per redirect hop."""
        return self.thresholds.redirect_ms_per_hop

    @property
    def long_chain_threshold(self) -> int:
        """Threshold for 'long' chain classification."""
        return self.thresholds.redirect_long_chain_threshold

    def analyze(self, pages: Dict[str, PageMetadata]) -> RedirectAnalysis:
        """Analyze redirect chains across all pages.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            RedirectAnalysis with redirect metrics
        """
        if not pages:
            return RedirectAnalysis()

        analysis = RedirectAnalysis(
            total_pages=len(pages),
            avg_time_per_redirect_ms=self.ms_per_redirect
        )

        chains: List[RedirectChain] = []

        for url, page in pages.items():
            if page.was_redirected and page.redirect_chain:
                analysis.pages_with_redirects += 1

                chain = RedirectChain(
                    source_url=url,
                    final_url=page.final_url or url,
                    chain=page.redirect_chain,
                    hop_count=len(page.redirect_chain),
                    estimated_time_ms=len(page.redirect_chain) * self.ms_per_redirect
                )
                chains.append(chain)

                # Count by length
                if chain.hop_count == 1:
                    analysis.chains_1_hop += 1
                elif chain.hop_count == 2:
                    analysis.chains_2_hops += 1
                else:
                    analysis.chains_3_plus_hops += 1
                    if chain.hop_count >= self.long_chain_threshold:
                        analysis.long_chains.append({
                            'source': chain.source_url,
                            'final': chain.final_url,
                            'hops': chain.hop_count,
                            'chain': chain.chain[:5],  # First 5 URLs
                            'time_ms': chain.estimated_time_ms
                        })

                analysis.total_hops += chain.hop_count
                analysis.total_time_wasted_ms += chain.estimated_time_ms

        analysis.total_chains = len(chains)

        if chains:
            analysis.avg_hops_per_chain = round(
                analysis.total_hops / len(chains), 2
            )
            analysis.max_chain_length = max(c.hop_count for c in chains)

        # Sort long chains by hop count
        analysis.long_chains.sort(key=lambda x: x['hops'], reverse=True)

        # Store all chains (limited)
        analysis.all_chains = [
            {
                'source': c.source_url,
                'final': c.final_url,
                'hops': c.hop_count,
                'time_ms': c.estimated_time_ms
            }
            for c in sorted(chains, key=lambda x: x.hop_count, reverse=True)[:50]
        ]

        # Generate recommendations
        analysis.recommendations = self._generate_recommendations(analysis)

        return analysis

    def _generate_recommendations(self, analysis: RedirectAnalysis) -> List[str]:
        """Generate recommendations based on redirect analysis."""
        recommendations = []

        if analysis.chains_3_plus_hops > 0:
            recommendations.append(
                f"{analysis.chains_3_plus_hops} redirect chains have {self.long_chain_threshold}+ hops. "
                "Consolidate these to single redirects to improve performance."
            )

        if analysis.total_time_wasted_ms > 1000:
            seconds = analysis.total_time_wasted_ms / 1000
            recommendations.append(
                f"Redirect chains waste approximately {seconds:.1f} seconds "
                f"of cumulative load time (estimated at {self.ms_per_redirect}ms per hop). "
                "Update internal links to point to final URLs."
            )

        if analysis.total_pages > 0 and analysis.pages_with_redirects > analysis.total_pages * 0.1:
            percentage = (analysis.pages_with_redirects / analysis.total_pages) * 100
            recommendations.append(
                f"{percentage:.0f}% of pages involve redirects. "
                "Review URL structure to minimize redirect dependencies."
            )

        if analysis.max_chain_length > 4:
            recommendations.append(
                f"Maximum chain length is {analysis.max_chain_length} hops. "
                "This significantly impacts crawl efficiency and should be fixed immediately."
            )

        return recommendations
