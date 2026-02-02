#!/bin/bash
# Regenerate HTML report from crawl data

show_help() {
    echo "Regenerate HTML report from existing crawl data"
    echo ""
    echo "Usage:"
    echo "  ./report.sh <domain/timestamp>"
    echo "  ./report.sh <domain>/<timestamp>"
    echo ""
    echo "Arguments:"
    echo "  domain/timestamp    Path to crawl directory under crawls/"
    echo ""
    echo "Examples:"
    echo "  ./report.sh www.example.com/2026-01-31_120000"
    echo "  ./report.sh mysite.com/latest"
    echo ""
    echo "The crawl data must exist in crawls/<domain>/<timestamp>/"
    echo ""
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ] || [ -z "$1" ]; then
    show_help
    exit 0
fi

URL_DATE=$1
poetry run python regenerate_report.py crawls/"${URL_DATE}"
