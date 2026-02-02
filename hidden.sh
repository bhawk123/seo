#!/bin/bash
# Run crawler with full URL (for hidden/non-indexed pages)

show_help() {
    echo "Run the SEO crawler with a full URL"
    echo ""
    echo "Usage:"
    echo "  ./hidden.sh <url> <max_pages>"
    echo ""
    echo "Arguments:"
    echo "  url         Full URL to crawl (including https://)"
    echo "  max_pages   Maximum pages to crawl"
    echo ""
    echo "Examples:"
    echo "  ./hidden.sh https://www.example.com/hidden-section 50"
    echo "  ./hidden.sh https://staging.example.com 100"
    echo ""
    echo "Note: Unlike run.sh, this accepts the full URL rather than just the domain."
    echo ""
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ] || [ -z "$1" ]; then
    show_help
    exit 0
fi

URL=$1
MAX=$2
poetry run python async_crawl.py "${URL}" --max-pages "${MAX}"
