# Claude Change Log

This log tracks all significant changes made by Claude during development.

---

## EPIC-SEO-INFRA-001: SEO Infrastructure Upgrade

**Date:** 2026-02-08
**Status:** Complete

### Overview

Ported battle-tested infrastructure components from Spectrum to SEO per BORROW.md recommendations.

---

### Milestone: Infrastructure Port

**Date:** 2026-02-08

**Artifacts Created:**

| File | Description |
|------|-------------|
| `src/seo/infrastructure/__init__.py` | Package exports for BrowserPool, RateLimiter |
| `src/seo/infrastructure/browser_pool.py` | Browser pool with health monitoring, session isolation |
| `src/seo/infrastructure/rate_limiter.py` | Adaptive rate limiter with exponential backoff |
| `src/seo/intelligence/__init__.py` | Package exports for site intelligence |
| `src/seo/intelligence/site_profile.py` | SiteProfile, PageProfile, FormProfile, SelectorEntry models |
| `src/seo/intelligence/selector_library.py` | Selector management with Bayesian confidence |
| `src/seo/intelligence/ai_cache.py` | SQLite-indexed AI response cache |
| `src/seo/utils/__init__.py` | Package exports for utilities |
| `src/seo/utils/challenge_handler.py` | CAPTCHA/bot challenge detection |
| `docs/plans/EPIC-SEO-INFRASTRUCTURE.md` | Epic document with features, stories, tasks |

**Artifacts Modified:**

| File | Changes |
|------|---------|
| `src/seo/__init__.py` | Added exports for infrastructure, intelligence, utils packages |
| `src/seo/llm.py` | Integrated AICache for LLM response caching |

**Tests Added:** 0 (pending)
**Tests Passing:** N/A

**Status:** Complete

---

### Key Capabilities Added

1. **Browser Pooling** (`infrastructure/browser_pool.py`)
   - Async context acquisition with automatic release
   - Session isolation (cookies/storage cleared between uses)
   - Health monitoring per context (HEALTHY, DEGRADED, UNHEALTHY)
   - Automatic recycling after 100 requests or 30% error rate
   - Thread-safe with async locks

2. **Adaptive Rate Limiting** (`infrastructure/rate_limiter.py`)
   - Response time-based throttling
   - Exponential backoff on errors
   - Gradual recovery when conditions improve
   - Token bucket for burst handling
   - Configurable bounds (min/max delay)

3. **Site Intelligence** (`intelligence/`)
   - `SiteProfile`: Top-level container for site knowledge
   - `PageProfile`: Page classification and structure
   - `FormProfile`: Form fields and interaction patterns
   - `SelectorEntry`: CSS/XPath selectors with Bayesian confidence
   - `SelectorLibrary`: Multi-strategy selector generation

4. **AI Response Caching** (`intelligence/ai_cache.py`)
   - Content-addressable keys (SHA256)
   - SQLite index for fast lookups
   - JSON file storage for responses
   - TTL-based expiration
   - LRU eviction for size limits

5. **Challenge Detection** (`utils/challenge_handler.py`)
   - reCAPTCHA v2/v3 detection
   - hCaptcha detection
   - Cloudflare challenge detection
   - Akamai Bot Manager detection
   - Human intervention pause mechanism

6. **LLM Cache Integration** (`llm.py`)
   - Cache check before API calls
   - Automatic caching of successful responses
   - Cache hit/miss statistics
   - 24-hour default TTL

---

### Source References

All components ported from Spectrum project:

| SEO File | Spectrum Source |
|----------|-----------------|
| `infrastructure/browser_pool.py` | `tools/site_discovery/parallel/browser_pool.py` |
| `infrastructure/rate_limiter.py` | `tools/site_discovery/parallel/rate_limiter.py` |
| `intelligence/site_profile.py` | `tools/site_discovery/intelligence/site_profile.py` |
| `intelligence/selector_library.py` | `tools/site_discovery/intelligence/selector_library.py` |
| `intelligence/ai_cache.py` | `tools/site_discovery/intelligence/ai_cache.py` |
| `utils/challenge_handler.py` | `tests/utils/challenge_handler.py` |

---

### Next Steps

- [ ] Add unit tests for ported components
- [ ] Consider integrating BrowserPool with AsyncSiteCrawler (requires rebrowser compatibility check)
- [ ] Add integration tests for AICache with LLMClient
