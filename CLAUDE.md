# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MeshSense — WiFi CSI(Channel State Information) 기반 실내 행동 인식 시스템. ESP32-S3 보드가 CSI를 수집해 Mac으로 전송하고(JSONL 저장), 후처리 파이프라인이 학습 텐서를 만들며, LSTM(PyTorch)으로 행동(empty/static/action)을 분류한다.

사용자 문서: `doc/README.md` (계층: `doc/overview/`, `doc/firmware/`, `doc/mac-collector/`, `doc/postprocessing/`).

**코드-문서 동기화 필수**: 상수·프로토콜·CLI·경로를 바꾸면 같은 커밋에서 관련 문서를 갱신한다. 코드↔문서 매핑표와 절차: `.claude/skills/doc-code-sync/SKILL.md` (다른 에이전트용 진입점: 루트 `AGENTS.md`).

## Architecture — 수집 경로 2개

같은 목표(100Hz CSI 수집)를 위한 서로 다른 두 파이프라인이 공존한다. 경로 A는 초기 설계(SoftAP + UDP)이고, 경로 B는 AP 접속 병목을 제거한 esp-csi 기반 구성이다. 학습 코드(`model_train/`)는 경로 B 데이터만 사용할 수 있다.

### 경로 A: UDP/AP (초기 설계 — AP/STA association 병목으로 실측 ~22Hz, `doc/overview/csi-rate-troubleshooting.md`)

```
TX/AP Node (esp32s3_tx_ap_node)
 └─ SoftAP(비콘 100TU, HT20 강제) + ESP-NOW 10ms(접속 STA unicast, 미접속 시 broadcast) + UDP heartbeat(3333)
 │
RX Nodes (esp32s3_csi_sender) × N대
 └─ TX/AP에 STA 접속, promiscuous + AP BSSID 필터 → CSI 콜백 → 큐+워커
 └─ 전처리(이동평균3 → z-score → ±3σ 클리핑) → UDP 전송 (9ms 상한)
 │
Mac Collector (mac_collector/udp_collector_mvp.py)
 └─ UDP 수신 → v1 헤더 검증 → JSONL 저장
 │
Post-processing (add/main.py)
 └─ received_at_unix_us 기준 100Hz 보간 → 슬라이딩 윈도우 → (N, 3, 52, 200) 텐서 (메모리 내, 파일 저장 없음)
```

### 경로 B: AP 없는 USB 시리얼 (esp-csi 기반 — 100Hz 실측 검증, 현재 수집·학습 주 경로)

```
TX (esp32s3_csi_send_poc)
 └─ association 없는 STA, 채널 11 고정, HT20, ESP-NOW broadcast 100Hz (payload에 tx_seq 카운터)
 │
RX (esp32s3_csi_recv_poc) × N대
 └─ promiscuous, 송신 MAC(1a:00:00:00:00:00) 필터 → v2 32B 프레임 → ring buffer → USB-Serial-JTAG
 │
Mac (scripts/csi_serial_reader.py — RX 보드당 1프로세스, meshsense_cli 메뉴 [6])
 └─ magic resync 파싱 → JSONL 저장 (경로 A 스키마 + tx_seq/rate/sig_len 추가)
 │
Model training (model_train/)
 └─ Preprocessing.py: tx_seq 격자 보간 → (N, 300, 52) → LSTM.py(PyTorch) 3-class 학습
```

**호환성 주의**: `model_train/model/Preprocessing.py`는 `tx_seq` 필드가 필수라서 **경로 B(csi_serial_reader.py)가 만든 JSONL만 입력 가능** (경로 A JSONL은 KeyError). `add/main.py`는 `received_at_unix_us` 기준이라 양쪽 JSONL 모두 동작. `add/`와 `model_train/`은 서로 독립 구현이며 파일을 주고받지 않는다.

**패킷 규격:**

- 경로 A UDP: little-endian 40바이트 헤더(`magic=0x4353`, `version=1`, `payload_type=1`) + `float32 csi_amp[sample_count]` — `doc/mac-collector/udp-packet-schema.md`
- 경로 B 시리얼: little-endian 32바이트 헤더(`magic=0x4353`, `version=2`, `tx_seq` 포함) + raw I/Q int8 — `doc/firmware/csi-poc.md`

**데이터 저장 경로(두 경로 공통):** `mac_collector_output/raw/YYYYMMDD/session_<id>/device_<id>.jsonl` (git 제외)

## Build & Run Commands

### ESP-IDF 펌웨어 (ESP32-S3)

프로젝트 로컬: `esp-idf/` (git submodule, **v5.2.2**) · 툴체인 `~/.espressif` · 마커 `프로젝트/.espressif/` (gitignore). 트러블슈팅: `doc/overview/esp-idf-troubleshooting.md`.

```bash
python scripts/meshsense_cli.py             # 메뉴: [1] 전체 가이드(경로 A) / [6] esp-csi PoC(경로 B)
python scripts/meshsense_cli.py --guide     # 가이드 바로 시작

git clone --recursive <repo>
cp scripts/meshsense_config.example.json scripts/meshsense_config.json
python scripts/idf_bootstrap.py -y          # 최초 1회 (submodule + install.sh esp32s3)

# 경로 A (registry 기반 자동 플래시)
python scripts/device_registry.py verify
python scripts/flash_rx.py -p /dev/cu.usbmodemXXXX -y   # bootstrap 자동 포함
python scripts/flash_tx.py -p /dev/cu.usbmodemXXXX -y

# 경로 B PoC (flash_*.py 미지원 — idf.py 직접 사용 또는 meshsense_cli 메뉴 [6])
cd esp32s3_csi_send_poc && idf.py set-target esp32s3 && idf.py -p <PORT> flash monitor

# 전역 ~/esp/esp-idf 만 사용: --skip-idf-bootstrap · 보드 전환 시: flash_*.py ... --clean -y
```

망 설정 SSOT: `scripts/meshsense_config.json` (`ap`, `collector`) — 경로 A 플래시 시 CMake `-D` 캐시로 주입되며 sdkconfig는 수정하지 않는다.
run `session_id` SSOT: `mac_collector/session_meta.yaml` — 수집기가 파싱해 `session_<id>/` 경로를 결정한다 (펌웨어 UDP 헤더 session_id는 항상 0).
RX: `device_registry.csv` + `flash_rx.py`. TX: `tx_registry.csv` + `flash_tx.py`. 경로 B PoC는 registry를 쓰지 않고 `device_id`를 reader CLI 인자로 받는다.
TODO: `session_meta.yaml` `network:` ↔ `meshsense_config.json` 자동 동기화 (현재 수동).

TX/AP 파라미터는 `esp32s3_tx_ap_node/CMakeLists.txt` CMake cache: `TX_AP_SSID`, `TX_AP_CHANNEL`(기본 6), `TX_AP_INTERVAL_MS`(10) 등 — cache 이름과 매크로 이름이 같다. RX는 `CSI_*` cache 변수가 무접두사 매크로(`WIFI_SSID`, `COLLECTOR_IP`, `DEVICE_ID`)로 변환되는 점에 주의.

### Mac Collector (경로 A)

```bash
python mac_collector/udp_collector_mvp.py \
 --host 0.0.0.0 --port 9999 \
 --output-dir mac_collector_output \
 --device-registry-csv mac_collector/device_registry.csv \
 --session-meta mac_collector/session_meta.yaml
```

### Serial Reader (경로 B — RX 보드당 1개, pyserial 필요)

```bash
python scripts/csi_serial_reader.py --port /dev/cu.usbmodemXXX \
 --device-id 101 --session-id 1 --output-dir mac_collector_output
```

### Post-processing / 모델 학습

```bash
# add/main.py: 상단 SESSION_DIR(기본값 dataset/... — 수집 경로로 변경)·RX_IDS 수정 후
python add/main.py            # (N, 3, 52, 200) 콘솔 출력만, 라벨은 랜덤 더미

# model_train (torch 필요, 경로 B JSONL 전용)
cd model_train/model          # LSTM.py가 bare import Preprocessing — 이 디렉터리에서 실행
python LSTM.py                # import 시 Preprocessing 전체 실행 (라벨 하드코딩, 모델 저장 없음)
```

상세: `doc/postprocessing/pipeline.md` · `doc/postprocessing/model-training.md` · 설계 노트 `model_train/LSTM_DESIGN.md`

Python 환경: `.venv` (`requirements-viz.txt`: numpy, matplotlib). `torch`(model_train)와 `pyserial`(serial reader)은 requirements에 미등재 — 별도 설치 필요. ESP-IDF는 별도 venv 사용.

## Key Constants

| 위치 | 상수 | 값 | 의미 |
|------|------|----|------|
| `csi_sender_main.c` | `SEND_INTERVAL_US` | 9000 | 경로 A RX UDP 전송 상한 (9ms) |
| `csi_sender_main.c` | `MAX_AMP_SAMPLES` | 64 | UDP `csi_amp` 최대 개수 |
| TX CMake | `TX_AP_ESPNOW_INTERVAL_MS` | 10 | ESP-NOW 주기 (100Hz 유도) |
| TX CMake | `TX_AP_BEACON_INTERVAL_TU` | 100 | SoftAP 비콘 (안정) |
| TX CMake | `TX_AP_INTERVAL_MS` | 10 | UDP heartbeat 주기 (ms) |
| `send_poc/app_main.c` | `CONFIG_SEND_FREQUENCY` | 100 | 경로 B ESP-NOW 송신 Hz |
| PoC 양쪽 | 채널 / 대역폭 | 11 / HT20 | 하드코딩 (2026-05 HT40→HT20 전환) |
| `add/main.py` | `F_S` / `WINDOW` / `STRIDE` | 100 / 200 / 100 | 100Hz, 2초 윈도, 1초 stride |
| `add/main.py` · `Preprocessing.py` | `N_SUB` | 52 | 후처리 서브캐리어 수 (앞 52개 절단) |
| `Preprocessing.py` | `WINDOW` / `STRIDE` | 300 / 30 | 3초 윈도, 0.3초 stride (tx_seq 격자) |
| `LSTM.py` | `INPUT_SIZE` / `HIDDEN_SIZE` / `NUM_LAYERS` / `NUM_CLASSES` | 52 / 128 / 2 / 3 | RX 1대(52 feature) 기준 |

## Conventions

- 한국어 커밋 메시지 및 주석 사용
- 문서는 쉬운 표현으로 가독성 있게 작성 (약어·전문용어는 첫 등장 시 풀어서 설명, 표는 주변 설명 문장과 함께)
- RX `device_id` / `sta_mac`: `mac_collector/device_registry.csv` — `scripts/device_registry.py`, `scripts/flash_rx.py`
- TX `tx_node_id` / `chip_mac`: `mac_collector/tx_registry.csv` — `scripts/tx_registry.py`, `scripts/flash_tx.py`
- run/session: `session_meta.yaml` `session_id` (수집기 SSOT); 장치: `device_registry.csv`
- 트러블슈팅 문서(`csi-rate-troubleshooting.md`, `csi-poc.md` 실측 절)는 날짜 붙은 실험 기록 — 과거 기록은 고쳐 쓰지 않고 추기(addendum)로 갱신
