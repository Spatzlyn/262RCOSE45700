# Data readiness — integrated-sample-0.2

이 run은 독립 장면 1개의 입력·출력·평가 경로을 검증합니다. 일반 성능·모델 순위·학습 일반화를 추정하지 않습니다.

| 항목 | 확인 결과 |
|---|---|
| PDF | `Kakao_Road_VLM_Benchmark_Spec_Final.pdf`, 25 pages, 생성 2026-11-05 14:23:48 KST |
| PDF version | 파일명 Final, 문서 내부 명시적 semantic version 없음. SHA-256을 식별자로 사용 |
| ZIP | `Integrated_Annotation_DryRun (1).zip`, integrated-sample-0.2, guideline pilot-guideline-0.2-draft |
| Git | 원본 실행 디렉터리는 Git repository가 아니었음. 이 정리본은 dry_run_v1 branch로 별도 게시함. PDF의 aba16a3는 과거 v0 참조이며 현재 코드 revision이 아님 |
| 독립 장면 / Source Group | 1 / 1 |
| 이미지 / 문항 | 4 / 1. F 문항만 정의되어 있음 |
| View / 해상도 | F/B/L/R, 모두 1920×1080 |
| Object | F 16, B 8, L 3, R 8; 총 35 (Source 18 + AI Draft 17) |
| Human Reviewed | 0. 전체 Draft, object coverage incomplete |
| Timestamp | capture_timestamp·frame_index 없음. token 및 export date는 촬영 시각이 아님 |
| Multi-view | 같은 Source Group, 정확한 동기화 미검증. Temporal Sequence 아님 |

모델에는 원본 F 이미지, Intent, 허용된 task field, 공통 규칙과 output schema만 제공합니다. C Polygon, Draft bbox, relation/action 정답, 정답 ID, expected prediction, B/L/R, source metadata는 inference 입력에서 제외합니다. 객체와 Region은 모델이 독립적으로 예측하며, GT 후보를 제공한 진단 실험은 하지 않습니다. 학습 시에만 별도 target으로 패키지의 Draft example을 사용합니다.

Object bbox는 원본 기준 normalized `[x1,y1,x2,y2]`입니다. Relation은 모델의 Object/Region ID 및 역할에 연결되고 Action의 `based_on`은 R1–R4를 참조합니다. C는 평가용 driving area이고 모델 출력 영역이 아닙니다. R3의 hidden Region은 관측 geometry가 null이어서 위치 매칭이 불가능합니다.

| Track | 지금 검증할 내용 | 공식 점수 / 추가 필요 정보 |
|---|---|---|
| Track 1 | 실제 image-only inference, JSON/schema, Draft bbox·role·relation·action 비교 | Reviewed 표본 0이므로 공식 quality 점수 N/A. C·object coverage·entrance·evidence sets·action rule Human Review 필요 |
| Track 2 | `missing_input`/null 출력 형식 | 사건 시점·판단 시점·horizon·시간 순서 frame·미래 target 없음. 분모 0, N/A |
| Track 3 | `missing_input`/null 출력 형식 | Timestamp·관측 Sequence·동기화 GNSS/INS 없음. 분모 0, N/A |

기존 `scripts/evaluate.py`와 validator를 재사용합니다. Object/Region은 같은 class/type, IoU≥0.5에서 maximum-cardinality, 다음으로 total-IoU 최대의 일대일 매칭입니다. ID 문자열 자체로 맞혔다고 처리하지 않습니다. Draft 목록에 매칭되지 않은 예측을 곧바로 hallucination/FP라고 단정하지 않습니다. V3/V4 공식 집계는 패키지 자체가 미구현이고 항상 null입니다. V5도 Reviewed 12 relation-state cell coverage가 없어 N/A입니다. V10–V12는 공식 점수가 아니라 패키지의 Draft action diagnostic만 제시합니다. V13/V14는 사람이 진술을 검수하지 않아 N/A입니다. Source Group 1개이므로 Bootstrap CI도 N/A입니다.

PDF와 ZIP 사이의 중요한 차이가 있습니다. PDF §2.4 및 App. B.2는 R1 점유 대상이 Roadside Vehicle/Obstacle뿐이면 R4의 VERIFY_PASSAGE로 필수 대응을 대체하고 HOLD를 허용으로 둡니다. 반면 ZIP prompt·guideline은 roadside Actor에도 YIELD/HOLD를 요구하며 고정 Obstacle에는 HOLD를 요구합니다. 이번 실행은 재현 가능한 ZIP schema/prompt/evaluator v0.2를 일관되게 적용하고, 이를 PDF 완전 준수 결과로 부르지 않습니다. 배포 전 규칙과 Reference를 합의하고 새 version으로 고정해야 합니다. PDF JSON 예시는 패키지 schema와도 다르므로 그대로 parser에 섞지 않습니다.

Annotation Region의 `model_input_available=false`와 `input_available=true`가 함께 나타납니다. 후자는 관측 근거 가용성을 표현한 field로 보이나 naming이 모호합니다. 실제 입력은 whitelist로 제한하므로 Region 정답이 모델에 들어가지 않습니다. 필드 의미를 명시적으로 분리해야 합니다.

ZIP 내 35개 MANIFEST 항목은 hash가 일치하며 원본 ZIP/PDF hash는 `provenance.json`에 있습니다. 패키지 구조 검사와 30개 기존 evaluator 테스트를 실행했고 로그는 `audit/`에 보존했습니다. Draft 비교·synthetic evaluator 검사·실제 모델 출력은 별도 파일로 구분합니다. Train/test split은 만들지 않습니다.

Source codebook은 제공되지 않았고 `source_codebook_available=false`입니다. 통합 class mapping은 ZIP의 현재 정의를 사용하며 외부 원본 codebook과의 의미 정합성을 독립 검증했다는 뜻은 아닙니다.


## 이번 audit에서 추가 확인한 상태

F Object 16개(Source 10 + AI-added Draft 6), 다른 view/Region 혼입 없음. Human Review 0, 독립 평가 문항 1, 단일 source group 1은 변함없습니다. GT나 판정을 수정하지 않았습니다. PDF/ZIP Action 규칙 충돌과 C/footprint/entrance/occlusion/evidence 대안은 [25개 Human Review 항목](reports/human_review.csv)으로 분리했습니다. Source input은 원본 ZIP의 추출본이며 model input은 F 이미지와 whitelist question만입니다. Training target은 같은 장면의 Draft example이므로 학습 후 결과는 held-out evaluation이 아닙니다. 시간 sequence, GNSS/INS, future event reference는 여전히 없어 Track 2·3 score=null/분모0입니다.
