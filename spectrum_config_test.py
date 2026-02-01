"""
Spectrum service configuration flow test.
Navigates through the config process to analyze pages.

WARNING: This script is for testing/analysis ONLY.
IT WILL NOT COMPLETE ANY ORDER OR CHECKOUT.
"""

import asyncio
import yaml
from pathlib import Path
from rebrowser_playwright.async_api import async_playwright

from seo.form_handler import FormHandler


# SAFETY: Pages that indicate order is being COMPLETED (stop here)
STOP_PAGES = [
    "order-confirmation",
    "order-complete",
    "order-success",
    "thank-you",
    "confirmation",
]


def load_addresses():
    """Load test addresses from address.yaml"""
    yaml_path = Path(__file__).parent / "address.yaml"
    with open(yaml_path) as f:
        return yaml.safe_load(f)


def is_safe_to_continue(url: str) -> bool:
    """Check if we should continue or stop for safety."""
    url_lower = url.lower()
    for stop_word in STOP_PAGES:
        if stop_word in url_lower:
            print(f"\n🛑 SAFETY STOP: Detected '{stop_word}' in URL")
            print(f"   URL: {url}")
            print(f"   Script will NOT proceed past this point.\n")
            return False
    return True


async def check_availability(page, address_data: dict):
    """Enter address, select from dropdown, and click Check availability."""

    address = address_data.get("address", "")
    unit = address_data.get("unit", "")
    zip_code = address_data.get("zip", "")
    city = address_data.get("city", "")

    full_address = f"{address}, {city}, {zip_code}" if city else f"{address}, {zip_code}"

    print(f"Entering address: {full_address}")

    # Find and fill address input
    # Try common selectors for address fields
    address_selectors = [
        'input[placeholder*="address" i]',
        'input[placeholder*="street" i]',
        'input[aria-label*="address" i]',
        'input[name*="address" i]',
        'input[id*="address" i]',
        '#address-input',
        '[data-testid="address-input"]',
    ]

    address_input = None
    for selector in address_selectors:
        try:
            address_input = await page.wait_for_selector(selector, timeout=3000)
            if address_input:
                print(f"  Found address input: {selector}")
                break
        except:
            continue

    if not address_input:
        print("  Could not find address input field")
        return False

    # Clear and type address
    await address_input.click()
    await address_input.fill("")
    await page.keyboard.type(full_address, delay=50)

    # Wait for dropdown suggestions
    await asyncio.sleep(1.5)

    # Try to find and click suggestion dropdown
    suggestion_selectors = [
        '[role="listbox"] [role="option"]',
        '.address-suggestions li',
        '.autocomplete-suggestions li',
        '[class*="suggestion"]',
        '[class*="dropdown"] li',
        '[class*="result"] li',
    ]

    suggestion = None
    for selector in suggestion_selectors:
        try:
            suggestions = await page.query_selector_all(selector)
            if suggestions:
                # Click the first matching suggestion
                suggestion = suggestions[0]
                print(f"  Found suggestions: {selector}")
                break
        except:
            continue

    if suggestion:
        await suggestion.click()
        print("  Selected address from dropdown")
        await asyncio.sleep(0.5)
    else:
        print("  No dropdown suggestions found, continuing anyway...")

    # Fill unit/apt if provided
    if unit:
        unit_selectors = [
            'input[placeholder*="apt" i]',
            'input[placeholder*="unit" i]',
            'input[name*="unit" i]',
            'input[name*="apt" i]',
            'input[id*="unit" i]',
            'input[id*="apt" i]',
        ]
        for selector in unit_selectors:
            try:
                unit_input = await page.query_selector(selector)
                if unit_input:
                    await unit_input.fill(unit)
                    print(f"  Filled unit: {unit}")
                    break
            except:
                continue

    # Click Check Availability button
    check_selectors = [
        'button:has-text("Check availability")',
        'button:has-text("Check Availability")',
        'button:has-text("Check address")',
        'button:has-text("Get started")',
        'button:has-text("See plans")',
        'button[type="submit"]',
        '[data-testid="check-availability"]',
    ]

    for selector in check_selectors:
        try:
            button = await page.query_selector(selector)
            if button:
                await button.click()
                print(f"  Clicked: {selector}")
                await asyncio.sleep(2)
                return True
        except:
            continue

    print("  Could not find Check Availability button")
    return False


async def navigate_config_flow(page, form_handler: FormHandler, max_steps: int = 10):
    """
    Navigate through configuration steps.
    STOPS before any checkout/order completion.

    - Selects first options in dropdowns
    - Clicks first selectable cards/plans
    - Fills forms with test data
    - Clicks continue buttons
    - NEVER submits payment or completes orders
    """
    steps_taken = 0

    while steps_taken < max_steps:
        current_url = page.url

        # SAFETY CHECK
        if not is_safe_to_continue(current_url):
            print("Stopping for safety - reached checkout/order page")
            break

        print(f"\nStep {steps_taken + 1}: {current_url}")

        # Wait for page to stabilize
        await asyncio.sleep(2)

        # 1. Handle any dropdowns - select first option
        dropdowns = await form_handler.select_all_first_options(page)
        if dropdowns:
            print(f"  Selected first option in {dropdowns} dropdown(s)")

        # 2. Click first selectable card/plan/product
        if await form_handler.click_first_selectable(page):
            print("  Selected first product/plan option")
            await asyncio.sleep(1)

        # 3. Analyze and fill any forms (skip payment fields)
        forms = await form_handler.find_and_analyze_forms(page)
        for analysis in forms:
            print(f"  Found form: {analysis.form_type} ({len(analysis.fields)} fields)")

            if analysis.has_payment_fields:
                print("  ⚠️  Payment form detected - filling with test card")
                # Fill non-payment fields first
                await form_handler.fill_form(page, analysis, skip_payment=True)
                # Fill payment with test card (will decline but continues flow)
                await form_handler.fill_payment_fields(page, analysis)
            else:
                await form_handler.fill_form(page, analysis, skip_payment=True)

        # 4. Try to click continue/next button
        clicked = await form_handler.find_and_click_continue(page)

        if not clicked:
            # Try more specific selectors
            extra_selectors = [
                'button:has-text("Get")',
                'button:has-text("Shop")',
                'button:has-text("View")',
                'button:has-text("See")',
                'a.btn:has-text("Continue")',
                '.continue-btn',
                '.next-btn',
            ]
            for selector in extra_selectors:
                try:
                    btn = await page.query_selector(selector)
                    if btn and await btn.is_visible():
                        text = await btn.text_content()
                        print(f"  Clicking: {text.strip() if text else selector}")
                        await btn.click()
                        clicked = True
                        break
                except:
                    continue

        if not clicked:
            print("  No more continue buttons found")
            break

        await asyncio.sleep(2)
        steps_taken += 1

        # Check URL changed - safety check again
        new_url = page.url
        if not is_safe_to_continue(new_url):
            break

    print(f"\nCompleted {steps_taken} configuration steps")
    return steps_taken


async def run_spectrum_test(address_type: str = "serviceable"):
    """
    Run the Spectrum configuration flow test.

    Args:
        address_type: "serviceable" for new service, "accounts" for existing
    """
    addresses = load_addresses()
    yaml_path = Path(__file__).parent / "address.yaml"

    if address_type == "serviceable":
        addr_list = addresses.get("serviceable", [])
    else:
        addr_list = addresses.get("accounts", [])

    if not addr_list:
        print(f"No addresses found for type: {address_type}")
        return

    address_data = addr_list[0]

    # Initialize form handler with address data
    form_handler = FormHandler(address_yaml_path=yaml_path)

    print("=" * 60)
    print("SPECTRUM CONFIGURATION FLOW TEST")
    print("=" * 60)
    print(f"Address type: {address_type}")
    print(f"Address: {address_data}")
    print("\n⚠️  SAFETY: This script will NOT complete any orders")
    print("⚠️  Payment fields will use test card: 4111 1111 1111 1111")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # Show browser for monitoring
            args=[
                "--disable-blink-features=AutomationControlled",
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        page = await context.new_page()

        try:
            # Navigate to Spectrum
            print("\nNavigating to spectrum.com...")
            await page.goto("https://www.spectrum.com", wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Check availability
            print("\nChecking address availability...")
            success = await check_availability(page, address_data)

            if success:
                # Navigate through config flow
                print("\nNavigating configuration flow...")
                steps = await navigate_config_flow(page, form_handler)

                # Take screenshot of final page
                screenshot_path = f"spectrum_config_step_{steps}.png"
                await page.screenshot(path=screenshot_path)
                print(f"\nScreenshot saved: {screenshot_path}")

            # Keep browser open for inspection
            print("\n" + "=" * 60)
            print("TEST COMPLETE - Browser left open for inspection")
            print("Press Ctrl+C to close")
            print("=" * 60)

            # Wait for manual inspection
            await asyncio.sleep(300)  # 5 minutes

        except KeyboardInterrupt:
            print("\nClosing browser...")
        finally:
            await browser.close()


if __name__ == "__main__":
    import sys

    addr_type = sys.argv[1] if len(sys.argv) > 1 else "serviceable"
    asyncio.run(run_spectrum_test(addr_type))
