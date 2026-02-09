# Spectrum Component Migration Log

> **Status:** COMPLETE
> **Created:** 2026-02-08
> **Completed:** 2026-02-08
> **Source:** BORROW.md Analysis
> **Target:** SEO Project Infrastructure Upgrade

---

## Executive Summary

This log tracks the migration of best-in-class components from the Spectrum project into SEO. Based on the BORROW.md analysis, SEO has adopted all key components from Spectrum to improve browser pool management, stealth/anti-detection, rate limiting, selector strategies, and LLM caching.

### Migration Status - ALL COMPLETE

| Component | Priority | Status | Location |
|-----------|----------|--------|----------|
| Browser Pool | Critical | COMPLETE | `infrastructure/browser_pool.py` |
| undetected-chromedriver | Critical | COMPLETE | `infrastructure/undetected_browser.py` |
| Adaptive Rate Limiter | High | COMPLETE | `infrastructure/rate_limiter.py` |
| reCAPTCHA Detection | High | COMPLETE | `utils/challenge_handler.py` |
| Selector Library | High | COMPLETE | `intelligence/selector_library.py` |
| AI Cache | Medium | COMPLETE | `intelligence/ai_cache.py` |

### Additional Gaps Implemented

| Gap | Description | Status | Location |
|-----|-------------|--------|----------|
| #2 | JS Rendering Metrics (FCP, CLS, LCP) | COMPLETE | `infrastructure/performance_metrics.py` |
| #3 | Cross-Browser Testing | COMPLETE | `infrastructure/cross_browser.py` |
| #4 | Dynamic Selector Handling (React/Vue) | COMPLETE | `intelligence/dynamic_selectors.py` |
| #6 | Smart IP/Proxy Rotation | COMPLETE | `infrastructure/proxy_rotation.py` |
| #7 | Request Timing Signature Evasion | COMPLETE | `infrastructure/timing_evasion.py` |

**Total Implementation:** All components ported and additional gaps filled

---

## Change Log

### 2026-02-08 - Implementation Complete

**Core Components Ported:**
- Created `infrastructure/browser_pool.py` - Browser pool with health monitoring, recycling
- Created `infrastructure/undetected_browser.py` - Stealth browser with nodriver/UC backend
- Created `infrastructure/rate_limiter.py` - Adaptive and token bucket rate limiting
- Created `intelligence/selector_library.py` - Selector persistence with confidence tracking
- Created `intelligence/site_profile.py` - Site/page/form profiles with metadata
- Created `intelligence/ai_cache.py` - Content-addressable LLM response caching
- Updated `utils/challenge_handler.py` - reCAPTCHA detection with evidence capture
- Updated `utils/human_simulator.py` - Human-like interaction simulation

**Additional Gap Implementations:**
- Created `infrastructure/performance_metrics.py` - CWV metrics (FCP, LCP, CLS, FID, TBT)
- Created `infrastructure/cross_browser.py` - Multi-browser testing support
- Created `intelligence/dynamic_selectors.py` - React/Vue framework detection & stable selectors
- Created `infrastructure/proxy_rotation.py` - Smart proxy pool with rotation strategies
- Created `infrastructure/timing_evasion.py` - Human-like request timing patterns

**Configuration Updates:**
- Updated `browser_config.py` - Added stealth_backend, UNDETECTED_CONFIG
- Updated `config.py` - Added human_sim_* configuration options

### 2026-02-08 - Initial Planning

- Created SPECTRUM_BORROW_LOG.md
- Created 4 new epics (E9-E12) for infrastructure borrowing
- Created BDD feature files for each epic
- Updated implementation plan with new epics

---

## Epic Summary

| Epic | Name | Stories | Features |
|------|------|---------|----------|
| E9 | Browser Infrastructure | 8 | Browser Pool, Stealth Mode |
| E10 | Rate Limiting & Metrics | 5 | Adaptive Limiter, Resource Metrics |
| E11 | Selector Intelligence | 5 | Selector Library, Stability Scoring |
| E12 | AI/LLM Caching | 4 | Response Cache, Similarity Search |

**Total: 4 Epics, 22 Stories**

---

## Source File Mapping

### From Spectrum - IMPLEMENTED

| Source File | Target Location | Status |
|-------------|-----------------|--------|
| `spectrum/parallel/browser_pool.py` | `src/seo/infrastructure/browser_pool.py` | COMPLETE |
| `spectrum/parallel/rate_limiter.py` | `src/seo/infrastructure/rate_limiter.py` | COMPLETE |
| `spectrum/intelligence/selector_library.py` | `src/seo/intelligence/selector_library.py` | COMPLETE |
| `spectrum/intelligence/ai_cache.py` | `src/seo/intelligence/ai_cache.py` | COMPLETE |
| `spectrum/crawler.py` (stealth) | `src/seo/infrastructure/undetected_browser.py` | COMPLETE |
| `spectrum/crawler.py` (reCAPTCHA) | `src/seo/utils/challenge_handler.py` | COMPLETE |

### Additional Implementations (Gap Fills)

| Component | Location | Description |
|-----------|----------|-------------|
| Performance Metrics | `infrastructure/performance_metrics.py` | CWV metrics via Performance API |
| Cross-Browser Testing | `infrastructure/cross_browser.py` | Multi-browser execution |
| Dynamic Selectors | `intelligence/dynamic_selectors.py` | React/Vue framework handling |
| Proxy Rotation | `infrastructure/proxy_rotation.py` | Smart proxy pool management |
| Timing Evasion | `infrastructure/timing_evasion.py` | Human-like request patterns |

### Implemented File Structure

```
src/seo/
├── infrastructure/
│   ├── __init__.py              # Updated with all exports
│   ├── browser_pool.py          # BrowserPool, ContextMetrics, BrowserHealth
│   ├── undetected_browser.py    # UndetectedBrowser, stealth scripts
│   ├── rate_limiter.py          # AdaptiveRateLimiter, TokenBucketLimiter
│   ├── performance_metrics.py   # BrowserPerformanceMetrics, CWV collection
│   ├── proxy_rotation.py        # ProxyPool, rotation strategies
│   ├── cross_browser.py         # CrossBrowserRunner, capability detection
│   └── timing_evasion.py        # TimingEvasion, human-like patterns
├── intelligence/
│   ├── __init__.py              # Updated with all exports
│   ├── selector_library.py      # SelectorLibrary, SelectorCandidate
│   ├── site_profile.py          # SiteProfile, PageProfile, FormProfile
│   ├── ai_cache.py              # AICache, CacheEntry
│   └── dynamic_selectors.py     # FrameworkType, stable selector generation
├── utils/
│   ├── __init__.py              # Updated with all exports
│   ├── challenge_handler.py     # reCAPTCHA detection, evidence capture
│   └── human_simulator.py       # HumanSimulator, configurable from thresholds
├── browser_config.py            # Updated with stealth_backend, UNDETECTED_CONFIG
└── config.py                    # Updated with human_sim_* options
```

---

# Epic 9: Browser Infrastructure (CRITICAL)

> **Priority:** P0 - Critical
> **Risk:** Current single-browser approach limits parallel crawling
> **Source Files:** `browser_pool.py`, `crawler.py`
> **Target Files:** `browser_pool.py` (new), `browser_config.py`

## Rationale

The SEO project currently uses a single browser instance with basic stealth configuration. Spectrum's browser pool enables parallel crawling with session isolation, health monitoring, and automatic recycling. The undetected-chromedriver approach significantly improves bot detection evasion.

---

## Feature 9.1: Browser Pool Management

### Story 9.1.1: Implement Browser Pool Core

**As** a crawler developer
**I want** a pool of managed browser instances
**So that** I can run parallel crawls efficiently

**Acceptance Criteria:**
- [ ] BrowserPool class created with configurable max_size
- [ ] Async context manager for acquisition/release
- [ ] Session isolation with cookie clearing
- [ ] Pool status reporting (available, in_use, healthy counts)

### Story 9.1.2: Implement Context Health Monitoring

**As** a crawler developer
**I want** browser contexts to be monitored for health
**So that** degraded browsers are recycled automatically

**Acceptance Criteria:**
- [ ] BrowserHealth enum with HEALTHY, DEGRADED, UNHEALTHY, RECYCLING states
- [ ] Error rate tracking per context (threshold: 0.3)
- [ ] Request count tracking (recycle after 100 requests)
- [ ] Automatic recycling on health degradation

### Story 9.1.3: Implement Context Metrics

**As** a crawler developer
**I want** to track metrics per browser context
**So that** I can monitor crawl performance

**Acceptance Criteria:**
- [ ] ContextMetrics dataclass with requests_handled, errors, error_rate
- [ ] Last used timestamp tracking
- [ ] Metrics exposed via get_status()
- [ ] Integration with EvidenceRecord for audit trail

### Story 9.1.4: Implement Graceful Shutdown

**As** a crawler developer
**I want** the browser pool to shut down gracefully
**So that** resources are properly released

**Acceptance Criteria:**
- [ ] stop() method closes all browser contexts
- [ ] Pending requests complete before shutdown
- [ ] No orphaned browser processes
- [ ] Uptime tracking for monitoring

---

## Feature 9.2: Stealth Mode & Anti-Detection

### Story 9.2.1: Migrate to undetected-chromedriver

**As** a crawler developer
**I want** to use undetected-chromedriver
**So that** crawls evade bot detection more effectively

**Acceptance Criteria:**
- [ ] undetected-chromedriver dependency added
- [ ] Chrome version pinning (version_main parameter)
- [ ] Existing stealth flags preserved where compatible
- [ ] Configuration option to switch between Playwright and UC

### Story 9.2.2: Implement reCAPTCHA Detection

**As** a crawler developer
**I want** to detect reCAPTCHA challenges
**So that** I can handle them appropriately

**Acceptance Criteria:**
- [ ] Detect reCAPTCHA by iframe selectors
- [ ] Classify version (v2_checkbox, v2_invisible, v3, enterprise)
- [ ] Return automation_impact level (high, medium, low)
- [ ] Store detection results in EvidenceRecord

### Story 9.2.3: Implement reCAPTCHA Blocking Check

**As** a crawler developer
**I want** to detect when reCAPTCHA is actively blocking
**So that** I can skip or retry appropriately

**Acceptance Criteria:**
- [ ] Detect visible challenge elements
- [ ] Wait for auto-resolution with configurable timeout
- [ ] Return blocked status with message
- [ ] Integrate with form submission flow

### Story 9.2.4: Add Human-like Interaction Simulation

**As** a crawler developer
**I want** to simulate human-like typing and pauses
**So that** behavior-based detection is evaded

**Acceptance Criteria:**
- [ ] Character-by-character typing with random delays
- [ ] Occasional typo simulation (5% chance) with correction
- [ ] Random pauses between actions (0.3-1.5s)
- [ ] Fast mode option to skip delays

---

# Epic 10: Rate Limiting & Metrics (HIGH)

> **Priority:** P1 - High
> **Risk:** Current basic delays don't adapt to server load
> **Source Files:** `rate_limiter.py`
> **Target Files:** `rate_limiter.py` (new), `crawler.py`

## Rationale

SEO currently uses simple random delays between requests. Spectrum's adaptive rate limiter adjusts based on server response times and error rates, preventing both server overload and unnecessary slowdowns.

---

## Feature 10.1: Adaptive Rate Limiting

### Story 10.1.1: Implement Adaptive Rate Limiter Core

**As** a crawler developer
**I want** rate limiting that adapts to server conditions
**So that** crawls are efficient without overloading servers

**Acceptance Criteria:**
- [ ] AdaptiveRateLimiter class with configurable parameters
- [ ] Base delay with min/max bounds (0.5s-10.0s)
- [ ] Target response time threshold (2.0s default)
- [ ] Error rate threshold (0.1 default)
- [ ] Moving window for recent request tracking (20 requests)
- [ ] Moving window for recent request tracking (20 requests)

### Story 10.1.2: Implement Multi-Factor Adjustment

**As** a crawler developer
**I want** delay adjustment based on multiple factors
**So that** throttling responds to actual conditions

**Acceptance Criteria:**
- [ ] Error-based backoff (2.0x multiplier on high error rate)
- [ ] Response time scaling (proportional slowdown)
- [ ] Recovery when healthy (0.9x speedup)
- [ ] Delay clamping between min and max

### Story 10.1.3: Implement Token Bucket Limiter

**As** a crawler developer
**I want** burst-aware rate limiting
**So that** short bursts don't trigger throttling

**Acceptance Criteria:**
- [ ] TokenBucketLimiter class with max_tokens and refill_rate
- [ ] Burst allowance with average rate maintenance
- [ ] Async acquire() method with waiting
- [ ] Integration as alternative to adaptive limiter

---

## Feature 10.2: Resource Metrics Tracking

### Story 10.2.1: Implement Resource Metrics Collection

**As** a crawler developer
**I want** to track resource utilization metrics
**So that** I can monitor and optimize crawl performance

**Acceptance Criteria:**
- [ ] ResourceMetrics dataclass with current_delay, avg_response_time, error_rate
- [ ] Request window tracking (requests_in_window, errors_in_window)
- [ ] Cumulative stats (total_requests, total_errors, total_wait_time)
- [ ] get_metrics() method for current snapshot

### Story 10.2.2: Integrate Metrics with Evidence System

**As** an SEO analyst
**I want** crawl metrics captured as evidence
**So that** I can audit crawl performance

**Acceptance Criteria:**
- [ ] ResourceMetrics serializable to EvidenceRecord
- [ ] Metrics included in crawl summary
- [ ] Threshold violations flagged
- [ ] Historical comparison support

---

# Epic 11: Selector Intelligence (HIGH)

> **Priority:** P1 - High
> **Risk:** Current selectors lack persistence and stability scoring
> **Source Files:** `selector_library.py`
> **Target Files:** `selector_library.py` (new), `form_handler.py`

## Rationale

SEO's form handler uses basic selector fallback without persistence or stability scoring. Spectrum's selector library tracks selector confidence over time, prioritizes stable selectors, and persists learned selectors to disk.

---

## Feature 11.1: Selector Library Core

### Story 11.1.1: Implement Selector Library Storage

**As** a crawler developer
**I want** selectors persisted across crawl sessions
**So that** learned selectors improve over time

**Acceptance Criteria:**
- [ ] SelectorLibrary class with JSON persistence
- [ ] Site-specific selector storage by purpose
- [ ] Global fallback patterns for cross-site consistency
- [ ] Load/save methods for disk persistence

### Story 11.1.2: Implement Selector Candidate Generation

**As** a crawler developer
**I want** multiple selector candidates generated per element
**So that** the most stable selector is used

**Acceptance Criteria:**
- [ ] SelectorCandidate dataclass with stability_score, specificity
- [ ] ID-based selectors (stability: 0.95)
- [ ] data-testid selectors (stability: 0.98)
- [ ] Class-based selectors (stability: 0.60)
- [ ] XPath text selectors (stability: 0.40)
- [ ] Candidates sorted by stability score

### Story 11.1.3: Implement Confidence Tracking

**As** a crawler developer
**I want** selector confidence updated based on usage
**So that** failing selectors are deprioritized

**Acceptance Criteria:**
- [ ] record_success() increases confidence
- [ ] record_failure() decreases confidence
- [ ] Automatic degradation of failed selectors
- [ ] Confidence exposed in selector retrieval

---

## Feature 11.2: Selector Fallback Strategies

### Story 11.2.1: Implement Fallback Prioritization

**As** a crawler developer
**I want** selectors tried in order of confidence
**So that** the most reliable selector is used first

**Acceptance Criteria:**
- [ ] get_selector_with_fallbacks() returns ordered list
- [ ] Primary selector based on highest confidence
- [ ] Fallbacks ordered by confidence then stability
- [ ] Maximum fallback attempts configurable

### Story 11.2.2: Integrate with Form Handler

**As** a crawler developer
**I want** form handler to use selector library
**So that** form filling uses learned selectors

**Acceptance Criteria:**
- [ ] FormHandler uses SelectorLibrary for field selection
- [ ] Success/failure recorded after form interaction
- [ ] Site-specific selectors prioritized
- [ ] Backward compatibility with existing forms

---

# Epic 12: AI/LLM Caching (MEDIUM)

> **Priority:** P2 - Medium
> **Risk:** Redundant LLM calls increase cost and latency
> **Source Files:** `ai_cache.py`
> **Target Files:** `ai_cache.py` (new), `llm.py`

## Rationale

SEO's LLM client doesn't cache responses. Spectrum's AI cache uses content-addressable storage with SQLite indexing to eliminate redundant LLM calls, reducing API costs and improving response times.

---

## Feature 12.1: AI Response Caching

### Story 12.1.1: Implement AI Cache Core

**As** a crawler developer
**I want** LLM responses cached by content hash
**So that** redundant API calls are eliminated

**Acceptance Criteria:**
- [ ] AICache class with SQLite metadata index
- [ ] Content-addressable storage (SHA-256 of prompt + context)
- [ ] JSON response files in structured directory
- [ ] Configurable TTL (default: 24 hours)
- [ ] Size limit with LRU eviction (default: 100 MB)

### Story 12.1.2: Implement Cache Entry Management

**As** a crawler developer
**I want** cache entries to track usage and expiration
**So that** cache is efficient and fresh

**Acceptance Criteria:**
- [ ] CacheEntry dataclass with key, response, timestamps
- [ ] Hit count tracking for analytics
- [ ] Automatic expiration cleanup
- [ ] Manual invalidation support

### Story 12.1.3: Implement Similarity Search

**As** a crawler developer
**I want** to find similar cached prompts
**So that** near-miss cache hits are possible

**Acceptance Criteria:**
- [ ] Prompt-only hash for similarity lookup
- [ ] Prefix matching for related queries
- [ ] Similarity threshold configuration
- [ ] Results include confidence score

### Story 12.1.4: Integrate with LLM Client

**As** a crawler developer
**I want** LLM client to use cache automatically
**So that** caching is transparent to callers

**Acceptance Criteria:**
- [ ] LLMClient checks cache before API call
- [ ] Cache populated on API response
- [ ] Cache hit/miss statistics tracked
- [ ] Evidence includes cache status

---

# BDD Scenarios

## Epic 9: Browser Infrastructure

```gherkin
Feature: Browser Pool Management
  As a crawler developer
  I want to manage a pool of browser instances
  So that I can crawl pages in parallel efficiently

  Background:
    Given the browser pool is configured with max_size 4
    And stealth mode is enabled

  # ===========================================================================
  # Story 9.1.1: Browser Pool Core
  # ===========================================================================

  @browser-pool @story-9.1.1
  Scenario: Browser pool initializes with configured size
    When the browser pool is started
    Then the pool status should show:
      | field      | value |
      | total_size | 4     |
      | available  | 4     |
      | in_use     | 0     |
    And all contexts should have health "HEALTHY"

  @browser-pool @story-9.1.1
  Scenario: Context acquisition and release
    When a context is acquired from the pool
    Then the pool status should show available: 3
    And the pool status should show in_use: 1
    When the context is released
    Then the pool status should show available: 4

  @browser-pool @story-9.1.1
  Scenario: Session isolation between acquisitions
    Given a context was used for site "example.com"
    And cookies were set during the session
    When the context is released and re-acquired
    Then the cookies should be cleared
    And localStorage should be empty

  @browser-pool @story-9.1.1
  Scenario: Concurrent acquisitions up to pool size
    When 4 contexts are acquired concurrently
    Then all acquisitions should succeed
    When a 5th context is requested
    Then the request should wait until a context is released

  # ===========================================================================
  # Story 9.1.2: Context Health Monitoring
  # ===========================================================================

  @browser-pool @story-9.1.2
  Scenario: Context health degrades on errors
    Given a context has handled 10 requests
    And 4 requests returned errors
    Then the context health should be "DEGRADED"
    When the error rate exceeds 0.3
    Then the context should be marked for recycling

  @browser-pool @story-9.1.2
  Scenario: Context recycled after max requests
    Given a context has handled 99 requests successfully
    When the context handles request 100
    Then the context should be recycled
    And a new context should replace it
    And the metrics should be reset

  @browser-pool @story-9.1.2
  Scenario: Unhealthy context triggers immediate recycling
    When a context throws an unrecoverable error
    Then the context health should be "UNHEALTHY"
    And the context should be recycled immediately
    And the error should be logged

  # ===========================================================================
  # Story 9.2.1: undetected-chromedriver Migration
  # ===========================================================================

  @stealth @story-9.2.1
  Scenario: undetected-chromedriver is used for browser creation
    When a new browser context is created
    Then it should use undetected-chromedriver
    And the Chrome version should be pinned
    And performance logging should be enabled

  @stealth @story-9.2.1
  Scenario: Stealth configuration is applied
    When a new browser context is created
    Then the webdriver property should be undefined
    And navigator.plugins should return non-empty array
    And chrome.runtime should exist

  # ===========================================================================
  # Story 9.2.2: reCAPTCHA Detection
  # ===========================================================================

  @stealth @story-9.2.2
  Scenario: reCAPTCHA v2 checkbox detected
    Given a page contains a reCAPTCHA v2 checkbox
    When reCAPTCHA detection runs
    Then the result should include:
      | field             | value        |
      | detected          | true         |
      | version           | v2_checkbox  |
      | automation_impact | medium       |

  @stealth @story-9.2.2
  Scenario: reCAPTCHA v3 detected
    Given a page contains reCAPTCHA v3 scoring
    When reCAPTCHA detection runs
    Then the result should include:
      | field             | value |
      | detected          | true  |
      | version           | v3    |
      | automation_impact | low   |

  @stealth @story-9.2.2
  Scenario: reCAPTCHA Enterprise detected
    Given a page contains reCAPTCHA Enterprise
    When reCAPTCHA detection runs
    Then the result should include:
      | field             | value      |
      | version           | enterprise |
      | automation_impact | high       |

  # ===========================================================================
  # Story 9.2.3: reCAPTCHA Blocking Check
  # ===========================================================================

  @stealth @story-9.2.3
  Scenario: Active reCAPTCHA challenge blocks progress
    Given a reCAPTCHA challenge is displayed
    When the blocking check runs
    Then the result should include blocked: true
    And the result should include challenge_visible: true

  @stealth @story-9.2.3
  Scenario: reCAPTCHA auto-resolves within timeout
    Given a reCAPTCHA challenge is displayed
    And the timeout is 5 seconds
    When the challenge resolves in 3 seconds
    Then the blocking check should return blocked: false

  # ===========================================================================
  # Story 9.2.4: Human-like Interaction
  # ===========================================================================

  @stealth @story-9.2.4
  Scenario: Typing simulates human speed
    When text "hello world" is typed with human simulation
    Then the typing should take at least 500ms
    And character intervals should vary randomly
    And occasional typos may occur

  @stealth @story-9.2.4
  Scenario: Fast mode skips human simulation
    Given fast_mode is enabled
    When text "hello world" is typed
    Then the typing should be immediate
    And no random delays should occur
```

## Epic 10: Rate Limiting & Metrics

```gherkin
Feature: Adaptive Rate Limiting
  As a crawler developer
  I want rate limiting that adapts to server conditions
  So that crawls are efficient without overloading servers

  Background:
    Given the adaptive rate limiter is configured with:
      | parameter            | value |
      | base_delay           | 1.0   |
      | min_delay            | 0.5   |
      | max_delay            | 10.0  |
      | target_response_time | 2.0   |
      | error_rate_threshold | 0.1   |

  # ===========================================================================
  # Story 10.1.1: Adaptive Rate Limiter Core
  # ===========================================================================

  @rate-limiter @story-10.1.1
  Scenario: Initial delay is base_delay
    When the rate limiter starts
    Then current_delay should be 1.0 seconds

  @rate-limiter @story-10.1.1
  Scenario: Wait enforces current delay
    Given current_delay is 1.0 seconds
    When wait() is called
    Then the call should block for approximately 1.0 seconds

  # ===========================================================================
  # Story 10.1.2: Multi-Factor Adjustment
  # ===========================================================================

  @rate-limiter @story-10.1.2
  Scenario: High error rate triggers backoff
    Given the last 20 requests had 5 errors
    Then the error rate is 0.25
    When the delay is adjusted
    Then current_delay should be multiplied by 2.0
    And current_delay should not exceed max_delay

  @rate-limiter @story-10.1.2
  Scenario: Slow response time increases delay
    Given the average response time is 4.0 seconds
    And the target response time is 2.0 seconds
    When the delay is adjusted
    Then current_delay should increase proportionally

  @rate-limiter @story-10.1.2
  Scenario: Healthy conditions allow recovery
    Given the error rate is 0%
    And the average response time is 1.0 seconds
    When the delay is adjusted
    Then current_delay should be multiplied by 0.9
    And current_delay should not go below min_delay

  @rate-limiter @story-10.1.2
  Scenario: Delay is clamped to bounds
    Given current_delay would be adjusted to 15.0 seconds
    When the delay is adjusted
    Then current_delay should be 10.0 seconds (max_delay)

  # ===========================================================================
  # Story 10.1.3: Token Bucket Limiter
  # ===========================================================================

  @rate-limiter @story-10.1.3
  Scenario: Token bucket allows burst
    Given max_tokens is 5 and refill_rate is 1/second
    When 5 requests are made immediately
    Then all should proceed without waiting
    When a 6th request is made
    Then it should wait for token refill

  # ===========================================================================
  # Story 10.2.1: Resource Metrics
  # ===========================================================================

  @metrics @story-10.2.1
  Scenario: Metrics are tracked accurately
    Given 50 requests have been made
    And 5 errors occurred
    And total wait time was 60 seconds
    When get_metrics() is called
    Then the result should include:
      | field          | value |
      | total_requests | 50    |
      | total_errors   | 5     |
      | error_rate     | 0.1   |
      | total_wait_time| 60    |
```

## Epic 11: Selector Intelligence

```gherkin
Feature: Selector Library
  As a crawler developer
  I want persistent selector management with stability scoring
  So that form interactions are reliable across crawl sessions

  Background:
    Given the selector library is initialized
    And site_id is "example.com"

  # ===========================================================================
  # Story 11.1.1: Selector Library Storage
  # ===========================================================================

  @selector @story-11.1.1
  Scenario: Selectors persist across sessions
    Given a selector is stored for purpose "email_field"
    When the library is saved and reloaded
    Then the selector should be retrievable for "email_field"

  @selector @story-11.1.1
  Scenario: Site-specific selectors are isolated
    Given selector "#email" is stored for site "site-a.com"
    And selector "#user-email" is stored for site "site-b.com"
    When getting selector for "email_field" on "site-a.com"
    Then the result should be "#email"

  # ===========================================================================
  # Story 11.1.2: Selector Candidate Generation
  # ===========================================================================

  @selector @story-11.1.2
  Scenario: Multiple candidates generated with stability scores
    Given an input element with id="email" class="form-control"
    When candidates are generated
    Then candidates should include:
      | selector       | stability_score |
      | #email         | 0.95            |
      | .form-control  | 0.60            |

  @selector @story-11.1.2
  Scenario: data-testid gets highest stability
    Given an element with data-testid="submit-button"
    When candidates are generated
    Then the data-testid selector should have stability 0.98

  # ===========================================================================
  # Story 11.1.3: Confidence Tracking
  # ===========================================================================

  @selector @story-11.1.3
  Scenario: Success increases confidence
    Given selector "#email" has confidence 0.8
    When record_success() is called
    Then confidence should increase

  @selector @story-11.1.3
  Scenario: Failure decreases confidence
    Given selector "#email" has confidence 0.8
    When record_failure() is called
    Then confidence should decrease

  @selector @story-11.1.3
  Scenario: Low confidence triggers fallback
    Given selector "#email" has confidence 0.3
    When getting selector for "email_field"
    Then a fallback selector should be preferred

  # ===========================================================================
  # Story 11.2.1: Fallback Prioritization
  # ===========================================================================

  @selector @story-11.2.1
  Scenario: Fallbacks ordered by confidence then stability
    Given multiple selectors for "submit_button":
      | selector          | confidence | stability |
      | #submit           | 0.7        | 0.95      |
      | [data-action=submit] | 0.9     | 0.85      |
      | .submit-btn       | 0.5        | 0.60      |
    When get_selector_with_fallbacks() is called
    Then the order should be:
      | rank | selector             |
      | 1    | [data-action=submit] |
      | 2    | #submit              |
      | 3    | .submit-btn          |
```

## Epic 12: AI/LLM Caching

```gherkin
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

  # ===========================================================================
  # Story 12.1.1: AI Cache Core
  # ===========================================================================

  @ai-cache @story-12.1.1
  Scenario: Cache hit returns stored response
    Given a prompt "Analyze this page" with context has been cached
    When the same prompt and context are requested
    Then the cached response should be returned
    And no API call should be made

  @ai-cache @story-12.1.1
  Scenario: Cache miss triggers API call and storage
    Given the cache is empty
    When a new prompt is requested
    Then an API call should be made
    And the response should be stored in cache

  @ai-cache @story-12.1.1
  Scenario: Content-addressable key generation
    Given prompt "Analyze" and context {"title": "Test"}
    When the cache key is computed
    Then it should be a SHA-256 hash
    And the same inputs should produce the same key

  # ===========================================================================
  # Story 12.1.2: Cache Entry Management
  # ===========================================================================

  @ai-cache @story-12.1.2
  Scenario: Expired entries are cleaned up
    Given a cache entry was created 25 hours ago
    And TTL is 24 hours
    When clean_expired() runs
    Then the entry should be removed

  @ai-cache @story-12.1.2
  Scenario: Size limit enforces LRU eviction
    Given the cache is at 99 MB
    And a new 5 MB entry is added
    When the size limit is enforced
    Then least recently used entries should be evicted
    And total size should be under 100 MB

  @ai-cache @story-12.1.2
  Scenario: Hit count is tracked
    Given a cache entry exists
    When it is accessed 5 times
    Then hit_count should be 5
    And last_hit should be updated

  # ===========================================================================
  # Story 12.1.3: Similarity Search
  # ===========================================================================

  @ai-cache @story-12.1.3
  Scenario: Similar prompts can be found
    Given cache contains entry for "Analyze SEO for homepage"
    When searching for similar to "Analyze SEO for product page"
    Then the homepage entry should be returned with similarity score

  # ===========================================================================
  # Story 12.1.4: LLM Client Integration
  # ===========================================================================

  @ai-cache @story-12.1.4
  Scenario: LLM client uses cache transparently
    Given a cached response exists for the prompt
    When LLMClient.analyze() is called
    Then the cached response should be returned
    And evidence should indicate "cache_hit: true"

  @ai-cache @story-12.1.4
  Scenario: Cache statistics are tracked
    Given 100 LLM requests have been made
    And 40 were cache hits
    When cache.stats() is called
    Then the result should show:
      | field      | value |
      | hit_rate   | 0.4   |
      | total_hits | 40    |
      | total_misses | 60  |
```

---

# Dependencies

## Python Packages to Add

```toml
# pyproject.toml additions
[tool.poetry.dependencies]
undetected-chromedriver = "^3.5"  # Bot detection evasion
```

## File Dependencies

```
browser_pool.py
├── requires: browser_config.py (for context creation)
└── uses: models.py (for EvidenceRecord)

rate_limiter.py
├── standalone (no dependencies)
└── uses: models.py (for EvidenceRecord)

selector_library.py
├── standalone (no dependencies)
└── uses: BeautifulSoup for HTML parsing

ai_cache.py
├── requires: sqlite3 (stdlib)
└── uses: models.py (for EvidenceRecord)
```

---

# Testing Strategy

## Unit Tests

| Component | Test File | Coverage Target |
|-----------|-----------|-----------------|
| BrowserPool | tests/test_browser_pool.py | 90% |
| AdaptiveRateLimiter | tests/test_rate_limiter.py | 95% |
| SelectorLibrary | tests/test_selector_library.py | 90% |
| AICache | tests/test_ai_cache.py | 90% |

## Integration Tests

| Scenario | Test File |
|----------|-----------|
| Parallel crawl with pool | tests/integration/test_parallel_crawl.py |
| Rate limiting under load | tests/integration/test_rate_limiting.py |
| Selector learning | tests/integration/test_selector_learning.py |
| LLM with cache | tests/integration/test_llm_caching.py |

---

# Migration Checklist

## Phase 1: Browser Infrastructure (Critical) - COMPLETE

- [x] Add undetected-chromedriver to dependencies
- [x] Create src/seo/infrastructure/browser_pool.py
- [x] Create src/seo/infrastructure/undetected_browser.py with stealth scripts
- [x] Add reCAPTCHA detection to utils/challenge_handler.py
- [x] Update browser_config.py with stealth_backend switching
- [x] Add UNDETECTED_CONFIG and UNDETECTED_PLAYWRIGHT_CONFIG presets
- [x] Update infrastructure/__init__.py exports

## Phase 2: Rate Limiting (High) - COMPLETE

- [x] Create src/seo/infrastructure/rate_limiter.py
- [x] Implement AdaptiveRateLimiter with multi-factor adjustment
- [x] Implement TokenBucketLimiter for burst handling
- [x] Add ResourceMetrics with EvidenceRecord integration
- [x] Update infrastructure/__init__.py exports

## Phase 3: Selector Intelligence (High) - COMPLETE

- [x] Create src/seo/intelligence/selector_library.py
- [x] Create src/seo/intelligence/site_profile.py
- [x] Create src/seo/intelligence/dynamic_selectors.py (Gap #4)
- [x] Add framework detection (React, Vue, Angular, Svelte)
- [x] Add stability scoring and confidence tracking
- [x] Update intelligence/__init__.py exports

## Phase 4: AI Caching (Medium) - COMPLETE

- [x] Create src/seo/intelligence/ai_cache.py
- [x] Implement content-addressable storage with SQLite index
- [x] Add TTL and LRU eviction
- [x] Add similarity search support
- [x] Update intelligence/__init__.py exports

## Phase 5: Additional Gaps - COMPLETE

- [x] Gap #2: Create infrastructure/performance_metrics.py (FCP, LCP, CLS, FID, TBT)
- [x] Gap #3: Create infrastructure/cross_browser.py (Chrome/Firefox/WebKit testing)
- [x] Gap #6: Create infrastructure/proxy_rotation.py (Smart proxy pool)
- [x] Gap #7: Create infrastructure/timing_evasion.py (Request timing patterns)

---

# Appendix: Source Code References

## Spectrum Files to Port

1. **browser_pool.py**: `/Users/brett.hawkins/Documents/dev/spectrum/tools/site_discovery/parallel/browser_pool.py`
   - Classes: BrowserPool, ContextMetrics, BrowserHealth, PoolStatus

2. **rate_limiter.py**: `/Users/brett.hawkins/Documents/dev/spectrum/tools/site_discovery/parallel/rate_limiter.py`
   - Classes: AdaptiveRateLimiter, TokenBucketLimiter, RateLimitConfig, ResourceMetrics

3. **selector_library.py**: `/Users/brett.hawkins/Documents/dev/spectrum/tools/site_discovery/intelligence/selector_library.py`
   - Classes: SelectorLibrary, SelectorCandidate

4. **ai_cache.py**: `/Users/brett.hawkins/Documents/dev/spectrum/tools/site_discovery/intelligence/ai_cache.py`
   - Classes: AICache, CacheEntry

5. **crawler.py** (partial): `/Users/brett.hawkins/Documents/dev/spectrum/tools/site_discovery/crawler.py`
   - Methods: _create_driver(), _detect_recaptcha(), _check_recaptcha_blocking()
