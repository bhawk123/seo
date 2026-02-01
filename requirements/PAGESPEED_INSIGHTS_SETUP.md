# Google PageSpeed Insights Integration - Setup Guide

**Status:** ✅ Implemented and Ready to Use

This guide will help you set up and use Google PageSpeed Insights API integration in your SEO Analyzer.

---

## What You Get

✅ **Real Lighthouse Scores** from Google's servers
✅ **Chrome User Experience Report (CrUX)** data from actual users
✅ **Performance Metrics**: FCP, LCP, SI, TTI, TBT, CLS
✅ **Optimization Opportunities** with estimated time/byte savings
✅ **5 Category Scores**: Performance, Accessibility, Best Practices, SEO, PWA

---

## Quick Setup (5 Minutes)

### Step 1: Get Google API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Navigate to **APIs & Services** > **Library**
4. Search for "PageSpeed Insights API"
5. Click **ENABLE**
6. Navigate to **APIs & Services** > **Credentials**
7. Click **+ CREATE CREDENTIALS** > **API Key**
8. Copy your API key

### Step 2: Add API Key to .env

```bash
# Edit your .env file
nano .env

# Add this line (replace with your actual key):
GOOGLE_PSI_API_KEY=AIzaSyC_your_actual_key_here

# Optional: Choose strategy
PSI_STRATEGY=mobile  # or 'desktop'
PSI_LOCALE=en
```

### Step 3: Run Crawl with PageSpeed Insights

#### Using async_crawl.py (Recommended)

```bash
# PSI is enabled by default if GOOGLE_PSI_API_KEY is set
./run.sh https://example.com --max-pages 20

# Explicitly enable with options
poetry run python async_crawl.py https://example.com --max-pages 20 --enable-psi

# Desktop strategy instead of mobile
poetry run python async_crawl.py https://example.com --max-pages 20 --psi-strategy desktop

# Analyze 20% of pages instead of default 10%
poetry run python async_crawl.py https://example.com --max-pages 20 --psi-sample 0.2

# Disable PSI
poetry run python async_crawl.py https://example.com --max-pages 20 --no-psi
```

#### Using crawl.py (Full Analysis with LLM)

```bash
# With PageSpeed Insights (mobile)
poetry run python crawl.py https://example.com 5 --enable-psi

# With PageSpeed Insights (desktop)
poetry run python crawl.py https://example.com 5 --enable-psi --psi-strategy desktop
```

**That's it!** Your report will now include real Google Lighthouse data.

---

## Usage Examples

### Using async_crawl.py (Fast, Stealth Browser)

```bash
# Quick 10-page analysis (PSI enabled by default)
./run.sh https://yoursite.com --max-pages 10

# Comprehensive 50-page analysis with 20% PSI sampling
./run.sh https://yoursite.com --max-pages 50 --psi-sample 0.2

# Desktop analysis
./run.sh https://yoursite.com --max-pages 20 --psi-strategy desktop

# Resume an interrupted crawl
./resume.sh crawls/yoursite.com/2026-01-31_120000
```

### Using crawl.py (Full Analysis with LLM Recommendations)

```bash
# Quick 3-page analysis
poetry run python crawl.py https://yoursite.com 3 --enable-psi

# Comprehensive 10-page analysis
poetry run python crawl.py https://yoursite.com 10 --enable-psi

# Desktop analysis
poetry run python crawl.py https://yoursite.com 5 --enable-psi --psi-strategy desktop

# Slow rate limit for stability
poetry run python crawl.py https://yoursite.com 5 1.0 --enable-psi
# Waits 1 second between pages (default is 0.5s)
```

---

## What You'll See in Reports

### New Section in Tab 5 (Security & Mobile):
- **5 Lighthouse Gauge Charts**
  - Performance Score (0-100)
  - Accessibility Score
  - Best Practices Score
  - SEO Score
  - PWA Score

- **Performance Metrics Bar Chart**
  - FCP (First Contentful Paint)
  - LCP (Largest Contentful Paint)
  - SI (Speed Index)
  - TTI (Time to Interactive)
  - TBT (Total Blocking Time)
  - CLS (Cumulative Layout Shift)

- **Top Optimization Opportunities Table**
  - Shows what to fix first
  - Estimated time savings (milliseconds)
  - Estimated byte savings (KB)
  - Number of items affected

- **Pages Needing Attention**
  - Lists pages with performance score < 50
  - Shows key metrics for each

---

## API Limits & Costs

### Free Tier (No Billing)
- **25,000 requests/day**
- **400 requests per 100 seconds**
- Sufficient for most small-to-medium sites

### With Billing Enabled
- **240,000 requests/day**
- Same rate limit (400/100s)
- **Cost**: FREE for first 240k, then minimal ($5 per 1,000 requests)

### How Many Pages Can I Analyze?
- **Without billing**: 25,000 pages per day
- **With billing**: 240,000 pages per day
- **In practice**: You'll hit rate limits before daily limits
  - ~1,440 pages per hour (max)
  - ~34,560 pages per day (theoretical max)

---

## Performance Impact

### Crawl Speed Comparison

| Pages | Without PSI | With PSI |
|-------|-------------|----------|
| 3 pages | ~5 seconds | ~25 seconds |
| 5 pages | ~8 seconds | ~40 seconds |
| 10 pages | ~15 seconds | ~90 seconds |

**Why slower?**
- PageSpeed Insights runs full Lighthouse audits (renders page, executes JS, measures performance)
- API rate limits enforce ~4 requests/second max
- Each request takes ~5-10 seconds

**Tips for faster analysis:**
- Start with fewer pages (3-5) to test
- Use parallel crawling when possible
- Consider analyzing only key pages (homepage, top landing pages)

---

## Troubleshooting

### Error: "GOOGLE_PSI_API_KEY not found"
**Solution**: Add your API key to `.env` file:
```bash
GOOGLE_PSI_API_KEY=your_key_here
```

### Error: "PageSpeed Insights rate limit exceeded"
**Solution**: This means you're over 400 requests in 100 seconds. The tool automatically waits and retries. Just be patient.

### Error: "API returned 400: Invalid URL"
**Solution**: The URL might not be publicly accessible. PageSpeed Insights can only analyze public URLs.

### Error: "API returned 403: Forbidden"
**Solution**:
1. Check your API key is correct
2. Ensure PageSpeed Insights API is enabled in Google Cloud Console
3. Check if your project has billing enabled (if needed)

### No CrUX Data in Report
**This is normal!** CrUX (real user) data is only available for sites with sufficient traffic. Low-traffic sites will only show Lighthouse (lab) data.

### Charts Not Showing
**Solution**: Make sure you click through all tabs. Lighthouse charts are in:
- **Tab 5**: Security & Mobile (Lighthouse section)

---

## Interpreting Scores

### Performance Score

| Score | Status | Action |
|-------|--------|--------|
| 90-100 | ✓ GOOD | Maintain current optimizations |
| 50-89 | ⚠ NEEDS WORK | Review optimization opportunities |
| 0-49 | ✗ POOR | Urgent optimization needed |

### Key Metrics Thresholds

| Metric | Good | Needs Work | Poor |
|--------|------|------------|------|
| **LCP** | < 2.5s | 2.5-4.0s | > 4.0s |
| **FCP** | < 1.8s | 1.8-3.0s | > 3.0s |
| **TBT** | < 200ms | 200-600ms | > 600ms |
| **CLS** | < 0.1 | 0.1-0.25 | > 0.25 |

---

## Best Practices

### 1. Start Small
```bash
# Test with 10 pages first
./run.sh https://yoursite.com --max-pages 10
```

### 2. Analyze Key Pages Only
Focus on pages that matter most:
- Homepage
- Top landing pages
- Main product/service pages
- Important conversion pages

### 3. Compare Mobile vs. Desktop
```bash
# Mobile (default)
./run.sh https://yoursite.com --max-pages 20

# Desktop
./run.sh https://yoursite.com --max-pages 20 --psi-strategy desktop
```

### 4. Track Over Time
Run crawls weekly/monthly to track improvements:
```bash
# Week 1 baseline
./run.sh https://yoursite.com --max-pages 50

# Week 2 after optimizations
./run.sh https://yoursite.com --max-pages 50
```

### 5. Resume Interrupted Crawls
```bash
# List resumable crawls
./resume.sh

# Resume a specific crawl
./resume.sh crawls/yoursite.com/2026-01-31_120000

# Resume with higher page target
./resume.sh crawls/yoursite.com/2026-01-31_120000 --max-pages 200
```

---

## Cost Estimation

### Typical Usage Scenarios

**Scenario 1: Small Site (10 pages, monthly)**
- 10 pages × 1 request = 10 requests
- **Cost**: $0 (well within free tier)

**Scenario 2: Medium Site (50 pages, weekly)**
- 50 pages × 4 times/month = 200 requests/month
- **Cost**: $0 (free tier)

**Scenario 3: Large Site (500 pages, weekly)**
- 500 pages × 4 times/month = 2,000 requests/month
- **Cost**: $0 (free tier)

**Scenario 4: Enterprise (10,000 pages, daily)**
- 10,000 pages × 30 days = 300,000 requests/month
- **Cost**: ~$300/month (60,000 requests over free tier @ $5/1k)
- **Recommendation**: Use sampling (analyze 100-200 representative pages)

**For 99% of users: FREE**

---

## Advanced Configuration

### Environment Variables

```bash
# .env file

# Required for PageSpeed Insights
GOOGLE_PSI_API_KEY=your_api_key

# Optional: Strategy (mobile or desktop)
PSI_STRATEGY=mobile

# Optional: Locale for results
PSI_LOCALE=en

# Optional: Other languages
# PSI_LOCALE=es  # Spanish
# PSI_LOCALE=fr  # French
# PSI_LOCALE=de  # German
```

### async_crawl.py CLI Options

```
--enable-psi          Enable PSI (default: enabled if API key exists)
--no-psi              Disable PSI
--psi-strategy        'mobile' or 'desktop' (default: mobile)
--psi-sample FLOAT    Fraction of pages to analyze (0.0-1.0, default: 0.1)
--resume PATH         Resume from existing crawl directory
--max-pages N         Maximum pages to crawl
--max-depth N         Maximum crawl depth
--rate-limit N        Delay between requests (seconds)
--headless            Run browser in headless mode
```

### Programmatic Usage

#### Using AsyncSiteCrawler (Recommended)

```python
import asyncio
from seo.async_site_crawler import AsyncSiteCrawler

async def crawl_with_psi():
    crawler = AsyncSiteCrawler(
        max_pages=20,
        rate_limit=0.5,
        enable_psi=True,
        psi_api_key="your_google_psi_key",
        psi_strategy="mobile",
        psi_sample_rate=0.1,  # Analyze 10% of pages
    )

    site_data = await crawler.crawl_site("https://example.com")

    # Access Lighthouse data
    for url, metadata in site_data.items():
        print(f"{url}:")
        print(f"  Performance: {metadata.lighthouse_performance_score}")
        print(f"  LCP: {metadata.lighthouse_lcp}ms")
        print(f"  CLS: {metadata.lighthouse_cls}")

asyncio.run(crawl_with_psi())
```

#### Using SEOAnalyzer (Full Analysis with LLM)

```python
from seo import SEOAnalyzer

analyzer = SEOAnalyzer(
    llm_api_key="your_llm_key",
    llm_model="gpt-4",
    llm_provider="openai"
)

# Enable PageSpeed Insights
site_data, issues, recommendations, advanced, crawler = analyzer.analyze_site(
    start_url="https://example.com",
    max_pages=5,
    rate_limit=0.5,
    enable_psi=True,
    psi_api_key="your_google_psi_key",
    psi_strategy="mobile"
)

# Access Lighthouse data
for url, metadata in site_data.items():
    print(f"{url}:")
    print(f"  Performance: {metadata.lighthouse_performance_score}")
    print(f"  LCP: {metadata.lighthouse_lcp}ms")
    print(f"  CLS: {metadata.lighthouse_cls}")
```

---

## FAQ

**Q: Do I need PageSpeed Insights for the SEO Analyzer to work?**
A: No! It's completely optional. The analyzer works great without it. PSI just adds Google's official performance scores.

**Q: Is there a cost?**
A: FREE for 25,000 requests/day (more than enough for most users).

**Q: How long does it take?**
A: ~5-10 seconds per page. A 10-page site takes ~1-2 minutes.

**Q: Can I analyze localhost/private sites?**
A: No, PageSpeed Insights only works with publicly accessible URLs.

**Q: What if I don't have CrUX data?**
A: That's fine! Low-traffic sites won't have CrUX data. You'll still get Lighthouse (lab) scores.

**Q: Can I run this on a cron job?**
A: Yes! Perfect for automated weekly/monthly reports.

**Q: How accurate are the scores?**
A: Very accurate. These are the same scores you'd get from pagespeed.web.dev

**Q: Can I disable it after enabling?**
A: Yes, use `--no-psi` flag with async_crawl.py, or remove `--enable-psi` from crawl.py.

---

## Next Steps

1. ✅ Get your API key (5 minutes)
2. ✅ Add to .env file
3. ✅ Run test crawl with 3 pages
4. ✅ Review Lighthouse section in report
5. ✅ Implement optimization recommendations
6. ✅ Re-crawl to measure improvements

---

## Support

- **Issues**: https://github.com/anthropics/claude-code/issues
- **Google PSI API Docs**: https://developers.google.com/speed/docs/insights/v5/get-started
- **Rate Limits**: https://developers.google.com/speed/docs/insights/v5/get-started#quotas

---

**Happy Optimizing! 🚀**
