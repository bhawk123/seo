@epic-11 @selector-intelligence @high
Feature: Selector Library
  As a crawler developer
  I want persistent selector management with stability scoring
  So that form interactions are reliable across crawl sessions

  Background:
    Given the selector library is initialized
    And site_id is "example.com"
    And a default set of global fallback patterns exist

  # ===========================================================================
  # Feature 11.1: Selector Library Core
  # Story 11.1.1: Implement Selector Library Storage
  # ===========================================================================

  @story-11.1.1 @persistence
  Scenario: Selectors persist across sessions
    Given a selector "input[name=email]" for purpose "email_field" is stored with confidence 0.9
    When the library is saved to disk
    And the library is reloaded from disk
    Then the selector for "email_field" should be "input[name=email]"
    And its confidence should be 0.9

  @story-11.1.1 @persistence
  Scenario: Site-specific selectors are isolated
    Given selector "#email-field-site-a" is stored for purpose "email_field" on "site-a.com"
    And selector "#email-input-site-b" is stored for purpose "email_field" on "site-b.com"
    When getting selector for "email_field" on "site-a.com"
    Then the result should be "#email-field-site-a"
    When getting selector for "email_field" on "site-b.com"
    Then the result should be "#email-input-site-b"

  @story-11.1.1 @persistence
  Scenario: Global fallback patterns are available
    Given no site-specific selector for "search_box"
    When getting selector for "search_box" on "any-site.com"
    Then a global fallback pattern (e.g., "input[type=search]") should be returned

  @story-11.1.1 @persistence
  Scenario: Saving and loading handles empty library
    Given the selector library is empty
    When the library is saved and reloaded
    Then the library should remain empty
    And no errors should occur

  # ===========================================================================
  # Feature 11.1: Selector Library Core
  # Story 11.1.2: Implement Selector Candidate Generation
  # ===========================================================================

  @story-11.1.2 @candidate-generation
  Scenario: Multiple candidates generated with stability scores
    Given an HTML element: <input id="email" name="user_email" class="form-control" data-qa="email-input">
    When candidates are generated for this element
    Then candidates should include:
      | selector                        | stability_score |
      | #email                          | 0.95            |
      | [data-qa="email-input"]         | 0.98            |
      | .form-control                   | 0.60            |
      | input[name="user_email"]        | 0.80            |
      | /html/body/input[1]             | 0.40            |
    And candidates should be sorted by stability_score (descending)

  @story-11.1.2 @candidate-generation
  Scenario: data-testid or data-qa gets highest stability
    Given an element with data-testid="submit-button"
    When candidates are generated
    Then a selector based on data-testid="submit-button" should have stability 0.98

  @story-11.1.2 @candidate-generation
  Scenario: Dynamic elements get lower scores for class/xpath
    Given an element with a dynamically generated class like "ng-12345-input"
    When candidates are generated
    Then the class-based selector should have a lower stability (e.g., < 0.60)
    And a generic XPath should also have a low stability

  # ===========================================================================
  # Feature 11.1: Selector Library Core
  # Story 11.1.3: Implement Confidence Tracking
  # ===========================================================================

  @story-11.1.3 @confidence-tracking
  Scenario: Success increases confidence
    Given selector "#email" has an initial confidence of 0.7
    When record_success("email_field", "#email") is called 3 times
    Then the confidence for "#email" should increase (e.g., to 0.85)
    And confidence should not exceed 1.0

  @story-11.1.3 @confidence-tracking
  Scenario: Failure decreases confidence
    Given selector "#email" has an initial confidence of 0.7
    When record_failure("email_field", "#email") is called 2 times
    Then the confidence for "#email" should decrease (e.g., to 0.5)
    And confidence should not go below 0.1

  @story-11.1.3 @confidence-tracking
  Scenario: Low confidence triggers fallback in retrieval
    Given selector "#email" has confidence 0.3 for "email_field"
    And selector "input[name=email]" has confidence 0.8 for "email_field"
    When getting selector for "email_field"
    Then "input[name=email]" should be returned first due to higher confidence

  @story-11.1.3 @confidence-tracking
  Scenario: New selectors start with default confidence
    When a new selector ".new-button" is stored for "action_button"
    Then its initial confidence should be a predefined default (e.g., 0.5)

  # ===========================================================================
  # Feature 11.2: Selector Fallback Strategies
  # Story 11.2.1: Implement Fallback Prioritization
  # ===========================================================================

  @story-11.2.1 @fallback-strategy
  Scenario: Fallbacks ordered by confidence then stability
    Given multiple selectors for "submit_button":
      | selector                 | confidence | stability |
      | [data-action=submit]     | 0.9        | 0.85      |
      | #submit-btn              | 0.7        | 0.95      |
      | .submit-button           | 0.5        | 0.60      |
      | input[type=submit]       | 0.7        | 0.70      |
    When get_selector_with_fallbacks("submit_button") is called
    Then the order should be:
      | rank | selector                 |
      | 1    | [data-action=submit]     |
      | 2    | #submit-btn              |
      | 3    | input[type=submit]       |
      | 4    | .submit-button           |

  @story-11.2.1 @fallback-strategy
  Scenario: Maximum fallback attempts configurable
    Given get_selector_with_fallbacks is configured for max_attempts 2
    And there are 3 candidate selectors
    When get_selector_with_fallbacks is called
    Then only the top 2 selectors should be returned

  @story-11.2.1 @fallback-strategy
  Scenario: No selectors found returns empty list
    Given no selectors are stored for purpose "non_existent_field"
    When get_selector_with_fallbacks("non_existent_field") is called
    Then an empty list should be returned

  # ===========================================================================
  # Feature 11.2: Selector Fallback Strategies
  # Story 11.2.2: Integrate with Form Handler
  # ===========================================================================

  @story-11.2.2 @integration @form-handler
  Scenario: FormHandler uses SelectorLibrary for field selection
    Given FormHandler needs to fill "email_field"
    And SelectorLibrary has a high-confidence selector for "email_field"
    When FormHandler attempts to fill the field
    Then it should retrieve the selector from SelectorLibrary
    And attempt to use that selector

  @story-11.2.2 @integration @form-handler
  Scenario: Success/failure recorded after form interaction
    Given FormHandler successfully fills "email_field" using "#email"
    When the interaction completes
    Then record_success("email_field", "#email") should be called on SelectorLibrary

  @story-11.2.2 @integration @form-handler
  Scenario: Site-specific selectors prioritized in FormHandler
    Given FormHandler is processing "site-a.com"
    When FormHandler needs a selector for "login_button"
    Then it should first look for "login_button" selectors specific to "site-a.com"
    Before considering global fallbacks.

  @story-11.2.2 @integration @form-handler
  Scenario: Backward compatibility with existing forms
    Given a form definition uses a hardcoded CSS selector
    When FormHandler processes this form
    Then it should still be able to use the hardcoded selector
    And SelectorLibrary integration should be optional/configurable.