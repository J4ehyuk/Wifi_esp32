"""device_registry.csv 로드·검증·MAC 조회 (MeshSense SSOT).

공통 CSV 로직은 registry_core에 있고, 이 모듈은 RX 명세와 DeviceRecord 변환만 담당한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from registry_core import (  # noqa: F401  (MAC_RE·normalize_mac은 기존 공개 API 재노출)
    MAC_RE,
    RegistrySpec,
    load_rows,
    normalize_mac,
    save_rows,
    suggest_next_id,
    verify_rows,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "mac_collector" / "device_registry.csv"

RX_SPEC = RegistrySpec(
    label="registry",
    id_field="device_id",
    mac_field="sta_mac",
    fieldnames=(
        "device_id",
        "board_name",
        "sta_mac",
        "room_x_m",
        "room_y_m",
        "height_m",
        "orientation_deg",
        "firmware_version",
        "notes",
    ),
    first_id=101,
)


@dataclass(frozen=True)
class DeviceRecord:
    device_id: int
    board_name: str
    sta_mac: str
    room_x_m: str = ""
    room_y_m: str = ""
    height_m: str = ""
    orientation_deg: str = ""
    firmware_version: str = ""
    notes: str = ""

    def as_csv_row(self) -> Dict[str, str]:
        return {
            "device_id": str(self.device_id),
            "board_name": self.board_name,
            "sta_mac": self.sta_mac,
            "room_x_m": self.room_x_m,
            "room_y_m": self.room_y_m,
            "height_m": self.height_m,
            "orientation_deg": self.orientation_deg,
            "firmware_version": self.firmware_version,
            "notes": self.notes,
        }


def _from_row(row: Dict[str, str]) -> DeviceRecord:
    return DeviceRecord(
        device_id=int(row["device_id"]),
        board_name=row["board_name"],
        sta_mac=row["sta_mac"],
        room_x_m=row["room_x_m"],
        room_y_m=row["room_y_m"],
        height_m=row["height_m"],
        orientation_deg=row["orientation_deg"],
        firmware_version=row["firmware_version"],
        notes=row["notes"],
    )


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> List[DeviceRecord]:
    return [_from_row(row) for row in load_rows(RX_SPEC, path)]


def build_indexes(records: List[DeviceRecord]) -> Tuple[Dict[str, DeviceRecord], Dict[int, DeviceRecord]]:
    by_mac: Dict[str, DeviceRecord] = {}
    by_id: Dict[int, DeviceRecord] = {}
    for rec in records:
        by_mac[rec.sta_mac] = rec
        by_id[rec.device_id] = rec
    return by_mac, by_id


def load_device_ids(path: Path = DEFAULT_REGISTRY_PATH) -> Set[int]:
    if not path.exists():
        return set()
    return {rec.device_id for rec in load_registry(path)}


def lookup_by_mac(mac: str, path: Path = DEFAULT_REGISTRY_PATH) -> Optional[DeviceRecord]:
    normalized = normalize_mac(mac)
    by_mac, _ = build_indexes(load_registry(path))
    return by_mac.get(normalized)


def lookup_by_device_id(device_id: int, path: Path = DEFAULT_REGISTRY_PATH) -> Optional[DeviceRecord]:
    _, by_id = build_indexes(load_registry(path))
    return by_id.get(device_id)


def verify_registry(path: Path = DEFAULT_REGISTRY_PATH) -> List[str]:
    """검증 오류 메시지 목록. 비어 있으면 OK."""
    return verify_rows(RX_SPEC, path)


def suggest_next_device_id(path: Path = DEFAULT_REGISTRY_PATH) -> int:
    return suggest_next_id(RX_SPEC, path)


def save_registry(records: List[DeviceRecord], path: Path = DEFAULT_REGISTRY_PATH) -> None:
    save_rows(RX_SPEC, [rec.as_csv_row() for rec in records], path)
