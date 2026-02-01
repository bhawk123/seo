#!/bin/bash
URL=$1
MAX=$2
poetry run python async_crawl.py "${URL}" --max-pages "${MAX}"
