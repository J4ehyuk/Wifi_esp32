# 모델 실험 문서

> 상태: **EXPERIMENTAL**

어떤 모델을 시도할지에 대한 후보 비교·선정 근거는
[학습 모델 비교와 선정 권고](model-comparison.md) (**PLANNED**)를 먼저 본다.

모델별 코드와 문서는 같은 디렉터리에 둔다.

```text
model_train/
└── <model-name>/
    ├── Preprocessing.py
    ├── preprocessing.md
    ├── preprocessing-improvement-plan.md
    ├── <Model>.py
    └── model-design-and-training.md
```

현재 모델:

| 모델 | 전처리 | 개선안 | 모델 설계·학습 |
|---|---|---|---|
| LSTM | [preprocessing](lstm/preprocessing.md) | [3-RX preprocessing improvement](lstm/preprocessing-improvement-plan.md) | [model design and training](lstm/model-design-and-training.md) |

각 문서는 현재 코드와 계획을 `EXPERIMENTAL`·`PLANNED`로 구분한다. 모델별
입력 shape, feature, label, split, 학습 설정은 해당 모델 디렉터리의 문서가
기준이다.
