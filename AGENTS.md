# AGENTS.md

이 파일은 이 저장소에서 작업하는 **모든 AI 코딩 에이전트**(Codex, Cursor, Gemini CLI 등) 공통 지침입니다. Claude Code는 여기에 더해 `CLAUDE.md`와 `.claude/skills/`를 사용합니다.

## 프로젝트 한눈에

MeshSense — ESP32-S3로 WiFi CSI를 100Hz 수집해 LSTM으로 실내 행동(empty/static/action)을 분류하는 시스템.

- 수집 경로가 2개: **경로 A** (SoftAP+UDP, `esp32s3_tx_ap_node`+`esp32s3_csi_sender`, ~22Hz 한계) / **경로 B** (AP 없는 USB 시리얼, `esp32s3_csi_*_poc`+`scripts/csi_serial_reader.py`, 100Hz — 현재 주 경로)
- 학습 코드 `model_train/`은 `tx_seq` 필드가 필요해 **경로 B JSONL만** 입력 가능
- 구조 상세: `doc/overview/architecture.md` · 문서 인덱스: `doc/README.md` · 상수표: `CLAUDE.md`

## 필수 규칙 1 — 코드-문서 동기화

**코드를 바꾸면 관련 문서를 같은 커밋에서 갱신한다.** 전체 절차와 코드↔문서 매핑표는 표준 Agent Skills 형식으로 작성된 [`.claude/skills/doc-code-sync/SKILL.md`](.claude/skills/doc-code-sync/SKILL.md)에 있다 (Claude 전용 아님 — 모든 에이전트가 이 파일을 따를 것). 요약:

1. 바꾼 상수명·옛 값으로 `doc/`, `CLAUDE.md`, `README.md`, `scripts/README.md`를 grep해 언급처를 모두 찾는다.
2. 매핑표에 따라 해당 문서를 갱신한다. 상수는 `CLAUDE.md`와 `doc/overview/architecture.md` 두 상수표 모두.
3. 새 디렉터리·파이프라인은 전용 문서 신설 + `doc/README.md`·루트 `README.md`·`CLAUDE.md` 등록.
4. 날짜 붙은 실험 기록(`csi-rate-troubleshooting.md`, `csi-poc.md` 실측 절)은 고쳐 쓰지 말고 "추기 (날짜, 커밋)"로 덧붙인다.

## 필수 규칙 2 — 문서 스타일

- 한국어. 약어·전문용어는 첫 등장에서 짧게 풀어 설명.
- 표에는 주변 설명 문장을 함께. 지나친 축약 금지 — 코드를 안 열어도 이해되게.
- 미구현·한계는 숨기지 않고 명시.

## 컨벤션

- 커밋 메시지·주석은 한국어
- 망 설정 SSOT: `scripts/meshsense_config.json` (gitignore, example 복사) · run SSOT: `mac_collector/session_meta.yaml`의 `session_id`
- 보드 등록: RX `mac_collector/device_registry.csv` / TX `mac_collector/tx_registry.csv` (플래시 스크립트가 참조)
- ESP-IDF는 v5.2.2 서브모듈(`esp-idf/`) 고정 — 버전 올릴 때는 `scripts/idf_paths.py`와 문서도 함께
- 수집 데이터(`mac_collector_output/`)·로그(`log/`)·`.venv`는 커밋 금지 (gitignore 확인)
