# 후처리 파이프라인 (add/main.py)

Mac 수집기가 저장한 JSONL을 읽어 여러 RX의 시간을 맞추고, 슬라이딩 윈도우로 잘라 학습용 텐서 `(N, 3, 52, 200)`을 만드는 스크립트입니다.

현재 구현: [`add/main.py`](../../add/main.py) — 함수 없이 위에서 아래로 실행되는 단일 스크립트로, 상단의 경로·상수를 수정한 뒤 실행합니다.

> **참고**: 이 스크립트는 경로 A(UDP 수집기) 시절 만든 것으로, 수신 시각(`received_at_unix_us`) 기준으로 동작합니다. 경로 B(serial reader) JSONL에도 그대로 쓸 수 있지만, LSTM 학습용 전처리는 `tx_seq` 기준으로 다시 구현된 [`model_train/model/Preprocessing.py`](model-training.md)를 사용합니다. 두 스크립트는 서로 독립입니다.

## 입력

수집기(또는 serial reader) 출력:

```text
mac_collector_output/raw/YYYYMMDD/session_<id>/device_<device_id>.jsonl
```

JSONL 한 줄에서 사용하는 필드는 3개뿐입니다: `device_id`, `received_at_unix_us`, `csi_amp`(float 배열, 펌웨어당 최대 64개).

## 상수 (`add/main.py` 상단)

| 상수 | 값 | 의미 |
|------|-----|------|
| `SESSION_DIR` | `dataset/20260429/session_1` | **기본값이 실험용 경로** — 실제 수집 경로로 반드시 변경 |
| `RX_IDS` | `[101, 102, 103]` | 사용할 RX `device_id` 3대 (환경에 맞게 수정) |
| `F_S` | 100 | 목표 샘플링 주파수 (Hz) |
| `WINDOW` | 200 | 윈도 길이 (100Hz × 2초 = 200 샘플) |
| `STRIDE` | 100 | 윈도 이동 간격 (1초) |
| `N_SUB` | 52 | 사용할 서브캐리어 수 |

## 실행 전 수정할 것

1. **`SESSION_DIR`** — 수집 결과 디렉터리로 변경:

```python
SESSION_DIR = Path("mac_collector_output/raw/20260513/session_1")
```

2. **`RX_IDS`** — 해당 세션에서 실제로 켜 둔 `device_id` 목록과 일치시킵니다. 목록에 있는 장치의 데이터가 하나도 없으면 보간 단계에서 에러가 납니다.

## 처리 단계

1. **로드** — `SESSION_DIR` 아래 모든 `*.jsonl`을 읽어 `device_id`별로 `(수신시각, csi_amp)` 목록을 만듭니다.
2. **시간 동기화** — 세 RX가 모두 데이터를 가진 공통 구간을 찾아 100Hz 격자(`t_grid`)를 만들고, 서브캐리어별 선형 보간으로 `aligned` 배열 `(3, T, 52)`을 만듭니다.
3. **윈도잉** — 2초 윈도우를 1초씩 밀며 잘라 `(N, 3, 52, 200)` 텐서 `X`를 만듭니다. 축 순서는 (윈도 수, RX, 서브캐리어, 시간)입니다.

## 현재 구현의 한계 (알고 쓰기)

- **결과를 파일로 저장하지 않습니다.** `X`, `y`는 메모리에만 있고 shape을 콘솔에 출력할 뿐입니다. 저장하려면 `np.save` 등을 직접 추가해야 합니다.
- **라벨 `y`는 랜덤 더미입니다** (`np.random.randint(0, 3, ...)`). 실제 라벨링은 구현되어 있지 않습니다.
- **64→52는 "유효 톤 선별"이 아니라 앞 52개 절단입니다.** 보간 루프가 `N_SUB=52`개 열만 읽는 방식이라, 정확한 OFDM 유효 톤 매핑이 필요하면 인덱스 매핑을 추가해야 합니다.
- 패킷을 수신 시각순으로 정렬하는 코드가 주석 처리되어 있어, UDP 도착 순서가 뒤섞이면 보간 입력이 비단조가 될 수 있습니다.

## 실행

```bash
source .venv/bin/activate   # numpy 필요
# add/main.py 상단 SESSION_DIR, RX_IDS 수정 후
python add/main.py
```

## Python 환경

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-viz.txt   # numpy, matplotlib
```

`meshsense_cli`의 사전 점검·수집 종료 후 PNG 생성 시에도 이 `.venv`를 사용하며, 없으면 생성을 안내합니다. ESP-IDF 빌드용 Python venv와는 별개입니다. 개요: [architecture.md](../overview/architecture.md).

## 다음 단계

이 텐서로 학습까지 이어가는 코드는 아직 없습니다. LSTM 학습은 별도 파이프라인인 [model-training.md](model-training.md) (`model_train/`)를 참조하세요.
