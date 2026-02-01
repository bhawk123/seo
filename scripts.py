"""
Post-install script for setting up browser dependencies.

This script is triggered after installation to automatically download
the Chromium browser required by Playwright for browser-based crawling.
"""
import subprocess
import sys


def postinstall():
    """
    Run playwright install to download browser binaries.

    This function is called automatically after `poetry install -E browser`.
    It checks if Playwright is installed and, if so, downloads Chromium.
    """
    print("Checking for browser installation...")

    # Check if playwright is installed
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Browser extras not installed. Skipping browser setup.\n"
            "To install, run: poetry install -E browser"
        )
        return

    # Playwright is installed, download Chromium
    print("Running 'playwright install chromium'...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            text=True
        )
        if result.stdout:
            print(result.stdout)
        print("Chromium browser installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing Chromium browser for Playwright: {e}", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        print(
            "Please run the following command manually:\n"
            "  poetry run playwright install chromium",
            file=sys.stderr
        )
    except FileNotFoundError as e:
        print(f"Error: Could not find Python executable: {e}", file=sys.stderr)
        print(
            "Please run the following command manually:\n"
            "  poetry run playwright install chromium",
            file=sys.stderr
        )


if __name__ == "__main__":
    postinstall()
