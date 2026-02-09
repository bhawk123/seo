@epic-9 @browser @critical
Feature: Browser Pool Management
  As a crawler developer
  I want to manage a pool of browser instances
  So that I can crawl pages in parallel efficiently

  Background:
    Given the browser pool is configured with max_size 4
    And stealth mode is enabled

  # ===========================================================================
  # Feature 9.1: Browser Pool Core
  # Story 9.1.1: Implement Browser Pool Core
  # ===========================================================================

  @story-9.1.1 @pool-core
  Scenario: Browser pool initializes with configured size
    When the browser pool is started
    Then the pool status should show:
      | field      | value |
      | total_size | 4     |
      | available  | 4     |
      | in_use     | 0     |
    And all contexts should have health "HEALTHY"

  @story-9.1.1 @pool-core
  Scenario: Context acquisition and release
    When a context is acquired from the pool
    Then the pool status should show available: 3
    And the pool status should show in_use: 1
    When the context is released
    Then the pool status should show available: 4

  @story-9.1.1 @pool-core
  Scenario: Session isolation between acquisitions
    Given a context was used for site "example.com"
    And cookies were set during the session
    When the context is released and re-acquired
    Then the cookies should be cleared
    And localStorage should be empty

  @story-9.1.1 @pool-core
  Scenario: Concurrent acquisitions up to pool size
    When 4 contexts are acquired concurrently
    Then all acquisitions should succeed
    When a 5th context is requested
    Then the request should wait until a context is released

  @story-9.1.1 @pool-core
  Scenario: Pool supports async context manager
    When using the pool with async context manager syntax
    Then the context should be automatically released on exit
    And errors should not prevent release

  # ===========================================================================
  # Feature 9.1: Browser Pool Core
  # Story 9.1.2: Context Health Monitoring
  # ===========================================================================

  @story-9.1.2 @health-monitoring
  Scenario: Context health degrades on errors
    Given a context has handled 10 requests
    And 4 requests returned errors
    Then the context health should be "DEGRADED"
    When the error rate exceeds 0.3
    Then the context should be marked for recycling

  @story-9.1.2 @health-monitoring
  Scenario: Context recycled after max requests
    Given a context has handled 99 requests successfully
    When the context handles request 100
    Then the context should be recycled
    And a new context should replace it
    And the metrics should be reset

  @story-9.1.2 @health-monitoring
  Scenario: Unhealthy context triggers immediate recycling
    When a context throws an unrecoverable error
    Then the context health should be "UNHEALTHY"
    And the context should be recycled immediately
    And the error should be logged

  @story-9.1.2 @health-monitoring
  Scenario: Health transitions follow expected flow
    Given a context starts as "HEALTHY"
    When error rate exceeds 0.2
    Then health should transition to "DEGRADED"
    When error rate exceeds 0.3
    Then health should transition to "RECYCLING"
    And a replacement context should be created

  # ===========================================================================
  # Feature 9.1: Browser Pool Core
  # Story 9.1.3: Context Metrics
  # ===========================================================================

  @story-9.1.3 @context-metrics
  Scenario: Context metrics track requests
    Given a fresh context
    When 5 requests are handled successfully
    And 2 requests fail
    Then context metrics should show:
      | field            | value |
      | requests_handled | 7     |
      | errors           | 2     |
      | error_rate       | 0.29  |

  @story-9.1.3 @context-metrics
  Scenario: Last used timestamp updates
    Given a context was last used at time T
    When the context handles a new request at time T+10s
    Then last_used should be T+10s

  @story-9.1.3 @context-metrics
  Scenario: Metrics exposed via pool status
    Given 2 contexts are in use with different metrics
    When get_status() is called
    Then the status should include aggregate metrics
    And per-context breakdown should be available

  # ===========================================================================
  # Feature 9.1: Browser Pool Core
  # Story 9.1.4: Graceful Shutdown
  # ===========================================================================

  @story-9.1.4 @graceful-shutdown
  Scenario: Stop method closes all contexts
    Given the pool has 4 active contexts
    When stop() is called
    Then all browser contexts should be closed
    And all browser instances should be terminated
    And no orphaned processes should exist

  @story-9.1.4 @graceful-shutdown
  Scenario: Pending requests complete before shutdown
    Given a context is handling a request
    When stop() is called
    Then the active request should complete
    And then the context should close

  @story-9.1.4 @graceful-shutdown
  Scenario: Uptime is tracked
    Given the pool was started at time T
    When 60 seconds have passed
    Then get_status().uptime_seconds should be approximately 60

  # ===========================================================================
  # Feature 9.2: Stealth Mode & Anti-Detection
  # Story 9.2.1: Migrate to undetected-chromedriver
  # ===========================================================================

  @story-9.2.1 @stealth @undetected-chromedriver
  Scenario: undetected-chromedriver is used for browser creation
    When a new browser context is created
    Then it should use undetected-chromedriver
    And the Chrome version should be pinned to version_main
    And performance logging should be enabled via CDP

  @story-9.2.1 @stealth @undetected-chromedriver
  Scenario: Stealth configuration hides automation
    When a new browser context is created
    Then navigator.webdriver should be undefined
    And navigator.plugins should return non-empty array
    And chrome.runtime should exist
    And window.chrome should be properly defined

  @story-9.2.1 @stealth @undetected-chromedriver
  Scenario: Configuration supports mode switching
    Given stealth_mode is set to "playwright"
    When a browser is created
    Then it should use Playwright with stealth flags
    Given stealth_mode is set to "undetected"
    When a browser is created
    Then it should use undetected-chromedriver

  @story-9.2.1 @stealth @undetected-chromedriver
  Scenario: Headless mode is supported
    Given headless is set to true
    When a browser is created with undetected-chromedriver
    Then the --headless=new flag should be set
    And stealth features should still work

  # ===========================================================================
  # Feature 9.2: Stealth Mode & Anti-Detection
  # Story 9.2.2: reCAPTCHA Detection
  # ===========================================================================

  @story-9.2.2 @stealth @recaptcha
  Scenario: reCAPTCHA v2 checkbox detected
    Given a page contains a reCAPTCHA v2 checkbox
    When reCAPTCHA detection runs
    Then the result should include:
      | field             | value        |
      | detected          | true         |
      | version           | v2_checkbox  |
      | automation_impact | medium       |
    And indicators should include ".g-recaptcha"

  @story-9.2.2 @stealth @recaptcha
  Scenario: reCAPTCHA v2 invisible detected
    Given a page contains reCAPTCHA v2 invisible
    When reCAPTCHA detection runs
    Then the result should include:
      | field             | value         |
      | detected          | true          |
      | version           | v2_invisible  |
      | automation_impact | medium        |

  @story-9.2.2 @stealth @recaptcha
  Scenario: reCAPTCHA v3 detected
    Given a page contains reCAPTCHA v3 scoring
    When reCAPTCHA detection runs
    Then the result should include:
      | field             | value |
      | detected          | true  |
      | version           | v3    |
      | automation_impact | low   |

  @story-9.2.2 @stealth @recaptcha
  Scenario: reCAPTCHA Enterprise detected
    Given a page contains reCAPTCHA Enterprise
    When reCAPTCHA detection runs
    Then the result should include:
      | field             | value      |
      | version           | enterprise |
      | automation_impact | high       |

  @story-9.2.2 @stealth @recaptcha
  Scenario: No reCAPTCHA returns clean result
    Given a page contains no reCAPTCHA
    When reCAPTCHA detection runs
    Then the result should include:
      | field    | value |
      | detected | false |
    And version should be null
    And indicators should be empty

  @story-9.2.2 @stealth @recaptcha
  Scenario: Detection results stored as evidence
    Given reCAPTCHA is detected
    When detection completes
    Then an EvidenceRecord should be created
    And evidence should include source "recaptcha_detection"
    And evidence should include the version detected

  # ===========================================================================
  # Feature 9.2: Stealth Mode & Anti-Detection
  # Story 9.2.3: reCAPTCHA Blocking Check
  # ===========================================================================

  @story-9.2.3 @stealth @recaptcha
  Scenario: Active reCAPTCHA challenge blocks progress
    Given a reCAPTCHA challenge is displayed
    When the blocking check runs
    Then the result should include:
      | field             | value |
      | blocked           | true  |
      | challenge_visible | true  |
    And should_skip should be true

  @story-9.2.3 @stealth @recaptcha
  Scenario: reCAPTCHA auto-resolves within timeout
    Given a reCAPTCHA challenge is displayed
    And the auto_resolve_timeout is 5 seconds
    When the challenge resolves in 3 seconds
    Then the blocking check should return:
      | field   | value |
      | blocked | false |

  @story-9.2.3 @stealth @recaptcha
  Scenario: Timeout exceeded marks as blocked
    Given a reCAPTCHA challenge is displayed
    And the auto_resolve_timeout is 5 seconds
    When 5 seconds pass without resolution
    Then the blocking check should return blocked: true
    And message should explain the timeout

  @story-9.2.3 @stealth @recaptcha
  Scenario: CI mode skips blocking challenges
    Given ci_behavior is set to "skip_in_ci"
    And running in CI environment
    When a reCAPTCHA challenge is detected
    Then should_skip should be true
    And the flow should continue without waiting

  # ===========================================================================
  # Feature 9.2: Stealth Mode & Anti-Detection
  # Story 9.2.4: Human-like Interaction
  # ===========================================================================

  @story-9.2.4 @stealth @human-like
  Scenario: Typing simulates human speed
    When text "hello world" is typed with human simulation
    Then the typing should take at least 500ms
    And character intervals should vary between 50-150ms
    And no two intervals should be identical

  @story-9.2.4 @stealth @human-like
  Scenario: Occasional typos are simulated
    Given typo_rate is 0.05
    When 100 characters are typed
    Then approximately 5 typos should occur
    And each typo should be corrected with backspace

  @story-9.2.4 @stealth @human-like
  Scenario: Pauses simulate human thinking
    When _human_pause() is called
    Then the pause should be between 0.3 and 1.5 seconds
    And the pause duration should vary randomly

  @story-9.2.4 @stealth @human-like
  Scenario: Fast mode skips human simulation
    Given fast_mode is enabled
    When text "hello world" is typed
    Then the typing should be immediate
    And no random delays should occur
    And no typos should be simulated

  @story-9.2.4 @stealth @human-like
  Scenario: Human-like click includes mouse movement
    Given human simulation is enabled
    When clicking on an element
    Then the mouse should move to the element first
    And the movement should have slight random offset
    And a small delay should occur before click

  # ===========================================================================
  # Feature 9.3: Browser Pool Fault Tolerance & Recovery
  # Story 9.3.1: Handle Browser Crashes
  # ===========================================================================

  @story-9.3.1 @fault-tolerance @recovery
  Scenario: AsyncSiteCrawler gracefully handles and recovers from browser crashes
    Given a "BrowserPool" configured with a maximum of 3 browser instances
    And the "AsyncSiteCrawler" is initialized with this BrowserPool
    And a crawl target "https://flaky-site.com" where one browser instance is designed to crash after 5 requests
    When the "AsyncSiteCrawler" attempts to crawl 10 pages on "https://flaky-site.com"
    Then the crawler should detect the browser crash
    And the "BrowserPool" should replace the crashed browser instance with a new, healthy one
    And the "AsyncSiteCrawler" should successfully complete the crawl of all 10 pages
    And the final crawl report should indicate no unhandled browser-related errors

  @story-9.3.1 @fault-tolerance @recovery
  Scenario: Browser context crash triggers automatic replacement
    Given a context has been acquired from the pool
    When the context throws "Target closed" error
    Then the context should be marked as UNHEALTHY
    And a new context should be created to replace it
    And the failed request should be retried on the new context
    And the original request should eventually succeed

  @story-9.3.1 @fault-tolerance @recovery
  Scenario: Pool continues operating during context replacement
    Given 3 contexts are active and healthy
    When context 2 crashes unexpectedly
    Then contexts 1 and 3 should continue processing requests
    And a new context 4 should be created
    And pool availability should not drop to zero

  @story-9.3.1 @fault-tolerance @recovery
  Scenario: Multiple simultaneous context failures handled
    Given 4 contexts are active
    When 2 contexts crash simultaneously
    Then both should be detected and marked UNHEALTHY
    And 2 new contexts should be created
    And pending requests should be redistributed
    And no requests should be permanently lost

  @story-9.3.1 @fault-tolerance @recovery
  Scenario: Browser instance failure triggers full restart
    Given a browser instance is managing 2 contexts
    When the browser process terminates unexpectedly
    Then both contexts should be marked UNHEALTHY
    And a new browser instance should be launched
    And new contexts should be created
    And the pool should recover to full capacity

  # ===========================================================================
  # Feature 9.3: Browser Pool Fault Tolerance & Recovery
  # Story 9.3.2: Resource Lifecycle Management
  # ===========================================================================

  @story-9.3.2 @lifecycle @context-manager
  Scenario: BrowserPool supports async context manager
    When using BrowserPool as an async context manager
    Then start() should be called on entry
    And stop() should be called on exit
    And cleanup should occur even if exceptions are raised

  @story-9.3.2 @lifecycle @context-manager
  Scenario: AsyncSiteCrawler cleanup on exception
    Given the crawler is using a BrowserPool
    When an unhandled exception occurs during crawl
    Then the BrowserPool should be properly stopped
    And all browser contexts should be closed
    And no orphaned browser processes should remain

  @story-9.3.2 @lifecycle @context-manager
  Scenario: Graceful degradation when pool exhausted
    Given a pool with max_size 2
    And both contexts are stuck on slow pages
    When a third request arrives
    Then it should wait up to the configured timeout
    And if timeout exceeded, should raise descriptive error
    And the stuck contexts should be monitored for health
