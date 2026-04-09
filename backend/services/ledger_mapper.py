"""Three-tier ledger mapping: stored rules → fuzzy match → AI suggestion.

Learns from user corrections to improve over time.

This module is in-memory only — `_stored_mappings` lives on the instance.
DB persistence is wired up in the orchestrator (Task 12).
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class MappingResult:
    ledger_name: str
    source: str  # "stored_rule" | "fuzzy_match" | "ai_suggestion"
    confidence: float
    is_new_ledger: bool = False
    suggested_parent: str | None = None


class LedgerMapper:
    """Maps vendor names to Tally ledgers using a 3-tier strategy."""

    FUZZY_THRESHOLD = 0.6

    def __init__(self):
        self._stored_mappings: list[dict] = []

    async def find_mapping(
        self,
        vendor_name: str,
        voucher_type: str,
        tally_ledgers: list[str],
        tally_groups: list[dict] | None = None,
    ) -> MappingResult:
        """Find the best ledger mapping for a vendor.

        Tries: stored rules → fuzzy match against Tally ledgers → AI suggestion.
        """
        vendor_lower = vendor_name.lower().strip()

        # Tier 1: Stored rules (sorted by use_count descending for hot-path priority)
        for mapping in sorted(self._stored_mappings, key=lambda m: -m["use_count"]):
            if (
                mapping["vendor_pattern"] == vendor_lower
                and mapping["voucher_type"] == voucher_type
            ):
                mapping["use_count"] += 1
                return MappingResult(
                    ledger_name=mapping["ledger_name"],
                    source="stored_rule",
                    confidence=mapping["confidence"],
                )

        # Tier 2: Fuzzy match against Tally ledger names
        best_match = None
        best_ratio = 0.0
        for ledger in tally_ledgers:
            ratio = SequenceMatcher(None, vendor_lower, ledger.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = ledger
        if best_match and best_ratio >= self.FUZZY_THRESHOLD:
            return MappingResult(
                ledger_name=best_match,
                source="fuzzy_match",
                confidence=best_ratio,
            )

        # Tier 3: AI suggestion (delegated; tests can override _ai_suggest)
        return await self._ai_suggest(vendor_name, voucher_type, tally_ledgers, tally_groups)

    async def _ai_suggest(
        self,
        vendor_name: str,
        voucher_type: str,
        tally_ledgers: list[str],
        tally_groups: list[dict] | None = None,
    ) -> MappingResult:
        """Default AI suggestion — proposes creating a new ledger.

        Override this or inject a real AI client for production use.
        """
        parent = "Indirect Expenses" if voucher_type == "Payment" else "Sundry Creditors"
        return MappingResult(
            ledger_name=vendor_name,
            source="ai_suggestion",
            confidence=0.5,
            is_new_ledger=True,
            suggested_parent=parent,
        )

    def learn_mapping(
        self,
        vendor: str,
        ledger_name: str,
        voucher_type: str,
        source: str = "user_correction",
    ) -> None:
        """Store a mapping from user correction or approved AI suggestion.

        User corrections override existing mappings (confidence=1.0).
        AI suggestions get confidence=0.8.
        """
        vendor_lower = vendor.lower().strip()
        confidence = 1.0 if source == "user_correction" else 0.8

        # Update existing mapping if same vendor + voucher type
        for mapping in self._stored_mappings:
            if (
                mapping["vendor_pattern"] == vendor_lower
                and mapping["voucher_type"] == voucher_type
            ):
                mapping["ledger_name"] = ledger_name
                mapping["confidence"] = confidence
                mapping["created_from"] = source
                return

        self._stored_mappings.append({
            "vendor_pattern": vendor_lower,
            "ledger_name": ledger_name,
            "voucher_type": voucher_type,
            "confidence": confidence,
            "use_count": 0,
            "created_from": source,
        })
