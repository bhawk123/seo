@epic-12 @ai-cache @medium
Feature: AI Response Caching
  As a crawler developer
  I want LLM responses cached
  So that redundant API calls are eliminated, reducing cost and improving latency

  Background:
    Given the AI cache is configured with:
      | parameter   | value |
      | ttl_hours   | 24    |
      | max_size_mb | 100   |
      | enabled     | true  |
    And the cache database is initialized
    And the cache directory is empty

  # ===========================================================================
  # Feature 12.1: AI Response Caching
  # Story 12.1.1: Implement AI Cache Core
  # ===========================================================================

  @story-12.1.1 @cache-core
  Scenario: Cache hit returns stored response
    Given a prompt "Analyze this page" with context {"url": "example.com"} has been cached
    When the same prompt and context are requested via get_response()
    Then the cached response should be returned
    And no external API call should be made
    And cache hit count should increment

  @story-12.1.1 @cache-core
  Scenario: Cache miss triggers API call and storage
    Given the cache is empty
    When a new prompt "Summarize text" with context {"text": "Long article"} is requested
    Then an external API call should be simulated
    And the simulated response should be stored in the cache
    And cache miss count should increment

  @story-12.1.1 @cache-core
  Scenario: Content-addressable key generation
    Given prompt "Analyze" and context {"title": "Test Page"}
    When the cache key is computed
    Then it should be a SHA-256 hash of the normalized prompt and context
    And the same inputs should consistently produce the same key
    And changing context order should produce the same key

  @story-12.1.1 @cache-core
  Scenario: Cache stores JSON response files in structured directory
    Given a response is stored for a prompt
    Then a JSON file named after its content hash should exist in the cache directory
    And the file content should match the stored response

  @story-12.1.1 @cache-core
  Scenario: Cache honors TTL
    Given an entry with TTL 1 hour is cached
    And 61 minutes have passed
    When the entry is requested
    Then it should be considered expired
    And trigger a cache miss (or return expired with option to refresh)

  # ===========================================================================
  # Feature 12.1: AI Response Caching
  # Story 12.1.2: Implement Cache Entry Management
  # ===========================================================================

  @story-12.1.2 @entry-management
  Scenario: Expired entries are cleaned up
    Given 3 cache entries: one expired, two unexpired
    When clean_expired() runs
    Then the expired entry should be removed from the database and file system
    And the two unexpired entries should remain

  @story-12.1.2 @entry-management
  Scenario: Size limit enforces LRU eviction
    Given the cache contains 95 MB of data
    And max_size_mb is 100 MB
    When a new 10 MB entry is added
    Then the least recently used entries should be evicted until total size is below 100 MB
    And the new entry should be successfully added

  @story-12.1.2 @entry-management
  Scenario: Hit count and timestamps are tracked
    Given a cache entry exists
    When it is accessed 5 times
    Then its hit_count should be 5
    And its last_accessed timestamp should be updated on each access

  @story-12.1.2 @entry-management
  Scenario: Manual invalidation removes entry
    Given a cache entry for "prompt_X" exists
    When invalidate("prompt_X") is called
    Then the entry should be removed from the cache

  # ===========================================================================
  # Feature 12.1: AI Response Caching
  # Story 12.1.3: Implement Similarity Search
  # ===========================================================================

  @story-12.1.3 @similarity-search
  Scenario: Similar prompts can be found
    Given cache contains entries for "Analyze SEO for homepage" and "Analyze meta tags on homepage"
    When searching for similar to "Analyze SEO for product page meta tags" with a similarity threshold of 0.7
    Then both "Analyze SEO for homepage" and "Analyze meta tags on homepage" entries should be returned
    And each result should include a confidence score (e.g., 0.85, 0.75)

  @story-12.1.3 @similarity-search
  Scenario: Search with prompt-only hash
    Given an entry with prompt "what is SEO" and some context
    When a similarity search is performed using only the prompt "what is SEO"
    Then the entry should be found based on its prompt hash, ignoring context differences

  @story-12.1.3 @similarity-search
  Scenario: Prefix matching finds related queries
    Given cache entries for "What is SEO?", "What is Technical SEO?", "What is Content SEO?"
    When searching for "What is SEO"
    Then all three entries should be returned as similar
    And ordered by relevance

  @story-12.1.3 @similarity-search
  Scenario: No similar prompts found
    Given cache contains entries unrelated to "weather report"
    When searching for similar to "current weather report"
    Then an empty list should be returned

  # ===========================================================================
  # Feature 12.1: AI Response Caching
  # Story 12.1.4: Integrate with LLM Client
  # ===========================================================================

  @story-12.1.4 @integration @llm-client
  Scenario: LLM client uses cache transparently for existing entries
    Given LLMClient.analyze("prompt A") was called and cached the response
    When LLMClient.analyze("prompt A") is called again
    Then the cached response should be returned directly
    And no actual LLM API call should occur

  @story-12.1.4 @integration @llm-client
  Scenario: LLM client populates cache on new responses
    Given LLMClient.analyze("prompt B") is called for the first time
    When the LLM API returns a response
    Then the response should be stored in the AI cache for "prompt B"
    And cache hit/miss statistics should be updated

  @story-12.1.4 @integration @llm-client
  Scenario: Cache hit/miss statistics are tracked
    Given 100 LLM requests have been made
    And 40 were cache hits, 60 were cache misses
    When AICache.get_stats() is called
    Then the result should show:
      | field        | value |
      | total_requests | 100 |
      | total_hits   | 40    |
      | total_misses | 60    |
      | hit_rate     | 0.4   |

  @story-12.1.4 @integration @llm-client
  Scenario: Evidence includes cache status
    Given LLMClient.analyze() is called
    When the call results in a cache hit
    Then the EvidenceRecord generated should include "cache_status: hit"
    When the call results in a cache miss
    Then the EvidenceRecord generated should include "cache_status: miss"