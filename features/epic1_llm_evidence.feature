@epic-1 @llm @critical
Feature: LLM Evidence Trail
  As an SEO analyst reviewing AI-generated evaluations
  I want to see the evidence behind LLM outputs
  So that I can verify accuracy and mitigate hallucination risks

  Background:
    Given the SEO analysis tool is configured to use LLM scoring
    And evidence capture is enabled for LLM components

  # ===========================================================================
  # Feature 1.1: LLM SEO Scoring Evidence
  # File: src/seo/llm.py
  # ===========================================================================

  @story-1.1.1 @input-capture
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

  @story-1.1.1 @input-capture
  Scenario: LLM input summary includes meta description
    When the tool generates an SEO score
    And the page has description "Find the best widgets for your home in 2024"
    Then the evidence record input_summary should include:
      | field              | value                                          |
      | description        | Find the best widgets for your home in 2024    |
      | description_length | 45                                             |

  @story-1.1.1 @input-capture
  Scenario: LLM input summary includes H1 data
    When the tool generates an SEO score
    And the page has 2 H1 tags
    Then the evidence record input_summary should include h1_count of 2

  @story-1.1.2 @model-metadata
  Scenario: LLM scoring captures model metadata
    When the tool generates an SEO score using "gpt-4"
    Then the evidence record should include model_id "gpt-4"
    And the evidence record should include a prompt_hash
    And the prompt_hash should be a valid SHA-256 hash

  @story-1.1.2 @model-metadata
  Scenario: LLM scoring captures model for Anthropic
    When the tool generates an SEO score using "claude-3-opus"
    Then the evidence record should include model_id "claude-3-opus"
    And the evidence record should include the API provider "anthropic"

  @story-1.1.2 @model-metadata
  Scenario: Prompt hash enables reproducibility verification
    When the tool generates two scores using the same prompt template
    Then both evidence records should have the same prompt_hash
    When the prompt template is modified
    Then the next evidence record should have a different prompt_hash

  @story-1.1.3 @reasoning
  Scenario: LLM scoring captures reasoning
    When the tool generates an overall_score of 72
    Then the evidence record should include a non-empty reasoning field
    And the reasoning should reference specific page attributes
    And the reasoning should explain score deductions

  @story-1.1.3 @reasoning
  Scenario: LLM reasoning references measurable data
    When the tool generates a title_score of 65
    And the reasoning mentions "title length"
    Then the reasoning should include the actual title length value
    And the reasoning should reference the recommended length threshold

  @story-1.1.3 @reasoning
  Scenario: LLM reasoning for content score references word count
    When the tool generates a content_score of 58
    And the page has 187 words
    Then the reasoning should reference the word count of 187
    And the reasoning should mention thin content concerns

  @story-1.1.3 @reasoning
  Scenario: LLM reasoning for technical score references specific issues
    When the tool generates a technical_score of 70
    And the page is missing meta description
    Then the reasoning should mention missing meta description
    And the reasoning should provide specific improvement suggestion

  # ===========================================================================
  # Feature 1.2: ICE Recommendation Evidence
  # File: src/seo/analyzer.py
  # ===========================================================================

  @story-1.2.1 @source-linking @hallucination-risk
  Scenario: Recommendation links to source crawl data
    When the tool generates recommendation "Fix 23 pages with missing meta descriptions"
    Then the evidence record should include:
      | field            | value                       |
      | component_ref    | technical_seo               |
      | metric_name      | missing_meta_descriptions   |
      | metric_value     | 23                          |
    And the metric_value should match TechnicalIssues.missing_descriptions count

  @story-1.2.1 @source-linking @hallucination-risk
  Scenario: Recommendation with percentage links to total count
    When the tool generates recommendation "15% of pages have thin content"
    Then the evidence record should include the actual page count
    And the evidence record should include the total pages crawled
    And the calculated percentage should match the stated percentage

  @story-1.2.1 @source-linking @hallucination-risk
  Scenario: Recommendation references correct component for broken links
    When the tool generates recommendation about broken links
    Then the evidence record should reference component "technical_seo"
    And the evidence record should include metric_name "broken_links"
    And the count should match the actual broken link count

  @story-1.2.1 @source-linking @hallucination-risk
  Scenario: Recommendation references correct component for performance
    When the tool generates recommendation about page speed
    Then the evidence record should reference component "core_web_vitals"
    And the evidence record should include specific metric (LCP, INP, or CLS)

  @story-1.2.2 @ice-justification
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

  @story-1.2.2 @ice-justification
  Scenario: Impact justification references business value
    When the tool assigns Impact score of 9 to "Fix critical page speed issues"
    Then the impact justification should mention:
      | term                        |
      | user experience             |
      | search rankings             |
      | conversion                  |

  @story-1.2.2 @ice-justification
  Scenario: Confidence justification references data reliability
    When the tool assigns Confidence score of 9 based on crawl data
    Then the confidence justification should mention "verified by crawl"
    When the tool assigns Confidence score of 6 based on estimates
    Then the confidence justification should mention "estimated values"

  @story-1.2.2 @ice-justification
  Scenario: Ease justification considers implementation complexity
    When the tool assigns Ease score of 3 for "Migrate to new CMS"
    Then the ease justification should mention:
      | factor              |
      | development effort  |
      | risk                |
      | timeline            |

  @story-1.2.3 @confidence-ceiling
  Scenario: LLM-only evaluations cannot have High confidence
    When the tool generates an LLM-only evaluation
    And the LLM suggests confidence should be "High"
    Then the stored confidence level should be "Medium"
    And the evidence record should include ai_generated: true
    And the evidence record should include a confidence_override_reason

  @story-1.2.3 @confidence-ceiling
  Scenario: Mixed evidence can have High confidence
    When the tool generates an evaluation based on LLM analysis
    And the evaluation is corroborated by pattern matching evidence
    Then the stored confidence level may be "High"
    And the evidence record should include multiple evidence sources
    And at least one source should have ai_generated: false

  @story-1.2.3 @confidence-ceiling
  Scenario: Confidence override is logged
    When an LLM evaluation attempts to set High confidence
    Then the confidence_override_reason should explain the policy
    And the original suggested confidence should be preserved in metadata

  # ===========================================================================
  # Feature 1.3: LLM Recommendations in Reports
  # File: src/seo/report_generator.py
  # ===========================================================================

  @story-1.3.1 @report-generation @critical
  Scenario: Report contains LLM-generated recommendations by default
    Given a completed site crawl with technical issues data
    When the report is generated
    Then the report should contain an "LLM Recommendations" section
    And the recommendations should include ICE framework scores
    And the recommendations should NOT contain "Failed to generate" error messages
    And the recommendations should include at least one actionable item

  @story-1.3.1 @report-generation @critical
  Scenario: LLM recommendations section displays structured content
    Given a completed site crawl
    When the LLM recommendations are generated successfully
    Then the report should display:
      | section                      |
      | Critical Issues              |
      | Quick Wins                   |
      | Content Optimization         |
      | Technical SEO Improvements   |
      | Prioritized 30-Day Action Plan |
    And each recommendation should include ICE scores in format "[I:X C:X E:X = ICE:X.X]"

  @story-1.3.2 @report-generation @retry
  Scenario: Report generation retries LLM on connection failure
    Given a site crawl is complete
    And the LLM API returns a connection error on first attempt
    When the report is generated
    Then the system should retry the LLM call up to 3 times
    And if all retries fail, the report should include a clear error message
    And the error message should suggest running regenerate_recommendations.py

  @story-1.3.3 @report-generation @fallback
  Scenario: Report regeneration updates existing report with LLM content
    Given a report exists with "Failed to generate LLM recommendations" error
    When regenerate_recommendations.py is run against the crawl directory
    Then the recommendations.txt file should be created
    And the report.html can be regenerated with the new recommendations
    And the "Failed to generate" message should be replaced with actual content

  # ===========================================================================
  # Edge Cases and Error Handling
  # ===========================================================================

  @edge-case
  Scenario: LLM API failure still captures partial evidence
    When the LLM API call fails
    Then the evidence record should still be created
    And the evidence should include error details
    And the confidence should be "Low"
    And ai_generated should still be true

  @edge-case
  Scenario: Empty LLM response handled gracefully
    When the LLM returns an empty or malformed response
    Then the evidence record should capture the raw response
    And an error flag should be set
    And the finding should indicate parsing failure

  @edge-case
  Scenario: Recommendation count mismatch is flagged
    When the LLM claims "50 pages with issues"
    And the actual crawl data shows 23 pages
    Then the evidence should flag the mismatch
    And the evidence should show both values
    And a warning should be included about potential hallucination
