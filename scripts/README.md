# MeshSense 호스트 스크립트

호스트(Mac)에서 쓰는 CLI·플래시·registry·수집 보조 도구 모음입니다.
최초 셋업 명령은 [quickstart.md](../doc/overview/quickstart.md) §0이 정본입니다.

## CLI 메뉴 맵

```bash
python scripts/meshsense_cli.py           # 메인 메뉴
python scripts/meshsense_cli.py --quick   # 안내 문구 없이 메뉴만
python scripts/meshsense_cli.py --guide   # AP 파이프라인 전체 가이드 바로 시작
```

```text
메인
├─ [1] USB 수집 (esp-csi PoC · USB 시리얼 100Hz)
│    ├─ [1] 보드 플래시 (PoC, MAC 자동 매칭)
│    ├─ [2] 수집 (USB 시리얼, 시간 입력)
│    └─ [3] 보드 관리 (registry 등록·검증)
├─ [2] AP 실시간 수집 (SoftAP + UDP)
│    ├─ [1] 전체 가이드 (설정 → TX → Wi-Fi → RX → 수집)
│    ├─ [2] 보드 플래시 (USB · MAC → TX/RX 자동)
│    ├─ [3] 수집기 실행
│    ├─ [4] 사전 점검
│    └─ [5] 보드 관리
└─ [3] 종료
```

- 플래시는 USB MAC으로 `tx_registry.csv`/`device_registry.csv`를 조회해 자동 분기
- 플래시 완료 여부는 `mac_collector/flash_state.json`(●/○)에 기록되어 보드 관리에 표시
- 다른 Mac 온보딩 시 `idf_bootstrap.py -y` 후 **[2]→[4] 사전 점검** 권장
  ([esp-idf-troubleshooting.md](../doc/overview/esp-idf-troubleshooting.md))

## 스크립트 목록

| 파일 | 설명 |
|------|------|
| `meshsense_cli.py` | 메뉴 CLI — 두 파이프라인의 플래시·수집·registry·사전 점검 |
| `flash_tx.py` / `flash_rx.py` | AP 파이프라인 TX/RX: bootstrap → registry 조회 → build·flash |
| `csi_serial_reader.py` | USB 파이프라인 reader: 시리얼 바이너리 프레임 → JSONL (pyserial) |
| `visualize_csi.py` | 세션 JSONL → CSI 워터폴 PNG (`.venv` 필요) |
| `measure_csi_hz.py` | 세션 JSONL → RX별 Hz·gap·seq_drop 요약 (진단용) |
| `meshsense_config.py` / `meshsense_config.example.json` | 망 설정 SSOT 로드 / 템플릿 |
| `registry_core.py` | RX/TX registry CSV 공통 로직 (load/save/verify) |
| `registry.py` / `device_registry.py` | RX registry 라이브러리 / CLI |
| `tx_registry.py` | TX registry 라이브러리 + CLI |
| `session_meta.py` | `session_meta.yaml` `session_id` 파서 (공용 단일 구현) |
| `flash_state.py` | `flash_state.json` 플래시 완료 추적 |
| `esptool_mac.py` | esptool로 USB MAC 읽기 |
| `idf_bootstrap.py` | esp-idf submodule + `install.sh esp32s3` → `.espressif/` 마커 |
| `idf_env.py` / `idf_paths.py` / `idf_util.py` | `export.sh` 래핑·경로 상수·`idf.py` subprocess |

## 수동 플래시 (AP 파이프라인)

```bash
python scripts/tx_registry.py add --port /dev/cu.usbmodem101 --board-name TX1
python scripts/flash_tx.py -p /dev/cu.usbmodem101 --monitor

python scripts/device_registry.py add --port /dev/cu.usbmodem102 --board-name RX1
python scripts/flash_rx.py -p /dev/cu.usbmodem102
```

- 전역 `~/esp/esp-idf`만 쓰려면 `--skip-idf-bootstrap`
- 보드 전환 시 `--clean -y`
- USB 파이프라인 플래시는 CLI `[1]→[1]` ([usb-collection.md](../doc/pipeline/usb-collection.md))

## meshsense_config.json

| 키 | 용도 |
|----|------|
| `ap.ssid` / `ap.pass` | TX SoftAP = RX STA 접속 Wi-Fi |
| `ap.channel` / `ap.max_conn` | SoftAP 설정 |
| `ap.beacon_interval_tu` / `ap.espnow_interval_ms` | 비콘·ESP-NOW 주기 |
| `collector.ip` / `collector.port` | RX → Mac 수집기 UDP 목적지 |
| `rx.espnow_only` | true면 ESP-NOW 프레임 CSI만 전송 (`CSI_ESPNOW_ONLY=1`) |

## Registry

| 대상 | 파일 | CLI |
|------|------|-----|
| RX | `mac_collector/device_registry.csv` | `python scripts/device_registry.py` |
| TX | `mac_collector/tx_registry.csv` | `python scripts/tx_registry.py` |

## TODO

- [ ] `session_meta.yaml` `network:` ↔ `meshsense_config.json` 자동 동기화
  ([collector.md](../doc/mac-collector/collector.md))
- [ ] `mac_collector` ↔ `scripts` 패키지화 (`sys.path` 조작 제거)
