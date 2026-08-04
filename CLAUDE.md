# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MeshSense — WiFi CSI 기반 실내 행동 인식 시스템. 수집 파이프라인 2개(USB 시리얼 / SoftAP+UDP)로
ESP32-S3가 CSI를 모으고, Mac이 JSONL로 저장하며, `model_train/`이 LSTM 학습 텐서를 만든다.

**아키텍처·상수·데이터 흐름은 `doc/overview/architecture.md`가 유일한 정본이다** — 이 파일에 복사하지 말 것.
문서 인덱스·저장소 레이아웃: `doc/README.md`. 셋업 명령: `doc/overview/quickstart.md`.

## 자주 쓰는 명령

```bash
python scripts/meshsense_cli.py                          # 메뉴 CLI: [1] USB 수집 / [2] AP 실시간 수집
python scripts/idf_bootstrap.py -y                       # ESP-IDF 준비 (최초 1회)
python scripts/flash_tx.py -p /dev/cu.usbmodemXXXX -y    # AP 파이프라인 TX (tx_registry 기반)
python scripts/flash_rx.py -p /dev/cu.usbmodemXXXX -y    # AP 파이프라인 RX (device_registry 기반)
python mac_collector/udp_collector_mvp.py                # AP 파이프라인 수집기 (기본 인자로 동작)
python model_train/model/Preprocessing.py                # 후처리 (최신 세션 자동 선택)
python model_train/model/LSTM.py --epochs 20             # 전처리 + LSTM 학습 (PyTorch 필요)
```

- USB 파이프라인 펌웨어(`esp32s3_csi_send_poc`/`esp32s3_csi_recv_poc`)는 CMake 파라미터가 없어
  `flash_*.py` 대상이 아님 — CLI `[1] 보드 플래시` 또는 `idf.py` 직접 사용
- ESP-IDF는 프로젝트 로컬 submodule `esp-idf/`(v5.2.2), 툴체인은 `~/.espressif`.
  트러블슈팅: `doc/overview/esp-idf-troubleshooting.md`
- Python 환경 2개 분리: 프로젝트 `.venv`(수집·후처리) / ESP-IDF venv(빌드)

## SSOT 위치 (수정 시 여기만)

- 망 설정: `scripts/meshsense_config.json` (`ap`, `collector`, `rx.espnow_only`)
- run `session_id`: `mac_collector/session_meta.yaml` (파서: `scripts/session_meta.py`)
- RX/TX 보드: `mac_collector/device_registry.csv` / `tx_registry.csv`
  (공통 로직: `scripts/registry_core.py`)
- 상수표: `doc/overview/architecture.md`

## Conventions

- 한국어 커밋 메시지 및 주석 사용
- 문서에 상수·메뉴 번호를 복붙하지 말고 `architecture.md` 표 또는 코드 링크로 위임
- TODO: `session_meta.yaml` `network:` ↔ `meshsense_config.json` 자동 동기화 (현재 수동)
