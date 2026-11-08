"""Per-repo compliance score from pattern checks (checks that set ``priority``).

P0 checks gate landing; P1 checks feed the score without turning the repo red.
Checks that have not run yet are counted separately and never as passing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Compliance:
    p0_passed: int = 0
    p0_total: int = 0
    p1_passed: int = 0
    p1_total: int = 0
    not_run: int = 0

    @property
    def passed(self) -> int:
        return self.p0_passed + self.p1_passed

    @property
    def total(self) -> int:
        return self.p0_total + self.p1_total

    @property
    def percent(self) -> int | None:
        """Share of P0+P1 results that pass, rounded down; None when nothing ran."""
        if not self.total:
            return None
        return self.passed * 100 // self.total

    @property
    def p0_failing(self) -> int:
        return self.p0_total - self.p0_passed

    @property
    def tier(self) -> str:
        """'fail' if any P0 fails, 'partial' if any P1 fails, else 'pass'."""
        if self.p0_failing:
            return "fail"
        if self.p1_passed < self.p1_total:
            return "partial"
        return "pass"


def compute_compliance(
    checks_by_branch: dict[str, list[dict[str, Any]]],
) -> Compliance | None:
    """Score every pattern-check entry across branches; None if the repo has none."""
    score = Compliance()
    seen = False
    for entries in checks_by_branch.values():
        for entry in entries:
            priority = entry.get("priority")
            if priority not in ("P0", "P1"):
                continue
            seen = True
            if entry.get("status") == "not-run":
                score.not_run += 1
                continue
            passed = entry.get("status") == "pass"
            if priority == "P0":
                score.p0_total += 1
                score.p0_passed += passed
            else:
                score.p1_total += 1
                score.p1_passed += passed
    return score if seen else None
