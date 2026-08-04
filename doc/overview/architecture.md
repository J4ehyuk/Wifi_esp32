# 아키텍처

MeshSense는 **수집 파이프라인 2개**와 **공통 후처리·학습 경로**로 구성됩니다.
CLI(`python scripts/meshsense_cli.py`) 첫 화면의 [1]/[2]가 이 두 파이프라인과 1:1 대응합니다.

## 데이터 흐름

```text
[1] USB 수집 파이프라인 (모델 학습 데이터 표준 경로)
    TX (esp32s3_csi_send_poc)
      └─ ESP-NOW broadcast 10ms (tx_seq 카운터 탑재)
    RX (esp32s3_csi_recv_poc) × N대
      └─ CSI 콜백 → ring buffer → USB-Serial-JTAG 바이너리 프레임 (100Hz)
    Mac (scripts/csi_serial_reader.py × N)
      └─ 프레임 파싱 → JSONL 저장

[2] AP 실시간 수집 파이프라인 (SoftAP + UDP)
    TX/AP (esp32s3_tx_ap_node)
      └─ SoftAP(비콘 100TU) + ESP-NOW 10ms unicast (유일한 CSI 자극원)
    RX (esp32s3_csi_sender) × N대
      └─ STA 접속 → CSI 콜백 → 전처리(이동평균→z-score→클리핑) → UDP 전송
    Mac (mac_collector/udp_collector_mvp.py)
      └─ UDP 수신 → 패킷 검증 → JSONL 저장

공통 하류
    JSONL (mac_collector_output/raw/YYYYMMDD/session_<id>/device_<id>.jsonl)
      └─ model_train/model/Preprocessing.py : tx_seq 격자 보간 → 윈도잉
      └─ X = (N, 300, RX수×52) → model_train/model/LSTM.py 학습
```

두 파이프라인은 **같은 JSONL 레이아웃·같은 `tx_seq` 동기화 키**를 쓰므로 후처리는 공용입니다.
상세: [usb-collection.md](../pipeline/usb-collection.md) · [ap-realtime.md](../pipeline/ap-realtime.md)

## 주요 상수 (SSOT — 이 표가 유일한 정본)

| 소스 | 상수 | 값 | 의미 |
|------|------|----|------|
| `esp32s3_tx_ap_node/CMakeLists.txt` | `TX_AP_ESPNOW_INTERVAL_MS` | 10 | ESP-NOW 송신 주기 (100Hz CSI 유도, 유일한 자극원) |
| `esp32s3_tx_ap_node/CMakeLists.txt` | `TX_AP_BEACON_INTERVAL_TU` | 100 | SoftAP 비콘 (10TU는 에어타임 붕괴로 gap 유발) |
| `esp32s3_csi_sender/main/csi_sender_main.c` | `SEND_INTERVAL_US` | 9000 | RX UDP 전송 상한 (9ms = 100Hz + jitter 허용) |
| `esp32s3_csi_sender/main/csi_sender_main.c` | `CSI_ESPNOW_ONLY` | 기본 0 | ESP-NOW 프레임 CSI만 전송. `meshsense_config.json` `rx.espnow_only: true`로 1 주입 |
| 펌웨어 공통 | `sample_count` | 최대 64 | 패킷당 CSI 진폭 개수 (후처리에서 앞 52개 사용) |
| `model_train/model/Preprocessing.py` | `F_S` | 100 | 샘플링 주파수 (Hz), tx_seq 1스텝 = 10ms |
| `model_train/model/Preprocessing.py` | `WINDOW` / `STRIDE` | 300 / 30 | 3초 윈도, 0.3초 stride |
| `model_train/model/Preprocessing.py` | `N_SUB` | 52 | 모델 입력 서브캐리어 수 |
| `model_train/model/Preprocessing.py` | 텐서 shape | `(N, 300, RX수×52)` | RX 1대=52, 3대=156 feature |
| UDP 스키마 | `version` | 2 | v1 하위호환. [udp-packet-schema.md](../mac-collector/udp-packet-schema.md) |

## 설정 SSOT 4종

| 파일 | 담당 | 소비처 |
|------|------|--------|
| `scripts/meshsense_config.json` | 망 설정 (`ap.ssid/pass/channel`, `collector.ip/port`, `rx.espnow_only`) | `flash_tx.py` / `flash_rx.py` / CLI |
| `mac_collector/session_meta.yaml` | run `session_id` + 실험 조건 기록 | 수집기·visualize·CLI (`scripts/session_meta.py`로 파싱) |
| `mac_collector/device_registry.csv` | RX `device_id` ↔ `sta_mac` | `flash_rx.py`, 수집기, CLI |
| `mac_collector/tx_registry.csv` | TX `tx_node_id` ↔ `chip_mac` | `flash_tx.py`, CLI |

- run `session_id`는 **Mac 전용** — 펌웨어에 없고 UDP 헤더 `session_id` 필드는 항상 0.
- **TODO:** `session_meta.yaml` `network:` ↔ `meshsense_config.json` 자동 동기화 (현재 수동, [collector.md](../mac-collector/collector.md)).

## Python 환경 (2개 분리)

| 환경 | 용도 | 준비 |
|------|------|------|
| 프로젝트 `.venv` | 수집기·시각화·후처리 (numpy, matplotlib, pyserial) | [quickstart.md](quickstart.md) |
| ESP-IDF venv (`~/.espressif`) | 펌웨어 빌드 (`idf_bootstrap.py`가 관리) | 자동 |

LSTM 학습(`model_train/model/LSTM.py`)은 추가로 **PyTorch**가 필요합니다 (`pip install torch`).
