@epic-3 @performance @high-priority
Feature: Performance Metrics Evidence
  As an SEO analyst reviewing performance data
  I want to understand the source and reliability of metrics
  So that I can make informed optimization decisions

  Background:
    Given the SEO analysis tool has analyzed page performance
    And evidence capture is enabled for performance components

  # ===========================================================================
  # Story 3.1.1: CWV Estimation Labels
  # File: src/seo/core_web_vitals.py
  # ===========================================================================

  @story-3.1.1 @estimate @lcp
  Scenario: LCP estimate is clearly labeled
    When the tool estimates LCP for a page
    Then the evidence record should include:
      | field         | value          |
      | finding       | lcp_estimate   |
      | confidence    | Estimate       |
    And the evidence should include is_estimate: true
    And the evidence should include estimation_methodology

  @story-3.1.1 @estimate @lcp
  Scenario: LCP estimate shows status classification
    When the tool estimates LCP at 3200ms
    Then the evidence record should include:
      | field       | value             |
      | status      | needs-improvement |
    And the evidence should show thresholds: good < 2500ms, poor > 4000ms

  @story-3.1.1 @estimate @inp
  Scenario: INP estimate includes methodology
    When the tool estimates INP for a page
    Then the evidence should include:
      | field                  | value                     |
      | estimation_methodology | blocking_script_heuristic |
    And the methodology description should be human-readable

  @story-3.1.1 @estimate @inp
  Scenario: INP estimate shows blocking script count
    When the tool estimates INP based on 5 blocking scripts
    Then the evidence should include:
      | field           | value |
      | blocking_scripts| 5     |
    And the confidence should be "Estimate"

  @story-3.1.1 @estimate @cls
  Scenario: CLS risk assessment shows contributing elements
    When the tool identifies CLS risk factors
    And 3 images lack width/height attributes
    Then the evidence should include:
      | field          | value              |
      | finding        | cls_risk           |
      | measured_value | 3                  |
      | unit           | elements_at_risk   |
    And the evidence should list the specific image sources

  @story-3.1.1 @estimate @cls
  Scenario: CLS risk includes iframe without dimensions
    When the tool identifies an iframe without dimensions
    Then the evidence should include finding "cls_risk"
    And the evidence should identify the iframe src
    And the element_type should be "iframe"

  @story-3.1.1 @estimate @disclaimer
  Scenario: All CWV estimates include disclaimer
    When any CWV metric is estimated
    Then the evidence should include a disclaimer field
    And the disclaimer should state "Without a real browser, we can only estimate"

  # ===========================================================================
  # Story 3.1.2: LCP Estimation Factors
  # ===========================================================================

  @story-3.1.2 @factors @lcp
  Scenario: LCP estimate shows response time contribution
    When the tool estimates LCP at 2800ms
    And the response time was 1200ms
    And 3 render-blocking resources added 1600ms penalty
    Then the evidence should include contributing_factors:
      | factor                    | value | unit |
      | response_time             | 1200  | ms   |
      | render_blocking_penalty   | 1600  | ms   |
    And the evidence should show the formula used

  @story-3.1.2 @factors @lcp
  Scenario: LCP estimation shows render-blocking resource count
    When the tool identifies render-blocking resources
    And 5 scripts and 2 stylesheets block rendering
    Then the evidence should include:
      | field                    | value |
      | blocking_scripts         | 5     |
      | blocking_stylesheets     | 2     |
      | total_blocking_resources | 7     |

  @story-3.1.2 @factors @lcp
  Scenario: LCP estimation formula is documented
    When the tool estimates LCP
    Then the evidence should include:
      | field   | value                                              |
      | formula | response_time + (blocking_resources * penalty_ms)  |
    And the penalty_ms default should be documented

  @story-3.1.2 @factors @lcp
  Scenario: LCP good status with fast response
    When the response time is 800ms
    And there are no render-blocking resources
    Then the estimated LCP should be approximately 800ms
    And the status should be "good"

  @story-3.1.2 @factors @lcp
  Scenario: LCP poor status with slow response and blocking resources
    When the response time is 2500ms
    And there are 5 render-blocking resources
    Then the estimated LCP should exceed 4000ms
    And the status should be "poor"

  # ===========================================================================
  # Story 3.2.1: Lab vs Field Data Source
  # File: src/seo/lab_field_analyzer.py
  # ===========================================================================

  @story-3.2.1 @source @lighthouse
  Scenario: Lab metric includes Lighthouse source
    When the tool reports Lighthouse performance score
    Then the evidence record should include:
      | field       | value                      |
      | source      | google_pagespeed_insights  |
      | source_type | api_response               |
    And the evidence should include api_timestamp
    And the evidence should include lighthouse_version

  @story-3.2.1 @source @lighthouse
  Scenario: Lighthouse data includes all audit categories
    When the tool retrieves Lighthouse data
    Then the evidence should include scores for:
      | category      |
      | performance   |
      | accessibility |
      | best-practices|
      | seo           |

  @story-3.2.1 @source @crux
  Scenario: Field metric includes CrUX source
    When the tool reports CrUX LCP percentile
    Then the evidence record should include:
      | field       | value        |
      | source      | crux         |
      | source_type | api_response |
    And the evidence should include data_freshness_date

  @story-3.2.1 @source @crux
  Scenario: CrUX data includes collection period
    When the tool retrieves CrUX data
    Then the evidence should include:
      | field              | description                    |
      | collection_period  | 28-day rolling window          |
      | data_freshness     | Date of most recent data       |

  @story-3.2.1 @source @comparison
  Scenario: Mixed metrics clearly distinguish sources
    When the tool compares lab and field LCP
    Then the lab LCP evidence should have source "lighthouse"
    And the field LCP evidence should have source "crux"
    And each should have independent timestamps

  @story-3.2.1 @source @comparison
  Scenario: Lab and field metrics shown together
    When the tool presents both lab and field CLS
    Then the report should show both values with sources:
      | metric | value | source     |
      | lab    | 0.05  | lighthouse |
      | field  | 0.12  | crux       |

  # ===========================================================================
  # Story 3.2.2: Lab/Field Gap Evidence
  # ===========================================================================

  @story-3.2.2 @gap
  Scenario: Significant gap is flagged with evidence
    When lab LCP is 2.0s and field LCP is 3.5s
    Then the gap should be calculated as 75%
    And the evidence should include:
      | field          | value         |
      | finding        | lab_field_gap |
      | measured_value | 75            |
      | unit           | percent       |
    And the threshold should specify "> 25%"

  @story-3.2.2 @gap
  Scenario: Gap evidence includes both metric values
    When the tool identifies a lab/field gap
    Then the evidence should include lab_value and field_value
    And both values should have their source labeled
    And a recommendation should explain potential causes

  @story-3.2.2 @gap
  Scenario: Small gap is not flagged
    When lab LCP is 2.0s and field LCP is 2.3s
    Then the gap should be calculated as 15%
    And no gap finding should be created
    And both metrics should still be captured with sources

  @story-3.2.2 @gap
  Scenario: Gap recommendation suggests investigation
    When a significant lab/field gap is detected
    Then the recommendation should suggest:
      | suggestion                                    |
      | Check real-world network conditions           |
      | Review third-party script impact              |
      | Test on representative devices                |

  @story-3.2.2 @gap
  Scenario: Gap direction is captured
    When field metrics are worse than lab metrics
    Then the evidence should include gap_direction "field_worse"
    When lab metrics are worse than field metrics
    Then the evidence should include gap_direction "lab_worse"

  # ===========================================================================
  # No Data Scenarios
  # ===========================================================================

  @edge-case @no-data
  Scenario: Missing Lighthouse data handled
    When the PageSpeed Insights API returns no data
    Then the evidence should include:
      | field   | value                |
      | finding | lighthouse_unavailable |
    And a reason should be provided (e.g., "URL not accessible")

  @edge-case @no-data
  Scenario: Missing CrUX data handled
    When no CrUX data is available for the URL
    Then the evidence should include:
      | field   | value            |
      | finding | crux_unavailable |
    And the evidence should note "Insufficient traffic for CrUX data"

  @edge-case @no-data
  Scenario: Lab-only comparison when CrUX unavailable
    When CrUX data is unavailable
    And Lighthouse data is available
    Then lab metrics should be displayed with source "lighthouse"
    And field comparison should show "No field data available"
