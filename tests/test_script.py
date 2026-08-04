"""Tests for the shebang-aware script execution helper."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from grimoire.script import OUTPUT_SIZE_CAP, create_script_process, read_output_capped


async def test_no_shebang_uses_shell(tmp_path: Path) -> None:
    """Scripts without a shebang run via /bin/sh (no temp file)."""
    proc, tmp_script = await create_script_process(
        "echo hello",
        cwd=tmp_path,
        env={},
    )
    stdout, _ = await proc.communicate()
    assert tmp_script is None
    assert proc.returncode == 0
    assert b"hello" in stdout


async def test_bash_shebang(tmp_path: Path) -> None:
    """Scripts with a bash shebang are executed via bash."""
    script = '#!/usr/bin/env bash\necho "bash: ${BASH_VERSION}"'
    proc, tmp_script = await create_script_process(
        script,
        cwd=tmp_path,
        env={},
    )
    stdout, _ = await proc.communicate()
    assert tmp_script is not None
    assert proc.returncode == 0
    assert b"bash:" in stdout
    tmp_script.unlink(missing_ok=True)


async def test_python_shebang(tmp_path: Path) -> None:
    """Scripts with a python3 shebang run via python3."""
    script = '#!/usr/bin/env python3\nimport sys; print(f"py{sys.version_info[0]}")'
    proc, tmp_script = await create_script_process(
        script,
        cwd=tmp_path,
        env={},
    )
    stdout, _ = await proc.communicate()
    assert tmp_script is not None
    assert proc.returncode == 0
    assert b"py3" in stdout
    tmp_script.unlink(missing_ok=True)


async def test_temp_file_cleaned_up(tmp_path: Path) -> None:
    """Caller can clean up the temp file after process finishes."""
    script = "#!/usr/bin/env bash\necho ok"
    proc, tmp_script = await create_script_process(
        script,
        cwd=tmp_path,
        env={},
    )
    await proc.communicate()
    assert tmp_script is not None
    assert tmp_script.exists()
    tmp_script.unlink()
    assert not tmp_script.exists()


async def test_shebang_uses_cwd(tmp_path: Path) -> None:
    """The script runs with the given cwd."""
    script = "#!/usr/bin/env bash\npwd"
    proc, tmp_script = await create_script_process(
        script,
        cwd=tmp_path,
        env={},
    )
    stdout, _ = await proc.communicate()
    assert str(tmp_path) in stdout.decode()
    if tmp_script:
        tmp_script.unlink(missing_ok=True)


async def test_shebang_passes_env(tmp_path: Path) -> None:
    """The script receives the provided environment variables."""
    script = '#!/usr/bin/env bash\necho "val=$MY_VAR"'
    proc, tmp_script = await create_script_process(
        script,
        cwd=tmp_path,
        env={"MY_VAR": "test123", "PATH": "/usr/bin:/bin"},
    )
    stdout, _ = await proc.communicate()
    assert b"val=test123" in stdout
    if tmp_script:
        tmp_script.unlink(missing_ok=True)


async def test_nonzero_exit_code(tmp_path: Path) -> None:
    """A failing script returns its exit code."""
    script = "#!/usr/bin/env bash\nexit 42"
    proc, tmp_script = await create_script_process(
        script,
        cwd=tmp_path,
        env={},
    )
    await proc.communicate()
    assert proc.returncode == 42
    if tmp_script:
        tmp_script.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Capped output reader (bug #3: subprocess-memory-unbounded-buffer)
# ---------------------------------------------------------------------------


def _emitter_script(total_bytes: int) -> str:
    """A python script that writes *total_bytes* of 'x' to stdout in chunks."""
    return (
        "import sys\n"
        f"n = {total_bytes}\n"
        "chunk = b'x' * 65536\n"
        "written = 0\n"
        "while written < n:\n"
        "    w = min(65536, n - written)\n"
        "    sys.stdout.buffer.write(chunk[:w])\n"
        "    written += w\n"
        "sys.stdout.buffer.flush()\n"
    )


async def test_read_capped_small_output_returned_in_full() -> None:
    """Output below the cap is returned unchanged."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import sys; sys.stdout.buffer.write(b'hello world')",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        output = await read_output_capped(proc, cap=OUTPUT_SIZE_CAP)
    finally:
        await proc.wait()
    assert output == "hello world"


async def test_read_capped_large_output_truncated_to_tail() -> None:
    """5MB of output is truncated to the last ``cap`` bytes (bug #3)."""
    total = 5 * 1024 * 1024  # 5 MB
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        _emitter_script(total),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    output = await read_output_capped(proc, cap=OUTPUT_SIZE_CAP)
    await proc.wait()

    marker = "[output truncated — showing last 64KB]\n"
    # Must be capped — not the full 5MB
    assert len(output) == len(marker) + OUTPUT_SIZE_CAP
    # Must carry the truncation marker
    assert output.startswith(marker)
    # Must be the TAIL: the rolling buffer kept the last cap bytes
    assert output.endswith("x")


async def test_read_capped_does_not_buffer_everything() -> None:
    """Peak buffer stays near the cap, not the full output size (bug #3 core).

    Asserts on the result length (bounded) rather than measuring RSS, which is
    flaky across platforms. The contract: a 2MB emission produces an output
    string no larger than cap + marker prefix.
    """
    total = 2 * 1024 * 1024  # 2 MB
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        _emitter_script(total),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    output = await read_output_capped(proc, cap=OUTPUT_SIZE_CAP)
    await proc.wait()

    marker = "[output truncated — showing last 64KB]\n"
    assert len(output) == len(marker) + OUTPUT_SIZE_CAP
