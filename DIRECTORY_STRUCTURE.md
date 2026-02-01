# 📁 Output Directory Structure

**Yes!** Now each crawl automatically saves to its own timestamped directory.

---

## 🎯 What You Get

Every time you run a crawl, it creates:

```
crawls/
└── example.com/
    ├── 2025-11-23_143022/          ← First crawl
    │   ├── metadata.json
    │   ├── technical_issues.json
    │   ├── recommendations.txt
    │   ├── summary.txt
    │   └── pages/
    │       ├── example.com_index.json
    │       ├── example.com_about.json
    │       ├── example.com_services.json
    │       └── ...
    ├── 2025-11-23_150845/          ← Second crawl
    │   ├── metadata.json
    │   ├── technical_issues.json
    │   ├── recommendations.txt
    │   ├── summary.txt
    │   └── pages/
    │       └── ...
    ├── 2025-11-23_163412/          ← Third crawl
    │   └── ...
    └── latest -> 2025-11-23_163412  ← Symlink to latest
```

---

## 📄 File Contents

### 1. **metadata.json**
Overall crawl information:

```json
{
  "start_url": "https://example.com",
  "crawled_at": "2025-11-23T14:30:22",
  "total_pages": 25,
  "urls_crawled": [
    "https://example.com",
    "https://example.com/about",
    ...
  ],
  "stats": {
    "total_words": 31250,
    "total_images": 87,
    "avg_words_per_page": 1250
  }
}
```

### 2. **technical_issues.json**
All SEO issues found:

```json
{
  "missing_titles": [],
  "duplicate_titles": {
    "Home - Example": ["https://example.com", "https://example.com/"]
  },
  "missing_meta_descriptions": [
    "https://example.com/contact"
  ],
  "slow_pages": [
    {"url": "https://example.com/services", "load_time": 3.42}
  ],
  "thin_content": [
    {"url": "https://example.com/contact", "word_count": 187}
  ],
  "images_without_alt": [
    {"url": "https://example.com", "missing": 3, "total": 12}
  ]
}
```

### 3. **recommendations.txt**
AI-powered recommendations from LLM:

```
## Critical Issues (Priority 1)
1. Fix slow loading pages...
2. Add missing meta descriptions...

## Quick Wins (Priority 2)
3. Add alt text to images...
...

## 30-Day Action Plan
Week 1: Performance optimization...
Week 2: Content improvements...
```

### 4. **summary.txt**
Human-readable overview:

```
============================================================
SEO CRAWL SUMMARY
============================================================

Start URL: https://example.com
Crawled at: 2025-11-23 14:30:22
Total pages: 25

TECHNICAL ISSUES
------------------------------------------------------------
Missing titles: 0
Duplicate titles: 1
Missing meta descriptions: 2
Slow pages (>3s): 2
Thin content (<300w): 1

PAGES CRAWLED
------------------------------------------------------------
  1. https://example.com
  2. https://example.com/about
  ...
```

### 5. **pages/\*.json**
Individual page data:

```json
// pages/example.com_about.json
{
  "url": "https://example.com/about",
  "title": "About Us - Example Company",
  "description": "Learn about our company...",
  "h1_tags": ["About Example Company"],
  "h2_tags": ["Our Mission", "Our Team", "Our History"],
  "word_count": 856,
  "load_time": 0.38,
  "internal_links": 8,
  "external_links": 2,
  "total_images": 4,
  "images_without_alt": 1,
  "has_https": true,
  "viewport_meta": "width=device-width, initial-scale=1",
  "lang_attribute": "en",
  "charset": "utf-8",
  "schema_markup": [...],
  "open_graph": {...},
  "security_headers": {...}
}
```

---

## 🚀 Usage

### Running a Crawl

```bash
python crawl.py https://example.com 25
```

**Output:**
```
Starting site crawl...
[L1] Crawling (1/25): https://example.com
  ✓ Success - 1247 words, 15 internal links
...

✅ Results saved to: crawls/example.com/2025-11-23_143022
   View files: ls crawls/example.com/2025-11-23_143022

============================================================
CRAWL SUMMARY
============================================================
...
```

### Viewing Results

```bash
# View the latest crawl
cd crawls/example.com/latest

# Or specific timestamp
cd crawls/example.com/2025-11-23_143022

# View summary
cat summary.txt

# View recommendations
cat recommendations.txt

# View all issues
cat technical_issues.json | jq .

# View a specific page
cat pages/example.com_about.json | jq .
```

---

## 🔍 Finding Past Crawls

### List All Crawls for a Domain

```bash
ls -la crawls/example.com/
```

**Output:**
```
drwxr-xr-x  2025-11-23_143022/
drwxr-xr-x  2025-11-23_150845/
drwxr-xr-x  2025-11-23_163412/
lrwxr-xr-x  latest -> 2025-11-23_163412
```

### Access Latest Crawl

```bash
# Always points to most recent
cd crawls/example.com/latest
```

### Compare Two Crawls

```python
from seo.output_manager import OutputManager

mgr = OutputManager()

# Compare first and second crawl
comparison = mgr.compare_crawls(
    domain="example.com",
    crawl1="2025-11-23_143022",
    crawl2="2025-11-23_150845"
)

print(f"Pages added: {comparison['pages_diff']}")
print(f"New pages: {comparison['new_pages']}")
print(f"Issues improved: {comparison['issues_diff']}")
```

**Output:**
```python
{
  "crawl1": "2025-11-23_143022",
  "crawl2": "2025-11-23_150845",
  "pages_diff": 3,  # 3 more pages in second crawl
  "new_pages": [
    "https://example.com/new-page"
  ],
  "removed_pages": [],
  "issues_diff": {
    "missing_titles": 0,  # No change
    "missing_descriptions": -1,  # Fixed 1!
    "slow_pages": 1,  # 1 more slow page
    "thin_content": 0
  }
}
```

---

## 📊 Benefits

### Track Changes Over Time ⏰
```bash
# Crawl weekly
python crawl.py https://example.com 50

# Compare this week vs last week
python compare_crawls.py example.com \
    2025-11-16_120000 \
    2025-11-23_120000
```

### Never Lose Data 💾
- Each crawl is preserved
- Can go back and review any historical crawl
- Compare before/after changes

### Organized by Domain 📁
```
crawls/
├── example.com/
│   ├── 2025-11-23_143022/
│   └── 2025-11-23_150845/
├── mysite.com/
│   ├── 2025-11-22_091234/
│   └── 2025-11-23_091234/
└── competitor.com/
    └── 2025-11-23_100000/
```

### Easy Automation 🤖
```bash
#!/bin/bash
# daily_seo_check.sh

python crawl.py https://example.com 50
python crawl.py https://competitor.com 50

# Results automatically saved with timestamp!
```

---

## 🔧 Configuration

### Change Output Directory

```python
from seo.output_manager import OutputManager

# Use custom directory
mgr = OutputManager(base_output_dir="my_crawls")

# Now saves to:
# my_crawls/example.com/2025-11-23_143022/
```

### Programmatic Access

```python
from seo.output_manager import OutputManager

mgr = OutputManager()

# Get all previous crawls for a domain
crawls = mgr.get_previous_crawls("example.com")

for crawl_dir in crawls:
    print(f"Crawl: {crawl_dir.name}")

    # Load the data
    metadata = mgr._load_json(crawl_dir / "metadata.json")
    print(f"  Pages: {metadata['total_pages']}")
    print(f"  Date: {metadata['crawled_at']}")
```

---

## 📈 Use Cases

### 1. **SEO Monitoring**
Crawl weekly, track improvements:
```bash
# Week 1
python crawl.py https://example.com 50

# Week 2 (after SEO improvements)
python crawl.py https://example.com 50

# Compare
ls crawls/example.com/
# See before/after in different directories
```

### 2. **Client Reporting**
```bash
# Before optimization
python crawl.py https://client-site.com 100

# After optimization (2 weeks later)
python crawl.py https://client-site.com 100

# Send both reports:
tar -czf client-report.tar.gz crawls/client-site.com/
```

### 3. **A/B Testing**
```bash
# Test version A
python crawl.py https://staging.example.com 50

# Test version B
python crawl.py https://staging-b.example.com 50

# Compare technical SEO between versions
```

### 4. **Regression Detection**
```bash
# After deploying changes
python crawl.py https://example.com 50

# Check if anything broke:
# - More slow pages?
# - New missing titles?
# - Broken links?
```

---

## 🎯 Quick Reference

| Task | Command |
|------|---------|
| Run crawl | `python crawl.py URL` |
| View latest | `cd crawls/DOMAIN/latest` |
| List all crawls | `ls crawls/DOMAIN/` |
| View summary | `cat crawls/DOMAIN/latest/summary.txt` |
| View issues | `cat crawls/DOMAIN/latest/technical_issues.json` |
| View page data | `cat crawls/DOMAIN/latest/pages/*.json` |
| Compare crawls | Use `OutputManager.compare_crawls()` |

---

## 🔐 .gitignore

Add to your `.gitignore`:
```
# Crawl results (can be large)
crawls/
```

Or keep them for version control:
```
# Keep crawl results but ignore large page files
crawls/*/pages/
```

---

**Try it now:**
```bash
python crawl.py https://example.com 10
ls crawls/example.com/
cd crawls/example.com/latest
cat summary.txt
```

**You'll see organized, timestamped results!** 📊
