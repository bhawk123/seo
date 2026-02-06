# SEO Enhancements Implementation Guide

## Document Overview

This document provides complete implementation specifications for enhancing the SEO analyzer. Each item includes:
- **Epic**: Large body of work with business value
- **Feature**: Capability within an epic
- **Story**: User-facing functionality
- **Task**: Specific implementation work with code specifications

---

# Epic 1: Resource & Performance Analysis

**Business Value:** Enable users to understand page weight distribution and identify specific optimization opportunities for faster load times.

## Feature 1.1: Resource Composition Analyzer

### Story 1.1.1: Analyze Page Resource Distribution

**As a** site owner, **I want** to see how page weight is distributed across resource types **so that** I can prioritize optimization efforts.

#### Task 1.1.1.1: Create ResourceAnalysis Data Model

**File:** `src/seo/models.py`

**Add after line 271 (after ComprehensiveSEOReport):**

```python
@dataclass
class ResourceBreakdown:
    """Breakdown of resources for a single page."""
    url: str
    html_bytes: int = 0
    css_bytes: int = 0
    js_bytes: int = 0
    image_bytes: int = 0
    font_bytes: int = 0
    other_bytes: int = 0
    total_bytes: int = 0

    @property
    def css_percentage(self) -> float:
        return (self.css_bytes / self.total_bytes * 100) if self.total_bytes > 0 else 0

    @property
    def js_percentage(self) -> float:
        return (self.js_bytes / self.total_bytes * 100) if self.total_bytes > 0 else 0

    @property
    def image_percentage(self) -> float:
        return (self.image_bytes / self.total_bytes * 100) if self.total_bytes > 0 else 0


@dataclass
class ResourceAnalysis:
    """Site-wide resource analysis results."""

    total_pages: int = 0

    # Aggregate sizes
    total_html_bytes: int = 0
    total_css_bytes: int = 0
    total_js_bytes: int = 0
    total_image_bytes: int = 0
    total_font_bytes: int = 0
    total_other_bytes: int = 0
    total_all_bytes: int = 0

    # Averages
    avg_page_weight_bytes: int = 0
    avg_html_bytes: int = 0
    avg_css_bytes: int = 0
    avg_js_bytes: int = 0
    avg_image_bytes: int = 0

    # Distribution percentages (site-wide)
    html_percentage: float = 0.0
    css_percentage: float = 0.0
    js_percentage: float = 0.0
    image_percentage: float = 0.0
    font_percentage: float = 0.0

    # Issues
    bloated_pages: list = field(default_factory=list)  # Pages > 2MB
    large_js_pages: list = field(default_factory=list)  # JS > 500KB
    large_css_pages: list = field(default_factory=list)  # CSS > 200KB
    large_image_pages: list = field(default_factory=list)  # Images > 1MB

    # Top heaviest pages
    heaviest_pages: list = field(default_factory=list)  # Top 10 by total weight

    # Per-page breakdown
    page_breakdowns: list = field(default_factory=list)

    # Recommendations
    recommendations: list = field(default_factory=list)
```

---

#### Task 1.1.1.2: Create ResourceAnalyzer Class

**File:** `src/seo/resource_analyzer.py` (new file)

```python
"""Resource composition analyzer for page weight optimization."""

from typing import Dict, List
from dataclasses import dataclass

from seo.models import PageMetadata, ResourceAnalysis, ResourceBreakdown


class ResourceAnalyzer:
    """Analyzes page resource composition and identifies optimization opportunities."""

    # Thresholds (bytes)
    BLOATED_PAGE_THRESHOLD = 2 * 1024 * 1024  # 2MB
    LARGE_JS_THRESHOLD = 500 * 1024  # 500KB
    LARGE_CSS_THRESHOLD = 200 * 1024  # 200KB
    LARGE_IMAGE_THRESHOLD = 1024 * 1024  # 1MB

    def analyze(self, pages: Dict[str, PageMetadata]) -> ResourceAnalysis:
        """Analyze resource composition across all pages.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            ResourceAnalysis with site-wide resource metrics
        """
        if not pages:
            return ResourceAnalysis()

        analysis = ResourceAnalysis(total_pages=len(pages))
        page_breakdowns = []

        for url, page in pages.items():
            breakdown = self._analyze_page(url, page)
            page_breakdowns.append(breakdown)

            # Aggregate totals
            analysis.total_html_bytes += breakdown.html_bytes
            analysis.total_css_bytes += breakdown.css_bytes
            analysis.total_js_bytes += breakdown.js_bytes
            analysis.total_image_bytes += breakdown.image_bytes
            analysis.total_font_bytes += breakdown.font_bytes
            analysis.total_other_bytes += breakdown.other_bytes
            analysis.total_all_bytes += breakdown.total_bytes

            # Check for issues
            if breakdown.total_bytes > self.BLOATED_PAGE_THRESHOLD:
                analysis.bloated_pages.append({
                    'url': url,
                    'total_bytes': breakdown.total_bytes,
                    'total_mb': round(breakdown.total_bytes / (1024 * 1024), 2)
                })

            if breakdown.js_bytes > self.LARGE_JS_THRESHOLD:
                analysis.large_js_pages.append({
                    'url': url,
                    'js_bytes': breakdown.js_bytes,
                    'js_kb': round(breakdown.js_bytes / 1024, 1)
                })

            if breakdown.css_bytes > self.LARGE_CSS_THRESHOLD:
                analysis.large_css_pages.append({
                    'url': url,
                    'css_bytes': breakdown.css_bytes,
                    'css_kb': round(breakdown.css_bytes / 1024, 1)
                })

            if breakdown.image_bytes > self.LARGE_IMAGE_THRESHOLD:
                analysis.large_image_pages.append({
                    'url': url,
                    'image_bytes': breakdown.image_bytes,
                    'image_mb': round(breakdown.image_bytes / (1024 * 1024), 2)
                })

        # Calculate averages
        if analysis.total_pages > 0:
            analysis.avg_page_weight_bytes = analysis.total_all_bytes // analysis.total_pages
            analysis.avg_html_bytes = analysis.total_html_bytes // analysis.total_pages
            analysis.avg_css_bytes = analysis.total_css_bytes // analysis.total_pages
            analysis.avg_js_bytes = analysis.total_js_bytes // analysis.total_pages
            analysis.avg_image_bytes = analysis.total_image_bytes // analysis.total_pages

        # Calculate distribution percentages
        if analysis.total_all_bytes > 0:
            analysis.html_percentage = round(
                analysis.total_html_bytes / analysis.total_all_bytes * 100, 1
            )
            analysis.css_percentage = round(
                analysis.total_css_bytes / analysis.total_all_bytes * 100, 1
            )
            analysis.js_percentage = round(
                analysis.total_js_bytes / analysis.total_all_bytes * 100, 1
            )
            analysis.image_percentage = round(
                analysis.total_image_bytes / analysis.total_all_bytes * 100, 1
            )
            analysis.font_percentage = round(
                analysis.total_font_bytes / analysis.total_all_bytes * 100, 1
            )

        # Sort and get top 10 heaviest pages
        page_breakdowns.sort(key=lambda x: x.total_bytes, reverse=True)
        analysis.heaviest_pages = [
            {
                'url': b.url,
                'total_bytes': b.total_bytes,
                'total_kb': round(b.total_bytes / 1024, 1),
                'html_kb': round(b.html_bytes / 1024, 1),
                'css_kb': round(b.css_bytes / 1024, 1),
                'js_kb': round(b.js_bytes / 1024, 1),
                'image_kb': round(b.image_bytes / 1024, 1),
            }
            for b in page_breakdowns[:10]
        ]

        analysis.page_breakdowns = page_breakdowns

        # Generate recommendations
        analysis.recommendations = self._generate_recommendations(analysis)

        return analysis

    def _analyze_page(self, url: str, page: PageMetadata) -> ResourceBreakdown:
        """Analyze resource breakdown for a single page."""
        breakdown = ResourceBreakdown(
            url=url,
            html_bytes=page.html_size_bytes,
            css_bytes=page.css_size_bytes,
            js_bytes=page.js_size_bytes,
            image_bytes=page.image_size_bytes,
            font_bytes=page.font_size_bytes,
        )

        # Calculate other and total
        known_bytes = (
            breakdown.html_bytes +
            breakdown.css_bytes +
            breakdown.js_bytes +
            breakdown.image_bytes +
            breakdown.font_bytes
        )

        if page.total_page_weight_bytes > known_bytes:
            breakdown.other_bytes = page.total_page_weight_bytes - known_bytes

        breakdown.total_bytes = page.total_page_weight_bytes or known_bytes

        return breakdown

    def _generate_recommendations(self, analysis: ResourceAnalysis) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # Image optimization
        if analysis.image_percentage > 50:
            recommendations.append(
                f"Images account for {analysis.image_percentage}% of page weight. "
                "Consider converting to WebP/AVIF format and implementing lazy loading."
            )

        if analysis.large_image_pages:
            recommendations.append(
                f"{len(analysis.large_image_pages)} pages have images exceeding 1MB. "
                "Compress and resize images to appropriate dimensions."
            )

        # JavaScript optimization
        if analysis.js_percentage > 30:
            recommendations.append(
                f"JavaScript accounts for {analysis.js_percentage}% of page weight. "
                "Consider code splitting, tree shaking, and deferring non-critical scripts."
            )

        if analysis.large_js_pages:
            recommendations.append(
                f"{len(analysis.large_js_pages)} pages have JavaScript bundles exceeding 500KB. "
                "Audit for unused code and consider dynamic imports."
            )

        # CSS optimization
        if analysis.large_css_pages:
            recommendations.append(
                f"{len(analysis.large_css_pages)} pages have CSS exceeding 200KB. "
                "Remove unused CSS and consider critical CSS extraction."
            )

        # Overall page weight
        if analysis.bloated_pages:
            recommendations.append(
                f"{len(analysis.bloated_pages)} pages exceed 2MB total weight. "
                "These pages will load slowly on mobile connections."
            )

        avg_kb = analysis.avg_page_weight_bytes / 1024
        if avg_kb > 1500:
            recommendations.append(
                f"Average page weight is {avg_kb:.0f}KB, above the recommended 1.5MB. "
                "Focus on reducing the largest resource categories."
            )

        return recommendations
```

---

#### Task 1.1.1.3: Integrate ResourceAnalyzer into Report Generator

**File:** `src/seo/report_generator.py`

**Add import at top:**
```python
from seo.resource_analyzer import ResourceAnalyzer
```

**Add method to ReportGenerator class:**
```python
def _process_resource_analysis(
    self,
    pages: Dict[str, PageMetadata]
) -> Dict:
    """Process resource composition analysis for report.

    Args:
        pages: Dictionary mapping URLs to PageMetadata

    Returns:
        Dictionary with resource analysis data for template
    """
    analyzer = ResourceAnalyzer()
    analysis = analyzer.analyze(pages)

    return {
        'enabled': True,
        'total_pages': analysis.total_pages,

        # Size summaries (formatted)
        'total_weight_mb': round(analysis.total_all_bytes / (1024 * 1024), 2),
        'avg_weight_kb': round(analysis.avg_page_weight_bytes / 1024, 1),

        # Distribution for pie chart
        'distribution': {
            'HTML': analysis.html_percentage,
            'CSS': analysis.css_percentage,
            'JavaScript': analysis.js_percentage,
            'Images': analysis.image_percentage,
            'Fonts': analysis.font_percentage,
        },

        # Issues
        'bloated_pages': analysis.bloated_pages[:10],
        'bloated_count': len(analysis.bloated_pages),
        'large_js_pages': analysis.large_js_pages[:10],
        'large_js_count': len(analysis.large_js_pages),
        'large_css_pages': analysis.large_css_pages[:10],
        'large_css_count': len(analysis.large_css_pages),
        'large_image_pages': analysis.large_image_pages[:10],
        'large_image_count': len(analysis.large_image_pages),

        # Top heaviest
        'heaviest_pages': analysis.heaviest_pages,

        # Recommendations
        'recommendations': analysis.recommendations,

        # Scores
        'has_issues': (
            len(analysis.bloated_pages) > 0 or
            len(analysis.large_js_pages) > 0 or
            len(analysis.large_css_pages) > 0
        ),
    }
```

---

#### Task 1.1.1.4: Add Resource Analysis Section to HTML Template

**File:** `templates/report.html`

**Add new tab button in navigation (around line 150):**
```html
<button class="tab-btn" data-tab="resources">Resources</button>
```

**Add new tab content section:**
```html
<!-- Resources Tab -->
<div id="resources" class="tab-content">
    {% if resource_analysis.enabled %}
    <div class="section">
        <h2>Resource Composition Analysis</h2>

        <!-- Summary Cards -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{{ resource_analysis.avg_weight_kb|format_number }} KB</div>
                <div class="stat-label">Average Page Weight</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ resource_analysis.total_weight_mb }} MB</div>
                <div class="stat-label">Total Site Weight</div>
            </div>
            <div class="stat-card {% if resource_analysis.bloated_count > 0 %}warning{% endif %}">
                <div class="stat-value">{{ resource_analysis.bloated_count }}</div>
                <div class="stat-label">Bloated Pages (&gt;2MB)</div>
            </div>
            <div class="stat-card {% if resource_analysis.large_js_count > 0 %}warning{% endif %}">
                <div class="stat-value">{{ resource_analysis.large_js_count }}</div>
                <div class="stat-label">Large JS (&gt;500KB)</div>
            </div>
        </div>

        <!-- Resource Distribution Chart -->
        <div class="chart-container" style="max-width: 400px; margin: 2rem auto;">
            <canvas id="resourceDistributionChart"></canvas>
        </div>

        <!-- Heaviest Pages Table -->
        <h3>Top 10 Heaviest Pages</h3>
        <div class="table-responsive">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>URL</th>
                        <th>Total</th>
                        <th>HTML</th>
                        <th>CSS</th>
                        <th>JS</th>
                        <th>Images</th>
                    </tr>
                </thead>
                <tbody>
                    {% for page in resource_analysis.heaviest_pages %}
                    <tr>
                        <td class="url-cell" title="{{ page.url }}">{{ page.url|truncate(50) }}</td>
                        <td>{{ page.total_kb }} KB</td>
                        <td>{{ page.html_kb }} KB</td>
                        <td>{{ page.css_kb }} KB</td>
                        <td>{{ page.js_kb }} KB</td>
                        <td>{{ page.image_kb }} KB</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Recommendations -->
        {% if resource_analysis.recommendations %}
        <h3>Optimization Recommendations</h3>
        <ul class="recommendations-list">
            {% for rec in resource_analysis.recommendations %}
            <li>{{ rec }}</li>
            {% endfor %}
        </ul>
        {% endif %}
    </div>
    {% else %}
    <div class="no-data">
        <p>Resource analysis data not available. Enable resource tracking during crawl.</p>
    </div>
    {% endif %}
</div>
```

**Add Chart.js initialization (in script section):**
```javascript
// Resource Distribution Pie Chart
function initResourceChart() {
    const ctx = document.getElementById('resourceDistributionChart');
    if (!ctx) return;

    const data = {{ resource_analysis.distribution | tojson }};

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(data),
            datasets: [{
                data: Object.values(data),
                backgroundColor: [
                    '#3b82f6',  // HTML - blue
                    '#8b5cf6',  // CSS - purple
                    '#f59e0b',  // JS - amber
                    '#10b981',  // Images - green
                    '#ef4444',  // Fonts - red
                ],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: 'Resource Distribution by Type'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.label + ': ' + context.parsed + '%';
                        }
                    }
                }
            }
        }
    });
}

// Call when resources tab is shown
document.querySelector('[data-tab="resources"]')?.addEventListener('click', function() {
    setTimeout(initResourceChart, 100);
});
```

---

## Feature 1.2: Console Error Reporting

### Story 1.2.1: Surface JavaScript Errors

**As a** developer, **I want** to see JavaScript console errors found during crawling **so that** I can fix runtime issues affecting user experience.

#### Task 1.2.1.1: Create ConsoleErrorAnalysis Data Model

**File:** `src/seo/models.py`

**Add after ResourceAnalysis:**

```python
@dataclass
class ConsoleErrorAnalysis:
    """Analysis of JavaScript console errors and warnings."""

    total_pages: int = 0
    pages_with_errors: int = 0
    pages_with_warnings: int = 0
    error_free_percentage: float = 0.0

    # Error counts by category
    total_errors: int = 0
    total_warnings: int = 0

    # Categorized errors
    errors_by_type: dict = field(default_factory=dict)  # TypeError: 5, ReferenceError: 3, etc.

    # Pages with most errors
    pages_by_error_count: list = field(default_factory=list)  # [(url, error_count, errors), ...]

    # Common error patterns
    common_errors: list = field(default_factory=list)  # Most frequent error messages

    # All errors with URLs
    all_errors: list = field(default_factory=list)  # [{url, error, type}, ...]
```

---

#### Task 1.2.1.2: Create ConsoleErrorAnalyzer Class

**File:** `src/seo/console_analyzer.py` (new file)

```python
"""Console error analyzer for JavaScript health assessment."""

import re
from collections import Counter
from typing import Dict, List, Tuple
from dataclasses import dataclass

from seo.models import PageMetadata, ConsoleErrorAnalysis


class ConsoleErrorAnalyzer:
    """Analyzes JavaScript console errors and warnings from crawled pages."""

    # Error type patterns
    ERROR_PATTERNS = {
        'TypeError': r'TypeError:',
        'ReferenceError': r'ReferenceError:',
        'SyntaxError': r'SyntaxError:',
        'RangeError': r'RangeError:',
        'URIError': r'URIError:',
        'NetworkError': r'(NetworkError|Failed to fetch|net::)',
        'SecurityError': r'(SecurityError|CORS|blocked)',
        'ResourceError': r'(404|Failed to load|ERR_)',
        'DeprecationWarning': r'(deprecated|Deprecation)',
        'Other': r'.*'
    }

    def analyze(self, pages: Dict[str, PageMetadata]) -> ConsoleErrorAnalysis:
        """Analyze console errors across all pages.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            ConsoleErrorAnalysis with error metrics
        """
        if not pages:
            return ConsoleErrorAnalysis()

        analysis = ConsoleErrorAnalysis(total_pages=len(pages))

        all_errors = []
        all_warnings = []
        error_messages = []
        pages_errors = []

        for url, page in pages.items():
            page_error_count = 0
            page_warning_count = 0
            page_errors_list = []

            # Process errors
            for error in page.console_errors:
                error_type = self._categorize_error(error)
                all_errors.append({
                    'url': url,
                    'message': error[:200],  # Truncate long messages
                    'type': error_type
                })
                error_messages.append(error[:100])  # For frequency analysis
                page_error_count += 1
                page_errors_list.append(error[:100])

                # Count by type
                analysis.errors_by_type[error_type] = \
                    analysis.errors_by_type.get(error_type, 0) + 1

            # Process warnings
            for warning in page.console_warnings:
                all_warnings.append({
                    'url': url,
                    'message': warning[:200]
                })
                page_warning_count += 1

            # Track pages with errors
            if page_error_count > 0:
                analysis.pages_with_errors += 1
                pages_errors.append({
                    'url': url,
                    'error_count': page_error_count,
                    'warning_count': page_warning_count,
                    'errors': page_errors_list[:5]  # Top 5 errors per page
                })

            if page_warning_count > 0:
                analysis.pages_with_warnings += 1

        # Totals
        analysis.total_errors = len(all_errors)
        analysis.total_warnings = len(all_warnings)

        # Error-free percentage
        if analysis.total_pages > 0:
            error_free = analysis.total_pages - analysis.pages_with_errors
            analysis.error_free_percentage = round(
                error_free / analysis.total_pages * 100, 1
            )

        # Sort pages by error count
        pages_errors.sort(key=lambda x: x['error_count'], reverse=True)
        analysis.pages_by_error_count = pages_errors[:20]  # Top 20

        # Find most common errors
        error_counter = Counter(error_messages)
        analysis.common_errors = [
            {'message': msg, 'count': count}
            for msg, count in error_counter.most_common(10)
        ]

        # Store all errors (limited)
        analysis.all_errors = all_errors[:100]

        return analysis

    def _categorize_error(self, error: str) -> str:
        """Categorize an error message by type.

        Args:
            error: Error message string

        Returns:
            Error type category
        """
        for error_type, pattern in self.ERROR_PATTERNS.items():
            if error_type == 'Other':
                continue
            if re.search(pattern, error, re.IGNORECASE):
                return error_type
        return 'Other'
```

---

#### Task 1.2.1.3: Integrate Console Analyzer into Report Generator

**File:** `src/seo/report_generator.py`

**Add import:**
```python
from seo.console_analyzer import ConsoleErrorAnalyzer
```

**Add method:**
```python
def _process_console_errors(
    self,
    pages: Dict[str, PageMetadata]
) -> Dict:
    """Process console error analysis for report.

    Args:
        pages: Dictionary mapping URLs to PageMetadata

    Returns:
        Dictionary with console error data for template
    """
    analyzer = ConsoleErrorAnalyzer()
    analysis = analyzer.analyze(pages)

    # Check if any console data was captured
    has_data = any(
        page.console_errors or page.console_warnings
        for page in pages.values()
    )

    return {
        'enabled': has_data,
        'total_pages': analysis.total_pages,
        'pages_with_errors': analysis.pages_with_errors,
        'pages_with_warnings': analysis.pages_with_warnings,
        'error_free_percentage': analysis.error_free_percentage,
        'total_errors': analysis.total_errors,
        'total_warnings': analysis.total_warnings,
        'errors_by_type': analysis.errors_by_type,
        'pages_by_error_count': analysis.pages_by_error_count,
        'common_errors': analysis.common_errors,
        'has_errors': analysis.total_errors > 0,
        'severity': self._get_console_severity(analysis),
    }

def _get_console_severity(self, analysis: ConsoleErrorAnalysis) -> str:
    """Determine severity level based on error analysis."""
    if analysis.pages_with_errors == 0:
        return 'good'

    error_rate = analysis.pages_with_errors / analysis.total_pages
    if error_rate > 0.5:
        return 'critical'
    elif error_rate > 0.2:
        return 'high'
    elif error_rate > 0.1:
        return 'medium'
    return 'low'
```

---

#### Task 1.2.1.4: Add Console Errors Section to HTML Template

**File:** `templates/report.html`

**Add to Technical Issues tab or create new JavaScript Health section:**

```html
<!-- JavaScript Health Section -->
<div class="section" id="js-health">
    <h2>JavaScript Health</h2>

    {% if console_errors.enabled %}
    <div class="stats-grid">
        <div class="stat-card {% if console_errors.severity == 'critical' %}critical{% elif console_errors.severity == 'high' %}warning{% endif %}">
            <div class="stat-value">{{ console_errors.total_errors }}</div>
            <div class="stat-label">Total Console Errors</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ console_errors.total_warnings }}</div>
            <div class="stat-label">Console Warnings</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ console_errors.pages_with_errors }}</div>
            <div class="stat-label">Pages with Errors</div>
        </div>
        <div class="stat-card {% if console_errors.error_free_percentage >= 90 %}success{% endif %}">
            <div class="stat-value">{{ console_errors.error_free_percentage }}%</div>
            <div class="stat-label">Error-Free Pages</div>
        </div>
    </div>

    {% if console_errors.has_errors %}
    <!-- Errors by Type -->
    <h3>Errors by Type</h3>
    <div class="chart-container" style="max-width: 500px;">
        <canvas id="errorsByTypeChart"></canvas>
    </div>

    <!-- Common Errors -->
    <h3>Most Common Errors</h3>
    <div class="table-responsive">
        <table class="data-table">
            <thead>
                <tr>
                    <th>Error Message</th>
                    <th>Count</th>
                </tr>
            </thead>
            <tbody>
                {% for error in console_errors.common_errors %}
                <tr>
                    <td><code>{{ error.message|truncate(80) }}</code></td>
                    <td>{{ error.count }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- Pages with Most Errors -->
    <h3>Pages with Most Errors</h3>
    <div class="table-responsive">
        <table class="data-table">
            <thead>
                <tr>
                    <th>URL</th>
                    <th>Errors</th>
                    <th>Sample Errors</th>
                </tr>
            </thead>
            <tbody>
                {% for page in console_errors.pages_by_error_count[:10] %}
                <tr>
                    <td class="url-cell">{{ page.url|truncate(50) }}</td>
                    <td><span class="badge badge-danger">{{ page.error_count }}</span></td>
                    <td>
                        <ul class="error-list">
                            {% for err in page.errors[:3] %}
                            <li><code>{{ err|truncate(60) }}</code></li>
                            {% endfor %}
                        </ul>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <div class="success-message">
        <p>No JavaScript console errors detected across all crawled pages.</p>
    </div>
    {% endif %}

    {% else %}
    <div class="no-data">
        <p>Console error data not available. Enable JavaScript rendering during crawl to capture console output.</p>
    </div>
    {% endif %}
</div>
```

---

## Feature 1.3: Third-Party Impact Analysis

### Story 1.3.1: Analyze Third-Party Resource Impact

**As a** performance engineer, **I want** to see which third-party resources are slowing down my site **so that** I can prioritize vendor optimization.

#### Task 1.3.1.1: Create ThirdPartyAnalysis Data Model

**File:** `src/seo/models.py`

```python
@dataclass
class ThirdPartyDomain:
    """Analysis of a single third-party domain."""
    domain: str
    request_count: int = 0
    total_bytes: int = 0
    pages_present: int = 0
    resource_types: list = field(default_factory=list)  # ['script', 'image', 'font']


@dataclass
class ThirdPartyAnalysis:
    """Analysis of third-party resources across site."""

    total_pages: int = 0
    pages_with_third_party: int = 0

    # Aggregate metrics
    total_third_party_requests: int = 0
    total_third_party_bytes: int = 0
    avg_third_party_requests_per_page: float = 0.0
    avg_third_party_bytes_per_page: int = 0

    # Percentage of page weight from third parties
    third_party_weight_percentage: float = 0.0

    # Per-domain breakdown
    domains: list = field(default_factory=list)  # List of ThirdPartyDomain

    # Top domains by impact
    top_by_requests: list = field(default_factory=list)
    top_by_bytes: list = field(default_factory=list)

    # Pages with most third-party resources
    heaviest_pages: list = field(default_factory=list)

    # Categorized domains
    analytics_domains: list = field(default_factory=list)
    advertising_domains: list = field(default_factory=list)
    cdn_domains: list = field(default_factory=list)
    social_domains: list = field(default_factory=list)
    other_domains: list = field(default_factory=list)

    # Recommendations
    recommendations: list = field(default_factory=list)
```

---

#### Task 1.3.1.2: Create ThirdPartyAnalyzer Class

**File:** `src/seo/third_party_analyzer.py` (new file)

```python
"""Third-party resource analyzer for performance impact assessment."""

from collections import defaultdict
from typing import Dict, List, Set
from urllib.parse import urlparse

from seo.models import PageMetadata, ThirdPartyAnalysis, ThirdPartyDomain


class ThirdPartyAnalyzer:
    """Analyzes third-party resource usage and performance impact."""

    # Known domain categories
    ANALYTICS_DOMAINS = {
        'google-analytics.com', 'googletagmanager.com', 'analytics.google.com',
        'hotjar.com', 'mixpanel.com', 'segment.com', 'amplitude.com',
        'heap.io', 'fullstory.com', 'mouseflow.com', 'clarity.ms'
    }

    ADVERTISING_DOMAINS = {
        'doubleclick.net', 'googlesyndication.com', 'googleadservices.com',
        'facebook.com', 'fbcdn.net', 'adsrvr.org', 'criteo.com',
        'taboola.com', 'outbrain.com', 'amazon-adsystem.com'
    }

    CDN_DOMAINS = {
        'cloudflare.com', 'cdnjs.cloudflare.com', 'jsdelivr.net',
        'unpkg.com', 'bootstrapcdn.com', 'googleapis.com', 'gstatic.com',
        'akamaized.net', 'fastly.net', 'cloudfront.net'
    }

    SOCIAL_DOMAINS = {
        'twitter.com', 'facebook.com', 'linkedin.com', 'pinterest.com',
        'instagram.com', 'youtube.com', 'tiktok.com'
    }

    def analyze(self, pages: Dict[str, PageMetadata]) -> ThirdPartyAnalysis:
        """Analyze third-party resource usage.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            ThirdPartyAnalysis with third-party metrics
        """
        if not pages:
            return ThirdPartyAnalysis()

        analysis = ThirdPartyAnalysis(total_pages=len(pages))

        domain_stats = defaultdict(lambda: {
            'request_count': 0,
            'total_bytes': 0,
            'pages': set()
        })

        total_site_bytes = 0
        page_third_party = []

        for url, page in pages.items():
            total_site_bytes += page.total_page_weight_bytes

            if page.third_party_domains:
                analysis.pages_with_third_party += 1
                analysis.total_third_party_requests += page.third_party_request_count
                analysis.total_third_party_bytes += page.third_party_size_bytes

                page_third_party.append({
                    'url': url,
                    'request_count': page.third_party_request_count,
                    'bytes': page.third_party_size_bytes,
                    'kb': round(page.third_party_size_bytes / 1024, 1),
                    'domains': page.third_party_domains[:5]
                })

                # Track per-domain stats
                for domain in page.third_party_domains:
                    domain_stats[domain]['pages'].add(url)
                    domain_stats[domain]['request_count'] += 1

        # Calculate averages
        if analysis.pages_with_third_party > 0:
            analysis.avg_third_party_requests_per_page = round(
                analysis.total_third_party_requests / analysis.pages_with_third_party, 1
            )
            analysis.avg_third_party_bytes_per_page = (
                analysis.total_third_party_bytes // analysis.pages_with_third_party
            )

        # Calculate third-party weight percentage
        if total_site_bytes > 0:
            analysis.third_party_weight_percentage = round(
                analysis.total_third_party_bytes / total_site_bytes * 100, 1
            )

        # Process domain stats
        domains_list = []
        for domain, stats in domain_stats.items():
            domains_list.append(ThirdPartyDomain(
                domain=domain,
                request_count=stats['request_count'],
                total_bytes=stats['total_bytes'],
                pages_present=len(stats['pages'])
            ))

        # Sort and categorize
        domains_list.sort(key=lambda x: x.request_count, reverse=True)
        analysis.domains = domains_list

        analysis.top_by_requests = [
            {'domain': d.domain, 'requests': d.request_count, 'pages': d.pages_present}
            for d in domains_list[:10]
        ]

        # Categorize domains
        for d in domains_list:
            base_domain = self._get_base_domain(d.domain)
            if base_domain in self.ANALYTICS_DOMAINS or 'analytics' in d.domain:
                analysis.analytics_domains.append(d.domain)
            elif base_domain in self.ADVERTISING_DOMAINS or 'ads' in d.domain:
                analysis.advertising_domains.append(d.domain)
            elif base_domain in self.CDN_DOMAINS or 'cdn' in d.domain:
                analysis.cdn_domains.append(d.domain)
            elif base_domain in self.SOCIAL_DOMAINS:
                analysis.social_domains.append(d.domain)
            else:
                analysis.other_domains.append(d.domain)

        # Pages with most third-party resources
        page_third_party.sort(key=lambda x: x['request_count'], reverse=True)
        analysis.heaviest_pages = page_third_party[:10]

        # Generate recommendations
        analysis.recommendations = self._generate_recommendations(analysis)

        return analysis

    def _get_base_domain(self, domain: str) -> str:
        """Extract base domain from full domain."""
        parts = domain.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        return domain

    def _generate_recommendations(self, analysis: ThirdPartyAnalysis) -> List[str]:
        """Generate recommendations based on third-party analysis."""
        recommendations = []

        if analysis.third_party_weight_percentage > 30:
            recommendations.append(
                f"Third-party resources account for {analysis.third_party_weight_percentage}% "
                "of page weight. Consider self-hosting critical resources."
            )

        if analysis.avg_third_party_requests_per_page > 20:
            recommendations.append(
                f"Average of {analysis.avg_third_party_requests_per_page} third-party requests "
                "per page. Consolidate or defer non-critical requests."
            )

        if len(analysis.analytics_domains) > 2:
            recommendations.append(
                f"Multiple analytics tools detected ({len(analysis.analytics_domains)}). "
                "Consider consolidating to reduce overhead."
            )

        if len(analysis.advertising_domains) > 5:
            recommendations.append(
                f"{len(analysis.advertising_domains)} advertising domains detected. "
                "Use lazy loading for ad scripts to improve initial load."
            )

        return recommendations
```

---

# Epic 2: Social & Structured Data Enhancements

**Business Value:** Improve social sharing appearance and search result rich snippets through comprehensive validation.

## Feature 2.1: Social Meta Validation

### Story 2.1.1: Validate Open Graph and Twitter Cards

**As a** marketer, **I want** to know if my social meta tags are complete **so that** content shares correctly on social platforms.

#### Task 2.1.1.1: Create SocialMetaAnalysis Data Model

**File:** `src/seo/models.py`

```python
@dataclass
class SocialMetaPageResult:
    """Social meta analysis for a single page."""
    url: str

    # Open Graph
    og_present: bool = False
    og_properties: dict = field(default_factory=dict)
    og_missing: list = field(default_factory=list)
    og_score: int = 0  # 0-100

    # Twitter Card
    twitter_present: bool = False
    twitter_properties: dict = field(default_factory=dict)
    twitter_missing: list = field(default_factory=list)
    twitter_score: int = 0  # 0-100

    # Issues
    issues: list = field(default_factory=list)


@dataclass
class SocialMetaAnalysis:
    """Site-wide social meta analysis."""

    total_pages: int = 0

    # Open Graph coverage
    pages_with_og: int = 0
    og_coverage_percentage: float = 0.0
    avg_og_score: float = 0.0

    # Twitter Card coverage
    pages_with_twitter: int = 0
    twitter_coverage_percentage: float = 0.0
    avg_twitter_score: float = 0.0

    # Common missing properties
    common_missing_og: dict = field(default_factory=dict)  # property: count
    common_missing_twitter: dict = field(default_factory=dict)

    # Pages with issues
    pages_missing_og: list = field(default_factory=list)
    pages_missing_twitter: list = field(default_factory=list)
    pages_with_issues: list = field(default_factory=list)

    # Best/worst pages
    best_pages: list = field(default_factory=list)
    worst_pages: list = field(default_factory=list)

    # Per-page results
    page_results: list = field(default_factory=list)
```

---

#### Task 2.1.1.2: Create SocialMetaAnalyzer Class

**File:** `src/seo/social_analyzer.py` (new file)

```python
"""Social meta tag analyzer for Open Graph and Twitter Cards."""

from typing import Dict, List
from collections import Counter

from seo.models import PageMetadata, SocialMetaAnalysis, SocialMetaPageResult


class SocialMetaAnalyzer:
    """Analyzes Open Graph and Twitter Card meta tags."""

    # Required Open Graph properties
    REQUIRED_OG = ['og:title', 'og:description', 'og:image', 'og:url', 'og:type']

    # Recommended Open Graph properties
    RECOMMENDED_OG = ['og:site_name', 'og:locale']

    # Required Twitter Card properties
    REQUIRED_TWITTER = ['twitter:card', 'twitter:title', 'twitter:description']

    # Recommended Twitter properties
    RECOMMENDED_TWITTER = ['twitter:image', 'twitter:site']

    # Valid twitter:card types
    VALID_TWITTER_CARDS = ['summary', 'summary_large_image', 'app', 'player']

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

        all_missing_og = []
        all_missing_twitter = []
        page_results = []

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
        page_results.sort(key=lambda x: x.og_score + x.twitter_score, reverse=True)
        analysis.best_pages = [
            {'url': r.url, 'og_score': r.og_score, 'twitter_score': r.twitter_score}
            for r in page_results[:5] if r.og_score + r.twitter_score > 0
        ]

        page_results.sort(key=lambda x: x.og_score + x.twitter_score)
        analysis.worst_pages = [
            {'url': r.url, 'og_score': r.og_score, 'twitter_score': r.twitter_score,
             'issues': r.issues[:3]}
            for r in page_results[:10]
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
        for prop in self.REQUIRED_OG:
            if prop in og or prop.replace('og:', '') in og:
                og_score += 15
            else:
                result.og_missing.append(prop)
                result.issues.append(f"Missing required OG property: {prop}")

        for prop in self.RECOMMENDED_OG:
            if prop in og or prop.replace('og:', '') in og:
                og_score += 5

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
        for prop in self.REQUIRED_TWITTER:
            prop_name = prop.replace('twitter:', '')
            if prop in twitter or prop_name in twitter:
                twitter_score += 25
            else:
                result.twitter_missing.append(prop)
                result.issues.append(f"Missing required Twitter property: {prop}")

        for prop in self.RECOMMENDED_TWITTER:
            prop_name = prop.replace('twitter:', '')
            if prop in twitter or prop_name in twitter:
                twitter_score += 10

        # Validate twitter:card value
        card_type = twitter.get('twitter:card') or twitter.get('card')
        if card_type and card_type not in self.VALID_TWITTER_CARDS:
            result.issues.append(f"Invalid twitter:card value: {card_type}")
            twitter_score -= 10

        result.twitter_score = max(0, min(twitter_score, 100))

        return result
```

---

## Feature 2.2: Extended Schema Validation

### Story 2.2.1: Validate Additional Schema Types

**As a** site owner, **I want** validation for all common schema types **so that** I can ensure rich result eligibility.

#### Task 2.2.1.1: Add Schema Validators to StructuredDataAnalyzer

**File:** `src/seo/structured_data.py`

**Add after existing validators (around line 275):**

```python
def _validate_faqpage_schema(self, data: Dict, score: StructuredDataScore):
    """Validate FAQPage schema."""
    if 'mainEntity' not in data:
        score.validation_errors.append(
            "FAQPage schema missing required 'mainEntity' property"
        )
        return

    main_entity = data['mainEntity']
    if not isinstance(main_entity, list):
        main_entity = [main_entity]

    for i, question in enumerate(main_entity):
        if '@type' not in question or question['@type'] != 'Question':
            score.validation_warnings.append(
                f"FAQPage mainEntity[{i}] should have @type 'Question'"
            )
        if 'name' not in question:
            score.validation_errors.append(
                f"FAQPage Question[{i}] missing 'name' (the question text)"
            )
        if 'acceptedAnswer' not in question:
            score.validation_errors.append(
                f"FAQPage Question[{i}] missing 'acceptedAnswer'"
            )
        else:
            answer = question['acceptedAnswer']
            if isinstance(answer, dict) and 'text' not in answer:
                score.validation_errors.append(
                    f"FAQPage Answer[{i}] missing 'text' property"
                )


def _validate_howto_schema(self, data: Dict, score: StructuredDataScore):
    """Validate HowTo schema."""
    required = ['name', 'step']
    recommended = ['totalTime', 'estimatedCost', 'supply', 'tool']

    for field in required:
        if field not in data:
            score.validation_errors.append(
                f"HowTo schema missing required field: {field}"
            )

    for field in recommended:
        if field not in data:
            score.validation_warnings.append(
                f"HowTo schema missing recommended field: {field}"
            )

    # Validate steps
    if 'step' in data:
        steps = data['step']
        if not isinstance(steps, list):
            steps = [steps]

        for i, step in enumerate(steps):
            if isinstance(step, dict):
                if 'name' not in step and 'text' not in step:
                    score.validation_errors.append(
                        f"HowTo step[{i}] missing 'name' or 'text'"
                    )


def _validate_recipe_schema(self, data: Dict, score: StructuredDataScore):
    """Validate Recipe schema."""
    required = ['name', 'recipeIngredient', 'recipeInstructions']
    recommended = ['image', 'author', 'prepTime', 'cookTime', 'totalTime',
                   'recipeYield', 'nutrition', 'recipeCategory', 'recipeCuisine']

    for field in required:
        if field not in data:
            score.validation_errors.append(
                f"Recipe schema missing required field: {field}"
            )

    for field in recommended:
        if field not in data:
            score.validation_warnings.append(
                f"Recipe schema missing recommended field: {field}"
            )

    # Validate aggregateRating if present
    if 'aggregateRating' in data:
        rating = data['aggregateRating']
        if isinstance(rating, dict):
            if 'ratingValue' not in rating:
                score.validation_errors.append(
                    "Recipe aggregateRating missing 'ratingValue'"
                )


def _validate_event_schema(self, data: Dict, score: StructuredDataScore):
    """Validate Event schema."""
    required = ['name', 'startDate', 'location']
    recommended = ['endDate', 'description', 'image', 'offers', 'performer', 'organizer']

    for field in required:
        if field not in data:
            score.validation_errors.append(
                f"Event schema missing required field: {field}"
            )

    for field in recommended:
        if field not in data:
            score.validation_warnings.append(
                f"Event schema missing recommended field: {field}"
            )

    # Validate location
    if 'location' in data:
        location = data['location']
        if isinstance(location, dict):
            if '@type' not in location:
                score.validation_warnings.append(
                    "Event location should specify @type (Place, VirtualLocation, etc.)"
                )


def _validate_jobposting_schema(self, data: Dict, score: StructuredDataScore):
    """Validate JobPosting schema."""
    required = ['title', 'description', 'datePosted', 'hiringOrganization']
    recommended = ['validThrough', 'employmentType', 'jobLocation',
                   'baseSalary', 'identifier']

    for field in required:
        if field not in data:
            score.validation_errors.append(
                f"JobPosting schema missing required field: {field}"
            )

    for field in recommended:
        if field not in data:
            score.validation_warnings.append(
                f"JobPosting schema missing recommended field: {field}"
            )

    # Validate hiringOrganization
    if 'hiringOrganization' in data:
        org = data['hiringOrganization']
        if isinstance(org, dict) and 'name' not in org:
            score.validation_errors.append(
                "JobPosting hiringOrganization missing 'name'"
            )


def _validate_localbusiness_schema(self, data: Dict, score: StructuredDataScore):
    """Validate LocalBusiness schema."""
    required = ['name', 'address']
    recommended = ['telephone', 'openingHours', 'geo', 'url',
                   'priceRange', 'image', 'aggregateRating']

    for field in required:
        if field not in data:
            score.validation_errors.append(
                f"LocalBusiness schema missing required field: {field}"
            )

    for field in recommended:
        if field not in data:
            score.validation_warnings.append(
                f"LocalBusiness schema missing recommended field: {field}"
            )

    # Validate address
    if 'address' in data:
        addr = data['address']
        if isinstance(addr, dict):
            addr_required = ['streetAddress', 'addressLocality', 'addressCountry']
            for field in addr_required:
                if field not in addr:
                    score.validation_warnings.append(
                        f"LocalBusiness address missing: {field}"
                    )


def _validate_breadcrumblist_schema(self, data: Dict, score: StructuredDataScore):
    """Validate BreadcrumbList schema."""
    if 'itemListElement' not in data:
        score.validation_errors.append(
            "BreadcrumbList missing required 'itemListElement'"
        )
        return

    items = data['itemListElement']
    if not isinstance(items, list):
        items = [items]

    for i, item in enumerate(items):
        if isinstance(item, dict):
            if 'position' not in item:
                score.validation_errors.append(
                    f"BreadcrumbList item[{i}] missing 'position'"
                )
            if 'name' not in item and 'item' not in item:
                score.validation_errors.append(
                    f"BreadcrumbList item[{i}] missing 'name' or 'item'"
                )


def _validate_videoobject_schema(self, data: Dict, score: StructuredDataScore):
    """Validate VideoObject schema."""
    required = ['name', 'description', 'thumbnailUrl', 'uploadDate']
    recommended = ['duration', 'contentUrl', 'embedUrl', 'interactionStatistic']

    for field in required:
        if field not in data:
            score.validation_errors.append(
                f"VideoObject schema missing required field: {field}"
            )

    for field in recommended:
        if field not in data:
            score.validation_warnings.append(
                f"VideoObject schema missing recommended field: {field}"
            )
```

**Update _validate_schema method to include new validators:**

```python
def _validate_schema(self, score: StructuredDataScore):
    """Validate structured data schemas."""

    for data in score.structured_data:
        if isinstance(data, dict):
            schema_type = data.get('@type', '')

            # Handle array of types
            if isinstance(schema_type, list):
                schema_type = schema_type[0] if schema_type else ''

            if schema_type == 'Product':
                self._validate_product_schema(data, score)
            elif schema_type == 'Organization':
                self._validate_organization_schema(data, score)
            elif schema_type in ['Article', 'BlogPosting', 'NewsArticle']:
                self._validate_article_schema(data, score)
            elif schema_type == 'FAQPage':
                self._validate_faqpage_schema(data, score)
            elif schema_type == 'HowTo':
                self._validate_howto_schema(data, score)
            elif schema_type == 'Recipe':
                self._validate_recipe_schema(data, score)
            elif schema_type == 'Event':
                self._validate_event_schema(data, score)
            elif schema_type == 'JobPosting':
                self._validate_jobposting_schema(data, score)
            elif schema_type == 'LocalBusiness':
                self._validate_localbusiness_schema(data, score)
            elif schema_type == 'BreadcrumbList':
                self._validate_breadcrumblist_schema(data, score)
            elif schema_type == 'VideoObject':
                self._validate_videoobject_schema(data, score)
```

---

# Epic 3: Performance Insights & Comparisons

**Business Value:** Enable data-driven performance optimization by correlating lab and field metrics.

## Feature 3.1: Lab vs Field Performance Comparison

### Story 3.1.1: Compare Lighthouse and CrUX Metrics

**As a** performance engineer, **I want** to see how lab metrics compare to real user data **so that** I can identify where synthetic testing differs from production.

#### Task 3.1.1.1: Create LabFieldComparison Data Model

**File:** `src/seo/models.py`

```python
@dataclass
class MetricComparison:
    """Comparison of a single metric between lab and field."""
    metric_name: str
    lab_value: float = 0.0
    field_value: float = 0.0
    lab_status: str = "unknown"  # good/needs-improvement/poor
    field_status: str = "unknown"
    difference_percentage: float = 0.0
    status_match: bool = True
    insight: str = ""


@dataclass
class LabFieldComparison:
    """Comparison between Lighthouse (lab) and CrUX (field) data."""

    total_pages: int = 0
    pages_with_both: int = 0  # Pages that have both lab and field data

    # Overall comparison
    overall_lab_better: int = 0
    overall_field_better: int = 0
    overall_match: int = 0

    # Per-metric comparisons (aggregated)
    lcp_comparison: MetricComparison = None
    fid_inp_comparison: MetricComparison = None
    cls_comparison: MetricComparison = None

    # Status mismatches (where lab and field disagree)
    status_mismatches: list = field(default_factory=list)

    # Pages with significant gaps
    pages_with_gaps: list = field(default_factory=list)

    # Insights
    insights: list = field(default_factory=list)

    # Is lab optimistic or pessimistic overall?
    lab_tendency: str = "neutral"  # optimistic/pessimistic/neutral
```

---

#### Task 3.1.1.2: Create LabFieldAnalyzer Class

**File:** `src/seo/lab_field_analyzer.py` (new file)

```python
"""Lab vs Field performance analyzer comparing Lighthouse and CrUX data."""

from typing import Dict, List, Optional
from dataclasses import dataclass

from seo.models import PageMetadata, LabFieldComparison, MetricComparison


class LabFieldAnalyzer:
    """Compares Lighthouse (lab) metrics with CrUX (field) data."""

    # Thresholds for status determination
    LCP_GOOD = 2500  # ms
    LCP_POOR = 4000
    INP_GOOD = 200  # ms
    INP_POOR = 500
    CLS_GOOD = 0.1
    CLS_POOR = 0.25

    # Significant gap threshold (percentage)
    SIGNIFICANT_GAP = 20

    def analyze(self, pages: Dict[str, PageMetadata]) -> LabFieldComparison:
        """Compare lab and field performance metrics.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            LabFieldComparison with comparison results
        """
        if not pages:
            return LabFieldComparison()

        comparison = LabFieldComparison(total_pages=len(pages))

        # Collect metrics from pages with both lab and field data
        lcp_lab_values = []
        lcp_field_values = []
        cls_lab_values = []
        cls_field_values = []

        lab_better_count = 0
        field_better_count = 0
        match_count = 0

        for url, page in pages.items():
            has_lab = page.lighthouse_lcp is not None
            has_field = page.crux_lcp_percentile is not None

            if has_lab and has_field:
                comparison.pages_with_both += 1

                # LCP comparison
                lab_lcp = page.lighthouse_lcp  # ms
                field_lcp = page.crux_lcp_percentile  # ms

                lcp_lab_values.append(lab_lcp)
                lcp_field_values.append(field_lcp)

                lab_status = self._get_lcp_status(lab_lcp)
                field_status = page.crux_lcp_category or self._get_lcp_status(field_lcp)

                if lab_status != field_status:
                    comparison.status_mismatches.append({
                        'url': url,
                        'metric': 'LCP',
                        'lab_value': lab_lcp,
                        'lab_status': lab_status,
                        'field_value': field_lcp,
                        'field_status': field_status
                    })

                # Calculate gap
                if field_lcp > 0:
                    gap = ((lab_lcp - field_lcp) / field_lcp) * 100
                    if abs(gap) > self.SIGNIFICANT_GAP:
                        comparison.pages_with_gaps.append({
                            'url': url,
                            'metric': 'LCP',
                            'lab_value': lab_lcp,
                            'field_value': field_lcp,
                            'gap_percentage': round(gap, 1)
                        })

                    if gap < -self.SIGNIFICANT_GAP:
                        lab_better_count += 1
                    elif gap > self.SIGNIFICANT_GAP:
                        field_better_count += 1
                    else:
                        match_count += 1

                # CLS comparison
                if page.lighthouse_cls is not None and page.crux_cls_percentile is not None:
                    cls_lab_values.append(page.lighthouse_cls)
                    cls_field_values.append(page.crux_cls_percentile)

        comparison.overall_lab_better = lab_better_count
        comparison.overall_field_better = field_better_count
        comparison.overall_match = match_count

        # Calculate aggregate comparisons
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

        # Determine lab tendency
        if lab_better_count > field_better_count * 1.5:
            comparison.lab_tendency = "optimistic"
        elif field_better_count > lab_better_count * 1.5:
            comparison.lab_tendency = "pessimistic"
        else:
            comparison.lab_tendency = "neutral"

        # Generate insights
        comparison.insights = self._generate_insights(comparison)

        return comparison

    def _get_lcp_status(self, value: float) -> str:
        """Determine LCP status."""
        if value <= self.LCP_GOOD:
            return "good"
        elif value <= self.LCP_POOR:
            return "needs-improvement"
        return "poor"

    def _get_cls_status(self, value: float) -> str:
        """Determine CLS status."""
        if value <= self.CLS_GOOD:
            return "good"
        elif value <= self.CLS_POOR:
            return "needs-improvement"
        return "poor"

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

        return insights
```

---

# Epic 4: Configuration & Thresholds

**Business Value:** Allow customization of analysis thresholds for different use cases and industries.

## Feature 4.1: Configurable Analysis Thresholds

### Story 4.1.1: Externalize Hardcoded Thresholds

**As a** developer, **I want** to configure analysis thresholds **so that** I can adjust them for different project requirements.

#### Task 4.1.1.1: Create AnalysisThresholds Configuration Class

**File:** `src/seo/config.py`

**Add after existing Config class:**

```python
import json
from pathlib import Path


@dataclass
class AnalysisThresholds:
    """Configurable thresholds for SEO analysis."""

    # Technical SEO
    meta_description_min: int = 120
    meta_description_max: int = 160
    title_min: int = 30
    title_max: int = 60
    slow_page_seconds: float = 3.0
    thin_content_words: int = 300

    # Core Web Vitals (milliseconds for time-based, decimal for CLS)
    lcp_good: float = 2500
    lcp_poor: float = 4000
    inp_good: int = 200
    inp_poor: int = 500
    cls_good: float = 0.1
    cls_poor: float = 0.25
    fcp_good: int = 1800
    fcp_poor: int = 3000

    # Resource sizes (bytes)
    max_js_size: int = 500 * 1024  # 500KB
    max_css_size: int = 200 * 1024  # 200KB
    max_image_size: int = 1024 * 1024  # 1MB
    max_page_weight: int = 2 * 1024 * 1024  # 2MB
    max_font_size: int = 100 * 1024  # 100KB

    # URL structure
    max_url_length: int = 100
    max_url_depth: int = 4
    max_url_parameters: int = 3

    # Security
    hsts_min_max_age: int = 31536000  # 1 year in seconds

    # Content quality
    min_readability_score: float = 50.0
    keyword_stuffing_threshold: float = 3.0  # percentage

    # Images
    lazy_load_threshold: int = 3  # Images after this position should be lazy

    @classmethod
    def from_env(cls) -> "AnalysisThresholds":
        """Load thresholds from environment variables.

        Environment variables should be prefixed with SEO_THRESHOLD_
        e.g., SEO_THRESHOLD_SLOW_PAGE_SECONDS=4.0

        Returns:
            AnalysisThresholds with values from environment
        """
        thresholds = cls()
        prefix = "SEO_THRESHOLD_"

        for field_name in thresholds.__dataclass_fields__:
            env_key = f"{prefix}{field_name.upper()}"
            env_value = os.getenv(env_key)

            if env_value is not None:
                field_type = thresholds.__dataclass_fields__[field_name].type
                try:
                    if field_type == int:
                        setattr(thresholds, field_name, int(env_value))
                    elif field_type == float:
                        setattr(thresholds, field_name, float(env_value))
                except ValueError:
                    pass  # Keep default if conversion fails

        return thresholds

    @classmethod
    def from_file(cls, path: str) -> "AnalysisThresholds":
        """Load thresholds from a JSON configuration file.

        Args:
            path: Path to JSON configuration file

        Returns:
            AnalysisThresholds with values from file
        """
        thresholds = cls()
        file_path = Path(path)

        if not file_path.exists():
            return thresholds

        with open(file_path, 'r') as f:
            config = json.load(f)

        threshold_config = config.get('thresholds', config)

        for field_name in thresholds.__dataclass_fields__:
            if field_name in threshold_config:
                setattr(thresholds, field_name, threshold_config[field_name])

        return thresholds

    def to_dict(self) -> dict:
        """Convert thresholds to dictionary.

        Returns:
            Dictionary of all threshold values
        """
        return {
            field_name: getattr(self, field_name)
            for field_name in self.__dataclass_fields__
        }

    def save_to_file(self, path: str) -> None:
        """Save current thresholds to a JSON file.

        Args:
            path: Path to save configuration
        """
        with open(path, 'w') as f:
            json.dump({'thresholds': self.to_dict()}, f, indent=2)


# Global default thresholds instance
default_thresholds = AnalysisThresholds()
```

---

#### Task 4.1.1.2: Update TechnicalAnalyzer to Use Thresholds

**File:** `src/seo/technical.py`

**Update class to accept thresholds:**

```python
from seo.config import AnalysisThresholds, default_thresholds


class TechnicalAnalyzer:
    """Analyzes technical SEO issues across crawled pages."""

    def __init__(self, thresholds: AnalysisThresholds = None):
        """Initialize analyzer with configurable thresholds.

        Args:
            thresholds: Custom thresholds or None for defaults
        """
        self.thresholds = thresholds or default_thresholds

    def _check_meta_description_issues(
        self, url: str, page: PageMetadata, issues: TechnicalIssues
    ) -> None:
        """Check for meta description issues."""
        if not page.description:
            issues.missing_meta_descriptions.append(url)
        elif len(page.description) < self.thresholds.meta_description_min:
            issues.short_meta_descriptions.append(
                (url, len(page.description))
            )
        elif len(page.description) > self.thresholds.meta_description_max:
            issues.long_meta_descriptions.append((url, len(page.description)))

    def _check_performance_issues(
        self, url: str, page: PageMetadata, issues: TechnicalIssues
    ) -> None:
        """Check for performance issues."""
        if page.load_time > self.thresholds.slow_page_seconds:
            issues.slow_pages.append((url, page.load_time))

    def _check_content_issues(
        self, url: str, page: PageMetadata, issues: TechnicalIssues
    ) -> None:
        """Check for content-related issues."""
        if page.word_count < self.thresholds.thin_content_words:
            issues.thin_content.append((url, page.word_count))
```

---

#### Task 4.1.1.3: Create Example Threshold Configuration File

**File:** `config/thresholds.example.json` (new file)

```json
{
  "thresholds": {
    "meta_description_min": 120,
    "meta_description_max": 160,
    "title_min": 30,
    "title_max": 60,
    "slow_page_seconds": 3.0,
    "thin_content_words": 300,

    "lcp_good": 2500,
    "lcp_poor": 4000,
    "inp_good": 200,
    "inp_poor": 500,
    "cls_good": 0.1,
    "cls_poor": 0.25,

    "max_js_size": 512000,
    "max_css_size": 204800,
    "max_image_size": 1048576,
    "max_page_weight": 2097152,

    "max_url_length": 100,
    "max_url_depth": 4,
    "max_url_parameters": 3,

    "min_readability_score": 50.0,
    "keyword_stuffing_threshold": 3.0
  }
}
```

---

# Epic 5: Redirect Chain Analysis

**Business Value:** Identify crawl budget waste and improve site performance by quantifying redirect impact.

## Feature 5.1: Redirect Impact Quantification

### Story 5.1.1: Quantify Redirect Chain Impact

**As a** technical SEO, **I want** to see the performance impact of redirect chains **so that** I can prioritize which redirects to consolidate.

#### Task 5.1.1.1: Create RedirectAnalysis Data Model

**File:** `src/seo/models.py`

```python
@dataclass
class RedirectChain:
    """A single redirect chain analysis."""
    source_url: str
    final_url: str
    chain: list = field(default_factory=list)  # List of URLs in chain
    hop_count: int = 0
    estimated_time_ms: int = 0  # Estimated time cost


@dataclass
class RedirectAnalysis:
    """Site-wide redirect chain analysis."""

    total_pages: int = 0
    pages_with_redirects: int = 0

    # Chain statistics
    total_chains: int = 0
    total_hops: int = 0
    avg_hops_per_chain: float = 0.0
    max_chain_length: int = 0

    # Time impact
    total_time_wasted_ms: int = 0
    avg_time_per_redirect_ms: int = 100  # Estimated ms per redirect

    # Chains by length
    chains_1_hop: int = 0
    chains_2_hops: int = 0
    chains_3_plus_hops: int = 0

    # Problem chains (3+ hops)
    long_chains: list = field(default_factory=list)

    # All chains
    all_chains: list = field(default_factory=list)

    # Recommendations
    recommendations: list = field(default_factory=list)
```

---

#### Task 5.1.1.2: Create RedirectAnalyzer Class

**File:** `src/seo/redirect_analyzer.py` (new file)

```python
"""Redirect chain analyzer for crawl efficiency assessment."""

from typing import Dict, List

from seo.models import PageMetadata, RedirectAnalysis, RedirectChain


class RedirectAnalyzer:
    """Analyzes redirect chains and their performance impact."""

    # Estimated time per redirect hop (milliseconds)
    MS_PER_REDIRECT = 100

    # Threshold for "long" chains
    LONG_CHAIN_THRESHOLD = 3

    def analyze(self, pages: Dict[str, PageMetadata]) -> RedirectAnalysis:
        """Analyze redirect chains across all pages.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            RedirectAnalysis with redirect metrics
        """
        if not pages:
            return RedirectAnalysis()

        analysis = RedirectAnalysis(total_pages=len(pages))

        chains = []

        for url, page in pages.items():
            if page.was_redirected and page.redirect_chain:
                analysis.pages_with_redirects += 1

                chain = RedirectChain(
                    source_url=url,
                    final_url=page.final_url or url,
                    chain=page.redirect_chain,
                    hop_count=len(page.redirect_chain),
                    estimated_time_ms=len(page.redirect_chain) * self.MS_PER_REDIRECT
                )
                chains.append(chain)

                # Count by length
                if chain.hop_count == 1:
                    analysis.chains_1_hop += 1
                elif chain.hop_count == 2:
                    analysis.chains_2_hops += 1
                else:
                    analysis.chains_3_plus_hops += 1
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
                f"{analysis.chains_3_plus_hops} redirect chains have 3+ hops. "
                "Consolidate these to single redirects to improve performance."
            )

        if analysis.total_time_wasted_ms > 1000:
            seconds = analysis.total_time_wasted_ms / 1000
            recommendations.append(
                f"Redirect chains waste approximately {seconds:.1f} seconds "
                "of cumulative load time. Update internal links to point to final URLs."
            )

        if analysis.pages_with_redirects > analysis.total_pages * 0.1:
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
```

---

# Epic 6: Image Optimization Analysis

**Business Value:** Provide specific image optimization recommendations to improve Core Web Vitals.

## Feature 6.1: Image Format and Size Analysis

### Story 6.1.1: Analyze Image Optimization Opportunities

**As a** developer, **I want** to know which images need optimization **so that** I can improve page load performance.

#### Task 6.1.1.1: Create ImageAnalysis Data Model

**File:** `src/seo/models.py`

```python
@dataclass
class ImageIssue:
    """A single image optimization issue."""
    url: str
    page_url: str
    issue_type: str  # 'format', 'size', 'dimensions', 'lazy', 'alt'
    current_value: str
    recommended_value: str
    estimated_savings_bytes: int = 0


@dataclass
class ImageAnalysis:
    """Site-wide image optimization analysis."""

    total_pages: int = 0
    total_images: int = 0

    # Format breakdown
    format_counts: dict = field(default_factory=dict)  # {'png': 50, 'jpg': 100}
    modern_format_percentage: float = 0.0  # WebP + AVIF percentage

    # Size metrics
    total_image_bytes: int = 0
    avg_image_bytes: int = 0
    largest_images: list = field(default_factory=list)

    # Optimization opportunities
    images_needing_modern_format: list = field(default_factory=list)
    images_missing_dimensions: list = field(default_factory=list)
    images_needing_lazy_load: list = field(default_factory=list)
    images_oversized: list = field(default_factory=list)

    # Lazy loading stats
    lazy_loaded_count: int = 0
    eager_loaded_count: int = 0
    lazy_load_percentage: float = 0.0

    # Alt text stats
    images_with_alt: int = 0
    images_without_alt: int = 0
    alt_coverage_percentage: float = 0.0

    # Estimated savings
    estimated_total_savings_bytes: int = 0
    estimated_savings_percentage: float = 0.0

    # All issues
    all_issues: list = field(default_factory=list)

    # Recommendations
    recommendations: list = field(default_factory=list)
```

---

#### Task 6.1.1.2: Create ImageAnalyzer Class

**File:** `src/seo/image_analyzer.py` (new file)

```python
"""Image optimization analyzer for performance improvement."""

import re
from typing import Dict, List
from urllib.parse import urlparse

from seo.models import PageMetadata, ImageAnalysis, ImageIssue


class ImageAnalyzer:
    """Analyzes image optimization opportunities."""

    # Modern formats that should be preferred
    MODERN_FORMATS = {'webp', 'avif'}

    # Formats that can typically be converted to modern formats
    CONVERTIBLE_FORMATS = {'png', 'jpg', 'jpeg', 'gif'}

    # Estimated savings when converting to WebP (percentage)
    WEBP_SAVINGS_ESTIMATE = 0.30  # 30% smaller on average

    # Size threshold for "large" images
    LARGE_IMAGE_THRESHOLD = 200 * 1024  # 200KB

    def analyze(self, pages: Dict[str, PageMetadata]) -> ImageAnalysis:
        """Analyze image optimization opportunities.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            ImageAnalysis with optimization metrics
        """
        if not pages:
            return ImageAnalysis()

        analysis = ImageAnalysis(total_pages=len(pages))

        format_counts = {}
        all_issues = []

        for url, page in pages.items():
            for img in page.images:
                analysis.total_images += 1

                img_src = img.get('src', '')
                img_alt = img.get('alt')

                # Determine format
                img_format = self._get_image_format(img_src)
                format_counts[img_format] = format_counts.get(img_format, 0) + 1

                # Check for modern format conversion opportunity
                if img_format in self.CONVERTIBLE_FORMATS:
                    analysis.images_needing_modern_format.append({
                        'src': img_src[:100],
                        'page': url,
                        'format': img_format
                    })

                # Check alt text
                if img_alt:
                    analysis.images_with_alt += 1
                else:
                    analysis.images_without_alt += 1

                # Check for dimensions
                if 'width' not in img and 'height' not in img:
                    analysis.images_missing_dimensions.append({
                        'src': img_src[:100],
                        'page': url
                    })
                    all_issues.append(ImageIssue(
                        url=img_src,
                        page_url=url,
                        issue_type='dimensions',
                        current_value='missing',
                        recommended_value='Add width and height attributes'
                    ))

            # Aggregate lazy loading stats
            analysis.lazy_loaded_count += page.lazy_images_count
            analysis.eager_loaded_count += page.eager_images_count
            analysis.total_image_bytes += page.image_size_bytes

            # Check for images that should be lazy loaded
            # (images after the 3rd on a page)
            if page.eager_images_count > 3:
                excess = page.eager_images_count - 3
                analysis.images_needing_lazy_load.append({
                    'page': url,
                    'eager_count': page.eager_images_count,
                    'should_lazy': excess
                })

        # Store format counts
        analysis.format_counts = format_counts

        # Calculate modern format percentage
        modern_count = sum(
            format_counts.get(fmt, 0) for fmt in self.MODERN_FORMATS
        )
        if analysis.total_images > 0:
            analysis.modern_format_percentage = round(
                modern_count / analysis.total_images * 100, 1
            )
            analysis.avg_image_bytes = analysis.total_image_bytes // analysis.total_images
            analysis.alt_coverage_percentage = round(
                analysis.images_with_alt / analysis.total_images * 100, 1
            )

        # Calculate lazy load percentage
        total_lazy_eager = analysis.lazy_loaded_count + analysis.eager_loaded_count
        if total_lazy_eager > 0:
            analysis.lazy_load_percentage = round(
                analysis.lazy_loaded_count / total_lazy_eager * 100, 1
            )

        # Estimate savings from format conversion
        convertible_count = sum(
            format_counts.get(fmt, 0) for fmt in self.CONVERTIBLE_FORMATS
        )
        if convertible_count > 0 and analysis.total_images > 0:
            convertible_ratio = convertible_count / analysis.total_images
            estimated_convertible_bytes = int(
                analysis.total_image_bytes * convertible_ratio
            )
            analysis.estimated_total_savings_bytes = int(
                estimated_convertible_bytes * self.WEBP_SAVINGS_ESTIMATE
            )
            analysis.estimated_savings_percentage = round(
                analysis.estimated_total_savings_bytes / analysis.total_image_bytes * 100, 1
            ) if analysis.total_image_bytes > 0 else 0

        analysis.all_issues = all_issues[:100]  # Limit stored issues

        # Generate recommendations
        analysis.recommendations = self._generate_recommendations(analysis)

        return analysis

    def _get_image_format(self, src: str) -> str:
        """Extract image format from URL."""
        if not src:
            return 'unknown'

        # Remove query string
        path = src.split('?')[0].lower()

        # Check for common extensions
        for ext in ['webp', 'avif', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'ico']:
            if path.endswith(f'.{ext}'):
                return ext

        # Check for format in URL path
        if 'webp' in path:
            return 'webp'
        if 'avif' in path:
            return 'avif'

        return 'unknown'

    def _generate_recommendations(self, analysis: ImageAnalysis) -> List[str]:
        """Generate recommendations based on image analysis."""
        recommendations = []

        if analysis.modern_format_percentage < 50:
            recommendations.append(
                f"Only {analysis.modern_format_percentage}% of images use modern formats. "
                "Convert PNG/JPEG images to WebP for ~30% size reduction."
            )

        if len(analysis.images_missing_dimensions) > 0:
            recommendations.append(
                f"{len(analysis.images_missing_dimensions)} images lack width/height attributes. "
                "Add dimensions to prevent Cumulative Layout Shift (CLS)."
            )

        if len(analysis.images_needing_lazy_load) > 0:
            total_excess = sum(p['should_lazy'] for p in analysis.images_needing_lazy_load)
            recommendations.append(
                f"{total_excess} images could be lazy-loaded to improve initial load time. "
                "Add loading=\"lazy\" to below-the-fold images."
            )

        if analysis.alt_coverage_percentage < 90:
            recommendations.append(
                f"Alt text coverage is {analysis.alt_coverage_percentage}%. "
                "Add descriptive alt text to all content images for accessibility and SEO."
            )

        if analysis.estimated_total_savings_bytes > 500 * 1024:
            savings_kb = analysis.estimated_total_savings_bytes / 1024
            recommendations.append(
                f"Converting to modern formats could save ~{savings_kb:.0f}KB "
                f"({analysis.estimated_savings_percentage}% of total image weight)."
            )

        return recommendations
```

---

# Implementation Checklist

## Phase 1: Quick Wins (Tier 1)

- [ ] **Task 1.2.1.1-1.2.1.4**: Console Error Reporting
- [ ] **Task 2.1.1.1-2.1.1.2**: Social Meta Validation
- [ ] **Task 5.1.1.1-5.1.1.2**: Redirect Chain Analysis
- [ ] **Task 1.3.1.1-1.3.1.2**: Third-Party Impact Analysis

## Phase 2: Core Enhancements (Tier 2)

- [ ] **Task 1.1.1.1-1.1.1.4**: Resource Composition Analysis
- [ ] **Task 3.1.1.1-3.1.1.2**: Lab vs Field Comparison
- [ ] **Task 2.2.1.1**: Extended Schema Validation
- [ ] **Task 6.1.1.1-6.1.1.2**: Image Optimization Analysis

## Phase 3: Configuration (Tier 3)

- [ ] **Task 4.1.1.1-4.1.1.3**: Configurable Thresholds

## Phase 4: Template Updates

- [ ] Add Resource Analysis tab to report.html
- [ ] Add JavaScript Health section to report.html
- [ ] Add Social SEO section to report.html
- [ ] Add Lab vs Field comparison section to report.html
- [ ] Add Third-Party Analysis section to report.html
- [ ] Add Image Optimization section to report.html
- [ ] Add Redirect Analysis section to report.html

---

# Testing Requirements

Each new analyzer should have corresponding tests:

## Unit Tests Required

```
tests/
├── test_resource_analyzer.py
├── test_console_analyzer.py
├── test_social_analyzer.py
├── test_third_party_analyzer.py
├── test_lab_field_analyzer.py
├── test_redirect_analyzer.py
├── test_image_analyzer.py
└── test_thresholds.py
```

## Test Coverage Targets

- Each analyzer: >90% line coverage
- Edge cases: empty pages, missing data, malformed input
- Threshold edge cases: values at boundaries
- Report integration: verify data flows to template correctly

---

# File Summary

## New Files to Create

| File | Purpose |
|------|---------|
| `src/seo/resource_analyzer.py` | Page weight and resource analysis |
| `src/seo/console_analyzer.py` | JavaScript console error analysis |
| `src/seo/social_analyzer.py` | Open Graph and Twitter Card validation |
| `src/seo/third_party_analyzer.py` | Third-party resource impact |
| `src/seo/lab_field_analyzer.py` | Lighthouse vs CrUX comparison |
| `src/seo/redirect_analyzer.py` | Redirect chain analysis |
| `src/seo/image_analyzer.py` | Image optimization analysis |
| `config/thresholds.example.json` | Example threshold configuration |

## Files to Modify

| File | Changes |
|------|---------|
| `src/seo/models.py` | Add 12 new dataclasses |
| `src/seo/config.py` | Add AnalysisThresholds class |
| `src/seo/technical.py` | Use configurable thresholds |
| `src/seo/structured_data.py` | Add 8 new schema validators |
| `src/seo/report_generator.py` | Add processing methods for new analyzers |
| `templates/report.html` | Add 7 new report sections |
