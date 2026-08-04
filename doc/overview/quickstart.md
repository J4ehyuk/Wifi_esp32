# 빠른 시작

## 0. 호스트 설정 (최초 1회 — 이 블록이 셋업 명령의 유일한 정본)

```bash
git clone --recursive <repo-url>
cd Wifi_esp32
cp scripts/meshsense_config.example.json scripts/meshsense_config.json
# collector.ip = TX SoftAP에 접속한 Mac IP (ipconfig getifaddr en0, 보통 192.168.4.2)
# AP 파이프라인만 필요. USB 파이프라인은 config 수정 없이 동작

python scripts/idf_bootstrap.py -y   # esp-idf/ + ~/.espressif (최초만 10–30분)

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-viz.txt  # numpy·matplotlib·pyserial (수집·시각화·후처리)
```

- 이미 clone한 경우: `git submodule update --init esp-idf`
- `idf.py`/빌드 오류: [esp-idf-troubleshooting.md](esp-idf-troubleshooting.md)
- 수집 전 `mac_collector/session_meta.yaml`의 **`session_id`** 를 run마다 갱신 ([collector.md](../mac-collector/collector.md))

## 1. 파이프라인 선택

```bash
python scripts/meshsense_cli.py
```

| 메뉴 | 파이프라인 | 언제 쓰나 |
|------|-----------|----------|
| **[1] USB 수집** | RX 보드를 USB로 연결, 시리얼로 100Hz 수집 | **모델 학습 데이터 수집 (권장)** — 손실 0%, Wi-Fi 설정 불필요 |
| **[2] AP 실시간 수집** | TX SoftAP + RX UDP 무선 전송 | 실시간·무선 배치가 필요할 때 |

두 경로 모두 같은 JSONL 레이아웃으로 저장되어 후처리가 공용입니다 ([architecture.md](architecture.md)).

## 2-A. USB 수집 경로

보드 등록 → CLI `[1] USB 수집 → [1] 보드 플래시 → [2] 수집(시간 입력)` 순서면 끝.
상세와 수동 명령: [usb-collection.md](../pipeline/usb-collection.md)

## 2-B. AP 실시간 수집 경로

CLI `[2] AP 실시간 수집 → [1] 전체 가이드` 가 아래 순서를 단계별로 안내합니다
(`python scripts/meshsense_cli.py --guide` 로 바로 시작).

1. TX 등록·플래시: `tx_registry.py add` → `flash_tx.py`
2. Mac Wi-Fi를 TX SoftAP(`ap.ssid`)에 접속, IP 확인
3. 수집기 실행 (메뉴 `[3] 수집기 실행`)
4. RX 등록·플래시: `device_registry.py` → `flash_rx.py`

상세와 수동 명령: [ap-realtime.md](../pipeline/ap-realtime.md) · [collector.md](../mac-collector/collector.md)

## 3. 후처리·학습

```bash
python model_train/model/Preprocessing.py    # 최신 세션 자동 선택, X=(N, 300, RX수×52)
python model_train/model/LSTM.py --epochs 20 # 전처리 + LSTM 학습 (PyTorch 필요)
```

상세: [pipeline.md](../postprocessing/pipeline.md) · [lstm-design.md](../postprocessing/lstm-design.md)
