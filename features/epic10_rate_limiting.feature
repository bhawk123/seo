@epic-10 @rate-limiting @high
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
      | window_size          | 20    |

  # ===========================================================================
  # Feature 10.1: Adaptive Rate Limiting
  # Story 10.1.1: Implement Adaptive Rate Limiter Core
  # ===========================================================================

  @story-10.1.1 @rate-limiter-core
  Scenario: Initial delay is base_delay
    When the rate limiter is initialized
    Then current_delay should be 1.0 seconds

  @story-10.1.1 @rate-limiter-core
  Scenario: Wait enforces current delay
    Given current_delay is 1.0 seconds
    When wait() is called
    Then the call should block for approximately 1.0 seconds
    And the time waited should be within 50ms of target

  @story-10.1.1 @rate-limiter-core
  Scenario: Request recording updates metrics
    When record_request() is called with:
      | response_time | success |
      | 1.5           | true    |
    Then the request should be added to the window
    And total_requests should increment

  @story-10.1.1 @rate-limiter-core
  Scenario: Window maintains rolling history
    Given window_size is 20
    When 25 requests are recorded
    Then only the last 20 should be in the window
    And older requests should be discarded

  @story-10.1.1 @rate-limiter-core
  Scenario: Reset clears all state
    Given 50 requests have been recorded
    When reset() is called
    Then current_delay should be base_delay
    And the window should be empty
    And total_requests should be 0

  # ===========================================================================
  # Feature 10.1: Adaptive Rate Limiting
  # Story 10.1.2: Implement Multi-Factor Adjustment
  # ===========================================================================

  @story-10.1.2 @multi-factor
  Scenario: High error rate triggers backoff
    Given the last 20 requests had 5 errors
    Then the error rate is 0.25
    When the delay is adjusted
    Then current_delay should be multiplied by 2.0
    And current_delay should be 2.0 seconds

  @story-10.1.2 @multi-factor
  Scenario: Very high error rate still capped at max
    Given current_delay is 6.0 seconds
    And the error rate is 0.5
    When the delay is adjusted
    Then current_delay should be 10.0 seconds (max_delay)
    And it should not exceed max_delay

  @story-10.1.2 @multi-factor
  Scenario: Slow response time increases delay
    Given the average response time is 4.0 seconds
    And the target response time is 2.0 seconds
    And the error rate is 0%
    When the delay is adjusted
    Then current_delay should increase proportionally
    And the increase should be approximately 2x

  @story-10.1.2 @multi-factor
  Scenario: Healthy conditions allow recovery
    Given the error rate is 0%
    And the average response time is 1.0 seconds
    When the delay is adjusted
    Then current_delay should be multiplied by 0.9
    And the delay should decrease

  @story-10.1.2 @multi-factor
  Scenario: Minimum delay is enforced
    Given current_delay is 0.6 seconds
    And conditions are healthy
    When the delay is adjusted
    Then current_delay should not go below 0.5 seconds (min_delay)

  @story-10.1.2 @multi-factor
  Scenario: Error-based backoff takes priority
    Given both high error rate and slow response time
    When the delay is adjusted
    Then error-based backoff should be applied first
    And response time adjustment should be secondary

  @story-10.1.2 @multi-factor
  Scenario: Adjustment happens after each request
    Given requests are being processed
    When a request completes
    Then _adjust_delay() should be called
    And current_delay should reflect new conditions

  # ===========================================================================
  # Feature 10.1: Adaptive Rate Limiting
  # Story 10.1.3: Implement Token Bucket Limiter
  # ===========================================================================

  @story-10.1.3 @token-bucket
  Scenario: Token bucket allows burst up to max_tokens
    Given max_tokens is 5 and refill_rate is 1 per second
    And the bucket is full
    When 5 requests are made immediately
    Then all should proceed without waiting
    And tokens_available should be 0

  @story-10.1.3 @token-bucket
  Scenario: Request waits when bucket is empty
    Given max_tokens is 5 and refill_rate is 1 per second
    And tokens_available is 0
    When a request is made
    Then it should wait for approximately 1 second
    And then proceed after token refill

  @story-10.1.3 @token-bucket
  Scenario: Tokens refill over time
    Given tokens_available is 0
    And refill_rate is 2 per second
    When 1 second passes
    Then tokens_available should be 2

  @story-10.1.3 @token-bucket
  Scenario: Tokens do not exceed max
    Given tokens_available is 4
    And max_tokens is 5
    When 2 seconds pass with refill_rate of 2 per second
    Then tokens_available should be 5 (not 8)

  @story-10.1.3 @token-bucket
  Scenario: Acquire is async and non-blocking for others
    Given 2 concurrent acquire() calls
    And only 1 token available
    Then the first should proceed immediately
    And the second should wait
    And they should not block each other

  # ===========================================================================
  # Feature 10.2: Resource Metrics Tracking
  # Story 10.2.1: Implement Resource Metrics Collection
  # ===========================================================================

  @story-10.2.1 @resource-metrics
  Scenario: Metrics track current delay
    Given current_delay is 2.5 seconds
    When get_metrics() is called
    Then the result should include current_delay: 2.5

  @story-10.2.1 @resource-metrics
  Scenario: Metrics calculate average response time
    Given the last 5 requests had response times:
      | response_time |
      | 1.0           |
      | 2.0           |
      | 3.0           |
      | 2.0           |
      | 2.0           |
    When get_metrics() is called
    Then avg_response_time should be 2.0

  @story-10.2.1 @resource-metrics
  Scenario: Metrics calculate error rate correctly
    Given 20 requests in window
    And 4 were errors
    When get_metrics() is called
    Then error_rate should be 0.2

  @story-10.2.1 @resource-metrics
  Scenario: Metrics track window counts
    Given 20 requests in window
    And 3 were errors
    When get_metrics() is called
    Then the result should include:
      | field             | value |
      | requests_in_window| 20    |
      | errors_in_window  | 3     |

  @story-10.2.1 @resource-metrics
  Scenario: Metrics track cumulative totals
    Given 100 total requests
    And 8 total errors
    And 150 seconds total wait time
    When get_metrics() is called
    Then the result should include:
      | field           | value |
      | total_requests  | 100   |
      | total_errors    | 8     |
      | total_wait_time | 150   |

  @story-10.2.1 @resource-metrics
  Scenario: Metrics dataclass is serializable
    When get_metrics() returns a ResourceMetrics object
    Then it should have a to_dict() method
    And the dict should be JSON serializable

  # ===========================================================================
  # Feature 10.2: Resource Metrics Tracking
  # Story 10.2.2: Integrate Metrics with Evidence System
  # ===========================================================================

  @story-10.2.2 @evidence-integration
  Scenario: Metrics can be converted to EvidenceRecord
    Given a ResourceMetrics snapshot
    When converted to EvidenceRecord
    Then the evidence should include:
      | field        | value           |
      | component_id | rate_limiter    |
      | source       | metrics_capture |
    And all metric values should be preserved

  @story-10.2.2 @evidence-integration
  Scenario: High error rate is flagged in evidence
    Given error_rate exceeds threshold
    When metrics evidence is captured
    Then the evidence should include severity "warning"
    And recommendation should suggest investigating errors

  @story-10.2.2 @evidence-integration
  Scenario: Metrics included in crawl summary
    Given a crawl has completed
    When the summary is generated
    Then it should include rate limiter metrics
    And the metrics should show total requests and errors

  @story-10.2.2 @evidence-integration
  Scenario: Per-domain metrics tracked separately
    Given requests to domain-a.com and domain-b.com
    When get_metrics(domain="domain-a.com") is called
    Then only domain-a.com metrics should be returned

  # ===========================================================================
  # Feature 10.3: Rate Limiter Edge Cases & Error Integration
  # Story 10.3.1: Edge Case Handling
  # ===========================================================================

  @story-10.3.1 @edge-cases
  Scenario: Successful requests followed by hard rate limits
    Given 10 successful requests at normal speed
    When the server returns 3 consecutive HTTP 429 responses
    Then current_delay should increase exponentially
    And the rate limiter should enter backoff mode
    And subsequent requests should wait longer between attempts

  @story-10.3.1 @edge-cases
  Scenario: Recovery from prolonged backoff
    Given the rate limiter is in maximum backoff (10s delay)
    And the server starts returning successful responses
    When 20 successful requests are recorded
    Then current_delay should gradually decrease
    And should approach base_delay (1.0s)
    And recovery should follow the success_recovery_multiplier

  @story-10.3.1 @edge-cases
  Scenario: Non-rate-limit errors do not trigger backoff
    Given the server returns HTTP 404 for 5 requests
    When the error rate is calculated
    Then HTTP 404 should NOT be counted as rate-limiting errors
    And current_delay should remain at base_delay
    And the requests should be marked as client errors

  @story-10.3.1 @edge-cases
  Scenario: HTTP 500 errors trigger server-side backoff
    Given the server returns HTTP 500 for 3 requests
    When the error rate is calculated
    Then HTTP 500 SHOULD be counted as server errors
    And current_delay should increase
    And the rate limiter should back off to reduce server load

  @story-10.3.1 @edge-cases
  Scenario: Connection timeouts trigger backoff
    Given 3 requests timeout without response
    When timeout errors are recorded
    Then they should be treated as server-side issues
    And current_delay should increase
    And the rate limiter should reduce request frequency

  @story-10.3.1 @edge-cases
  Scenario: Mixed success and failure patterns
    Given a pattern of: success, success, 429, success, 429, 429
    When the sliding window is evaluated
    Then error_rate should be 0.5 (3/6)
    And current_delay should reflect the mixed pattern
    And should not over-react to isolated failures

  # ===========================================================================
  # Feature 10.3: Rate Limiter Edge Cases & Error Integration
  # Story 10.3.2: Comprehensive Error Feedback
  # ===========================================================================

  @story-10.3.2 @error-feedback @integration
  Scenario: Browser crashes reported to rate limiter
    Given a page request causes a browser crash
    When the error is caught by AsyncSiteCrawler
    Then the error should be reported to the rate limiter
    And it should be classified as infrastructure error
    And should not trigger rate-based backoff

  @story-10.3.2 @error-feedback @integration
  Scenario: Network errors reported to rate limiter
    Given a request fails with "Connection reset by peer"
    When the error is caught by AsyncSiteCrawler
    Then the error should be reported to the rate limiter
    And it should be classified as network error
    And should trigger moderate backoff

  @story-10.3.2 @error-feedback @integration
  Scenario: DNS resolution failures reported
    Given a request fails with "Name resolution failed"
    When the error is caught by AsyncSiteCrawler
    Then the error should be reported as DNS failure
    And subsequent requests to same domain should wait
    And the domain should be flagged for potential issues

  @story-10.3.2 @error-feedback @integration
  Scenario: Error types have configurable weights
    Given error_weights configuration:
      | error_type    | weight |
      | http_429      | 2.0    |
      | http_503      | 1.5    |
      | timeout       | 1.0    |
      | connection    | 0.8    |
      | browser_crash | 0.0    |
    When errors of each type are recorded
    Then backoff should be weighted accordingly
    And browser crashes should not affect rate limiting
