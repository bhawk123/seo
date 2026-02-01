# SEO Analyzer

A Python-based website crawler and SEO evaluator that uses Large Language Models (LLMs) to provide intelligent SEO analysis and recommendations.

## Features

### Core Features
- **Single Page Analysis**: Analyze individual pages for SEO quality
- **Site Crawling**: Breadth-first site crawling that processes pages level by level (L1, L2, L3...)
- **Smart Crawling**: Tracks visited URLs to avoid duplicates and circular crawls
- **LLM-Powered Insights**: Uses OpenAI or Anthropic models for intelligent recommendations
- **Flexible Output**: JSON and text formats with file export support

### Advanced SEO Analysis
- **Content Quality Metrics**: Flesch Reading Ease scores, keyword density, content depth analysis
- **Security Analysis**: HTTPS validation, security headers, SSL checks
- **URL Structure Analysis**: Length, keywords, parameters, depth level, readability
- **Mobile SEO**: Viewport meta tags, responsive design indicators
- **International SEO**: Lang attributes, hreflang tags, charset validation
- **Social Media Meta**: Open Graph and Twitter Card extraction
- **Structured Data**: Schema.org markup detection and validation

### Technical SEO Detection
- Missing or duplicate titles
- Meta description issues (missing, too short, too long)
- H1 tag problems (missing or multiple)
- Images without alt text
- Slow loading pages (>3s)
- Thin content (<300 words)
- Missing canonical URLs
- Missing viewport meta tags
- Non-HTTPS pages
- Poor readability scores

## Installation

### Prerequisites

- Python 3.12 or higher
- Poetry package manager

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd seo
```

2. Install dependencies:
```bash
poetry install
```

3. Create a `.env` file from the example:
```bash
cp .env.example .env
```

4. Edit `.env` and add your LLM API key:
```env
LLM_API_KEY=your-api-key-here
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
```

For Anthropic Claude:
```env
LLM_API_KEY=sk-ant-your-key-here
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-sonnet-20240229
```

## Usage

### Command Line Interface

#### Single Page Analysis

Analyze a single URL:
```bash
poetry run seo-analyzer https://example.com
```

Analyze multiple URLs:
```bash
poetry run seo-analyzer https://example.com https://another-site.com
```

Specify LLM provider and model:
```bash
poetry run seo-analyzer https://example.com --provider openai --model gpt-4
```

Output as JSON:
```bash
poetry run seo-analyzer https://example.com --output json
```

Save results to file:
```bash
poetry run seo-analyzer https://example.com --output json --output-file results.json
```

#### Site Crawling (Full Site Analysis)

**Quick Start with `crawl.py` (Synchronous):**
```bash
# Crawl a site (uses .env for configuration)
python crawl.py https://example.com

# Customize parameters
python crawl.py https://example.com 100 1.0  # 100 pages, 1s rate limit
```

**⚡ NEW: Async Crawler (5-10x Faster!):**
```bash
# High-performance async crawling
python async_crawl.py https://example.com

# Customize: 100 pages, 10 concurrent requests
python async_crawl.py https://example.com 100 0.5

# Example performance:
# Sync:  50 pages in ~75 seconds
# Async: 50 pages in ~12 seconds  🚀
```

**📁 NEW: Timestamped Results:**
Each crawl automatically saves to its own directory:
```bash
python crawl.py https://example.com 25

# Results saved to:
# crawls/example.com/2025-11-23_143022/
# ├── metadata.json
# ├── technical_issues.json
# ├── recommendations.txt
# ├── summary.txt
# └── pages/*.json

# View latest results:
cd crawls/example.com/latest
cat summary.txt
```
See **DIRECTORY_STRUCTURE.md** for full details.

**Using the CLI:**

Crawl an entire site using breadth-first search:
```bash
poetry run seo-analyzer https://example.com --site-crawl
```

Customize crawl parameters:
```bash
# Crawl up to 100 pages with 1 second between requests
poetry run seo-analyzer https://example.com --site-crawl --max-pages 100 --rate-limit 1.0
```

Export site analysis to JSON:
```bash
poetry run seo-analyzer https://example.com --site-crawl --output json --output-file site-audit.json
```

**How Site Crawling Works:**
- Starts at the provided URL (L1)
- Extracts all internal links and queues them for L2
- Processes pages level by level (breadth-first)
- Tracks visited URLs to avoid duplicates and circular crawls
- Skips non-HTML files (PDFs, images, CSS, JS, etc.)
- Generates comprehensive technical SEO report
- Provides AI-powered recommendations for the entire site

### Python API

#### Single Page Analysis

```python
from seo import SEOAnalyzer, Config

# Option 1: Use configuration from .env file
config = Config.from_env()
analyzer = SEOAnalyzer(
    llm_api_key=config.llm_api_key,
    llm_model=config.llm_model,
    llm_provider=config.llm_provider
)

# Option 2: Specify credentials directly
analyzer = SEOAnalyzer(
    llm_api_key="your-api-key",
    llm_model="gpt-4",
    llm_provider="openai"
)

# Analyze a URL
crawl_result, seo_score = analyzer.analyze_url("https://example.com")

# Print results
print(f"Overall Score: {seo_score.overall_score}/100")
print(f"Recommendations: {seo_score.recommendations}")
```

#### Site Crawling

```python
from seo import SEOAnalyzer, Config

# Initialize analyzer
config = Config.from_env()
analyzer = SEOAnalyzer(
    llm_api_key=config.llm_api_key,
    llm_model=config.llm_model,
    llm_provider=config.llm_provider
)

# Crawl entire site
site_data, technical_issues, llm_recommendations = analyzer.analyze_site(
    start_url="https://example.com",
    max_pages=50,
    rate_limit=0.5
)

# Access crawl results
print(f"Crawled {len(site_data)} pages")

# Check technical issues
print(f"Missing titles: {len(technical_issues.missing_titles)}")
print(f"Duplicate titles: {len(technical_issues.duplicate_titles)}")
print(f"Slow pages: {len(technical_issues.slow_pages)}")

# View AI recommendations
print(llm_recommendations)

# Access individual page data
for url, page_metadata in site_data.items():
    print(f"{url}: {page_metadata.title} ({page_metadata.word_count} words)")
```

### Advanced Features

The SEO analyzer now includes advanced analysis modules:

```python
from seo import (
    ContentQualityAnalyzer,
    SecurityAnalyzer,
    URLStructureAnalyzer,
    MobileSEOAnalyzer,
    InternationalSEOAnalyzer
)

# Analyze content quality (readability, keyword density)
content_analyzer = ContentQualityAnalyzer()
quality_metrics = content_analyzer.analyze(url, page_text)
print(f"Readability Score: {quality_metrics.readability_score}/100")
print(f"Grade Level: {quality_metrics.readability_grade}")
print(f"Top Keywords: {quality_metrics.keyword_density}")

# Analyze security (HTTPS, security headers)
security_analyzer = SecurityAnalyzer()
security_analysis = security_analyzer.analyze(url, page_metadata)
print(f"Security Score: {security_analysis.security_score}/100")
print(f"Has HTTPS: {security_analysis.has_https}")

# Analyze URL structure
url_analyzer = URLStructureAnalyzer()
url_analysis = url_analyzer.analyze(url)
print(f"URL Length: {url_analysis.url_length}")
print(f"URL Issues: {url_analysis.issues}")

# Analyze mobile SEO
mobile_analyzer = MobileSEOAnalyzer()
mobile_analysis = mobile_analyzer.analyze(page_metadata)
print(f"Mobile Score: {mobile_analysis['mobile_score']}/100")

# Analyze international SEO
intl_analyzer = InternationalSEOAnalyzer()
intl_analysis = intl_analyzer.analyze(page_metadata)
print(f"Has Lang Attribute: {intl_analysis['has_lang_attribute']}")
print(f"Hreflang Count: {intl_analysis['hreflang_count']}")
```

**Advanced Metrics Tracked:**
- ✅ **Content Quality**: Flesch Reading Ease, keyword density, content depth
- ✅ **Security**: HTTPS, SSL, security headers, mixed content
- ✅ **URL Structure**: Length, keywords, parameters, depth, readability
- ✅ **Mobile SEO**: Viewport meta, responsive design indicators
- ✅ **International SEO**: Lang attributes, hreflang tags, charset
- ✅ **Social Media**: Open Graph, Twitter Card meta tags
- ✅ **Structured Data**: Schema.org markup validation

## Configuration

Configuration is managed through a `.env` file in the project root. Available settings:

- `LLM_API_KEY`: API key for LLM provider (required)
- `LLM_MODEL`: Model to use (default: gpt-4)
- `LLM_PROVIDER`: LLM provider - openai or anthropic (default: openai)
- `USER_AGENT`: Custom user agent for web crawling
- `TIMEOUT`: Request timeout in seconds (default: 30)
- `MAX_CONCURRENT_REQUESTS`: Max concurrent requests (default: 5)

See `.env.example` for a complete configuration template.

## Project Structure

```
seo/
├── src/
│   └── seo/
│       ├── __init__.py              # Package exports
│       ├── analyzer.py              # Main SEO analyzer
│       ├── site_crawler.py          # BFS site crawler
│       ├── crawler.py               # Single page crawler
│       ├── llm.py                   # LLM integration
│       ├── technical.py             # Technical SEO analyzer
│       ├── content_quality.py       # Content quality metrics
│       ├── advanced_analyzer.py     # Security, URL, Mobile, Intl SEO
│       ├── models.py                # Data models
│       ├── config.py                # Configuration management
│       └── cli.py                   # Command-line interface
├── tests/
│   ├── __init__.py
│   ├── test_analyzer.py
│   ├── test_crawler.py
│   └── test_llm.py
├── crawl.py             # Standalone site crawler script
├── example.py           # Single page analysis example
├── pyproject.toml       # Dependencies and configuration
├── .env.example         # Environment configuration template
└── README.md
```

## Development

### Running Tests

```bash
poetry run pytest
```

Run with coverage:
```bash
poetry run pytest --cov=seo --cov-report=html
```

### Code Quality

Format code:
```bash
poetry run black src/ tests/
```

Lint code:
```bash
poetry run ruff check src/ tests/
```

Type checking:
```bash
poetry run mypy src/
```

## SEO Analysis Components

The analyzer evaluates the following aspects:

1. **Title Optimization**: Title tag presence, length, and relevance
2. **Meta Description**: Description quality and keyword usage
3. **Content Quality**: Content structure, readability, and keyword optimization
4. **Technical SEO**: HTML structure, heading hierarchy, image alt text, internal linking

## LLM Providers

### OpenAI

Set in `.env`:
```env
LLM_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
```

Then run:
```bash
poetry run seo-analyzer https://example.com
```

### Anthropic (Claude)

Set in `.env`:
```env
LLM_API_KEY=sk-ant-...
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-sonnet-20240229
```

Then run:
```bash
poetry run seo-analyzer https://example.com
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
