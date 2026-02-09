# Epic 9-12 Clarifications

This document addresses the clarification requests from the Gemini review (2026-02-08) for Epics 9-12.

---

## Epic 9: Browser Infrastructure

### M1.1: Stealth Mode Configuration

**Question:** Where and how will the configuration option to switch between Playwright and `undetected-chromedriver` reside?

**Answer:** Stealth mode configuration is managed through a combination of:

1. **`BrowserPool` constructor parameter:**
   ```python
   pool = BrowserPool(
       stealth_backend="playwright"  # or "undetected"
   )
   ```

2. **Environment variable (fallback):**
   ```bash
   export SEO_STEALTH_BACKEND=undetected
   ```

3. **CLI argument (highest priority):**
   ```bash
   python -m seo.cli analyze --stealth-backend undetected https://example.com
   ```

**Priority order:** CLI > Environment > Constructor default

**Location:** `src/seo/infrastructure/browser_pool.py:156-158`

---

### M1.2: Browser Context Termination on Health Degradation

**Question:** Clarify if "recycling" implies graceful termination or immediate killing, and mechanisms to prevent resource leaks.

**Answer:** Recycling uses **graceful termination with timeout fallback**:

1. **Graceful phase (default):**
   - Close all pages in context via `page.close()`
   - Clear cookies and storage
   - Close context via `context.close()`
   - Timeout: 5 seconds per phase

2. **Force phase (if graceful fails):**
   - Kill context immediately
   - Log warning for investigation
   - Continue with new context creation

3. **Resource leak prevention:**
   - Context metrics track open resources
   - Pool status monitors healthy/degraded/unhealthy counts
   - Automatic recycling when `error_rate > 0.3` or `requests_handled > 100`

**Implementation:** `BrowserPool._recycle_context()` at line 358-374

**Thresholds (configurable):**
```python
MAX_REQUESTS_PER_CONTEXT = 100
ERROR_RATE_RECYCLE_THRESHOLD = 0.3
```

---

### M1.3: Performance Metrics via CDP

**Question:** Specify the type of performance metrics collected and their integration point.

**Answer:** Performance metrics are collected via CDP and stored in `BrowserPerformanceMetrics`:

**Metrics collected:**
- Core Web Vitals: FCP, LCP, CLS, FID, TBT, TTI
- Layout shift entries with element attribution
- Long task entries (>50ms)
- Resource timing (per-resource load times)

**Integration points:**
1. **EvidenceRecord:** CWV metrics are captured in `EvidenceRecord` via `source_api="CDP_PERFORMANCE"`
2. **PageMetadata:** Stored in `cwv_*` fields for per-page analysis
3. **Separate metrics file:** `{crawl_dir}/performance_metrics.json`

**Implementation:** `src/seo/infrastructure/performance_metrics.py`

---

### M1.4: Error Handling for undetected-chromedriver Setup

**Question:** Consider explicit error handling or pre-flight checks during setup/initialization.

**Answer:** Pre-flight checks implemented in `UndetectedBrowser.start()`:

1. **Chrome installation check:**
   ```python
   # Verify Chrome is installed at expected path
   chrome_paths = [
       "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
       "/usr/bin/google-chrome",  # Linux
       "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",  # Windows
   ]
   ```

2. **Version compatibility check:**
   ```python
   # Verify ChromeDriver version matches Chrome
   # Raises UndetectedBrowserSetupError if mismatch
   ```

3. **Error messages:**
   - `UndetectedBrowserSetupError`: Clear message with resolution steps
   - `UndetectedBrowserVersionError`: Chrome/driver version mismatch
   - Graceful fallback to Playwright if undetected setup fails (configurable)

**Implementation:** `src/seo/infrastructure/undetected_browser.py`

---

### M1.5: Human-like Interaction Parameters

**Question:** Specify default and configurable values for human-like interaction parameters.

**Answer:** Human simulation parameters in `HumanSimulator`:

| Parameter | Default | Config Key | Description |
|-----------|---------|------------|-------------|
| `typing_speed_cpm` | 250 | `HUMAN_TYPING_CPM` | Characters per minute |
| `typing_variance` | 0.3 | `HUMAN_TYPING_VARIANCE` | Speed variation (0-1) |
| `typo_chance` | 0.02 | `HUMAN_TYPO_CHANCE` | Probability of typo |
| `pause_min_ms` | 50 | `HUMAN_PAUSE_MIN_MS` | Minimum pause |
| `pause_max_ms` | 200 | `HUMAN_PAUSE_MAX_MS` | Maximum pause |
| `mouse_jitter_px` | 3 | `HUMAN_MOUSE_JITTER_PX` | Mouse movement jitter |

**Configuration via:**
- Environment variables (e.g., `SEO_HUMAN_TYPING_CPM=200`)
- `config.py` constants
- Constructor parameters

**Implementation:** `src/seo/utils/human_simulator.py`

---

### M1.6: Integration with browser_crawler.py

**Question:** Detail how `browser_crawler.py` will interact with the new `BrowserPool`.

**Answer:** Integration pattern:

```python
# In AsyncSiteCrawler.__init__
self._browser_pool = BrowserPool(
    max_size=self.max_concurrent,
    headless=self.headless,
    stealth_backend=stealth_backend,
)

# In crawl_site()
await self._browser_pool.start()

# In _crawl_page()
async with self._browser_pool.acquire() as (context, page):
    await page.goto(url)
    # ... crawl logic
    # Context automatically returned to pool on exit

# Cleanup
await self._browser_pool.stop()
```

**Migration path:**
1. Replace `self._browser`, `self._context` with `self._browser_pool`
2. Replace `await self._context.new_page()` with `pool.acquire()`
3. Replace page pool logic with BrowserPool's built-in pooling
4. Remove manual session error recovery (handled by pool)

---

## Epic 10: Rate Limiting & Metrics

### M1.1: Granularity of Rate Limiting

**Question:** Is rate limiting applied globally, per-domain, or per-request type?

**Answer:** **Per-domain** rate limiting is the default:

```python
class DomainRateLimiter:
    """Manages per-domain rate limiters."""

    def __init__(self, default_config: RateLimitConfig = None):
        self._limiters: dict[str, AdaptiveRateLimiter] = {}
        self._default_config = default_config or RateLimitConfig()

    def get_limiter(self, domain: str) -> AdaptiveRateLimiter:
        if domain not in self._limiters:
            self._limiters[domain] = AdaptiveRateLimiter(self._default_config)
        return self._limiters[domain]

    async def wait(self, url: str) -> float:
        domain = urlparse(url).netloc
        return await self.get_limiter(domain).wait()
```

**Rationale:** Per-domain is recommended for SEO crawling because:
- Different domains have different rate limits
- Prevents cross-domain interference
- Allows domain-specific backoff

---

### M1.2: Configuration of Limiter Choice

**Question:** Clarify how the choice between `AdaptiveRateLimiter` and `TokenBucketLimiter` is configured.

**Answer:**

| Limiter | Use Case | Configuration |
|---------|----------|---------------|
| `AdaptiveRateLimiter` | Default for crawling | Adjusts based on response times/errors |
| `TokenBucketLimiter` | Burst traffic control | For APIs with strict rate limits |

**Configuration:**
```python
# In config.py or CLI
RATE_LIMITER_TYPE = "adaptive"  # or "token_bucket"

# Or combined usage:
rate_limiter = AdaptiveRateLimiter(config)
burst_limiter = TokenBucketLimiter(rate=10, capacity=50)

async def rate_limited_request():
    await rate_limiter.wait()
    await burst_limiter.acquire()
    # make request
```

---

### M1.3: Error Definition for Rate Limiter

**Question:** Define what constitutes an "error" for the `AdaptiveRateLimiter`'s error rate threshold.

**Answer:** Errors are classified as:

**Counted as errors (trigger backoff):**
- HTTP 429 (Too Many Requests)
- HTTP 503 (Service Unavailable)
- HTTP 500-599 (Server errors)
- Connection timeout
- Connection reset
- DNS resolution failure

**Not counted as errors:**
- HTTP 400-499 (except 429) - client errors, not rate limiting
- HTTP 200-399 - success/redirect
- Page content errors (JS errors, missing elements)

**Implementation:**
```python
def record_request(self, response_time: float, status_code: int = 200):
    success = status_code < 500 and status_code != 429
    # ... existing logic
```

---

### M1.4: Integration with crawler.py

**Question:** Detail the specific interaction points within `crawler.py`.

**Answer:** Integration points in `AsyncSiteCrawler`:

```python
# 1. Initialization
self._rate_limiter = DomainRateLimiter(RateLimitConfig(
    base_delay=self.rate_limit,
    target_response_time=2.0,
))

# 2. Before each request (in _crawl_page)
async def _crawl_page(self, url: str, ...):
    # Wait for rate limit
    wait_time = await self._rate_limiter.wait(url)

    # Make request
    start = time.time()
    response = await page.goto(url)
    response_time = time.time() - start

    # Record result
    self._rate_limiter.record_request(
        url,
        response_time=response_time,
        status_code=response.status,
    )

# 3. Metrics reporting
def get_crawl_summary(self):
    return {
        ...
        "rate_limiter_metrics": self._rate_limiter.get_all_metrics(),
    }
```

---

### M1.5: ResourceMetrics Storage and Access

**Question:** Are metrics stored cumulatively, as snapshots, or both?

**Answer:** **Both** - cumulative totals and rolling window snapshots:

```python
@dataclass
class ResourceMetrics:
    # Cumulative (lifetime)
    total_requests: int
    total_errors: int
    total_wait_time: float

    # Rolling window (recent)
    current_delay: float
    avg_response_time: float  # Over window
    error_rate: float         # Over window
    requests_in_window: int
    errors_in_window: int
    last_request_time: datetime | None
```

**Access patterns:**
1. **Real-time:** `limiter.get_metrics()` returns current snapshot
2. **Post-crawl:** `metadata.json` includes aggregated metrics
3. **Historical:** `metrics_history.json` stores periodic snapshots (every 10 requests)

---

### M1.6: Threshold Violations Flagged

**Question:** Define specific thresholds and what constitutes a "flag".

**Answer:**

| Metric | Warning Threshold | Critical Threshold | Flag Type |
|--------|-------------------|-------------------|-----------|
| Error rate | > 10% | > 30% | `EvidenceRecord` + log warning |
| Avg response time | > 3s | > 10s | `EvidenceRecord` + log warning |
| Consecutive errors | > 5 | > 10 | Context recycle + log error |

**Flag representation:**
```python
@dataclass
class ThresholdViolation:
    metric_name: str
    current_value: float
    threshold: float
    severity: str  # "warning" or "critical"
    timestamp: datetime
    domain: str
```

Violations are:
1. Logged with appropriate level
2. Added to `EvidenceRecord` for the affected page
3. Stored in `threshold_violations` array in `metadata.json`

---

## Epic 11: Selector Intelligence

### M1.1: Persistence Mechanism for SelectorLibrary

**Question:** Specify storage location, naming convention, and conflict resolution.

**Answer:**

**Storage location:** `{crawl_output_dir}/selectors/`

**Naming convention:**
- Per-site: `selectors_{site_id}.json` (e.g., `selectors_example_com.json`)
- Global patterns: `global_patterns.json`

**File structure:**
```
crawls/
  example.com/
    2026-02-08_120000/
      selectors/
        selectors_example_com.json
        global_patterns.json
```

**Conflict resolution for concurrent crawls:**
- File locking via `fcntl.flock()` on Unix, `msvcrt.locking()` on Windows
- Atomic writes using temp file + rename
- Merge strategy: higher confidence selector wins

---

### M1.2: Definition of "Purpose"

**Question:** Define a standardized list or enum of common selector purposes.

**Answer:** Standardized enum in `SelectorPurpose`:

```python
class SelectorPurpose(Enum):
    # Form fields
    FIELD_EMAIL = "field_email"
    FIELD_PASSWORD = "field_password"
    FIELD_FIRST_NAME = "field_first_name"
    FIELD_LAST_NAME = "field_last_name"
    FIELD_ADDRESS = "field_address"
    FIELD_CITY = "field_city"
    FIELD_STATE = "field_state"
    FIELD_ZIP = "field_zip"
    FIELD_PHONE = "field_phone"
    FIELD_CREDIT_CARD = "field_credit_card"
    FIELD_CVV = "field_cvv"
    FIELD_EXPIRY = "field_expiry"

    # Buttons
    BTN_SUBMIT = "btn_submit"
    BTN_ADD_TO_CART = "btn_add_to_cart"
    BTN_CHECKOUT = "btn_checkout"
    BTN_CONTINUE = "btn_continue"
    BTN_CLOSE = "btn_close"

    # Navigation
    NAV_NEXT_PAGE = "nav_next_page"
    NAV_PREV_PAGE = "nav_prev_page"
    NAV_CATEGORY = "nav_category"

    # Content
    CONTENT_PRICE = "content_price"
    CONTENT_TITLE = "content_title"
    CONTENT_DESCRIPTION = "content_description"

    # Custom (for site-specific purposes)
    CUSTOM = "custom"
```

---

### M1.3: Cross-site vs. Site-specific Fallbacks

**Question:** How are global fallback patterns prioritized relative to site-specific selectors?

**Answer:** Priority order (highest to lowest):

1. **Site-specific primary selector** (highest confidence)
2. **Site-specific alternatives** (by confidence score)
3. **Global patterns** (lowest confidence, 0.3 default)

**Implementation in `get_selector_with_fallbacks()`:**
```python
def get_selector_with_fallbacks(self, site_id: str, purpose: str) -> list[SelectorEntry]:
    selectors = []

    # 1. Site-specific primary
    primary = self.get_selector(site_id, purpose)
    if primary:
        selectors.append(primary)
        # 2. Site-specific alternatives
        for alt in primary.alternatives:
            selectors.append(SelectorEntry(
                selector=alt,
                confidence=primary.confidence * 0.8,
            ))

    # 3. Global patterns (last resort)
    if purpose in self._global_patterns:
        for pattern in self._global_patterns[purpose]:
            if not any(s.selector == pattern for s in selectors):
                selectors.append(SelectorEntry(
                    selector=pattern,
                    confidence=0.3,  # Low confidence for globals
                ))

    return sorted(selectors, key=lambda s: s.confidence, reverse=True)
```

---

### M1.4: Integration with BeautifulSoup

**Question:** Detail how BeautifulSoup will be used for selector candidate generation.

**Answer:** BeautifulSoup is used for **static HTML analysis** to generate selector candidates:

```python
def generate_candidates(self, element_html: str, purpose: str) -> list[SelectorCandidate]:
    """Generate selector candidates from element HTML using multiple strategies."""

    soup = BeautifulSoup(element_html, 'html.parser')
    element = soup.find()  # Get root element

    candidates = []

    # Strategy 1: ID-based (highest stability)
    if element.get('id'):
        candidates.append(SelectorCandidate(
            selector=f"#{element['id']}",
            stability_score=0.95,
        ))

    # Strategy 2: data-testid (very stable)
    if element.get('data-testid'):
        candidates.append(SelectorCandidate(
            selector=f"[data-testid='{element['data-testid']}']",
            stability_score=0.98,
        ))

    # ... additional strategies
```

**Context:** BeautifulSoup parses the element HTML captured from Playwright's `element.inner_html()` or page's static HTML.

---

### M1.5: Initial Stability Scores

**Question:** Confirm if provided stability scores are fixed, configurable, or dynamically calculated.

**Answer:** **Fixed defaults with configurable overrides:**

| Selector Type | Default Stability | Config Key |
|---------------|-------------------|------------|
| ID-based | 0.95 | `SELECTOR_STABILITY_ID` |
| data-testid | 0.98 | `SELECTOR_STABILITY_TESTID` |
| data-* attributes | 0.85 | `SELECTOR_STABILITY_DATA_ATTR` |
| aria-label | 0.80 | `SELECTOR_STABILITY_ARIA` |
| Class-based | 0.60 | `SELECTOR_STABILITY_CLASS` |
| Text content (XPath) | 0.40 | `SELECTOR_STABILITY_TEXT` |

**Configuration:**
```python
# In config.py
SELECTOR_STABILITY_SCORES = {
    "id": 0.95,
    "testid": 0.98,
    # ... etc
}
```

---

### M1.6: Confidence Adjustment Magnitude

**Question:** Specify the magnitude of confidence adjustments and bounds.

**Answer:**

**Adjustment formula (Bayesian):**
```python
confidence = (success_count + PRIOR_SUCCESS) / (total_count + PRIOR_TOTAL)
```

Where:
- `PRIOR_SUCCESS = 2`
- `PRIOR_FAILURE = 1`
- `PRIOR_TOTAL = 3`

**Additional adjustments:**
- Recent failure penalty: `-5%` (multiply by 0.95)
- Bounds: `min=0.0`, `max=1.0`

**Example progression:**
| Successes | Failures | Raw Confidence | With Prior |
|-----------|----------|----------------|------------|
| 0 | 0 | N/A | 0.67 |
| 1 | 0 | 1.00 | 0.75 |
| 5 | 0 | 1.00 | 0.88 |
| 5 | 2 | 0.71 | 0.70 |
| 10 | 0 | 1.00 | 0.92 |

---

### M1.7: FormHandler Integration Details

**Question:** Outline API changes in `form_handler.py`.

**Answer:**

**New constructor parameter:**
```python
class FormHandler:
    def __init__(
        self,
        page: Page,
        selector_library: SelectorLibrary | None = None,
        site_id: str | None = None,
    ):
        self._selector_library = selector_library
        self._site_id = site_id
```

**New methods:**
```python
async def _try_library_selectors(
    self,
    purpose: str,
    fallback_selectors: list[str],
) -> tuple[str | None, str | None]:
    """Try selectors from library, falling back to provided list."""

    if self._selector_library and self._site_id:
        selectors = self._selector_library.get_selector_with_fallbacks(
            self._site_id, purpose
        )
        for entry in selectors:
            element = await self._try_selector(entry.selector)
            if element:
                return entry.selector, entry.selector

    # Fallback to provided selectors
    for selector in fallback_selectors:
        element = await self._try_selector(selector)
        if element:
            return selector, None

    return None, None

def _record_selector_result(
    self,
    purpose: str,
    selector: str,
    success: bool,
    is_alternative: bool = False,
) -> None:
    """Record selector success/failure in library."""
    if not self._selector_library or not self._site_id:
        return

    if is_alternative:
        if success:
            self._selector_library.record_alternative_result(
                self._site_id, purpose, selector, success=True
            )
        else:
            self._selector_library.record_alternative_result(
                self._site_id, purpose, selector, success=False
            )
    else:
        if success:
            self._selector_library.record_success(self._site_id, purpose)
        else:
            self._selector_library.record_failure(self._site_id, purpose)
```

---

## Epic 12: AI/LLM Caching

### M1.1: Cache Directory Structure

**Question:** Specify the detailed directory structure for JSON response files.

**Answer:**

```
{cache_root}/
├── cache_index.db          # SQLite metadata index
└── responses/              # JSON response files
    ├── 00/                 # Hash prefix subdirectory
    │   ├── 00a1b2c3...json
    │   └── 00f4e5d6...json
    ├── 01/
    │   └── 01b2c3d4...json
    ├── ...
    └── ff/
        └── ff9e8d7c...json
```

**Rationale:** Hash prefix subdirectories prevent filesystem issues with too many files in a single directory (commonly limited to ~32K entries).

**Permissions:** `0755` for directories, `0644` for files

**Auto-creation:** Directories are created on-demand when storing responses.

---

### M1.2: SQLite Database Management

**Question:** Clarify storage location, naming, and concurrency handling.

**Answer:**

**Location:** `{cache_root}/cache_index.db`

**Schema:**
```sql
CREATE TABLE cache_entries (
    key TEXT PRIMARY KEY,
    prompt_hash TEXT NOT NULL,
    model TEXT NOT NULL,
    response_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    hit_count INTEGER DEFAULT 0,
    last_hit TEXT
);

CREATE INDEX idx_expires_at ON cache_entries(expires_at);
CREATE INDEX idx_prompt_hash ON cache_entries(prompt_hash);
```

**Concurrency handling:**
- Thread lock (`threading.Lock()`) for in-process safety
- `check_same_thread=False` for multi-threaded access
- WAL mode for better concurrent read performance:
  ```python
  conn.execute("PRAGMA journal_mode=WAL")
  ```
- File-level locking not needed (SQLite handles it)

---

### M1.3: Content-Addressable Storage Normalization

**Question:** Define exact normalization steps for prompt/context hashing.

**Answer:**

**Normalization steps:**
1. **Prompt normalization:**
   - Strip leading/trailing whitespace
   - Normalize Unicode (NFC form)
   - Lowercase (optional, configurable)

2. **Context normalization:**
   - Sort dictionary keys recursively
   - Remove null/None values
   - Serialize with `json.dumps(sort_keys=True)`

3. **Hash computation:**
   ```python
   def _compute_key(self, prompt: str, context: dict | None) -> str:
       # Normalize prompt
       normalized_prompt = prompt.strip()

       # Normalize and serialize context
       content = normalized_prompt
       if context:
           # Sort keys, remove nulls
           clean_context = {
               k: v for k, v in sorted(context.items())
               if v is not None
           }
           content += json.dumps(clean_context, sort_keys=True)

       return hashlib.sha256(content.encode('utf-8')).hexdigest()
   ```

---

### M1.4: LRU Eviction Strategy Details

**Question:** Detail LRU implementation and cache size calculation.

**Answer:**

**Size calculation:**
- Count actual file sizes on disk (JSON files + DB file)
- Periodic recalculation (not on every write)
- Cached size value with dirty flag

**LRU implementation:**
```python
def _enforce_size_limit_unlocked(self, conn: sqlite3.Connection) -> None:
    """Evict oldest entries until under size limit."""
    while self._get_cache_size_mb() > self.max_size_mb:
        # Find oldest by created_at (LRU uses last_hit, but created_at as tiebreaker)
        cursor = conn.execute("""
            SELECT key FROM cache_entries
            ORDER BY
                COALESCE(last_hit, created_at) ASC,
                created_at ASC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if not row:
            break
        self._remove_entry_unlocked(conn, row["key"])
```

**Eviction triggers:**
- After each `put()` operation
- Configurable high-water mark (default: 90% of max)

---

### M1.5: Similarity Search Algorithm

**Question:** Elaborate on the similarity search algorithm.

**Answer:**

**Current implementation: Hash-prefix matching (simple, fast)**

```python
def find_similar(self, prompt: str, limit: int = 5) -> list[dict]:
    """Find similar prompts using hash prefix matching."""
    prompt_hash = self._compute_prompt_hash(prompt)
    prefix = prompt_hash[:8]  # First 8 chars

    cursor = conn.execute("""
        SELECT key, prompt_hash, model, created_at, hit_count
        FROM cache_entries
        WHERE prompt_hash LIKE ?
        ORDER BY hit_count DESC
        LIMIT ?
    """, (f"{prefix}%", limit))

    return [dict(row) for row in cursor.fetchall()]
```

**Future enhancement: Embedding-based similarity (optional)**

```python
# Optional embedding-based search (requires additional setup)
class EmbeddingCache(AICache):
    def __init__(self, ..., embedding_model: str = "text-embedding-3-small"):
        self._embedding_model = embedding_model
        # Additional table for embeddings

    def find_similar_by_embedding(
        self,
        prompt: str,
        threshold: float = 0.85,
        limit: int = 5,
    ) -> list[dict]:
        """Find similar using cosine similarity on embeddings."""
        query_embedding = self._get_embedding(prompt)
        # ... similarity search implementation
```

**Configuration:**
```python
# In config.py
AI_CACHE_SIMILARITY_MODE = "hash_prefix"  # or "embedding"
AI_CACHE_SIMILARITY_THRESHOLD = 0.85      # For embedding mode
```

---

### M1.6: Integration with LLMClient

**Question:** Detail the integration mechanism with `llm.py`.

**Answer:**

**Integration approach: Wrapper method with transparent caching**

```python
class LLMClient:
    def __init__(
        self,
        api_key: str,
        cache: AICache | None = None,
        cache_enabled: bool = True,
    ):
        self._cache = cache
        self._cache_enabled = cache_enabled and cache is not None

    async def get_seo_analysis(
        self,
        content: str,
        metadata: dict,
        url: str,
        use_cache: bool = True,
    ) -> dict:
        """Get SEO analysis with automatic caching."""
        prompt = self._build_seo_prompt(content, metadata, url)
        context = {"url": url, "word_count": metadata.get("word_count")}

        # Try cache first
        if self._cache_enabled and use_cache:
            cached = self._cache.get(prompt, context)
            if cached:
                cached["_from_cache"] = True
                return cached

        # Call LLM
        response = await self._call_llm(prompt)
        result = self._parse_seo_response(response)

        # Store in cache
        if self._cache_enabled and use_cache:
            self._cache.put(prompt, result, self.model, context)

        result["_from_cache"] = False
        return result
```

**Cache bypass:**
- `use_cache=False` parameter for forced refresh
- Automatic bypass for prompts with `temperature > 0`

---

### M1.7: Cache Statistics Reporting

**Question:** Specify where cache statistics will be stored and presented.

**Answer:**

**Storage locations:**

1. **metadata.json (per-crawl):**
   ```json
   {
     "ai_cache_stats": {
       "enabled": true,
       "entry_count": 150,
       "size_mb": 12.5,
       "total_hits": 89,
       "hit_rate": 0.59,
       "ttl_hours": 24
     }
   }
   ```

2. **EvidenceRecord (per-recommendation):**
   ```python
   EvidenceRecord(
       component_id="llm_recommendation",
       source_api="OPENAI_GPT4",
       cache_hit=True,
       cache_key="abc123...",
   )
   ```

3. **CLI output:**
   ```
   AI Cache: 89/150 hits (59.3%), 12.5MB used
   ```

4. **HTML report:**
   - Summary in metadata section
   - Per-recommendation cache indicator

---

## Summary of Implementation Status

| Epic | Clarification | Status | Location |
|------|---------------|--------|----------|
| 9.1 | Stealth config | Implemented | `browser_pool.py:156` |
| 9.2 | Context termination | Implemented | `browser_pool.py:358` |
| 9.3 | Performance metrics | Implemented | `performance_metrics.py` |
| 9.4 | UC error handling | Implemented | `undetected_browser.py` |
| 9.5 | Human simulation | Implemented | `human_simulator.py` |
| 9.6 | BrowserPool integration | **Pending** | See integration plan |
| 10.1 | Per-domain limiting | Implemented | `rate_limiter.py` |
| 10.2 | Limiter choice | Implemented | Config-based |
| 10.3 | Error definition | Documented | This file |
| 10.4 | Crawler integration | **Pending** | See integration plan |
| 10.5 | Metrics storage | Implemented | Both modes |
| 10.6 | Threshold flags | Implemented | `EvidenceRecord` |
| 11.1 | SelectorLibrary persistence | Implemented | `selector_library.py` |
| 11.2 | Purpose enum | Documented | This file |
| 11.3 | Fallback priority | Implemented | `selector_library.py:130` |
| 11.4 | BeautifulSoup integration | Implemented | `selector_library.py:207` |
| 11.5 | Stability scores | Configurable | `config.py` |
| 11.6 | Confidence adjustment | Implemented | Bayesian formula |
| 11.7 | FormHandler integration | **Pending** | See integration plan |
| 12.1 | Cache directory | Implemented | `ai_cache.py:152` |
| 12.2 | SQLite management | Implemented | WAL mode, locks |
| 12.3 | Normalization | Implemented | `ai_cache.py:139` |
| 12.4 | LRU eviction | Implemented | `ai_cache.py:336` |
| 12.5 | Similarity search | Hash-prefix | Embedding optional |
| 12.6 | LLMClient integration | **Pending** | See integration plan |
| 12.7 | Cache stats | Implemented | Multiple locations |

---

*Document created: 2026-02-09*
*Last updated: 2026-02-09*
