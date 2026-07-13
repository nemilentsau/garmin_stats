"""Local Codex CLI stub used by coach runner tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def codex_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    auth = home / ".codex/auth.json"
    auth.parent.mkdir(parents=True)
    auth.write_text('{"token":"test"}')
    binary = tmp_path / "bin/codex"
    binary.parent.mkdir()
    binary.write_text(
        """#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from pathlib import Path

args = sys.argv[1:]
record = Path(os.environ["CODEX_STUB_RECORD"])
record.write_text(json.dumps({
    "argv": args,
    "cwd": os.getcwd(),
    "home": os.environ.get("HOME"),
    "codex_home": os.environ.get("CODEX_HOME"),
}))
behavior = os.environ.get("CODEX_STUB_BEHAVIOR", "success")
if behavior == "nonzero":
    print("stub exploded", file=sys.stderr)
    raise SystemExit(7)
if behavior == "sleep":
    child = subprocess.Popen(["sleep", "60"])
    child_pid = os.environ.get("CODEX_STUB_CHILD_PID")
    if child_pid:
        Path(child_pid).write_text(str(child.pid))
    time.sleep(60)

output_path = Path(args[args.index("-o") + 1]) if "-o" in args else None
if behavior != "missing" and output_path is not None:
    raw = os.environ.get("CODEX_STUB_OUTPUT", "{}")
    output_path.write_text("not json" if behavior == "malformed" else raw)
print(json.dumps({"type": "thread.started", "thread_id": "session-123"}))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 11, "output_tokens": 7}}))
"""
    )
    binary.chmod(0o755)
    record = tmp_path / "record.json"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", f"{binary.parent}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("CODEX_STUB_RECORD", str(record))
    monkeypatch.setenv("CODEX_STUB_BEHAVIOR", "success")
    return record
