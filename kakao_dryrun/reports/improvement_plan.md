# 개선 계획: 데이터·정답과 모델 문제 분리

| 우선순위 / 구분 | 관측 근거 | 다음 작업 | 완료 기준 |
|---|---|---|---|
| P0 / Rule | PDF와 ZIP의 Roadside/Obstacle 예외 및 allowed pairs 차이 | 담당자가 canonical rule version을 확정하고 schema/prompt/reference/evaluator를 함께 versioning | Human adjudication 승인 및 version 고정, 변경 전후 점수 병기 |
| P0 / GT | 16개 모두 Draft, Source class codebook 미제공, coverage partial | 독립 reviewer 2인이 class/Box/C/footprint/entrance 경계와 대안 evidence를 확인 | 25개 검토 항목 합의 기록, Reviewed 범위와 미검수 범위 구분 |
| P0 / 평가 범위 | F의 모든 Object가 분모이며 speed_bump·작은/가린 대상도 포함 | 모델 결과를 보기 전에 포함 기준과 전체/크기/역할별 subset 정의 | 전체 denominator 유지와 별도 subset 진단, 불완전 GT의 FP/F1 확정 금지 |
| P1 / Format | NF4·QLoRA 원래 prompt에서 regions 누락 | 검증한 required-fields prompt를 후보로 고정하고 다양한 Dev 장면에서 strict first-pass 평가 | First-pass와 retry를 분리한 valid JSON/schema rate 및 비용 |
| P1 / Grounding | Left truck class confusion, 작은 pedestrian·scooter·원거리 객체 누락 | Class vocabulary와 가시 extent annotation을 정제한 Dev set으로 input resolution/crop strategy를 통제 비교 | 동일 장면·동일 prompt·decode 조건의 class/size별 match, crop 좌표 roundtrip 검증 |
| P1 / Relation | 주요 차량 3개를 찾아도 evidence=[] 및 all-A | P/A/U 구별과 Object→role→Relation 연결을 supervised target에 일관되게 반영 | Reviewed held-out set에서 state와 geometry-grounded evidence를 별도 평가 |
| P1 / Action | all-A에서 MONITOR/no_condition, required 0/4 | canonical rule에 맞춘 조건부 대응 target 구성 및 consistency 검사 | Group 충족, allowed/forbidden, based_on consistency를 따로 보고 |
| P2 / Training | 단일 Draft를 5 step 학습, 저장/reload 정상이나 semantic 개선 없음 | Source-group 단위 Train/Dev/Test를 먼저 분리하고 충분한 Reviewed data 확보 후 학습 | Leakage 없는 held-out evaluation, baseline과 동일 측정 조건 |

Format 실패를 score=0으로 치환하거나 missing field를 parser로 채워 semantic 평가를 통과시키지 않습니다. GT 수정과 모델 변경을 같은 실험에 섞지 않고, 승인된 GT/rule 변경이 생기면 원본 및 변경 전후 결과를 함께 보존합니다.
