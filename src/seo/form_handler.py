"""
Form detection, analysis, and auto-fill for SEO crawling.
Identifies form fields and fills with rational test values.

SAFETY: Avoids submitting payment forms when possible.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import yaml

try:
    from faker import Faker
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False

logger = logging.getLogger(__name__)


import random as _random

# Common email providers for realistic fake emails
EMAIL_PROVIDERS = [
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "icloud.com",
    "aol.com",
    "protonmail.com",
    "mail.com",
]


def generate_fake_email(fake, first: str, last: str) -> str:
    """
    Generate a realistic fake email using common providers.

    Args:
        fake: Faker instance
        first: First name
        last: Last name

    Returns:
        Fake email address with common provider domain
    """
    provider = _random.choice(EMAIL_PROVIDERS)

    # Various email formats people actually use
    formats = [
        f"{first.lower()}.{last.lower()}",           # john.smith
        f"{first.lower()}{last.lower()}",            # johnsmith
        f"{first[0].lower()}{last.lower()}",         # jsmith
        f"{first.lower()}{last[0].lower()}",         # johns
        f"{first.lower()}.{last.lower()}{_random.randint(1, 99)}",  # john.smith42
        f"{first.lower()}{_random.randint(1, 999)}", # john123
        f"{last.lower()}.{first.lower()}",           # smith.john
    ]

    username = _random.choice(formats)
    return f"{username}@{provider}"


def generate_random_test_data(locale: str = "en_US") -> Dict[str, str]:
    """
    Generate randomized test data using Faker.

    Args:
        locale: Faker locale (default: en_US)

    Returns:
        Dict with randomized test values
    """
    if not FAKER_AVAILABLE:
        logger.warning("Faker not installed, using static test data")
        return TEST_DATA.copy()

    fake = Faker(locale)

    first = fake.first_name()
    last = fake.last_name()

    return {
        # Personal info
        "first_name": first,
        "last_name": last,
        "full_name": f"{first} {last}",
        "email": generate_fake_email(fake, first, last),
        "phone": fake.numerify("##########"),
        "phone_formatted": fake.phone_number(),

        # Address
        "address": fake.street_address(),
        "address_line1": fake.street_address(),
        "address_line2": "",
        "unit": "",
        "apt": "",
        "city": fake.city(),
        "state": fake.state_abbr(),
        "state_full": fake.state(),
        "zip": fake.zipcode(),
        "zip_full": fake.zipcode_plus4(),
        "country": "United States",

        # Account
        "username": fake.user_name(),
        "password": fake.password(length=12, special_chars=True),

        # Payment (test card - will decline but validates format)
        "cc_number": "4111111111111111",
        "cc_exp": "01/29",
        "cc_exp_month": "01",
        "cc_exp_year": "29",
        "cc_exp_year_full": "2029",
        "cc_cvv": "123",
        "cc_name": f"{first} {last}",

        # Other
        "company": fake.company(),
        "website": fake.url(),
        "message": fake.paragraph(nb_sentences=2),
        "date": fake.date(pattern="%m/%d/%Y"),
        "ssn_last4": fake.numerify("####"),
    }


@dataclass
class FormField:
    """Represents a detected form field."""
    selector: str
    field_type: str  # text, email, tel, password, select, textarea, checkbox, radio
    name: str
    id: str
    placeholder: str
    label: str
    required: bool
    classification: str  # first_name, last_name, email, phone, address, city, state, zip, cc_number, etc.


@dataclass
class FormAnalysis:
    """Analysis of a form on the page."""
    form_selector: str
    fields: List[FormField]
    submit_button: Optional[str]
    form_type: str  # contact, address, payment, login, signup, search, unknown
    has_payment_fields: bool
    is_safe_to_submit: bool


# Test data for form filling
TEST_DATA = {
    # Personal info
    "first_name": "John",
    "last_name": "Smith",
    "full_name": "John Smith",
    "email": "test@example.com",
    "phone": "5551234567",
    "phone_formatted": "(555) 123-4567",

    # Address - using serviceable test address
    "address": "3400 Lowry Rd",
    "address_line1": "3400 Lowry Rd",
    "address_line2": "",
    "unit": "",
    "apt": "",
    "city": "Los Angeles",
    "state": "CA",
    "state_full": "California",
    "zip": "90027",
    "zip_full": "90027-1234",
    "country": "United States",

    # Account
    "username": "testuser123",
    "password": "TestPass123!",

    # Payment (test card - will decline but validates format)
    "cc_number": "4111111111111111",
    "cc_exp": "01/29",
    "cc_exp_month": "01",
    "cc_exp_year": "29",
    "cc_exp_year_full": "2029",
    "cc_cvv": "123",
    "cc_name": "John Smith",

    # Other
    "company": "Test Company",
    "website": "https://example.com",
    "message": "This is a test message.",
    "date": "01/15/2025",
    "ssn_last4": "1234",
}


# Field classification patterns
FIELD_PATTERNS = {
    "first_name": [
        r"first.?name", r"fname", r"given.?name", r"forename",
    ],
    "last_name": [
        r"last.?name", r"lname", r"surname", r"family.?name",
    ],
    "full_name": [
        r"full.?name", r"^name$", r"your.?name", r"customer.?name",
    ],
    "email": [
        r"email", r"e-mail", r"mail",
    ],
    "phone": [
        r"phone", r"tel", r"mobile", r"cell", r"contact.?number",
    ],
    "address": [
        r"address", r"street", r"address.?line.?1", r"addr1",
    ],
    "address_line2": [
        r"address.?line.?2", r"addr2", r"apt", r"unit", r"suite",
    ],
    "city": [
        r"city", r"town", r"municipality",
    ],
    "state": [
        r"state", r"province", r"region",
    ],
    "zip": [
        r"zip", r"postal", r"postcode",
    ],
    "country": [
        r"country", r"nation",
    ],
    "cc_number": [
        r"card.?number", r"cc.?num", r"credit.?card", r"pan",
    ],
    "cc_exp": [
        r"expir", r"exp.?date", r"valid.?thru",
    ],
    "cc_exp_month": [
        r"exp.?month", r"card.?month",
    ],
    "cc_exp_year": [
        r"exp.?year", r"card.?year",
    ],
    "cc_cvv": [
        r"cvv", r"cvc", r"security.?code", r"card.?code",
    ],
    "cc_name": [
        r"name.?on.?card", r"cardholder", r"card.?name",
    ],
    "username": [
        r"user.?name", r"login", r"user.?id",
    ],
    "password": [
        r"password", r"pass", r"pwd",
    ],
    "company": [
        r"company", r"organization", r"business",
    ],
    "website": [
        r"website", r"url", r"web.?address",
    ],
    "message": [
        r"message", r"comment", r"note", r"description", r"inquiry",
    ],
    "search": [
        r"search", r"query", r"q$",
    ],
}

# Payment-related field classifications
PAYMENT_FIELDS = {"cc_number", "cc_exp", "cc_exp_month", "cc_exp_year", "cc_cvv", "cc_name"}


def classify_field(name: str, id: str, placeholder: str, label: str, field_type: str) -> str:
    """
    Classify a form field based on its attributes.

    Returns classification string like 'email', 'phone', 'cc_number', etc.
    """
    # Combine all text for matching
    text = f"{name} {id} {placeholder} {label}".lower()

    # Check field type hints first
    if field_type == "email":
        return "email"
    if field_type == "tel":
        return "phone"
    if field_type == "password":
        return "password"

    # Match against patterns
    for classification, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return classification

    return "unknown"


def classify_form_type(fields: List[FormField]) -> Tuple[str, bool]:
    """
    Classify form type based on its fields.

    Returns: (form_type, has_payment_fields)
    """
    classifications = {f.classification for f in fields}

    has_payment = bool(classifications & PAYMENT_FIELDS)

    # Determine form type
    if has_payment:
        return "payment", True

    if {"username", "password"} <= classifications:
        if "email" in classifications or "first_name" in classifications:
            return "signup", False
        return "login", False

    if {"address", "city", "state", "zip"} <= classifications:
        return "address", False

    if "email" in classifications:
        if "message" in classifications:
            return "contact", False
        if "first_name" in classifications or "last_name" in classifications:
            return "signup", False

    if "search" in classifications:
        return "search", False

    return "unknown", False


class FormHandler:
    """Handles form detection, analysis, and filling."""

    def __init__(
        self,
        test_data: Optional[Dict] = None,
        address_yaml_path: Optional[Path] = None,
        randomize: bool = False,
        locale: str = "en_US",
    ):
        """
        Initialize form handler.

        Args:
            test_data: Override default test data
            address_yaml_path: Path to address.yaml for address data
            randomize: If True, generate random test data using Faker
            locale: Faker locale for random data (default: en_US)
        """
        if randomize:
            self.test_data = generate_random_test_data(locale)
            logger.info(f"Using randomized test data (locale: {locale})")
        else:
            self.test_data = test_data or TEST_DATA.copy()

        # Load addresses from yaml if provided (overrides random address data)
        if address_yaml_path and address_yaml_path.exists():
            self._load_addresses(address_yaml_path)

    def _load_addresses(self, yaml_path: Path):
        """Load address and default registration data from address.yaml"""
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)

            # Load defaults section (personal info, phone, etc.)
            defaults = data.get("defaults", {})
            for key, value in defaults.items():
                if value:
                    self.test_data[key] = value
            if defaults:
                logger.info(f"Loaded defaults: {', '.join(defaults.keys())}")

            # Use serviceable address for test data
            serviceable = data.get("serviceable", [])
            if serviceable:
                addr = serviceable[0]
                self.test_data["address"] = addr.get("address", self.test_data["address"])
                self.test_data["address_line1"] = addr.get("address", self.test_data["address"])
                self.test_data["city"] = addr.get("city", self.test_data["city"])
                self.test_data["zip"] = addr.get("zip", self.test_data["zip"])
                self.test_data["unit"] = addr.get("unit", "")
                logger.info(f"Loaded test address: {self.test_data['address']}, {self.test_data['city']}")
        except Exception as e:
            logger.warning(f"Could not load address.yaml: {e}")

    async def analyze_form(self, page, form_selector: str = "form") -> Optional[FormAnalysis]:
        """
        Analyze a form on the page.

        Args:
            page: Playwright page
            form_selector: CSS selector for the form

        Returns:
            FormAnalysis or None if no form found
        """
        try:
            form = await page.query_selector(form_selector)
            if not form:
                return None

            fields = []

            # Find all input fields
            inputs = await form.query_selector_all("input, select, textarea")

            for inp in inputs:
                try:
                    field_type = await inp.get_attribute("type") or "text"

                    # Skip hidden and submit fields
                    if field_type in ("hidden", "submit", "button", "image"):
                        continue

                    name = await inp.get_attribute("name") or ""
                    id_attr = await inp.get_attribute("id") or ""
                    placeholder = await inp.get_attribute("placeholder") or ""
                    required = await inp.get_attribute("required") is not None

                    # Try to find label
                    label = ""
                    if id_attr:
                        label_el = await page.query_selector(f'label[for="{id_attr}"]')
                        if label_el:
                            label = await label_el.text_content() or ""

                    # Classify the field
                    classification = classify_field(name, id_attr, placeholder, label, field_type)

                    # Build selector for this field
                    if id_attr:
                        selector = f"#{id_attr}"
                    elif name:
                        selector = f'[name="{name}"]'
                    else:
                        selector = f'{form_selector} input[placeholder="{placeholder}"]'

                    fields.append(FormField(
                        selector=selector,
                        field_type=field_type,
                        name=name,
                        id=id_attr,
                        placeholder=placeholder,
                        label=label.strip(),
                        required=required,
                        classification=classification,
                    ))
                except Exception as e:
                    logger.debug(f"Error analyzing field: {e}")
                    continue

            # Find submit button
            submit_button = None
            submit_selectors = [
                f'{form_selector} button[type="submit"]',
                f'{form_selector} input[type="submit"]',
                f'{form_selector} button:has-text("Submit")',
                f'{form_selector} button:has-text("Continue")',
                f'{form_selector} button:has-text("Next")',
                f'{form_selector} button:has-text("Send")',
            ]

            for sel in submit_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        submit_button = sel
                        break
                except:
                    continue

            # Classify form
            form_type, has_payment = classify_form_type(fields)

            # Determine if safe to submit
            is_safe = not has_payment

            return FormAnalysis(
                form_selector=form_selector,
                fields=fields,
                submit_button=submit_button,
                form_type=form_type,
                has_payment_fields=has_payment,
                is_safe_to_submit=is_safe,
            )

        except Exception as e:
            logger.error(f"Error analyzing form: {e}")
            return None

    async def fill_form(self, page, analysis: FormAnalysis, skip_payment: bool = True) -> bool:
        """
        Fill form fields with test data.

        Args:
            page: Playwright page
            analysis: FormAnalysis from analyze_form()
            skip_payment: If True, don't fill payment fields

        Returns:
            True if form was filled successfully
        """
        filled_count = 0

        for field in analysis.fields:
            try:
                # Skip payment fields if requested
                if skip_payment and field.classification in PAYMENT_FIELDS:
                    logger.info(f"Skipping payment field: {field.classification}")
                    continue

                # Get test value
                value = self.test_data.get(field.classification)
                if not value:
                    if field.classification == "unknown" and field.field_type == "text":
                        value = "Test"  # Generic fallback
                    elif field.field_type != "select":
                        continue

                # Fill the field
                element = await page.query_selector(field.selector)
                if not element:
                    continue

                if field.field_type == "select":
                    # Handle select dropdowns - pick first valid option if no specific value
                    if value:
                        try:
                            await element.select_option(value=value)
                        except:
                            await self._select_first_option(element)
                    else:
                        await self._select_first_option(element)
                elif field.field_type == "checkbox":
                    # Check if not already checked
                    is_checked = await element.is_checked()
                    if not is_checked:
                        await element.check()
                elif field.field_type == "radio":
                    await element.check()
                else:
                    # Text inputs
                    await element.fill("")
                    await element.type(str(value), delay=30)

                logger.info(f"Filled {field.classification}: {field.selector}")
                filled_count += 1

            except Exception as e:
                logger.debug(f"Could not fill {field.selector}: {e}")
                continue

        return filled_count > 0

    async def _select_first_option(self, select_element) -> bool:
        """Select the first non-empty option in a dropdown."""
        try:
            # Get all options
            options = await select_element.query_selector_all("option")
            for option in options:
                value = await option.get_attribute("value")
                text = await option.text_content()
                # Skip empty/placeholder options
                if value and value.strip() and not value.startswith("--"):
                    if text and not text.strip().lower().startswith("select"):
                        await select_element.select_option(value=value)
                        logger.info(f"Selected first option: {text.strip()}")
                        return True
            return False
        except Exception as e:
            logger.debug(f"Could not select first option: {e}")
            return False

    async def fill_payment_fields(self, page, analysis: FormAnalysis) -> bool:
        """
        Fill payment fields with test card data.
        USE WITH CAUTION - only for testing payment flows.

        Args:
            page: Playwright page
            analysis: FormAnalysis from analyze_form()

        Returns:
            True if payment fields were filled
        """
        logger.warning("⚠️  Filling payment fields with test card data")

        filled_count = 0

        for field in analysis.fields:
            if field.classification not in PAYMENT_FIELDS:
                continue

            try:
                value = self.test_data.get(field.classification)
                if not value:
                    continue

                element = await page.query_selector(field.selector)
                if not element:
                    continue

                await element.fill("")
                await element.type(str(value), delay=50)

                logger.info(f"Filled payment field {field.classification}")
                filled_count += 1

            except Exception as e:
                logger.debug(f"Could not fill payment field {field.selector}: {e}")

        return filled_count > 0

    async def find_and_analyze_forms(self, page) -> List[FormAnalysis]:
        """
        Find and analyze all forms on a page.

        Args:
            page: Playwright page

        Returns:
            List of FormAnalysis objects
        """
        forms = []

        # Find all forms
        form_elements = await page.query_selector_all("form")

        for i, form_el in enumerate(form_elements):
            # Try to get form id or create selector
            form_id = await form_el.get_attribute("id")
            if form_id:
                selector = f"#{form_id}"
            else:
                selector = f"form:nth-of-type({i + 1})"

            analysis = await self.analyze_form(page, selector)
            if analysis and analysis.fields:
                forms.append(analysis)

        return forms

    async def auto_fill_and_submit(
        self,
        page,
        skip_payment_forms: bool = True,
        fill_payment_if_required: bool = False,
    ) -> Dict:
        """
        Automatically find, fill, and optionally submit forms.

        Args:
            page: Playwright page
            skip_payment_forms: Skip forms that have payment fields
            fill_payment_if_required: If True, fill payment with test card when encountered

        Returns:
            Dict with results
        """
        results = {
            "forms_found": 0,
            "forms_filled": 0,
            "forms_submitted": 0,
            "payment_forms_skipped": 0,
            "details": [],
        }

        forms = await self.find_and_analyze_forms(page)
        results["forms_found"] = len(forms)

        for analysis in forms:
            form_result = {
                "selector": analysis.form_selector,
                "type": analysis.form_type,
                "has_payment": analysis.has_payment_fields,
                "filled": False,
                "submitted": False,
            }

            # Handle payment forms
            if analysis.has_payment_fields:
                if skip_payment_forms and not fill_payment_if_required:
                    logger.warning(f"⚠️  Skipping payment form: {analysis.form_selector}")
                    results["payment_forms_skipped"] += 1
                    form_result["skipped"] = "payment form"
                    results["details"].append(form_result)
                    continue

            # Fill non-payment fields
            filled = await self.fill_form(page, analysis, skip_payment=True)

            # Fill payment if required
            if analysis.has_payment_fields and fill_payment_if_required:
                await self.fill_payment_fields(page, analysis)

            if filled:
                results["forms_filled"] += 1
                form_result["filled"] = True

                # Submit if safe
                if analysis.is_safe_to_submit and analysis.submit_button:
                    try:
                        await page.click(analysis.submit_button)
                        results["forms_submitted"] += 1
                        form_result["submitted"] = True
                        logger.info(f"Submitted form: {analysis.form_selector}")
                    except Exception as e:
                        logger.warning(f"Could not submit form: {e}")

            results["details"].append(form_result)

        return results


    async def select_all_first_options(self, page) -> int:
        """
        Select first option in all dropdowns on the page.
        Useful for configurators, shipping methods, etc.

        Returns:
            Number of dropdowns handled
        """
        count = 0
        selects = await page.query_selector_all("select")

        for select in selects:
            try:
                if await select.is_visible():
                    if await self._select_first_option(select):
                        count += 1
            except:
                continue

        return count

    async def click_first_selectable(self, page, container_selector: str = None) -> bool:
        """
        Click the first selectable option in a configurator/card layout.
        Handles radio-style product cards, plan selections, etc.

        Args:
            page: Playwright page
            container_selector: Optional container to search within

        Returns:
            True if something was clicked
        """
        base = page if not container_selector else await page.query_selector(container_selector)
        if not base:
            return False

        # Common selectable item patterns
        selectors = [
            '[role="radio"]:not([aria-checked="true"])',
            '[role="option"]:not([aria-selected="true"])',
            '.selectable:not(.selected)',
            '.option-card:not(.selected)',
            '.plan-card:not(.selected)',
            '.product-card:not(.selected)',
            '[data-selectable]:not([data-selected])',
            'input[type="radio"]:not(:checked)',
            '.card:has(input[type="radio"]):not(.active)',
        ]

        for selector in selectors:
            try:
                items = await base.query_selector_all(selector)
                for item in items:
                    if await item.is_visible():
                        await item.click()
                        logger.info(f"Selected first option: {selector}")
                        return True
            except:
                continue

        return False

    async def handle_configurator_step(self, page) -> Dict:
        """
        Handle a single configurator step - select first options and continue.

        Returns:
            Dict with actions taken
        """
        results = {
            "dropdowns_filled": 0,
            "options_selected": 0,
            "forms_filled": 0,
        }

        # 1. Handle any dropdowns
        results["dropdowns_filled"] = await self.select_all_first_options(page)

        # 2. Click first selectable card/option
        if await self.click_first_selectable(page):
            results["options_selected"] += 1

        # 3. Fill any forms
        forms = await self.find_and_analyze_forms(page)
        for analysis in forms:
            if await self.fill_form(page, analysis):
                results["forms_filled"] += 1

        return results

    async def find_and_click_continue(self, page) -> bool:
        """
        Find and click continue/next/checkout button.
        Avoids order COMPLETION buttons.

        Returns:
            True if a button was clicked
        """
        # Safe buttons to click (checkout is OK, completing order is NOT)
        safe_buttons = [
            'button:has-text("Continue")',
            'button:has-text("Next")',
            'button:has-text("Add to cart")',
            'button:has-text("Add")',
            'button:has-text("Select")',
            'button:has-text("Choose")',
            'button:has-text("Proceed")',
            'button:has-text("Get started")',
            'button:has-text("Check availability")',
            'button:has-text("Checkout")',
            'button:has-text("Go to checkout")',
            'button:has-text("Review")',
            'a:has-text("Continue")',
            'a:has-text("Next")',
            'a:has-text("Checkout")',
            '[data-testid="continue"]',
            '[data-testid="next"]',
            '[data-testid="checkout"]',
        ]

        # NEVER click these - these COMPLETE the order
        dangerous_patterns = [
            "submit order", "place order", "complete order",
            "complete purchase", "confirm order", "finalize order",
            "pay now", "place my order", "submit my order",
            "complete my order", "finish order",
        ]

        for selector in safe_buttons:
            try:
                buttons = await page.query_selector_all(selector)
                for btn in buttons:
                    if not await btn.is_visible():
                        continue
                    if not await btn.is_enabled():
                        continue

                    text = await btn.text_content() or ""
                    text_lower = text.lower().strip()

                    # Skip dangerous buttons
                    if any(d in text_lower for d in dangerous_patterns):
                        logger.warning(f"⚠️  Skipping dangerous button: {text}")
                        continue

                    await btn.click()
                    logger.info(f"Clicked: {text.strip()}")
                    return True
            except:
                continue

        return False


# Convenience function
async def analyze_page_forms(page) -> List[FormAnalysis]:
    """Quick analysis of all forms on a page."""
    handler = FormHandler()
    return await handler.find_and_analyze_forms(page)


async def auto_configure_page(
    page,
    address_yaml: Path = None,
    randomize: bool = False,
    locale: str = "en_US",
) -> Dict:
    """
    Automatically handle a configurator page:
    - Fill dropdowns with first options
    - Select first product/plan cards
    - Fill forms with test data
    - Click continue (but not checkout)

    Args:
        page: Playwright page
        address_yaml: Path to address.yaml for test data
        randomize: If True, generate random data using Faker
        locale: Faker locale for random data

    Returns:
        Dict with actions taken
    """
    handler = FormHandler(
        address_yaml_path=address_yaml,
        randomize=randomize,
        locale=locale,
    )
    results = await handler.handle_configurator_step(page)
    return results
