# Track 1 v1.1 rev6 채점 결과 (2026-11-26)

| 항목 | 값 |
|---|---|
| Run | **`v11_a_rev6_pilot6`** (pilot_001–006). 원본 Run: 001·003·005·006 = `v11_rev6_20261125_184805`, 002·004 = `v11_rev6_002_004_20261125_194929` (두 배치의 프롬프트·모델 hash 동일 확인 후 한 Run으로 등록, 문항별 원본 Run ID 보존) |
| 예측 출처 | `work/model-ab-1123@6ed56dc:ai_model/track1/파일럿_6건_채점_인계_20261125/` · raw SHA-256 6건 일치, `decoded_output.txt` = `parsed_output.json` 6건 일치 |
| 프롬프트 | `prompt_v11_a_rev6` (parent rev5) · system `5274b334…` · task `dc423c98…` |
| GT | `1.1-pilot6-reviewed-20261125` (R1–R3 + 보조 4개만 검수) |
| 채점기 | `backend-scorer-0.3.0-v11-review` (채점 코드 commit `ee8dcee`) · result_hash `0555927a…` |

## 결과 (공식, 첫 응답 그대로)

형식 **6/6 통과** (코드 펜스 없음). 7개 판정 **23/42**.

| 문항 | R1 | R2 | R3 | 연결부 이용자 | 전방 가림 | 측방 가림 | 병목 | 맞음 |
|---|---|---|---|---|---|---|---|---|
| 001 | P/P ✅ | U/P ❌ | P/A ❌ | U/P ❌ | A/A ✅ | P/A ❌ | A/A ✅ | 3/7 |
| 002 | P/P ✅ | U/P ❌ | P/A ❌ | U/P ❌ | P/A ❌ | P/A ❌ | P/A ❌ | 1/7 |
| 003 | A/P ❌ | P/P ✅ | A/A ✅ | A/P ❌ | A/A ✅ | A/A ✅ | A/A ✅ | 5/7 |
| 004 | P/P ✅ | P/A ❌ | P/P ✅ | A/NA ❌ | P/P ✅ | P/P ✅ | P/P ✅ | 5/7 |
| 005 | U/P ❌ | P/A ❌ | A/A ✅ | P/NA ❌ | A/A ✅ | A/A ✅ | A/A ✅ | 4/7 |
| 006 | P/P ✅ | P/P ✅ | P/A ❌ | P/P ✅ | P/A ❌ | A/A ✅ | A/A ✅ | 5/7 |

(GT/예측)

| 지표 | 값 |
|---|---|
| V1 형식 통과 | 6/6 |
| V6 P 재현율 | 7/12 |
| V7 오탐률 (GT A를 P로) | 1/3 |
| V8 U 재현율 | **0/3** |
| V9 과잉 보류 | 0/15 |
| V5 | N/A (`R2.A`, `R3.U` 칸 정답 없음) → Supported-class F1(7칸) **0.324** |
| 보조 정답 | 연결부 이용자 1/6 · 전방 가림 4/6 · 측방 가림 4/6 · 병목 5/6 |

이전 대비: v1.1 A/B 첫 응답은 공식 0/42(코드 펜스로 전부 형식 실패), 펜스 제거 진단으로도 A 8/42 · B 6/42였습니다. rev6는 형식 문제가 해결되어 공식 23/42입니다.

남은 오류 경향 (6장 기준):
- **U를 여전히 답하지 않습니다.** GT U 5칸(001·002의 R2·연결부 이용자, 005의 R1)을 모두 P로 답했습니다.
- **R3 가림**: GT P 4장 중 3장(001·002·006)을 A로 답했습니다. 004만 맞았습니다.
- **연결부 이용자**: 1/6. 004·005는 NA로 답했는데 GT는 A·P입니다.

## 채점 제외

V3 객체(objects 미검수), V4 근거(evidence 미검수), V10–V12 대응(actions 미검수), V13·V14(진술 검수 없음). 문항 전체 제외는 없습니다.

## 파일

`items_official.csv`(문항 × 7개 판정, 제외 사유), `summary.json`, `v11_a_rev6_pilot6.official.json`. 진단(펜스 제거) 파일도 같이 생성되지만 rev6는 펜스가 없어 공식과 같습니다.

```bash
python -m backend.tools.import_track1_handoff --ref origin/work/model-ab-1123 --base "ai_model/track1/파일럿_6건_채점_인계_20261125" --run-id v11_a_rev6_pilot6
python -m backend.tools.export_v11_scoring docs/backend/v11_rev6_scoring_20261126 v11_a_rev6_pilot6
```
