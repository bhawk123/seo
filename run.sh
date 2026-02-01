#!/bin/bash
# Run async crawler
#
# Usage:
#   ./run.sh <site> [max_pages] [max_depth] [psi_sample] [max_concurrent]
#   ./run.sh www.example.com 10 3 0.2 2
#
# Or pass flags directly:
#   ./run.sh www.example.com --max-pages 10 --max-concurrent 2

SITE=$1
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
