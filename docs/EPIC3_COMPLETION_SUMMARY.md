# Epic 3: Performance Evidence - Completion Summary

> **Status:** Complete
> **Completed:** 2026-02-08
> **Feature File:** `features/epic3_performance_evidence.feature`

---

## Executive Summary

Epic 3 implements comprehensive evidence capture for performance analysis. The analyzers now include full provenance metadata for Lighthouse and CrUX data, enabling audit trails and transparency in performance recommendations.

---

## Features Completed

### Feature 3.1: Core Web Vitals Evidence

| Story | Description | Status |
|-------|-------------|--------|
| 3.1.1 | CWV Estimate Methodology Evidence | Complete (pre-existing) |
| 3.1.2 | Estimate vs Actual Disclaimer | Complete (pre-existing) |
| 3.1.3 | Contributing Factors Evidence | Complete (pre-existing) |

### Feature 3.2: Lab/Field Comparison Evidence

| Story | Description | Status |
|-------|-------------|--------|
| 3.2.1 | Data Source Provenance | Complete |
| 3.2.2 | Lighthouse Metadata Capture | Complete |
| 3.2.3 | CrUX Data Freshness | Complete |
| 3.2.4 | Status Mismatch Evidence | Complete (pre-existing) |

### Feature 3.3: PSI Coverage Requirements

| Story | Description | Status |
|-------|-------------|--------|
| 3.3.1 | Coverage Threshold Tracking | Complete |
| 3.3.2 | Failed Request Logging | Complete |
| 3.3.3 | Backfill Script Support | Complete (pre-existing) |
| 3.3.4 | Coverage Statistics Reporting | Complete |

---

## Implementation Details

### Story 3.2.1: Data Source Provenance

Lab/Field analyzer now includes full API identifiers:

```python
# Source labels for evidence provenance
LAB_SOURCE = "Lighthouse"
LAB_SOURCE_FULL = "google_pagespeed_insights"
FIELD_SOURCE = "CrUX"
FIELD_SOURCE_FULL = "chrome_user_experience_report"

# CrUX data freshness metadata
CRUX_COLLECTION_PERIOD = "28-day rolling window"
CRUX_DATA_FRESHNESS_NOTE = "Real user data aggregated over last 28 days"
```

### Story 3.2.2: Lighthouse Metadata

PageSpeed Insights results now include:

| Field | Description |
|-------|-------------|
| `lighthouse_version` | Lighthouse version used for analysis |
| `user_agent` | User agent string used during test |
| `requested_url` | Original URL requested |
| `final_url` | Final URL after redirects |
| `run_warnings` | Any warnings from Lighthouse run |

### Story 3.2.3: CrUX Data Freshness

CrUX (field) data now includes provenance metadata:

| Field | Value |
|-------|-------|
| `origin_fallback` | Whether origin-level data was used as fallback |
| `collection_period` | "28-day rolling window" |
| `data_freshness` | "Real user data from last 28 days" |

### Story 3.3.1: PSI Coverage Tracking

New `get_psi_coverage()` method provides:

```python
{
    'total_pages': 50,              # Total pages crawled
    'pages_sampled': 50,            # Pages selected for PSI
    'pages_with_psi': 47,           # Successful PSI analyses
    'pages_failed': 3,              # Failed PSI requests
    'pages_skipped': 0,             # Not sampled (when sample_rate < 1.0)
    'coverage_percentage': 94.0,    # Percentage with PSI data
    'sample_coverage_percentage': 94.0,
    'sample_rate': 1.0,
    'failed_urls': {                # URLs with error reasons
        'https://...': 'Timeout',
    },
    'skipped_urls': [],
    'meets_threshold': True,        # >= 90% coverage
}
```

### Story 3.3.4: Coverage Statistics Reporting

PSI coverage is now:
- Logged at crawl completion with percentage
- Warnings logged if coverage < 90%
- Saved to `lighthouse/_coverage.json` for persistence

---

## Evidence Structure

### Mismatch Evidence

```python
{
    'component_id': 'lab_field_analyzer',
    'finding': 'lcp_status_mismatch',
    'evidence_string': 'LCP status mismatch: Lighthouse shows good, CrUX shows needs-improvement',
    'confidence': 'High',
    'source': 'Lighthouse vs CrUX',
    'source_type': 'measurement',
    'measured_value': {
        'lab': {
            'value': 2100,
            'status': 'good',
            'source': 'Lighthouse',
            'source_api': 'google_pagespeed_insights',
        },
        'field': {
            'value': 2800,
            'status': 'needs-improvement',
            'source': 'CrUX',
            'source_api': 'chrome_user_experience_report',
            'collection_period': '28-day rolling window',
        },
    },
}
```

### Gap Evidence

```python
{
    'component_id': 'lab_field_analyzer',
    'finding': 'lcp_significant_gap',
    'evidence_string': 'LCP gap: Lighthouse is 25.0% slower than CrUX',
    'measured_value': {
        'lab': {
            'value': 3500,
            'source': 'Lighthouse',
            'source_api': 'google_pagespeed_insights',
        },
        'field': {
            'value': 2800,
            'source': 'CrUX',
            'source_api': 'chrome_user_experience_report',
            'collection_period': '28-day rolling window',
            'data_freshness': 'Real user data aggregated over last 28 days',
        },
        'gap_percentage': 25.0,
        'threshold': 20.0,
    },
    'input_summary': {
        'formula': '((lab_value - field_value) / field_value) * 100',
        'lab_source': 'Lighthouse',
        'lab_api': 'google_pagespeed_insights',
        'field_source': 'CrUX',
        'field_api': 'chrome_user_experience_report',
    },
}
```

---

## Pre-Existing Implementation

The following was already implemented prior to this Epic:

### Core Web Vitals Analyzer (`core_web_vitals.py`)

- `_add_estimate_evidence()` method with:
  - `is_estimate` flag
  - `estimation_methodology`
  - `contributing_factors`
  - `thresholds`
  - `disclaimer`

### Lab/Field Analyzer (`lab_field_analyzer.py`)

- Status mismatch detection with evidence
- Significant gap detection with evidence
- Aggregate summary evidence

### PageSpeed Insights API (`pagespeed_insights.py`)

- Rate limiting
- Category score extraction
- CWV metric extraction
- Opportunity extraction

---

## Files Modified

| File | Changes |
|------|---------|
| `src/seo/external/pagespeed_insights.py` | Added Lighthouse metadata, CrUX freshness fields |
| `src/seo/lab_field_analyzer.py` | Added source labels, enhanced evidence records |
| `src/seo/async_site_crawler.py` | Added PSI coverage tracking, failure logging |
| `src/seo/output_manager.py` | Added `save_psi_coverage()` method |

---

## Test Results

All 82 existing tests pass.

---

## BDD Scenario Coverage

| Scenario Tag | Count | Status |
|--------------|-------|--------|
| @story-3.1.x @cwv-estimates | 9 | Pre-existing |
| @story-3.2.x @lab-field | 8 | Enhanced |
| @story-3.3.x @psi-coverage | 10 | Implemented |
| @edge-case | 4 | Implemented |
| **Total** | **31** | **100%** |

---

## Usage Example

```python
from seo.async_site_crawler import AsyncSiteCrawler
from seo.output_manager import OutputManager

# Crawl with PSI enabled
crawler = AsyncSiteCrawler(
    start_url="https://example.com",
    enable_psi=True,
    psi_api_key="your-api-key",
    psi_sample_rate=1.0,  # 100% coverage
)

site_data = await crawler.crawl()

# Get coverage statistics
coverage = crawler.get_psi_coverage()
print(f"PSI Coverage: {coverage['coverage_percentage']:.1f}%")
print(f"Meets threshold: {coverage['meets_threshold']}")

if coverage['pages_failed'] > 0:
    print(f"Failed URLs: {list(coverage['failed_urls'].keys())}")

# Save coverage for evidence
output_manager = OutputManager()
output_manager.save_psi_coverage(crawl_dir, coverage)
```

---

## Next Steps

Epic 3 is complete. The following epics can now proceed:

1. **Epic 4: Content Quality Evidence** - Already complete (per GEMINI_REVIEW_LOG)
2. **Epic 8: Report UI Evidence Display** - Surface evidence in HTML reports

---

## Appendix: Key Files

| File | Purpose |
|------|---------|
| `src/seo/core_web_vitals.py` | CWV estimation with evidence |
| `src/seo/lab_field_analyzer.py` | Lab/field comparison with evidence |
| `src/seo/external/pagespeed_insights.py` | PSI API client with metadata |
| `src/seo/async_site_crawler.py` | Crawler with PSI coverage tracking |
| `features/epic3_performance_evidence.feature` | BDD scenarios |
