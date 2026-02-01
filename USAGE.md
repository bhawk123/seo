# SEO Analyzer Usage Guide

## Command Syntax

### Option 1: Using the CLI (seo-analyzer)

**Single page analysis:**
```bash
poetry run seo-analyzer https://example.com/page
```

**Full site crawl:**
```bash
poetry run seo-analyzer --site-crawl --max-pages 100 https://example.com
```

### Option 2: Using the Python scripts directly

**Site crawl (synchronous):**
```bash
poetry run python crawl.py <url> [max_pages] [rate_limit]
```
Example:
```bash
poetry run python crawl.py https://pinsandaces.com 100 0.5
```

**Site crawl (asynchronous - faster):**
```bash
poetry run python async_crawl.py <url> [max_pages] [rate_limit]
```
Example:
```bash
poetry run python async_crawl.py https://pinsandaces.com 100 0.5
```

## Common Options

| Option | Description | Default |
|--------|-------------|---------|
| `--max-pages N` | Maximum pages to crawl | 50 |
| `--rate-limit N` | Seconds between requests | 1.0 |
| `--provider {openai,anthropic}` | LLM provider | anthropic |
| `--model MODEL` | LLM model name | claude-sonnet-4-5 |
| `--output {text,json}` | Output format | text |
| `--output-file FILE` | Save to file | stdout |

## Examples

**Crawl 100 pages with 0.5s rate limit:**
```bash
poetry run seo-analyzer --site-crawl --max-pages 100 --rate-limit 0.5 https://pinsandaces.com
```

**Use OpenAI instead of Anthropic:**
```bash
poetry run seo-analyzer --site-crawl --provider openai --model gpt-4 https://example.com
```

**Save JSON output:**
```bash
poetry run seo-analyzer --site-crawl --output json --output-file report.json https://example.com
```

## Output Location

Reports are saved to:
```
crawls/{domain}/{timestamp}/
├── report.html              # Main HTML report
├── metadata.json           # Crawl metadata
├── technical_issues.json   # Technical SEO issues
└── advanced_analysis.json  # Advanced metrics
```

Latest report symlink:
```
crawls/{domain}/latest/
```

## Environment Variables

Set these in `.env` file:

```env
LLM_API_KEY=your-api-key-here
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
USER_AGENT=SEO-Analyzer-Bot/1.0
TIMEOUT=30
MAX_CONCURRENT_REQUESTS=10
LOG_LEVEL=INFO
```
