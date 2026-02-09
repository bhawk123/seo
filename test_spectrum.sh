#!/bin/bash
# Test script for spectrum.com SEO analysis
# Crawls the site and runs PageSpeed Insights on all pages

set -e

# Configuration
START_URL="https://www.spectrum.com"
MAX_PAGES="${1:-50}"  # Default to 50 pages, can override with first argument
OUTPUT_DIR="crawls/spectrum.com"

echo "=============================================="
echo "Spectrum.com SEO Analysis"
echo "=============================================="
echo "Start URL: $START_URL"
echo "Max pages: $MAX_PAGES"
echo ""

# Activate virtual environment if not already active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Check for required API keys
if [ -z "$GOOGLE_PSI_API_KEY" ]; then
    if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
    fi
fi

if [ -z "$GOOGLE_PSI_API_KEY" ]; then
    echo "Warning: GOOGLE_PSI_API_KEY not set. PSI analysis will be skipped."
    echo "Add to .env: GOOGLE_PSI_API_KEY=your_key_here"
    echo ""
fi

# Run the crawl
echo "Starting crawl..."
python async_crawl.py "$START_URL" \
    --max-pages "$MAX_PAGES" \
    --enable-psi \
    --psi-sample 1.0 \
    --psi-strategy mobile \
    --rate-limit 1.0

# Find the latest crawl directory
LATEST_CRAWL=$(ls -td "$OUTPUT_DIR"/*/ 2>/dev/null | head -1)

if [ -z "$LATEST_CRAWL" ]; then
    echo "Error: No crawl directory found"
    exit 1
fi

echo ""
echo "=============================================="
echo "Crawl complete: $LATEST_CRAWL"
echo "=============================================="

# Check PSI coverage
PSI_COUNT=$(ls "$LATEST_CRAWL/lighthouse"/*.json 2>/dev/null | wc -l | tr -d ' ')
PAGE_COUNT=$(ls "$LATEST_CRAWL/pages"/*.json 2>/dev/null | wc -l | tr -d ' ')

echo "Pages crawled: $PAGE_COUNT"
echo "PSI analyses: $PSI_COUNT"

if [ "$PSI_COUNT" -lt "$PAGE_COUNT" ]; then
    MISSING=$((PAGE_COUNT - PSI_COUNT))
    echo ""
    echo "Warning: $MISSING pages missing PSI data"
    echo "Running backfill..."
    python backfill_psi.py "$LATEST_CRAWL"
fi

# Regenerate report to ensure latest data
echo ""
echo "Generating report..."
python regenerate_report.py "$LATEST_CRAWL"

echo ""
echo "=============================================="
echo "Analysis complete!"
echo "=============================================="
echo "Report: $LATEST_CRAWL/report.html"
echo ""
echo "To open the report:"
echo "  open $LATEST_CRAWL/report.html"
