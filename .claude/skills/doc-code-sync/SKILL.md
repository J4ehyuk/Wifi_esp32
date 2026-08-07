---
name: doc-code-sync
description: MeshSense 코드를 변경할 때 함께 갱신해야 하는 문서를 찾아 같은 커밋에서 동기화한다. 상수·패킷 규격·CLI 인자·파일 경로·CLI 메뉴·디렉터리 구조를 바꾸거나 새 구성요소를 추가할 때 반드시 이 스킬의 매핑표와 절차를 따른다.
---

# 코드-문서 동기화 (doc-code-sync)

이 저장소의 문서는 코드의 거울이다. **코드를 바꾸면 관련 문서를 같은 커밋에서 갱신한다.** 문서만 나중에 고치는 커밋을 따로 만들지 않는다.

> 이 스킬은 표준 Agent Skills 형식(SKILL.md)으로 작성되어 Claude Code 외의 에이전트(Codex 등)도 그대로 읽을 수 있다. 비-Claude 에이전트용 진입점은 루트 `AGENTS.md`.

## 언제 발동하는가

다음 중 하나라도 바꾸면 문서 동기화 대상이다:

- 상수 값 (전송 주기, 윈도 크기, 채널, 포트, shape 등)
- 패킷/프레임 규격 (헤더 필드, 크기, version, JSONL 레코드 필드)
- CLI 인자·기본값, `meshsense_cli.py` 메뉴 구성
- 파일·디렉터리 추가/삭제/이동, 실행 방법 변경
- WiFi 설정 (대역폭, 모드, 필터), 전처리 순서
- 의존성 추가 (pip 패키지 등)

## 절차

1. **변경한 식별자·옛 값으로 문서를 검색**해 언급된 곳을 전부 찾는다:

   ```bash
   grep -rn "<상수명 또는 옛값>" doc/ CLAUDE.md AGENTS.md README.md scripts/README.md model_train/LSTM_DESIGN.md
   ```

2. 아래 **매핑표**에서 변경한 코드에 대응하는 문서를 확인하고, grep 결과와 합쳐 전부 갱신한다.
3. **상수를 바꿨다면 상수표는 두 곳** — `CLAUDE.md`의 "Key Constants"와 `doc/overview/architecture.md`의 "주요 상수" — 를 모두 확인한다.
4. **새 구성요소(디렉터리·파이프라인)를 추가했다면**: 전용 문서를 신설하고, `doc/README.md`(인덱스 표 + 저장소 레이아웃), 루트 `README.md`(문서 표), `CLAUDE.md`(아키텍처·명령)에 등록한다.
5. 커밋 전에 1번 grep을 다시 돌려 옛 값이 문서에 남아 있지 않은지 확인한다.

## 코드 → 문서 매핑표

| 변경한 코드 | 함께 갱신할 문서 |
|---|---|
| `esp32s3_csi_sender/main/csi_sender_main.c` (상수·전처리·UDP 헤더) | `doc/firmware/rx-csi-sender.md` · 헤더 변경 시 `doc/mac-collector/udp-packet-schema.md` · 상수표 2곳 |
| `esp32s3_csi_sender/CMakeLists.txt` (CSI_* cache 변수) | `doc/firmware/rx-csi-sender.md`(대응표) · `scripts/README.md` |
| `esp32s3_tx_ap_node/` (tx_ap_main.c, CMakeLists.txt) | `doc/firmware/tx-ap-node.md` · 상수표 2곳 |
| `esp32s3_csi_send_poc/` · `esp32s3_csi_recv_poc/` (경로 B 펌웨어) | `doc/firmware/csi-poc.md` · `doc/overview/architecture.md` · `CLAUDE.md` |
| `scripts/csi_serial_reader.py` (v2 프레임·JSONL 필드·CLI) | `doc/firmware/csi-poc.md`(프레임 표·사용법) · `scripts/README.md` |
| `mac_collector/udp_collector_mvp.py` (CLI·검증·레코드 필드) | `doc/mac-collector/collector.md` · 헤더 파싱 변경 시 `udp-packet-schema.md` |
| `mac_collector/session_meta.yaml` 구조·의미 | `doc/mac-collector/collector.md` · `doc/overview/quickstart.md` |
| `mac_collector/*_registry.csv` 컬럼 | `doc/mac-collector/collector.md` · `scripts/README.md` |
| `add/main.py` (상수·처리 단계·출력 shape) | `doc/postprocessing/pipeline.md` · 상수표 2곳 · 루트 `README.md` 요약 |
| `model_train/` (Preprocessing.py, LSTM.py) | `doc/postprocessing/model-training.md` · `model_train/LSTM_DESIGN.md` · 상수표 2곳 |
| `scripts/*.py` 추가·삭제·CLI 변경 | `scripts/README.md`(파일 목록 표) |
| `scripts/meshsense_cli.py` 메뉴 변경 | `scripts/README.md`(메뉴 표) · `doc/overview/quickstart.md` |
| `scripts/meshsense_config.example.json` 키 | `scripts/README.md` · `doc/firmware/tx-ap-node.md`(대응표) · `doc/firmware/rx-csi-sender.md` |
| 최상위 디렉터리 추가/삭제 | `doc/README.md`(레이아웃) · 루트 `README.md` · `CLAUDE.md` |
| 의존성 추가 (pip 등) | `doc/overview/architecture.md`(Python 환경) · `scripts/README.md`(의존성 절) |

## 기록 보존 규칙 (중요)

`doc/overview/csi-rate-troubleshooting.md`와 `doc/firmware/csi-poc.md`의 실측 절은 **날짜 붙은 실험 기록**이다. 과거 기록의 수치·결론은 고쳐 쓰지 않는다. 이후 상황이 바뀌었으면 다음 형식으로 **추기**한다:

```markdown
- **추기 (YYYY-MM-DD, 커밋 `해시`)**: <무엇이 어떻게 바뀌었는지 한두 문장>
```

현재 상태를 서술하는 문장(토폴로지 설명 등)은 예외로 즉시 고친다 — "지금 이렇다"는 서술이 코드와 다르면 그것이 버그다.

## 문서 스타일

- 한국어로 쓴다. 약어·전문용어(SSOT, DTIM, promiscuous 등)는 첫 등장에서 짧게 풀어 쓴다.
- 표는 주변에 설명 문장을 함께 둔다. 표만 던지지 않는다.
- 너무 간략하게 줄이지 않는다 — 독자가 코드를 열지 않고도 동작을 이해할 수 있어야 한다.
- 알려진 한계·미구현은 숨기지 말고 "현재 구현의 한계" 식으로 명시한다.
