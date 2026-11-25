# v1.1 Pilot A/B 채점 결과 (2026-11-25)

담당 문혜승 · 경흠님 요청(문항별 채점 결과, 채점 제외 사유, 사용한 GT 버전)에 대한 회신입니다.

## 1. 기준

| 항목 | 값 |
|---|---|
| Run | **A** `v11_a_e18f74ffcc` (`prompt_v11_a`) · **B** `v11_b_9895a83702` (`prompt_v11_b`), 각 pilot_001–006 |
| 예측 출처 | `8e0a628:docs/model/v11_ab_handoff/` (실행기록.json의 파일 SHA-256 48개 모두 일치, system prompt hash = 백엔드 `prompt_v11_a/b`) |
| 정답(GT) | **`1.1-pilot6-reviewed-20261125`** (`work/pilot-gt-review@619ff69:data_handoff/pilot6/pilot6_reviewed_gt.jsonl`), 6건 모두 `Reviewed`, 검수자 기록 있음 |
| 스키마 | `1.1-review` |
| 채점기 | `backend-scorer-0.3.0-v11-review` · 채점 코드 commit `5a5e962` (v1.1 통합본, 이번에 채점 코드는 수정하지 않음) |
| 채점 범위 | GT `reviewed_fields`의 7개 판정: 핵심 R1·R2·R3 + 보조 연결부 이용자·전방 가림·측방 가림·병목 |

## 2. 공식 결과 (첫 응답 그대로)

요청하신 대로 첫 응답의 `invalid_output` 상태를 유지했습니다. 12건 모두 `decoded_output.txt`가 Markdown 코드 펜스(```` ``` ````)로 시작해 JSON 파싱이 첫 글자에서 실패합니다. 형식 오류는 요청 수에서 빼지 않고, 관계·보조 판정에서는 정답을 놓친 것(FN)으로 셉니다.

| Run | 형식 통과 V1 | 7개 판정 정답 | V6 P 재현율 | V7 오탐률 | V8 U 재현율 | V9 과잉 보류 | V5 |
|---|---|---|---|---|---|---|---|
| A | 0/6 | 0/42 | 0/12 | 0/3 | 0/3 | 0/15 | N/A |
| B | 0/6 | 0/42 | 0/12 | 0/3 | 0/3 | 0/15 | N/A |

문항별: [items_official.csv](items_official.csv). 모든 문항: `prediction_status=invalid`, 첫 오류 `JSON parse error: Expecting value: line 1 column 1 (char 0)`, 7개 판정 모두 X.

## 3. 진단 결과 (코드 펜스만 제거 · 공식 점수 아님)

오류 분석용으로, 경흠님 오프라인 진단과 같은 방법(바깥 공백과 앞뒤 코드 펜스 한 쌍만 제거)으로 다시 채점했습니다. 형식 판정은 경흠님 진단과 문항·오류 수까지 같습니다(양쪽 003·004만 통과).

| Run | 문항 | 형식 | 오류 수 | 첫 오류 | 맞은 판정 |
|---|---|---|---|---|---|
| A | 001 | invalid | 6 | `track1: 'context' is a required property` | 0/7 |
| A | 002 | invalid | 1 | `R1 positive evidence must equal declared in_D actors/obstacles` | 0/7 |
| A | 003 | **valid** | 0 | | **6/7** (R1 A→P 오답) |
| A | 004 | **valid** | 0 | | **2/7** (R3·연결부 이용자·전방·측방 가림·병목 오답) |
| A | 005 | invalid | 1 | `connection_actor P requires actor(s) and declared connection region(s)` | 0/7 |
| A | 006 | invalid | 2 | `connection_actor: positive requires region ID` | 0/7 |
| B | 001 | invalid | 6 | `track1: 'context' is a required property` | 0/7 |
| B | 002 | invalid | 2 | `R1 positive evidence must equal declared in_D actors/obstacles` | 0/7 |
| B | 003 | **valid** | 0 | | **4/7** (R1 A→P, R2 P→A, 연결부 이용자 A→NA 오답) |
| B | 004 | **valid** | 0 | | **2/7** (A의 004와 같은 항목 오답) |
| B | 005 | invalid | 3 | `forward_occlusion: negative/NA evidence must be empty` | 0/7 |
| B | 006 | invalid | 1 | `connection_actor P requires actor(s) and declared connection region(s)` | 0/7 |

| Run | V1 | 7개 판정 정답 | V6 | V7 | V8 | V9 | Supported-class F1 (7칸) |
|---|---|---|---|---|---|---|---|
| A (진단) | 2/6 | 8/42 | 3/12 | 1/3 | 0/3 | 0/15 | 0.214 |
| B (진단) | 2/6 | 6/42 | 2/12 | 1/3 | 0/3 | 0/15 | 0.176 |

문항별: [items_diagnostic_fence_stripped.csv](items_diagnostic_fence_stripped.csv). 형식 검사에 실패한 문항도 펜스 제거 후 JSON이 읽히면 모델이 적은 판정값을 `*_pred_unvalidated` 열에 따로 넣었습니다(채점에는 사용하지 않음).

참고 관찰 (6장·진단 기준이라 결론 아님):
- 모델이 **U를 한 번도 답하지 않았습니다**(검증 전 값 포함). 핵심 관계에서 GT가 U인 3칸(001·002의 R2, 005의 R1)을 모두 P로 답했고, 연결부 이용자 GT가 U인 002도 P로 답했습니다(001은 `context` 누락).
- **가림을 A로 답하는 경향**: GT R3=P인 001·002·004·006에서 R3를 A로 답했고, 전방·측방 가림도 대부분 A입니다.
- 003의 R1(GT A)을 양쪽 모두 P로 답했습니다.

## 4. 채점 제외 항목과 사유

| 항목 | 상태 | 사유 |
|---|---|---|
| V3 객체 Box 대조 | 제외 | GT `objects_reviewed=false` (객체 검수 전) |
| V4 근거 ID 일치 | 제외 | GT `evidence_reviewed_fields=[]` (근거 검수 전) |
| V10–V12 대응 | 제외 | GT `actions_reviewed=false` → `action_or_object_roles_not_reviewed` |
| V5 Relation Macro-F1 (9칸) | N/A | 9칸 중 `R2.A`, `R3.U`에 검수 정답이 없음 → 정답이 있는 7칸 평균(Supported-class F1)만 보고 |
| V13·V14 진술 오류 | 미산출 | 사람 진술 검수 입력 없음 (자동 판정하지 않음) |
| 신뢰구간 | N/A | 문항별 Source Group이 백엔드 문항 목록에 없음 |
| 문항 단위 공식 벤치마크 판정 | `eligible=false` | `reference_partial_review` (7개 판정만 검수됨) |
| 문항 전체 제외 | 없음 | 12건 모두 Reviewed 정답이 있어 7개 판정은 채점됨 |

## 5. 파일과 재현

| 파일 | 내용 |
|---|---|
| `items_official.csv` | 공식, 문항 × 7개 판정 (GT / 예측 / O·X / 제외 사유), 근거·대응 제외 사유 |
| `items_diagnostic_fence_stripped.csv` | 진단, 위와 같은 열 + 검증 전 판정값 |
| `summary.json` | Run별 지표, 분모, N/A 사유, result_hash |
| `<run_id>.official.json`, `<run_id>.diagnostic_fence_stripped.json` | 채점기 전체 출력 |

```bash
python -m backend.tools.import_references references data_handoff/pilot6/pilot6_reviewed_gt.jsonl
python -m backend.tools.import_v11_ab --ref 8e0a62838d0df742dd146c122c86eeb9582c34e3
python -m backend.tools.export_v11_scoring docs/backend/v11_ab_scoring_20261125 v11_a_e18f74ffcc v11_b_9895a83702
```
같은 예측·GT·채점 코드로 다시 실행하면 같은 `result_hash`가 나옵니다. 공식 결과는 A·B가 모두 형식 실패라 채점 내용이 같아 `result_hash`도 같습니다.
