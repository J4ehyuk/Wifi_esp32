"""수집 JSONL → tx_seq 격자 정렬 → LSTM 입력 텐서 생성.

세션 디렉터리의 device_*.jsonl을 읽어 tx_seq(100Hz) 공통 격자에 보간하고,
슬라이딩 윈도로 X=(N, WINDOW, len(rx_ids)*N_SUB), y=(N,) 을 만든다.

  python model_train/model/Preprocessing.py                     # 최신 세션 자동 선택
  python model_train/model/Preprocessing.py \
      --session-dir mac_collector_output/raw/20260616/session_21 --label empty
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_ROOT = PROJECT_ROOT / "mac_collector_output" / "raw"

F_S = 100  # Hz, 송신기가 10ms마다 tx_seq 1개 증가
WINDOW_SECONDS = 3.0
STRIDE_SECONDS = 0.3
SESSION_SECONDS = 5 * 60
WINDOW = int(F_S * WINDOW_SECONDS)  # 3초 = 300 samples
STRIDE = int(F_S * STRIDE_SECONDS)  # 0.3초 = 30 samples
MAX_SESSION_SAMPLES = int(F_S * SESSION_SECONDS)  # 세션 5분 상한 = 30000
N_SUB = 52
LABEL_MAP = {
    "empty": 0,
    "static": 1,
    "action": 2,
}
DEFAULT_RX_IDS = (102,)


def find_latest_session_dir(raw_root: Path = DEFAULT_RAW_ROOT) -> Path:
    """raw/YYYYMMDD/session_* 중 최근 수정된 세션 디렉터리."""
    candidates = [p for p in raw_root.glob("*/session_*") if p.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"no session directories under {raw_root}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_buffers(session_dir: Path):
    """JSONL → device_id별 (tx_seq, amp) 목록 (tx_seq 오름차순).

    tx_seq가 없는 v1 레코드는 격자 정렬에 쓸 수 없으므로 건너뛴다.
    """
    buffers = defaultdict(list)
    skipped_v1 = 0
    for jsonl_path in sorted(session_dir.glob("*.jsonl")):
        with jsonl_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                pkt = json.loads(line)
                if pkt.get("tx_seq") is None:
                    skipped_v1 += 1
                    continue
                amp = np.array(pkt["csi_amp"], dtype=np.float64)
                buffers[pkt["device_id"]].append((int(pkt["tx_seq"]), amp))

    for dev in buffers:
        buffers[dev].sort(key=lambda item: item[0])

    if skipped_v1:
        print(f"  warning: tx_seq 없는 v1 레코드 {skipped_v1}개 건너뜀")
    return buffers


def to_array(buf):
    """버퍼를 (seq,), (T, N_SUB) 두 배열로 분리."""
    if not buf:
        return np.array([]), np.empty((0, N_SUB), np.float64)

    seq = np.array([s for s, _ in buf], dtype=np.float64)
    amp = np.stack([a[:N_SUB] for _, a in buf])
    return seq, amp


def resample_to_grid(buf, seq_grid):
    """RX 하나의 amplitude를 공통 seq_grid에 선형 보간. 결과 (T_common, N_SUB)."""
    seq, amp = to_array(buf)
    out = np.empty((len(seq_grid), N_SUB), dtype=np.float64)
    for k in range(N_SUB):
        out[:, k] = np.interp(seq_grid, seq, amp[:, k])
    return out


def run_preprocessing(session_dir: Path, rx_ids=DEFAULT_RX_IDS, label_name: str = "empty"):
    """세션 하나를 X=(N, WINDOW, len(rx_ids)*N_SUB), y=(N,) 으로 변환."""
    if label_name not in LABEL_MAP:
        raise ValueError(f"unknown label {label_name!r}. expected one of {sorted(LABEL_MAP)}")
    label = LABEL_MAP[label_name]

    buffers = load_buffers(session_dir)
    print(f"[1단계] device_id별 버퍼 ({session_dir})")
    for dev, items in buffers.items():
        print(f"  RX{dev}: {len(items)}개 패킷")

    missing = [dev for dev in rx_ids if not buffers.get(dev)]
    if missing:
        raise ValueError(
            f"no tx_seq data for RX {missing} in {session_dir} "
            f"(available: {sorted(buffers)})"
        )

    # tx_seq 기반 시간 동기화: 모든 RX가 겹치는 공통 seq 격자에 보간
    rx_arrays = {dev: to_array(buffers[dev]) for dev in rx_ids}
    start_seq = int(max(seq[0] for seq, _ in rx_arrays.values()))
    end_seq = int(min(seq[-1] for seq, _ in rx_arrays.values()))
    end_seq = min(end_seq, start_seq + MAX_SESSION_SAMPLES - 1)
    seq_grid = np.arange(start_seq, end_seq + 1, dtype=np.float64)

    # aligned: (len(rx_ids), T_common, N_SUB)
    aligned = np.stack([resample_to_grid(buffers[d], seq_grid) for d in rx_ids])
    print("\n[2단계] tx_seq 기반 시간 동기화 완료")
    print(f"  seq range: {start_seq} ~ {end_seq}")
    print(f"  duration: {len(seq_grid) / F_S:.3f}s")
    print(f"  aligned shape: {aligned.shape}   (RX, 시점, 서브캐리어)")

    t_common = aligned.shape[1]
    if t_common < WINDOW:
        raise ValueError(f"session too short: {t_common} samples < WINDOW={WINDOW}")

    # 윈도잉: (RX, T, N_SUB) → (N, WINDOW, len(rx_ids)*N_SUB)
    windows = []
    for start in range(0, t_common - WINDOW + 1, STRIDE):
        w = aligned[:, start : start + WINDOW, :]  # (RX, WINDOW, N_SUB)
        w = w.transpose(1, 0, 2).reshape(WINDOW, len(rx_ids) * N_SUB)
        windows.append(w)

    X = np.stack(windows)
    y = np.full(len(windows), label, dtype=np.int64)

    print("\n[3단계] 윈도잉 결과")
    print(f"  X shape: {X.shape}   ← (윈도 수, 시간, feature)")
    print(f"  y shape: {y.shape}")
    print(f"  label: {label_name} -> class {label}")
    print(f"  윈도 {len(windows)}개 ({WINDOW_SECONDS}초 윈도, {STRIDE_SECONDS}초 stride)")
    return X, y


def _parse_args():
    parser = argparse.ArgumentParser(description="세션 JSONL → LSTM 입력 텐서")
    parser.add_argument(
        "--session-dir",
        type=Path,
        default=None,
        help=f"세션 디렉터리 (기본: {DEFAULT_RAW_ROOT} 아래 최신 세션)",
    )
    parser.add_argument(
        "--rx-ids",
        type=int,
        nargs="+",
        default=list(DEFAULT_RX_IDS),
        help=f"사용할 RX device_id 목록 (기본: {list(DEFAULT_RX_IDS)})",
    )
    parser.add_argument(
        "--label",
        choices=sorted(LABEL_MAP),
        default="empty",
        help="이 세션 전체에 부여할 라벨 (기본: empty)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    session_dir = args.session_dir or find_latest_session_dir()
    run_preprocessing(session_dir, rx_ids=tuple(args.rx_ids), label_name=args.label)
