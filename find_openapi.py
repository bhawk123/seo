#!/usr/bin/env python3
"""
Find OpenAPI/Swagger endpoints on a target domain.

Probes common API documentation paths and reports which ones are accessible.

Usage:
    python find_openapi.py https://www.spectrum.com
    python find_openapi.py https://api.spectrum.com --timeout 10
"""

import argparse
import asyncio
import sys
from urllib.parse import urljoin, urlparse

import httpx

# Common OpenAPI/Swagger paths to probe
OPENAPI_PATHS = [
    # OpenAPI 3.x
    "/openapi.json",
    "/openapi.yaml",
    "/openapi.yml",
    "/openapi/v3/api-docs",
    "/v3/api-docs",
    "/api/openapi.json",
    "/api/openapi.yaml",

    # Swagger 2.x
    "/swagger.json",
    "/swagger.yaml",
    "/swagger.yml",
    "/swagger/v1/swagger.json",
    "/swagger/v2/swagger.json",

    # Swagger UI
    "/swagger",
    "/swagger/",
    "/swagger-ui",
    "/swagger-ui/",
    "/swagger-ui.html",
    "/swagger-ui/index.html",
    "/api/swagger-ui.html",
    "/api/swagger-ui/",

    # API docs paths
    "/api-docs",
    "/api-docs/",
    "/api-docs.json",
    "/apidocs",
    "/apidocs/",
    "/docs",
    "/docs/",
    "/api/docs",
    "/api/docs/",
    "/documentation",
    "/api/documentation",

    # Spring Boot Actuator / Springdoc
    "/v2/api-docs",
    "/v3/api-docs",
    "/v3/api-docs.yaml",
    "/actuator/swagger-ui",
    "/actuator/api-docs",

    # Redoc
    "/redoc",
    "/redoc/",
    "/api/redoc",

    # GraphQL
    "/graphql",
    "/graphiql",
    "/playground",
    "/api/graphql",

    # Versioned API docs
    "/api/v1/docs",
    "/api/v1/swagger.json",
    "/api/v1/openapi.json",
    "/api/v2/docs",
    "/api/v2/swagger.json",
    "/api/v2/openapi.json",
    "/api/v3/docs",

    # Other common patterns
    "/spec",
    "/spec.json",
    "/api/spec",
    "/api/spec.json",
    "/api.json",
    "/api.yaml",
    "/_swagger",
    "/_api-docs",
    "/developer",
    "/developer/docs",
    "/developers",
    "/developers/api",
]

# Subdomains to check
COMMON_API_SUBDOMAINS = [
    "api",
    "developer",
    "developers",
    "docs",
    "swagger",
    "gateway",
    "services",
]


async def check_url(client: httpx.AsyncClient, url: str) -> dict:
    """Check if a URL is accessible and looks like API docs."""
    try:
        response = await client.get(url, follow_redirects=True)

        content_type = response.headers.get("content-type", "").lower()
        content = response.text[:2000] if response.status_code == 200 else ""

        # Determine if it looks like API documentation
        is_json = "application/json" in content_type
        is_yaml = "yaml" in content_type or "yml" in content_type
        is_html = "text/html" in content_type

        looks_like_openapi = any(term in content.lower() for term in [
            "openapi", "swagger", "api-docs", "paths", "components",
            "definitions", "basepath", "info", "servers"
        ])

        looks_like_swagger_ui = any(term in content.lower() for term in [
            "swagger-ui", "swagger ui", "api documentation", "try it out"
        ])

        return {
            "url": url,
            "status": response.status_code,
            "content_type": content_type,
            "is_json": is_json,
            "is_yaml": is_yaml,
            "is_html": is_html,
            "looks_like_openapi": looks_like_openapi,
            "looks_like_swagger_ui": looks_like_swagger_ui,
            "final_url": str(response.url),
            "redirected": str(response.url) != url,
        }
    except httpx.TimeoutException:
        return {"url": url, "status": "timeout", "error": "Request timed out"}
    except httpx.ConnectError:
        return {"url": url, "status": "error", "error": "Connection failed"}
    except Exception as e:
        return {"url": url, "status": "error", "error": str(e)}


async def probe_domain(base_url: str, timeout: int = 5, check_subdomains: bool = True) -> list:
    """Probe a domain for OpenAPI/Swagger endpoints."""
    results = []
    urls_to_check = []

    parsed = urlparse(base_url)
    base_domain = parsed.netloc
    scheme = parsed.scheme or "https"

    # Add paths to main domain
    for path in OPENAPI_PATHS:
        urls_to_check.append(urljoin(f"{scheme}://{base_domain}", path))

    # Add subdomain variations
    if check_subdomains:
        # Extract root domain (e.g., spectrum.com from www.spectrum.com)
        parts = base_domain.split(".")
        if len(parts) >= 2:
            root_domain = ".".join(parts[-2:])

            for subdomain in COMMON_API_SUBDOMAINS:
                subdomain_url = f"{scheme}://{subdomain}.{root_domain}"
                # Check root of subdomain
                urls_to_check.append(subdomain_url)
                urls_to_check.append(subdomain_url + "/")
                # Check common paths on subdomain
                for path in OPENAPI_PATHS[:20]:  # Top 20 paths only for subdomains
                    urls_to_check.append(urljoin(subdomain_url, path))

    # Deduplicate
    urls_to_check = list(dict.fromkeys(urls_to_check))

    print(f"Probing {len(urls_to_check)} URLs...")
    print("-" * 60)

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        verify=False,  # Some API docs use self-signed certs
        headers={"User-Agent": "Mozilla/5.0 OpenAPI-Scanner/1.0"}
    ) as client:
        # Process in batches to avoid overwhelming the server
        batch_size = 10
        for i in range(0, len(urls_to_check), batch_size):
            batch = urls_to_check[i:i + batch_size]
            tasks = [check_url(client, url) for url in batch]
            batch_results = await asyncio.gather(*tasks)

            for result in batch_results:
                if result.get("status") == 200:
                    results.append(result)
                    # Print findings immediately
                    if result.get("looks_like_openapi") or result.get("looks_like_swagger_ui"):
                        print(f"[FOUND] {result['url']}")
                        if result.get("looks_like_openapi"):
                            print(f"        ^ Looks like OpenAPI spec")
                        if result.get("looks_like_swagger_ui"):
                            print(f"        ^ Looks like Swagger UI")
                    elif result.get("is_json") or result.get("is_yaml"):
                        print(f"[  OK ] {result['url']} ({result['content_type']})")

            # Small delay between batches
            await asyncio.sleep(0.2)

    return results


def print_results(results: list) -> None:
    """Print summary of results."""
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    # Categorize results
    openapi_specs = [r for r in results if r.get("looks_like_openapi") and (r.get("is_json") or r.get("is_yaml"))]
    swagger_uis = [r for r in results if r.get("looks_like_swagger_ui") and r.get("is_html")]
    other_docs = [r for r in results if r.get("status") == 200 and r not in openapi_specs and r not in swagger_uis]

    if openapi_specs:
        print("\nOpenAPI/Swagger Specifications Found:")
        for r in openapi_specs:
            print(f"  {r['url']}")
            print(f"    Content-Type: {r['content_type']}")

    if swagger_uis:
        print("\nSwagger UI / API Documentation Pages:")
        for r in swagger_uis:
            print(f"  {r['url']}")

    if other_docs:
        print(f"\nOther Accessible Endpoints ({len(other_docs)}):")
        for r in other_docs[:10]:  # Show first 10
            print(f"  {r['url']}")
        if len(other_docs) > 10:
            print(f"  ... and {len(other_docs) - 10} more")

    if not openapi_specs and not swagger_uis:
        print("\nNo OpenAPI/Swagger endpoints found.")
        print("The API documentation may be:")
        print("  - Behind authentication")
        print("  - On a different subdomain")
        print("  - Using non-standard paths")
        print("  - Not publicly accessible")

    print("\n" + "=" * 60)
    print(f"Total URLs checked: {len(results)} returned 200 OK")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Find OpenAPI/Swagger endpoints on a target domain"
    )
    parser.add_argument(
        "url",
        help="Target URL (e.g., https://www.spectrum.com)"
    )
    parser.add_argument(
        "--timeout", type=int, default=5,
        help="Request timeout in seconds (default: 5)"
    )
    parser.add_argument(
        "--no-subdomains", action="store_true",
        help="Don't check common API subdomains"
    )

    args = parser.parse_args()

    # Ensure URL has scheme
    url = args.url
    if not url.startswith("http"):
        url = "https://" + url

    print("=" * 60)
    print("OpenAPI/Swagger Endpoint Scanner")
    print("=" * 60)
    print(f"Target: {url}")
    print(f"Timeout: {args.timeout}s")
    print(f"Check subdomains: {not args.no_subdomains}")
    print()

    # Suppress SSL warnings
    import warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    results = asyncio.run(probe_domain(
        url,
        timeout=args.timeout,
        check_subdomains=not args.no_subdomains
    ))

    print_results(results)


if __name__ == "__main__":
    main()
