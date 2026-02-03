@epic-5 @advanced @medium-priority
Feature: Advanced Analyzer Evidence
  As an SEO analyst reviewing advanced analysis
  I want evidence for security, URL, mobile, and international checks
  So that I can address issues with full context

  Background:
    Given the SEO analysis tool has performed advanced analysis
    And evidence capture is enabled for advanced analyzers

  # ===========================================================================
  # Story 5.1.1: Security Header Evidence
  # File: src/seo/advanced_analyzer.py (SecurityAnalyzer)
  # ===========================================================================

  @story-5.1.1 @security
  Scenario: Security headers show presence status
    When the tool analyzes security headers
    Then the evidence should list each header with status:
      | header                      | status  | points |
      | Strict-Transport-Security   | present | 20     |
      | X-Content-Type-Options      | missing | 0      |
      | X-Frame-Options             | present | 10     |
      | Content-Security-Policy     | missing | 0      |

  @story-5.1.1 @security
  Scenario: Present headers include raw value
    When the tool finds "Strict-Transport-Security" header
    And the value is "max-age=31536000; includeSubDomains"
    Then the evidence_string should include the raw value
    And a recommendation may suggest adding "preload"

  @story-5.1.1 @security
  Scenario: Security score calculation is shown
    When HTTPS is present (40 pts) and 2 headers present (30 pts)
    Then the evidence should show:
      | component        | points |
      | https            | 40     |
      | security_headers | 30     |
      | total_score      | 70     |

  @story-5.1.1 @security
  Scenario: Missing HTTPS flagged as critical
    When the site uses HTTP instead of HTTPS
    Then the evidence should include:
      | field    | value        |
      | finding  | missing_https|
      | severity | critical     |
      | points   | 0            |

  @story-5.1.1 @security
  Scenario: CSP header quality assessed
    When Content-Security-Policy header is present
    Then the evidence should note the CSP value
    And the evidence may include CSP quality assessment
    And recommendations for CSP improvements may be included

  # ===========================================================================
  # Story 5.2.1: URL Quality Evidence
  # File: src/seo/advanced_analyzer.py (URLStructureAnalyzer)
  # ===========================================================================

  @story-5.2.1 @url
  Scenario: Long URL is flagged with measurement
    When the tool identifies a URL with 92 characters
    Then the evidence should include:
      | field          | value        |
      | finding        | url_too_long |
      | measured_value | 92           |
      | unit           | characters   |
      | threshold      | > 75         |

  @story-5.2.1 @url
  Scenario: URL depth is calculated
    When the tool analyzes URL "/products/category/subcategory/item"
    Then the evidence should include:
      | field          | value |
      | path_depth     | 4     |
    And recommendation may suggest flattening structure

  @story-5.2.1 @url
  Scenario: Special characters are identified
    When the tool finds URL with encoded characters "%20"
    Then the evidence should flag "contains_encoded_characters"
    And the specific characters should be listed

  @story-5.2.1 @url
  Scenario: Underscores flagged for SEO
    When the tool finds URL with underscores "/my_page_name"
    Then the evidence should include:
      | field   | value           |
      | finding | underscores_in_url |
    And recommendation should suggest using hyphens

  @story-5.2.1 @url
  Scenario: URL keyword presence assessed
    When the page targets keyword "widgets"
    And the URL is "/products/widgets"
    Then the evidence should include:
      | field            | value |
      | keyword_in_url   | true  |

  @story-5.2.1 @url
  Scenario: Good URL structure noted
    When the URL is "/products/blue-widgets"
    And it is under 75 characters
    And it uses hyphens
    And path depth is 2
    Then the evidence should show passing status for all checks

  # ===========================================================================
  # Story 5.3.1: Mobile Optimization Evidence
  # File: src/seo/advanced_analyzer.py (MobileSEOAnalyzer)
  # ===========================================================================

  @story-5.3.1 @mobile
  Scenario: Viewport meta tag presence captured
    When the tool finds viewport meta tag
    And the content is "width=device-width, initial-scale=1"
    Then the evidence should include:
      | field           | value                                 |
      | finding         | viewport_present                      |
      | evidence_string | width=device-width, initial-scale=1   |

  @story-5.3.1 @mobile
  Scenario: Missing viewport is flagged
    When the tool finds no viewport meta tag
    Then the evidence should include:
      | field    | value            |
      | finding  | viewport_missing |
      | severity | critical         |

  @story-5.3.1 @mobile
  Scenario: Viewport with fixed width flagged
    When the viewport has "width=1024"
    Then the evidence should include:
      | field           | value          |
      | finding         | fixed_viewport |
      | evidence_string | width=1024     |
    And recommendation should suggest responsive viewport

  @story-5.3.1 @mobile
  Scenario: Text size assessment
    When the tool detects small text sizes
    Then the evidence should include:
      | field   | value          |
      | finding | small_text     |
    And the threshold should be "< 16px base font"

  @story-5.3.1 @mobile
  Scenario: Touch target assessment
    When the tool detects small touch targets
    Then the evidence should include:
      | field     | value                |
      | finding   | small_touch_targets  |
      | threshold | < 48x48 pixels       |

  # ===========================================================================
  # Story 5.4.1: International SEO Evidence
  # File: src/seo/advanced_analyzer.py (InternationalSEOAnalyzer)
  # ===========================================================================

  @story-5.4.1 @international
  Scenario: Lang attribute captured
    When the tool finds lang="en-US" attribute
    Then the evidence should include:
      | field           | value          |
      | finding         | lang_attribute |
      | evidence_string | en-US          |

  @story-5.4.1 @international
  Scenario: Missing lang attribute flagged
    When the tool finds no lang attribute
    Then the evidence should include:
      | field   | value               |
      | finding | missing_lang        |
      | severity| warning             |

  @story-5.4.1 @international
  Scenario: Hreflang tags listed
    When the tool finds hreflang tags for en, es, fr
    Then the evidence should list all hreflang configurations:
      | hreflang | href                        |
      | en       | https://example.com/        |
      | es       | https://example.com/es/     |
      | fr       | https://example.com/fr/     |

  @story-5.4.1 @international
  Scenario: Missing hreflang for detected languages
    When content appears in multiple languages
    And hreflang tags are not configured
    Then the evidence should flag "missing_hreflang"
    And recommendation should list detected languages

  @story-5.4.1 @international
  Scenario: Hreflang self-reference check
    When hreflang tags exist
    And the current page is not self-referenced
    Then the evidence should flag "missing_self_reference"
    And recommendation should explain importance

  @story-5.4.1 @international
  Scenario: Invalid hreflang code flagged
    When hreflang contains invalid code "english"
    Then the evidence should include:
      | field           | value            |
      | finding         | invalid_hreflang |
      | evidence_string | english          |
    And recommendation should suggest valid ISO code "en"
