# Epic: EPIC-SEO-INFRA-001 SEO Infrastructure Upgrade

**Requirement:** REQ-BORROW-001 (Cross-Project Component Sharing)
**Status:** In Progress
**Created:** 2026-02-08
**Estimated Effort:** ~14 hours

## Description

Port Spectrum's battle-tested infrastructure components to the SEO project to enhance reliability, performance, and capabilities. These components have been proven in production and address gaps in the SEO project's current architecture.

## Business Value

- Reduce API costs through intelligent caching (AICache)
- Improve crawl reliability through browser pooling and health monitoring
- Prevent rate limiting through adaptive request throttling
- Enable form automation with robust selector management
- Support CAPTCHA detection for graceful degradation

## Features

| ID | Feature | Priority | Status | Effort |
|----|---------|----------|--------|--------|
| FEAT-INFRA-001 | Parallel Infrastructure | P1 | Pending | 4 hrs |
| FEAT-INFRA-002 | Site Intelligence | P1 | Pending | 5 hrs |
| FEAT-INFRA-003 | Challenge Detection | P2 | Pending | 2 hrs |
| FEAT-INFRA-004 | Integration & Testing | P1 | Pending | 3 hrs |

---

## FEAT-INFRA-001: Parallel Infrastructure

**Priority:** P1
**Effort:** 4 hours

### Description
Port browser pool and rate limiting from Spectrum to enable reliable parallel crawling.

### Stories

| ID | Story | Priority | Tasks | Effort |
|----|-------|----------|-------|--------|
| STORY-INFRA-001 | Browser Pool Management | P1 | 4 | 2 hrs |
| STORY-INFRA-002 | Adaptive Rate Limiting | P1 | 3 | 2 hrs |

### STORY-INFRA-001: Browser Pool Management

**User Story:**
As a crawler, I want managed browser instances so that I can process pages in parallel without resource exhaustion.

**Tasks:**
- [ ] TASK-001: Create `src/seo/infrastructure/` directory structure
- [ ] TASK-002: Port BrowserPool class from Spectrum (browser_pool.py)
- [ ] TASK-003: Add BrowserHealth enum and PoolStatus dataclass
- [ ] TASK-004: Implement context metrics with error rate tracking

**Definition of Done:**
- [ ] BrowserPool can start/stop with configurable pool size
- [ ] Context isolation clears cookies/storage between uses
- [ ] Health monitoring detects degraded contexts
- [ ] Automatic recycling of unhealthy contexts

### STORY-INFRA-002: Adaptive Rate Limiting

**User Story:**
As a crawler, I want automatic request throttling so that I don't overwhelm target servers or get blocked.

**Tasks:**
- [ ] TASK-005: Port AdaptiveRateLimiter class (rate_limiter.py)
- [ ] TASK-006: Port TokenBucketLimiter for burst handling
- [ ] TASK-007: Add RateLimitConfig and ResourceMetrics dataclasses

**Definition of Done:**
- [ ] Rate limiter adapts to response times
- [ ] Automatic backoff on errors
- [ ] Gradual recovery when conditions improve
- [ ] Configurable bounds (min/max delay)

---

## FEAT-INFRA-002: Site Intelligence

**Priority:** P1
**Effort:** 5 hours

### Description
Port site profiling, selector management, and AI caching from Spectrum.

### Stories

| ID | Story | Priority | Tasks | Effort |
|----|-------|----------|-------|--------|
| STORY-INFRA-003 | Site Profile Models | P1 | 3 | 1.5 hrs |
| STORY-INFRA-004 | Selector Library | P1 | 3 | 1.5 hrs |
| STORY-INFRA-005 | AI Response Cache | P1 | 3 | 2 hrs |

### STORY-INFRA-003: Site Profile Models

**User Story:**
As a crawler, I want to persist site knowledge so that I can learn from previous crawls.

**Tasks:**
- [ ] TASK-008: Create `src/seo/intelligence/` directory structure
- [ ] TASK-009: Port SiteProfile, PageProfile, FormProfile models
- [ ] TASK-010: Port SelectorEntry with Bayesian confidence scoring

**Definition of Done:**
- [ ] Models serialize/deserialize to JSON
- [ ] Confidence scoring uses Bayesian averaging
- [ ] Page type classification enum available

### STORY-INFRA-004: Selector Library

**User Story:**
As an automation engineer, I want managed selectors with fallbacks so that tests remain robust across site changes.

**Tasks:**
- [ ] TASK-011: Port SelectorLibrary class
- [ ] TASK-012: Implement selector candidate generation
- [ ] TASK-013: Add global pattern fallback system

**Definition of Done:**
- [ ] Selectors have confidence tracking
- [ ] Automatic fallback to alternatives
- [ ] HTML-based candidate generation works

### STORY-INFRA-005: AI Response Cache

**User Story:**
As a system, I want to cache AI responses so that I can reduce API costs and latency.

**Tasks:**
- [ ] TASK-014: Port AICache class (SQLite-based)
- [ ] TASK-015: Implement content-addressable key generation
- [ ] TASK-016: Add cache eviction and size management

**Definition of Done:**
- [ ] Cache uses SQLite index + JSON files
- [ ] TTL-based expiration works
- [ ] Size limit enforcement via LRU eviction

---

## FEAT-INFRA-003: Challenge Detection

**Priority:** P2
**Effort:** 2 hours

### Description
Port CAPTCHA/challenge detection from Spectrum for graceful degradation.

### Stories

| ID | Story | Priority | Tasks | Effort |
|----|-------|----------|-------|--------|
| STORY-INFRA-006 | Challenge Handler | P2 | 4 | 2 hrs |

### STORY-INFRA-006: Challenge Handler

**User Story:**
As a crawler, I want to detect bot challenges so that I can pause for human intervention or skip problematic pages.

**Tasks:**
- [ ] TASK-017: Port ChallengeHandler with detection selectors
- [ ] TASK-018: Add reCAPTCHA, hCaptcha, Cloudflare, Akamai detection
- [ ] TASK-019: Implement pause_for_human() function
- [ ] TASK-020: Add challenge-specific instruction messages

**Definition of Done:**
- [ ] Detects major CAPTCHA types (reCAPTCHA, hCaptcha)
- [ ] Detects CDN challenges (Cloudflare, Akamai)
- [ ] Can pause for manual intervention in headed mode

---

## FEAT-INFRA-004: Integration & Testing

**Priority:** P1
**Effort:** 3 hours

### Description
Wire up ported components and add tests.

### Stories

| ID | Story | Priority | Tasks | Effort |
|----|-------|----------|-------|--------|
| STORY-INFRA-007 | Module Integration | P1 | 3 | 1.5 hrs |
| STORY-INFRA-008 | Unit Tests | P1 | 3 | 1.5 hrs |

### STORY-INFRA-007: Module Integration

**Tasks:**
- [ ] TASK-021: Create `__init__.py` files with exports
- [ ] TASK-022: Update SEO crawler to use BrowserPool
- [ ] TASK-023: Integrate AICache with LLM client

### STORY-INFRA-008: Unit Tests

**Tasks:**
- [ ] TASK-024: Write tests for BrowserPool
- [ ] TASK-025: Write tests for AdaptiveRateLimiter
- [ ] TASK-026: Write tests for AICache

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Browser pool uptime | >99% |
| Cache hit rate | >40% for repeated analyses |
| Rate limit blocks | <1% of requests |
| CAPTCHA detection accuracy | >95% |

---

## Source Files (Spectrum)

| Component | Source Path | Lines |
|-----------|-------------|-------|
| BrowserPool | `tools/site_discovery/parallel/browser_pool.py` | 391 |
| AdaptiveRateLimiter | `tools/site_discovery/parallel/rate_limiter.py` | 332 |
| SiteProfile | `tools/site_discovery/intelligence/site_profile.py` | 420 |
| SelectorLibrary | `tools/site_discovery/intelligence/selector_library.py` | 358 |
| AICache | `tools/site_discovery/intelligence/ai_cache.py` | 434 |
| ChallengeHandler | `tests/utils/challenge_handler.py` | 243 |

---

## Target Structure (SEO)

```
src/seo/
├── infrastructure/
│   ├── __init__.py
│   ├── browser_pool.py
│   └── rate_limiter.py
├── intelligence/
│   ├── __init__.py
│   ├── site_profile.py
│   ├── selector_library.py
│   └── ai_cache.py
└── utils/
    └── challenge_handler.py
```

---

## Gemini Validation Criteria

Per Gemini M1.6, the following criteria must be met:
1. Architecture adherence: Follows SEO project patterns
2. Security best practices: No hardcoded credentials
3. Test coverage: Unit tests for core functionality
4. Realistic effort: Estimates account for integration complexity
