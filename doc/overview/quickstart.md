# 빠른 시작

MeshSense에는 수집 경로가 2개 있습니다 (구조 설명: [architecture.md](architecture.md)).

- **경로 B — AP 없는 USB 시리얼 (권장, 100Hz)**: 보드 2종을 PoC 펌웨어로 플래시하고 USB로 수집합니다. 터미널 CLI 메뉴 **[6]** 이 플래시부터 수집까지 안내합니다.
- **경로 A — UDP/AP (초기 설계, ~22Hz 한계)**: TX가 SoftAP를 열고 RX가 접속해 UDP로 보냅니다. 아래 단계별 명령이 이 경로입니다.

어느 쪽이든 시작은 같습니다:

```bash
python scripts/meshsense_cli.py
```

메뉴 **[1] 전체 가이드**가 경로 A 순서(TX 플래시 → Mac Wi-Fi 접속 → RX 플래시 → 수집기)를, **[6] esp-csi PoC**가 경로 B(PoC 플래시 → USB 수집)를 안내합니다. 아래는 수동 명령 참고용입니다.

## 0. 호스트 설정 (최초 1회, 공통)

```bash
git clone --recursive <repo-url>
cd Wifi_esp32
cp scripts/meshsense_config.example.json scripts/meshsense_config.json
# collector.ip = TX SoftAP에 접속한 Mac의 IP (ipconfig getifaddr en0, 보통 192.168.4.2)

python scripts/idf_bootstrap.py -y   # esp-idf/ 서브모듈 + ~/.espressif 툴체인 (최초만 오래 걸림)
```

TX/RX 플래시에 들어가는 Wi-Fi·수집기 설정은 `meshsense_config.json` 한 파일만 수정하면 됩니다.
플래시 스크립트는 툴체인이 없으면 bootstrap을 자동 호출합니다. 상세: [scripts/README.md](../../scripts/README.md).
`idf.py` 오류가 나면: [esp-idf-troubleshooting.md](esp-idf-troubleshooting.md).

run 구분용 `session_id`는 `mac_collector/session_meta.yaml`에서 관리합니다. `network:` 블록은 config와 수동으로 맞춰야 합니다 ([collector.md](../mac-collector/collector.md)).

## 경로 A — 단계별 수동 명령

### 1. TX/AP 노드

```bash
python scripts/tx_registry.py add --port /dev/cu.usbmodem101 --board-name TX1
python scripts/flash_tx.py -p /dev/cu.usbmodem101 --monitor
```

상세: [tx-ap-node.md](../firmware/tx-ap-node.md)

### 2. Mac 네트워크·수집기

1. Mac Wi-Fi를 TX SoftAP(`meshsense_config.json`의 `ap.ssid`)에 연결합니다.
2. **RX 보드보다 Mac을 먼저 접속**시키세요. SoftAP의 DHCP는 접속 순서대로 IP를 주기 때문에, RX가 먼저 붙으면 Mac이 `collector.ip`(보통 192.168.4.2)가 아닌 다른 IP를 받아 패킷을 한 개도 못 받습니다 ([csi-rate-troubleshooting.md](csi-rate-troubleshooting.md) 하단 참조).
3. 수집기 실행 (`collector.port`와 CLI `--port` 일치):

```bash
python mac_collector/udp_collector_mvp.py \
  --host 0.0.0.0 --port 9999 \
  --output-dir mac_collector_output \
  --device-registry-csv mac_collector/device_registry.csv \
  --session-meta mac_collector/session_meta.yaml
```

### 3. RX 노드

```bash
python scripts/device_registry.py verify
python scripts/flash_rx.py -p /dev/cu.usbmodem102 --monitor
```

상세: [rx-csi-sender.md](../firmware/rx-csi-sender.md)

### 4. 후처리

[`add/main.py`](../../add/main.py) 상단의 `SESSION_DIR`(기본값이 `dataset/...`으로 되어 있음)과 `RX_IDS`를 수집 결과 경로·장치 목록에 맞게 수정한 뒤:

```bash
python add/main.py
```

상세: [pipeline.md](../postprocessing/pipeline.md)

## 경로 B — PoC 100Hz 수집 (요약)

PoC 펌웨어는 `flash_rx.py`/`flash_tx.py`를 쓰지 않고 `idf.py`로 직접 플래시하거나, CLI 메뉴 **[6]** 을 사용합니다.

```bash
# TX 보드
cd esp32s3_csi_send_poc
idf.py set-target esp32s3 && idf.py -p /dev/cu.usbmodemXXX flash monitor

# RX 보드 (별도 터미널; monitor는 열지 말 것 — reader와 포트 충돌)
cd esp32s3_csi_recv_poc
idf.py set-target esp32s3 && idf.py -p /dev/cu.usbmodemYYY flash

# Mac 수집 (RX 보드당 1개, pyserial 필요)
python scripts/csi_serial_reader.py --port /dev/cu.usbmodemYYY \
  --device-id 101 --session-id 1 --output-dir mac_collector_output
```

플래시 절차·프레임 규격·다중 RX 수집·실측 결과는 [csi-poc.md](../firmware/csi-poc.md)에 정리되어 있습니다.

수집한 데이터로 LSTM을 학습하려면: [model-training.md](../postprocessing/model-training.md)
