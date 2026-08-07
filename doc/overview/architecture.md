# 아키텍처

MeshSense의 목표는 **여러 대의 ESP32-S3 보드로 WiFi CSI(Channel State Information, 채널 상태 정보)를 초당 100회(100Hz) 수집**하고, 이 데이터를 Mac에 모아 행동 인식 모델(LSTM)을 학습시키는 것입니다.

현재 저장소에는 **수집 경로가 2개** 있습니다. 처음 만든 경로 A(UDP/AP 방식)가 속도 한계에 부딪혀, 그 병목을 제거한 경로 B(USB 시리얼 방식)를 새로 만들었기 때문입니다. 두 경로 모두 최종 산출물은 같은 폴더 구조의 JSONL 파일입니다.

| 구분 | 경로 A — UDP/AP | 경로 B — AP 없는 USB 시리얼 |
|------|----------------|------------------------------|
| 펌웨어 | `esp32s3_tx_ap_node` + `esp32s3_csi_sender` | `esp32s3_csi_send_poc` + `esp32s3_csi_recv_poc` |
| 데이터 이동 | WiFi UDP (RX → Mac) | USB 케이블 (RX → Mac) |
| Mac 쪽 수신 프로그램 | `mac_collector/udp_collector_mvp.py` | `scripts/csi_serial_reader.py` (보드당 1개 실행) |
| 실측 수집률 | 평균 ~22Hz (한계 확인됨) | **100Hz, 손실 0%** (2026-05-23 검증) |
| 후처리 | `add/main.py` | `model_train/model/Preprocessing.py` → LSTM 학습 |
| 현재 역할 | 초기 설계. 인프라(플래시 스크립트·registry)는 이 경로 기준 | **현재 데이터 수집과 모델 학습의 주 경로** |

경로 A가 느렸던 원인(AP 접속 구조 + DTIM 게이팅 + 대역폭 설정)과 경로 B로 전환한 과정은 [csi-rate-troubleshooting.md](csi-rate-troubleshooting.md)에 실험 기록으로 남아 있습니다.

## 경로 A — UDP/AP 방식

TX 보드가 WiFi 공유기(SoftAP) 역할을 하고, RX 보드들이 그 공유기에 접속(STA)한 상태에서 CSI를 뽑아 UDP로 Mac에 보내는 구조입니다.

```text
TX/AP Node (esp32s3_tx_ap_node)
  └─ SoftAP (비콘 100TU, HT20 강제)
  └─ ESP-NOW 10ms 송신 — 접속한 RX에는 unicast, 없으면 broadcast (CSI를 유발하는 주 트래픽)
  └─ UDP heartbeat (포트 3333, 10ms) — 보조 자극
       │  WiFi
RX Nodes (esp32s3_csi_sender) × N대
  └─ TX SoftAP에 STA로 접속, promiscuous 모드 + "우리 AP의 BSSID인지" 필터
  └─ CSI 콜백 → 큐에 넣고 워커 태스크가 처리 (콜백 안에서 무거운 일 금지)
  └─ 전처리: 3점 이동평균 → z-score 정규화 → ±3σ 클리핑
  └─ UDP 전송 (9ms 간격 상한 = 초당 최대 약 111회)
       │  WiFi UDP
Mac Collector (mac_collector/udp_collector_mvp.py)
  └─ 40바이트 v1 헤더 검증 → 장치별 JSONL 파일에 한 줄씩 저장
       │
Post-processing (add/main.py)
  └─ 수신 시각(received_at_unix_us) 기준 100Hz 격자로 보간
  └─ 2초 윈도우(1초 겹침)로 잘라 (N, 3, 52, 200) 텐서 생성 — 파일 저장은 없고 콘솔 출력만
```

## 경로 B — AP 없는 USB 시리얼 방식 (현재 주 경로)

WiFi 접속(association)을 아예 없앤 구조입니다. TX와 RX 모두 어디에도 접속하지 않은 STA 상태로, 같은 채널(11번)에서 TX가 ESP-NOW 브로드캐스트를 100Hz로 쏘고 RX는 그 프레임의 CSI만 골라 받습니다. RX는 IP 주소가 없으므로 데이터를 **USB 케이블(USB-Serial-JTAG)** 로 Mac에 직접 흘려보냅니다.

```text
TX (esp32s3_csi_send_poc)
  └─ 접속 없는 STA, 채널 11 고정, HT20, MAC을 1a:00:00:00:00:00로 덮어씀
  └─ ESP-NOW broadcast 100Hz — payload에 송신 카운터(tx_seq) 포함
       │  무선 (접속 없음)
RX (esp32s3_csi_recv_poc) × N대
  └─ promiscuous 모드, "송신 MAC이 1a:00:...인지" 필터
  └─ CSI 콜백 → 32바이트 v2 헤더 + raw I/Q를 ring buffer에 push (non-blocking)
  └─ uart_writer_task가 USB-Serial-JTAG로 그대로 전송
       │  USB
Mac (scripts/csi_serial_reader.py — RX 보드당 1개, meshsense_cli 메뉴 [6]이 자동 실행)
  └─ magic(0x4353) 동기화 파싱 → JSONL 저장 (경로 A와 같은 폴더 구조, tx_seq 필드 추가)
       │
Model training (model_train/)
  └─ Preprocessing.py: tx_seq 격자 기준 보간 → 3초 윈도우 → (N, 300, 52)
  └─ LSTM.py: PyTorch LSTM으로 empty/static/action 3-class 분류 학습
```

`tx_seq`는 TX가 보낸 순번이라 **모든 RX가 같은 프레임에 같은 값을 기록**합니다. 여러 RX의 데이터를 시간 정렬할 때 이 값을 join key로 씁니다. 상세: [csi-poc.md](../firmware/csi-poc.md).

### 두 경로의 데이터 호환성 (중요)

- `model_train/model/Preprocessing.py`는 `tx_seq` 필드를 요구하므로 **경로 B의 JSONL만 처리 가능**합니다. 경로 A JSONL을 넣으면 `KeyError: 'tx_seq'`가 납니다.
- `add/main.py`는 수신 시각(`received_at_unix_us`) 기준이라 **양쪽 JSONL 모두 처리 가능**합니다.
- `add/`와 `model_train/`은 별개 구현입니다. 출력 텐서 모양도 다르고(`(N,3,52,200)` vs `(N,300,52)`), 서로 파일을 주고받지 않습니다.
- 전처리 위치도 다릅니다: 경로 A는 RX 펌웨어가 z-score까지 해서 보내고, 경로 B는 raw 진폭(sqrt(I²+Q²))을 그대로 저장하며 Python 쪽에도 정규화가 없습니다.

## 패킷 규격 (둘 다 magic=0x4353, little-endian)

| | 경로 A (UDP v1) | 경로 B (시리얼 v2) |
|---|---|---|
| 헤더 크기 | 40바이트 | 32바이트 |
| version 필드 | 1 | 2 |
| 페이로드 | `float32 csi_amp[]` (전처리 완료 진폭, 최대 64개) | raw I/Q int8 배열 |
| 시간 동기화 키 | 없음 (Mac 수신 시각 사용) | `tx_seq` (TX 송신 카운터) |
| 문서 | [udp-packet-schema.md](../mac-collector/udp-packet-schema.md) | [csi-poc.md](../firmware/csi-poc.md) Phase 2 절 |

같은 magic을 쓰지만 **서로 호환되지 않는 별개 포맷**입니다. UDP 수집기는 version=1만, serial reader는 32바이트 v2 프레임만 받습니다.

**데이터 저장 경로(두 경로 공통):** `mac_collector_output/raw/YYYYMMDD/session_<id>/device_<id>.jsonl` (git 제외)

## 주요 상수

| 위치 | 상수 | 값 | 의미 |
|------|------|----|------|
| `csi_sender_main.c` | `SEND_INTERVAL_US` | 9000 | 경로 A RX UDP 전송 간격 하한 (9ms) |
| `csi_sender_main.c` | `MAX_AMP_SAMPLES` | 64 | UDP로 보내는 진폭 개수 상한 |
| TX CMake | `TX_AP_ESPNOW_INTERVAL_MS` | 10 | 경로 A ESP-NOW 주기 (100Hz 유도) |
| TX CMake | `TX_AP_BEACON_INTERVAL_TU` | 100 | SoftAP 비콘 간격 (짧으면 gap 유발) |
| TX CMake | `TX_AP_INTERVAL_MS` | 10 | UDP heartbeat 주기 |
| `send_poc/app_main.c` | `CONFIG_SEND_FREQUENCY` | 100 | 경로 B ESP-NOW 송신 Hz |
| PoC 양쪽 | 채널 / 대역폭 | 11 / HT20 | 하드코딩 (2026-05 HT40→HT20 전환) |
| `add/main.py` | `F_S` / `WINDOW` / `STRIDE` | 100 / 200 / 100 | 100Hz, 2초 윈도, 1초 stride |
| `model_train` `Preprocessing.py` | `WINDOW` / `STRIDE` | 300 / 30 | 3초 윈도, 0.3초 stride |
| 양쪽 후처리 | `N_SUB` | 52 | 사용할 서브캐리어 수 (64개 중 앞 52개 절단) |
| `LSTM.py` | `INPUT_SIZE` / `HIDDEN_SIZE` / `NUM_LAYERS` | 52 / 128 / 2 | RX 1대(52 feature) 기준 |

펌웨어는 최대 64개의 서브캐리어 진폭을 보내고, PC 후처리에서 앞 52개만 잘라 씁니다. 현재 두 후처리 모두 "유효 톤 선별 매핑"이 아니라 단순 절단이라는 점에 유의하세요 ([pipeline.md](../postprocessing/pipeline.md)).

## Python 환경

프로젝트 공용 venv 하나(`.venv`)와 ESP-IDF 전용 venv(자동 관리)를 분리해서 씁니다.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-viz.txt   # numpy, matplotlib (후처리·워터폴 PNG)
pip install pyserial                  # 경로 B serial reader 사용 시
pip install torch                     # model_train 학습 시
```

`pyserial`과 `torch`는 아직 requirements 파일에 등재되어 있지 않으므로 위처럼 직접 설치해야 합니다.

## 발표 자료

중간보고 PPT·PDF 등은 `presentations/`에 두며 git에는 포함하지 않습니다 (`.gitignore`).

## 운영 규칙

- 망 설정(SSID·채널·수집기 IP)은 `scripts/meshsense_config.json` 한 곳에서 관리하고, 경로 A 플래시 때 펌웨어에 주입됩니다 (`ap`, `collector` 블록)
- run 구분용 `session_id`는 `mac_collector/session_meta.yaml`이 유일한 기준(SSOT)입니다 — 펌웨어에는 session 개념이 없습니다
- RX 보드 등록: `mac_collector/device_registry.csv` — `scripts/device_registry.py`, `scripts/flash_rx.py`
- TX 보드 등록: `mac_collector/tx_registry.csv` — `scripts/tx_registry.py`, `scripts/flash_tx.py`
- **TODO:** `session_meta.yaml`의 `network:` 블록 ↔ `meshsense_config.json` 자동 동기화 (현재 수동, [collector.md](../mac-collector/collector.md))
- 실험 조건(방 크기·라벨·분할 전략)은 `mac_collector/session_meta.yaml`에 기록
