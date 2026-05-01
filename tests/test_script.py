"""Tests for the shebang-aware script execution helper."""

from __future__ import annotations

from pathlib import Path

from grimoire.script import create_script_process


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
