#!/bin/bash
URL_DATE=$1
poetry run python regenerate_report.py crawls/"${URL_DATE}"
