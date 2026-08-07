# MeshSense

WiFi CSI(Channel State Information) 기반 실내 행동 인식 시스템.

ESP32-S3 보드가 CSI를 100Hz로 수집해 Mac에 JSONL로 저장하고, 후처리를 거쳐 LSTM(PyTorch)으로 행동(empty/static/action)을 분류합니다.

## 수집 경로 (2가지)

```text
경로 A (초기 설계, ~22Hz 한계):
  TX SoftAP + ESP-NOW → RX STA 접속·CSI → UDP → Mac JSONL → add/main.py → (N, 3, 52, 200)

경로 B (100Hz 검증, 현재 주 경로):
  TX ESP-NOW 100Hz (AP 없음) → RX CSI → USB 시리얼 → Mac JSONL(+tx_seq)
    → model_train/ 전처리 (N, 300, 52) → LSTM 학습
```

경로 A의 병목 분석과 경로 B 전환 과정은 [csi-rate-troubleshooting.md](doc/overview/csi-rate-troubleshooting.md)에 기록되어 있습니다.

## 문서

전체 문서는 **[doc/](doc/README.md)** 에 계층적으로 정리되어 있습니다.

| 구분 | 문서 |
|------|------|
| 개요 | [아키텍처(두 경로)](doc/overview/architecture.md) · [빠른 시작](doc/overview/quickstart.md) |
| 펌웨어 (경로 A) | [TX/AP](doc/firmware/tx-ap-node.md) · [RX CSI](doc/firmware/rx-csi-sender.md) |
| 펌웨어 (경로 B) | [esp-csi 베이스 + USB 시리얼](doc/firmware/csi-poc.md) |
| 수집 | [Mac Collector](doc/mac-collector/collector.md) · [UDP v1 스키마](doc/mac-collector/udp-packet-schema.md) |
| 후처리·학습 | [add/ 파이프라인](doc/postprocessing/pipeline.md) · [LSTM 학습](doc/postprocessing/model-training.md) |
| 트러블슈팅 | [ESP-IDF·플래시](doc/overview/esp-idf-troubleshooting.md) · [수집률 디버깅 기록](doc/overview/csi-rate-troubleshooting.md) |
| 호스트 | [스크립트 전체 (플래시·registry·수집·시각화)](scripts/README.md) |

## 시작하기

```bash
git clone --recursive <repo-url>
cd Wifi_esp32
cp scripts/meshsense_config.example.json scripts/meshsense_config.json
python scripts/idf_bootstrap.py -y      # ESP-IDF 툴체인 (최초 1회)
python scripts/meshsense_cli.py         # [1] 경로 A 가이드 / [6] 경로 B PoC
```

AI 코딩 어시스턴트용 프로젝트 요약: [CLAUDE.md](CLAUDE.md) · 에이전트 공통 지침: [AGENTS.md](AGENTS.md)
