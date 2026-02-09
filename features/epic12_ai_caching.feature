@epic-12 @ai-cache @medium
Feature: AI Response Caching
  As a crawler developer
  I want LLM responses cached
  So that redundant API calls are eliminated

  Background:
    Given the AI cache is configured with:
      | parameter   | value |
      | ttl_hours   | 24    |
      | max_size_mb | 100   |
      | enabled     | true  |
    And the cache directory exists

  # ===========================================================================
  # Feature 12.1: AI Response Caching
  # Story 12.1.1: Implement AI Cache Core
  # ===========================================================================

  @story-12.1.1 @cache-core
  Scenario: Cache hit returns stored response
    Given a prompt "Analyze this page" with context has been cached
    And the cached response is {"score": 85}
    When the same prompt and context are requested
    Then the cached response {"score": 85} should be returned
    And no API call should be made

  @story-12.1.1 @cache-core
  Scenario: Cache miss triggers API call and storage
    Given the cache is empty
    When a new prompt "Evaluate SEO" is requested
    Then an API call should be made
    And the response should be stored in cache
    And subsequent requests should return cached response

  @story-12.1.1 @cache-core
  Scenario: Content-addressable key generation
    Given prompt "Analyze" and context {"title": "Test"}
    When the cache key is computed
    Then it should be a SHA-256 hash
    And the hash should be 64 characters
    And the same inputs should produce the same key

  @story-12.1.1 @cache-core
  Scenario: Different context produces different key
    Given prompt "Analyze" and context {"title": "Test A"}
    And prompt "Analyze" and context {"title": "Test B"}
    When cache keys are computed
    Then the keys should be different

  @story-12.1.1 @cache-core
  Scenario: Cache uses SQLite for metadata
    When the cache is initialized
    Then a SQLite database should be created
    And it should have a cache_entries table
    And indexes should exist for expires_at and prompt_hash

  @story-12.1.1 @cache-core
  Scenario: Responses stored as JSON files
    When a response is cached
    Then a JSON file should be created
    And the path should be responses/{key[:2]}/{key}.json
    And the file should contain the full response

  @story-12.1.1 @cache-core
  Scenario: Cache can be disabled
    Given enabled is set to false
    When a prompt is requested
    Then the cache should not be checked
    And the response should not be stored

  # ===========================================================================
  # Feature 12.1: AI Response Caching
  # Story 12.1.2: Implement Cache Entry Management
  # ===========================================================================

  @story-12.1.2 @entry-management
  Scenario: Expired entries are cleaned up
    Given a cache entry was created 25 hours ago
    And TTL is 24 hours
    When clean_expired() runs
    Then the entry should be removed from SQLite
    And the JSON file should be deleted

  @story-12.1.2 @entry-management
  Scenario: Non-expired entries are retained
    Given a cache entry was created 12 hours ago
    And TTL is 24 hours
    When clean_expired() runs
    Then the entry should still exist

  @story-12.1.2 @entry-management
  Scenario: Size limit enforces LRU eviction
    Given the cache is at 99 MB
    And a new 5 MB entry is added
    When the size limit is enforced
    Then least recently used entries should be evicted
    And total size should be under 100 MB

  @story-12.1.2 @entry-management
  Scenario: Hit count is tracked
    Given a cache entry exists
    When it is accessed 5 times
    Then hit_count should be 5
    And last_hit should be updated to current time

  @story-12.1.2 @entry-management
  Scenario: Manual invalidation removes entry
    Given a cache entry with key "abc123"
    When invalidate("abc123") is called
    Then the entry should be removed
    And get("abc123") should return None

  @story-12.1.2 @entry-management
  Scenario: Clear removes all entries
    Given 10 cache entries exist
    When clear() is called
    Then all entries should be removed
    And the cache should be empty

  @story-12.1.2 @entry-management
  Scenario: CacheEntry has timestamp tracking
    When a new cache entry is created
    Then it should have created_at timestamp
    And it should have expires_at timestamp
    And expires_at should be created_at + ttl_hours

  # ===========================================================================
  # Feature 12.1: AI Response Caching
  # Story 12.1.3: Implement Similarity Search
  # ===========================================================================

  @story-12.1.3 @similarity-search
  Scenario: Similar prompts can be found by prefix
    Given cache contains entry for prompt_hash starting with "abc123"
    When searching for similar prompts with prefix "abc1"
    Then the entry should be returned

  @story-12.1.3 @similarity-search
  Scenario: Prompt-only hash enables similarity matching
    Given prompts "Analyze SEO for homepage" and "Analyze SEO for product page"
    When prompt-only hashes are computed
    Then they should share a common prefix
    And find_similar() should find related entries

  @story-12.1.3 @similarity-search
  Scenario: Similarity results include metadata
    Given similar entries are found
    When find_similar() returns results
    Then each result should include:
      | field      |
      | key        |
      | prompt_hash|
      | hit_count  |
      | created_at |

  @story-12.1.3 @similarity-search
  Scenario: Empty result for no matches
    Given cache contains unrelated prompts
    When searching for similar to "unique query xyz"
    Then an empty list should be returned

  # ===========================================================================
  # Feature 12.1: AI Response Caching
  # Story 12.1.4: Integrate with LLM Client
  # ===========================================================================

  @story-12.1.4 @llm-integration
  Scenario: LLM client checks cache before API call
    Given a cached response exists for the prompt
    When LLMClient.analyze() is called
    Then the cache should be checked first
    And the cached response should be returned
    And no API call should be made

  @story-12.1.4 @llm-integration
  Scenario: Cache miss makes API call and stores result
    Given no cached response exists
    When LLMClient.analyze() is called
    Then an API call should be made
    And the response should be stored in cache
    And the response should be returned

  @story-12.1.4 @llm-integration
  Scenario: Evidence includes cache status for hit
    Given a cached response exists
    When analysis is performed
    Then the EvidenceRecord should include:
      | field        | value |
      | cache_hit    | true  |
      | cache_key    | <key> |

  @story-12.1.4 @llm-integration
  Scenario: Evidence includes cache status for miss
    Given no cached response exists
    When analysis is performed
    Then the EvidenceRecord should include:
      | field        | value |
      | cache_hit    | false |
      | model_id     | <model> |

  @story-12.1.4 @llm-integration
  Scenario: Cache statistics are tracked
    Given 100 LLM requests have been made
    And 40 were cache hits
    When cache.stats() is called
    Then the result should show:
      | field        | value |
      | hit_rate     | 0.4   |
      | total_hits   | 40    |
      | total_misses | 60    |

  @story-12.1.4 @llm-integration
  Scenario: Cache statistics include size info
    When cache.stats() is called
    Then the result should include:
      | field          |
      | total_entries  |
      | total_size_mb  |
      | oldest_entry   |
      | newest_entry   |

  @story-12.1.4 @llm-integration
  Scenario: Thread safety for concurrent access
    Given multiple threads accessing the cache
    When concurrent get() and put() operations occur
    Then no race conditions should occur
    And data should remain consistent

  @story-12.1.4 @llm-integration
  Scenario: Cache integrates with evidence system
    Given an LLM response is cached
    When the cache entry is created
    Then it should be auditable via evidence
    And the prompt hash should enable reproducibility

  # ===========================================================================
  # Edge Cases and Error Handling
  # ===========================================================================

  @edge-case
  Scenario: Corrupted cache file is handled gracefully
    Given a cache entry exists
    And the JSON file is corrupted
    When get() is called for that entry
    Then None should be returned
    And the corrupted entry should be invalidated
    And no exception should be raised

  @edge-case
  Scenario: SQLite database corruption recovery
    Given the SQLite database is corrupted
    When the cache is initialized
    Then a new database should be created
    And a warning should be logged

  @edge-case
  Scenario: Disk full during cache write
    Given the disk is full
    When put() is called
    Then the operation should fail gracefully
    And a warning should be logged
    And the LLM response should still be returned

  @edge-case
  Scenario: Large response is handled
    Given an LLM response is 50 MB
    When put() is called
    Then the response should be stored
    And size limit enforcement should trigger if needed

  # ===========================================================================
  # Feature 12.2: AICache Interaction with Stale Data
  # Story 12.2.1: Cache Freshness and Selector Interaction
  # ===========================================================================

  @story-12.2.1 @stale-data @selector-interaction
  Scenario: Stale SelectorEntry triggers related cache invalidation
    Given a SelectorEntry for "email_field" is marked as stale
    And cached LLM responses reference form interactions with "email_field"
    When stale data cleanup runs
    Then related cache entries should be invalidated
    And fresh LLM analysis should be triggered on next request

  @story-12.2.1 @stale-data @selector-interaction
  Scenario: Expired SelectorEntry propagates to dependent caches
    Given SelectorEntry "#old-form" expired 7 days ago
    And AICache has entries that depend on form analysis using "#old-form"
    When the system detects the expired selector
    Then dependent cache entries should be marked for refresh
    And a flag should indicate "requires_re-analysis"

  @story-12.2.1 @stale-data @selector-interaction
  Scenario: Cache freshness checked before returning hit
    Given a cache entry was created 20 hours ago
    And TTL is 24 hours
    And the source page has been modified since cache creation
    When get() is called
    Then the cache should verify content freshness
    And if page changed, should return None (forcing refresh)

  # ===========================================================================
  # Feature 12.2: AICache Interaction with Stale Data
  # Story 12.2.2: LRU Eviction Impact on Critical Data
  # ===========================================================================

  @story-12.2.2 @lru-eviction @critical-data
  Scenario: LRU eviction considers selector importance
    Given cache is at capacity
    And some entries are related to high-confidence selectors
    And some entries are related to low-confidence selectors
    When LRU eviction runs
    Then entries for low-confidence selectors should be evicted first
    And high-confidence selector data should be preserved longer

  @story-12.2.2 @lru-eviction @critical-data
  Scenario: Frequently accessed entries resist eviction
    Given entry A was accessed 50 times
    And entry B was accessed 2 times
    And entry A is older than entry B
    When LRU eviction runs
    Then entry B should be evicted before entry A
    And access frequency should be weighted

  @story-12.2.2 @lru-eviction @critical-data
  Scenario: Critical selector data can be pinned
    Given a SelectorEntry is marked as "critical" (e.g., payment form)
    And related AICache entries exist
    When LRU eviction runs
    Then pinned entries should never be evicted
    And an alternative entry should be evicted instead

  @story-12.2.2 @lru-eviction @critical-data
  Scenario: Eviction logs affected selectors
    Given LRU eviction removes an entry
    When the entry had selector dependencies
    Then the eviction should be logged
    And affected selectors should be noted for re-analysis
    And metrics should track selector-related evictions

  # ===========================================================================
  # Feature 12.2: AICache Interaction with Stale Data
  # Story 12.2.3: Cross-Component Staleness Propagation
  # ===========================================================================

  @story-12.2.3 @staleness-propagation
  Scenario: Website structure change invalidates multiple caches
    Given SelectorLibrary detects major page structure change
    When propagate_staleness() is called
    Then AICache entries for affected pages should be invalidated
    And BrowserPool should be notified to refresh contexts
    And rate limiter metrics should reset for the domain

  @story-12.2.3 @staleness-propagation
  Scenario: Staleness events create audit trail
    Given staleness is detected in SelectorEntry
    When the staleness propagates to AICache
    Then an EvidenceRecord should be created
    And it should document the staleness chain
    And it should include timestamps and component IDs

  @story-12.2.3 @staleness-propagation
  Scenario: Selective invalidation based on staleness scope
    Given SelectorEntry for "checkout_form" becomes stale
    When invalidation propagates
    Then only checkout-related cache entries should be invalidated
    And unrelated entries (e.g., homepage analysis) should be preserved
    And scope should be determined by component_id matching
