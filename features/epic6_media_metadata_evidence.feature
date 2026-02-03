@epic-6 @media @metadata @medium-priority
Feature: Media and Metadata Evidence
  As an SEO analyst reviewing media and metadata
  I want detailed evidence for image, social, and schema findings
  So that I can optimize these elements effectively

  Background:
    Given the SEO analysis tool has analyzed media and metadata
    And evidence capture is enabled for media components

  # ===========================================================================
  # Story 6.1.1: Image Optimization Evidence
  # File: src/seo/image_analyzer.py
  # ===========================================================================

  @story-6.1.1 @image
  Scenario: Image format recommendation includes evidence
    When the tool identifies a JPEG image suitable for WebP
    Then the evidence should include:
      | field             | value           |
      | finding           | format_upgrade  |
      | current_format    | jpeg            |
      | recommended       | webp            |
      | image_src         | /images/hero.jpg|
      | estimated_savings | 30%             |

  @story-6.1.1 @image
  Scenario: Missing alt text includes image identifier
    When the tool finds image without alt text
    And the image src is "/images/product-123.jpg"
    Then the evidence should include:
      | field           | value                    |
      | finding         | missing_alt              |
      | source_location | /images/product-123.jpg  |

  @story-6.1.1 @image
  Scenario: Missing dimensions shows CLS risk
    When the tool finds image without width/height
    Then the evidence should include:
      | field          | value              |
      | finding        | missing_dimensions |
      | severity       | warning            |
    And the evidence should reference CLS risk

  @story-6.1.1 @image
  Scenario: Missing lazy loading flagged
    When the tool finds above-fold image without lazy loading
    Then the evidence should NOT flag lazy loading issue
    When the tool finds below-fold image without lazy loading
    Then the evidence should include:
      | field   | value               |
      | finding | missing_lazy_loading|

  @story-6.1.1 @image
  Scenario: Modern format adoption tracked
    When the tool analyzes all images on the page
    Then the evidence should include format breakdown:
      | format | count | percentage |
      | jpeg   | 10    | 50%        |
      | png    | 6     | 30%        |
      | webp   | 4     | 20%        |
    And recommendation should target non-modern formats

  @story-6.1.1 @image
  Scenario: Potential savings estimated
    When the tool finds 5 JPEG images totaling 500KB
    Then the evidence should include:
      | field                | value |
      | potential_savings_kb | 150   |
      | savings_percentage   | 30%   |

  # ===========================================================================
  # Story 6.2.1: Social Meta Evidence
  # File: src/seo/social_analyzer.py
  # ===========================================================================

  @story-6.2.1 @social @og
  Scenario: Open Graph tags show completeness
    When the tool analyzes Open Graph tags
    Then the evidence should list each tag with status:
      | property        | status  | value                    |
      | og:title        | present | Page Title               |
      | og:description  | present | Description text...      |
      | og:image        | present | https://example.com/img  |
      | og:url          | missing | null                     |
      | og:type         | missing | null                     |

  @story-6.2.1 @social @twitter
  Scenario: Twitter Card scoring shows calculation
    When the tool calculates Twitter Card score of 75
    Then the evidence should include score breakdown:
      | property            | status  | points |
      | twitter:card        | present | 25     |
      | twitter:title       | present | 25     |
      | twitter:description | present | 25     |
      | twitter:image       | missing | 0      |

  @story-6.2.1 @social @og
  Scenario: Invalid og:image URL is flagged
    When og:image is "/images/share.jpg" (relative URL)
    Then the evidence should include:
      | field   | value                |
      | finding | invalid_og_image_url |
      | issue   | must_be_absolute_url |

  @story-6.2.1 @social @twitter
  Scenario: Invalid twitter:card type flagged
    When twitter:card is "invalid_type"
    Then the evidence should include:
      | field   | value                  |
      | finding | invalid_twitter_card   |
    And valid types should be listed in recommendation

  @story-6.2.1 @social
  Scenario: Duplicate social meta captured
    When og:title differs from page title
    Then the evidence should note the discrepancy
    And both values should be captured

  @story-6.2.1 @social
  Scenario: Perfect social meta score
    When all required OG and Twitter tags are present
    And all values are valid
    Then the evidence should show:
      | field     | value |
      | og_score  | 100   |
      | tw_score  | 100   |

  # ===========================================================================
  # Story 6.3.1: Schema Validation Evidence
  # File: src/seo/structured_data.py
  # ===========================================================================

  @story-6.3.1 @schema
  Scenario: Schema type detection includes raw JSON-LD
    When the tool detects a Product schema
    Then the evidence should include:
      | field       | value           |
      | finding     | schema_detected |
      | schema_type | Product         |
    And the evidence_string should contain the raw JSON-LD

  @story-6.3.1 @schema
  Scenario: Validation error includes field path
    When the Product schema is missing "price" field
    Then the evidence should include:
      | field          | value                    |
      | finding        | schema_validation_error  |
      | schema_type    | Product                  |
      | missing_field  | price                    |
      | spec_reference | schema.org/Product       |

  @story-6.3.1 @schema
  Scenario: Rich result eligibility shows requirements
    When Product schema is eligible for rich results
    And it has name, image, price, and availability
    Then the evidence should include:
      | field                | value |
      | rich_result_eligible | true  |
    And the evidence should list the satisfied requirements

  @story-6.3.1 @schema
  Scenario: Rich result ineligibility shows missing fields
    When Product schema is missing required fields for rich results
    Then the evidence should include:
      | field                | value |
      | rich_result_eligible | false |
    And missing requirements should be listed

  @story-6.3.1 @schema
  Scenario: Multiple schema types detected
    When the page has Organization and Product schemas
    Then the evidence should list all detected types:
      | schema_type  |
      | Organization |
      | Product      |

  @story-6.3.1 @schema
  Scenario: Microdata detected separately
    When the tool detects Microdata (not JSON-LD)
    Then the evidence should include:
      | field        | value     |
      | format       | microdata |
      | schema_type  | Product   |

  @story-6.3.1 @schema
  Scenario: Validation warning (non-critical)
    When schema has recommended but not required field missing
    Then the evidence should include:
      | field    | value              |
      | finding  | schema_warning     |
      | severity | info               |

  @story-6.3.1 @schema
  Scenario: Invalid JSON-LD syntax
    When JSON-LD has syntax errors
    Then the evidence should include:
      | field   | value             |
      | finding | invalid_json_ld   |
    And the parse error message should be captured
