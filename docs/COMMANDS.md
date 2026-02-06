# SEO Crawler Commands

## Quick Start

```bash
# Basic crawl (fast, no extras)
poetry run python async_crawl.py https://example.com --max-pages 3 --no-psi --no-llm --headless --no-open

# Full crawl with PSI + AI recommendations
poetry run python async_crawl.py https://example.com --max-pages 10 --max-depth 5 --headless
```

## Crawl Options

| Flag | Description | Default |
|------|-------------|---------|
| `--max-pages N` | Limit number of pages | 50 |
| `--max-depth N` | Limit crawl depth | unlimited |
| `--headless` | Run browser headless | visible |
| `--no-psi` | Skip PageSpeed Insights | enabled |
| `--no-llm` | Skip AI recommendations | enabled |
| `--no-open` | Don't open report after | opens |
| `--resume PATH` | Resume interrupted crawl | - |
| `--rate-limit N` | Seconds between requests | 0.5 |
| `--max-concurrent N` | Parallel browser pages | 1 |
| `--psi-strategy` | `mobile` or `desktop` | mobile |
| `--psi-sample N` | Fraction of pages for PSI (0.0-1.0) | 1.0 |

## Examples

```bash
# Minimal test crawl
poetry run python async_crawl.py https://example.com --max-pages 3 --no-psi --no-llm --headless --no-open

# Production crawl (10 pages, full analysis)
poetry run python async_crawl.py https://example.com --max-pages 10 --max-depth 5 --headless

# Large site (50 pages, sample PSI)
poetry run python async_crawl.py https://example.com --max-pages 50 --psi-sample 0.2 --headless

# Resume interrupted crawl
poetry run python async_crawl.py --resume crawls/example.com/2026-02-03_170015
```

## Report Management

```bash
# Regenerate report from existing crawl data
poetry run python regenerate_report.py crawls/example.com/2026-02-03_170015

# Open latest report for a domain
open crawls/example.com/latest/report.html

# List all crawls for a domain
ls -la crawls/example.com/
```

## Testing

```bash
# Run all tests
poetry run pytest tests/ --ignore=tests/test_mcp_client.py -v

# Run only e2e tests
poetry run pytest tests/test_e2e.py -v

# Quick test (no verbose)
poetry run pytest tests/ --ignore=tests/test_mcp_client.py -q
```

## Output Structure

```
crawls/
└── example.com/
    ├── 2026-02-03_170015/
    │   ├── report.html          # Main HTML report
    │   ├── metadata.json        # Crawl metadata
    │   ├── technical_issues.json
    │   ├── recommendations.txt  # LLM recommendations
    │   ├── advanced_analysis.json
    │   ├── summary.txt
    │   ├── pages/               # Individual page data
    │   └── lighthouse/          # PSI reports per page
    └── latest -> 2026-02-03_170015
```

## Environment Variables

Required in `.env`:
```
GOOGLE_PSI_API_KEY=your_key    # For PageSpeed Insights
LLM_API_KEY=your_key           # For AI recommendations (Anthropic)
```

Optional:
```
LLM_PROVIDER=anthropic         # or openai
LLM_MODEL=claude-sonnet-4-20250514
```
