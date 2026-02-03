@epic-7 @structure @lower-priority
Feature: Site Structure Evidence
  As an SEO analyst reviewing site structure
  I want evidence for crawlability, redirects, third-party, and resource analysis
  So that I can optimize site architecture

  Background:
    Given the SEO analysis tool has analyzed site structure
    And evidence capture is enabled for structure components

  # ===========================================================================
  # Story 7.1.1: Robots.txt Evidence
  # File: src/seo/crawlability.py
  # ===========================================================================

  @story-7.1.1 @crawlability @robots
  Scenario: Robots.txt rules are captured
    When the tool parses robots.txt
    And it contains "Disallow: /admin/"
    Then the evidence should include:
      | field           | value         |
      | finding         | disallow_rule |
      | evidence_string | /admin/       |
      | user_agent      | *             |

  @story-7.1.1 @crawlability @robots
  Scenario: Sitemap references are captured
    When the tool finds sitemap reference in robots.txt
    And the sitemap URL is "https://example.com/sitemap.xml"
    Then the evidence should include:
      | field           | value                            |
      | finding         | sitemap_reference                |
      | evidence_string | https://example.com/sitemap.xml  |

  @story-7.1.1 @crawlability @robots
  Scenario: Missing robots.txt flagged
    When robots.txt is not found
    Then the evidence should include:
      | field   | value              |
      | finding | missing_robots_txt |

  @story-7.1.1 @crawlability @robots
  Scenario: Multiple user-agent rules captured
    When robots.txt has rules for Googlebot and Bingbot
    Then the evidence should list rules by user-agent:
      | user_agent | disallow_count |
      | *          | 2              |
      | Googlebot  | 1              |
      | Bingbot    | 3              |

  @story-7.1.1 @crawlability @sitemap
  Scenario: Sitemap URL count captured
    When the tool parses sitemap.xml
    And it contains 150 URLs
    Then the evidence should include:
      | field          | value |
      | sitemap_urls   | 150   |

  @story-7.1.1 @crawlability @orphan
  Scenario: Orphan pages identified
    When pages are crawled but not linked internally
    Then the evidence should include:
      | field        | value        |
      | finding      | orphan_pages |
    And the orphan page URLs should be listed

  # ===========================================================================
  # Story 7.2.1: Redirect Chain Evidence
  # File: src/seo/redirect_analyzer.py
  # ===========================================================================

  @story-7.2.1 @redirect
  Scenario: Redirect chain shows full path
    When the tool identifies a redirect chain
    And the chain is: /old → /new → /final
    Then the evidence should include the full chain:
      | hop | url    | status |
      | 1   | /old   | 301    |
      | 2   | /new   | 302    |
      | 3   | /final | 200    |

  @story-7.2.1 @redirect
  Scenario: Long redirect chain is flagged
    When the redirect chain has 5 hops
    And the threshold is 4 hops
    Then the evidence should include:
      | field          | value               |
      | finding        | long_redirect_chain |
      | measured_value | 5                   |
      | threshold      | > 4 hops            |

  @story-7.2.1 @redirect
  Scenario: Redirect time estimation shown
    When the redirect chain has 3 hops
    And estimated time per hop is 50ms
    Then the evidence should include:
      | field          | value |
      | time_waste_ms  | 150   |

  @story-7.2.1 @redirect
  Scenario: Mixed redirect types captured
    When the chain includes both 301 and 302 redirects
    Then the evidence should note the mixed types
    And a recommendation may suggest using consistent 301s

  @story-7.2.1 @redirect
  Scenario: Redirect percentage calculated
    When 15 of 100 pages involve redirects
    Then the evidence should include:
      | field               | value |
      | redirect_percentage | 15%   |

  # ===========================================================================
  # Story 7.3.1: Third-Party Impact Evidence
  # File: src/seo/third_party_analyzer.py
  # ===========================================================================

  @story-7.3.1 @third-party
  Scenario: Third-party domains are categorized
    When the tool analyzes third-party requests
    Then the evidence should categorize domains:
      | domain                | category  | requests | bytes  |
      | google-analytics.com  | analytics | 3        | 45KB   |
      | doubleclick.net       | ads       | 8        | 120KB  |
      | cloudflare.com        | cdn       | 5        | 200KB  |

  @story-7.3.1 @third-party
  Scenario: High-impact domain is flagged
    When a third-party domain accounts for >10% of page weight
    Then the evidence should include:
      | field          | value               |
      | finding        | high_impact_domain  |
      | domain         | tracking.example    |
      | percentage     | 15                  |

  @story-7.3.1 @third-party
  Scenario: Category totals summarized
    When the tool analyzes third-party impact
    Then the evidence should include category totals:
      | category  | total_requests | total_bytes |
      | analytics | 5              | 75KB        |
      | ads       | 12             | 250KB       |
      | cdn       | 8              | 180KB       |
      | social    | 3              | 45KB        |

  @story-7.3.1 @third-party
  Scenario: Unknown domains flagged
    When a third-party domain is not in known categories
    Then the evidence should include:
      | field    | value           |
      | category | unknown         |
      | domain   | mystery.example |

  @story-7.3.1 @third-party
  Scenario: Third-party performance recommendation
    When third-party resources exceed 30% of page weight
    Then the evidence should include performance_warning
    And recommendation should suggest audit of third-party scripts

  # ===========================================================================
  # Story 7.4.1: Page Weight Evidence
  # File: src/seo/resource_analyzer.py
  # ===========================================================================

  @story-7.4.1 @resource
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

  @story-7.4.1 @resource
  Scenario: Bloated JS is flagged
    When JavaScript size is 850KB
    And the threshold is 500KB
    Then the evidence should include:
      | field          | value      |
      | finding        | bloated_js |
      | measured_value | 850        |
      | unit           | KB         |
      | threshold      | > 500 KB   |

  @story-7.4.1 @resource
  Scenario: Bloated images flagged
    When image size is 1.5MB
    And the threshold is 1MB
    Then the evidence should include:
      | field          | value          |
      | finding        | bloated_images |
      | measured_value | 1536           |
      | unit           | KB             |
      | threshold      | > 1024 KB      |

  @story-7.4.1 @resource
  Scenario: Average page weight calculated
    When 50 pages have been analyzed
    Then the evidence should include:
      | field            | value |
      | average_weight   | 1.2MB |
      | pages_analyzed   | 50    |

  @story-7.4.1 @resource
  Scenario: Heaviest pages identified
    When page weight analysis is complete
    Then the evidence should list top 5 heaviest pages:
      | url                | total_weight |
      | /media-gallery     | 3.5MB        |
      | /product-showcase  | 2.8MB        |
      | /team              | 2.1MB        |

  @story-7.4.1 @resource
  Scenario: Good page weight noted
    When a page is under all thresholds
    Then the evidence should show passing status
    And no bloat findings should be created
