"""Redirect chain analyzer for crawl efficiency assessment."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from seo.models import (
    PageMetadata,
    RedirectAnalysis,
    RedirectChain,
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)
from seo.config import AnalysisThresholds, default_thresholds
from seo.constants import (
    MAX_CHAIN_URLS_IN_EVIDENCE,
    MAX_ALL_CHAINS_TO_STORE,
    HIGH_REDIRECT_PERCENTAGE_THRESHOLD,
)


class RedirectAnalyzer:
    """Analyzes redirect chains and their performance impact."""

    def __init__(self, thresholds: Optional[AnalysisThresholds] = None):
        """Initialize analyzer with configurable thresholds.

        Args:
            thresholds: Analysis thresholds configuration
        """
        self.thresholds = thresholds or default_thresholds
        self._evidence_collection: Optional[EvidenceCollection] = None

    @property
    def ms_per_redirect(self) -> int:
        """Estimated milliseconds per redirect hop."""
        return self.thresholds.redirect_ms_per_hop

    @property
    def long_chain_threshold(self) -> int:
        """Threshold for 'long' chain classification."""
        return self.thresholds.redirect_long_chain_threshold

    def analyze(self, pages: Dict[str, PageMetadata]) -> Tuple[RedirectAnalysis, Dict]:
        """Analyze redirect chains across all pages.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Tuple of (RedirectAnalysis, evidence_dict)
        """
        self._evidence_collection = EvidenceCollection(
            finding='redirect_analysis',
            component_id='redirect_analyzer',
        )

        if not pages:
            return RedirectAnalysis(), self._evidence_collection.to_dict()

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
                            'chain': chain.chain[:MAX_CHAIN_URLS_IN_EVIDENCE],
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
            for c in sorted(chains, key=lambda x: x.hop_count, reverse=True)[:MAX_ALL_CHAINS_TO_STORE]
        ]

        # Generate recommendations
        analysis.recommendations = self._generate_recommendations(analysis)

        # Add evidence for redirect chains
        self._add_chain_evidence(chains, analysis)
        self._add_summary_evidence(analysis)

        return analysis, self._evidence_collection.to_dict()

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

        high_redirect_ratio = HIGH_REDIRECT_PERCENTAGE_THRESHOLD / 100.0
        if analysis.total_pages > 0 and analysis.pages_with_redirects > analysis.total_pages * high_redirect_ratio:
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

    def _add_chain_evidence(
        self,
        chains: List[RedirectChain],
        analysis: RedirectAnalysis,
    ) -> None:
        """Add evidence for redirect chains.

        Args:
            chains: List of redirect chains found
            analysis: The analysis object
        """
        # Add evidence for long chains (detailed)
        for chain in chains:
            if chain.hop_count >= self.long_chain_threshold:
                # Build full chain path for evidence
                chain_path = []
                for i, url in enumerate(chain.chain):
                    # Extract status code from chain if available
                    chain_path.append({
                        'hop': i + 1,
                        'url': url[:100],
                        'status': 301 if i < len(chain.chain) - 1 else 200,  # Simplified
                    })

                record = EvidenceRecord(
                    component_id='redirect_analyzer',
                    finding='long_redirect_chain',
                    evidence_string=f'{chain.hop_count} hops: {chain.source_url[:50]} -> {chain.final_url[:50]}',
                    confidence=ConfidenceLevel.HIGH,
                    timestamp=datetime.now(),
                    source='Redirect Chain Analysis',
                    source_type=EvidenceSourceType.MEASUREMENT,
                    source_location=chain.source_url,
                    measured_value=chain.hop_count,
                    ai_generated=False,
                    reasoning=f'Chain exceeds threshold of {self.long_chain_threshold} hops',
                    input_summary={
                        'threshold': f'> {self.long_chain_threshold} hops',
                        'chain_path': chain_path,
                        'time_waste_ms': chain.estimated_time_ms,
                        'source_url': chain.source_url,
                        'final_url': chain.final_url,
                    },
                )
                self._evidence_collection.add_record(record)

        # Add evidence for mixed redirect types if detected
        # (In production, this would check actual status codes)

    def _add_summary_evidence(self, analysis: RedirectAnalysis) -> None:
        """Add summary evidence for redirect analysis.

        Args:
            analysis: The completed analysis object
        """
        # Calculate redirect percentage
        redirect_percentage = 0
        if analysis.total_pages > 0:
            redirect_percentage = round(
                analysis.pages_with_redirects / analysis.total_pages * 100, 1
            )

        record = EvidenceRecord(
            component_id='redirect_analyzer',
            finding='redirect_summary',
            evidence_string=f'{analysis.total_chains} chains, {analysis.total_hops} total hops, {analysis.total_time_wasted_ms}ms wasted',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Redirect Chain Analysis',
            source_type=EvidenceSourceType.CALCULATION,
            source_location='aggregate',
            measured_value={
                'total_chains': analysis.total_chains,
                'total_hops': analysis.total_hops,
                'total_time_wasted_ms': analysis.total_time_wasted_ms,
                'pages_with_redirects': analysis.pages_with_redirects,
                'redirect_percentage': redirect_percentage,
                'chains_by_length': {
                    '1_hop': analysis.chains_1_hop,
                    '2_hops': analysis.chains_2_hops,
                    '3_plus_hops': analysis.chains_3_plus_hops,
                },
                'max_chain_length': analysis.max_chain_length,
                'avg_hops_per_chain': analysis.avg_hops_per_chain,
            },
            ai_generated=False,
            reasoning='Summary of redirect chain analysis',
            input_summary={
                'ms_per_redirect': self.ms_per_redirect,
                'long_chain_threshold': self.long_chain_threshold,
                'time_formula': 'hop_count * ms_per_redirect',
            },
        )
        self._evidence_collection.add_record(record)

        # Add evidence for redirect percentage if significant
        if redirect_percentage > HIGH_REDIRECT_PERCENTAGE_THRESHOLD:
            record = EvidenceRecord(
                component_id='redirect_analyzer',
                finding='high_redirect_percentage',
                evidence_string=f'{redirect_percentage}% of pages involve redirects',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Redirect Chain Analysis',
                source_type=EvidenceSourceType.CALCULATION,
                source_location='aggregate',
                measured_value={
                    'percentage': redirect_percentage,
                    'threshold': 10,
                },
                ai_generated=False,
                reasoning='High percentage of pages with redirects impacts performance',
            )
            self._evidence_collection.add_record(record)
