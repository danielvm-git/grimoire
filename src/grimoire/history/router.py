"""History API — time-series metrics for trend visualisation."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.config import StalenessConfig
from grimoire.database import StatsSnapshot
from grimoire.github.service import AGE_BUCKET_THRESHOLDS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/history", tags=["history"])

# ---------------------------------------------------------------------------
# Module-level state (injected at startup via set_history_state)
# ---------------------------------------------------------------------------

_engine: AsyncEngine | None = None
_staleness: StalenessConfig = StalenessConfig()


def set_history_state(engine: AsyncEngine, staleness: StalenessConfig) -> None:
    """Inject dependencies at startup."""
    global _engine, _staleness  # noqa: PLW0603
    _engine = engine
    _staleness = staleness


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pick_bucket(threshold_days: int) -> int:
    """Return the closest available age bucket for the given staleness threshold."""
    best = AGE_BUCKET_THRESHOLDS[0]
    best_dist = abs(threshold_days - best)
    for t in AGE_BUCKET_THRESHOLDS[1:]:
        dist = abs(threshold_days - t)
        if dist < best_dist:
            best = t
            best_dist = dist
    return best


def _extract_stale_series(
    snapshots: list[StatsSnapshot],
    json_field: str,
    threshold_days: int,
) -> list[int]:
    """Extract the stale count series from age-bucketed JSON for a given threshold."""
    bucket = _pick_bucket(threshold_days)
    result: list[int] = []
    for snap in snapshots:
        raw = getattr(snap, json_field) or "{}"
        try:
            buckets = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            buckets = {}
        result.append(buckets.get(str(bucket), 0))
    return result


def _build_series(
    snapshots: list[StatsSnapshot],
) -> dict[str, list[int]]:
    """Build all time-series from a list of snapshots (already ordered by date)."""
    return {
        "open_issues": [s.open_issues for s in snapshots],
        "stale_issues": [s.stale_issues for s in snapshots],
        "open_prs": [s.open_prs for s in snapshots],
        "stale_prs": [s.stale_prs for s in snapshots],
        "workflow_total": [s.workflow_total for s in snapshots],
        "workflow_failures": [s.workflow_failures for s in snapshots],
        "check_total": [s.check_total for s in snapshots],
        "check_failures": [s.check_failures for s in snapshots],
        "total_branches": [s.total_branches for s in snapshots],
        "stale_branches": [s.stale_branches for s in snapshots],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/global")
async def history_global(
    days: int = Query(default=30, ge=1, le=365),
    repos: list[str] | None = Query(default=None),
) -> dict:
    """Aggregated time-series across all (or selected) repos."""
    if _engine is None:
        raise HTTPException(503, "History not available — engine not initialised")

    cutoff = date.today() - timedelta(days=days)

    async with AsyncSession(_engine) as session:
        stmt = select(StatsSnapshot).where(col(StatsSnapshot.snapshot_date) >= cutoff)
        if isinstance(repos, list) and len(repos) > 0:
            stmt = stmt.where(col(StatsSnapshot.repo_full_name).in_(repos))
        rows = (await session.exec(stmt.order_by(col(StatsSnapshot.snapshot_date)))).all()

    if not rows:
        return {"timestamps": [], "series": {}}

    # Group by snapshot_date and aggregate (SUM across repos)
    by_date: dict[date, list[StatsSnapshot]] = {}
    for snap in rows:
        by_date.setdefault(snap.snapshot_date, []).append(snap)

    dates_sorted = sorted(by_date.keys())
    agg_snapshots: list[StatsSnapshot] = []
    for d in dates_sorted:
        group = by_date[d]
        merged_issues_age: dict[str, int] = {}
        merged_prs_age: dict[str, int] = {}
        merged_branches_age: dict[str, int] = {}
        for s in group:
            for field, target in [
                ("issues_by_age_json", merged_issues_age),
                ("prs_by_age_json", merged_prs_age),
                ("branches_by_age_json", merged_branches_age),
            ]:
                try:
                    buckets = json.loads(getattr(s, field) or "{}")
                except (json.JSONDecodeError, TypeError):
                    buckets = {}
                for k, v in buckets.items():
                    target[k] = target.get(k, 0) + v

        agg_snapshots.append(
            StatsSnapshot(
                snapshot_date=d,
                timestamp=group[0].timestamp,
                repo_full_name="(global)",
                open_issues=sum(s.open_issues for s in group),
                stale_issues=sum(s.stale_issues for s in group),
                open_prs=sum(s.open_prs for s in group),
                stale_prs=sum(s.stale_prs for s in group),
                workflow_total=sum(s.workflow_total for s in group),
                workflow_failures=sum(s.workflow_failures for s in group),
                check_total=sum(s.check_total for s in group),
                check_failures=sum(s.check_failures for s in group),
                total_branches=sum(s.total_branches for s in group),
                stale_branches=sum(s.stale_branches for s in group),
                issues_by_age_json=json.dumps(merged_issues_age),
                prs_by_age_json=json.dumps(merged_prs_age),
                branches_by_age_json=json.dumps(merged_branches_age),
            )
        )

    series = _build_series(agg_snapshots)
    timestamps = [d.isoformat() for d in dates_sorted]
    return {"timestamps": timestamps, "series": series}


@router.get("/{repo:path}")
async def history_repo(
    repo: str,
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Time-series for a single repository."""
    if _engine is None:
        raise HTTPException(503, "History not available — engine not initialised")

    cutoff = date.today() - timedelta(days=days)

    async with AsyncSession(_engine) as session:
        rows = (
            await session.exec(
                select(StatsSnapshot)
                .where(col(StatsSnapshot.snapshot_date) >= cutoff)
                .where(StatsSnapshot.repo_full_name == repo)
                .order_by(col(StatsSnapshot.snapshot_date))
            )
        ).all()

    if not rows:
        return {"timestamps": [], "series": {}}

    series = _build_series(list(rows))
    timestamps = [s.snapshot_date.isoformat() for s in rows]
    return {"timestamps": timestamps, "series": series}
