# MeshSense 문서

WiFi CSI(Channel State Information) 기반 실내 행동 인식 시스템 문서입니다.
수집 파이프라인 2개(USB / AP 실시간)와 공통 후처리·학습 경로로 구성됩니다.

## 문서 목록

| 경로 | 내용 |
|------|------|
| [overview/quickstart.md](overview/quickstart.md) | 최초 설정(셋업 명령 SSOT) → 파이프라인 선택 → 후처리 |
| [overview/architecture.md](overview/architecture.md) | 데이터 흐름·주요 상수(SSOT)·설정 SSOT 4종 |
| [overview/esp-idf-troubleshooting.md](overview/esp-idf-troubleshooting.md) | ESP-IDF bootstrap·`idf.py`·플래시 오류 |
| [overview/csi-rate-troubleshooting.md](overview/csi-rate-troubleshooting.md) | CSI 수집률 100Hz 미달 디버깅 기록 |
| [pipeline/usb-collection.md](pipeline/usb-collection.md) | USB 수집 파이프라인 (모델 학습 데이터 표준 경로) |
| [pipeline/ap-realtime.md](pipeline/ap-realtime.md) | AP 실시간 수집 파이프라인 (SoftAP + UDP) |
| [mac-collector/collector.md](mac-collector/collector.md) | UDP 수집기·registry·세션 메타 (공용 자산) |
| [mac-collector/udp-packet-schema.md](mac-collector/udp-packet-schema.md) | ESP → Mac 바이너리 UDP 규격 (v2) |
| [postprocessing/pipeline.md](postprocessing/pipeline.md) | JSONL → tx_seq 정렬 → 학습 텐서 |
| [postprocessing/lstm-design.md](postprocessing/lstm-design.md) | LSTM 모델 설계·라벨링·학습 |
| [../scripts/README.md](../scripts/README.md) | 호스트 스크립트 레퍼런스·CLI 메뉴 맵 |

## 저장소 레이아웃 (SSOT)

```text
Wifi_esp32/
├── doc/                    ← 이 문서 트리
├── esp-idf/                ESP-IDF v5.2.2 (git submodule)
├── .espressif/             bootstrap 마커만 (gitignore; 툴체인은 ~/.espressif)
├── scripts/                CLI·플래시·registry·config·수집 보조 도구
├── esp32s3_csi_send_poc/   USB 파이프라인 TX 펌웨어 (ESP-NOW 송신)
├── esp32s3_csi_recv_poc/   USB 파이프라인 RX 펌웨어 (CSI → USB 시리얼)
├── esp32s3_tx_ap_node/     AP 파이프라인 TX/AP 펌웨어
├── esp32s3_csi_sender/     AP 파이프라인 RX 펌웨어 (CSI → UDP)
├── mac_collector/          UDP 수집기·registry CSV·session_meta.yaml
├── model_train/            후처리(Preprocessing.py)·LSTM 학습
└── mac_collector_output/   수집 데이터 (git 제외)
```

AI 코딩 어시스턴트용 요약은 루트 [CLAUDE.md](../CLAUDE.md)를 참조하세요.
