@epic-8 @report @ui
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

  @story-8.1.1 @tooltip
  Scenario: Evidence tooltip appears on hover
    When the user hovers over an evaluation result
    Then a tooltip should appear within 200ms
    And the tooltip should display the evidence summary
    And the tooltip should include the confidence level

  @story-8.1.1 @tooltip
  Scenario: Tooltip shows source type
    When the user hovers over a technology detection result
    Then the tooltip should show source_type "pattern_match"
    And the tooltip should show what pattern was matched

  @story-8.1.1 @tooltip @ai
  Scenario: Tooltip indicates AI-generated content
    When the user hovers over an AI-generated evaluation
    Then the tooltip should display "AI Generated" indicator
    And the tooltip should show the model identifier
    And the tooltip should include a verification reminder

  @story-8.1.1 @tooltip @accessibility
  Scenario: Tooltip is keyboard accessible
    When the user focuses an evaluation using Tab key
    Then the tooltip should appear on focus
    And the tooltip should remain visible while focused
    And the tooltip should hide when focus moves away

  @story-8.1.1 @tooltip @accessibility
  Scenario: Tooltip has appropriate ARIA attributes
    When an evaluation has evidence
    Then the element should have aria-describedby
    And the tooltip should have role="tooltip"
    And the tooltip should have appropriate aria-label

  @story-8.1.1 @tooltip
  Scenario: Tooltip shows threshold for technical issues
    When the user hovers over a "thin content" finding
    Then the tooltip should show:
      | field     | value       |
      | measured  | 187 words   |
      | threshold | < 300 words |

  # ===========================================================================
  # Story 8.2.1: Evidence Panels
  # ===========================================================================

  @story-8.2.1 @panel
  Scenario: Evidence panel expands on click
    When the user clicks the evidence toggle button
    Then the evidence panel should expand with animation
    And the panel should show the source type
    And the panel should show the raw evidence value
    And the panel should show any applicable thresholds

  @story-8.2.1 @panel
  Scenario: Evidence panel collapses on second click
    Given the evidence panel is expanded
    When the user clicks the toggle button again
    Then the panel should collapse with animation
    And the toggle icon should rotate back

  @story-8.2.1 @panel
  Scenario: Evidence panel shows threshold comparison
    Given a technical issue with threshold evidence
    When the user expands the evidence panel
    Then the panel should show the measured value
    And the panel should show the threshold
    And the panel should show the unit
    And a visual indicator should show pass/fail status

  @story-8.2.1 @panel
  Scenario: Evidence panel shows multiple sources
    Given a technology detected by multiple patterns
    When the user expands the evidence panel
    Then the panel should list all evidence sources
    And each source should show its matched value
    And sources should be independently verifiable

  @story-8.2.1 @panel
  Scenario: Evidence panel shows timestamp
    When the user expands the evidence panel
    Then the panel should show when the evidence was captured
    And the timestamp should be in human-readable format

  @story-8.2.1 @panel @ai
  Scenario: Evidence panel shows LLM details
    Given an AI-generated recommendation
    When the user expands the evidence panel
    Then the panel should show:
      | field        | description           |
      | model_id     | The LLM used          |
      | input_summary| Data provided to LLM  |
      | reasoning    | LLM's explanation     |

  # ===========================================================================
  # Story 8.3.1: AI Content Indicators
  # ===========================================================================

  @story-8.3.1 @ai-styling
  Scenario: AI-generated sections have distinct styling
    When the report includes LLM-based evaluations
    Then AI-generated sections should have class "ai-generated"
    And the sections should have an orange left border (#f59e0b)
    And the sections should have a subtle warning background

  @story-8.3.1 @ai-styling
  Scenario: AI badge is displayed
    When an evaluation is AI-generated
    Then an "AI Generated" badge should be visible
    And the badge should use warning color styling
    And the badge text should be "AI Generated"

  @story-8.3.1 @ai-styling
  Scenario: AI disclaimer is included
    When the report includes AI-generated recommendations
    Then each AI section should include a disclaimer
    And the disclaimer should state verification is recommended
    And the disclaimer should be styled as secondary text

  @story-8.3.1 @ai-styling
  Scenario: AI content has consistent styling site-wide
    When multiple AI-generated sections exist
    Then all should have identical styling:
      | property         | value                        |
      | border-left      | 3px solid #f59e0b            |
      | background       | rgba(245, 158, 11, 0.05)     |
      | padding-left     | 1rem                         |

  @story-8.3.1 @ai-styling
  Scenario: Non-AI content has no AI indicators
    When a finding is based purely on pattern matching
    Then the section should not have class "ai-generated"
    And no AI badge should be displayed
    And no disclaimer should appear

  # ===========================================================================
  # Story 8.4.1: Evidence Data Integration
  # ===========================================================================

  @story-8.4.1 @data
  Scenario: Evidence is available in template context
    When the report template renders
    Then the context should include evidence_collections
    And each finding should have access to its evidence
    And evidence should be serializable to JSON

  @story-8.4.1 @data
  Scenario: Evidence JSON is embedded for JavaScript
    When the report includes evidence
    Then evidence data should be in a script tag
    And the data should be valid JSON
    And JavaScript can access window.evidenceData

  @story-8.4.1 @data @backward-compat
  Scenario: Reports work without evidence data
    When evidence capture is disabled
    And a report is generated
    Then the report should render without errors
    And evidence UI elements should be hidden
    And no JavaScript errors should occur

  @story-8.4.1 @data
  Scenario: Evidence is linked to DOM elements
    When the report renders with evidence
    Then each finding element should have data-evidence-id
    And the evidence data should be retrievable by that ID

  # ===========================================================================
  # Story 8.4.2: Evidence JavaScript
  # ===========================================================================

  @story-8.4.2 @javascript
  Scenario: Evidence panels initialize on page load
    When the report page loads
    Then initEvidencePanels() should be called
    And all evidence toggle buttons should have click handlers
    And all panels should start in collapsed state

  @story-8.4.2 @javascript
  Scenario: Evidence toggle is keyboard accessible
    When the user presses Enter on a focused toggle button
    Then the associated panel should expand
    And when the user presses Space on a focused toggle button
    Then the associated panel should expand

  @story-8.4.2 @javascript
  Scenario: Multiple panels can be open simultaneously
    Given two evidence toggle buttons
    When the user opens the first panel
    And the user opens the second panel
    Then both panels should remain open

  @story-8.4.2 @javascript
  Scenario: Animation is smooth and consistent
    When the user toggles an evidence panel
    Then the expansion should animate over 200ms
    And the animation should use ease-in-out timing
    And no layout shift should occur

  @story-8.4.2 @javascript
  Scenario: Escape key closes expanded panel
    Given an evidence panel is expanded
    When the user presses Escape
    Then the panel should collapse
    And focus should return to the toggle button

  # ===========================================================================
  # Confidence Badges
  # ===========================================================================

  @confidence
  Scenario: High confidence badge styling
    When an evaluation has confidence "High"
    Then the confidence badge should have class "confidence-high"
    And the badge should display "High Confidence"
    And the badge should use green styling

  @confidence
  Scenario: Medium confidence badge styling
    When an evaluation has confidence "Medium"
    Then the confidence badge should have class "confidence-medium"
    And the badge should display "Medium Confidence"
    And the badge should use yellow styling

  @confidence
  Scenario: Low confidence badge styling
    When an evaluation has confidence "Low"
    Then the confidence badge should have class "confidence-low"
    And the badge should display "Low Confidence"
    And the badge should use orange styling

  @confidence
  Scenario: Estimate confidence badge styling
    When an evaluation has confidence "Estimate"
    Then the confidence badge should have class "confidence-estimate"
    And the badge should display "Estimated"
    And the badge should use gray styling

  # ===========================================================================
  # Print Styling
  # ===========================================================================

  @print
  Scenario: Evidence is visible in print
    When the report is printed
    Then expanded evidence panels should print
    And collapsed evidence panels should be hidden
    And AI indicators should print in grayscale

  @print
  Scenario: Tooltips are not printed
    When the report is printed
    Then tooltips should be hidden
    And toggle buttons should be hidden
    And core evidence data should be visible if expanded
