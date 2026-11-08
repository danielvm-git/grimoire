"""CLI: ``python -m grimoire.conformance <rule> [--path DIR]``.

Exit code 0 means the rule passed; any failure — including an unexpected error
inside the rule — exits 1, so a broken rule can never report a pass.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from grimoire.conformance import RuleContext, get_rules


def main(argv: list[str] | None = None) -> int:
    rules = get_rules()
    parser = argparse.ArgumentParser(prog="python -m grimoire.conformance")
    parser.add_argument("rule", choices=sorted(rules))
    parser.add_argument(
        "--path", default=".", help="repository checkout (default: cwd)"
    )
    args = parser.parse_args(argv)

    ctx = RuleContext(
        repo_path=Path(args.path).resolve(),
        repo_full_name=os.environ.get("REPO_FULL_NAME", ""),
        default_branch=os.environ.get("DEFAULT_BRANCH", "main"),
        token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", ""),
        api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
    )
    try:
        result = rules[args.rule](ctx)
    except Exception as exc:  # noqa: BLE001 — any crash must surface as a failure
        print(f"FAIL {args.rule}: rule crashed: {type(exc).__name__}: {exc}")
        return 1

    for note in result.notes:
        print(f"  note: {note}")
    if result.passed:
        print(f"PASS {args.rule}")
        return 0
    print(f"FAIL {args.rule}: {len(result.problems)} problem(s)")
    for problem in result.problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
