"""Probe types: outcomes, part results, the Probe record, and how part outcomes combine (S0 spec §5.1, §5.4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from v2.probes.context import ProbeContext


class Outcome(str, Enum):
    CONFIRMED = "CONFIRMED"
    DIFFERENT = "DIFFERENT"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"


class ProbeBlocked(Exception):
    """A part can't continue: timeout, Tally unreachable, missing prerequisite, or a manual step in non-interactive mode."""


@dataclass
class PartResult:
    outcome: Outcome
    summary: str
    observations: dict[str, Any] = field(default_factory=dict)
    spec_impact: str = ""

    def __post_init__(self) -> None:
        if self.outcome is Outcome.PARTIAL:
            raise ValueError("PARTIAL is a probe-level outcome, never a part outcome")
        if self.outcome in (Outcome.DIFFERENT, Outcome.FAILED) and not self.spec_impact.strip():
            raise ValueError(f"{self.outcome.value} needs a spec_impact sentence")


PartFn = Callable[["ProbeContext"], Awaitable[PartResult]]


@dataclass(frozen=True, eq=False)
class Probe:
    id: int
    name: str
    question: str
    feeds: tuple[str, ...]
    parts: dict[str, PartFn]
    requires: tuple[int, ...] = ()
    mutating: bool = False
    guard: bool = True
    educational_sensitive: bool = False
    planned_parts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.planned_parts and not set(self.parts) <= set(self.planned_parts):
            raise ValueError(f"Probe {self.id}: built parts {sorted(self.parts)} must be among {list(self.planned_parts)}")

    @property
    def part_labels(self) -> tuple[str, ...]:
        """Every company part of this probe, built now or in a later plan part (S0 spec §5.1, §5.4 PARTIAL)."""
        return self.planned_parts or tuple(self.parts)


_PRECEDENCE = (Outcome.BLOCKED, Outcome.FAILED, Outcome.DIFFERENT)


def combine(part_outcomes: dict[str, Outcome | None]) -> Outcome:
    """Probe outcome from its parts; first match wins: PARTIAL, BLOCKED, FAILED, DIFFERENT, else CONFIRMED."""
    if not part_outcomes or any(outcome is None for outcome in part_outcomes.values()):
        return Outcome.PARTIAL
    present = set(part_outcomes.values())
    for outcome in _PRECEDENCE:
        if outcome in present:
            return outcome
    return Outcome.CONFIRMED
