#!/bin/bash
# Run async crawler (alias for run.sh)

show_help() {
    echo "Run the SEO async crawler on a website"
    echo ""
    echo "Usage:"
    echo "  ./crawl.sh <site> [max_pages] [max_depth] [psi_sample] [max_concurrent]"
    echo "  ./crawl.sh <site> [options]"
    echo ""
    echo "Arguments:"
    echo "  site            Domain to crawl (without https://)"
    echo "  max_pages       Maximum pages to crawl (default: 5)"
    echo "  max_depth       Maximum crawl depth (default: 3)"
    echo "  psi_sample      PageSpeed Insights sample rate 0-1 (default: 1.0)"
    echo "  max_concurrent  Maximum concurrent requests (default: 1)"
    echo ""
    echo "Options (flag style):"
    echo "  --max-pages N       Maximum pages to crawl"
    echo "  --max-depth N       Maximum crawl depth"
    echo "  --psi-sample N      PageSpeed Insights sample rate"
    echo "  --max-concurrent N  Maximum concurrent requests"
    echo "  --headless          Run browser in headless mode"
    echo "  --ignore-robots     Ignore robots.txt restrictions"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./crawl.sh www.example.com                        # Crawl with defaults"
    echo "  ./crawl.sh www.example.com 10 3 0.2 2             # Positional args"
    echo "  ./crawl.sh www.example.com --max-pages 10         # Flag style"
    echo "  ./crawl.sh www.example.com --max-pages 50 --max-concurrent 3"
    echo ""
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ] || [ -z "$1" ]; then
    show_help
    exit 0
fi

SITE=$1
# Strip https:// or http:// if provided
SITE="${SITE#https://}"
SITE="${SITE#http://}"
shift

# Check if remaining args look like flags (start with --)
if [[ "$1" == --* ]] || [[ -z "$1" ]]; then
    # Pass through as flags
    poetry run python async_crawl.py "https://${SITE}" "$@"
else
    # Positional args: max_pages, max_depth, psi_sample, max_concurrent
    MAX=${1:-5}
    DEPTH=${2:-3}
    PSI=${3:-1.0}
    CONCURRENT=${4:-1}
    poetry run python async_crawl.py "https://${SITE}" --max-pages "${MAX}" --max-depth "${DEPTH}" --psi-sample "${PSI}" --max-concurrent "${CONCURRENT}"
fi
