#!/bin/bash
# Resume an interrupted crawl
#
# Usage:
#   ./resume.sh                          # List all resumable crawls
#   ./resume.sh <path>                   # Resume from full path
#   ./resume.sh <domain> <timestamp>     # Resume from domain/timestamp
#   ./resume.sh <path> --max-pages 500   # Resume with additional options

set -e

CRAWLS_DIR="crawls"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_help() {
    echo "Resume an interrupted SEO crawl"
    echo ""
    echo "Usage:"
    echo "  ./resume.sh                              List all resumable (paused) crawls"
    echo "  ./resume.sh <path>                       Resume from full path to crawl directory"
    echo "  ./resume.sh <domain> <timestamp>         Resume using domain and timestamp"
    echo "  ./resume.sh <path> [options]             Resume with additional options"
    echo ""
    echo "Options (passed to async_crawl.py):"
    echo "  --max-pages N      Set new max pages target"
    echo "  --max-depth N      Set max crawl depth"
    echo "  --rate-limit N     Set rate limit between requests"
    echo "  --headless         Run in headless mode"
    echo ""
    echo "Examples:"
    echo "  ./resume.sh                                              # List paused crawls"
    echo "  ./resume.sh crawls/www.example.com/2026-01-31_120000     # Resume full path"
    echo "  ./resume.sh www.example.com 2026-01-31_120000            # Resume by parts"
    echo "  ./resume.sh www.example.com latest                       # Resume latest for domain"
    echo "  ./resume.sh crawls/www.example.com/2026-01-31_120000 --max-pages 500"
    echo ""
}

list_resumable_crawls() {
    echo -e "${BLUE}Scanning for resumable crawls...${NC}"
    echo ""

    found=0
    for domain_dir in "$CRAWLS_DIR"/*/; do
        if [ -d "$domain_dir" ]; then
            domain=$(basename "$domain_dir")
            for crawl_dir in "$domain_dir"*/; do
                if [ -d "$crawl_dir" ] && [ "$(basename "$crawl_dir")" != "latest" ]; then
                    state_file="$crawl_dir/crawl_state.json"
                    if [ -f "$state_file" ]; then
                        status=$(grep -o '"status": *"[^"]*"' "$state_file" 2>/dev/null | cut -d'"' -f4)
                        pages=$(grep -o '"pages_crawled": *[0-9]*' "$state_file" 2>/dev/null | grep -o '[0-9]*')
                        max_pages=$(grep -o '"max_pages": *[0-9]*' "$state_file" 2>/dev/null | grep -o '[0-9]*')

                        if [ "$status" = "paused" ]; then
                            found=$((found + 1))
                            timestamp=$(basename "$crawl_dir")
                            echo -e "${YELLOW}[$found]${NC} ${GREEN}$domain${NC} / $timestamp"
                            echo -e "    Status: ${YELLOW}paused${NC} ($pages/$max_pages pages)"
                            echo -e "    Resume: ./resume.sh ${crawl_dir%/}"
                            echo ""
                        elif [ "$status" = "running" ]; then
                            found=$((found + 1))
                            timestamp=$(basename "$crawl_dir")
                            echo -e "${YELLOW}[$found]${NC} ${GREEN}$domain${NC} / $timestamp"
                            echo -e "    Status: ${BLUE}running${NC} (may have crashed) ($pages/$max_pages pages)"
                            echo -e "    Resume: ./resume.sh ${crawl_dir%/}"
                            echo ""
                        fi
                    fi
                fi
            done
        fi
    done

    if [ $found -eq 0 ]; then
        echo -e "${YELLOW}No resumable crawls found.${NC}"
        echo "Start a new crawl with: ./run.sh <url> --max-pages N"
    else
        echo -e "Found ${GREEN}$found${NC} resumable crawl(s)."
    fi
}

find_latest_for_domain() {
    local domain=$1
    local domain_dir="$CRAWLS_DIR/$domain"

    if [ ! -d "$domain_dir" ]; then
        echo ""
        return
    fi

    # Find the latest timestamp directory
    latest=$(ls -1 "$domain_dir" 2>/dev/null | grep -v "latest" | sort -r | head -1)
    if [ -n "$latest" ]; then
        echo "$domain_dir/$latest"
    fi
}

# Show help if requested
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_help
    exit 0
fi

# No arguments - list resumable crawls
if [ $# -eq 0 ]; then
    list_resumable_crawls
    exit 0
fi

# Determine the crawl path
CRAWL_PATH=""
EXTRA_ARGS=""

if [ -d "$1" ]; then
    # First arg is a full path
    CRAWL_PATH="$1"
    shift
    EXTRA_ARGS="$@"
elif [ -d "$CRAWLS_DIR/$1" ]; then
    # First arg is a domain
    if [ "$2" = "latest" ]; then
        CRAWL_PATH=$(find_latest_for_domain "$1")
        shift 2
        EXTRA_ARGS="$@"
    elif [ -n "$2" ] && [ -d "$CRAWLS_DIR/$1/$2" ]; then
        # Second arg is a timestamp
        CRAWL_PATH="$CRAWLS_DIR/$1/$2"
        shift 2
        EXTRA_ARGS="$@"
    else
        # Just domain, find latest
        CRAWL_PATH=$(find_latest_for_domain "$1")
        shift
        EXTRA_ARGS="$@"
    fi
else
    echo -e "${RED}Error: Could not find crawl directory${NC}"
    echo "  Tried: $1"
    echo "  Tried: $CRAWLS_DIR/$1"
    echo ""
    echo "Run ./resume.sh without arguments to list available crawls."
    exit 1
fi

if [ -z "$CRAWL_PATH" ] || [ ! -d "$CRAWL_PATH" ]; then
    echo -e "${RED}Error: Crawl directory not found: $CRAWL_PATH${NC}"
    exit 1
fi

# Check for state file
STATE_FILE="$CRAWL_PATH/crawl_state.json"
if [ ! -f "$STATE_FILE" ]; then
    echo -e "${RED}Error: No crawl_state.json found in $CRAWL_PATH${NC}"
    echo "This crawl cannot be resumed (no state file)."
    exit 1
fi

# Show status
status=$(grep -o '"status": *"[^"]*"' "$STATE_FILE" 2>/dev/null | cut -d'"' -f4)
pages=$(grep -o '"pages_crawled": *[0-9]*' "$STATE_FILE" 2>/dev/null | grep -o '[0-9]*')

if [ "$status" = "completed" ]; then
    echo -e "${YELLOW}Warning: This crawl is already completed ($pages pages).${NC}"
    echo "Start a new crawl instead with: ./run.sh <url>"
    exit 0
fi

echo -e "${GREEN}Resuming crawl from:${NC} $CRAWL_PATH"
echo -e "${GREEN}Pages already crawled:${NC} $pages"
if [ -n "$EXTRA_ARGS" ]; then
    echo -e "${GREEN}Extra options:${NC} $EXTRA_ARGS"
fi
echo ""

# Run the resume command
poetry run python async_crawl.py --resume "$CRAWL_PATH" $EXTRA_ARGS
