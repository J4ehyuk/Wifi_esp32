# MeshSense 호스트 스크립트

Mac에서 보드 플래시·데이터 수집·시각화를 담당하는 스크립트 모음입니다. 핵심 파일 세 가지를 기준으로 동작합니다.

- `scripts/meshsense_config.json` — 망 설정 SSOT (SSID·채널·수집기 IP/포트). example을 복사해 만듭니다.
- `mac_collector/device_registry.csv` — RX 보드 명단 (`device_id` ↔ USB MAC)
- `mac_collector/tx_registry.csv` — TX 보드 명단 (`tx_node_id` ↔ chip MAC)

## 터미널 가이드 CLI (권장)

```bash
python scripts/meshsense_cli.py          # 메인 메뉴
python scripts/meshsense_cli.py --guide  # [1] 전체 가이드 바로 시작
python scripts/meshsense_cli.py --quick  # 가이드 없이 메뉴만
```

메뉴 구성:

| 메뉴 | 내용 |
|------|------|
| [1] 전체 가이드 | 경로 A 실험 순서(TX 플래시 → Mac Wi-Fi·IP 확인 → RX 플래시 → 수집기)를 단계별 안내 |
| [2] 플래시 | USB MAC으로 registry를 조회해 TX/RX를 자동 분기 플래시 |
| [3] 보드 관리 | registry 등록·삭제·검증 |
| [4] 수집기 실행 | UDP 수집기 실행 (시간 입력 → 종료 후 워터폴 PNG 자동 생성) |
| [5] 사전 점검 | config·ESP-IDF·registry·venv 상태 일괄 확인 |
| [6] esp-csi PoC | **경로 B**: PoC 펌웨어 플래시 + USB 시리얼 수집 (reader 자동 실행, `log/`에 로그 저장) |

플래시 완료 여부는 `mac_collector/flash_state.json`(●/○)에 기록되어 보드 관리 목록에 표시됩니다. 메뉴 [6]의 reader 출력은 화면과 `log/reader_session<id>_dev<id>_<시각>.log` 파일에 동시에 기록됩니다 (`log/`는 git 제외).

**다른 Mac**에서는 플래시 전 `python3 scripts/idf_bootstrap.py -y`와 CLI **[5] 사전 점검**을 권장합니다 (`idf_env.py`가 Homebrew·pyenv·IDF venv PATH를 통일). 상세: [esp-idf-troubleshooting.md](../doc/overview/esp-idf-troubleshooting.md).

## 최초 설정

```bash
git clone --recursive <repo-url>   # esp-idf 서브모듈 포함
cd Wifi_esp32
cp scripts/meshsense_config.example.json scripts/meshsense_config.json
# ap.pass, collector.ip 등 수정 (Mac이 TX SoftAP에서 받은 IP: ipconfig getifaddr en0)

# ESP-IDF 툴체인 (최초 1회, 10–30분·수 GB)
python scripts/idf_bootstrap.py -y
```

이미 clone 한 경우: `git submodule update --init esp-idf`

### ESP-IDF 경로 (프로젝트 로컬)

| 경로 | 설명 |
|------|------|
| `esp-idf/` | git submodule 또는 bootstrap clone (`v5.2.2`) |
| `~/.espressif/` | 툴체인·Python venv (ESP-IDF 기본, 전역) |
| `.espressif/` (프로젝트 루트) | bootstrap 완료 마커 `.meshsense_tools_ready`만 (gitignore) |

`flash_rx.py` / `flash_tx.py`는 실행 시 bootstrap 상태를 확인하고 없으면 자동 준비한 뒤 빌드·플래시합니다. 전역 `~/esp/esp-idf`만 쓰려면 `--skip-idf-bootstrap` (기존 `export.sh` 필요). 오류 시: [doc/overview/esp-idf-troubleshooting.md](../doc/overview/esp-idf-troubleshooting.md).

### Python 의존성

- 플래시·수집기: 표준 라이브러리만 (venv 불필요)
- 워터폴 PNG·후처리: 프로젝트 `.venv` + `pip install -r requirements-viz.txt` (numpy, matplotlib)
- **`csi_serial_reader.py`: `pip install pyserial` 필요** (requirements 파일 미등재)
- USB MAC 읽기: esptool (`pip install esptool` 또는 IDF venv 자동 사용)

## 플래시 (경로 A)

```bash
# TX
python scripts/tx_registry.py add --port /dev/cu.usbmodem101 --board-name TX1
python scripts/flash_tx.py -p /dev/cu.usbmodem101 --monitor

# RX
python scripts/device_registry.py add --port /dev/cu.usbmodem102 --board-name RX1
python scripts/flash_rx.py -p /dev/cu.usbmodem102
```

동작 방식: USB로 보드 MAC을 읽어 registry에서 ID를 찾고, `meshsense_config.json` 값과 함께 CMake `-D` 인자로 빌드에 주입합니다. **경로 B PoC 펌웨어는 이 스크립트 대상이 아닙니다** — `idf.py` 직접 사용 또는 CLI 메뉴 [6].

## meshsense_config.json

| 블록 | 용도 |
|------|------|
| `ap.ssid` / `ap.pass` | TX SoftAP = RX STA 접속 Wi-Fi |
| `ap.channel`, `interval_ms`, `beacon_interval_tu`, `espnow_interval_ms`, … | TX 동작 파라미터 |
| `collector.ip` / `collector.port` | RX → Mac 수집기 주소 |

## Registry

| 대상 | 파일 | CLI |
|------|------|-----|
| RX | `mac_collector/device_registry.csv` | `python scripts/device_registry.py` (list/add/remove/verify/show) |
| TX | `mac_collector/tx_registry.csv` | `python scripts/tx_registry.py` (동일) |

## 파일 목록

| 파일 | 설명 |
|------|------|
| `meshsense_cli.py` | 터미널 메뉴·전체 가이드·플래시·수집·PoC 파이프라인 |
| `flash_rx.py` / `flash_tx.py` | bootstrap → registry 조회 → CMake 주입 빌드·플래시 |
| `device_registry.py` | RX registry CLI |
| `registry.py` / `tx_registry.py` | registry CSV 라이브러리 (+ TX CLI) |
| `flash_state.py` | 플래시 완료 기록 (`mac_collector/flash_state.json`, ●/○) |
| `meshsense_config.py` / `meshsense_config.example.json` | 통합 설정 로드 / 템플릿 |
| `idf_bootstrap.py` | esp-idf 서브모듈 + `install.sh esp32s3` + ruamel.yaml 호환 처리 |
| `idf_env.py` / `idf_paths.py` / `idf_util.py` | `export.sh`·PATH·venv 차이 흡수, `idf.py` 실행 |
| `esptool_mac.py` | esptool로 USB MAC 읽기 |
| `csi_serial_reader.py` | **경로 B 수집기** — USB 시리얼 v2 프레임 → JSONL (pyserial 필요) |
| `measure_csi_hz.py` | 세션 JSONL의 수집률(Hz)·gap·seq 누락 분석 |
| `visualize_csi.py` | 세션 JSONL → RX별 CSI 워터폴 PNG (`csi_waterfall.png`) |

## TODO

- [ ] **`session_meta.yaml` `network:` 자동 동기화**: `meshsense_config.json`의 `ap`/`collector`를 `session_meta.yaml` `network:`에 반영 (run `session_id`는 yaml 전용). 상세: [collector.md](../doc/mac-collector/collector.md)
- [ ] `requirements-viz.txt`에 pyserial 등재 또는 reader 전용 requirements 분리
