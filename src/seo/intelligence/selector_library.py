"""
Selector Library with Confidence Scoring.

Ported from Spectrum per EPIC-SEO-INFRA-001 (STORY-INFRA-004).

This module provides a library for managing CSS/XPath selectors
with confidence scoring and adaptive fallback strategies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import json

from .site_profile import SelectorEntry


@dataclass
class SelectorCandidate:
    """
    A candidate selector with associated metadata.

    Used during discovery to rank potential selectors.
    """
    selector: str
    selector_type: str  # "css" or "xpath"
    element_type: str  # "button", "input", "link", etc.
    purpose: str  # What this selector is for
    specificity: int  # CSS specificity score
    stability_score: float  # How stable this selector is likely to be
    attributes: dict[str, str] = field(default_factory=dict)  # id, class, data-*, etc.
    text_content: str | None = None

    def to_selector_entry(self, initial_confidence: float = 0.5) -> SelectorEntry:
        """Convert to a SelectorEntry for storage."""
        return SelectorEntry(
            selector=self.selector,
            selector_type=self.selector_type,
            confidence=initial_confidence,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "selector": self.selector,
            "selector_type": self.selector_type,
            "element_type": self.element_type,
            "purpose": self.purpose,
            "specificity": self.specificity,
            "stability_score": self.stability_score,
            "attributes": self.attributes,
            "text_content": self.text_content,
        }


class SelectorLibrary:
    """
    Library for managing and selecting optimal selectors.

    Provides:
    - Selector storage with confidence tracking
    - Automatic fallback selection
    - Selector generation strategies
    - Cross-site selector patterns
    """

    def __init__(self, storage_path: Path | None = None):
        """
        Initialize the selector library.

        Args:
            storage_path: Path to persist the library
        """
        self.storage_path = storage_path
        self._selectors: dict[str, dict[str, SelectorEntry]] = {}  # site_id -> purpose -> entry
        self._global_patterns: dict[str, list[str]] = {}  # purpose -> common patterns
        self._archive: dict[str, dict[str, dict]] = {}  # Archived expired selectors

        if storage_path and storage_path.exists():
            self._load()

    def _load(self) -> None:
        """Load library from disk."""
        if self.storage_path and self.storage_path.exists():
            with open(self.storage_path) as f:
                data = json.load(f)
            self._selectors = {
                site_id: {
                    purpose: SelectorEntry.from_dict(entry)
                    for purpose, entry in purposes.items()
                }
                for site_id, purposes in data.get("selectors", {}).items()
            }
            self._global_patterns = data.get("global_patterns", {})
            self._archive = data.get("archive", {})

    def _save(self) -> None:
        """Save library to disk."""
        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w") as f:
                json.dump({
                    "selectors": {
                        site_id: {
                            purpose: entry.to_dict()
                            for purpose, entry in purposes.items()
                        }
                        for site_id, purposes in self._selectors.items()
                    },
                    "global_patterns": self._global_patterns,
                    "archive": self._archive,
                }, f, indent=2)

    def get_selector(self, site_id: str, purpose: str) -> SelectorEntry | None:
        """
        Get the best selector for a purpose.

        Args:
            site_id: Site identifier
            purpose: What the selector is for (e.g., "add_to_cart", "checkout_button")

        Returns:
            Best available SelectorEntry or None
        """
        if site_id in self._selectors and purpose in self._selectors[site_id]:
            return self._selectors[site_id][purpose]
        return None

    def get_selector_with_fallbacks(
        self,
        site_id: str,
        purpose: str,
    ) -> list[SelectorEntry]:
        """
        Get selector with fallback alternatives.

        Returns list ordered by confidence (highest first).
        """
        selectors = []

        # Primary selector for this site
        primary = self.get_selector(site_id, purpose)
        if primary:
            selectors.append(primary)
            # Add alternatives
            for alt in primary.alternatives:
                selectors.append(SelectorEntry(
                    selector=alt,
                    selector_type=primary.selector_type,
                    confidence=primary.confidence * 0.8,  # Lower confidence for alternatives
                ))

        # Global patterns as last resort
        if purpose in self._global_patterns:
            for pattern in self._global_patterns[purpose]:
                if not any(s.selector == pattern for s in selectors):
                    selectors.append(SelectorEntry(
                        selector=pattern,
                        selector_type="css",
                        confidence=0.3,  # Low confidence for global patterns
                    ))

        return sorted(selectors, key=lambda s: s.confidence, reverse=True)

    def store_selector(
        self,
        site_id: str,
        purpose: str,
        entry: SelectorEntry,
    ) -> None:
        """
        Store a selector in the library.

        Args:
            site_id: Site identifier
            purpose: What the selector is for
            entry: The selector entry to store
        """
        if site_id not in self._selectors:
            self._selectors[site_id] = {}
        self._selectors[site_id][purpose] = entry
        self._save()

    def record_success(self, site_id: str, purpose: str) -> None:
        """Record a successful selector usage."""
        entry = self.get_selector(site_id, purpose)
        if entry:
            entry.record_success()
            self._save()

    def record_failure(self, site_id: str, purpose: str) -> None:
        """Record a failed selector usage."""
        entry = self.get_selector(site_id, purpose)
        if entry:
            entry.record_failure()
            self._save()

    def add_global_pattern(self, purpose: str, pattern: str) -> None:
        """Add a global selector pattern for cross-site fallback."""
        if purpose not in self._global_patterns:
            self._global_patterns[purpose] = []
        if pattern not in self._global_patterns[purpose]:
            self._global_patterns[purpose].append(pattern)
            self._save()

    def generate_candidates(
        self,
        element_html: str,
        purpose: str,
    ) -> list[SelectorCandidate]:
        """
        Generate selector candidates from element HTML.

        Uses multiple strategies to create robust selectors:
        1. ID-based (most specific)
        2. Data attribute-based (stable)
        3. Class-based (common)
        4. Text content-based (semantic)
        5. Structural (last resort)

        Args:
            element_html: The HTML of the target element
            purpose: What this selector is for

        Returns:
            List of candidates ordered by stability score
        """
        from html.parser import HTMLParser

        candidates = []

        class ElementParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tag = None
                self.attrs = {}
                self.text = ""

            def handle_starttag(self, tag, attrs):
                if self.tag is None:
                    self.tag = tag
                    self.attrs = dict(attrs)

            def handle_data(self, data):
                self.text += data.strip()

        parser = ElementParser()
        try:
            parser.feed(element_html)
        except Exception:
            return candidates

        tag = parser.tag or "div"
        attrs = parser.attrs
        text = parser.text

        # Strategy 1: ID-based (highest stability)
        if "id" in attrs:
            candidates.append(SelectorCandidate(
                selector=f"#{attrs['id']}",
                selector_type="css",
                element_type=tag,
                purpose=purpose,
                specificity=100,
                stability_score=0.95,
                attributes={"id": attrs["id"]},
            ))

        # Strategy 2: Data attribute-based
        data_attrs = {k: v for k, v in attrs.items() if k.startswith("data-")}
        for attr, value in data_attrs.items():
            candidates.append(SelectorCandidate(
                selector=f"{tag}[{attr}='{value}']",
                selector_type="css",
                element_type=tag,
                purpose=purpose,
                specificity=40,
                stability_score=0.85,
                attributes={attr: value},
            ))

        # Strategy 3: Test ID (very stable in test environments)
        if "data-testid" in attrs:
            candidates.append(SelectorCandidate(
                selector=f"[data-testid='{attrs['data-testid']}']",
                selector_type="css",
                element_type=tag,
                purpose=purpose,
                specificity=50,
                stability_score=0.98,
                attributes={"data-testid": attrs["data-testid"]},
            ))

        # Strategy 4: Aria label-based (accessible selectors)
        if "aria-label" in attrs:
            candidates.append(SelectorCandidate(
                selector=f"{tag}[aria-label='{attrs['aria-label']}']",
                selector_type="css",
                element_type=tag,
                purpose=purpose,
                specificity=40,
                stability_score=0.80,
                attributes={"aria-label": attrs["aria-label"]},
            ))

        # Strategy 5: Class-based (less stable but common)
        if "class" in attrs:
            classes = attrs["class"].split()
            # Filter out utility classes (common in CSS frameworks)
            meaningful_classes = [
                c for c in classes
                if not any(c.startswith(p) for p in ["col-", "row-", "mt-", "mb-", "px-", "py-"])
            ]
            if meaningful_classes:
                selector = f"{tag}.{'.'.join(meaningful_classes[:2])}"  # Max 2 classes
                candidates.append(SelectorCandidate(
                    selector=selector,
                    selector_type="css",
                    element_type=tag,
                    purpose=purpose,
                    specificity=20,
                    stability_score=0.60,
                    attributes={"class": " ".join(meaningful_classes[:2])},
                ))

        # Strategy 6: Text content-based (semantic but fragile)
        if text and len(text) < 50:
            candidates.append(SelectorCandidate(
                selector=f"//{tag}[contains(text(), '{text[:30]}')]",
                selector_type="xpath",
                element_type=tag,
                purpose=purpose,
                specificity=10,
                stability_score=0.40,
                text_content=text,
            ))

        return sorted(candidates, key=lambda c: c.stability_score, reverse=True)

    def stats(self) -> dict[str, Any]:
        """Get library statistics."""
        total_selectors = sum(
            len(purposes) for purposes in self._selectors.values()
        )
        total_archived = sum(
            len(purposes) for purposes in self._archive.values()
        )
        avg_confidence = 0.0
        if total_selectors > 0:
            confidences = [
                entry.confidence
                for purposes in self._selectors.values()
                for entry in purposes.values()
            ]
            avg_confidence = sum(confidences) / len(confidences)

        return {
            "site_count": len(self._selectors),
            "total_selectors": total_selectors,
            "average_confidence": round(avg_confidence, 2),
            "global_pattern_count": sum(len(p) for p in self._global_patterns.values()),
            "archived_count": total_archived,
            "archived_sites": len(self._archive),
        }

    # =========================================================================
    # Lifecycle Management (Gemini recommendation)
    # =========================================================================

    def cleanup_expired(self, archive: bool = True) -> dict[str, Any]:
        """
        Remove expired selectors from the library.

        By default, archives expired selectors instead of permanently deleting.
        Archived selectors can be restored if needed.

        Args:
            archive: If True, archive expired selectors; if False, delete permanently

        Returns:
            Dict with cleanup statistics
        """
        from datetime import datetime

        expired_count = 0
        stale_count = 0
        sites_affected = set()
        archived_selectors = []

        for site_id, purposes in list(self._selectors.items()):
            for purpose, entry in list(purposes.items()):
                if entry.is_expired():
                    # Archive before removing
                    if archive:
                        if site_id not in self._archive:
                            self._archive[site_id] = {}
                        self._archive[site_id][purpose] = {
                            **entry.to_dict(),
                            "archived_at": datetime.now().isoformat(),
                            "archive_reason": "expired",
                        }
                        archived_selectors.append({
                            "site_id": site_id,
                            "purpose": purpose,
                            "selector": entry.selector,
                        })

                    del purposes[purpose]
                    expired_count += 1
                    sites_affected.add(site_id)
                elif entry.is_stale():
                    stale_count += 1

            # Remove site if no selectors remain
            if not purposes:
                del self._selectors[site_id]

        if expired_count > 0:
            self._save()

        return {
            "expired_removed": expired_count,
            "expired_archived": len(archived_selectors) if archive else 0,
            "stale_count": stale_count,
            "sites_affected": len(sites_affected),
            "archived_selectors": archived_selectors if archive else [],
        }

    def restore_from_archive(self, site_id: str, purpose: str) -> bool:
        """
        Restore an archived selector to active use.

        Args:
            site_id: Site identifier
            purpose: Selector purpose

        Returns:
            True if restored, False if not found in archive
        """
        if site_id not in self._archive or purpose not in self._archive[site_id]:
            return False

        archived = self._archive[site_id][purpose]

        # Remove archive metadata before restoring
        archived_data = {k: v for k, v in archived.items()
                        if k not in ("archived_at", "archive_reason")}

        entry = SelectorEntry.from_dict(archived_data)

        # Store the restored selector
        if site_id not in self._selectors:
            self._selectors[site_id] = {}
        self._selectors[site_id][purpose] = entry

        # Remove from archive
        del self._archive[site_id][purpose]
        if not self._archive[site_id]:
            del self._archive[site_id]

        self._save()
        return True

    def get_archived(self, site_id: str | None = None) -> dict[str, Any]:
        """
        Get archived selectors.

        Args:
            site_id: Optional site to filter by

        Returns:
            Dict of archived selectors
        """
        if site_id:
            return self._archive.get(site_id, {})
        return self._archive

    def clear_archive(self, site_id: str | None = None) -> int:
        """
        Permanently clear archived selectors.

        Args:
            site_id: Optional site to clear; if None, clears all

        Returns:
            Number of archived entries cleared
        """
        if site_id:
            count = len(self._archive.get(site_id, {}))
            if site_id in self._archive:
                del self._archive[site_id]
        else:
            count = sum(len(purposes) for purposes in self._archive.values())
            self._archive = {}

        self._save()
        return count

    def auto_promote_alternatives(self) -> list[dict[str, Any]]:
        """
        Automatically promote successful alternatives to primary.

        Checks all selectors and promotes alternatives that have
        exceeded the promotion threshold AND outperform the current primary.

        Returns:
            List of promotion events with comparison details
        """
        promotions = []

        for site_id, purposes in self._selectors.items():
            for purpose, entry in purposes.items():
                candidate = entry.get_promotion_candidate()
                if candidate:
                    result = entry.promote_alternative(candidate)
                    if result["success"]:
                        promotions.append({
                            "site_id": site_id,
                            "purpose": purpose,
                            "old_selector": result["old_primary"],
                            "new_selector": result["new_primary"],
                            "new_confidence": entry.confidence,
                            "comparison": result["comparison"],
                        })

        if promotions:
            self._save()

        return promotions

    def get_lifecycle_report(self) -> dict[str, Any]:
        """
        Get a comprehensive lifecycle report for all selectors.

        Returns:
            Dict with lifecycle statistics and recommendations
        """
        total = 0
        stale = 0
        expired = 0
        low_confidence = 0
        promotion_candidates = []

        for site_id, purposes in self._selectors.items():
            for purpose, entry in purposes.items():
                total += 1
                status = entry.get_lifecycle_status()

                if status["is_expired"]:
                    expired += 1
                elif status["is_stale"]:
                    stale += 1

                if entry.confidence < 0.5:
                    low_confidence += 1

                if status["promotion_candidate"]:
                    promotion_candidates.append({
                        "site_id": site_id,
                        "purpose": purpose,
                        "current_selector": entry.selector,
                        "candidate": status["promotion_candidate"],
                        "candidate_success_rate": entry.get_alternative_success_rate(
                            status["promotion_candidate"]
                        ),
                    })

        return {
            "total_selectors": total,
            "stale_selectors": stale,
            "expired_selectors": expired,
            "low_confidence_selectors": low_confidence,
            "promotion_candidates": promotion_candidates,
            "recommendations": self._generate_lifecycle_recommendations(
                total, stale, expired, low_confidence, len(promotion_candidates)
            ),
        }

    def _generate_lifecycle_recommendations(
        self,
        total: int,
        stale: int,
        expired: int,
        low_confidence: int,
        promotion_count: int,
    ) -> list[str]:
        """Generate actionable recommendations based on lifecycle status."""
        recommendations = []

        if expired > 0:
            recommendations.append(
                f"Run cleanup_expired() to remove {expired} expired selector(s)"
            )

        if stale > 0 and stale > total * 0.2:
            recommendations.append(
                f"{stale} selector(s) are stale - consider re-validating"
            )

        if low_confidence > 0 and low_confidence > total * 0.1:
            recommendations.append(
                f"{low_confidence} selector(s) have low confidence - review alternatives"
            )

        if promotion_count > 0:
            recommendations.append(
                f"Run auto_promote_alternatives() to promote {promotion_count} successful alternative(s)"
            )

        if not recommendations:
            recommendations.append("Selector library is healthy - no action needed")

        return recommendations

    def record_alternative_result(
        self,
        site_id: str,
        purpose: str,
        alternative: str,
        success: bool,
    ) -> None:
        """
        Record result for an alternative selector.

        Args:
            site_id: Site identifier
            purpose: Selector purpose
            alternative: The alternative selector used
            success: Whether it succeeded
        """
        entry = self.get_selector(site_id, purpose)
        if entry:
            if success:
                entry.record_alternative_success(alternative)
            else:
                entry.record_alternative_failure(alternative)
            self._save()
