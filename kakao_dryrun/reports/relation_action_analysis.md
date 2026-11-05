# Relation 0/4와 Action=False 분석

문항은 `sample_front_001` **1개**입니다. R1–R4는 그 문항의 판정 항목 4개이며 독립 장면 4개가 아닙니다. 아래 GT는 모두 보존한 Draft입니다. 실제 출력은 기존 BF16/280 첫 실행에서 JSON fence만 제거한 결과입니다.

| 항목 | Draft GT / evidence | 실제 prediction / evidence | 판정 근거 |
|---|---|---|---|
| R1 | P; F_742187,F_742188,F_742189,F_742190; Region 없음 | A; Object=[], Region=[]; 보이는 Actor나 Obstacle의 지면 접촉 부분이 C와 겹치는 부분이 관측되지 않았습니다. | GT는 관측 접지점이 C 내부인 4개 차량을 근거로 P입니다. 예측은 그중 3개를 찾았지만 evidence를 비웠고, 명확히 관측되지 않는다는 설명으로 A를 택했습니다. C 경계 검수 문제와 관측→관계 연결 실패를 분리해야 합니다. |
| R2 | U; F_742182,F_742185,F_added_001; F_entrance_left_candidates | A; Object=[], Region=[]; C와 연결된 출입구 경계가 명확하게 관측되지 않았습니다. | GT는 보이는 scooter 2개와 pedestrian의 접지 위치·entrance 경계/C 연결이 미확정이라 U입니다. 예측은 Actor를 누락하고 입구를 명확히 관측하지 못했다는 설명으로 A를 택했습니다. 정보 부족과 확인된 부재를 혼동한 출력입니다. |
| R3 | P; F_742188,F_742190,F_742189; F_hidden_road_ahead | A; Object=[], Region=[]; 진행 판단에 필요한 영역을 가리는 Object가 관측되지 않았습니다. | GT는 sedan·box truck·SUV에 의한 occlusion을 P로 기록했습니다. 예측은 이 차량 3개를 모두 찾았으나 occluder 역할을 연결하지 않고 A를 출력했습니다. 숨은 Actor 존재는 별도 U이며 R3와 동일하지 않습니다. Hidden Region geometry는 null이므로 geometry evidence의 완전 검증은 deferred 대상입니다. |
| R4 | P; F_742187,F_742188,F_742189,F_742190; Region 없음 | A; Object=[], Region=[]; Object의 배치가 통행 공간을 제한하는 것으로 판단되지 않았습니다. | GT는 4개 차량의 배치가 통행 공간을 제한한다고 P로 기록했습니다. 예측은 실제 통과 가능성과 무관하게 배치 제한을 판단해야 하지만 근거 없이 A입니다. 좁아짐 P는 통과 불가 확정이 아닙니다. |

State는 4개 모두 불일치합니다. Evidence는 별도로 class/IoU mapping 후 accepted set과 role의 exact equality를 검사합니다. R1은 4개 Actor의 비어 있지 않은 subset 15개를 허용합니다. R2/R3/R4는 등록된 집합 각 1개만 허용하므로 대안 근거 집합의 독립 검수가 필요합니다. C는 reference 전용이므로 예측에 F_C ID를 요구하지 않습니다. R3의 hidden Region geometry=null은 미측정 사유이나, 이번 출력은 Object evidence부터 비어 있어 현재 evaluator 결과는 mismatch입니다. 이를 임의로 deferred로 고치지 않았습니다.

실제 Action은 `MONITOR_AHEAD / no_condition / based_on=[R1,R2,R3,R4]` 1개입니다. 모델의 all-A 출력과는 내부적으로 맞지만 Draft GT와 맞지 않습니다. **allowed set 밖의 pair**이며 ZIP에 열거된 forbidden pair(ADVANCE_WITH_MONITORING) 위반과는 구분합니다.

| group | Draft required | actual | 결과 |
|---|---|---|---|
| 1 | [{"code": "YIELD_IF_OCCUPIED", "condition": "while_corridor_occupied", "based_on": ["R1"]}, {"code": "HOLD_UNTIL_CLEAR", "condition": "while_corridor_occupied", "based_on": ["R1"]}] | MONITOR_AHEAD / no_condition | 미충족 |
| 2 | [{"code": "VERIFY_BEFORE_ADVANCE", "condition": "before_resolving_uncertainty", "based_on": ["R2"]}] | MONITOR_AHEAD / no_condition | 미충족 |
| 3 | [{"code": "VERIFY_BEFORE_ADVANCE", "condition": "before_entering_occluded_area", "based_on": ["R3"]}] | MONITOR_AHEAD / no_condition | 미충족 |
| 4 | [{"code": "VERIFY_PASSAGE", "condition": "before_passing_restricted_section", "based_on": ["R4"]}] | MONITOR_AHEAD / no_condition | 미충족 |

Action evaluator 오류 9개는 다음과 같습니다. 동일 원인에서 파생된 항목이므로 서로 독립적인 오류 9건으로 해석하지 않습니다.

- `action pair outside reference allowed set`
- `required action group 1 not met`
- `required action group 2 not met`
- `required action group 3 not met`
- `required action group 4 not met`
- `action based_on R1 disagrees with reference relation`
- `action based_on R2 disagrees with reference relation`
- `action based_on R3 disagrees with reference relation`
- `action based_on R4 disagrees with reference relation`

## PDF와 ZIP의 차이와 이번 출력에 대한 영향

| 검토 항목 | PDF | ZIP / 실행 evaluator | 이번 판정 영향 |
|---|---|---|---|
| R1 Roadside-only / Obstacle-only 점유 | §2.4, App. B.2: R1 필수 요구를 R4 VERIFY_PASSAGE로 대체, HOLD는 허용 | system.txt/Guideline: roadside Actor도 YIELD/HOLD 필수, fixed Obstacle은 HOLD 필수 | 규칙은 충돌합니다. 다만 현 Draft R1에는 travel_space Actor F_742188도 있으므로 Roadside-only 예외가 적용되지 않습니다. 현재 baseline Action=False가 True로 바뀌지 않습니다. Human Review가 이 객체의 점유/placement를 바꾸면 required group 수가 달라질 수 있습니다. |
| REDUCE_SPEED_IF_MOVING 허용 | App. B.2에서 R1 movable Actor 및 R3에 추가 허용 | sample reference allowed_pairs에는 없음 | 해당 code를 출력한 답은 허용 판정이 달라질 수 있습니다. 현재 baseline에는 없으므로 영향 없음. |
| C의 정의 | §2.1: 도로 구조·Intent로 정하는 가상 Corridor | ZIP: 보이는 무표시 도로의 shared travel space, 정밀 ego trajectory와 구분 | 둘 다 정밀 실제 궤적과 구분하나 operational C 경계를 사람이 합의해야 합니다. 현재 GT polygon을 임의로 축소/변경하지 않았습니다. |
| R2 A/U | 보이는 Actor의 위치/entrance 경계가 불명확하면 U | 같은 원칙, sample은 U | baseline A는 규칙 버전 차이로 설명되지 않습니다. |
| JSON 구조 | App. B.4의 설명용 v0 예시 | integrated-sample-0.2 schema | 구조가 다릅니다. 이번 실행은 ZIP schema 고정이며 PDF 예시로 missing regions를 면제하지 않습니다. |

PDF 규칙으로 다시 채점한 공식 점수는 산출하지 않았습니다. 다른 GT나 대응을 만들지 않고, 적용 가능 조건과 현재 출력의 영향만 구분했습니다. 사람이 확정할 항목은 `human_review.csv`에 남겼습니다.

원문 위치: PDF page 6 (§2.4), page 18 (App. B.2). ZIP `prompts/system.txt`, `ANNOTATION_GUIDELINE.md`, `data/references.jsonl`을 대조했습니다. 원본 PDF는 `source/spec.pdf`에 포함했습니다.
