# Pilot 6건 Draft GT 대조

Prompt A/B 실험 설계와 문항별 오류 분석을 위한 임시 결과다. 데이터 파트의 1인 작성 Draft GT를 사용했다. 공식 채점은 2인 검수 후 합의된 Reviewed GT로 진행한다.

| 관계 | 일치 / 전체 |
|---|---:|
| R1 | 3 / 6 |
| R2 | 5 / 6 |
| R3 | 4 / 6 |
| R4 | 4 / 6 |
| 합계 | 16 / 24 |

불일치 8개 중 7개는 GT가 P, 모델 출력이 A였고 1개는 GT가 U, 모델 출력이 A였다. `pilot_002`에서 4개, `pilot_004`에서 3개, `pilot_005`에서 1개가 나왔다.

[문항별 비교 CSV](comparison.csv)에는 GT 판정, 모델 판정, 일치 여부, GT 근거 객체 ID, 모델이 출력한 판단 이유가 들어 있다. 판정값의 정확 일치만 집계했다.

## 입력 및 비교 방법

1. 데이터 브랜치 커밋 `b08b750`의 `docs/data/pilot_1115/Pilot/GT.csv`를 읽는다.
2. GT의 `image`를 [items.jsonl](../../store/items.jsonl)의 `image_file`과 연결해 `item_id`를 찾는다.
3. [RUN-PILOT6-BASE-001 예측](../../store/runs/RUN-PILOT6-BASE-001/predictions/)에서 문항별 `output_text`를 JSON으로 읽어 `track1.relations`의 R1–R4 `state`를 GT와 비교한다.
