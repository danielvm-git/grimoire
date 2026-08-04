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

# Maximum output bytes retained per stream. Reads beyond this are drained and
# discarded so a runaway subprocess cannot exhaust memory (bug #3).
OUTPUT_SIZE_CAP = 64 * 1024  # 64 KB
_TRUNCATION_MARKER = "[output truncated — showing last 64KB]\n"

# Chunk size for incremental stream reads.
_READ_CHUNK = 64 * 1024


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


async def _read_stream_capped(
    stream: asyncio.StreamReader | None, cap: int
) -> tuple[bytes, bool]:
    """Drain *stream*, keeping only the last *cap* bytes in a rolling buffer.

    Returns ``(tail_bytes, truncated)``. When *stream* is ``None`` (not piped),
    returns ``(b"", False)``. This bounds peak memory to ~*cap* regardless of how
    much the subprocess emits (bug #3), instead of buffering the whole stream.
    """
    if stream is None:
        return b"", False

    tail = bytearray()
    truncated = False
    while not stream.at_eof():
        chunk = await stream.read(_READ_CHUNK)
        if not chunk:
            break
        tail.extend(chunk)
        if len(tail) > cap:
            # Keep only the last `cap` bytes; discard the head we've already seen.
            del tail[: len(tail) - cap]
            truncated = True
    return bytes(tail), truncated


def _format_capped(tail: bytes, truncated: bool) -> str:
    """Decode a tail buffer, prepending the truncation marker if it was capped."""
    text = tail.decode(errors="replace")
    if truncated:
        return _TRUNCATION_MARKER + text
    return text


async def read_output_capped(
    proc: asyncio.subprocess.Process,
    cap: int = OUTPUT_SIZE_CAP,
) -> str:
    """Read a process's combined stdout+stderr, capped to the last *cap* bytes.

    For actions the caller wires ``stderr=STDOUT`` so there is a single stream.
    For checks the caller keeps stdout and stderr separate; in that case use
    :func:`read_stdout_stderr_capped` instead. This helper reads the single
    combined stdout stream (bug #3: bounds memory instead of communicate()).
    """
    tail, truncated = await _read_stream_capped(proc.stdout, cap)
    # Drain stderr if it was separately piped (defensive; normally merged).
    if proc.stderr is not None and proc.stderr is not proc.stdout:
        await _read_stream_capped(proc.stderr, cap)
    return _format_capped(tail, truncated)


async def read_stdout_stderr_capped(
    proc: asyncio.subprocess.Process,
    cap: int = OUTPUT_SIZE_CAP,
) -> tuple[str, str]:
    """Read separate stdout and stderr streams, each capped to the last *cap* bytes.

    Returns ``(stdout_text, stderr_text)``, each independently truncated with the
    standard marker. Used by the checks engine which keeps the two streams apart
    (bug #3: bounds memory instead of communicate()).
    """
    out_tail, out_trunc = await _read_stream_capped(proc.stdout, cap)
    err_tail, err_trunc = await _read_stream_capped(proc.stderr, cap)
    return _format_capped(out_tail, out_trunc), _format_capped(err_tail, err_trunc)
