"""
Browser Performance Metrics Collection.

Implements Critical Gap #2: JavaScript rendering metrics (FCP, CLS, LCP, etc.)

This module provides real browser-based performance metric collection using:
- Performance API (PerformanceObserver, performance.getEntriesByType)
- Layout Instability API (for CLS)
- Largest Contentful Paint API
- First Contentful Paint timing

Unlike static HTML analysis, this captures actual runtime metrics.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# JavaScript to inject for performance metric collection
PERFORMANCE_OBSERVER_SCRIPT = """
() => {
    // Initialize metrics storage
    window.__perfMetrics = window.__perfMetrics || {
        fcp: null,
        lcp: null,
        cls: 0,
        clsEntries: [],
        lcpElement: null,
        ttfb: null,
        domContentLoaded: null,
        load: null,
        resourceTimings: [],
        longTasks: [],
        layoutShifts: [],
        firstInput: null,
        errors: []
    };

    try {
        // Get navigation timing
        const navTiming = performance.getEntriesByType('navigation')[0];
        if (navTiming) {
            window.__perfMetrics.ttfb = navTiming.responseStart;
            window.__perfMetrics.domContentLoaded = navTiming.domContentLoadedEventEnd;
            window.__perfMetrics.load = navTiming.loadEventEnd;
        }

        // Get paint timings (FCP)
        const paintEntries = performance.getEntriesByType('paint');
        for (const entry of paintEntries) {
            if (entry.name === 'first-contentful-paint') {
                window.__perfMetrics.fcp = entry.startTime;
            }
        }

        // Observe LCP
        if ('PerformanceObserver' in window) {
            try {
                const lcpObserver = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    const lastEntry = entries[entries.length - 1];
                    if (lastEntry) {
                        window.__perfMetrics.lcp = lastEntry.startTime;
                        window.__perfMetrics.lcpElement = lastEntry.element ?
                            lastEntry.element.tagName + (lastEntry.element.id ? '#' + lastEntry.element.id : '') : null;
                    }
                });
                lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });
            } catch (e) {
                window.__perfMetrics.errors.push('LCP observer: ' + e.message);
            }

            // Observe CLS
            try {
                const clsObserver = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        if (!entry.hadRecentInput) {
                            window.__perfMetrics.cls += entry.value;
                            window.__perfMetrics.layoutShifts.push({
                                value: entry.value,
                                startTime: entry.startTime,
                                sources: entry.sources ? entry.sources.map(s => ({
                                    node: s.node ? s.node.tagName : null,
                                    previousRect: s.previousRect,
                                    currentRect: s.currentRect
                                })) : []
                            });
                        }
                    }
                });
                clsObserver.observe({ type: 'layout-shift', buffered: true });
            } catch (e) {
                window.__perfMetrics.errors.push('CLS observer: ' + e.message);
            }

            // Observe Long Tasks (for INP estimation)
            try {
                const longTaskObserver = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        window.__perfMetrics.longTasks.push({
                            duration: entry.duration,
                            startTime: entry.startTime,
                            name: entry.name
                        });
                    }
                });
                longTaskObserver.observe({ type: 'longtask', buffered: true });
            } catch (e) {
                window.__perfMetrics.errors.push('Long task observer: ' + e.message);
            }

            // Observe First Input (for FID)
            try {
                const fidObserver = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    if (entries.length > 0) {
                        window.__perfMetrics.firstInput = {
                            delay: entries[0].processingStart - entries[0].startTime,
                            startTime: entries[0].startTime,
                            name: entries[0].name
                        };
                    }
                });
                fidObserver.observe({ type: 'first-input', buffered: true });
            } catch (e) {
                window.__perfMetrics.errors.push('FID observer: ' + e.message);
            }
        }

        // Get resource timings (sample of largest resources)
        const resources = performance.getEntriesByType('resource');
        const sortedResources = resources
            .filter(r => r.transferSize > 0)
            .sort((a, b) => b.transferSize - a.transferSize)
            .slice(0, 10);

        window.__perfMetrics.resourceTimings = sortedResources.map(r => ({
            name: r.name,
            type: r.initiatorType,
            duration: r.duration,
            transferSize: r.transferSize,
            startTime: r.startTime
        }));

    } catch (e) {
        window.__perfMetrics.errors.push('Setup error: ' + e.message);
    }

    return true;
}
"""

# Script to retrieve collected metrics
GET_METRICS_SCRIPT = """
() => {
    return window.__perfMetrics || null;
}
"""


@dataclass
class LayoutShiftEntry:
    """Individual layout shift entry."""
    value: float
    start_time: float
    sources: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class LongTaskEntry:
    """Long task entry."""
    duration: float
    start_time: float
    name: str = ""


@dataclass
class ResourceTiming:
    """Resource timing entry."""
    name: str
    type: str
    duration: float
    transfer_size: int
    start_time: float


@dataclass
class BrowserPerformanceMetrics:
    """
    Complete browser performance metrics.

    Contains actual measurements from the browser's Performance API,
    not estimates from static HTML analysis.
    """
    # Core Web Vitals
    fcp: Optional[float] = None  # First Contentful Paint (ms)
    lcp: Optional[float] = None  # Largest Contentful Paint (ms)
    cls: float = 0.0  # Cumulative Layout Shift (score)
    fid: Optional[float] = None  # First Input Delay (ms)

    # Navigation timing
    ttfb: Optional[float] = None  # Time to First Byte (ms)
    dom_content_loaded: Optional[float] = None  # DOMContentLoaded (ms)
    load: Optional[float] = None  # Load event (ms)

    # LCP element info
    lcp_element: Optional[str] = None  # Tag#id of LCP element

    # Layout shifts
    layout_shifts: List[LayoutShiftEntry] = field(default_factory=list)

    # Long tasks (blocking)
    long_tasks: List[LongTaskEntry] = field(default_factory=list)
    total_blocking_time: float = 0.0  # Sum of long task time over 50ms

    # Resource timing (top 10 by size)
    resource_timings: List[ResourceTiming] = field(default_factory=list)

    # Collection metadata
    timestamp: Optional[datetime] = None
    url: str = ""
    errors: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        # Calculate TBT from long tasks
        if self.long_tasks:
            self.total_blocking_time = sum(
                max(0, task.duration - 50) for task in self.long_tasks
            )

    def get_cwv_status(self, thresholds: Optional[Dict[str, Dict[str, float]]] = None) -> Dict[str, str]:
        """
        Get Core Web Vitals status (good/needs-improvement/poor).

        Uses configurable thresholds from AnalysisThresholds or defaults to Google's values:
        - LCP: good < 2.5s, poor > 4.0s
        - FID: good < 100ms, poor > 300ms
        - CLS: good < 0.1, poor > 0.25

        Args:
            thresholds: Optional custom thresholds dict. If None, uses config or Google defaults.
                        Format: {'lcp': {'good': 2500, 'poor': 4000}, ...}
        """
        # Get thresholds from config if not provided
        if thresholds is None:
            thresholds = self._get_config_thresholds()

        status = {}

        # LCP status (thresholds in ms)
        if self.lcp is not None:
            lcp_good = thresholds.get('lcp', {}).get('good', 2500)
            lcp_poor = thresholds.get('lcp', {}).get('poor', 4000)
            if self.lcp <= lcp_good:
                status['lcp'] = 'good'
            elif self.lcp <= lcp_poor:
                status['lcp'] = 'needs-improvement'
            else:
                status['lcp'] = 'poor'
        else:
            status['lcp'] = 'unknown'

        # FID status
        if self.fid is not None:
            fid_good = thresholds.get('fid', {}).get('good', 100)
            fid_poor = thresholds.get('fid', {}).get('poor', 300)
            if self.fid <= fid_good:
                status['fid'] = 'good'
            elif self.fid <= fid_poor:
                status['fid'] = 'needs-improvement'
            else:
                status['fid'] = 'poor'
        else:
            status['fid'] = 'unknown'

        # CLS status
        cls_good = thresholds.get('cls', {}).get('good', 0.1)
        cls_poor = thresholds.get('cls', {}).get('poor', 0.25)
        if self.cls <= cls_good:
            status['cls'] = 'good'
        elif self.cls <= cls_poor:
            status['cls'] = 'needs-improvement'
        else:
            status['cls'] = 'poor'

        # Overall status (worst of the three)
        statuses = [v for v in status.values() if v != 'unknown']
        if 'poor' in statuses:
            status['overall'] = 'poor'
        elif 'needs-improvement' in statuses:
            status['overall'] = 'needs-improvement'
        elif statuses:
            status['overall'] = 'good'
        else:
            status['overall'] = 'unknown'

        return status

    def _get_config_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Get CWV thresholds from AnalysisThresholds config."""
        try:
            from seo.config import AnalysisThresholds
            config = AnalysisThresholds.from_env()
            return {
                'lcp': {'good': config.lcp_good, 'poor': config.lcp_poor, 'unit': 'ms'},
                'fcp': {'good': config.fcp_good, 'poor': config.fcp_poor, 'unit': 'ms'},
                'fid': {'good': config.fid_good, 'poor': config.fid_poor, 'unit': 'ms'},
                'cls': {'good': config.cls_good, 'poor': config.cls_poor, 'unit': 'score'},
                'tbt': {'good': config.tbt_good, 'poor': config.tbt_poor, 'unit': 'ms'},
                'ttfb': {'good': 800, 'poor': 1800, 'unit': 'ms'},  # Not in config yet
            }
        except Exception:
            # Fall back to Google defaults
            return {
                'lcp': {'good': 2500, 'poor': 4000, 'unit': 'ms'},
                'fcp': {'good': 1800, 'poor': 3000, 'unit': 'ms'},
                'fid': {'good': 100, 'poor': 300, 'unit': 'ms'},
                'cls': {'good': 0.1, 'poor': 0.25, 'unit': 'score'},
                'tbt': {'good': 200, 'poor': 600, 'unit': 'ms'},
                'ttfb': {'good': 800, 'poor': 1800, 'unit': 'ms'},
            }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'fcp': self.fcp,
            'lcp': self.lcp,
            'cls': self.cls,
            'fid': self.fid,
            'ttfb': self.ttfb,
            'dom_content_loaded': self.dom_content_loaded,
            'load': self.load,
            'lcp_element': self.lcp_element,
            'total_blocking_time': self.total_blocking_time,
            'long_task_count': len(self.long_tasks),
            'layout_shift_count': len(self.layout_shifts),
            'cwv_status': self.get_cwv_status(),
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'url': self.url,
            'errors': self.errors,
        }

    def to_evidence_dict(self) -> Dict[str, Any]:
        """Convert to EvidenceRecord-compatible dict."""
        status = self.get_cwv_status()
        severity = 'info'
        if status.get('overall') == 'poor':
            severity = 'critical'
        elif status.get('overall') == 'needs-improvement':
            severity = 'warning'

        return {
            'component_id': 'browser_performance',
            'finding': f"cwv_status:{status.get('overall', 'unknown')}",
            'evidence_string': f"LCP={self.lcp}ms, CLS={self.cls:.3f}, FID={self.fid}ms",
            'confidence': 'High',
            'source': 'browser_performance_api',
            'source_location': self.url,
            'measured_value': self.to_dict(),
            'severity': severity,
        }

    def to_evidence_records(self) -> List[Any]:
        """Create EvidenceRecord objects for all CWV metrics.

        Returns a list of EvidenceRecord objects, one for each Core Web Vital
        and additional performance metric. Uses the factory method for proper
        integration with the evidence system.

        Thresholds are loaded from AnalysisThresholds config, allowing users
        to customize CWV thresholds via environment variables or config.

        Returns:
            List of EvidenceRecord objects
        """
        # Import here to avoid circular dependency
        from seo.models import EvidenceRecord

        records = []

        # Get thresholds from config
        thresholds = self._get_config_thresholds()
        status = self.get_cwv_status(thresholds)

        # LCP
        if self.lcp is not None:
            records.append(EvidenceRecord.from_browser_performance(
                url=self.url,
                metric_name='lcp',
                metric_value=self.lcp,
                status=status.get('lcp', 'unknown'),
                thresholds=thresholds['lcp'],
                additional_data={'lcp_element': self.lcp_element},
            ))

        # FCP
        if self.fcp is not None:
            fcp_thresh = thresholds.get('fcp', {'good': 1800, 'poor': 3000})
            fcp_status = 'good' if self.fcp <= fcp_thresh['good'] else (
                'poor' if self.fcp > fcp_thresh['poor'] else 'needs-improvement'
            )
            records.append(EvidenceRecord.from_browser_performance(
                url=self.url,
                metric_name='fcp',
                metric_value=self.fcp,
                status=fcp_status,
                thresholds=thresholds.get('fcp', {}),
            ))

        # CLS
        records.append(EvidenceRecord.from_browser_performance(
            url=self.url,
            metric_name='cls',
            metric_value=self.cls,
            status=status.get('cls', 'unknown'),
            thresholds=thresholds['cls'],
            additional_data={'layout_shift_count': len(self.layout_shifts)},
        ))

        # FID (if available)
        if self.fid is not None:
            records.append(EvidenceRecord.from_browser_performance(
                url=self.url,
                metric_name='fid',
                metric_value=self.fid,
                status=status.get('fid', 'unknown'),
                thresholds=thresholds['fid'],
            ))

        # TTFB
        if self.ttfb is not None:
            ttfb_thresh = thresholds.get('ttfb', {'good': 800, 'poor': 1800})
            ttfb_status = 'good' if self.ttfb <= ttfb_thresh['good'] else (
                'poor' if self.ttfb > ttfb_thresh['poor'] else 'needs-improvement'
            )
            records.append(EvidenceRecord.from_browser_performance(
                url=self.url,
                metric_name='ttfb',
                metric_value=self.ttfb,
                status=ttfb_status,
                thresholds=thresholds.get('ttfb', {}),
            ))

        # TBT (Total Blocking Time)
        if self.total_blocking_time > 0:
            tbt_thresh = thresholds.get('tbt', {'good': 200, 'poor': 600})
            tbt_status = 'good' if self.total_blocking_time <= tbt_thresh['good'] else (
                'poor' if self.total_blocking_time > tbt_thresh['poor'] else 'needs-improvement'
            )
            records.append(EvidenceRecord.from_browser_performance(
                url=self.url,
                metric_name='tbt',
                metric_value=self.total_blocking_time,
                status=tbt_status,
                thresholds=thresholds['tbt'],
                additional_data={'long_task_count': len(self.long_tasks)},
            ))

        return records


async def inject_performance_observers(page) -> bool:
    """
    Inject performance observers into a page.

    Call this early in the page lifecycle to capture all metrics.
    Works with both Playwright pages and UndetectedBrowserPage.

    Args:
        page: Browser page instance

    Returns:
        True if injection succeeded
    """
    try:
        if hasattr(page, 'evaluate'):
            await page.evaluate(PERFORMANCE_OBSERVER_SCRIPT)
        else:
            # Fallback for different page interfaces
            await page.evaluate(PERFORMANCE_OBSERVER_SCRIPT)
        logger.debug("Performance observers injected")
        return True
    except Exception as e:
        logger.warning(f"Failed to inject performance observers: {e}")
        return False


async def collect_performance_metrics(page, url: str = "") -> BrowserPerformanceMetrics:
    """
    Collect performance metrics from a page.

    Call this after the page has loaded and settled.

    Args:
        page: Browser page instance
        url: URL being measured (for reference)

    Returns:
        BrowserPerformanceMetrics with collected data
    """
    metrics = BrowserPerformanceMetrics(url=url)

    try:
        raw_metrics = await page.evaluate(GET_METRICS_SCRIPT)

        if not raw_metrics:
            metrics.errors.append("No metrics collected - observers may not have been injected")
            return metrics

        # Parse core metrics
        metrics.fcp = raw_metrics.get('fcp')
        metrics.lcp = raw_metrics.get('lcp')
        metrics.cls = raw_metrics.get('cls', 0.0)
        metrics.ttfb = raw_metrics.get('ttfb')
        metrics.dom_content_loaded = raw_metrics.get('domContentLoaded')
        metrics.load = raw_metrics.get('load')
        metrics.lcp_element = raw_metrics.get('lcpElement')

        # Parse FID
        first_input = raw_metrics.get('firstInput')
        if first_input:
            metrics.fid = first_input.get('delay')

        # Parse layout shifts
        for shift in raw_metrics.get('layoutShifts', []):
            metrics.layout_shifts.append(LayoutShiftEntry(
                value=shift.get('value', 0),
                start_time=shift.get('startTime', 0),
                sources=shift.get('sources', [])
            ))

        # Parse long tasks
        for task in raw_metrics.get('longTasks', []):
            metrics.long_tasks.append(LongTaskEntry(
                duration=task.get('duration', 0),
                start_time=task.get('startTime', 0),
                name=task.get('name', '')
            ))

        # Parse resource timings
        for resource in raw_metrics.get('resourceTimings', []):
            metrics.resource_timings.append(ResourceTiming(
                name=resource.get('name', ''),
                type=resource.get('type', ''),
                duration=resource.get('duration', 0),
                transfer_size=resource.get('transferSize', 0),
                start_time=resource.get('startTime', 0)
            ))

        # Collect errors
        metrics.errors = raw_metrics.get('errors', [])

        # Recalculate TBT
        metrics.total_blocking_time = sum(
            max(0, task.duration - 50) for task in metrics.long_tasks
        )

        logger.info(f"Collected performance metrics: LCP={metrics.lcp}ms, CLS={metrics.cls:.3f}")

    except Exception as e:
        metrics.errors.append(f"Collection error: {str(e)}")
        logger.warning(f"Error collecting performance metrics: {e}")

    return metrics


async def measure_page_performance(page, url: str, wait_time: float = 3.0) -> BrowserPerformanceMetrics:
    """
    Complete workflow: inject observers, wait for page to settle, collect metrics.

    Args:
        page: Browser page instance
        url: URL being measured
        wait_time: Seconds to wait for metrics to stabilize

    Returns:
        BrowserPerformanceMetrics with all collected data
    """
    # Inject observers
    await inject_performance_observers(page)

    # Wait for metrics to stabilize (LCP can update for a few seconds)
    await asyncio.sleep(wait_time)

    # Collect metrics
    return await collect_performance_metrics(page, url)
