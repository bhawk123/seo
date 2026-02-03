@epic-4 @content @medium-priority
Feature: Content Quality Evidence
  As an SEO analyst reviewing content metrics
  I want to see how quality scores were calculated
  So that I can verify the analysis accuracy

  Background:
    Given the SEO analysis tool has analyzed page content
    And evidence capture is enabled for content quality

  # ===========================================================================
  # Story 4.1.1: Readability Formula Inputs
  # File: src/seo/content_quality.py
  # ===========================================================================

  @story-4.1.1 @readability
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

  @story-4.1.1 @readability
  Scenario: Readability grade shows derivation
    When the tool assigns readability grade "8th Grade"
    And the readability score is 65.2
    Then the evidence should include the grade mapping table reference
    And the evidence should show which range 65.2 falls into

  @story-4.1.1 @readability
  Scenario: Very easy content scored appropriately
    When the tool calculates a readability score of 90
    Then the grade should be "5th Grade"
    And the evidence should show score range 90-100 maps to 5th Grade

  @story-4.1.1 @readability
  Scenario: College level content scored appropriately
    When the tool calculates a readability score of 25
    Then the grade should be "College Graduate"
    And the evidence should show score range 0-30 maps to College Graduate

  @story-4.1.1 @readability
  Scenario: Formula calculation is verifiable
    When the tool calculates readability
    Then the evidence should include the Flesch formula:
      | formula | 206.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words) |
    And plugging in the components should equal the calculated score

  # ===========================================================================
  # Story 4.1.2: Keyword Density Evidence
  # ===========================================================================

  @story-4.1.2 @keyword-density
  Scenario: Keyword density shows calculation basis
    When the tool calculates keyword density for "widget"
    And "widget" appears 17 times in 850 words
    Then the evidence should include:
      | field            | value           |
      | finding          | keyword_density |
      | keyword          | widget          |
      | occurrences      | 17              |
      | total_words      | 850             |
      | density_percent  | 2.0             |

  @story-4.1.2 @keyword-density
  Scenario: Stop word exclusion is documented
    When the tool calculates keyword density
    And 150 stop words were excluded
    Then the evidence should include:
      | field               | value |
      | stop_words_excluded | 150   |
      | analyzed_word_count | 700   |

  @story-4.1.2 @keyword-density
  Scenario: Top keywords are ranked
    When the tool identifies top 10 keywords
    Then the evidence should list keywords with:
      | rank | keyword  | occurrences | density |
      | 1    | widget   | 25          | 2.9%    |
      | 2    | product  | 18          | 2.1%    |
      | 3    | quality  | 12          | 1.4%    |
    And keywords should be sorted by occurrence count

  @story-4.1.2 @keyword-density
  Scenario: Keyword density formula is shown
    When keyword density is calculated
    Then the evidence should include formula:
      | formula | (keyword_occurrences / analyzed_word_count) * 100 |

  @story-4.1.2 @keyword-density
  Scenario: High keyword density is flagged
    When a keyword has density above 3%
    Then the evidence should include a warning
    And the recommendation should mention keyword stuffing risk

  # ===========================================================================
  # Story 4.1.3: Difficult Word Evidence
  # ===========================================================================

  @story-4.1.3 @difficult-words
  Scenario: Difficult word count shows threshold
    When the tool identifies 45 difficult words
    Then the evidence should include:
      | field            | value           |
      | finding          | difficult_words |
      | measured_value   | 45              |
      | threshold        | >= 3 syllables  |

  @story-4.1.3 @difficult-words
  Scenario: Sample difficult words are listed
    When the tool identifies difficult words
    Then the evidence should include a sample_words list
    And the sample should contain up to 10 words
    And each word should have its syllable count:
      | word          | syllables |
      | technology    | 4         |
      | infrastructure| 4         |
      | optimization  | 5         |

  @story-4.1.3 @difficult-words
  Scenario: Difficult word percentage calculated
    When 45 difficult words exist in 850 total words
    Then the evidence should include:
      | field      | value |
      | percentage | 5.3   |
    And the percentage calculation should be verifiable

  @story-4.1.3 @difficult-words
  Scenario: No difficult words handled
    When the tool finds no difficult words
    Then the evidence should include:
      | field          | value |
      | measured_value | 0     |
    And no sample_words list should be present

  # ===========================================================================
  # Edge Cases
  # ===========================================================================

  @edge-case
  Scenario: Very short content analysis
    When the content has only 20 words
    Then readability metrics should be flagged as unreliable
    And the evidence should note "Insufficient content for accurate analysis"
    And the confidence should be "Low"

  @edge-case
  Scenario: Content with no sentences
    When the content has no sentence-ending punctuation
    Then the tool should handle the edge case
    And the evidence should note the parsing issue
    And avg_words_per_sentence should be handled gracefully

  @edge-case
  Scenario: Non-English content
    When the content is not primarily English
    Then the evidence should include language_warning
    And readability metrics may be less accurate
    And the confidence should reflect uncertainty

  @edge-case
  Scenario: HTML stripped for analysis
    When content contains HTML tags
    Then the evidence should note "HTML tags stripped"
    And word count should reflect visible text only
