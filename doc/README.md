# MeshSense 문서

WiFi CSI(Channel State Information) 기반 실내 행동 인식 시스템 문서입니다. 구성요소별로 디렉터리를 나누어 두었습니다.

처음이라면 [overview/architecture.md](overview/architecture.md)에서 **수집 경로 2개(경로 A: UDP/AP, 경로 B: AP 없는 USB 시리얼)** 구조를 먼저 읽는 것을 권장합니다. 현재 데이터 수집과 모델 학습은 경로 B를 사용합니다.

## 문서 목록

| 경로 | 내용 |
|------|------|
| [overview/architecture.md](overview/architecture.md) | **전체 구조** — 두 수집 경로, 패킷 규격 비교, 상수, Python 환경 |
| [overview/quickstart.md](overview/quickstart.md) | 빠른 시작 (경로 A: TX → RX → 수집기 → 후처리, 경로 B: 메뉴 [6]) |
| [overview/esp-idf-troubleshooting.md](overview/esp-idf-troubleshooting.md) | ESP-IDF bootstrap·`idf.py`·플래시 오류 해결 |
| [overview/csi-rate-troubleshooting.md](overview/csi-rate-troubleshooting.md) | 수집률 22Hz 병목 디버깅 기록 → 경로 B 전환 결정 과정 + collector IP 이슈 |
| [firmware/tx-ap-node.md](firmware/tx-ap-node.md) | 경로 A TX: SoftAP + ESP-NOW + UDP heartbeat, 빌드·플래시 |
| [firmware/rx-csi-sender.md](firmware/rx-csi-sender.md) | 경로 A RX: CSI 수집·전처리·UDP 전송, `device_id`, 플래시 |
| [firmware/csi-poc.md](firmware/csi-poc.md) | **경로 B 전체** — esp-csi 기반 펌웨어 2종, v2 시리얼 프레임, 100Hz 실측 |
| [mac-collector/collector.md](mac-collector/collector.md) | 경로 A UDP 수집기 실행·등록표·세션 메타·워터폴 PNG |
| [mac-collector/udp-packet-schema.md](mac-collector/udp-packet-schema.md) | 경로 A UDP v1 바이너리 규격 (경로 B v2와의 관계 포함) |
| [postprocessing/pipeline.md](postprocessing/pipeline.md) | `add/main.py`: JSONL → 100Hz 보간 → `(N, 3, 52, 200)` 텐서 |
| [postprocessing/model-training.md](postprocessing/model-training.md) | **`model_train/`**: tx_seq 기반 전처리 → LSTM 3-class 학습 (PyTorch) |
| [scripts/README.md](../scripts/README.md) | 호스트 스크립트 전체 — 플래시·registry·수집·시각화 CLI |

## 저장소 레이아웃

```text
Wifi_esp32/
├── doc/                    ← 이 문서 트리
├── esp-idf/                ESP-IDF v5.2.2 (git submodule)
├── .espressif/             bootstrap 마커만 (gitignore; 툴체인은 ~/.espressif)
├── scripts/                플래시·bootstrap·registry·serial reader·시각화 CLI
├── esp32s3_tx_ap_node/     경로 A TX/AP 펌웨어 (SoftAP + ESP-NOW + UDP)
├── esp32s3_csi_sender/     경로 A RX 펌웨어 (CSI → 전처리 → UDP)
├── esp32s3_csi_send_poc/   경로 B TX 펌웨어 (esp-csi 기반, AP 없음)
├── esp32s3_csi_recv_poc/   경로 B RX 펌웨어 (CSI → USB 시리얼)
├── mac_collector/          UDP 수집기·session_meta.yaml·registry CSV 2종
├── add/                    후처리 스크립트 (경로 A 계열, main.py 단일 파일)
├── model_train/            LSTM 학습 코드 + 설계 노트 (경로 B 데이터 전용)
├── log/                    경로 B reader 실행 로그 (git 제외)
└── mac_collector_output/   수집 데이터 JSONL (git 제외)
```

AI 코딩 어시스턴트용 요약은 루트 [CLAUDE.md](../CLAUDE.md), 다른 에이전트용 공통 지침은 루트 [AGENTS.md](../AGENTS.md)를 참조하세요. 코드를 바꿀 때 어떤 문서를 함께 고쳐야 하는지는 [.claude/skills/doc-code-sync/SKILL.md](../.claude/skills/doc-code-sync/SKILL.md)의 매핑표에 정리되어 있습니다.
