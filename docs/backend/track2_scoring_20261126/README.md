# Track 2 예측 결과 등록·채점 (2026-11-26)

| 항목 | 값 |
|---|---|
| Run | **`t2_pilot28_gemma_base`** (영상 4개, 판단 시점 28개) |
| 예측 출처 | `work/model-ab-1123@6ed56dc:ai_model/track2/판단시점_28건_예측결과_인계/` · 선택·위치 원문 56개 SHA-256 일치, 판단 시점·프레임·해상도 28건 모두 백엔드 문항과 일치 |
| GT | `t2-draft-aihub-isObjectA-20261125` (**Draft**: 대상은 AI Hub `isObjectA`, 최초 충돌 시점 미검수) |
| 채점기 | `backend-track2-0.1.0` · result_hash는 `summary_track2.json` |

## 1. 공식 결과: 미산출

명세 App. D.1의 분모는 "검수된 최초 충돌 시점 기준 H(2초) 안에 충돌하는 Positive 문항"입니다. 충돌 시점이 아직 검수되지 않아 **28건 모두 `reference_not_reviewed (Draft)`로 제외**되고, TargetAcc·mIoU·Acc.5는 N/A입니다. 형식은 선택 28/28, 위치 28/28 통과입니다.

또한 이번 결과는 **첫 응답이 아닙니다.** 인계 문서대로 "최초 실행과 보완 실행에서 유효한 응답을 과제별로 모은 것"이라, Run에 `response_policy = valid_responses_collected_across_attempts`, `official = false`로 기록했습니다.

| 과제 | 응답 출처(시도) |
|---|---|
| 선택 | `track2_batch27_v1` 13 · `track2_repair25_v1` 14 · `track2_smoke_f007_v1` 1 |
| 위치 | `track2_batch27_v1` 16 · `track2_repair25_v1` 6 · `track2_box5_v4` 5 · `track2_f007_box_v2` 1 |

공식 점수에는 문항마다 첫 응답(실패 포함)이 필요합니다.

## 2. 진단: Draft 대상 기준 (공식 아님)

충돌 시점을 무시하고 "AI Hub 사고 보행자(`isObjectA`)를 가리켰는가"만 본 값입니다. 명세의 "H초 안에 충돌할 보행자" 질문과 다르므로 발표에서도 진단값으로만 써야 합니다.

| 영상 | 문항 | 모델 선택 | 기준선: 가장 큰 Box | 기준선: 가장 아래 Box | 무작위 기대값 | Box IoU 평균 | IoU≥0.5 |
|---|---|---|---|---|---|---|---|
| 전체 | 28 | **16/28 (57%)** | 23/28 (82%) | 19/28 (68%) | 34% | **0.000** | 0/28 |
| 후보 2명 이상 | 23 | 11/23 (48%) | | | | | |
| 160630 | 16 | 10/16 | 16/16 | 13/16 | 19% | 0.000 | 0/16 |
| 180227 | 7 | 1/7 | 2/7 | 1/7 | 23% | 0.000 | 0/7 |
| 181002 | 3 (후보 1명) | 3/3 | 3/3 | 3/3 | 100% | 0.000 | 0/3 |
| 190430 | 2 (후보 1명) | 2/2 | 2/2 | 2/2 | 100% | 0.000 | 0/2 |

- **선택**: 단순 규칙("가장 큰 Box", "가장 아래 Box")보다 낮습니다. 후보가 1명인 5건은 아무거나 골라도 맞는 문항입니다.
- **위치**: 28건 모두 IoU 0입니다. 0–1000 정규화나 `[y1,x1,y2,x2]` 순서로 바꿔 봐도 평균 IoU가 0.06 미만이라 좌표 형식 문제가 아니라, 사람이 아닌 곳(도로 바닥·가장자리의 납작한 띠 모양)을 짚고 있습니다. 선택한 후보와 위치 Box도 같은 사람이 아닙니다(겹침 0).
- 160630 후반(f099 이후)은 Draft 대상이 1번인데 모델이 4·7번을 골랐습니다. 이 구간이 충돌 이후일 수 있어 충돌 시점 검수 후 분모에서 빠질 수 있습니다.

## 3. 필요한 것

- **태문님**: 영상별 최초 충돌 프레임 번호와 대상 확인 → `python -m backend.tools.track2_data review <file>`로 Reviewed 처리하면 바로 공식 점수가 나옵니다.
- **경흠님**: 문항별 첫 응답(실패·재시도 포함) 원문. 위치 프롬프트도 점검이 필요합니다.

## 파일

`items_track2.csv`(문항별 후보 수, Draft 대상, 선택, Box, IoU, 기준선, 응답 출처), `summary_track2.json`, `t2_pilot28_gemma_base.official.json`.

```bash
python -m backend.tools.track2_data import-handoff t2_pilot28_gemma_base --ref origin/work/model-ab-1123 --base "ai_model/track2/판단시점_28건_예측결과_인계" --response-policy valid_responses_collected_across_attempts
python -m backend.tools.export_track2_scoring docs/backend/track2_scoring_20261126 t2_pilot28_gemma_base
```
