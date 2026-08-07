# LSTM 모델 학습 (model_train/)

경로 B(USB 시리얼)로 수집한 CSI 데이터를 3초 윈도우로 잘라, PyTorch LSTM으로 행동 3-class(**empty / static / action**)를 분류하는 학습 코드입니다. 2026-05-25 `feat/model` 브랜치에서 병합되었습니다.

## 파일 구성

```text
model_train/
├── LSTM_DESIGN.md            설계 노트 (한국어, 14개 절 — 왜 이런 구조인지 상세 설명)
└── model/
    ├── Preprocessing.py      JSONL → (N, 300, 52) 텐서 + 라벨 (import 시 전체 실행)
    └── LSTM.py               LSTM 모델 정의 + 학습 루프 (python LSTM.py 로 실행)
```

## 전처리 — Preprocessing.py

`add/main.py`와 비슷한 일을 하지만 **별개 구현**입니다. 가장 큰 차이는 시간 동기화 기준입니다.

| | `add/main.py` (경로 A 계열) | `Preprocessing.py` (경로 B 전용) |
|---|---|---|
| 동기화 기준 | Mac 수신 시각 (`received_at_unix_us`) | TX 송신 카운터 (`tx_seq`) |
| 입력 가능 JSONL | 경로 A·B 모두 | **경로 B만** (`tx_seq` 없으면 KeyError) |
| 윈도 / stride | 200 / 100 (2초 / 1초) | 300 / 30 (3초 / 0.3초) |
| RX 대수 | 3대 `[101, 102, 103]` | 1대 `[102]` (현재 설정) |
| 출력 shape | `(N, 3, 52, 200)` | `(N, 300, 52)` |

`tx_seq`는 TX가 ESP-NOW payload에 실어 보내는 송신 순번으로, 모든 RX가 같은 프레임에 같은 값을 기록하기 때문에 수신 시각보다 정확한 동기화 키가 됩니다. TX가 10ms마다 1씩 증가시키므로 "seq 1칸 = 10ms"로 간주하고 seq 격자에 선형 보간합니다.

### 주요 상수 (`Preprocessing.py` 상단)

| 상수 | 값 | 의미 |
|------|-----|------|
| `SESSION_DIR` | `<repo>/mac_collector_output/raw/20260525/session_2` | 입력 세션 폴더 (수정해서 사용) |
| `RX_IDS` | `[102]` | 사용할 RX (여러 대로 늘리면 feature 수가 52×대수로 증가) |
| `WINDOW` / `STRIDE` | 300 / 30 | 3초 윈도, 0.3초 간격 (겹침 큼) |
| `MAX_SESSION_SAMPLES` | 30000 | 세션당 최대 5분(100Hz)까지만 사용 |
| `N_SUB` | 52 | 서브캐리어 64개 중 앞 52개 사용 (`a[:52]` 절단) |
| `LABEL_MAP` | empty=0, static=1, action=2 | 클래스 번호 |

### 출력 shape에 대한 주의

코드 주석과 `LSTM_DESIGN.md`에는 출력이 `(N, 300, 156)`(RX 3대 × 52)로 적혀 있지만, **현재 커밋된 설정은 `RX_IDS = [102]` 1대라서 실제 출력은 `(N, 300, 52)`** 입니다. `LSTM.py`의 `INPUT_SIZE = 52`도 이 1대 기준에 맞춰져 있습니다. RX를 3대로 늘리면 feature가 156이 되므로 `INPUT_SIZE`도 함께 바꿔야 합니다 (자동 연동 없음).

### 라벨 처리 (현재는 하드코딩)

세션 폴더의 `session_meta_snapshot.yaml`에서 `experiment.label_target`을 읽어 라벨을 정하는 함수(`read_experiment_meta`)가 있지만 **호출이 주석 처리되어 있고**, 대신 `LABEL_NAME = 'empty'`(class 0)가 하드코딩되어 있습니다. 즉 현재는 한 번 실행하면 **모든 윈도우가 같은 라벨**을 갖습니다. 설계 노트에도 "코드 동작 확인용이며 분류 평가용은 아님"이라고 명시되어 있습니다. 라벨을 바꾸려면 `Preprocessing.py`의 `LABEL_NAME`/`LABEL`/`SPLIT`을 직접 수정하세요. `LABEL_MAP`에 없는 값(예: 현재 `session_meta.yaml`의 `label_target: "mask"`)은 메타 연동을 다시 켤 때 에러가 나니 주의.

## 모델·학습 — LSTM.py

```text
입력 (batch, 300, 52)
  → nn.LSTM(input=52, hidden=128, num_layers=2, batch_first=True)
  → 마지막 타임스텝 출력 (batch, 128)
  → Dropout(0.2) → Linear(128 → 3)
출력 logits (batch, 3)    # softmax 없음 — CrossEntropyLoss가 내부 처리
```

| 하이퍼파라미터 | 값 |
|----------------|-----|
| `BATCH_SIZE` | 32 |
| `LEARNING_RATE` | 1e-3 (Adam) |
| `EPOCHS` | 20 |
| `DROPOUT` | 0.2 (FC 앞단; LSTM 층간 dropout은 미적용) |
| 디바이스 | cuda → mps → cpu 자동 선택 |

학습 후 훈련 데이터 앞 5개 샘플의 logits/확률/예측을 출력하는 디버그 함수(`print_sample_predictions`)가 실행됩니다.

## 실행 방법

```bash
pip install torch          # requirements 파일에 없으므로 직접 설치

cd model_train/model       # 반드시 이 디렉터리에서 — LSTM.py가 `from Preprocessing import ...` (bare import)
python LSTM.py
```

실행하면 ① `Preprocessing.py`가 import 시점에 JSONL 파싱부터 텐서 생성까지 전부 수행하고 ② 20 epoch 학습이 돌며 epoch별 loss/accuracy가 출력됩니다. 캐시가 없어서 **매 실행마다 JSONL을 다시 파싱**합니다.

## 아직 없는 것 (설계 노트 §14 향후 작업)

- train/val/test 분할 (설계 노트 §12에 "세션 단위로 나눠야 함" 정책만 정의됨 — 윈도우가 많이 겹치므로 윈도우 단위 분할 금지)
- `torch.save` 모델 저장 / 불러오기
- confusion matrix 등 평가 지표
- 라벨을 `session_meta_snapshot.yaml`에서 자동으로 읽기 (코드는 있고 비활성)
- 여러 세션(여러 라벨) 데이터셋 합치기
- 입력 정규화 — 경로 B JSONL은 raw 진폭이라 정규화가 아직 어디에도 없음

설계 배경과 각 결정의 이유는 [`model_train/LSTM_DESIGN.md`](../../model_train/LSTM_DESIGN.md)에 자세히 정리되어 있습니다.

## 관련 문서

- 데이터 수집(경로 B): [csi-poc.md](../firmware/csi-poc.md)
- 경로 A 계열 후처리: [pipeline.md](pipeline.md)
- 전체 구조: [architecture.md](../overview/architecture.md)
