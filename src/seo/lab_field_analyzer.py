"""Lab vs Field performance analyzer comparing Lighthouse and CrUX data."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from seo.models import (
    PageMetadata,
    LabFieldComparison,
    MetricComparison,
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)
from seo.config import AnalysisThresholds, default_thresholds


class LabFieldAnalyzer:
    """Compares Lighthouse (lab) metrics with CrUX (field) data.

    Provides complete Core Web Vitals comparison:
    - LCP: Largest Contentful Paint
    - CLS: Cumulative Layout Shift
    - TBT vs FID: Total Blocking Time (lab) vs First Input Delay (field)
    """

    # Source labels for evidence provenance
    LAB_SOURCE = "Lighthouse"
    FIELD_SOURCE = "CrUX"

    def __init__(self, thresholds: Optional[AnalysisThresholds] = None):
        """Initialize analyzer with configurable thresholds.

        Args:
            thresholds: Analysis thresholds configuration
        """
        self.thresholds = thresholds or default_thresholds
        self._evidence_collection: Optional[EvidenceCollection] = None

    @property
    def lcp_good(self) -> float:
        """LCP threshold for 'good' status (ms)."""
        return self.thresholds.lcp_good

    @property
    def lcp_poor(self) -> float:
        """LCP threshold for 'poor' status (ms)."""
        return self.thresholds.lcp_poor

    @property
    def cls_good(self) -> float:
        """CLS threshold for 'good' status."""
        return self.thresholds.cls_good

    @property
    def cls_poor(self) -> float:
        """CLS threshold for 'poor' status."""
        return self.thresholds.cls_poor

    @property
    def tbt_good(self) -> int:
        """TBT threshold for 'good' status (ms)."""
        return self.thresholds.tbt_good

    @property
    def tbt_poor(self) -> int:
        """TBT threshold for 'poor' status (ms)."""
        return self.thresholds.tbt_poor

    @property
    def fid_good(self) -> int:
        """FID threshold for 'good' status (ms)."""
        return self.thresholds.fid_good

    @property
    def fid_poor(self) -> int:
        """FID threshold for 'poor' status (ms)."""
        return self.thresholds.fid_poor

    @property
    def significant_gap(self) -> float:
        """Percentage difference considered significant."""
        return self.thresholds.lab_field_significant_gap

    def analyze(self, pages: Dict[str, PageMetadata]) -> Tuple[LabFieldComparison, Dict]:
        """Compare lab and field performance metrics.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Tuple of (LabFieldComparison, evidence_dict)
        """
        self._evidence_collection = EvidenceCollection(
            finding='lab_field_comparison',
            component_id='lab_field_analyzer',
        )

        if not pages:
            return LabFieldComparison(), self._evidence_collection.to_dict()

        comparison = LabFieldComparison(total_pages=len(pages))

        # Collect metrics from pages with both lab and field data
        lcp_lab_values: List[float] = []
        lcp_field_values: List[float] = []
        cls_lab_values: List[float] = []
        cls_field_values: List[float] = []
        tbt_values: List[float] = []
        fid_values: List[float] = []

        lab_better_count = 0
        field_better_count = 0
        match_count = 0

        for url, page in pages.items():
            has_lab_lcp = page.lighthouse_lcp is not None
            has_field_lcp = page.crux_lcp_percentile is not None

            if has_lab_lcp and has_field_lcp:
                comparison.pages_with_both += 1

                # LCP comparison
                lab_lcp = page.lighthouse_lcp  # ms
                field_lcp = page.crux_lcp_percentile  # ms

                lcp_lab_values.append(lab_lcp)
                lcp_field_values.append(field_lcp)

                lab_status = self._get_lcp_status(lab_lcp)
                field_status = self._normalize_crux_category(
                    page.crux_lcp_category
                ) or self._get_lcp_status(field_lcp)

                if lab_status != field_status:
                    comparison.status_mismatches.append({
                        'url': url,
                        'metric': 'LCP',
                        'lab_value': lab_lcp,
                        'lab_status': lab_status,
                        'field_value': field_lcp,
                        'field_status': field_status
                    })
                    # Add evidence for status mismatch
                    self._add_mismatch_evidence(
                        url=url,
                        metric='LCP',
                        lab_value=lab_lcp,
                        lab_status=lab_status,
                        field_value=field_lcp,
                        field_status=field_status,
                    )

                # Calculate gap
                if field_lcp > 0:
                    gap = ((lab_lcp - field_lcp) / field_lcp) * 100
                    if abs(gap) > self.significant_gap:
                        comparison.pages_with_gaps.append({
                            'url': url,
                            'metric': 'LCP',
                            'lab_value': lab_lcp,
                            'field_value': field_lcp,
                            'gap_percentage': round(gap, 1)
                        })
                        # Add evidence for significant gap
                        self._add_gap_evidence(
                            url=url,
                            metric='LCP',
                            lab_value=lab_lcp,
                            field_value=field_lcp,
                            gap_percentage=round(gap, 1),
                        )

                    if gap < -self.significant_gap:
                        lab_better_count += 1
                    elif gap > self.significant_gap:
                        field_better_count += 1
                    else:
                        match_count += 1

            # CLS comparison
            if page.lighthouse_cls is not None and page.crux_cls_percentile is not None:
                cls_lab_values.append(page.lighthouse_cls)
                cls_field_values.append(page.crux_cls_percentile)

            # TBT (lab) vs FID (field) - interactivity comparison
            if page.lighthouse_tbt is not None:
                tbt_values.append(page.lighthouse_tbt)
            if page.crux_fid_percentile is not None:
                fid_values.append(page.crux_fid_percentile)

        comparison.overall_lab_better = lab_better_count
        comparison.overall_field_better = field_better_count
        comparison.overall_match = match_count

        # Calculate aggregate LCP comparison
        if lcp_lab_values and lcp_field_values:
            avg_lab_lcp = sum(lcp_lab_values) / len(lcp_lab_values)
            avg_field_lcp = sum(lcp_field_values) / len(lcp_field_values)

            comparison.lcp_comparison = MetricComparison(
                metric_name="Largest Contentful Paint",
                lab_value=round(avg_lab_lcp, 0),
                field_value=round(avg_field_lcp, 0),
                lab_status=self._get_lcp_status(avg_lab_lcp),
                field_status=self._get_lcp_status(avg_field_lcp),
                difference_percentage=round(
                    ((avg_lab_lcp - avg_field_lcp) / avg_field_lcp * 100)
                    if avg_field_lcp > 0 else 0, 1
                ),
                status_match=self._get_lcp_status(avg_lab_lcp) == self._get_lcp_status(avg_field_lcp)
            )

        # Calculate aggregate CLS comparison
        if cls_lab_values and cls_field_values:
            avg_lab_cls = sum(cls_lab_values) / len(cls_lab_values)
            avg_field_cls = sum(cls_field_values) / len(cls_field_values)

            comparison.cls_comparison = MetricComparison(
                metric_name="Cumulative Layout Shift",
                lab_value=round(avg_lab_cls, 3),
                field_value=round(avg_field_cls, 3),
                lab_status=self._get_cls_status(avg_lab_cls),
                field_status=self._get_cls_status(avg_field_cls),
                difference_percentage=round(
                    ((avg_lab_cls - avg_field_cls) / avg_field_cls * 100)
                    if avg_field_cls > 0 else 0, 1
                ),
                status_match=self._get_cls_status(avg_lab_cls) == self._get_cls_status(avg_field_cls)
            )

        # Calculate TBT vs FID comparison (interactivity)
        if tbt_values and fid_values:
            avg_tbt = sum(tbt_values) / len(tbt_values)
            avg_fid = sum(fid_values) / len(fid_values)

            comparison.fid_inp_comparison = MetricComparison(
                metric_name="Interactivity (TBT vs FID)",
                lab_value=round(avg_tbt, 0),
                field_value=round(avg_fid, 0),
                lab_status=self._get_tbt_status(avg_tbt),
                field_status=self._get_fid_status(avg_fid),
                difference_percentage=round(
                    ((avg_tbt - avg_fid) / avg_fid * 100)
                    if avg_fid > 0 else 0, 1
                ),
                status_match=self._get_tbt_status(avg_tbt) == self._get_fid_status(avg_fid),
                insight="TBT (lab) measures main thread blocking; FID (field) measures actual input delay"
            )

        # Determine lab tendency
        if lab_better_count > field_better_count * 1.5:
            comparison.lab_tendency = "optimistic"
        elif field_better_count > lab_better_count * 1.5:
            comparison.lab_tendency = "pessimistic"
        else:
            comparison.lab_tendency = "neutral"

        # Generate insights
        comparison.insights = self._generate_insights(comparison)

        # Add aggregate evidence for the comparison
        self._add_aggregate_evidence(comparison)

        return comparison, self._evidence_collection.to_dict()

    def _get_lcp_status(self, value: float) -> str:
        """Determine LCP status."""
        if value <= self.lcp_good:
            return "good"
        elif value <= self.lcp_poor:
            return "needs-improvement"
        return "poor"

    def _get_cls_status(self, value: float) -> str:
        """Determine CLS status."""
        if value <= self.cls_good:
            return "good"
        elif value <= self.cls_poor:
            return "needs-improvement"
        return "poor"

    def _get_tbt_status(self, value: float) -> str:
        """Determine TBT status."""
        if value <= self.tbt_good:
            return "good"
        elif value <= self.tbt_poor:
            return "needs-improvement"
        return "poor"

    def _get_fid_status(self, value: float) -> str:
        """Determine FID status."""
        if value <= self.fid_good:
            return "good"
        elif value <= self.fid_poor:
            return "needs-improvement"
        return "poor"

    def _normalize_crux_category(self, category: Optional[str]) -> Optional[str]:
        """Normalize CrUX category to standard status."""
        if not category:
            return None
        category = category.upper()
        if category == 'FAST':
            return 'good'
        elif category == 'AVERAGE':
            return 'needs-improvement'
        elif category == 'SLOW':
            return 'poor'
        return None

    def _generate_insights(self, comparison: LabFieldComparison) -> List[str]:
        """Generate insights from lab/field comparison."""
        insights = []

        if comparison.pages_with_both == 0:
            insights.append(
                "No pages have both Lighthouse and CrUX data. "
                "Run Lighthouse and ensure sufficient traffic for CrUX data."
            )
            return insights

        if comparison.lab_tendency == "optimistic":
            insights.append(
                "Lab tests show better performance than real users experience. "
                "Real-world factors like network variability and device diversity "
                "may be impacting actual performance."
            )
        elif comparison.lab_tendency == "pessimistic":
            insights.append(
                "Real users experience better performance than lab tests predict. "
                "This could indicate effective caching or CDN performance in production."
            )

        if len(comparison.status_mismatches) > 0:
            insights.append(
                f"{len(comparison.status_mismatches)} pages show different status "
                "between lab and field. Investigate these pages for optimization opportunities."
            )

        if comparison.lcp_comparison and not comparison.lcp_comparison.status_match:
            insights.append(
                f"LCP status differs: Lab shows '{comparison.lcp_comparison.lab_status}' "
                f"but field shows '{comparison.lcp_comparison.field_status}'."
            )

        if comparison.fid_inp_comparison and not comparison.fid_inp_comparison.status_match:
            insights.append(
                f"Interactivity status differs: TBT (lab) is '{comparison.fid_inp_comparison.lab_status}' "
                f"but FID (field) is '{comparison.fid_inp_comparison.field_status}'. "
                "This may indicate JavaScript execution issues not captured in lab conditions."
            )

        return insights

    def _add_mismatch_evidence(
        self,
        url: str,
        metric: str,
        lab_value: float,
        lab_status: str,
        field_value: float,
        field_status: str,
    ) -> None:
        """Add evidence for a status mismatch between lab and field data.

        Args:
            url: Page URL
            metric: Metric name (LCP, CLS, etc.)
            lab_value: Lab measurement value
            lab_status: Lab status (good/needs-improvement/poor)
            field_value: Field measurement value
            field_status: Field status (good/needs-improvement/poor)
        """
        record = EvidenceRecord(
            component_id='lab_field_analyzer',
            finding=f'{metric.lower()}_status_mismatch',
            evidence_string=f'{metric} status mismatch: {self.LAB_SOURCE} shows {lab_status}, {self.FIELD_SOURCE} shows {field_status}',
            confidence=ConfidenceLevel.HIGH,  # Direct measurement comparison
            timestamp=datetime.now(),
            source=f'{self.LAB_SOURCE} vs {self.FIELD_SOURCE}',
            source_type=EvidenceSourceType.MEASUREMENT,
            source_location=url,
            measured_value={
                'lab': {'value': lab_value, 'status': lab_status, 'source': self.LAB_SOURCE},
                'field': {'value': field_value, 'status': field_status, 'source': self.FIELD_SOURCE},
            },
            ai_generated=False,
            reasoning=f'Lab ({self.LAB_SOURCE}) and field ({self.FIELD_SOURCE}) data show different status for {metric}',
        )
        self._evidence_collection.add_record(record)

    def _add_gap_evidence(
        self,
        url: str,
        metric: str,
        lab_value: float,
        field_value: float,
        gap_percentage: float,
    ) -> None:
        """Add evidence for a significant gap between lab and field values.

        Args:
            url: Page URL
            metric: Metric name (LCP, CLS, etc.)
            lab_value: Lab measurement value
            field_value: Field measurement value
            gap_percentage: Gap as percentage
        """
        direction = "faster" if gap_percentage < 0 else "slower"
        record = EvidenceRecord(
            component_id='lab_field_analyzer',
            finding=f'{metric.lower()}_significant_gap',
            evidence_string=f'{metric} gap: {self.LAB_SOURCE} is {abs(gap_percentage):.1f}% {direction} than {self.FIELD_SOURCE}',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source=f'{self.LAB_SOURCE} vs {self.FIELD_SOURCE}',
            source_type=EvidenceSourceType.CALCULATION,
            source_location=url,
            measured_value={
                'lab': {'value': lab_value, 'source': self.LAB_SOURCE},
                'field': {'value': field_value, 'source': self.FIELD_SOURCE},
                'gap_percentage': gap_percentage,
                'threshold': self.significant_gap,
            },
            ai_generated=False,
            reasoning=f'Gap exceeds threshold of {self.significant_gap}%',
            input_summary={
                'formula': '((lab_value - field_value) / field_value) * 100',
                'lab_source': self.LAB_SOURCE,
                'field_source': self.FIELD_SOURCE,
            },
        )
        self._evidence_collection.add_record(record)

    def _add_aggregate_evidence(self, comparison: LabFieldComparison) -> None:
        """Add aggregate evidence for the overall lab/field comparison.

        Args:
            comparison: The completed LabFieldComparison
        """
        record = EvidenceRecord(
            component_id='lab_field_analyzer',
            finding='lab_field_summary',
            evidence_string=f'Lab tendency: {comparison.lab_tendency}; {len(comparison.status_mismatches)} mismatches, {len(comparison.pages_with_gaps)} gaps',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source=f'{self.LAB_SOURCE} vs {self.FIELD_SOURCE}',
            source_type=EvidenceSourceType.CALCULATION,
            source_location='aggregate',
            measured_value={
                'total_pages': comparison.total_pages,
                'pages_with_both': comparison.pages_with_both,
                'lab_tendency': comparison.lab_tendency,
                'status_mismatch_count': len(comparison.status_mismatches),
                'gap_count': len(comparison.pages_with_gaps),
                'overall_lab_better': comparison.overall_lab_better,
                'overall_field_better': comparison.overall_field_better,
                'overall_match': comparison.overall_match,
            },
            ai_generated=False,
            reasoning='Aggregate comparison of lab (Lighthouse) vs field (CrUX) performance data',
            input_summary={
                'lab_source': self.LAB_SOURCE,
                'field_source': self.FIELD_SOURCE,
                'gap_threshold': f'{self.significant_gap}%',
            },
        )
        self._evidence_collection.add_record(record)
