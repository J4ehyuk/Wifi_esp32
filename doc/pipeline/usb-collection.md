# USB 수집 파이프라인 (모델 학습 데이터 표준 경로)

esp-csi 공식 예제 기반 펌웨어로 CSI를 수집해 **USB 시리얼로 직접 스트리밍**하는 경로입니다.
Wi-Fi association·IP 네트워크 없이 동작하며, 실측 100Hz·손실 0%로 모델 학습 데이터 수집의
표준 경로입니다 (검증 이력은 하단 부록).

```text
TX (esp32s3_csi_send_poc) ── ESP-NOW broadcast 10ms (tx_seq) ──▶ RX (esp32s3_csi_recv_poc) × N
                                                                  │ CSI cb → ringbuf → USB-Serial-JTAG
Mac ◀── USB (921600 baud, 바이너리 프레임) ── scripts/csi_serial_reader.py × N → JSONL
```

실행은 CLI 메뉴 **[1] USB 수집**:
`[1] 보드 플래시 (PoC, MAC 자동 매칭) · [2] 수집 (USB 시리얼, 시간 입력) · [3] 보드 관리`

## 펌웨어 구성

| 디렉터리 | 역할 |
|----------|------|
| `esp32s3_csi_send_poc` | ESP-NOW 10ms broadcast 송신 (페이로드에 `tx_seq` 카운터) |
| `esp32s3_csi_recv_poc` | CSI 콜백 수신 → ring buffer → USB-Serial-JTAG 바이너리 스트리밍 |

esp-csi upstream 예제와의 차이:

- **토폴로지** — AP/STA association 없음. 양쪽 모두 `WIFI_MODE_STA`, STA MAC을
  `1a:00:00:00:00:00`로 통일(`esp_wifi_set_mac`)하고 RX는 이 MAC의 프레임만 CSI 통과.
  채널 11 고정
- **대역폭 HT20** — raw CSI 128B = 64 서브캐리어 × I/Q 2B. RX CSI config는
  `htltf_en=false`(LLTF only)로 64 SC 유지 (둘 다 켜면 LLTF+HT-LTF concat으로 256B가 됨)
- **USB-Serial-JTAG** — ESP32-S3 보드의 USB-C는 UART0이 아니라 USB-Serial-JTAG 페리페럴.
  `usb_serial_jtag_write_bytes`로 송신 (UART API로는 USB에 안 나감)
- RX `hz_log_task`가 5초마다 `5s: cb=N (+M, Hz) uart=K ... ringbuf_drop=D` 진단 로그 출력.
  cb ≈ uart, `ringbuf_drop=0`이 정상
- `POC_DUMP_CSV` (기본 0, `esp32s3_csi_recv_poc/main/app_main.c`) — 1로 바꾸면 upstream 방식
  CSV 덤프 모드. 921600 baud가 ~50Hz로 병목되므로 속도 측정에는 사용 금지

## 바이너리 시리얼 프레임 (LE, packed) — v2

헤더 32바이트 + raw CSI. CRC 없음 — magic + `raw_len` sanity check로 재동기화.

| 오프셋 | 타입 | 필드 | 비고 |
|---|---|---|---|
| 0 | u16 | magic | `0x4353` ('CS') |
| 2 | u8 | version | 2 (v1은 tx_seq 없음) |
| 3 | u8 | reserved | 0 |
| 4 | u16 | total_len | header + raw |
| 6 | u16 | raw_len | raw[] 바이트 수 (HT20 LLTF = 128) |
| 8 | u32 | seq | RX 부팅부터 단조 증가 (보드별 독립) |
| 12 | u64 | timestamp_us | RX `esp_timer_get_time()` (보드별 독립) |
| 20 | i8 | rssi | dBm |
| 21 | u8 | channel | |
| 22 | i8 | noise_floor | dBm |
| 23 | u8 | rate | rx_ctrl->rate |
| 24 | u16 | sig_len | |
| 26 | u16 | reserved | 0 |
| 28 | u32 | **tx_seq** | TX 송신 카운터 — **모든 RX 공통, cross-RX 동기화 키** |
| 32 | i8[raw_len] | raw CSI (I/Q 교차) | |

reader(`scripts/csi_serial_reader.py`)는 raw int8 I/Q 페어를 `sqrt(I²+Q²)`로 변환해
`csi_amp`로 저장합니다. JSONL 필드는 [udp-packet-schema.md](../mac-collector/udp-packet-schema.md)의
UDP 경로와 호환: `received_at_unix_us`, `session_id`, `device_id`, `seq`, `timestamp_us`,
`channel`, `rssi_dbm`, `noise_floor_dbm`, `tx_seq`, `sample_count`, `csi_amp`.

## 수집 실행

CLI가 권장 경로입니다 — 연결된 보드의 MAC을 registry와 대조해 `device_id`를 자동 매칭하고,
`session_meta.yaml`의 `session_id`로 reader를 병렬 실행합니다.

수동 실행 (reader와 monitor는 포트를 동시에 못 씀에 주의):

```bash
python scripts/csi_serial_reader.py \
    --port /dev/cu.usbmodem101 \
    --device-id 101 \
    --session-id 1 \
    --output-dir mac_collector_output
```

출력: `mac_collector_output/raw/YYYYMMDD/session_<id>/device_<id>.jsonl`
(UDP 파이프라인과 동일 레이아웃 — 후처리 공용, [pipeline.md](../postprocessing/pipeline.md))

### Multi-RX 동시 수집

RX 보드 N개를 USB로 연결하면 각각 독립 포트(`/dev/cu.usbmodem*`)로 잡히고 대역 충돌이
없습니다. 보드별 `device_id`만 다르게, `--session-id`는 같게 하여 reader N개를 병렬 실행
(CLI `[2] 수집`이 자동으로 수행). 각 보드의 `seq`/`timestamp_us`는 부팅 시각이 달라 독립이지만,
같은 ESP-NOW broadcast를 받은 보드들은 **동일한 `tx_seq`** 를 기록하므로 후처리에서
`tx_seq`를 join key로 정렬합니다.

### 알려진 제약

- ESP_LOG(5초 진단)와 바이너리 스트림이 같은 USB-CDC를 공유 — reader가 magic resync로
  복구하지만 5초에 1회 1~2 프레임 손실 가능(~0.4%). 더 엄격하면 sdkconfig
  `CONFIG_LOG_DEFAULT_LEVEL_NONE=y`
- RX ring buffer 64KB ≈ 2초분. reader가 2초 이상 멈추면 `ringbuf_drop` 증가

## 빌드·플래시 (수동, 고급)

PoC 펌웨어는 CMake cache 파라미터가 없어 `flash_rx/tx.py` 대상이 아닙니다.
CLI `[1] 보드 플래시`가 권장 경로이고, 수동은 `idf.py` 직접:

```bash
cd esp32s3_csi_send_poc   # TX 먼저, 이후 esp32s3_csi_recv_poc
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash monitor   # RX monitor는 -b 921600
```

RX는 `esp_csi_gain_ctrl` managed component를 자동 다운로드합니다 (ESP-IDF v5.2.2 검증).

## 부록 — 검증 이력

배경: AP 파이프라인 초기 구현이 22Hz 천장에 막혀([csi-rate-troubleshooting.md](../overview/csi-rate-troubleshooting.md))
esp-csi 예제 기반으로 재구성한 경로가 이 파이프라인입니다.

- **Hz 검증 (2026-05-22)** — RX 5초 카운터 평균 97.5Hz (목표 100Hz 사실상 달성)
- **USB 스트리밍 검증 (2026-05-23)** — reader 측 구간 500 frames/5s = 100Hz 정확,
  `invalid=0`, `seq_drop=0` (전 파이프라인 손실 0%), `tx_seq` 단조 증가 확인

## 참고

- esp-csi: https://github.com/espressif/esp-csi
- ESP32-S3 CSI 가이드: https://docs.espressif.com/projects/esp-idf/en/v5.2.2/esp32s3/api-guides/wifi.html#wi-fi-channel-state-information
