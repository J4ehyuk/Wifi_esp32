"""session_meta.yaml 파서 — run session_id SSOT 읽기의 단일 구현."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

_SESSION_ID_RE = re.compile(r"^session_id:\s*(\d+)\s*$")


def read_session_id(path: Path, *, default: Optional[int] = None) -> int:
    """session_meta.yaml 루트 session_id를 읽는다.

    default가 None이면 파일/키 부재 시 예외(FileNotFoundError/ValueError)를 던지고,
    지정되어 있으면 어떤 실패든 default를 반환한다.
    """
    if not path.is_file():
        if default is not None:
            return default
        raise FileNotFoundError(f"session meta not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        if default is not None:
            return default
        raise
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _SESSION_ID_RE.match(stripped)
        if m:
            return int(m.group(1))
    if default is not None:
        return default
    raise ValueError(f"session_id not found in {path}")
