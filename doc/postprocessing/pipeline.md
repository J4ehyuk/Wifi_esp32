# 후처리 파이프라인

수집 JSONL → `tx_seq` 격자 정렬 → 슬라이딩 윈도 → 학습 텐서 `X = (N, 300, RX수×52)`.

구현: [`model_train/model/Preprocessing.py`](../../model_train/model/Preprocessing.py)
(USB·AP 두 파이프라인의 JSONL을 동일하게 처리)

## 실행

```bash
source .venv/bin/activate    # numpy 필요 (quickstart.md §0)

python model_train/model/Preprocessing.py                    # 최신 세션 자동 선택
python model_train/model/Preprocessing.py \
    --session-dir mac_collector_output/raw/20260616/session_21 \
    --rx-ids 102 \
    --label empty
```

| 인자 | 기본 | 의미 |
|------|------|------|
| `--session-dir` | 최신 세션 자동 | `raw/YYYYMMDD/session_<id>` 디렉터리 |
| `--rx-ids` | `102` | 사용할 RX `device_id` 목록 (공백 구분) |
| `--label` | `empty` | 세션 전체 라벨: `empty` / `static` / `action` |

다른 코드에서는 `run_preprocessing(session_dir, rx_ids, label_name)` 함수로 호출합니다
(`LSTM.py`가 이 방식 사용).

## 입력

```text
mac_collector_output/raw/YYYYMMDD/session_<id>/device_<device_id>.jsonl
```

레코드 필수 필드: `device_id`, `tx_seq`, `csi_amp`(펌웨어당 최대 64개, 앞 52개 사용).
**`tx_seq`가 `null`인 v1 레코드는 건너뜁니다** (건수 경고 출력) — 격자 정렬 키가 없기 때문.

## 상수

값은 [architecture.md 상수표](../overview/architecture.md)가 정본입니다.
요약: `F_S=100`, `WINDOW=300`(3초), `STRIDE=30`(0.3초), `N_SUB=52`, 세션 상한 5분.

## 처리 단계

1. **로드** — 세션의 `*.jsonl`을 `device_id`별 버퍼 `(tx_seq, csi_amp)`로 적재, `tx_seq` 오름차순 정렬
2. **tx_seq 격자 정렬** — TX ESP-NOW 카운터는 모든 RX가 같은 프레임에 같은 값을 기록하므로
   네트워크 지터 없는 10ms 클럭입니다. 모든 RX가 겹치는 공통 구간에 1스텝(=10ms) 격자를
   만들고, 빠진 라운드는 서브캐리어별 선형 보간 → `aligned = (RX수, T, 52)`
3. **윈도잉** — `WINDOW`/`STRIDE` 슬라이딩 → `X = (N, 300, RX수×52)`
   (RX축을 feature축으로 병합: RX 1대=52, 3대=156)
4. **라벨** — `--label`값을 `LABEL_MAP`(empty=0, static=1, action=2)으로 변환해
   `y = (N,)` 전체에 부여 (세션 단위 단일 라벨)

주의: TX 보드가 수집 중 재부팅하면 `tx_seq`가 0부터 다시 시작해 격자가 깨집니다 —
그런 세션은 재수집을 권장합니다.

## 다음 단계

`X`, `y`는 [`LSTM.py`](../../model_train/model/LSTM.py)의 입력입니다 —
[lstm-design.md](lstm-design.md) 참고.

```bash
python model_train/model/LSTM.py --epochs 20   # 전처리 + 학습 (PyTorch 필요)
```
