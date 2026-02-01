# SEO Crawler Output Examples

This document shows what output you get from the different crawlers.

---

## 📊 Terminal Output (What You See)

### Running `python crawl.py https://example.com 10`

```
Initializing SEO Analyzer...
Provider: openai
Model: gpt-4

Starting site crawl...
URL: https://example.com
Max pages: 10
Rate limit: 0.5s between requests

[L1] Crawling (1/10): https://example.com
  ✓ Success - 1247 words, 15 internal links
  → Queued 12 new links for L2

[L2] Crawling (2/10): https://example.com/about
  ✓ Success - 856 words, 8 internal links
  → Queued 5 new links for L3

[L2] Crawling (3/10): https://example.com/services
  ✓ Success - 1523 words, 22 internal links
  → Queued 18 new links for L3

... (continues for all pages)

============================================================
Analyzing Technical SEO Issues...
============================================================

TECHNICAL SEO ISSUES SUMMARY
============================================================

Missing Titles (0):

Duplicate Titles (1):
  Title: "Home - Example Company"
    - https://example.com
    - https://example.com/

Missing Meta Descriptions (2):
  • https://example.com/contact
  • https://example.com/privacy

Short Meta Descriptions (3):
  • https://example.com/about (45 chars)
  • https://example.com/blog (78 chars)
  • https://example.com/services (92 chars)

Missing H1 Tags (1):
  • https://example.com/404

Images Without Alt Text (3):
  • https://example.com (3/12 images)
  • https://example.com/about (1/4 images)
  • https://example.com/services (5/18 images)

Slow Pages (2):
  • https://example.com/services (3.42s)
  • https://example.com/portfolio (4.18s)

Thin Content Pages (1):
  • https://example.com/contact (187 words)

Missing Canonical URLs (0):

============================================================
Generating AI-Powered Recommendations...
============================================================

## Critical Issues (Priority 1 - Fix Immediately)

1. **Slow Page Load Times**
   - Impact: Pages loading >3s will see 40% bounce rate increase
   - Pages affected: /services (3.42s), /portfolio (4.18s)
   - Fix: Optimize images, minify CSS/JS, enable caching
   - Expected result: 50-70% load time reduction

2. **Missing Meta Descriptions**
   - Impact: Lower click-through rates from search results
   - Pages affected: 2 pages
   - Fix: Write unique 120-160 character descriptions
   - Expected result: 5-15% CTR improvement

## Quick Wins (Priority 2 - Easy fixes with high impact)

3. **Images Missing Alt Text**
   - Impact: Accessibility and image SEO issues
   - Total images affected: 9 of 34 images
   - Fix: Add descriptive alt text to all images
   - Expected result: Better accessibility score, image search traffic

4. **Short Meta Descriptions**
   - Impact: Not fully utilizing SERP real estate
   - Pages affected: 3 pages with <120 char descriptions
   - Fix: Expand descriptions to 120-160 characters
   - Expected result: Better SERP CTR

## Content Optimization

5. **Thin Content**
   - The contact page has only 187 words
   - Recommendation: Add helpful content about contact methods, hours, FAQ
   - Target: 300+ words for better relevance signals

## Technical SEO Improvements

6. **Duplicate Title Tags**
   - / and /index both use same title
   - Fix: Implement proper canonical tag or redirect
   - Prevents duplicate content issues

## 30-Day Action Plan

**Week 1:**
- Fix slow loading pages (optimize images, caching)
- Add missing meta descriptions
- Add alt text to all images

**Week 2:**
- Expand thin content pages
- Fix short meta descriptions
- Resolve duplicate titles

**Week 3:**
- Internal linking audit
- Schema markup implementation
- Mobile optimization review

**Week 4:**
- Performance monitoring
- Track ranking improvements
- Iterate on content

============================================================
CRAWL SUMMARY
============================================================
Total pages crawled: 10
Total words: 12,456
Average words per page: 1,245
Total images: 34

============================================================
TECHNICAL ISSUES SUMMARY
============================================================
Missing titles: 0
Duplicate titles: 1
Missing meta descriptions: 2
Missing H1 tags: 1
Images without alt text: 3
Slow pages (>3s): 2
Thin content (<300 words): 1
Missing canonical URLs: 0

============================================================
CRAWLED PAGES
============================================================
  1. ✓ https://example.com
  2. ✓ https://example.com/about [no description]
  3. ✓ https://example.com/services
  4. ✓ https://example.com/portfolio
  5. ✓ https://example.com/blog
  6. ✓ https://example.com/contact [no description, 187w]
  7. ✓ https://example.com/pricing
  8. ✓ https://example.com/faq
  9. ✓ https://example.com/terms
 10. ✓ https://example.com/privacy [no H1]

============================================================
Crawl complete!
============================================================
```

---

## ⚡ Async Crawler Output

### Running `python async_crawl.py https://example.com 10`

```
Initializing Async SEO Crawler...
Max pages: 10
Rate limit: 0.5s
Max concurrent: 10

Starting async crawl of https://example.com...

INFO - Loaded robots.txt from https://example.com/robots.txt

--- Moving to Level 1 ---

[L1] Crawling (1/10): https://example.com
  ✓ Success - 1247 words, 15 internal links, 0.52s
  → Queued 12 new links for L2

--- Moving to Level 2 ---

[L2] Crawling (2/10): https://example.com/about
  ✓ Success - 856 words, 8 internal links, 0.38s
[L2] Crawling (3/10): https://example.com/services
  ✓ Success - 1523 words, 22 internal links, 0.45s
[L2] Crawling (4/10): https://example.com/contact
  ✓ Success - 187 words, 3 internal links, 0.29s
  → Queued 18 new links for L3

... (continues)

============================================================
CRAWL SUMMARY
============================================================
Total pages crawled: 10
Total time: 3.24 seconds
Average time per page: 0.32s
Total words: 12,456
Average words per page: 1,245
Total images: 34
Average page load time: 0.41s

============================================================
QUICK ISSUES SUMMARY
============================================================
Missing titles: 0
Missing meta descriptions: 2
Missing H1 tags: 1
Thin content (<300 words): 1
Non-HTTPS pages: 0

============================================================
CRAWLED PAGES
============================================================
  1. ✓ https://example.com
  2. ✓ https://example.com/about [no desc]
  3. ✓ https://example.com/services
  4. ✓ https://example.com/portfolio
  5. ✓ https://example.com/blog
  6. ✓ https://example.com/contact [no desc, 187w]
  7. ✓ https://example.com/pricing
  8. ✓ https://example.com/faq
  9. ✓ https://example.com/terms
 10. ✓ https://example.com/privacy [no H1, no viewport]

============================================================
⚡ Async crawl complete in 3.24s!
============================================================
```

**Notice:** Async crawler shows concurrent processing and includes timing info!

---

## 📦 Data Structures Returned

### Python API - What You Get Back

#### 1. `crawl.py` or `analyzer.analyze_site()`

```python
site_data, technical_issues, llm_recommendations = analyzer.analyze_site(
    start_url="https://example.com",
    max_pages=50
)
```

**Returns 3 things:**

#### A. `site_data` - Dict[str, PageMetadata]
Dictionary mapping URLs to page metadata:

```python
{
    "https://example.com": PageMetadata(
        url="https://example.com",
        title="Home - Example Company",
        description="Leading provider of...",
        keywords=["example", "company", "services"],
        h1_tags=["Welcome to Example Company"],
        h2_tags=["Our Services", "Why Choose Us", "Get Started"],
        word_count=1247,
        load_time=0.52,
        status_code=200,
        internal_links=15,
        external_links=3,
        total_images=12,
        images_without_alt=3,
        canonical_url="https://example.com",
        has_https=True,
        viewport_meta="width=device-width, initial-scale=1",
        lang_attribute="en",
        charset="utf-8",
        schema_markup=[{...}],  # Structured data found
        open_graph={"og:title": "...", "og:image": "..."},
        twitter_card={"twitter:card": "summary_large_image"},
        security_headers={"strict-transport-security": "..."},
        robots_directives={"noindex": False, "nofollow": False},
        hreflang_tags=[],
        content_text="Full page text...",
    ),
    "https://example.com/about": PageMetadata(...),
    # ... all crawled pages
}
```

#### B. `technical_issues` - TechnicalIssues
Object with lists of issues found:

```python
TechnicalIssues(
    missing_titles=[],  # Empty = good!
    duplicate_titles={
        "Home - Example Company": [
            "https://example.com",
            "https://example.com/"
        ]
    },
    missing_meta_descriptions=[
        "https://example.com/contact",
        "https://example.com/privacy"
    ],
    short_meta_descriptions=[
        ("https://example.com/about", 45),
        ("https://example.com/blog", 78)
    ],
    long_meta_descriptions=[],
    missing_h1=["https://example.com/404"],
    multiple_h1=[],
    images_without_alt=[
        ("https://example.com", 3, 12),  # 3 of 12 images
        ("https://example.com/about", 1, 4)
    ],
    slow_pages=[
        ("https://example.com/services", 3.42),
        ("https://example.com/portfolio", 4.18)
    ],
    thin_content=[
        ("https://example.com/contact", 187)  # only 187 words
    ],
    missing_canonical=[],
    missing_viewport=[],
    missing_lang=[],
    non_https=[],
    broken_links=[],
    missing_structured_data=[],
    poor_readability=[]
)
```

#### C. `llm_recommendations` - String
AI-generated recommendations from your LLM:

```python
"""
## Critical Issues (Priority 1)
1. Slow page load times on /services and /portfolio
2. Missing meta descriptions on 2 pages

## Quick Wins (Priority 2)
3. Add alt text to 9 images
4. Expand short meta descriptions
...

## 30-Day Action Plan
Week 1: ...
Week 2: ...
"""
```

---

## 🔧 Advanced Features - What Else You Can Extract

### Content Quality Analysis

```python
from seo import ContentQualityAnalyzer

analyzer = ContentQualityAnalyzer()
metrics = analyzer.analyze(url, page.content_text)

print(f"Readability Score: {metrics.readability_score}/100")
# Output: Readability Score: 72.3/100

print(f"Grade Level: {metrics.readability_grade}")
# Output: Grade Level: 8-9th Grade

print(f"Keyword Density: {metrics.keyword_density}")
# Output: {'seo': 3.2, 'optimization': 2.1, 'content': 1.8, ...}
```

### Security Analysis

```python
from seo import SecurityAnalyzer

sec_analyzer = SecurityAnalyzer()
security = sec_analyzer.analyze(url, page_metadata, page.security_headers)

print(f"Security Score: {security.security_score}/100")
# Output: Security Score: 80/100

print(f"Has HTTPS: {security.has_https}")
# Output: Has HTTPS: True

print(f"Security Headers: {security.security_headers}")
# Output: {'strict-transport-security': 'max-age=31536000', ...}
```

### URL Structure Analysis

```python
from seo import URLStructureAnalyzer

url_analyzer = URLStructureAnalyzer()
url_analysis = url_analyzer.analyze("https://example.com/blog/seo-tips")

print(f"URL Length: {url_analysis.url_length}")
# Output: URL Length: 38

print(f"Has Keywords: {url_analysis.has_keywords}")
# Output: Has Keywords: True

print(f"Depth Level: {url_analysis.depth_level}")
# Output: Depth Level: 2

print(f"Issues: {url_analysis.issues}")
# Output: []  (empty = no issues!)
```

---

## 💾 JSON Export

You can also export everything as JSON:

### CLI with JSON output:

```bash
python crawl.py https://example.com 10 --output json --output-file results.json
```

### JSON Structure:

```json
{
  "start_url": "https://example.com",
  "total_pages": 10,
  "pages": {
    "https://example.com": {
      "title": "Home - Example Company",
      "description": "Leading provider of...",
      "word_count": 1247,
      "load_time": 0.52,
      "h1_tags": ["Welcome to Example Company"],
      "internal_links": 15,
      "external_links": 3
    },
    ...
  },
  "technical_issues": {
    "missing_titles": [],
    "duplicate_titles": {...},
    "missing_meta_descriptions": [...],
    ...
  },
  "recommendations": "AI-generated recommendations here..."
}
```

---

## 📊 Summary - What You Get

### From Terminal:
1. ✅ Real-time crawl progress (L1, L2, L3...)
2. ✅ Technical issues summary (counts of each issue)
3. ✅ AI-powered recommendations with priorities
4. ✅ Detailed page list with inline issues
5. ✅ Crawl statistics (total words, images, timing)

### From Python API:
1. ✅ `site_data` - Full metadata for every page
2. ✅ `technical_issues` - Organized lists of all problems
3. ✅ `llm_recommendations` - AI analysis and action plan

### From JSON Export:
1. ✅ Complete structured data
2. ✅ Easy to process programmatically
3. ✅ Can be imported into databases or dashboards

---

## 🎯 Quick Reference

| What You Want | How to Get It |
|---------------|---------------|
| Quick terminal output | `python crawl.py URL` |
| Fast async crawl | `python async_crawl.py URL` |
| JSON export | Add `--output json -f results.json` |
| Python data structures | Use `analyzer.analyze_site()` |
| Just technical issues | Access `technical_issues` object |
| Individual page data | Access `site_data[url]` |
| AI recommendations | Read `llm_recommendations` string |

---

**Try it now:**
```bash
python async_crawl.py https://example.com 10
```

This will show you all the output types! 🚀
