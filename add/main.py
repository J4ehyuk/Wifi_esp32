import numpy as np
import json
from collections import defaultdict
from pathlib import Path

np.set_printoptions(precision=16, floatmode="maxprec_equal", threshold=np.inf, suppress=False)

# === dataset/20260429/session_1 밑의 모든 JSONL 로드 ===
SESSION_DIR = Path("dataset/20260429/session_1")
raw_json_lines = []

# 각 파일별 공백 확인
for jsonl_path in sorted(SESSION_DIR.glob("*.jsonl")):
    with jsonl_path.open() as f:
        raw_json_lines.extend(line.strip() for line in f if line.strip())

# ======================== ① 파싱 후 device_id 별 버퍼에 적재 ========================
buffers = defaultdict(list)      # {101: [(t, amp), ...], 102: [...], 103: [...]}
tx_buffers = defaultdict(list)   # {101: [(tx_seq, amp), ...]} — v2 패킷(tx_seq 유효)만

for line in raw_json_lines:
    pkt = json.loads(line)
    dev = pkt['device_id']
    t   = pkt['received_at_unix_us']
    amp = np.array(pkt['csi_amp'], dtype=np.float64)
    rounded = amp.round(16) # 진폭: 소수점 16자리 까지 정밀도 설정
    buffers[dev].append((t, amp)) # 튜플로 저장
    tx_seq = pkt.get('tx_seq')    # v1 JSONL에는 키 없음 → None
    if tx_seq is not None:
        tx_buffers[dev].append((tx_seq, amp))

# for dev in buffers:
#     buffers[dev].sort(key=lambda item: item[0])

print("[1단계] device_id별 버퍼")
for dev, items in buffers.items():
    n_tx = len(tx_buffers[dev])
    cov = n_tx / len(items) * 100.0 if items else 0.0
    print(f"  RX{dev}: {len(items)}개 패킷 (tx_seq 유효 {n_tx}개, {cov:.0f}%)")
    # print(buffers[102][0][1])


# # ======================== ② 시간 동기화: 공통 축에 보간(interpolate) ========================
# 정렬 축 두 가지:
#   - "tx_seq":    TX ESP-NOW 카운터 (UDP v2). 모든 RX가 같은 프레임에 같은 값을 기록하므로
#                  네트워크 지터 없는 TX 쪽 10ms 클럭. tx_seq 1 = ESPNOW_INTERVAL_S.
#   - "recv_time": Mac 수신 시각(received_at_unix_us). v1 데이터 fallback.
#   - "auto":      모든 RX에 tx_seq가 있으면 tx_seq, 아니면 recv_time.
ALIGN_MODE        = "auto"
ESPNOW_INTERVAL_S = 0.01    # TX_AP_ESPNOW_INTERVAL_MS = 10ms (tx_seq 1 스텝)

RX_IDS  = [101, 102, 103]   # 사용자 환경에 맞춰 device_id 매핑
F_S     = 100               # Hz
WINDOW  = 200               # 2초
STRIDE  = 100               # 1초
N_SUB   = 52

# 버퍼를 시간배열과 진폭배열 두 개로 분리.
def to_array(buf):
    """버퍼를 (T,), (T, 52) 두 배열로"""
    if not buf:
        return np.array([]), np.empty((0, N_SUB), np.float64)

    ts  = np.array([t for t, _ in buf], dtype=np.float64) / 1e6   # us -> s, 초단위 변환
    amp = np.stack([a for _, a in buf]) # 시간별로 여러개의 amplitude 벡터를 2차원 배열로 쌓기
    return ts, amp

def to_txseq_array(buf):
    """tx_seq 버퍼를 (T,), (T, N_amp) 두 배열로. 정렬 + 중복 tx_seq 제거(첫 값 유지).

    주의: TX 보드가 수집 중 재부팅하면 tx_seq가 0부터 다시 시작해 축이 깨진다.
    """
    seen = set()
    qs, amps = [], []
    for q, a in sorted(buf, key=lambda item: item[0]):
        if q in seen:
            continue
        seen.add(q)
        qs.append(q)
        amps.append(a)
    if not qs:
        return np.array([]), np.empty((0, N_SUB), np.float64)
    return np.array(qs, dtype=np.float64), np.stack(amps)

def resample_axis(xs, amp, x_grid):
    """임의 축(xs) 위 진폭을 x_grid로 선형보간 → (len(x_grid), N_SUB)"""
    out = np.empty((len(x_grid), N_SUB), dtype=np.float64)
    for k in range(N_SUB):
        out[:, k] = np.interp(x_grid, xs, amp[:, k])
    return out

use_tx_seq = ALIGN_MODE == "tx_seq" or (
    ALIGN_MODE == "auto" and all(len(tx_buffers[d]) >= 2 for d in RX_IDS)
)

if use_tx_seq:
    # === tx_seq 공통 구간에서 1스텝(=10ms) 격자 생성 + 선형보간 ===
    rx_arrays = {dev: to_txseq_array(tx_buffers[dev]) for dev in RX_IDS}
    start_q = max(qs[0] for qs, _ in rx_arrays.values())   # 모든 RX가 존재하는 공통 tx_seq 구간
    end_q   = min(qs[-1] for qs, _ in rx_arrays.values())
    q_grid  = np.arange(start_q, end_q + 1, dtype=np.float64)
    aligned = np.stack([resample_axis(*rx_arrays[d], q_grid) for d in RX_IDS])
    t_grid  = q_grid * ESPNOW_INTERVAL_S                    # 후속 단계 호환용 상대 시간축(초)

    print(f"\n[2단계] tx_seq 동기화 완료 (TX 클럭 기준, 지터 없음)")
    print(f"  공통 tx_seq: {int(start_q)} ~ {int(end_q)}  (overlap {(end_q - start_q) * ESPNOW_INTERVAL_S:.3f}s)")
    for d in RX_IDS:
        n_rounds = len(rx_arrays[d][0])
        cov = n_rounds / len(q_grid) * 100.0 if len(q_grid) else 0.0
        print(f"  RX{d}: 라운드 커버리지 {cov:.1f}% ({n_rounds}/{len(q_grid)}) — 빈 라운드는 보간")
else:
    # === 공통 시간축 (100Hz 격자) 생성 + 선형보간 (v1 fallback) ===
    if ALIGN_MODE == "auto":
        print("\n[안내] tx_seq 없는 RX가 있어 recv_time 정렬로 fallback (v1 데이터?)")
    rx_arrays = {dev: to_array(buffers[dev]) for dev in RX_IDS}
    start_s = max(ts[0] for ts, _ in rx_arrays.values() if len(ts) > 0) # 세 RX가 모두 존재하는 공통 시작 시각
    end_s = min(ts[-1] for ts, _ in rx_arrays.values() if len(ts) > 0)  # 세 RX가 모두 존재하는 공통 종료 시각
    t_grid = np.arange(start_s, end_s, 1.0 / F_S, dtype=np.float64)
    aligned = np.stack([resample_axis(*rx_arrays[d], t_grid) for d in RX_IDS])

    print(f"\n[2단계] recv_time 동기화 완료")
    print(f"  overlap: {end_s - start_s:.3f}s")

# aligned: (3, T, 52)
print(f"  grid samples: {len(t_grid)}")
print(f"  aligned shape: {aligned.shape}   (RX, 시점, 서브캐리어)")

if len(t_grid) < WINDOW:
    print(f"  warning: WINDOW={WINDOW} requires at least {WINDOW} samples")


# ======================== ③ 윈도잉 → (N, 3, 52, 200) ========================
T = aligned.shape[1]
windows = []
for start in range(0, T - WINDOW + 1, STRIDE):
    w = aligned[:, start:start+WINDOW, :]   # (3, 200, 52)
    w = w.transpose(0, 2, 1)                # (3, 52, 200)  ← 모델 입력 순서로
    windows.append(w) # '리스트'에 추가

X = np.stack(windows)    # (N, 3, 52, 200), 4차원 배열로 쌓기, N=윈도 개수
y = np.random.randint(0, 3, size=len(windows))   # 가짜 라벨, 3-class

print(f"\n[3단계] 윈도잉 결과")
print(f"  X shape: {X.shape}   ← (윈도 수, RX, 서브캐리어, 시간)")
print(f"  y shape: {y.shape}")
print(f"  60초 → 윈도 {len(windows)}개 (2초 윈도, 1초 stride)")

# ======================== ④ 학습 batch ========================
# B = 32
# batch_x = X[:B]
# batch_y = y[:B]
# print(f"\n[4단계] Batch")
# print(f"  batch_x: {batch_x.shape}   ← 모델 입력")
# print(f"  batch_y: {batch_y.shape}")
