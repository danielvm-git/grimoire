"""Publish check results as GitHub commit statuses.

Check-runs need a GitHub App; a personal access token can only write commit
statuses, which branch protection can also require. Publishing is best-effort:
it never raises and never changes the check result.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_API = "https://api.github.com"
_DESCRIPTION_MAX = 140


def _summary(passed: bool, detail: str) -> str:
    head = "Check passed" if passed else "Check failed"
    line = next((ln.strip() for ln in reversed(detail.splitlines()) if ln.strip()), "")
    text = f"{head}: {line}" if line and not passed else head
    return text[:_DESCRIPTION_MAX]


async def publish_commit_status(
    token: str,
    full_name: str,
    sha: str,
    *,
    passed: bool,
    context: str,
    detail: str,
) -> bool:
    """POST a commit status. Returns True on success, False on any failure."""
    body = {
        "state": "success" if passed else "failure",
        "context": context,
        "description": _summary(passed, detail),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                f"{_API}/repos/{full_name}/statuses/{sha}",
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
    except httpx.HTTPError as exc:
        logger.warning("Status publish for %s failed: %s", full_name, exc)
        return False
    if resp.status_code >= 300:
        logger.warning(
            "Status publish for %s@%s refused (HTTP %s); the token needs "
            "'repo:status' (classic) or 'Commit statuses: write' (fine-grained)",
            full_name,
            sha[:7],
            resp.status_code,
        )
        return False
    return True


async def _head_sha(workdir: Path) -> str | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "rev-parse",
            "HEAD",
            cwd=workdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
    except OSError:
        return None
    sha = out.decode().strip()
    return sha if proc.returncode == 0 and len(sha) == 40 else None


async def publish_result_status(
    context: str,
    full_name: str,
    workdir: Path,
    passed: bool,
    output: str,
    token: str,
) -> None:
    """Publish a finished check's result to the workdir's head commit."""
    if not token:
        return
    sha = await _head_sha(workdir)
    if sha is None:
        logger.warning("No head commit in %s; skipping status publish", workdir)
        return
    await publish_commit_status(
        token, full_name, sha, passed=passed, context=context, detail=output
    )
