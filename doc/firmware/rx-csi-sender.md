# RX CSI Sender 펌웨어 (경로 A)

`esp32s3_csi_sender` — 경로 A(UDP/AP)에서 CSI를 실제로 수집하는 보드입니다. TX SoftAP에 STA로 접속한 상태에서 CSI 콜백을 받아, 보드 위에서 1차 전처리까지 마친 진폭 배열을 UDP로 Mac 수집기에 보냅니다.

## 동작 흐름

```text
Wi-Fi STA 접속 (TX SoftAP, HT20 강제, 절전 끔)
  → promiscuous 모드 + CSI 활성화
  → CSI 콜백: "우리 AP의 BSSID에서 온 frame인지" 필터 → 큐에 push (콜백은 즉시 반환)
  → 워커 태스크: 9ms 간격 제한(throttle) 확인
      → raw I/Q에서 진폭 계산 sqrt(I²+Q²), 최대 64개
      → 3점 이동평균 → z-score 정규화 → ±3σ 클리핑
      → 40바이트 v1 헤더 + float32 배열을 UDP 전송
```

설계 포인트 몇 가지 (이유는 [csi-rate-troubleshooting.md](../overview/csi-rate-troubleshooting.md)의 실험으로 확정):

- **promiscuous 모드 필수** — STA 모드만으로는 CSI 콜백이 거의 발생하지 않습니다 (실측 0.2Hz).
- promiscuous를 켜면 주변 모든 프레임이 들어오므로 **BSSID 필터**로 우리 AP 프레임만 남깁니다.
- 콜백 안에서 DSP·전송을 하면 WiFi 드라이버가 막히므로 **큐 + 워커 태스크**로 분리했습니다.
- 전송 간격 하한은 `SEND_INTERVAL_US = 9000`(9ms)입니다. 100Hz 목표에 지터 여유를 둔 값으로, 예전 문서의 10ms에서 조정되었습니다.
- `sdkconfig.defaults`에서 AMPDU TX/RX를 끕니다 (프레임 타이밍 지터 완화).

## 사전 준비

- ESP-IDF v5.2.2, TX SoftAP가 먼저 동작 중이어야 함
- `mac_collector/device_registry.csv`에 보드 등록, `scripts/meshsense_config.json` 준비 — [scripts/README.md](../../scripts/README.md)
- Mac 수집기 실행 준비 ([collector.md](../mac-collector/collector.md))

## 플래시 (권장)

```bash
cp scripts/meshsense_config.example.json scripts/meshsense_config.json

python scripts/device_registry.py verify
python scripts/flash_rx.py -p /dev/cu.usbmodemXXXX
python scripts/flash_rx.py -p /dev/cu.usbmodemXXXX --clean --monitor -y   # 보드 전환 시
```

플래시 스크립트가 USB로 보드 MAC을 읽어 `device_registry.csv`에서 `device_id`를 찾고, 아래 값들을 CMake `-D`로 빌드에 주입합니다.

## 설정 키 → CMake 변수 대응

| 출처 | CMake cache 변수 | C 매크로 | 의미 |
|----|------|------|------|
| `ap.ssid` / `ap.pass` | `CSI_WIFI_SSID` / `CSI_WIFI_PASS` | `WIFI_SSID` / `WIFI_PASS` | TX SoftAP 접속 정보 |
| `collector.ip` / `collector.port` | `CSI_COLLECTOR_IP` / `CSI_COLLECTOR_PORT` | `COLLECTOR_IP` / `COLLECTOR_PORT` | UDP 수집기 주소 (기본 192.168.4.2:9999) |
| `device_registry.csv` | `CSI_DEVICE_ID` | `DEVICE_ID` | 이 보드의 장치 번호 |

주의: **cache 변수 이름(`CSI_*`)과 매크로 이름이 다릅니다.** 수동 빌드 시 `-DWIFI_SSID=...`가 아니라 `-DCSI_WIFI_SSID=...`를 써야 합니다.

**수집기 IP는 컴파일 시점에 고정됩니다.** 실행 중 재탐색이 없으므로, Mac이 SoftAP에서 다른 IP를 받으면 패킷이 전부 버려집니다. Mac을 RX보다 먼저 접속시키거나, IP가 바뀌었으면 `collector.ip` 수정 후 재플래시하세요 ([csi-rate-troubleshooting.md](../overview/csi-rate-troubleshooting.md) 하단 IP 이슈).

## device_registry.csv (RX 보드 명단)

```bash
python scripts/device_registry.py add --port /dev/cu.usbmodemXXXX --board-name RX4
python scripts/device_registry.py list
```

보드마다 고유한 `device_id`(101부터)를 부여합니다. 두 보드가 같은 ID로 플래시되면 수집기의 seq 통계가 뒤엉킵니다(음수 drop). MeshSense에서는 `CSI_DEVICE_ID=0`(MAC 자동 ID)을 쓰지 않습니다.

## 동작 확인 (모니터 로그)

```text
device_id=101
UDP target: 192.168.4.2:9999
Wi-Fi power save disabled (CSI target 100Hz)
connected with MeshSense_TX_AP, ... BW20
AP BSSID locked for CSI filter: xx:xx:xx:xx:xx:xx
CSI enabled (queue=32, worker offload)
5s: cb=N (+Δ, X.XHz) sent=N (+Δ, X.XHz) throttle_drop=N filter_drop=N qdrop=N
```

5초마다 나오는 카운터의 의미: `cb` = CSI 콜백 발생 수, `sent` = UDP로 실제 내보낸 수, `throttle_drop` = 9ms 제한으로 버린 수, `filter_drop` = 다른 장치 프레임이라 버린 수, `qdrop` = 큐가 가득 차 버린 수.

수집률(Hz) 확인: `python scripts/measure_csi_hz.py mac_collector_output/raw/.../session_<id>`

## 수동 빌드 (고급)

```bash
cd esp32s3_csi_sender
idf.py set-target esp32s3
idf.py -DCSI_WIFI_SSID="MeshSense_TX_AP" -DCSI_WIFI_PASS="mstx1234" \
  -DCSI_COLLECTOR_IP="192.168.4.2" -DCSI_DEVICE_ID=101 build
idf.py -p /dev/tty.usbmodemXXXX flash monitor
```

## 트러블슈팅

- **registry에 MAC 없음**: `python scripts/device_registry.py add --port …`
- **수집기에 invalid packet**: `collector.ip`·포트가 실제 Mac IP와 일치하는지 확인
- **cb는 나오는데 sent가 0에 가까움**: 정상일 수 있음 — 경로 A의 구조적 한계(우리 AP 프레임의 CSI 트리거율 5~10%). 100Hz가 필요하면 [경로 B](csi-poc.md) 사용
- **IDF_PATH 없음**: `export.sh` 또는 [esp-idf-troubleshooting.md](../overview/esp-idf-troubleshooting.md)
