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
      | moving_window_size   | 20    |

  # ===========================================================================
  # Feature 10.1: Adaptive Rate Limiting
  # Story 10.1.1: Implement Adaptive Rate Limiter Core
  # ===========================================================================

  @story-10.1.1 @adaptive-core
  Scenario: Initial delay is base_delay
    When the rate limiter starts
    Then current_delay should be 1.0 seconds
    And current_delay should be within min_delay and max_delay

  @story-10.1.1 @adaptive-core
  Scenario: Wait enforces current delay
    Given current_delay is 1.0 seconds
    When wait() is called
    Then the call should block for approximately 1.0 seconds
    And total_wait_time should increase by approximately 1.0

  @story-10.1.1 @adaptive-core
  Scenario: Wait respects min_delay and max_delay
    Given current_delay is adjusted to 0.2 seconds
    When wait() is called
    Then the call should block for approximately 0.5 seconds (min_delay)
    Given current_delay is adjusted to 12.0 seconds
    When wait() is called
    Then the call should block for approximately 10.0 seconds (max_delay)

  # ===========================================================================
  # Feature 10.1: Adaptive Rate Limiting
  # Story 10.1.2: Implement Multi-Factor Adjustment
  # ===========================================================================

  @story-10.1.2 @multi-factor
  Scenario: High error rate triggers backoff
    Given the last 20 requests had 5 errors (error_rate = 0.25)
    And current_delay is 1.0 seconds
    When the delay is adjusted
    Then current_delay should be approximately 2.0 seconds (1.0 * 2.0 multiplier)
    And current_delay should not exceed max_delay

  @story-10.1.2 @multi-factor
  Scenario: Slow response time increases delay
    Given the average response time is 4.0 seconds
    And the target response time is 2.0 seconds
    And current_delay is 1.0 seconds
    When the delay is adjusted
    Then current_delay should increase proportionally, e.g., to 2.0 seconds

  @story-10.1.2 @multi-factor
  Scenario: Healthy conditions allow recovery
    Given the error rate is 0%
    And the average response time is 1.0 seconds
    And current_delay is 2.0 seconds
    When the delay is adjusted
    Then current_delay should be approximately 1.8 seconds (2.0 * 0.9 speedup)
    And current_delay should not go below min_delay

  @story-10.1.2 @multi-factor
  Scenario: Combined factors adjust delay
    Given the error rate is 0.05
    And average response time is 3.0 seconds
    And current_delay is 1.0 seconds
    When the delay is adjusted
    Then current_delay should reflect both error and response time adjustments

  # ===========================================================================
  # Feature 10.1: Adaptive Rate Limiting
  # Story 10.1.3: Implement Token Bucket Limiter
  # ===========================================================================

  @story-10.1.3 @token-bucket
  Scenario: Token bucket allows burst
    Given max_tokens is 5 and refill_rate is 1 token/second
    When 5 acquire() calls are made immediately
    Then all should proceed without waiting
    When a 6th acquire() call is made
    Then it should wait for token refill (approx 1 second)

  @story-10.1.3 @token-bucket
  Scenario: Refill rate correctly replenishes tokens
    Given max_tokens is 5 and refill_rate is 2 tokens/second
    And the bucket is empty
    When 0.5 seconds pass
    Then 1 token should be available
    When 2.5 seconds pass
    Then 5 tokens should be available (max_tokens limit)

  @story-10.1.3 @token-bucket
  Scenario: Token bucket can be used as an alternative limiter
    Given the crawler is configured to use TokenBucketLimiter
    When requests are made
    Then they should adhere to the token bucket mechanics
    And AdaptiveRateLimiter should not be used

  # ===========================================================================
  # Feature 10.2: Resource Metrics Tracking
  # Story 10.2.1: Implement Resource Metrics Collection
  # ===========================================================================

  @story-10.2.1 @metrics
  Scenario: Metrics are tracked accurately over a window
    Given the moving_window_size is 10
    When 5 successful requests and 2 error requests occur
    Then requests_in_window should be 7
    And errors_in_window should be 2
    And error_rate in window should be 0.28-0.29

  @story-10.2.1 @metrics
  Scenario: Metrics track cumulative stats
    Given 50 requests have been made (45 successful, 5 errors)
    And total wait time was 60 seconds
    When get_metrics() is called
    Then the result should include:
      | field            | value |
      | total_requests   | 50    |
      | total_errors     | 5     |
      | cumulative_error_rate | 0.1   |
      | total_wait_time  | 60    |

  @story-10.2.1 @metrics
  Scenario: Average response time is calculated
    Given 3 requests with response times 1s, 2s, 3s
    When metrics are updated
    Then avg_response_time should be 2.0 seconds

  # ===========================================================================
  # Feature 10.2: Resource Metrics Tracking
  # Story 10.2.2: Integrate Metrics with Evidence System
  # ===========================================================================

  @story-10.2.2 @metrics @evidence
  Scenario: ResourceMetrics serializable to EvidenceRecord
    Given current ResourceMetrics
    When serialize_to_evidence() is called
    Then it should return a dictionary suitable for EvidenceRecord
    And key fields like "avg_response_time" and "error_rate" should be present

  @story-10.2.2 @metrics @evidence
  Scenario: Metrics included in crawl summary
    Given a crawl completes with tracked ResourceMetrics
    When the crawl summary report is generated
    Then the report should contain a section for "Rate Limiter Metrics"
    And display key statistics like total requests, errors, and average delay

  @story-10.2.2 @metrics @evidence
  Scenario: Threshold violations flagged in evidence
    Given the error_rate_threshold is 0.1
    And the actual error rate is 0.15
    When metrics are integrated with evidence
    Then an "ALERT" or "WARNING" should be flagged in the evidence
    And specify "Error rate exceeded threshold"