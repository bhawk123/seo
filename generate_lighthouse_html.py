#!/usr/bin/env python3
"""Generate HTML reports from Lighthouse JSON files."""

import json
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


def generate_html_reports(crawl_dir: Path):
    """Generate HTML reports for all Lighthouse JSON files."""
    lighthouse_dir = crawl_dir / "lighthouse"
    if not lighthouse_dir.exists():
        print(f"No lighthouse directory found in {crawl_dir}")
        return

    # Load template
    template_path = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_path)))
    template = env.get_template("lighthouse_report.html")

    json_files = list(lighthouse_dir.glob("*.json"))
    print(f"Generating HTML reports for {len(json_files)} pages...")

    for json_file in json_files:
        try:
            with open(json_file) as f:
                data = json.load(f)

            html = template.render(**data)
            html_file = json_file.with_suffix(".html")
            html_file.write_text(html, encoding="utf-8")
        except Exception as e:
            print(f"  Error processing {json_file.name}: {e}")

    print(f"✅ Generated {len(json_files)} HTML reports in {lighthouse_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_lighthouse_html.py <crawl_directory>")
        sys.exit(1)

    crawl_dir = Path(sys.argv[1])
    if not crawl_dir.exists():
        print(f"Error: Directory not found: {crawl_dir}")
        sys.exit(1)

    generate_html_reports(crawl_dir)
