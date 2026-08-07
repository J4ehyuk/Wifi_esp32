# TX/AP 노드 펌웨어 (경로 A)

`esp32s3_tx_ap_node` — 경로 A(UDP/AP)에서 송신기 겸 공유기 역할을 하는 보드입니다. 하는 일은 세 가지입니다.

1. **SoftAP** — RX 보드와 Mac이 접속할 WiFi를 엽니다 (기본 `MeshSense_TX_AP` / `mstx1234`, 채널 6, 비콘 100TU, **HT20 강제**)
2. **ESP-NOW 송신 (10ms = 100Hz)** — RX의 CSI 콜백을 유발하는 주 트래픽. 접속한 RX(STA)가 있으면 각 RX로 **unicast**(DTIM 게이팅 회피), 없으면 broadcast로 전환합니다. payload는 4바이트 송신 순번입니다.
3. **UDP heartbeat (10ms, 포트 3333)** — `192.168.4.255`로 뿌리는 보조 자극 패킷(magic `0x5458`). 현재 이 패킷을 받는 프로그램은 없으며 CSI 자극 용도로만 존재합니다.

이 구성으로 실측된 CSI 수집률은 약 22Hz가 한계였고, 그 분석 기록이 [csi-rate-troubleshooting.md](../overview/csi-rate-troubleshooting.md)에 있습니다. 100Hz 수집이 필요하면 [경로 B](csi-poc.md)를 사용하세요.

## 소스 구성

- `main/tx_ap_main.c` — 단일 소스. SoftAP 초기화 → ESP-NOW 초기화 → 송신 태스크 2개 생성
- `CMakeLists.txt` — 아래 파라미터를 CMake cache 변수로 정의 (cache 이름 = C 매크로 이름)
- `sdkconfig.defaults` — **AMPDU TX/RX 비활성** (CSI 타이밍 지터 완화, 트러블슈팅에서 확정)
- CSI 기능 자체는 꺼져 있습니다 (`CONFIG_ESP_WIFI_CSI_ENABLED` 미설정) — 순수 송신기입니다

## 사전 준비

- ESP-IDF v5.2.2 (`python scripts/idf_bootstrap.py -y`가 자동 준비)
- `mac_collector/tx_registry.csv`에 보드 등록 — [scripts/README.md](../../scripts/README.md)
- `scripts/meshsense_config.json` (example 복사 후 수정)

## 플래시 (권장)

```bash
cp scripts/meshsense_config.example.json scripts/meshsense_config.json

python scripts/tx_registry.py add --port /dev/cu.usbmodem101 --board-name TX1
python scripts/flash_tx.py -p /dev/cu.usbmodem101 --monitor
```

플래시 스크립트가 하는 일: `meshsense_config.json`의 `ap.*` 값과 `tx_registry.csv`의 `tx_node_id`를 CMake `-D` 인자로 빌드에 주입합니다 (sdkconfig는 건드리지 않음). run 구분용 `session_id`는 Mac의 `session_meta.yaml`에서 관리하며 펌웨어에는 없습니다.

## 설정 키 → CMake 변수 대응

| meshsense_config.json | CMake / 매크로 | 기본값 |
|----|--------|--------|
| `ap.ssid` / `ap.pass` | `TX_AP_SSID` / `TX_AP_PASS` | `MeshSense_TX_AP` / `mstx1234` |
| `ap.channel` | `TX_AP_CHANNEL` | 6 |
| `ap.max_conn` | `TX_AP_MAX_CONN` | 4 |
| `ap.broadcast_port` | `TX_AP_BROADCAST_PORT` | 3333 |
| `ap.interval_ms` | `TX_AP_INTERVAL_MS` (UDP heartbeat) | 10 |
| `ap.beacon_interval_tu` | `TX_AP_BEACON_INTERVAL_TU` | 100 |
| `ap.espnow_interval_ms` | `TX_AP_ESPNOW_INTERVAL_MS` | 10 |
| `ap.payload_bytes` | `TX_AP_PAYLOAD_BYTES` | 64 |
| (tx_registry.csv) | `TX_AP_NODE_ID` | 1 |

비밀번호가 8자 미만이면 SoftAP가 **개방형(OPEN)** 으로 열리는데, RX 펌웨어는 WPA2를 요구하도록 하드코딩되어 있어 접속하지 못합니다. 비밀번호는 8자 이상을 유지하세요.

## RX와 맞출 것

같은 `meshsense_config.json`의 `ap.ssid` / `ap.pass`가 RX 플래시 때 STA 접속 정보로 함께 주입되므로, 별도 파일을 맞출 필요가 없습니다.

## 동작 확인 (모니터 로그)

정상 부팅 시 순서대로:

```text
SoftAP started ssid=... channel=6 max_conn=4 beacon=100TU auth=WPA2
ESP-NOW broadcaster ready ch=6 interval=10ms
UDP broadcast: :3333 every 10ms payload=64B
```

이후 ESP-NOW 패킷 500개마다 송신 카운터가 출력됩니다:

```text
esp_now seq=... api(ok=... fail=...) tx_done(ok=... fail=...)
```

`api ok`가 5초당 +500(=100Hz)이면 송신 측은 정상입니다. RX가 접속하면 `station ... join` 로그와 함께 해당 STA가 ESP-NOW unicast 대상에 추가됩니다.

## 수동 빌드 (고급)

```bash
cd esp32s3_tx_ap_node
idf.py set-target esp32s3
idf.py -DTX_AP_SSID="MeshSense_TX_AP" -DTX_AP_PASS="mstx1234" -DTX_AP_NODE_ID=1 build
idf.py -p /dev/tty.usbmodemXXXX flash monitor
```

## 트러블슈팅

- **registry에 MAC 없음**: `python scripts/tx_registry.py add --port …`
- **RX가 접속 못 함**: `meshsense_config.json`의 `ap` 블록 확인, 비밀번호 8자 이상인지 확인
- **Mac이 패킷을 못 받음**: Mac이 RX보다 **먼저** SoftAP에 접속해 192.168.4.2를 받았는지 확인 ([csi-rate-troubleshooting.md](../overview/csi-rate-troubleshooting.md) 하단 IP 이슈)
- **IDF_PATH 없음**: `export.sh` 실행 또는 [esp-idf-troubleshooting.md](../overview/esp-idf-troubleshooting.md)
