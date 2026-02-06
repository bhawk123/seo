# Evidence Trail Documentation

This document outlines how the SEO crawler captures, stores, and can surface evidence for all evaluations and conclusions. Given that AI/LLM components are involved, maintaining transparent audit trails is critical for user trust.

---

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| EvidenceRecord dataclass | **DONE** | `src/seo/models.py` |
| EvidenceCollection dataclass | **DONE** | `src/seo/models.py` |
| ConfidenceLevel enum | **DONE** | `src/seo/models.py` |
| EvidenceSourceType enum | **DONE** | `src/seo/models.py` |
| Technology Detection evidence | **DONE** | `src/seo/technology_detector.py` |
| BDD Feature file | **DONE** | `features/evidence_capture.feature` |
| Technical SEO evidence | Planned | Phase 2 |
| LLM output evidence | Planned | Phase 2 |
| Report UI integration | Planned | Phase 3 |

---

## Table of Contents

1. [Design Philosophy](#design-philosophy)
2. [Evidence Capture by Component](#evidence-capture-by-component)
3. [Hallucination Risk Assessment](#hallucination-risk-assessment)
4. [Implementation Guide: Surfacing Evidence](#implementation-guide-surfacing-evidence)
5. [UI Patterns for Evidence Display](#ui-patterns-for-evidence-display)
6. [Future Enhancements](#future-enhancements)

---

## Design Philosophy

Every evaluation, score, or conclusion made by the crawler should be:

1. **Traceable** - The raw data that led to the conclusion is stored
2. **Verifiable** - Users can inspect the evidence themselves
3. **Transparent** - AI-generated content is clearly labeled
4. **Reproducible** - Same inputs produce same outputs (where possible)

### Evidence Hierarchy

```
Conclusion/Score
    └── Evidence Summary (human-readable)
        └── Raw Data (inspectable)
            └── Source (URL, header, HTML snippet)
```

---

## Evidence Capture by Component

### 1. Technology Detection

**File:** `src/seo/technology_detector.py`

**STATUS: IMPLEMENTED**

| Conclusion | Evidence Captured | Evidence Gap |
|------------|-------------------|--------------|
| "Magento/Adobe Commerce detected" | Full `EvidenceCollection` with matched string | None |
| Technology version | Script URL version extraction | Incomplete: not all techs have version detection |
| Technology category | Static mapping in `CATEGORIES` | None |

**Implemented Evidence Structure:**

The `detect()` method now returns an `evidence` key containing full audit trails:

```python
{
    'all_technologies': ['Magento/Adobe Commerce', 'jQuery', 'Nginx'],
    'by_category': {...},
    'details': {...},
    'evidence': {
        'Magento/Adobe Commerce': {
            'finding': 'Magento/Adobe Commerce',
            'component_id': 'technology_detection',
            'records': [
                {
                    'component_id': 'technology_detection',
                    'finding': 'Magento/Adobe Commerce',
                    'evidence_string': 'mage/cookies.js',  # Actual matched string
                    'confidence': 'High',
                    'timestamp': '2024-01-15T10:30:00',
                    'source': 'Pattern Match',
                    'source_type': 'html_content',
                    'pattern_matched': r'magento|mage\.js|mage/|varien/',
                    'source_location': 'HTML content'
                }
            ],
            'combined_confidence': 'High',
            'record_count': 1
        },
        'Nginx': {
            'finding': 'Nginx',
            'component_id': 'technology_detection',
            'records': [
                {
                    'evidence_string': 'nginx/1.24.0',
                    'source': 'Pattern Match',
                    'source_type': 'http_header',
                    'source_location': 'HTTP Header: Server',
                    ...
                }
            ],
            ...
        }
    },
    'total_count': 3
}
```

**Detection methods with evidence capture:**
- `_detect_pattern()` - Captures regex matches with the actual matched string
- `_add_evidence()` - Adds evidence records to the collection
- Header detection - Captures HTTP header name and value as evidence

---

### 2. Technical SEO Issues

**File:** `src/seo/technical.py`

| Issue | Evidence Captured | Threshold |
|-------|-------------------|-----------|
| Missing title | Page URL | `if not page.title` |
| Duplicate titles | List of URLs sharing title | `count > 1` |
| Missing meta description | Page URL | `if not page.description` |
| Short meta description | URL + actual length | `< 120 chars` |
| Long meta description | URL + actual length | `> 160 chars` |
| Missing H1 | Page URL | `if not page.h1_tags` |
| Multiple H1s | URL + H1 tag list | `len(h1_tags) > 1` |
| Images without alt | URL + image count | `images_without_alt > 0` |
| Slow pages | URL + load time | `> 3.0 seconds` |
| Thin content | URL + word count | `< 300 words` |
| Missing canonical | Page URL | `if not page.canonical_url` |
| Broken links | Source URL + target URL | Link not in crawled URLs |

**Evidence Quality:** HIGH - All raw data is preserved in `PageMetadata` and `TechnicalIssues`.

**Recommended Enhancement:** Add threshold values to issue records:
```python
{
    'issue': 'thin_content',
    'url': '/about',
    'measured_value': 187,
    'threshold': 300,
    'unit': 'words',
    'severity': 'warning'
}
```

---

### 3. Core Web Vitals (Estimated)

**File:** `src/seo/core_web_vitals.py`

| Metric | Evidence | Method |
|--------|----------|--------|
| LCP estimate | Response time, render blocking resources | Heuristic: `response_time + render_penalty` |
| INP estimate | Blocking script count | Heuristic: script-based estimation |
| CLS risk | Images/iframes without dimensions | Pattern detection |

**Evidence Quality:** MEDIUM - These are estimates, not measurements.

**Current Storage:**
```python
PageMetadata.cwv_lcp_estimate  # milliseconds
PageMetadata.cwv_lcp_status    # 'good', 'needs-improvement', 'poor'
PageMetadata.cwv_cls_risks     # list of elements causing CLS risk
PageMetadata.cwv_blocking_scripts  # count
```

**Recommended Enhancement:** Clearly label as estimates:
```python
{
    'metric': 'LCP',
    'value': 2800,
    'status': 'needs-improvement',
    'is_estimate': True,
    'estimation_method': 'response_time_plus_render_blocking',
    'contributing_factors': [
        {'factor': 'response_time', 'value': 1200, 'unit': 'ms'},
        {'factor': 'render_blocking_resources', 'count': 3, 'penalty': 1600}
    ],
    'thresholds': {'good': 2500, 'poor': 4000}
}
```

---

### 4. Lighthouse / PageSpeed Insights

**File:** `src/seo/external/pagespeed_insights.py`

| Metric | Evidence | Source |
|--------|----------|--------|
| Performance score | Lighthouse audit | Google PSI API |
| Accessibility score | Lighthouse audit | Google PSI API |
| CrUX LCP/FID/CLS | Real user data | Chrome UX Report |

**Evidence Quality:** HIGH - Real measurements from Google.

**Current Storage:**
```python
PageMetadata.lighthouse_performance_score
PageMetadata.lighthouse_accessibility_score
PageMetadata.crux_lcp_percentile
PageMetadata.crux_lcp_category  # 'FAST', 'AVERAGE', 'SLOW'
```

**Recommended Enhancement:** Store full audit trail:
```python
{
    'source': 'google_pagespeed_insights',
    'api_version': 'v5',
    'fetch_timestamp': '2024-01-15T10:30:00Z',
    'lighthouse_version': '11.0.0',
    'scores': {...},
    'audits': {...},  # Individual audit results
    'raw_response_hash': 'sha256:...'  # For verification
}
```

---

### 5. Content Quality Analysis

**File:** `src/seo/content_quality.py`

| Metric | Evidence | Method |
|--------|----------|--------|
| Readability score | Word/sentence counts | Flesch Reading Ease formula |
| Keyword density | Word frequency map | Stop word filtering + counting |
| Difficult words | Syllable counts | Syllable counting algorithm |

**Evidence Quality:** MEDIUM - Algorithm-based, but syllable counting can be inaccurate.

**Current Storage:**
```python
ContentQualityMetrics.readability_score
ContentQualityMetrics.readability_grade  # "8th Grade", etc.
ContentQualityMetrics.keyword_density    # {word: percentage}
ContentQualityMetrics.word_count
ContentQualityMetrics.sentence_count
```

**Recommended Enhancement:**
```python
{
    'readability': {
        'score': 65.2,
        'grade': '8th Grade',
        'formula': 'flesch_reading_ease',
        'formula_components': {
            'total_words': 850,
            'total_sentences': 42,
            'total_syllables': 1230,
            'avg_words_per_sentence': 20.2,
            'avg_syllables_per_word': 1.45
        }
    }
}
```

---

### 6. Structured Data Validation

**File:** `src/seo/structured_data.py`

| Evaluation | Evidence | Method |
|------------|----------|--------|
| Schema types present | Extracted JSON-LD/Microdata | HTML parsing |
| Validation errors | Missing required fields | Schema.org spec comparison |
| Rich result eligibility | Schema completeness | Google rich result requirements |

**Evidence Quality:** HIGH - Based on actual extracted data and documented specs.

**Current Storage:**
```python
StructuredDataScore.structured_data  # List of extracted schemas
StructuredDataScore.validation_errors
StructuredDataScore.validation_warnings
StructuredDataScore.rich_result_eligibility
```

**Recommended Enhancement:** Include spec references:
```python
{
    'schema_type': 'Product',
    'validation_errors': [
        {
            'field': 'price',
            'error': 'missing_required',
            'spec_reference': 'https://schema.org/Product',
            'rich_result_requirement': 'https://developers.google.com/search/docs/data-types/product'
        }
    ]
}
```

---

### 7. Security Analysis

**File:** `src/seo/advanced_analyzer.py` (SecurityAnalyzer)

| Check | Evidence | Threshold |
|-------|----------|-----------|
| HTTPS | URL scheme | `scheme == 'https'` |
| Security headers | Raw header values | Presence check |
| Mixed content | HTTP resources on HTTPS page | Any occurrence |

**Evidence Quality:** HIGH - Direct observation of headers and content.

**Current Storage:**
```python
SecurityAnalysis.has_https
SecurityAnalysis.security_headers  # Dict of header: value
SecurityAnalysis.security_score
```

**Recommended Enhancement:**
```python
{
    'security_headers': {
        'Strict-Transport-Security': {
            'present': True,
            'value': 'max-age=31536000; includeSubDomains',
            'recommendation': 'Consider adding preload directive',
            'points': 20
        },
        'Content-Security-Policy': {
            'present': False,
            'recommendation': 'Add CSP header to prevent XSS attacks',
            'points': 0,
            'max_points': 20
        }
    }
}
```

---

### 8. Image Optimization

**File:** `src/seo/image_analyzer.py`

| Evaluation | Evidence | Method |
|------------|----------|--------|
| Format detection | File extension, content-type | URL/header inspection |
| Missing alt text | Image element | HTML parsing |
| Missing dimensions | Image element | Attribute check |
| Lazy loading | `loading` attribute | HTML parsing |

**Evidence Quality:** HIGH - Direct HTML inspection.

**Current Storage:**
```python
PageMetadata.images  # List of image URLs
PageMetadata.images_without_alt
ImageAnalysis.format_breakdown
ImageAnalysis.potential_savings
```

**Recommended Enhancement:**
```python
{
    'images': [
        {
            'src': '/images/hero.jpg',
            'alt': None,
            'width': None,
            'height': None,
            'loading': None,
            'format': 'jpeg',
            'issues': ['missing_alt', 'missing_dimensions', 'no_lazy_loading'],
            'recommendations': [
                {'issue': 'format', 'suggestion': 'Convert to WebP', 'estimated_savings': '30%'}
            ]
        }
    ]
}
```

---

### 9. Link Analysis

**Files:** `src/seo/technical.py`, `src/seo/redirect_analyzer.py`

| Evaluation | Evidence | Method |
|------------|----------|--------|
| Broken links | Source URL, target URL, status code | Crawl results |
| Redirect chains | Full redirect path | Follow redirects |
| Orphan pages | Link graph | Graph analysis |

**Evidence Quality:** HIGH - Based on actual crawl data.

**Current Storage:**
```python
PageMetadata.internal_links
PageMetadata.external_links
TechnicalIssues.broken_links  # List of (source, target) tuples
RedirectAnalysis.chains  # Full redirect paths
```

---

### 10. Social Meta Tags

**File:** `src/seo/social_analyzer.py`

| Evaluation | Evidence | Method |
|------------|----------|--------|
| Open Graph completeness | Extracted OG tags | HTML meta tag parsing |
| Twitter Card validity | Extracted Twitter tags | HTML meta tag parsing |

**Evidence Quality:** HIGH - Direct extraction from HTML.

**Current Storage:**
```python
PageMetadata.open_graph  # Dict of og:* properties
PageMetadata.twitter_card  # Dict of twitter:* properties
SocialMetaAnalysis.og_score
SocialMetaAnalysis.twitter_score
```

---

### 11. LLM-Based SEO Scoring

**File:** `src/seo/llm.py`

| Output | Evidence | Method |
|--------|----------|--------|
| Overall score | Page metadata summary | LLM inference |
| Title score | Title text | LLM inference |
| Description score | Meta description | LLM inference |
| Content score | First 1000 chars | LLM inference |
| Technical score | Technical metrics | LLM inference |

**Evidence Quality:** LOW - Black-box LLM output.

**Current Storage:**
```python
SEOScore.overall_score
SEOScore.title_score
SEOScore.description_score
SEOScore.content_score
SEOScore.technical_score
```

**CRITICAL: This is a hallucination-prone component.**

**Recommended Enhancement:**
```python
{
    'overall_score': 72,
    'ai_generated': True,
    'model': 'gpt-4',
    'model_version': '2024-01-01',
    'prompt_hash': 'sha256:...',
    'input_summary': {
        'title': 'Example Page Title',
        'title_length': 18,
        'description': 'Meta description text...',
        'description_length': 145,
        'h1_count': 1,
        'word_count': 850
    },
    'reasoning': 'Title is concise but could include primary keyword...',
    'confidence': 'medium',
    'disclaimer': 'AI-generated score. Verify with manual review.'
}
```

---

### 12. LLM-Based Recommendations

**File:** `src/seo/analyzer.py` → `_generate_site_recommendations()`

| Output | Evidence | Method |
|--------|----------|--------|
| ICE scores | Aggregated metrics | LLM inference |
| Priority recommendations | Site summary | LLM inference |
| 30-day action plan | All crawl data | LLM inference |

**Evidence Quality:** LOW - Entirely LLM-generated.

**CRITICAL: This is the highest hallucination risk in the system.**

**Recommended Enhancement:**
```python
{
    'recommendation': 'Fix 23 pages with missing meta descriptions',
    'ai_generated': True,
    'ice_scores': {
        'impact': 8,
        'confidence': 9,
        'ease': 7,
        'composite': 8.0
    },
    'evidence_basis': {
        'metric': 'missing_meta_descriptions',
        'count': 23,
        'percentage': 15.2,
        'source': 'TechnicalIssues.missing_meta_descriptions'
    },
    'validation': {
        'impact_justification': 'Meta descriptions affect CTR in search results',
        'confidence_justification': 'Direct count from crawl data',
        'ease_justification': 'Simple content addition, no technical changes'
    }
}
```

---

## Hallucination Risk Assessment

### Risk Matrix

| Component | Risk Level | Mitigation |
|-----------|------------|------------|
| Technology Detection | Low | Pattern-based, verifiable |
| Technical Issues | Low | Threshold-based, raw data available |
| CWV Estimates | Medium | Label as estimates, show methodology |
| Lighthouse/CrUX | Low | External API, verifiable |
| Content Quality | Medium | Show formula inputs |
| Structured Data | Low | Schema specs as reference |
| **LLM SEO Scores** | **High** | Show inputs, add disclaimers |
| **LLM Recommendations** | **Critical** | Require evidence linking, add disclaimers |

### Mitigation Strategies

1. **Label AI Content**
   - All LLM-generated content must be clearly marked
   - Use visual indicators (icon, badge, border style)

2. **Show Your Work**
   - Display inputs that were provided to the LLM
   - Include any reasoning the LLM provided

3. **Link to Evidence**
   - Every recommendation should link to supporting data
   - Users should be able to verify claims

4. **Confidence Indicators**
   - Display confidence levels where applicable
   - Distinguish between measured vs. estimated values

5. **Validation Hooks**
   - Allow users to mark recommendations as accurate/inaccurate
   - Use feedback to improve prompts

---

## Implementation Guide: Surfacing Evidence

### Data Model Updates

**IMPLEMENTED** in `src/seo/models.py`:

```python
class ConfidenceLevel(str, Enum):
    """Confidence levels for evidence-backed evaluations."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    ESTIMATE = "Estimate"


class EvidenceSourceType(str, Enum):
    """Types of evidence sources."""
    HTML_CONTENT = "html_content"
    HTML_ATTRIBUTE = "html_attribute"
    SCRIPT_SRC = "script_src"
    LINK_HREF = "link_href"
    HTTP_HEADER = "http_header"
    META_TAG = "meta_tag"
    API_RESPONSE = "api_response"
    CALCULATION = "calculation"
    PATTERN_MATCH = "pattern_match"
    LLM_INFERENCE = "llm_inference"
    HEURISTIC = "heuristic"


@dataclass
class EvidenceRecord:
    """Standardized evidence container for all evaluations."""

    # Required fields
    component_id: str          # e.g., 'technology_detection', 'technical_seo'
    finding: str               # e.g., 'Magento/Adobe Commerce', 'missing_meta_description'
    evidence_string: str       # e.g., 'mage/cookies.js', actual meta text
    confidence: ConfidenceLevel
    timestamp: datetime
    source: str                # e.g., 'Lighthouse', 'Pattern Match', 'LLM Heuristic'

    # Optional enrichment fields
    source_type: Optional[EvidenceSourceType] = None
    source_location: Optional[str] = None
    pattern_matched: Optional[str] = None
    threshold: Optional[dict] = None  # {'operator': '<', 'value': 300, 'unit': 'words'}
    measured_value: Optional[Any] = None
    unit: Optional[str] = None
    recommendation: Optional[str] = None
    severity: Optional[str] = None  # 'critical', 'warning', 'info'

    # AI-specific metadata (for hallucination mitigation)
    ai_generated: bool = False
    model_id: Optional[str] = None
    prompt_hash: Optional[str] = None
    reasoning: Optional[str] = None
    input_summary: Optional[dict] = None

    # Factory methods for common patterns
    @classmethod
    def from_pattern_match(cls, ...) -> 'EvidenceRecord': ...

    @classmethod
    def from_threshold_check(cls, ...) -> 'EvidenceRecord': ...

    @classmethod
    def from_api_response(cls, ...) -> 'EvidenceRecord': ...

    @classmethod
    def from_llm(cls, ...) -> 'EvidenceRecord': ...


@dataclass
class EvidenceCollection:
    """Collection of evidence records for a single evaluation.
    Used when multiple pieces of evidence support a single conclusion."""

    finding: str
    component_id: str
    records: list[EvidenceRecord] = field(default_factory=list)
    combined_confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
```

### Report Template Integration

```jinja2
{# Evidence tooltip pattern #}
<span class="evaluation"
      data-evidence="{{ evaluation.evidence | tojson }}"
      data-confidence="{{ evaluation.confidence }}">
    {{ evaluation.conclusion }}
    <button class="evidence-toggle" aria-label="Show evidence">
        <svg><!-- info icon --></svg>
    </button>
</span>

{# Evidence panel (hidden by default) #}
<div class="evidence-panel" hidden>
    <h4>Evidence</h4>
    <dl>
        <dt>Source</dt>
        <dd>{{ evaluation.evidence[0].source_type }}</dd>
        <dt>Raw Value</dt>
        <dd><code>{{ evaluation.evidence[0].raw_value }}</code></dd>
        {% if evaluation.evidence[0].threshold %}
        <dt>Threshold</dt>
        <dd>{{ evaluation.evidence[0].threshold.operator }} {{ evaluation.evidence[0].threshold.value }} {{ evaluation.evidence[0].threshold.unit }}</dd>
        {% endif %}
    </dl>
    {% if evaluation.ai_generated %}
    <p class="ai-disclaimer">This evaluation was generated by AI and should be verified.</p>
    {% endif %}
</div>
```

---

## UI Patterns for Evidence Display

### 1. Inline Indicators

```
Technology: Magento/Adobe Commerce [?]
            └── Tooltip: "Detected via pattern 'mage/' in script src"
```

### 2. Expandable Details

```
┌─────────────────────────────────────────────┐
│ ▸ Missing Meta Descriptions (23 pages)      │
├─────────────────────────────────────────────┤
│ ▾ Missing Meta Descriptions (23 pages)      │
│   Threshold: description.length == 0        │
│   Affected pages:                           │
│   • /products/widget-a                      │
│   • /products/widget-b                      │
│   • /about/team                             │
│   [Show all 23...]                          │
└─────────────────────────────────────────────┘
```

### 3. Evidence Sidebar

```
┌──────────────────┬─────────────────────────┐
│ Main Report      │ Evidence Panel          │
│                  │                         │
│ [Click item] ───►│ Source: HTML parsing    │
│                  │ Location: <head>        │
│                  │ Raw: <title>...</title> │
│                  │ Length: 45 chars        │
│                  │ Threshold: 50-60 chars  │
└──────────────────┴─────────────────────────┘
```

### 4. AI Content Styling

```css
/* Visual distinction for AI-generated content */
.ai-generated {
    border-left: 3px solid #f59e0b;  /* Warning orange */
    background: rgba(245, 158, 11, 0.05);
    padding-left: 1rem;
}

.ai-generated::before {
    content: "AI Generated";
    font-size: 0.75rem;
    color: #f59e0b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.ai-disclaimer {
    font-size: 0.85rem;
    color: #666;
    font-style: italic;
}
```

### 5. Confidence Badges

```html
<span class="confidence confidence-high">High Confidence</span>
<span class="confidence confidence-medium">Medium Confidence</span>
<span class="confidence confidence-low">Low Confidence</span>
<span class="confidence confidence-estimate">Estimated</span>
```

---

## Future Enhancements

### Phase 1: Evidence Capture (Immediate) - **PARTIALLY COMPLETE**

- [x] Update `TechnologyDetector` to capture matched patterns
- [x] Create `EvidenceRecord` dataclass
- [x] Create `EvidenceCollection` dataclass
- [x] Create BDD feature file (`features/evidence_capture.feature`)
- [ ] Add threshold values to all issue detection (technical.py)
- [ ] Store LLM prompt inputs alongside outputs (llm.py)
- [ ] Add `ai_generated` flag to all LLM outputs

### Phase 2: Evidence Storage (Short-term)

- [x] Create `EvidenceRecord` dataclass - **DONE**
- [ ] Update `PageMetadata` to include evidence collections
- [ ] Add evidence fields to database schema
- [ ] Implement evidence serialization for reports
- [ ] Update `TechnicalIssues` to use `EvidenceRecord`

### Phase 3: Evidence Display (Medium-term)

- [ ] Add evidence toggle JS to `ne-branding.js`
- [ ] Create evidence panel CSS styles
- [ ] Update report templates with evidence markup
- [ ] Add AI content visual indicators
- [ ] Implement tooltip evidence display

### Phase 4: Validation & Feedback (Long-term)

- [ ] Add user feedback mechanism for AI recommendations
- [ ] Implement confidence calibration based on feedback
- [ ] Create audit log for evidence trail
- [ ] Add evidence export for compliance/documentation

---

## Appendix: Evidence Fields by Model

### PageMetadata Evidence Fields

| Field | Evidence Type | Notes |
|-------|--------------|-------|
| `title` | Raw extraction | Direct from `<title>` tag |
| `title_length` | Calculation | `len(title)` |
| `description` | Raw extraction | From meta description tag |
| `h1_tags` | Raw extraction | All H1 elements |
| `word_count` | Calculation | Text extraction + counting |
| `load_time` | Measurement | HTTP request timing |
| `technologies` | Pattern matching | See tech detector |
| `lighthouse_*` | External API | Google PSI response |
| `cwv_*_estimate` | Heuristic | Clearly labeled as estimate |

### TechnicalIssues Evidence

All issues include:
- List of affected URLs
- Measured value (where applicable)
- Threshold used for detection

### LLM Outputs Evidence

All LLM outputs should include:
- Input data provided to model
- Model identifier and version
- Prompt template hash
- Generated reasoning (if available)
- `ai_generated: true` flag
