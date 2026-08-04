"""RX/TX registry CSV 공통 로직 (registry.py / tx_registry.py 내부 구현용)."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

MAC_RE = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")


def normalize_mac(mac: str) -> str:
    """다양한 MAC 표기를 AA:BB:CC:DD:EE:FF (대문자)로 통일."""
    raw = mac.strip().upper().replace("-", ":")
    if ":" not in raw and len(raw) == 12 and re.fullmatch(r"[0-9A-F]{12}", raw):
        raw = ":".join(raw[i : i + 2] for i in range(0, 12, 2))
    if not MAC_RE.match(raw):
        raise ValueError(f"invalid MAC address: {mac!r}")
    return raw


@dataclass(frozen=True)
class RegistrySpec:
    """registry 종류별 차이점만 담는 명세 (RX/TX 래퍼가 정의)."""

    label: str  # 에러 메시지용 ("registry" / "tx registry")
    id_field: str  # "device_id" / "tx_node_id"
    mac_field: str  # "sta_mac" / "chip_mac"
    fieldnames: Tuple[str, ...]  # CSV 컬럼 순서 (save 시 사용)
    first_id: int  # suggest_next_id 시작값


def load_rows(spec: RegistrySpec, path: Path) -> List[Dict[str, str]]:
    """CSV → row dict 목록. mac은 normalize 완료, 빈 행은 건너뜀."""
    if not path.exists():
        raise FileNotFoundError(f"{spec.label} not found: {path}")

    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if (
            not reader.fieldnames
            or spec.id_field not in reader.fieldnames
            or spec.mac_field not in reader.fieldnames
        ):
            raise ValueError(
                f"{spec.label} missing required columns ({spec.id_field}, {spec.mac_field}): {path}"
            )

        for line_no, row in enumerate(reader, start=2):
            raw_id = (row.get(spec.id_field) or "").strip()
            raw_mac = (row.get(spec.mac_field) or "").strip()
            if not raw_id and not raw_mac:
                continue
            if not raw_id or not raw_mac:
                raise ValueError(
                    f"{path}:{line_no}: {spec.id_field} and {spec.mac_field} are required"
                )

            clean = {name: (row.get(name) or "").strip() for name in spec.fieldnames}
            clean[spec.mac_field] = normalize_mac(raw_mac)
            rows.append(clean)
    return rows


def verify_rows(spec: RegistrySpec, path: Path) -> List[str]:
    """검증 오류 메시지 목록. 비어 있으면 OK."""
    try:
        rows = load_rows(spec, path)
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)]

    errors: List[str] = []
    seen_ids: Dict[int, int] = {}
    seen_macs: Dict[str, int] = {}
    for idx, row in enumerate(rows, start=1):
        row_id = int(row[spec.id_field])
        row_mac = row[spec.mac_field]
        if row_id in seen_ids:
            errors.append(
                f"duplicate {spec.id_field} {row_id} (rows {seen_ids[row_id]} and {idx})"
            )
        else:
            seen_ids[row_id] = idx

        if row_mac in seen_macs:
            errors.append(
                f"duplicate {spec.mac_field} {row_mac} (rows {seen_macs[row_mac]} and {idx})"
            )
        else:
            seen_macs[row_mac] = idx

    return errors


def suggest_next_id(spec: RegistrySpec, path: Path) -> int:
    if not path.exists():
        return spec.first_id
    rows = load_rows(spec, path)
    if not rows:
        return spec.first_id
    return max(int(row[spec.id_field]) for row in rows) + 1


def save_rows(spec: RegistrySpec, rows: List[Dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(spec.fieldnames))
        writer.writeheader()
        for row in sorted(rows, key=lambda r: int(r[spec.id_field])):
            writer.writerow(row)
