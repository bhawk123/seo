#!/usr/bin/env python3
"""
Discover API endpoints by crawling a website and intercepting network requests.
Generates an OpenAPI/Swagger specification from discovered endpoints.

Usage:
    python discover_api.py https://www.spectrum.com
    python discover_api.py https://www.spectrum.com --max-pages 50 --output spectrum-api.json
"""

import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.async_api import async_playwright, Request, Response


class APIDiscoverer:
    """Discovers API endpoints by intercepting browser network requests."""

    def __init__(self, base_url: str, output_dir: Path = None):
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.output_dir = output_dir or Path("api_discovery")
        self.output_dir.mkdir(exist_ok=True)

        # Discovered endpoints
        self.endpoints: dict[str, dict] = {}  # path -> endpoint info
        self.requests_log: list[dict] = []

        # Patterns to identify API calls vs static resources
        self.api_patterns = [
            r'/api/',
            r'/v\d+/',
            r'/graphql',
            r'/rest/',
            r'/services/',
            r'/data/',
            r'/ajax/',
            r'/json',
            r'\.json$',
            r'/rpc/',
        ]

        self.static_extensions = {
            '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
            '.woff', '.woff2', '.ttf', '.eot', '.map', '.webp', '.mp4', '.webm'
        }

        # Track visited pages
        self.visited_urls: set[str] = set()
        self.pages_crawled = 0

    def is_api_request(self, url: str, resource_type: str) -> bool:
        """Determine if a request looks like an API call."""
        parsed = urlparse(url)
        path = parsed.path.lower()

        # Skip static resources
        if any(path.endswith(ext) for ext in self.static_extensions):
            return False

        # Check resource type
        if resource_type in ['xhr', 'fetch']:
            return True

        # Check URL patterns
        if any(re.search(pattern, path) for pattern in self.api_patterns):
            return True

        return False

    def normalize_path(self, path: str) -> tuple[str, dict]:
        """
        Normalize a path by replacing dynamic segments with parameters.
        Returns (normalized_path, path_parameters)
        """
        segments = path.strip('/').split('/')
        normalized = []
        params = {}

        for i, segment in enumerate(segments):
            # UUID pattern
            if re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', segment, re.I):
                param_name = f"id_{i}"
                normalized.append(f"{{{param_name}}}")
                params[param_name] = {"type": "string", "format": "uuid", "example": segment}
            # Numeric ID
            elif re.match(r'^\d+$', segment):
                param_name = f"id_{i}"
                normalized.append(f"{{{param_name}}}")
                params[param_name] = {"type": "integer", "example": int(segment)}
            # Hash/token pattern
            elif re.match(r'^[a-f0-9]{24,}$', segment, re.I):
                param_name = f"token_{i}"
                normalized.append(f"{{{param_name}}}")
                params[param_name] = {"type": "string", "example": segment}
            else:
                normalized.append(segment)

        return '/' + '/'.join(normalized), params

    def extract_schema_from_json(self, data: Any, max_depth: int = 3) -> dict:
        """Extract a JSON schema from sample data."""
        if max_depth <= 0:
            return {"type": "object"}

        if data is None:
            return {"type": "null"}
        elif isinstance(data, bool):
            return {"type": "boolean", "example": data}
        elif isinstance(data, int):
            return {"type": "integer", "example": data}
        elif isinstance(data, float):
            return {"type": "number", "example": data}
        elif isinstance(data, str):
            schema = {"type": "string"}
            if len(data) < 100:
                schema["example"] = data
            # Detect formats
            if re.match(r'^\d{4}-\d{2}-\d{2}', data):
                schema["format"] = "date-time" if 'T' in data else "date"
            elif re.match(r'^https?://', data):
                schema["format"] = "uri"
            elif re.match(r'^[^@]+@[^@]+\.[^@]+$', data):
                schema["format"] = "email"
            return schema
        elif isinstance(data, list):
            if len(data) > 0:
                return {
                    "type": "array",
                    "items": self.extract_schema_from_json(data[0], max_depth - 1)
                }
            return {"type": "array", "items": {}}
        elif isinstance(data, dict):
            properties = {}
            for key, value in list(data.items())[:20]:  # Limit properties
                properties[key] = self.extract_schema_from_json(value, max_depth - 1)
            return {
                "type": "object",
                "properties": properties
            }
        return {"type": "string"}

    async def handle_request(self, request: Request) -> None:
        """Handle intercepted request."""
        url = request.url
        resource_type = request.resource_type

        if not self.is_api_request(url, resource_type):
            return

        parsed = urlparse(url)
        method = request.method.upper()

        # Normalize the path
        normalized_path, path_params = self.normalize_path(parsed.path)

        # Create endpoint key
        endpoint_key = f"{method}:{normalized_path}"

        # Parse query parameters
        query_params = parse_qs(parsed.query)

        # Get request body if present
        request_body = None
        try:
            post_data = request.post_data
            if post_data:
                try:
                    request_body = json.loads(post_data)
                except:
                    request_body = post_data
        except:
            pass

        # Store request info
        request_info = {
            "url": url,
            "method": method,
            "path": parsed.path,
            "normalized_path": normalized_path,
            "path_params": path_params,
            "query_params": {k: v[0] if len(v) == 1 else v for k, v in query_params.items()},
            "request_body": request_body,
            "headers": dict(request.headers),
            "resource_type": resource_type,
            "timestamp": datetime.now().isoformat(),
        }

        self.requests_log.append(request_info)

        # Update endpoint info
        if endpoint_key not in self.endpoints:
            self.endpoints[endpoint_key] = {
                "method": method,
                "path": normalized_path,
                "original_paths": [],
                "path_parameters": path_params,
                "query_parameters": {},
                "request_bodies": [],
                "responses": [],
                "hosts": set(),
                "count": 0,
            }

        ep = self.endpoints[endpoint_key]
        ep["count"] += 1
        ep["hosts"].add(parsed.netloc)

        if parsed.path not in ep["original_paths"]:
            ep["original_paths"].append(parsed.path)

        # Merge query parameters
        for key, values in query_params.items():
            if key not in ep["query_parameters"]:
                ep["query_parameters"][key] = {"examples": []}
            for v in values:
                if v not in ep["query_parameters"][key]["examples"]:
                    ep["query_parameters"][key]["examples"].append(v)

        # Store request body sample
        if request_body and len(ep["request_bodies"]) < 3:
            ep["request_bodies"].append(request_body)

    async def handle_response(self, response: Response) -> None:
        """Handle intercepted response."""
        request = response.request
        url = request.url

        if not self.is_api_request(url, request.resource_type):
            return

        parsed = urlparse(url)
        method = request.method.upper()
        normalized_path, _ = self.normalize_path(parsed.path)
        endpoint_key = f"{method}:{normalized_path}"

        if endpoint_key not in self.endpoints:
            return

        # Get response info
        status = response.status
        content_type = response.headers.get("content-type", "")

        response_body = None
        if "json" in content_type.lower():
            try:
                response_body = await response.json()
            except:
                pass

        # Store response sample
        ep = self.endpoints[endpoint_key]
        if len(ep["responses"]) < 3:
            ep["responses"].append({
                "status": status,
                "content_type": content_type,
                "body_sample": response_body,
            })

    async def crawl_page(self, page, url: str) -> list[str]:
        """Crawl a single page and return discovered links."""
        if url in self.visited_urls:
            return []

        self.visited_urls.add(url)
        new_links = []

        try:
            print(f"  [{self.pages_crawled + 1}] {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            self.pages_crawled += 1

            # Wait a bit for dynamic content
            await asyncio.sleep(2)

            # Scroll to trigger lazy loading
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)

            # Extract links
            links = await page.evaluate("""
                () => Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(href => href.startsWith('http'))
            """)

            # Filter to same domain
            for link in links:
                parsed = urlparse(link)
                if parsed.netloc == self.base_domain and link not in self.visited_urls:
                    # Clean URL (remove fragments)
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if parsed.query:
                        clean_url += f"?{parsed.query}"
                    if clean_url not in self.visited_urls:
                        new_links.append(clean_url)

        except Exception as e:
            print(f"    Error: {str(e)[:50]}")

        return list(set(new_links))

    async def discover(self, max_pages: int = 30) -> dict:
        """
        Crawl the site and discover API endpoints.
        Returns OpenAPI specification.
        """
        print(f"\nDiscovering API endpoints on {self.base_url}")
        print(f"Max pages: {max_pages}")
        print("=" * 60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )

            page = await context.new_page()

            # Set up request/response interception
            page.on("request", lambda req: asyncio.create_task(self.handle_request(req)))
            page.on("response", lambda res: asyncio.create_task(self.handle_response(res)))

            # BFS crawl
            urls_to_visit = [self.base_url]

            while urls_to_visit and self.pages_crawled < max_pages:
                url = urls_to_visit.pop(0)
                new_links = await self.crawl_page(page, url)
                urls_to_visit.extend(new_links)

            await browser.close()

        print(f"\nCrawled {self.pages_crawled} pages")
        print(f"Discovered {len(self.endpoints)} unique API endpoints")
        print(f"Total API requests logged: {len(self.requests_log)}")

        return self.generate_openapi_spec()

    def generate_openapi_spec(self) -> dict:
        """Generate OpenAPI 3.0 specification from discovered endpoints."""
        paths = {}

        for endpoint_key, ep in self.endpoints.items():
            path = ep["path"]
            method = ep["method"].lower()

            if path not in paths:
                paths[path] = {}

            # Build operation object
            operation = {
                "summary": f"{ep['method']} {path}",
                "description": f"Discovered endpoint (called {ep['count']} times)",
                "tags": self._extract_tags(path),
                "responses": {},
            }

            # Add path parameters
            if ep["path_parameters"]:
                operation["parameters"] = []
                for name, schema in ep["path_parameters"].items():
                    operation["parameters"].append({
                        "name": name,
                        "in": "path",
                        "required": True,
                        "schema": schema,
                    })

            # Add query parameters
            for name, info in ep["query_parameters"].items():
                if "parameters" not in operation:
                    operation["parameters"] = []
                param = {
                    "name": name,
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                }
                if info["examples"]:
                    param["example"] = info["examples"][0]
                operation["parameters"].append(param)

            # Add request body
            if ep["request_bodies"]:
                sample = ep["request_bodies"][0]
                operation["requestBody"] = {
                    "content": {
                        "application/json": {
                            "schema": self.extract_schema_from_json(sample)
                        }
                    }
                }

            # Add responses
            response_statuses = set()
            for resp in ep["responses"]:
                status = str(resp["status"])
                if status not in response_statuses:
                    response_statuses.add(status)
                    response_obj = {"description": f"Response {status}"}
                    if resp["body_sample"]:
                        response_obj["content"] = {
                            "application/json": {
                                "schema": self.extract_schema_from_json(resp["body_sample"])
                            }
                        }
                    operation["responses"][status] = response_obj

            if not operation["responses"]:
                operation["responses"]["200"] = {"description": "Success"}

            paths[path][method] = operation

        # Build full spec
        spec = {
            "openapi": "3.0.3",
            "info": {
                "title": f"Discovered API - {self.base_domain}",
                "description": f"API specification reverse-engineered from {self.base_url}",
                "version": "1.0.0",
                "x-generated": datetime.now().isoformat(),
                "x-pages-crawled": self.pages_crawled,
                "x-endpoints-discovered": len(self.endpoints),
            },
            "servers": [
                {"url": f"https://{host}", "description": f"Discovered host"}
                for host in sorted(set().union(*[ep["hosts"] for ep in self.endpoints.values()]))
            ][:5],  # Limit to 5 servers
            "paths": dict(sorted(paths.items())),
            "tags": self._generate_tags(),
        }

        return spec

    def _extract_tags(self, path: str) -> list[str]:
        """Extract tags from path."""
        segments = path.strip('/').split('/')
        if segments and segments[0]:
            return [segments[0]]
        return ["default"]

    def _generate_tags(self) -> list[dict]:
        """Generate tag definitions."""
        tags = set()
        for ep in self.endpoints.values():
            for tag in self._extract_tags(ep["path"]):
                tags.add(tag)
        return [{"name": tag} for tag in sorted(tags)]

    def save_results(self, spec: dict) -> tuple[Path, Path, Path]:
        """Save the OpenAPI spec and raw request log."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save OpenAPI spec
        spec_file = self.output_dir / f"{self.base_domain}_{timestamp}_openapi.json"
        with open(spec_file, "w") as f:
            json.dump(spec, f, indent=2, default=str)

        # Save as YAML too
        yaml_file = self.output_dir / f"{self.base_domain}_{timestamp}_openapi.yaml"
        try:
            import yaml
            with open(yaml_file, "w") as f:
                yaml.dump(spec, f, default_flow_style=False, sort_keys=False)
        except ImportError:
            yaml_file = None

        # Save raw request log
        log_file = self.output_dir / f"{self.base_domain}_{timestamp}_requests.json"
        with open(log_file, "w") as f:
            json.dump(self.requests_log, f, indent=2, default=str)

        return spec_file, yaml_file, log_file


async def main():
    parser = argparse.ArgumentParser(
        description="Discover API endpoints by crawling a website"
    )
    parser.add_argument("url", help="Target URL to crawl")
    parser.add_argument(
        "--max-pages", type=int, default=30,
        help="Maximum pages to crawl (default: 30)"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("api_discovery"),
        help="Output directory for results"
    )

    args = parser.parse_args()

    discoverer = APIDiscoverer(args.url, args.output_dir)
    spec = await discoverer.discover(max_pages=args.max_pages)

    # Save results
    spec_file, yaml_file, log_file = discoverer.save_results(spec)

    print("\n" + "=" * 60)
    print("DISCOVERY COMPLETE")
    print("=" * 60)
    print(f"\nOpenAPI spec: {spec_file}")
    if yaml_file:
        print(f"YAML version: {yaml_file}")
    print(f"Request log:  {log_file}")

    # Print summary
    print(f"\nEndpoints discovered: {len(discoverer.endpoints)}")
    print("\nTop endpoints by call count:")
    sorted_endpoints = sorted(
        discoverer.endpoints.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )
    for key, ep in sorted_endpoints[:15]:
        print(f"  {ep['count']:3}x  {ep['method']:6} {ep['path']}")

    print(f"\nTo view the spec, you can use:")
    print(f"  - Swagger Editor: https://editor.swagger.io/")
    print(f"  - Swagger UI: paste the JSON into a local instance")


if __name__ == "__main__":
    asyncio.run(main())
