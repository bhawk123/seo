"""
Site Profile Model.

Ported from Spectrum per EPIC-SEO-INFRA-001 (STORY-INFRA-003).

This module defines the core data structures for storing site intelligence:
- SiteProfile: Top-level container for all site knowledge
- PageProfile: Individual page classification and structure
- FormProfile: Form fields, validation, and interaction patterns
- SelectorEntry: CSS/XPath selectors with confidence scores
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
import hashlib
import json


class PageType(Enum):
    """Classification of page types for semantic understanding."""
    HOMEPAGE = "homepage"
    PRODUCT_LIST = "product_list"
    PRODUCT_DETAIL = "product_detail"
    CART = "cart"
    CHECKOUT_ADDRESS = "checkout_address"
    CHECKOUT_SHIPPING = "checkout_shipping"
    CHECKOUT_PAYMENT = "checkout_payment"
    CHECKOUT_REVIEW = "checkout_review"
    ORDER_CONFIRMATION = "order_confirmation"
    LOGIN = "login"
    REGISTRATION = "registration"
    ACCOUNT = "account"
    SEARCH_RESULTS = "search_results"
    CATEGORY = "category"
    CONTENT = "content"
    ERROR = "error"
    UNKNOWN = "unknown"


class FormFieldType(Enum):
    """Classification of form field types."""
    TEXT = "text"
    EMAIL = "email"
    PHONE = "phone"
    PASSWORD = "password"
    ADDRESS_LINE1 = "address_line1"
    ADDRESS_LINE2 = "address_line2"
    CITY = "city"
    STATE = "state"
    ZIP = "zip"
    COUNTRY = "country"
    CREDIT_CARD = "credit_card"
    CVV = "cvv"
    EXPIRY = "expiry"
    NAME = "name"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SELECT = "select"
    TEXTAREA = "textarea"
    HIDDEN = "hidden"
    UNKNOWN = "unknown"


class ButtonIntent(Enum):
    """Classification of button/link intent."""
    ADD_TO_CART = "add_to_cart"
    PROCEED_CHECKOUT = "proceed_checkout"
    CONTINUE = "continue"
    SUBMIT_ORDER = "submit_order"  # DANGEROUS - never click
    APPLY_COUPON = "apply_coupon"
    UPDATE_CART = "update_cart"
    REMOVE_ITEM = "remove_item"
    LOGIN = "login"
    REGISTER = "register"
    SEARCH = "search"
    NAVIGATION = "navigation"
    CLOSE = "close"
    CANCEL = "cancel"
    BACK = "back"
    UNKNOWN = "unknown"


@dataclass
class SelectorEntry:
    """
    A CSS/XPath selector with Bayesian confidence scoring.

    Uses Bayesian averaging for more robust confidence calculation.
    Tracks selector reliability over time to enable adaptive selection.

    Lifecycle features (Gemini recommendation):
    - Tracks creation time for expiry calculations
    - Tracks last used time for staleness detection
    - Supports alternative promotion based on success rates
    """
    selector: str
    selector_type: str  # "css" or "xpath"
    confidence: float  # 0.0 to 1.0
    success_count: int = 0
    failure_count: int = 0
    last_success: datetime | None = None
    last_failure: datetime | None = None
    last_used: datetime | None = None  # For staleness detection
    created_at: datetime = field(default_factory=datetime.now)  # For expiry
    alternatives: list[str] = field(default_factory=list)
    # Track success/failure for each alternative
    alternative_stats: dict[str, dict[str, int]] = field(default_factory=dict)

    # Bayesian prior: assume 2 successes and 1 failure for new selectors
    PRIOR_SUCCESS: int = 2
    PRIOR_FAILURE: int = 1

    # Lifecycle thresholds
    STALE_DAYS: int = 30  # Consider stale if not used in 30 days
    EXPIRY_DAYS: int = 90  # Consider expired if not used in 90 days
    PROMOTION_THRESHOLD: float = 0.8  # Promote alternative if success rate > 80%
    MIN_ATTEMPTS_FOR_PROMOTION: int = 5  # Need at least 5 attempts to promote

    def record_success(self) -> None:
        """Record a successful selector usage."""
        self.success_count += 1
        self.last_success = datetime.now()
        self.last_used = datetime.now()
        self._update_confidence()

    def record_failure(self) -> None:
        """Record a failed selector usage."""
        self.failure_count += 1
        self.last_failure = datetime.now()
        self.last_used = datetime.now()
        self._update_confidence()

    def record_alternative_success(self, alternative: str) -> None:
        """Record successful usage of an alternative selector."""
        now = datetime.now()
        if alternative not in self.alternative_stats:
            self.alternative_stats[alternative] = {
                "success": 0,
                "failure": 0,
                "last_success": None,
                "last_failure": None,
            }
        self.alternative_stats[alternative]["success"] += 1
        self.alternative_stats[alternative]["last_success"] = now.isoformat()
        self.last_used = now

    def record_alternative_failure(self, alternative: str) -> None:
        """Record failed usage of an alternative selector."""
        now = datetime.now()
        if alternative not in self.alternative_stats:
            self.alternative_stats[alternative] = {
                "success": 0,
                "failure": 0,
                "last_success": None,
                "last_failure": None,
            }
        self.alternative_stats[alternative]["failure"] += 1
        self.alternative_stats[alternative]["last_failure"] = now.isoformat()
        self.last_used = now

    def _update_confidence(self) -> None:
        """
        Recalculate confidence using Bayesian averaging.

        Formula: confidence = (success + prior_success) / (total + prior_total)
        """
        # Bayesian average with prior
        effective_success = self.success_count + self.PRIOR_SUCCESS
        effective_total = (
            self.success_count + self.failure_count +
            self.PRIOR_SUCCESS + self.PRIOR_FAILURE
        )

        base_confidence = effective_success / effective_total

        # Apply small recency penalty if most recent attempt was a failure
        if self.last_failure and self.last_success:
            if self.last_failure > self.last_success:
                base_confidence *= 0.95  # 5% penalty for recent failure

        self.confidence = min(1.0, max(0.0, base_confidence))

    def get_reliability_score(self) -> float:
        """
        Get a reliability score that factors in sample size.
        """
        total_attempts = self.success_count + self.failure_count
        # Weight increases with sample size, maxing out around 20 attempts
        sample_weight = min(1.0, total_attempts / 20.0)
        # Blend between prior confidence and actual confidence based on sample size
        return 0.5 * (1 - sample_weight) + self.confidence * sample_weight

    # =========================================================================
    # Lifecycle Management (Gemini recommendation)
    # =========================================================================

    def is_stale(self) -> bool:
        """Check if selector is stale (not used recently)."""
        if self.last_used is None:
            # Never used, check created_at
            reference = self.created_at
        else:
            reference = self.last_used

        days_since = (datetime.now() - reference).days
        return days_since >= self.STALE_DAYS

    def is_expired(self) -> bool:
        """Check if selector is expired (not used for a long time)."""
        if self.last_used is None:
            reference = self.created_at
        else:
            reference = self.last_used

        days_since = (datetime.now() - reference).days
        return days_since >= self.EXPIRY_DAYS

    def days_since_used(self) -> int:
        """Get number of days since last use."""
        if self.last_used is None:
            return (datetime.now() - self.created_at).days
        return (datetime.now() - self.last_used).days

    def get_alternative_success_rate(self, alternative: str) -> float | None:
        """Get success rate for an alternative selector."""
        if alternative not in self.alternative_stats:
            return None
        stats = self.alternative_stats[alternative]
        total = stats["success"] + stats["failure"]
        if total == 0:
            return None
        return stats["success"] / total

    def get_primary_success_rate(self) -> float:
        """Get success rate of the primary selector."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # Neutral if no data
        return self.success_count / total

    def get_promotion_candidate(self) -> str | None:
        """
        Get an alternative that should be promoted to primary.

        Returns the alternative selector if one has a success rate above
        the promotion threshold with enough attempts AND performs better
        than the current primary selector.
        """
        primary_rate = self.get_primary_success_rate()
        best_candidate = None
        best_rate = self.PROMOTION_THRESHOLD

        for alt, stats in self.alternative_stats.items():
            total = stats["success"] + stats["failure"]
            if total >= self.MIN_ATTEMPTS_FOR_PROMOTION:
                rate = stats["success"] / total
                # Must be above threshold AND better than primary
                if rate > best_rate and rate > primary_rate:
                    best_rate = rate
                    best_candidate = alt

        return best_candidate

    def compare_with_alternative(self, alternative: str) -> dict[str, Any] | None:
        """
        Compare primary selector performance with an alternative.

        Args:
            alternative: Alternative selector to compare

        Returns:
            Comparison dict or None if alternative has no stats
        """
        if alternative not in self.alternative_stats:
            return None

        alt_stats = self.alternative_stats[alternative]
        alt_total = alt_stats["success"] + alt_stats["failure"]
        primary_total = self.success_count + self.failure_count

        if alt_total == 0:
            return None

        primary_rate = self.get_primary_success_rate()
        alt_rate = alt_stats["success"] / alt_total

        return {
            "primary_selector": self.selector,
            "primary_success_rate": round(primary_rate, 3),
            "primary_attempts": primary_total,
            "alternative_selector": alternative,
            "alternative_success_rate": round(alt_rate, 3),
            "alternative_attempts": alt_total,
            "rate_difference": round(alt_rate - primary_rate, 3),
            "should_promote": alt_rate > primary_rate and alt_rate >= self.PROMOTION_THRESHOLD,
            "alternative_last_success": alt_stats.get("last_success"),
            "alternative_last_failure": alt_stats.get("last_failure"),
        }

    def promote_alternative(self, alternative: str, force: bool = False) -> dict[str, Any]:
        """
        Promote an alternative to be the primary selector.

        Swaps the current primary with the alternative, preserving stats.
        By default, only promotes if the alternative performs better.

        Args:
            alternative: The alternative selector to promote
            force: If True, skip comparison check and force promotion

        Returns:
            Dict with promotion result and details
        """
        result = {
            "success": False,
            "old_primary": self.selector,
            "new_primary": alternative,
            "reason": None,
            "comparison": None,
        }

        if alternative not in self.alternatives:
            result["reason"] = "Alternative not found in alternatives list"
            return result

        # Compare performance unless forced
        if not force:
            comparison = self.compare_with_alternative(alternative)
            result["comparison"] = comparison

            if comparison is None:
                result["reason"] = "No stats available for alternative"
                return result

            if not comparison["should_promote"]:
                result["reason"] = (
                    f"Alternative ({comparison['alternative_success_rate']:.1%}) does not "
                    f"outperform primary ({comparison['primary_success_rate']:.1%})"
                )
                return result

        # Store current primary info with full stats
        old_primary = self.selector
        old_stats = {
            "success": self.success_count,
            "failure": self.failure_count,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "demoted_at": datetime.now().isoformat(),
        }

        # Get alternative stats
        alt_stats = self.alternative_stats.get(alternative, {"success": 0, "failure": 0})

        # Promote alternative to primary
        self.selector = alternative
        self.success_count = alt_stats.get("success", 0)
        self.failure_count = alt_stats.get("failure", 0)
        self._update_confidence()

        # Demote old primary to alternative
        self.alternatives.remove(alternative)
        self.alternatives.insert(0, old_primary)  # Add at front

        # Update alternative stats - archive old primary's stats
        self.alternative_stats[old_primary] = old_stats
        if alternative in self.alternative_stats:
            del self.alternative_stats[alternative]

        result["success"] = True
        result["reason"] = "Promotion successful"
        return result

    def get_lifecycle_status(self) -> dict[str, Any]:
        """Get lifecycle status summary."""
        promotion_candidate = self.get_promotion_candidate()
        return {
            "is_stale": self.is_stale(),
            "is_expired": self.is_expired(),
            "days_since_used": self.days_since_used(),
            "total_attempts": self.success_count + self.failure_count,
            "success_rate": self.success_count / max(1, self.success_count + self.failure_count),
            "alternatives_count": len(self.alternatives),
            "alternatives_with_stats": len(self.alternative_stats),
            "promotion_candidate": promotion_candidate,
            "should_promote": promotion_candidate is not None,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "selector": self.selector,
            "selector_type": self.selector_type,
            "confidence": self.confidence,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "created_at": self.created_at.isoformat(),
            "alternatives": self.alternatives,
            "alternative_stats": self.alternative_stats,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SelectorEntry":
        """Deserialize from dictionary."""
        return cls(
            selector=data["selector"],
            selector_type=data["selector_type"],
            confidence=data.get("confidence", 0.5),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            last_success=datetime.fromisoformat(data["last_success"]) if data.get("last_success") else None,
            last_failure=datetime.fromisoformat(data["last_failure"]) if data.get("last_failure") else None,
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            alternatives=data.get("alternatives", []),
            alternative_stats=data.get("alternative_stats", {}),
        )


@dataclass
class FormProfile:
    """
    Profile of a form on a page.

    Captures form structure, field types, and interaction patterns.
    """
    form_id: str
    form_name: str | None
    action: str | None
    method: str
    fields: dict[str, FormFieldType] = field(default_factory=dict)
    field_selectors: dict[str, SelectorEntry] = field(default_factory=dict)
    submit_selector: SelectorEntry | None = None
    validation_patterns: dict[str, str] = field(default_factory=dict)  # field -> regex
    required_fields: list[str] = field(default_factory=list)
    ai_analysis: dict[str, Any] = field(default_factory=dict)  # Raw AI classification data

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "form_id": self.form_id,
            "form_name": self.form_name,
            "action": self.action,
            "method": self.method,
            "fields": {k: v.value for k, v in self.fields.items()},
            "field_selectors": {k: v.to_dict() for k, v in self.field_selectors.items()},
            "submit_selector": self.submit_selector.to_dict() if self.submit_selector else None,
            "validation_patterns": self.validation_patterns,
            "required_fields": self.required_fields,
            "ai_analysis": self.ai_analysis,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FormProfile":
        """Deserialize from dictionary."""
        return cls(
            form_id=data["form_id"],
            form_name=data.get("form_name"),
            action=data.get("action"),
            method=data.get("method", "POST"),
            fields={k: FormFieldType(v) for k, v in data.get("fields", {}).items()},
            field_selectors={k: SelectorEntry.from_dict(v) for k, v in data.get("field_selectors", {}).items()},
            submit_selector=SelectorEntry.from_dict(data["submit_selector"]) if data.get("submit_selector") else None,
            validation_patterns=data.get("validation_patterns", {}),
            required_fields=data.get("required_fields", []),
            ai_analysis=data.get("ai_analysis", {}),
        )


@dataclass
class PageProfile:
    """
    Profile of a single page.

    Captures page classification, structure, and navigation options.
    """
    url_pattern: str  # Regex pattern matching this page
    page_type: PageType
    title_pattern: str | None = None
    forms: list[FormProfile] = field(default_factory=list)
    navigation_selectors: dict[str, SelectorEntry] = field(default_factory=dict)  # intent -> selector
    button_intents: dict[str, ButtonIntent] = field(default_factory=dict)  # selector -> intent
    branch_points: list[dict[str, Any]] = field(default_factory=list)  # Discovered branch options
    ai_classification: dict[str, Any] = field(default_factory=dict)
    last_seen: datetime | None = None
    visit_count: int = 0

    def record_visit(self) -> None:
        """Record a page visit."""
        self.visit_count += 1
        self.last_seen = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "url_pattern": self.url_pattern,
            "page_type": self.page_type.value,
            "title_pattern": self.title_pattern,
            "forms": [f.to_dict() for f in self.forms],
            "navigation_selectors": {k: v.to_dict() for k, v in self.navigation_selectors.items()},
            "button_intents": {k: v.value for k, v in self.button_intents.items()},
            "branch_points": self.branch_points,
            "ai_classification": self.ai_classification,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "visit_count": self.visit_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PageProfile":
        """Deserialize from dictionary."""
        return cls(
            url_pattern=data["url_pattern"],
            page_type=PageType(data.get("page_type", "unknown")),
            title_pattern=data.get("title_pattern"),
            forms=[FormProfile.from_dict(f) for f in data.get("forms", [])],
            navigation_selectors={k: SelectorEntry.from_dict(v) for k, v in data.get("navigation_selectors", {}).items()},
            button_intents={k: ButtonIntent(v) for k, v in data.get("button_intents", {}).items()},
            branch_points=data.get("branch_points", []),
            ai_classification=data.get("ai_classification", {}),
            last_seen=datetime.fromisoformat(data["last_seen"]) if data.get("last_seen") else None,
            visit_count=data.get("visit_count", 0),
        )


@dataclass
class SiteProfile:
    """
    Top-level container for all site intelligence.
    """
    site_id: str  # Unique identifier (usually domain name)
    base_url: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0.0"

    # Page profiles indexed by URL pattern
    pages: dict[str, PageProfile] = field(default_factory=dict)

    # Global selector library
    global_selectors: dict[str, SelectorEntry] = field(default_factory=dict)

    # Discovered user journeys
    journeys: list[dict[str, Any]] = field(default_factory=list)

    # Site-wide metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # AI learning history
    learning_history: list[dict[str, Any]] = field(default_factory=list)

    # Calibration corrections (human feedback)
    calibrations: list[dict[str, Any]] = field(default_factory=list)

    def get_page_profile(self, url: str) -> PageProfile | None:
        """Find a page profile matching the given URL."""
        import re
        for pattern, profile in self.pages.items():
            if re.match(pattern, url):
                return profile
        return None

    def add_page_profile(self, profile: PageProfile) -> None:
        """Add or update a page profile."""
        self.pages[profile.url_pattern] = profile
        self.updated_at = datetime.now()

    def record_learning(self, learning_type: str, data: dict[str, Any]) -> None:
        """Record an AI learning event."""
        self.learning_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": learning_type,
            "data": data,
        })
        self.updated_at = datetime.now()

    def add_calibration(self, original: dict[str, Any], corrected: dict[str, Any], notes: str = "") -> None:
        """Record a human calibration correction."""
        self.calibrations.append({
            "timestamp": datetime.now().isoformat(),
            "original": original,
            "corrected": corrected,
            "notes": notes,
        })
        self.updated_at = datetime.now()

    def compute_hash(self) -> str:
        """Compute a content hash for change detection."""
        content = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "site_id": self.site_id,
            "base_url": self.base_url,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "pages": {k: v.to_dict() for k, v in self.pages.items()},
            "global_selectors": {k: v.to_dict() for k, v in self.global_selectors.items()},
            "journeys": self.journeys,
            "metadata": self.metadata,
            "learning_history": self.learning_history,
            "calibrations": self.calibrations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SiteProfile":
        """Deserialize from dictionary."""
        profile = cls(
            site_id=data["site_id"],
            base_url=data["base_url"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            version=data.get("version", "1.0.0"),
        )
        profile.pages = {k: PageProfile.from_dict(v) for k, v in data.get("pages", {}).items()}
        profile.global_selectors = {k: SelectorEntry.from_dict(v) for k, v in data.get("global_selectors", {}).items()}
        profile.journeys = data.get("journeys", [])
        profile.metadata = data.get("metadata", {})
        profile.learning_history = data.get("learning_history", [])
        profile.calibrations = data.get("calibrations", [])
        return profile

    def save(self, path: Path) -> None:
        """Save site profile to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def load(cls, path: Path) -> "SiteProfile":
        """Load site profile from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)
