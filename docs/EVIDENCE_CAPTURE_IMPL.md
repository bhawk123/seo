# Implementation Plan: Evidence Capture System

> **Status:** For Review
> **Created:** 2026-02-03
> **Scope:** Phase 2-4 of Evidence Trail System

---

## Executive Summary

This implementation plan extends the evidence capture system (Phase 1 complete) to cover all 20 evaluation components in the SEO crawler. The goal is to provide complete audit trails for all findings, with special emphasis on AI/LLM outputs to mitigate hallucination risks.

### Current State (Phase 1 Complete)
- `EvidenceRecord` and `EvidenceCollection` dataclasses implemented
- Technology Detection captures evidence for 80+ patterns
- BDD feature file created with 17 scenarios

### Target State
- All 20 components capture evidence
- LLM outputs include input summaries and reasoning
- Reports display evidence via tooltips, panels, and AI indicators
- Complete audit trail from raw data to conclusion

---

## Priority Matrix

| Priority | Components | Risk Level | Effort |
|----------|-----------|------------|--------|
| **P0 - Critical** | LLM Analyzer, Main Analyzer (ICE recommendations) | High hallucination risk | High |
| **P1 - High** | Technical SEO, Core Web Vitals, Lab/Field | Core functionality | Medium |
| **P2 - Medium** | Content Quality, Security, Image, Social, Structured Data | User-facing evaluations | Medium |
| **P3 - Lower** | URL Structure, Mobile, International, Crawlability, Redirects, Third-Party, Resource, Console | Supporting analysis | Low |
| **P4 - UI** | Report Generator, Templates | Display layer | Medium |

---

## Epic Overview

| Epic | Name | Components | Stories |
|------|------|------------|---------|
| E1 | LLM Evidence Trail | llm.py, analyzer.py | 6 |
| E2 | Technical SEO Evidence | technical.py | 5 |
| E3 | Performance Evidence | core_web_vitals.py, lab_field_analyzer.py | 4 |
| E4 | Content Quality Evidence | content_quality.py | 3 |
| E5 | Advanced Analyzer Evidence | advanced_analyzer.py (4 analyzers) | 4 |
| E6 | Media & Metadata Evidence | image_analyzer.py, social_analyzer.py, structured_data.py | 4 |
| E7 | Site Structure Evidence | crawlability.py, redirect_analyzer.py, third_party_analyzer.py, resource_analyzer.py | 4 |
| E8 | Report UI Evidence Display | report_generator.py, templates | 5 |

**Total: 8 Epics, 35 Stories**

---

# Epic 1: LLM Evidence Trail (CRITICAL)

> **Priority:** P0 - Critical
> **Risk:** Highest hallucination potential
> **Files:** `src/seo/llm.py`, `src/seo/analyzer.py`

## Rationale

LLM-generated outputs are black-box evaluations with no inherent audit trail. Users cannot verify why a score was assigned or whether a recommendation is based on actual crawl data. This epic addresses the most critical trust gap in the system.

---

## Feature 1.1: LLM SEO Scoring Evidence

**File:** `src/seo/llm.py`

### Story 1.1.1: Capture LLM Input Summary

**As** an SEO analyst
**I want** to see what data was provided to the LLM for scoring
**So that** I can understand the basis for AI-generated scores

**Acceptance Criteria:**
- [ ] LLM scoring captures all inputs sent to the model
- [ ] Input summary includes: title, title_length, description, description_length, h1_count, word_count, content_snippet
- [ ] Input summary is stored alongside the score output
- [ ] Evidence record created with `ai_generated: true`

### Story 1.1.2: Capture LLM Model Metadata

**As** an SEO analyst
**I want** to know which AI model generated a score
**So that** I can assess the reliability of the evaluation

**Acceptance Criteria:**
- [ ] Model identifier captured (e.g., "gpt-4", "claude-3-opus")
- [ ] Model version/timestamp captured when available
- [ ] Prompt template hash stored for reproducibility
- [ ] Evidence record includes `model_id` field

### Story 1.1.3: Extract LLM Reasoning

**As** an SEO analyst
**I want** to see the AI's reasoning for each score
**So that** I can evaluate whether the logic is sound

**Acceptance Criteria:**
- [ ] Prompt updated to request reasoning from LLM
- [ ] Reasoning extracted and stored in evidence record
- [ ] Reasoning is human-readable and references specific data points
- [ ] Evidence record includes `reasoning` field

---

## Feature 1.2: ICE Recommendation Evidence

**File:** `src/seo/analyzer.py` → `_generate_site_recommendations()`

### Story 1.2.1: Link Recommendations to Source Data

**As** an SEO analyst
**I want** each recommendation to link to the crawl data that supports it
**So that** I can verify the recommendation is based on real findings

**Acceptance Criteria:**
- [ ] Each recommendation references the source component (e.g., `technical_seo`)
- [ ] Specific metric name included (e.g., `missing_meta_descriptions`)
- [ ] Actual count/value from crawl data included
- [ ] Evidence record links to supporting `TechnicalIssues` data

### Story 1.2.2: Capture ICE Score Justifications

**As** an SEO analyst
**I want** to see why each ICE score was assigned
**So that** I can evaluate the prioritization logic

**Acceptance Criteria:**
- [ ] Impact score includes justification text
- [ ] Confidence score includes justification text
- [ ] Ease score includes justification text
- [ ] Each justification references verifiable data points
- [ ] Evidence record includes `ice_justification` object

### Story 1.2.3: Enforce Confidence Ceiling for LLM Outputs

**As** an SEO analyst
**I want** LLM-only evaluations to never show "High" confidence
**So that** I understand these require human verification

**Acceptance Criteria:**
- [ ] LLM-only evaluations capped at `ConfidenceLevel.MEDIUM`
- [ ] Evidence record always includes `ai_generated: true` for LLM outputs
- [ ] Validation prevents `confidence: High` when `ai_generated: true`

---

## Feature 1.1-1.2 BDD Scenarios

```gherkin
Feature: LLM Evidence Trail
  As an SEO analyst reviewing AI-generated evaluations
  I want to see the evidence behind LLM outputs
  So that I can verify accuracy and mitigate hallucination risks

  Background:
    Given the SEO analysis tool is configured to use LLM scoring
    And evidence capture is enabled for LLM components

  # ===========================================================================
  # Feature 1.1: LLM SEO Scoring Evidence
  # ===========================================================================

  @llm @evidence @story-1.1.1
  Scenario: LLM scoring captures input summary
    When the tool generates an SEO score using an LLM
    And the page has title "Best Widgets for 2024"
    And the page has 850 words of content
    Then the evidence record should include "ai_generated: true"
    And the evidence record input_summary should include:
      | field             | value                    |
      | title             | Best Widgets for 2024    |
      | title_length      | 23                       |
      | word_count        | 850                      |
    And the input_summary should include the first 1000 characters of content

  @llm @evidence @story-1.1.2
  Scenario: LLM scoring captures model metadata
    When the tool generates an SEO score using "gpt-4"
    Then the evidence record should include model_id "gpt-4"
    And the evidence record should include a prompt_hash
    And the prompt_hash should be a valid SHA-256 hash

  @llm @evidence @story-1.1.3
  Scenario: LLM scoring captures reasoning
    When the tool generates an overall_score of 72
    Then the evidence record should include a non-empty reasoning field
    And the reasoning should reference specific page attributes
    And the reasoning should explain score deductions

  @llm @evidence @story-1.1.3
  Scenario: LLM reasoning references measurable data
    When the tool generates a title_score of 65
    And the reasoning mentions "title length"
    Then the reasoning should include the actual title length value
    And the reasoning should reference the recommended length threshold

  # ===========================================================================
  # Feature 1.2: ICE Recommendation Evidence
  # ===========================================================================

  @llm @evidence @story-1.2.1 @hallucination-risk
  Scenario: Recommendation links to source crawl data
    When the tool generates recommendation "Fix 23 pages with missing meta descriptions"
    Then the evidence record should include:
      | field            | value                       |
      | component_ref    | technical_seo               |
      | metric_name      | missing_meta_descriptions   |
      | metric_value     | 23                          |
    And the metric_value should match TechnicalIssues.missing_descriptions count

  @llm @evidence @story-1.2.1 @hallucination-risk
  Scenario: Recommendation with percentage links to total count
    When the tool generates recommendation "15% of pages have thin content"
    Then the evidence record should include the actual page count
    And the evidence record should include the total pages crawled
    And the calculated percentage should match the stated percentage

  @llm @evidence @story-1.2.2
  Scenario: ICE scores include full justification
    When the tool assigns ICE scores to a recommendation
    And the scores are Impact: 8, Confidence: 9, Ease: 7
    Then the evidence record should include ice_justification with:
      | score_type  | has_justification | references_data |
      | impact      | true              | true            |
      | confidence  | true              | true            |
      | ease        | true              | true            |
    And the impact justification should explain SEO/traffic benefit
    And the confidence justification should cite data source reliability
    And the ease justification should estimate implementation effort

  @llm @evidence @story-1.2.3
  Scenario: LLM-only evaluations cannot have High confidence
    When the tool generates an LLM-only evaluation
    And the LLM suggests confidence should be "High"
    Then the stored confidence level should be "Medium"
    And the evidence record should include ai_generated: true
    And the evidence record should include a confidence_override_reason

  @llm @evidence @story-1.2.3
  Scenario: Mixed evidence can have High confidence
    When the tool generates an evaluation based on LLM analysis
    And the evaluation is corroborated by pattern matching evidence
    Then the stored confidence level may be "High"
    And the evidence record should include multiple evidence sources
    And at least one source should have ai_generated: false
```

---

# Epic 2: Technical SEO Evidence (HIGH)

> **Priority:** P1 - High
> **Risk:** Core functionality, user-facing
> **File:** `src/seo/technical.py`

## Rationale

Technical SEO issues are the most actionable findings in the report. Users need to understand exactly why pages were flagged and what thresholds were applied.

---

## Feature 2.1: Issue Detection Evidence

### Story 2.1.1: Capture Threshold Evidence for All Issues

**As** an SEO analyst
**I want** to see the threshold applied to each issue detection
**So that** I can understand why a page was flagged

**Acceptance Criteria:**
- [ ] Each issue type includes threshold definition
- [ ] Threshold includes operator, value, and unit
- [ ] Measured value stored alongside threshold
- [ ] Evidence record created using `EvidenceRecord.from_threshold_check()`

### Story 2.1.2: Capture Raw Evidence for Content Issues

**As** an SEO analyst
**I want** to see the actual content that triggered an issue
**So that** I can verify the detection is correct

**Acceptance Criteria:**
- [ ] Missing title: evidence shows empty/null title
- [ ] Short description: evidence includes actual description text
- [ ] Thin content: evidence includes word count and sample
- [ ] Multiple H1s: evidence includes all H1 tag texts

### Story 2.1.3: Capture Link Evidence for Broken Links

**As** an SEO analyst
**I want** to see complete link context for broken links
**So that** I can diagnose and fix the issue

**Acceptance Criteria:**
- [ ] Source URL (page containing the link) captured
- [ ] Target URL (broken destination) captured
- [ ] Anchor text captured when available
- [ ] HTTP status code captured when available
- [ ] Link context (surrounding HTML) optionally captured

### Story 2.1.4: Capture Duplicate Detection Evidence

**As** an SEO analyst
**I want** to see all pages sharing duplicate content
**So that** I can decide which to prioritize

**Acceptance Criteria:**
- [ ] Duplicate titles: list all URLs sharing the title
- [ ] Duplicate descriptions: list all URLs sharing the description
- [ ] Canonical conflicts: show conflicting canonical declarations
- [ ] Evidence includes the duplicated text value

### Story 2.1.5: Create Evidence-Enabled Issue Format

**As** a developer
**I want** a standardized evidence format for technical issues
**So that** all issues are consistently structured

**Acceptance Criteria:**
- [ ] `TechnicalIssue` dataclass updated or created
- [ ] Each issue includes `evidence: EvidenceRecord`
- [ ] Backward compatibility with existing `TechnicalIssues` structure
- [ ] Serialization to dict/JSON for report consumption

---

## Feature 2.1 BDD Scenarios

```gherkin
Feature: Technical SEO Issue Evidence
  As an SEO analyst reviewing technical issues
  I want to see the evidence behind each flagged issue
  So that I can verify findings and prioritize fixes

  Background:
    Given the SEO analysis tool has crawled a website
    And evidence capture is enabled for technical SEO

  # ===========================================================================
  # Story 2.1.1: Threshold Evidence
  # ===========================================================================

  @technical @evidence @story-2.1.1
  Scenario: Missing meta description includes threshold evidence
    When the tool identifies a page with a missing meta description
    Then the evidence record should include:
      | field          | value                    |
      | component_id   | technical_seo            |
      | finding        | missing_meta_description |
      | measured_value | null                     |
    And the threshold should specify "description.length == 0"
    And the confidence level should be "High"

  @technical @evidence @story-2.1.1
  Scenario: Short meta description includes length comparison
    When the tool identifies a page with a short meta description
    And the meta description is 85 characters long
    Then the evidence record should include:
      | field          | value          |
      | finding        | short_description |
      | measured_value | 85             |
      | unit           | characters     |
    And the threshold should specify "< 120 characters"

  @technical @evidence @story-2.1.1
  Scenario: Long meta description includes length evidence
    When the tool identifies a page with a long meta description
    And the meta description is 185 characters long
    Then the evidence record should include measured_value "185"
    And the threshold should specify "> 160 characters"
    And the unit should be "characters"

  @technical @evidence @story-2.1.1
  Scenario: Thin content includes word count evidence
    When the tool identifies a page with thin content
    And the page contains 187 words
    Then the evidence record should include:
      | field          | value        |
      | finding        | thin_content |
      | measured_value | 187          |
      | unit           | words        |
    And the threshold should specify "< 300 words"

  @technical @evidence @story-2.1.1
  Scenario: Slow page includes load time evidence
    When the tool identifies a slow-loading page
    And the page load time is 4.2 seconds
    Then the evidence record should include:
      | field          | value     |
      | finding        | slow_page |
      | measured_value | 4.2       |
      | unit           | seconds   |
    And the threshold should specify "> 3.0 seconds"

  # ===========================================================================
  # Story 2.1.2: Raw Content Evidence
  # ===========================================================================

  @technical @evidence @story-2.1.2
  Scenario: Short description evidence includes actual text
    When the tool identifies a short meta description
    And the description is "Buy our products today"
    Then the evidence_string should be "Buy our products today"
    And the measured_value should be 22

  @technical @evidence @story-2.1.2
  Scenario: Multiple H1 evidence includes all H1 texts
    When the tool identifies a page with multiple H1 tags
    And the H1 tags are "Welcome" and "About Us"
    Then the evidence_string should include "Welcome"
    And the evidence_string should include "About Us"
    And the measured_value should be 2

  @technical @evidence @story-2.1.2
  Scenario: Missing H1 evidence shows empty state
    When the tool identifies a page with no H1 tag
    Then the evidence record should include:
      | field          | value      |
      | finding        | missing_h1 |
      | measured_value | 0          |
    And the evidence_string should indicate "No H1 tag found"

  # ===========================================================================
  # Story 2.1.3: Broken Link Evidence
  # ===========================================================================

  @technical @evidence @story-2.1.3
  Scenario: Broken link includes source and target URLs
    When the tool identifies a broken internal link
    And the link is from "/products" to "/discontinued-item"
    Then the evidence record should include:
      | field           | value              |
      | finding         | broken_link        |
      | source_location | /products          |
    And the evidence_string should include "/discontinued-item"

  @technical @evidence @story-2.1.3
  Scenario: Broken link includes HTTP status when available
    When the tool identifies a broken link returning 404
    Then the evidence record should include measured_value 404
    And the unit should be "http_status"

  @technical @evidence @story-2.1.3
  Scenario: Broken link includes anchor text
    When the tool identifies a broken link with anchor text "Learn More"
    Then the evidence record should include the anchor text "Learn More"
    And this aids in identifying the link visually

  # ===========================================================================
  # Story 2.1.4: Duplicate Detection Evidence
  # ===========================================================================

  @technical @evidence @story-2.1.4
  Scenario: Duplicate titles lists all affected URLs
    When the tool identifies duplicate titles
    And pages "/page-a" and "/page-b" share the title "Welcome"
    Then the evidence record should include finding "duplicate_title"
    And the evidence_string should be "Welcome"
    And the evidence should list affected URLs:
      | url      |
      | /page-a  |
      | /page-b  |

  @technical @evidence @story-2.1.4
  Scenario: Duplicate descriptions lists all affected URLs
    When the tool identifies duplicate meta descriptions
    And 5 pages share the same description
    Then the evidence record should include finding "duplicate_description"
    And the evidence should list all 5 affected URLs
    And the measured_value should be 5

  # ===========================================================================
  # Story 2.1.5: Evidence-Enabled Issue Format
  # ===========================================================================

  @technical @evidence @story-2.1.5
  Scenario: Technical issue includes evidence record
    When any technical issue is identified
    Then the issue should include an evidence field
    And the evidence field should be an EvidenceRecord
    And the evidence should be serializable to JSON

  @technical @evidence @story-2.1.5
  Scenario: Issue severity derives from evidence
    When a technical issue has measured_value exceeding threshold by 50%+
    Then the severity should be "critical"
    When measured_value exceeds threshold by 20-50%
    Then the severity should be "warning"
    When measured_value barely exceeds threshold
    Then the severity should be "info"
```

---

# Epic 3: Performance Evidence (HIGH)

> **Priority:** P1 - High
> **Risk:** Estimates often confused with measurements
> **Files:** `src/seo/core_web_vitals.py`, `src/seo/lab_field_analyzer.py`

## Rationale

Performance metrics come from multiple sources with different reliability levels. Users need to clearly distinguish between estimates, lab data, and field data.

---

## Feature 3.1: Core Web Vitals Estimation Evidence

**File:** `src/seo/core_web_vitals.py`

### Story 3.1.1: Label All CWV as Estimates

**As** an SEO analyst
**I want** CWV metrics to be clearly labeled as estimates
**So that** I don't confuse them with real measurements

**Acceptance Criteria:**
- [ ] All CWV evidence records include `is_estimate: true`
- [ ] Estimation methodology documented in evidence
- [ ] Contributing factors listed with values
- [ ] Confidence level set to `ESTIMATE`

### Story 3.1.2: Capture LCP Estimation Factors

**As** an SEO analyst
**I want** to see what factors contributed to LCP estimate
**So that** I can identify optimization opportunities

**Acceptance Criteria:**
- [ ] Response time contribution captured
- [ ] Render-blocking resource count captured
- [ ] Render-blocking penalty calculation shown
- [ ] Formula: `LCP_estimate = response_time + (blocking_count * penalty)`

---

## Feature 3.2: Lab vs Field Data Provenance

**File:** `src/seo/lab_field_analyzer.py`

### Story 3.2.1: Label Data Source for Each Metric

**As** an SEO analyst
**I want** to know whether a metric is lab or field data
**So that** I understand its reliability

**Acceptance Criteria:**
- [ ] Lab metrics labeled with source "lighthouse"
- [ ] Field metrics labeled with source "crux"
- [ ] Each metric includes measurement timestamp
- [ ] API version captured for external data

### Story 3.2.2: Capture Lab/Field Gap Evidence

**As** an SEO analyst
**I want** to see when lab and field metrics significantly differ
**So that** I can investigate discrepancies

**Acceptance Criteria:**
- [ ] Gap percentage calculated and stored
- [ ] Gap threshold (25%) documented
- [ ] Evidence includes both lab and field values
- [ ] Recommendation generated for significant gaps

---

## Feature 3.1-3.2 BDD Scenarios

```gherkin
Feature: Performance Metrics Evidence
  As an SEO analyst reviewing performance data
  I want to understand the source and reliability of metrics
  So that I can make informed optimization decisions

  Background:
    Given the SEO analysis tool has analyzed page performance
    And evidence capture is enabled for performance components

  # ===========================================================================
  # Story 3.1.1: CWV Estimation Labels
  # ===========================================================================

  @performance @evidence @story-3.1.1
  Scenario: LCP estimate is clearly labeled
    When the tool estimates LCP for a page
    Then the evidence record should include:
      | field         | value          |
      | finding       | lcp_estimate   |
      | confidence    | Estimate       |
    And the evidence should include is_estimate: true
    And the evidence should include estimation_methodology

  @performance @evidence @story-3.1.1
  Scenario: INP estimate includes methodology
    When the tool estimates INP for a page
    Then the evidence should include:
      | field                  | value                    |
      | estimation_methodology | blocking_script_heuristic |
    And the methodology description should be human-readable

  @performance @evidence @story-3.1.1
  Scenario: CLS risk assessment shows contributing elements
    When the tool identifies CLS risk factors
    And 3 images lack width/height attributes
    Then the evidence should include:
      | field          | value              |
      | finding        | cls_risk           |
      | measured_value | 3                  |
      | unit           | elements_at_risk   |
    And the evidence should list the specific image sources

  # ===========================================================================
  # Story 3.1.2: LCP Estimation Factors
  # ===========================================================================

  @performance @evidence @story-3.1.2
  Scenario: LCP estimate shows response time contribution
    When the tool estimates LCP at 2800ms
    And the response time was 1200ms
    And 3 render-blocking resources added 1600ms penalty
    Then the evidence should include contributing_factors:
      | factor                    | value | unit |
      | response_time             | 1200  | ms   |
      | render_blocking_penalty   | 1600  | ms   |
    And the evidence should show the formula used

  @performance @evidence @story-3.1.2
  Scenario: LCP estimation shows render-blocking resource count
    When the tool identifies render-blocking resources
    And 5 scripts and 2 stylesheets block rendering
    Then the evidence should include:
      | field                   | value |
      | blocking_scripts        | 5     |
      | blocking_stylesheets    | 2     |
      | total_blocking_resources| 7     |

  # ===========================================================================
  # Story 3.2.1: Lab vs Field Data Source
  # ===========================================================================

  @performance @evidence @story-3.2.1
  Scenario: Lab metric includes Lighthouse source
    When the tool reports Lighthouse performance score
    Then the evidence record should include:
      | field      | value                      |
      | source     | google_pagespeed_insights  |
      | source_type| api_response               |
    And the evidence should include api_timestamp
    And the evidence should include lighthouse_version

  @performance @evidence @story-3.2.1
  Scenario: Field metric includes CrUX source
    When the tool reports CrUX LCP percentile
    Then the evidence record should include:
      | field      | value |
      | source     | crux  |
      | source_type| api_response |
    And the evidence should include data_freshness_date

  @performance @evidence @story-3.2.1
  Scenario: Mixed metrics clearly distinguish sources
    When the tool compares lab and field LCP
    Then the lab LCP evidence should have source "lighthouse"
    And the field LCP evidence should have source "crux"
    And each should have independent timestamps

  # ===========================================================================
  # Story 3.2.2: Lab/Field Gap Evidence
  # ===========================================================================

  @performance @evidence @story-3.2.2
  Scenario: Significant gap is flagged with evidence
    When lab LCP is 2.0s and field LCP is 3.5s
    Then the gap should be calculated as 75%
    And the evidence should include:
      | field          | value    |
      | finding        | lab_field_gap |
      | measured_value | 75       |
      | unit           | percent  |
    And the threshold should specify "> 25%"

  @performance @evidence @story-3.2.2
  Scenario: Gap evidence includes both metric values
    When the tool identifies a lab/field gap
    Then the evidence should include lab_value and field_value
    And both values should have their source labeled
    And a recommendation should explain potential causes
```

---

# Epic 4: Content Quality Evidence (MEDIUM)

> **Priority:** P2 - Medium
> **Risk:** Algorithm accuracy varies
> **File:** `src/seo/content_quality.py`

## Rationale

Content quality metrics use formulas that users may want to verify. Showing the formula inputs builds trust in the calculations.

---

## Feature 4.1: Readability Score Evidence

### Story 4.1.1: Capture Readability Formula Inputs

**As** an SEO analyst
**I want** to see the components of the readability calculation
**So that** I can verify the score accuracy

**Acceptance Criteria:**
- [ ] Total words captured
- [ ] Total sentences captured
- [ ] Total syllables captured
- [ ] Average words per sentence calculated
- [ ] Average syllables per word calculated
- [ ] Formula name identified (Flesch Reading Ease)

### Story 4.1.2: Capture Keyword Density Evidence

**As** an SEO analyst
**I want** to see how keyword density was calculated
**So that** I can verify the analysis

**Acceptance Criteria:**
- [ ] Total word count captured
- [ ] Keyword occurrence counts captured
- [ ] Stop words excluded count shown
- [ ] Density calculation formula shown

### Story 4.1.3: Capture Difficult Word Evidence

**As** an SEO analyst
**I want** to see which words were classified as difficult
**So that** I can evaluate content complexity

**Acceptance Criteria:**
- [ ] Difficult word count captured
- [ ] Sample difficult words listed (top 10)
- [ ] Syllable threshold documented (3+ syllables)
- [ ] Percentage of difficult words calculated

---

## Feature 4.1 BDD Scenarios

```gherkin
Feature: Content Quality Evidence
  As an SEO analyst reviewing content metrics
  I want to see how quality scores were calculated
  So that I can verify the analysis accuracy

  Background:
    Given the SEO analysis tool has analyzed page content
    And evidence capture is enabled for content quality

  # ===========================================================================
  # Story 4.1.1: Readability Formula Inputs
  # ===========================================================================

  @content @evidence @story-4.1.1
  Scenario: Readability score shows formula components
    When the tool calculates a readability score of 65.2
    Then the evidence record should include:
      | field           | value               |
      | finding         | readability_score   |
      | measured_value  | 65.2                |
      | formula         | flesch_reading_ease |
    And the formula_components should include:
      | component              | value |
      | total_words            | 850   |
      | total_sentences        | 42    |
      | total_syllables        | 1230  |
      | avg_words_per_sentence | 20.2  |
      | avg_syllables_per_word | 1.45  |

  @content @evidence @story-4.1.1
  Scenario: Readability grade shows derivation
    When the tool assigns readability grade "8th Grade"
    And the readability score is 65.2
    Then the evidence should include the grade mapping table reference
    And the evidence should show which range 65.2 falls into

  # ===========================================================================
  # Story 4.1.2: Keyword Density Evidence
  # ===========================================================================

  @content @evidence @story-4.1.2
  Scenario: Keyword density shows calculation basis
    When the tool calculates keyword density for "widget"
    And "widget" appears 17 times in 850 words
    Then the evidence should include:
      | field            | value   |
      | finding          | keyword_density |
      | keyword          | widget  |
      | occurrences      | 17      |
      | total_words      | 850     |
      | density_percent  | 2.0     |

  @content @evidence @story-4.1.2
  Scenario: Stop word exclusion is documented
    When the tool calculates keyword density
    And 150 stop words were excluded
    Then the evidence should include:
      | field               | value |
      | stop_words_excluded | 150   |
      | analyzed_word_count | 700   |

  # ===========================================================================
  # Story 4.1.3: Difficult Word Evidence
  # ===========================================================================

  @content @evidence @story-4.1.3
  Scenario: Difficult word count shows threshold
    When the tool identifies 45 difficult words
    Then the evidence should include:
      | field            | value          |
      | finding          | difficult_words |
      | measured_value   | 45             |
      | threshold        | >= 3 syllables |

  @content @evidence @story-4.1.3
  Scenario: Sample difficult words are listed
    When the tool identifies difficult words
    Then the evidence should include a sample_words list
    And the sample should contain up to 10 words
    And each word should have its syllable count
```

---

# Epic 5: Advanced Analyzer Evidence (MEDIUM)

> **Priority:** P2-P3
> **Files:** `src/seo/advanced_analyzer.py` (Security, URL, Mobile, International)

## Rationale

The advanced analyzer contains four distinct analyzers. Each needs appropriate evidence capture for its domain.

---

## Feature 5.1: Security Analysis Evidence

### Story 5.1.1: Capture Security Header Evidence

**As** an SEO analyst
**I want** to see which security headers are present/missing
**So that** I can assess and improve site security

**Acceptance Criteria:**
- [ ] Each checked header listed with present/missing status
- [ ] Raw header value captured when present
- [ ] Points allocated per header documented
- [ ] Security score calculation shown

---

## Feature 5.2: URL Structure Evidence

### Story 5.2.1: Capture URL Quality Evidence

**As** an SEO analyst
**I want** to see why URLs were flagged
**So that** I can improve URL structure

**Acceptance Criteria:**
- [ ] URL length measured and compared to threshold (75 chars)
- [ ] Special character presence detected
- [ ] Path depth calculated
- [ ] Keyword presence assessed

---

## Feature 5.3: Mobile SEO Evidence

### Story 5.3.1: Capture Mobile Optimization Evidence

**As** an SEO analyst
**I want** to see mobile optimization checks performed
**So that** I can improve mobile experience

**Acceptance Criteria:**
- [ ] Viewport meta tag presence captured
- [ ] Viewport content value captured
- [ ] Mobile-specific issues listed

---

## Feature 5.4: International SEO Evidence

### Story 5.4.1: Capture Internationalization Evidence

**As** an SEO analyst
**I want** to see language/locale configuration
**So that** I can improve international targeting

**Acceptance Criteria:**
- [ ] Lang attribute value captured
- [ ] Hreflang tags listed
- [ ] Language/region targeting assessed

---

## Feature 5.1-5.4 BDD Scenarios

```gherkin
Feature: Advanced Analyzer Evidence
  As an SEO analyst reviewing advanced analysis
  I want to see evidence for security, URL, mobile, and international checks
  So that I can address issues with full context

  Background:
    Given the SEO analysis tool has performed advanced analysis
    And evidence capture is enabled for advanced analyzers

  # ===========================================================================
  # Story 5.1.1: Security Header Evidence
  # ===========================================================================

  @security @evidence @story-5.1.1
  Scenario: Security headers show presence status
    When the tool analyzes security headers
    Then the evidence should list each header with status:
      | header                      | status  | points |
      | Strict-Transport-Security   | present | 20     |
      | X-Content-Type-Options      | missing | 0      |
      | X-Frame-Options             | present | 10     |
      | Content-Security-Policy     | missing | 0      |

  @security @evidence @story-5.1.1
  Scenario: Present headers include raw value
    When the tool finds "Strict-Transport-Security" header
    And the value is "max-age=31536000; includeSubDomains"
    Then the evidence_string should include the raw value
    And a recommendation may suggest adding "preload"

  @security @evidence @story-5.1.1
  Scenario: Security score calculation is shown
    When HTTPS is present (40 pts) and 2 headers present (30 pts)
    Then the evidence should show:
      | component        | points |
      | https            | 40     |
      | security_headers | 30     |
      | total_score      | 70     |

  # ===========================================================================
  # Story 5.2.1: URL Quality Evidence
  # ===========================================================================

  @url @evidence @story-5.2.1
  Scenario: Long URL is flagged with measurement
    When the tool identifies a URL with 92 characters
    Then the evidence should include:
      | field          | value     |
      | finding        | url_too_long |
      | measured_value | 92        |
      | unit           | characters |
      | threshold      | > 75      |

  @url @evidence @story-5.2.1
  Scenario: URL depth is calculated
    When the tool analyzes URL "/products/category/subcategory/item"
    Then the evidence should include:
      | field          | value |
      | path_depth     | 4     |
    And recommendation may suggest flattening structure

  @url @evidence @story-5.2.1
  Scenario: Special characters are identified
    When the tool finds URL with encoded characters "%20"
    Then the evidence should flag "contains_encoded_characters"
    And the specific characters should be listed

  # ===========================================================================
  # Story 5.3.1: Mobile Optimization Evidence
  # ===========================================================================

  @mobile @evidence @story-5.3.1
  Scenario: Viewport meta tag presence captured
    When the tool finds viewport meta tag
    And the content is "width=device-width, initial-scale=1"
    Then the evidence should include:
      | field          | value                                |
      | finding        | viewport_present                     |
      | evidence_string| width=device-width, initial-scale=1  |

  @mobile @evidence @story-5.3.1
  Scenario: Missing viewport is flagged
    When the tool finds no viewport meta tag
    Then the evidence should include:
      | field    | value            |
      | finding  | viewport_missing |
      | severity | critical         |

  # ===========================================================================
  # Story 5.4.1: International SEO Evidence
  # ===========================================================================

  @international @evidence @story-5.4.1
  Scenario: Lang attribute captured
    When the tool finds lang="en-US" attribute
    Then the evidence should include:
      | field          | value  |
      | finding        | lang_attribute |
      | evidence_string| en-US  |

  @international @evidence @story-5.4.1
  Scenario: Hreflang tags listed
    When the tool finds hreflang tags for en, es, fr
    Then the evidence should list all hreflang configurations:
      | hreflang | href                        |
      | en       | https://example.com/        |
      | es       | https://example.com/es/     |
      | fr       | https://example.com/fr/     |

  @international @evidence @story-5.4.1
  Scenario: Missing hreflang for detected languages
    When content appears in multiple languages
    And hreflang tags are not configured
    Then the evidence should flag "missing_hreflang"
    And recommendation should list detected languages
```

---

# Epic 6: Media & Metadata Evidence (MEDIUM)

> **Priority:** P2
> **Files:** `src/seo/image_analyzer.py`, `src/seo/social_analyzer.py`, `src/seo/structured_data.py`

## Rationale

Media and metadata analysis provides concrete, verifiable findings that directly impact SEO and social sharing.

---

## Feature 6.1: Image Analysis Evidence

### Story 6.1.1: Capture Image Optimization Evidence

**As** an SEO analyst
**I want** to see specific image issues with full details
**So that** I can optimize images effectively

**Acceptance Criteria:**
- [ ] Each image issue includes the image source URL
- [ ] Format detection shows detected vs recommended format
- [ ] Missing alt text includes image src for identification
- [ ] Missing dimensions includes image src
- [ ] Potential savings estimation shows calculation basis

---

## Feature 6.2: Social Meta Evidence

### Story 6.2.1: Capture Social Tag Evidence

**As** an SEO analyst
**I want** to see which social tags are present/missing
**So that** I can optimize social sharing

**Acceptance Criteria:**
- [ ] Each OG property checked with status
- [ ] Each Twitter Card property checked with status
- [ ] Raw tag values captured
- [ ] Score calculation shown

---

## Feature 6.3: Structured Data Evidence

### Story 6.3.1: Capture Schema Validation Evidence

**As** an SEO analyst
**I want** to see structured data validation details
**So that** I can fix schema errors

**Acceptance Criteria:**
- [ ] Detected schema types listed
- [ ] Validation errors include field path
- [ ] Rich result eligibility shows requirements
- [ ] Raw JSON-LD/Microdata captured

---

## Feature 6.1-6.3 BDD Scenarios

```gherkin
Feature: Media and Metadata Evidence
  As an SEO analyst reviewing media and metadata
  I want detailed evidence for image, social, and schema findings
  So that I can optimize these elements effectively

  Background:
    Given the SEO analysis tool has analyzed media and metadata
    And evidence capture is enabled for media components

  # ===========================================================================
  # Story 6.1.1: Image Optimization Evidence
  # ===========================================================================

  @image @evidence @story-6.1.1
  Scenario: Image format recommendation includes evidence
    When the tool identifies a JPEG image suitable for WebP
    Then the evidence should include:
      | field            | value           |
      | finding          | format_upgrade  |
      | current_format   | jpeg            |
      | recommended      | webp            |
      | image_src        | /images/hero.jpg |
      | estimated_savings| 30%             |

  @image @evidence @story-6.1.1
  Scenario: Missing alt text includes image identifier
    When the tool finds image without alt text
    And the image src is "/images/product-123.jpg"
    Then the evidence should include:
      | field          | value                   |
      | finding        | missing_alt             |
      | source_location| /images/product-123.jpg |

  @image @evidence @story-6.1.1
  Scenario: Missing dimensions shows CLS risk
    When the tool finds image without width/height
    Then the evidence should include:
      | field          | value             |
      | finding        | missing_dimensions |
      | severity       | warning           |
    And the evidence should reference CLS risk

  # ===========================================================================
  # Story 6.2.1: Social Tag Evidence
  # ===========================================================================

  @social @evidence @story-6.2.1
  Scenario: Open Graph tags show completeness
    When the tool analyzes Open Graph tags
    Then the evidence should list each tag with status:
      | property     | status  | value                    |
      | og:title     | present | Page Title               |
      | og:description| present| Description text...      |
      | og:image     | present | https://example.com/img  |
      | og:url       | missing | null                     |
      | og:type      | missing | null                     |

  @social @evidence @story-6.2.1
  Scenario: Twitter Card scoring shows calculation
    When the tool calculates Twitter Card score of 75
    Then the evidence should include score breakdown:
      | property      | status  | points |
      | twitter:card  | present | 25     |
      | twitter:title | present | 25     |
      | twitter:description | present | 25 |
      | twitter:image | missing | 0      |

  @social @evidence @story-6.2.1
  Scenario: Invalid og:image URL is flagged
    When og:image is "/images/share.jpg" (relative URL)
    Then the evidence should include:
      | field    | value                |
      | finding  | invalid_og_image_url |
      | issue    | must_be_absolute_url |

  # ===========================================================================
  # Story 6.3.1: Schema Validation Evidence
  # ===========================================================================

  @schema @evidence @story-6.3.1
  Scenario: Schema type detection includes raw JSON-LD
    When the tool detects a Product schema
    Then the evidence should include:
      | field       | value   |
      | finding     | schema_detected |
      | schema_type | Product |
    And the evidence_string should contain the raw JSON-LD

  @schema @evidence @story-6.3.1
  Scenario: Validation error includes field path
    When the Product schema is missing "price" field
    Then the evidence should include:
      | field         | value                    |
      | finding       | schema_validation_error  |
      | schema_type   | Product                  |
      | missing_field | price                    |
      | spec_reference| schema.org/Product       |

  @schema @evidence @story-6.3.1
  Scenario: Rich result eligibility shows requirements
    When Product schema is eligible for rich results
    And it has name, image, price, and availability
    Then the evidence should include:
      | field            | value |
      | rich_result_eligible | true |
    And the evidence should list the satisfied requirements
```

---

# Epic 7: Site Structure Evidence (LOWER)

> **Priority:** P3
> **Files:** `src/seo/crawlability.py`, `src/seo/redirect_analyzer.py`, `src/seo/third_party_analyzer.py`, `src/seo/resource_analyzer.py`

## Rationale

Site structure analysis provides supporting data for the main findings. Evidence capture here adds depth to the audit trail.

---

## Feature 7.1: Crawlability Evidence

### Story 7.1.1: Capture Robots.txt Evidence

**As** an SEO analyst
**I want** to see robots.txt analysis details
**So that** I can verify crawl configuration

**Acceptance Criteria:**
- [ ] Robots.txt presence/absence captured
- [ ] Disallow rules listed
- [ ] Sitemap references captured
- [ ] Issues flagged with specific rule

---

## Feature 7.2: Redirect Evidence

### Story 7.2.1: Capture Redirect Chain Evidence

**As** an SEO analyst
**I want** to see full redirect chains
**So that** I can identify optimization opportunities

**Acceptance Criteria:**
- [ ] Full redirect path captured (hop by hop)
- [ ] Status code for each hop
- [ ] Time per hop (estimated)
- [ ] Total chain length

---

## Feature 7.3: Third-Party Evidence

### Story 7.3.1: Capture Third-Party Impact Evidence

**As** an SEO analyst
**I want** to see third-party resource details
**So that** I can evaluate performance impact

**Acceptance Criteria:**
- [ ] Each domain categorized (Analytics, Ads, CDN, etc.)
- [ ] Request count per domain
- [ ] Byte size per category
- [ ] High-impact domains flagged

---

## Feature 7.4: Resource Weight Evidence

### Story 7.4.1: Capture Page Weight Evidence

**As** an SEO analyst
**I want** to see page weight breakdown
**So that** I can identify bloat

**Acceptance Criteria:**
- [ ] Weight by resource type (HTML, CSS, JS, Images, Fonts)
- [ ] Total page weight calculated
- [ ] Comparison to thresholds
- [ ] Bloated pages flagged with specific resource

---

## Feature 7.1-7.4 BDD Scenarios

```gherkin
Feature: Site Structure Evidence
  As an SEO analyst reviewing site structure
  I want evidence for crawlability, redirects, third-party, and resource analysis
  So that I can optimize site architecture

  Background:
    Given the SEO analysis tool has analyzed site structure
    And evidence capture is enabled for structure components

  # ===========================================================================
  # Story 7.1.1: Robots.txt Evidence
  # ===========================================================================

  @crawlability @evidence @story-7.1.1
  Scenario: Robots.txt rules are captured
    When the tool parses robots.txt
    And it contains "Disallow: /admin/"
    Then the evidence should include:
      | field          | value      |
      | finding        | disallow_rule |
      | evidence_string| /admin/    |
      | user_agent     | *          |

  @crawlability @evidence @story-7.1.1
  Scenario: Sitemap references are captured
    When the tool finds sitemap reference in robots.txt
    And the sitemap URL is "https://example.com/sitemap.xml"
    Then the evidence should include:
      | field          | value                           |
      | finding        | sitemap_reference               |
      | evidence_string| https://example.com/sitemap.xml |

  # ===========================================================================
  # Story 7.2.1: Redirect Chain Evidence
  # ===========================================================================

  @redirect @evidence @story-7.2.1
  Scenario: Redirect chain shows full path
    When the tool identifies a redirect chain
    And the chain is: /old → /new → /final
    Then the evidence should include the full chain:
      | hop | url    | status |
      | 1   | /old   | 301    |
      | 2   | /new   | 302    |
      | 3   | /final | 200    |

  @redirect @evidence @story-7.2.1
  Scenario: Long redirect chain is flagged
    When the redirect chain has 5 hops
    And the threshold is 4 hops
    Then the evidence should include:
      | field          | value           |
      | finding        | long_redirect_chain |
      | measured_value | 5               |
      | threshold      | > 4 hops        |

  # ===========================================================================
  # Story 7.3.1: Third-Party Impact Evidence
  # ===========================================================================

  @third-party @evidence @story-7.3.1
  Scenario: Third-party domains are categorized
    When the tool analyzes third-party requests
    Then the evidence should categorize domains:
      | domain                | category  | requests | bytes  |
      | google-analytics.com  | analytics | 3        | 45KB   |
      | doubleclick.net       | ads       | 8        | 120KB  |
      | cloudflare.com        | cdn       | 5        | 200KB  |

  @third-party @evidence @story-7.3.1
  Scenario: High-impact domain is flagged
    When a third-party domain accounts for >10% of page weight
    Then the evidence should include:
      | field          | value              |
      | finding        | high_impact_domain |
      | domain         | tracking.example   |
      | percentage     | 15                 |

  # ===========================================================================
  # Story 7.4.1: Page Weight Evidence
  # ===========================================================================

  @resource @evidence @story-7.4.1
  Scenario: Page weight breakdown by type
    When the tool analyzes page weight
    Then the evidence should include breakdown:
      | type   | bytes   |
      | html   | 45KB    |
      | css    | 120KB   |
      | js     | 450KB   |
      | images | 800KB   |
      | fonts  | 150KB   |
      | total  | 1565KB  |

  @resource @evidence @story-7.4.1
  Scenario: Bloated JS is flagged
    When JavaScript size is 850KB
    And the threshold is 500KB
    Then the evidence should include:
      | field          | value      |
      | finding        | bloated_js |
      | measured_value | 850        |
      | unit           | KB         |
      | threshold      | > 500 KB   |
```

---

# Epic 8: Report UI Evidence Display (UI)

> **Priority:** P4 - UI Layer
> **Files:** `src/seo/report_generator.py`, `templates/report.html`

## Rationale

Evidence capture is meaningless without proper display. This epic focuses on surfacing evidence to users through intuitive UI patterns.

---

## Feature 8.1: Evidence Tooltips

### Story 8.1.1: Implement Evidence Tooltip on Hover

**As** an SEO analyst viewing a report
**I want** to see evidence summary on hover
**So that** I can quickly verify findings

**Acceptance Criteria:**
- [ ] Tooltip appears on hover over evidence-enabled elements
- [ ] Tooltip shows confidence level
- [ ] Tooltip shows source type
- [ ] Tooltip indicates if AI-generated
- [ ] Tooltip is accessible (keyboard navigation)

---

## Feature 8.2: Evidence Panels

### Story 8.2.1: Implement Expandable Evidence Panel

**As** an SEO analyst viewing a report
**I want** to expand full evidence details
**So that** I can deeply inspect findings

**Acceptance Criteria:**
- [ ] Toggle button expands evidence panel
- [ ] Panel shows source type and location
- [ ] Panel shows raw evidence value
- [ ] Panel shows thresholds when applicable
- [ ] Panel collapses on second click

---

## Feature 8.3: AI Content Indicators

### Story 8.3.1: Style AI-Generated Content Distinctly

**As** an SEO analyst viewing a report
**I want** AI-generated content to be visually distinct
**So that** I know which findings require verification

**Acceptance Criteria:**
- [ ] AI-generated sections have orange left border
- [ ] AI badge/label displayed
- [ ] Disclaimer text included
- [ ] Consistent styling across all AI content

---

## Feature 8.4: Evidence Data Integration

### Story 8.4.1: Pass Evidence to Report Template

**As** a developer
**I want** evidence data available in templates
**So that** I can render evidence UI

**Acceptance Criteria:**
- [ ] Evidence collections serialized to JSON
- [ ] Template context includes evidence data
- [ ] Evidence accessible per-finding
- [ ] Backward compatible with evidence-free data

### Story 8.4.2: Implement Evidence Toggle JavaScript

**As** a developer
**I want** evidence toggle functionality in `ne-branding.js`
**So that** evidence panels work interactively

**Acceptance Criteria:**
- [ ] `initEvidencePanels()` function created
- [ ] Click handlers for evidence toggles
- [ ] Smooth expand/collapse animation
- [ ] Keyboard accessibility (Enter/Space to toggle)

---

## Feature 8.1-8.4 BDD Scenarios

```gherkin
Feature: Report Evidence Display
  As an SEO analyst viewing HTML reports
  I want evidence to be accessible and clearly displayed
  So that I can verify findings and understand AI involvement

  Background:
    Given a generated HTML report with evidence-enabled evaluations
    And the report uses NE branding

  # ===========================================================================
  # Story 8.1.1: Evidence Tooltips
  # ===========================================================================

  @report @ui @story-8.1.1
  Scenario: Evidence tooltip appears on hover
    When the user hovers over an evaluation result
    Then a tooltip should appear within 200ms
    And the tooltip should display the evidence summary
    And the tooltip should include the confidence level

  @report @ui @story-8.1.1
  Scenario: Tooltip indicates AI-generated content
    When the user hovers over an AI-generated evaluation
    Then the tooltip should display "AI Generated" indicator
    And the tooltip should show the model identifier
    And the tooltip should include a verification reminder

  @report @ui @story-8.1.1
  Scenario: Tooltip is keyboard accessible
    When the user focuses an evaluation using Tab key
    Then the tooltip should appear on focus
    And the tooltip should remain visible while focused
    And the tooltip should hide when focus moves away

  # ===========================================================================
  # Story 8.2.1: Evidence Panels
  # ===========================================================================

  @report @ui @story-8.2.1
  Scenario: Evidence panel expands on click
    When the user clicks the evidence toggle button
    Then the evidence panel should expand with animation
    And the panel should show the source type
    And the panel should show the raw evidence value
    And the panel should show any applicable thresholds

  @report @ui @story-8.2.1
  Scenario: Evidence panel collapses on second click
    Given the evidence panel is expanded
    When the user clicks the toggle button again
    Then the panel should collapse with animation
    And the toggle icon should rotate back

  @report @ui @story-8.2.1
  Scenario: Evidence panel shows threshold comparison
    Given a technical issue with threshold evidence
    When the user expands the evidence panel
    Then the panel should show the measured value
    And the panel should show the threshold
    And the panel should show the unit
    And a visual indicator should show pass/fail status

  # ===========================================================================
  # Story 8.3.1: AI Content Indicators
  # ===========================================================================

  @report @ui @story-8.3.1
  Scenario: AI-generated sections have distinct styling
    When the report includes LLM-based evaluations
    Then AI-generated sections should have class "ai-generated"
    And the sections should have an orange left border (#f59e0b)
    And the sections should have a subtle warning background

  @report @ui @story-8.3.1
  Scenario: AI badge is displayed
    When an evaluation is AI-generated
    Then an "AI Generated" badge should be visible
    And the badge should use warning color styling
    And the badge text should be "AI Generated"

  @report @ui @story-8.3.1
  Scenario: AI disclaimer is included
    When the report includes AI-generated recommendations
    Then each AI section should include a disclaimer
    And the disclaimer should state verification is recommended
    And the disclaimer should be styled as secondary text

  # ===========================================================================
  # Story 8.4.1: Evidence Data Integration
  # ===========================================================================

  @report @data @story-8.4.1
  Scenario: Evidence is available in template context
    When the report template renders
    Then the context should include evidence_collections
    And each finding should have access to its evidence
    And evidence should be serializable to JSON

  @report @data @story-8.4.1
  Scenario: Reports work without evidence data
    When evidence capture is disabled
    And a report is generated
    Then the report should render without errors
    And evidence UI elements should be hidden
    And no JavaScript errors should occur

  # ===========================================================================
  # Story 8.4.2: Evidence JavaScript
  # ===========================================================================

  @report @js @story-8.4.2
  Scenario: Evidence panels initialize on page load
    When the report page loads
    Then initEvidencePanels() should be called
    And all evidence toggle buttons should have click handlers
    And all panels should start in collapsed state

  @report @js @story-8.4.2
  Scenario: Evidence toggle is keyboard accessible
    When the user presses Enter on a focused toggle button
    Then the associated panel should expand
    And when the user presses Space on a focused toggle button
    Then the associated panel should expand
```

---

# Implementation Sequence

## Phase 2A: Critical (Weeks 1-2)
1. **E1: LLM Evidence Trail** - All 6 stories
   - Highest risk, enables trust in AI outputs
   - Update `llm.py` and `analyzer.py`

## Phase 2B: High Priority (Weeks 3-4)
2. **E2: Technical SEO Evidence** - All 5 stories
   - Core functionality, user-facing
   - Update `technical.py`

3. **E3: Performance Evidence** - All 4 stories
   - Update `core_web_vitals.py` and `lab_field_analyzer.py`

## Phase 3A: Medium Priority (Weeks 5-6)
4. **E4: Content Quality Evidence** - All 3 stories
5. **E6: Media & Metadata Evidence** - All 4 stories

## Phase 3B: Lower Priority (Weeks 7-8)
6. **E5: Advanced Analyzer Evidence** - All 4 stories
7. **E7: Site Structure Evidence** - All 4 stories

## Phase 4: UI Layer (Weeks 9-10)
8. **E8: Report UI Evidence Display** - All 5 stories

---

# File Change Summary

| File | Epic(s) | Changes |
|------|---------|---------|
| `src/seo/llm.py` | E1 | Add evidence capture, input summary, model metadata |
| `src/seo/analyzer.py` | E1 | Add ICE justification, link to source data |
| `src/seo/technical.py` | E2 | Add threshold evidence, duplicate evidence |
| `src/seo/core_web_vitals.py` | E3 | Add estimation factors, label as estimates |
| `src/seo/lab_field_analyzer.py` | E3 | Add source labels, gap evidence |
| `src/seo/content_quality.py` | E4 | Add formula inputs, keyword evidence |
| `src/seo/advanced_analyzer.py` | E5 | Add security/URL/mobile/intl evidence |
| `src/seo/image_analyzer.py` | E6 | Add per-image evidence |
| `src/seo/social_analyzer.py` | E6 | Add tag-level evidence |
| `src/seo/structured_data.py` | E6 | Add validation evidence |
| `src/seo/crawlability.py` | E7 | Add robots.txt evidence |
| `src/seo/redirect_analyzer.py` | E7 | Add chain evidence |
| `src/seo/third_party_analyzer.py` | E7 | Add categorization evidence |
| `src/seo/resource_analyzer.py` | E7 | Add weight breakdown evidence |
| `src/seo/report_generator.py` | E8 | Add evidence template context |
| `templates/report.html` | E8 | Add evidence UI markup |
| `ne-style-guide/js/ne-branding.js` | E8 | Add evidence toggle JS |
| `ne-style-guide/css/ne-branding.css` | E8 | Add AI content styles |

---

# Acceptance Criteria Summary

**Total Stories:** 35
**Total BDD Scenarios:** 85+
**Files Modified:** 18
**New Files:** 0 (all modifications to existing)

## Definition of Done per Story:
- [ ] Code implementation complete
- [ ] BDD scenarios pass
- [ ] Evidence records created with all required fields
- [ ] Backward compatibility maintained
- [ ] Evidence serializes to JSON correctly
- [ ] Unit tests added/updated
- [ ] Code review approved

## Definition of Done per Epic:
- [ ] All stories complete
- [ ] Integration tests pass
- [ ] Evidence visible in generated reports
- [ ] Documentation updated

---

# Appendix A: EvidenceRecord Field Reference

```python
@dataclass
class EvidenceRecord:
    # Required fields
    component_id: str          # e.g., 'technical_seo', 'llm_analyzer'
    finding: str               # e.g., 'missing_meta_description', 'lcp_estimate'
    evidence_string: str       # The actual matched/measured value
    confidence: ConfidenceLevel  # High, Medium, Low, Estimate
    timestamp: datetime
    source: str                # e.g., 'Pattern Match', 'Lighthouse', 'LLM'

    # Optional enrichment fields
    source_type: Optional[EvidenceSourceType]  # html_content, http_header, api_response, etc.
    source_location: Optional[str]             # URL, header name, file path
    pattern_matched: Optional[str]             # Regex pattern used
    threshold: Optional[dict]                  # {'operator': '<', 'value': 300, 'unit': 'words'}
    measured_value: Optional[Any]              # The actual measured value
    unit: Optional[str]                        # characters, words, ms, KB, etc.
    recommendation: Optional[str]              # Suggested fix
    severity: Optional[str]                    # critical, warning, info

    # AI-specific metadata
    ai_generated: bool = False
    model_id: Optional[str] = None             # gpt-4, claude-3-opus, etc.
    prompt_hash: Optional[str] = None          # SHA-256 of prompt template
    reasoning: Optional[str] = None            # LLM's explanation
    input_summary: Optional[dict] = None       # Data provided to LLM
```

---

# Appendix B: Related Files

- `docs/EVIDENCE.md` - Evidence system documentation
- `features/evidence_capture.feature` - Existing BDD scenarios (Phase 1)
- `src/seo/models.py` - EvidenceRecord and EvidenceCollection dataclasses
- `src/seo/technology_detector.py` - Reference implementation (Phase 1)

---

# Appendix C: Infrastructure Epics (from Spectrum)

> **Added:** 2026-02-08
> **Source:** BORROW.md analysis and `docs/SPECTRUM_BORROW_LOG.md`

The following epics represent infrastructure improvements borrowed from the Spectrum project. These are complementary to the evidence capture epics and should be implemented to improve overall crawl reliability and efficiency.

| Epic | Name | Priority | Stories | Feature File |
|------|------|----------|---------|--------------|
| E9 | Browser Infrastructure | Critical | 8 | `features/epic9_browser_infrastructure.feature` |
| E10 | Rate Limiting & Metrics | High | 5 | `features/epic10_rate_limiting.feature` |
| E11 | Selector Intelligence | High | 5 | `features/epic11_selector_intelligence.feature` |
| E12 | AI/LLM Caching | Medium | 4 | `features/epic12_ai_caching.feature` |

**Total: 4 Epics, 22 Stories**

## Key Components to Borrow

| Component | Source | Target | Priority |
|-----------|--------|--------|----------|
| BrowserPool | `spectrum/parallel/browser_pool.py` | `src/seo/browser_pool.py` | Critical |
| undetected-chromedriver | `spectrum/crawler.py` | `src/seo/browser_config.py` | Critical |
| AdaptiveRateLimiter | `spectrum/parallel/rate_limiter.py` | `src/seo/rate_limiter.py` | High |
| SelectorLibrary | `spectrum/intelligence/selector_library.py` | `src/seo/selector_library.py` | High |
| AICache | `spectrum/intelligence/ai_cache.py` | `src/seo/ai_cache.py` | Medium |

For full details, see `docs/SPECTRUM_BORROW_LOG.md`.
