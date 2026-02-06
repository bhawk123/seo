Feature: Standardized Evidence Capture
  As an SEO analyst reviewing crawl results
  I want to see the evidence behind every evaluation and conclusion
  So that I can verify the accuracy of findings and build trust in AI-assisted analysis

  Background:
    Given the SEO analysis tool is configured to scan a website
    And evidence capture is enabled for all components

  # ============================================================================
  # EPIC: Evidence Trail System
  # Story 1: Technology Detection Evidence
  # ============================================================================

  @technology @evidence @story-1
  Scenario: Capturing Evidence for Technology Detection
    Given the SEO analysis tool is configured to scan a website
    When the tool detects a specific technology, such as Magento/Adobe Commerce
    And the detection is based on finding the string "mage/cookies.js" in a network request
    Then the final report data should include an evidence record for the "Technology Detection" component
    And this evidence record should contain the finding "Magento/Adobe Commerce"
    And the evidence record should specify the matched string "mage/cookies.js" as evidence
    And the evidence record should have a confidence level of "High"

  @technology @evidence @story-1
  Scenario: Technology detection captures pattern source location
    When the tool detects "jQuery" on a page
    And the detection matched pattern "jquery" in a script src attribute
    Then the evidence record should include the source type "script_src"
    And the evidence record should include the full URL of the matched script

  @technology @evidence @story-1
  Scenario: Technology detection captures HTTP header evidence
    When the tool detects "Nginx" web server
    And the detection is based on the "Server" HTTP header value "nginx/1.24.0"
    Then the evidence record should include the source type "http_header"
    And the evidence record should include the header name "Server"
    And the evidence record should include the raw header value "nginx/1.24.0"
    And the technology version should be extracted as "1.24.0"

  @technology @evidence @story-1
  Scenario: Multiple detection sources are all captured
    When the tool detects "WordPress" on a page
    And the detection matched "wp-content" in HTML content
    And the detection matched "WordPress" in a meta generator tag
    Then the evidence record should contain multiple evidence sources
    And each evidence source should be independently verifiable

  # ============================================================================
  # Story 2: Technical SEO Issue Evidence
  # ============================================================================

  @technical @evidence @story-2
  Scenario: Missing meta description includes threshold evidence
    When the tool identifies a page with a missing meta description
    Then the evidence record should include the component_id "technical_seo"
    And the evidence record should include the finding "missing_meta_description"
    And the evidence record should include the threshold "description.length == 0"
    And the evidence record should include the measured value "null"

  @technical @evidence @story-2
  Scenario: Short meta description includes length comparison
    When the tool identifies a page with a short meta description
    And the meta description is 85 characters long
    Then the evidence record should include the measured value "85"
    And the evidence record should include the threshold "< 120 characters"
    And the evidence record should include the actual meta description text

  @technical @evidence @story-2
  Scenario: Thin content includes word count evidence
    When the tool identifies a page with thin content
    And the page contains 187 words
    Then the evidence record should include the finding "thin_content"
    And the evidence record should include the measured value "187"
    And the evidence record should include the threshold "< 300 words"
    And the confidence level should be "High"

  @technical @evidence @story-2
  Scenario: Broken link includes source and target URLs
    When the tool identifies a broken internal link
    And the link is from "/products" to "/discontinued-item"
    Then the evidence record should include the source URL "/products"
    And the evidence record should include the target URL "/discontinued-item"
    And the evidence record should include the HTTP status code if available

  # ============================================================================
  # Story 3: Performance Assessment Evidence
  # ============================================================================

  @performance @evidence @story-3
  Scenario: Core Web Vitals estimates are clearly labeled
    When the tool estimates LCP for a page
    And the estimate is based on response time and render-blocking resources
    Then the evidence record should include "is_estimate: true"
    And the evidence record should include the estimation methodology
    And the evidence record should list contributing factors with their values

  @performance @evidence @story-3
  Scenario: Lighthouse scores include API source
    When the tool retrieves Lighthouse performance scores
    And the data comes from Google PageSpeed Insights API
    Then the evidence record should include the source "google_pagespeed_insights"
    And the evidence record should include the API fetch timestamp
    And the evidence record should include the Lighthouse version used

  @performance @evidence @story-3
  Scenario: Lab vs Field comparison shows data provenance
    When the tool compares lab metrics to field metrics
    Then lab metrics should be labeled with source "lighthouse"
    And field metrics should be labeled with source "crux"
    And each metric should include its measurement timestamp

  # ============================================================================
  # Story 4: AI/LLM Output Evidence (Critical for Hallucination Mitigation)
  # ============================================================================

  @llm @evidence @story-4 @hallucination-risk
  Scenario: LLM-generated scores include input data
    When the tool generates an SEO score using an LLM
    Then the evidence record should include "ai_generated: true"
    And the evidence record should include the model identifier
    And the evidence record should include a summary of inputs provided to the LLM
    And the evidence record should include any reasoning provided by the LLM

  @llm @evidence @story-4 @hallucination-risk
  Scenario: LLM recommendations link to supporting evidence
    When the tool generates a recommendation using an LLM
    And the recommendation is "Fix 23 pages with missing meta descriptions"
    Then the evidence record should link to the technical_seo component
    And the evidence record should reference the actual count from crawl data
    And the evidence record should include the metric name "missing_meta_descriptions"

  @llm @evidence @story-4 @hallucination-risk
  Scenario: ICE framework scores include justification
    When the tool assigns ICE scores to a recommendation
    And the Impact score is 8, Confidence is 9, and Ease is 7
    Then the evidence record should include justification for the Impact score
    And the evidence record should include justification for the Confidence score
    And the evidence record should include justification for the Ease score
    And each justification should reference verifiable data points

  @llm @evidence @story-4 @hallucination-risk
  Scenario: AI-generated content includes disclaimer
    When the tool displays any AI-generated evaluation
    Then the output should include a visible "AI Generated" indicator
    And the output should include a disclaimer about verification
    And the confidence level should never be "High" for LLM-only evaluations

  # ============================================================================
  # Story 5: Evidence Display in Reports
  # ============================================================================

  @report @evidence @story-5
  Scenario: Evidence is accessible via tooltip on hover
    Given a generated HTML report with evidence-enabled evaluations
    When a user hovers over an evaluation result
    Then a tooltip should display the evidence summary
    And the tooltip should include the confidence level
    And the tooltip should indicate if the evaluation is AI-generated

  @report @evidence @story-5
  Scenario: Evidence panel can be expanded for full details
    Given a generated HTML report with evidence-enabled evaluations
    When a user clicks the evidence toggle button
    Then an evidence panel should expand
    And the panel should show the source type
    And the panel should show the raw evidence value
    And the panel should show any applicable thresholds

  @report @evidence @story-5
  Scenario: AI-generated content has distinct visual styling
    Given a generated HTML report with LLM-based evaluations
    Then AI-generated sections should have a distinct visual indicator
    And the indicator should use a warning color (e.g., orange border)
    And AI-generated sections should include a disclaimer message

  # ============================================================================
  # Story 6: Evidence Data Model
  # ============================================================================

  @datamodel @evidence @story-6
  Scenario: EvidenceRecord contains all required fields
    When an EvidenceRecord is created
    Then it should have a "component_id" field identifying the source component
    And it should have a "finding" field describing the conclusion
    And it should have an "evidence_string" field with the matched/raw data
    And it should have a "confidence_score" field (High/Medium/Low)
    And it should have a "timestamp" field
    And it should have a "source" field (e.g., "Lighthouse", "LLM Heuristic", "Pattern Match")

  @datamodel @evidence @story-6
  Scenario: EvidenceRecord supports optional enrichment fields
    When an EvidenceRecord is created for a technical issue
    Then it may optionally include a "threshold" field
    And it may optionally include a "measured_value" field
    And it may optionally include a "unit" field (e.g., "characters", "words", "ms")
    And it may optionally include a "recommendation" field

  @datamodel @evidence @story-6
  Scenario: EvidenceRecord supports AI-specific metadata
    When an EvidenceRecord is created for an LLM evaluation
    Then it should include "ai_generated: true"
    And it may optionally include "model_id" identifying the LLM used
    And it may optionally include "prompt_hash" for reproducibility
    And it may optionally include "reasoning" with the LLM's explanation
