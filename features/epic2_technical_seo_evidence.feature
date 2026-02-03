@epic-2 @technical @high-priority
Feature: Technical SEO Issue Evidence
  As an SEO analyst reviewing technical issues
  I want to see the evidence behind each flagged issue
  So that I can verify findings and prioritize fixes

  Background:
    Given the SEO analysis tool has crawled a website
    And evidence capture is enabled for technical SEO

  # ===========================================================================
  # Story 2.1.1: Threshold Evidence for All Issues
  # File: src/seo/technical.py
  # ===========================================================================

  @story-2.1.1 @threshold @meta-description
  Scenario: Missing meta description includes threshold evidence
    When the tool identifies a page with a missing meta description
    Then the evidence record should include:
      | field          | value                    |
      | component_id   | technical_seo            |
      | finding        | missing_meta_description |
      | measured_value | null                     |
    And the threshold should specify "description.length == 0"
    And the confidence level should be "High"

  @story-2.1.1 @threshold @meta-description
  Scenario: Short meta description includes length comparison
    When the tool identifies a page with a short meta description
    And the meta description is 85 characters long
    Then the evidence record should include:
      | field          | value             |
      | finding        | short_description |
      | measured_value | 85                |
      | unit           | characters        |
    And the threshold should specify "< 120 characters"

  @story-2.1.1 @threshold @meta-description
  Scenario: Long meta description includes length evidence
    When the tool identifies a page with a long meta description
    And the meta description is 185 characters long
    Then the evidence record should include measured_value "185"
    And the threshold should specify "> 160 characters"
    And the unit should be "characters"

  @story-2.1.1 @threshold @title
  Scenario: Missing title includes threshold evidence
    When the tool identifies a page with a missing title
    Then the evidence record should include:
      | field          | value         |
      | finding        | missing_title |
      | measured_value | null          |
    And the threshold should specify "title.length == 0"

  @story-2.1.1 @threshold @title
  Scenario: Short title includes length evidence
    When the tool identifies a page with a short title
    And the title is 15 characters long
    Then the evidence record should include:
      | field          | value       |
      | finding        | short_title |
      | measured_value | 15          |
      | unit           | characters  |
    And the threshold should specify "< 30 characters"

  @story-2.1.1 @threshold @title
  Scenario: Long title includes length evidence
    When the tool identifies a page with a long title
    And the title is 75 characters long
    Then the evidence record should include:
      | field          | value      |
      | finding        | long_title |
      | measured_value | 75         |
      | unit           | characters |
    And the threshold should specify "> 60 characters"

  @story-2.1.1 @threshold @content
  Scenario: Thin content includes word count evidence
    When the tool identifies a page with thin content
    And the page contains 187 words
    Then the evidence record should include:
      | field          | value        |
      | finding        | thin_content |
      | measured_value | 187          |
      | unit           | words        |
    And the threshold should specify "< 300 words"

  @story-2.1.1 @threshold @performance
  Scenario: Slow page includes load time evidence
    When the tool identifies a slow-loading page
    And the page load time is 4.2 seconds
    Then the evidence record should include:
      | field          | value     |
      | finding        | slow_page |
      | measured_value | 4.2       |
      | unit           | seconds   |
    And the threshold should specify "> 3.0 seconds"

  @story-2.1.1 @threshold @canonical
  Scenario: Missing canonical includes threshold evidence
    When the tool identifies a page with a missing canonical URL
    Then the evidence record should include:
      | field   | value             |
      | finding | missing_canonical |
    And the threshold should specify "canonical_url == null"

  # ===========================================================================
  # Story 2.1.2: Raw Content Evidence
  # ===========================================================================

  @story-2.1.2 @raw-content @meta-description
  Scenario: Short description evidence includes actual text
    When the tool identifies a short meta description
    And the description is "Buy our products today"
    Then the evidence_string should be "Buy our products today"
    And the measured_value should be 22

  @story-2.1.2 @raw-content @title
  Scenario: Short title evidence includes actual text
    When the tool identifies a short title
    And the title is "Welcome"
    Then the evidence_string should be "Welcome"
    And the measured_value should be 7

  @story-2.1.2 @raw-content @h1
  Scenario: Multiple H1 evidence includes all H1 texts
    When the tool identifies a page with multiple H1 tags
    And the H1 tags are "Welcome" and "About Us"
    Then the evidence_string should include "Welcome"
    And the evidence_string should include "About Us"
    And the measured_value should be 2

  @story-2.1.2 @raw-content @h1
  Scenario: Missing H1 evidence shows empty state
    When the tool identifies a page with no H1 tag
    Then the evidence record should include:
      | field          | value      |
      | finding        | missing_h1 |
      | measured_value | 0          |
    And the evidence_string should indicate "No H1 tag found"

  @story-2.1.2 @raw-content @content
  Scenario: Thin content evidence includes content sample
    When the tool identifies thin content
    And the content is "This is a short page with minimal content..."
    Then the evidence should include a content_sample
    And the content_sample should be the first 200 characters

  # ===========================================================================
  # Story 2.1.3: Broken Link Evidence
  # ===========================================================================

  @story-2.1.3 @broken-links
  Scenario: Broken link includes source and target URLs
    When the tool identifies a broken internal link
    And the link is from "/products" to "/discontinued-item"
    Then the evidence record should include:
      | field           | value              |
      | finding         | broken_link        |
      | source_location | /products          |
    And the evidence_string should include "/discontinued-item"

  @story-2.1.3 @broken-links
  Scenario: Broken link includes HTTP status when available
    When the tool identifies a broken link returning 404
    Then the evidence record should include measured_value 404
    And the unit should be "http_status"

  @story-2.1.3 @broken-links
  Scenario: Broken link with 500 error captures status
    When the tool identifies a broken link returning 500
    Then the evidence record should include measured_value 500
    And the severity should be "critical"

  @story-2.1.3 @broken-links
  Scenario: Broken link includes anchor text
    When the tool identifies a broken link with anchor text "Learn More"
    Then the evidence record should include the anchor text "Learn More"
    And this aids in identifying the link visually

  @story-2.1.3 @broken-links
  Scenario: Broken link to external site captured
    When the tool identifies a broken external link
    And the link is from "/resources" to "https://external.com/deleted"
    Then the evidence record should include:
      | field           | value                           |
      | finding         | broken_external_link            |
      | source_location | /resources                      |
      | evidence_string | https://external.com/deleted    |

  # ===========================================================================
  # Story 2.1.4: Duplicate Detection Evidence
  # ===========================================================================

  @story-2.1.4 @duplicates @title
  Scenario: Duplicate titles lists all affected URLs
    When the tool identifies duplicate titles
    And pages "/page-a" and "/page-b" share the title "Welcome"
    Then the evidence record should include finding "duplicate_title"
    And the evidence_string should be "Welcome"
    And the evidence should list affected URLs:
      | url      |
      | /page-a  |
      | /page-b  |

  @story-2.1.4 @duplicates @title
  Scenario: Duplicate title with many pages shows count
    When the tool identifies duplicate titles
    And 15 pages share the same title "Product Page"
    Then the evidence record should include:
      | field          | value           |
      | finding        | duplicate_title |
      | measured_value | 15              |
    And the evidence should list all 15 URLs

  @story-2.1.4 @duplicates @meta-description
  Scenario: Duplicate descriptions lists all affected URLs
    When the tool identifies duplicate meta descriptions
    And 5 pages share the same description
    Then the evidence record should include finding "duplicate_description"
    And the evidence should list all 5 affected URLs
    And the measured_value should be 5

  @story-2.1.4 @duplicates @canonical
  Scenario: Canonical conflicts show conflicting declarations
    When the tool identifies canonical URL conflicts
    And "/page-a" declares canonical as "/page-b"
    And "/page-b" declares canonical as "/page-a"
    Then the evidence record should include finding "canonical_conflict"
    And the evidence should show both conflicting declarations

  # ===========================================================================
  # Story 2.1.5: Evidence-Enabled Issue Format
  # ===========================================================================

  @story-2.1.5 @format
  Scenario: Technical issue includes evidence record
    When any technical issue is identified
    Then the issue should include an evidence field
    And the evidence field should be an EvidenceRecord
    And the evidence should be serializable to JSON

  @story-2.1.5 @format
  Scenario: Issue severity derives from evidence
    When a technical issue has measured_value exceeding threshold by 50%+
    Then the severity should be "critical"

  @story-2.1.5 @format
  Scenario: Issue severity warning for moderate excess
    When a technical issue has measured_value exceeding threshold by 20-50%
    Then the severity should be "warning"

  @story-2.1.5 @format
  Scenario: Issue severity info for minor excess
    When a technical issue has measured_value barely exceeding threshold
    Then the severity should be "info"

  @story-2.1.5 @format
  Scenario: Evidence includes affected URL
    When a technical issue is identified on page "/about"
    Then the evidence record should include:
      | field           | value  |
      | source_location | /about |

  @story-2.1.5 @format
  Scenario: Evidence timestamp captures detection time
    When a technical issue is identified
    Then the evidence record should include a timestamp
    And the timestamp should be within the crawl session timeframe

  # ===========================================================================
  # Edge Cases
  # ===========================================================================

  @edge-case
  Scenario: Page with all issues captures all evidence
    When a page has missing title, missing H1, and thin content
    Then three separate evidence records should be created
    And each evidence record should have the same source_location
    And each should have different findings

  @edge-case
  Scenario: Unicode content in meta description handled
    When the tool identifies a meta description with unicode "Best widgets 🎉"
    Then the evidence_string should preserve the unicode
    And the measured_value should count characters correctly

  @edge-case
  Scenario: Very long meta description truncated in evidence
    When the tool identifies a meta description of 500 characters
    Then the evidence_string should be truncated to 200 characters
    And the full_value should be available in extended evidence
    And the measured_value should still be 500
