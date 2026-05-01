"""Shared script execution helper with shebang support.

When a script starts with ``#!``, it is written to a temporary file, made
executable, and run directly so the OS uses the specified interpreter (bash,
python3, etc.).  Scripts without a shebang are passed to ``/bin/sh`` via
``create_subprocess_shell`` as before.
"""

from __future__ import annotations

import asyncio
import os
import stat
import tempfile
from pathlib import Path


async def create_script_process(
    script: str,
    *,
    cwd: Path | str,
    env: dict[str, str],
    stdout: int | None = asyncio.subprocess.PIPE,
    stderr: int | None = asyncio.subprocess.PIPE,
) -> tuple[asyncio.subprocess.Process, Path | None]:
    """Create a subprocess for *script*, honoring shebang lines.

    Returns ``(process, temp_script_path)``.  When *temp_script_path* is not
    ``None`` the caller **must** delete the file after the process finishes.
    """
    if script.startswith("#!"):
        fd, tmp = tempfile.mkstemp(prefix="grimoire-script-")
        tmp_path = Path(tmp)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(script)
            tmp_path.chmod(tmp_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
            proc = await asyncio.create_subprocess_exec(
                str(tmp_path),
                cwd=str(cwd),
                env=env,
                stdout=stdout,
                stderr=stderr,
            )
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
        return proc, tmp_path

    proc = await asyncio.create_subprocess_shell(
        script,
        cwd=str(cwd),
        env=env,
        stdout=stdout,
        stderr=stderr,
    )
    return proc, None
