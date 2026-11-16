# 백엔드 — 채점기 · 저장 구조 · Report API (work/backend-1115)

담당: 문혜승 · 기준 문서: `참고자료/Role_Backend.pdf` §3–6, §9 (`kakao_meeting_1106` 브랜치). 명세서와 다르면 명세서를 따릅니다.

이번 주 범위는 **실제 Run 1개의 채점·저장·조회 연결**입니다(F3 문항 목록 → F5 문항 상세). 통계 모듈 전체와 전체 서비스 배포는 다음 단계입니다.

## 1. 한눈에 보기

| 항목 | 상태 |
|---|---|
| 실제 Run | `RUN-PILOT6-BASE-001`: 경흠님 Pilot 6건(gemma-4-E4B NF4, prompt v1, 첫 응답). **6/6 형식 통과**(V1 = 1.0) |
| 정답(GT) | **아직 아무도 작성하지 않음** → 6건 모두 `annotation_status: Missing`. V3–V12는 N/A와 이유를 반환하고 0점으로 채우지 않음 |
| 예시 Run | `EXAMPLE-RUN-001`: 화면 개발용 합성 데이터 5건(정상 / 형식 오류 / Timeout / Draft 정답 / 방향 충돌). 응답에 `data_kind: "example"`이 붙음 |
| 예외 테스트 | `python -m pytest backend/tests -q` → **12 passed** |
| 서버 | **http://32.196.229.237:8888** (외부 접속 확인, Swagger 문서 `/docs`) |

## 2. 처리 흐름

```
모델 출력 수신 (runs/<run_id>/predictions/<item>.json, 원문 그대로 보존)
  → ① 형식 검사 (V1, V2)        JSON 읽기 · 필수 항목 · 허용 값 · 0–1 좌표 · 참조 ID 선언
  → 정답 게이트                  Reviewed 정답만 통과. Missing / Draft는 이유와 함께 제외
  → ② 근거 대조 (V3, V4)        같은 Class + IoU ≥ 0.5, Hungarian(M+IoU)으로 1:1 짝짓기 → 모델 ID를 정답 ID로 변환
  → ③ 관계·속성 (V5–V9, A1, A2) 12칸 Macro-F1 (12칸이 다 차지 않으면 N/A + Supported-class F1)
  → ④ 대응 (V10–V12)           필요 / 허용 / 금지 집합 + 일관성(Ci). Direction Match=Conflicting 장면은 여기서만 제외
  → ⑤ 진술 검수 (V13, V14)       사람 검수 입력만 집계. 입력이 없으면 not_computed
  → 결과 저장 store/results/<run_id>.json (result_hash 포함) → Report API → 화면
```

### 설명할 원칙 (미팅용)
- **형식 오류를 요청 수에서 빼지 않는 이유**: 요청 목록은 실행 전에 고정합니다(`requests.json`). 실패를 빼면 실패율이 실제보다 낮게 집계되어 형식을 자주 깨는 모델이 유리해집니다. 그래서 Invalid와 Timeout은 V1/V2 분모에 남습니다. 관계 판정에서는 FN, V10/V11에서는 실패, V12에서는 분모에만 포함됩니다. 결과 파일 자체가 없어도 `not_returned`로 남깁니다.
- **U와 Missing의 차이**: U는 "입력만으로 판정할 수 없음"이라는 **정답 값**이라 채점합니다(V8, V9). Missing은 정답이 **없거나** 검수되지 않은 상태라 채점 전에 제외하고 제외 수와 이유를 보고합니다.
- **검수 완료 정답만 채점하는 이유**: Draft 정답으로 점수를 내면 정답이 바뀔 때 모든 모델 비교가 흔들리고, 공식 점수와 진단 점수가 섞입니다. `annotation_status == "Reviewed"`만 통과합니다.
- **재채점과 재추론**: 같은 예측을 같은 정답·채점 코드로 다시 채점하면 `result_hash`가 같아야 합니다(테스트로 확인). 재추론은 `run.json`에 설정을 남기고 변동을 따로 보고합니다.

## 3. 저장 구조 (`backend/store`)

모델이 볼 수 있는 자료와 볼 수 없는 자료를 파일 단위로 나눴습니다. SQLite는 아직 쓰지 않고 파일로 저장합니다(git으로 버전을 추적할 수 있고, 데이터 규모가 작음).

| 저장 위치 | 내용 | 현재 |
|---|---|---|
| `items.jsonl` | 모델 입력: item_id, 이미지 파일·sha256·크기, task. **C·GT 없음** | Pilot 6 + 예시 5 |
| `annotations.jsonl` | 장면 속성·근거·작성/검수 상태 | **비어 있음** (GT 미작성) |
| `references.jsonl` | 검수된 정답·대응 규칙 (`annotation_status`: Reviewed / Draft / Missing) | Pilot 6건 = Missing으로 명시, 예시 5건 = 합성 |
| `runs/<run_id>/run.json` | 모델·revision·양자화, prompt/schema hash, 디코딩·seed, 패키지, 데이터·정답 버전 | 2개 |
| `runs/<run_id>/requests.json` | 실행 전에 고정한 요청 목록 | |
| `runs/<run_id>/predictions/*.json` | 원문 출력(`raw_text`, `output_text`), 상태(ok/timeout/error), 생성 시간 | 실패도 삭제하지 않음 |
| `results/<run_id>.json` | 채점 결과 (자동 생성, git 제외) | |

기존 자료 재사용:
- `scorer/validate.py`, `scorer/prediction.schema.json`: `dry_run_v1@ef1ed25`의 `integrated_annotation_sample`에서 **수정 없이** 복사했습니다. 모델팀이 기록한 schema hash(`de20d146…`)는 같은 파일을 CRLF로 저장했을 때의 hash와 일치합니다.
- Pilot 예측은 `tools/import_pilot.py`가 `origin/work/model-1115@e5fc3d3`에서 git으로 직접 읽고, 원본 hash를 확인한 뒤 가져옵니다.

## 4. API (FastAPI)

| 메서드 · 경로 | 용도 |
|---|---|
| `GET /api/health` | 상태, 버전 |
| `GET /api/runs` | 실행 목록 |
| `GET /api/runs/{run_id}` | 실행 설정과 버전 |
| `GET /api/runs/{run_id}/items` | **F3** 문항 목록. 필터: `relation=R1..R4`(그 관계가 틀린 문항), `fail_reason`, `annotation_status`, `prediction_status`, `data_kind` |
| `GET /api/runs/{run_id}/items/{item_id}` | **F5** 문항 상세 |
| `GET /api/runs/{run_id}/report` | 지표 전체, 분모, 제외 수, N/A 이유 |
| `POST /api/runs/{run_id}/rescore` | 저장된 파일로 다시 채점 |
| `GET /api/images/{item_id}` | 입력 이미지 (EC2 `/data/aihub_71784/images`에서 바로 제공) |

응답 예시는 `examples/`에 있습니다. API를 실제로 호출해 저장한 파일입니다.
- `examples/example_run/`: **합성 예시**. 정상(`item_valid_action_fail`), 형식 오류(`item_format_error`), Timeout(`item_timeout`), Draft 정답(`item_draft_reference`), 방향 충돌(`item_direction_conflict`), 목록·리포트
- `examples/real_pilot/`: **실제 Run**. 모델 출력은 실제 값이고, GT가 없어 정답 기반 지표는 N/A

### 공통 필드
- `data_kind`: `"real"` 또는 `"example"`. 모든 응답에 붙습니다.
- `versions`: `{api, scorer, scorer_commit, model, prompt, data, reference, result_hash}`. 채점 코드 버전, 정답 버전, 결과 hash가 여기 들어갑니다.
- 지표 형식: `{status, value, numerator, n, reason, ci95, ci_status}`
  - `status`: `computed`(계산됨), `not_applicable`(분모 0이거나 조건 미충족, `reason` 필수), `not_computed`(기능·입력 없음, `reason` 필수)
  - 계산되지 않은 지표는 `value`가 **항상 null**입니다. 0이나 예시 값을 넣지 않습니다.

### F5 문항 상세 필드 (연오님 `FRONTEND_1113.md` §3과 맞춤)

| 필드 | 내용 |
|---|---|
| `input`, `image_url`, `image_size` | 모델 입력 (C·GT 없음) |
| `prediction.{status, format_errors, raw_text, output_text, parsed, meta}` | 원본 예측. 실패해도 원문 유지 |
| `reference` | 정답: objects / regions(C 포함) / relations / action_rules. **뷰어 전용**이고 모델 입력과 분리 |
| `scoring.relations.{R}.{expected, predicted, match}` | 관계 판정 비교 |
| `scoring.diagnostics.grounding.objects["0.3"/"0.5"/"0.7"].{pairs[], unmatched_prediction_ids, unmatched_reference_ids}` | Box 짝짓기 |
| `scoring.diagnostics.grounding.regions.unmeasurable_reference_ids` | 측정 불가 Region |
| `scoring.diagnostics.evidence.{R}.{status, reason, mapped_ids}` | V4 근거 일치 |
| `scoring.diagnostics.benchmark.{eligible, blockers[]}` | 공식 점수를 낼 수 없는 이유 |
| `scoring.action_eval.{pass, pass_status, fail_reasons[], errors[], matched_required_groups, required_groups, excluded_reason}` | 대응 채점 |
| `scoring.statement_review` | V13/V14 검수 상태 (현재 `not_submitted`) |
| `scoring.excluded_reason` | `reference_missing`, `reference_not_reviewed (Draft)` 등 |

`fail_reasons` 코드 (연오님 요청 1·2번 답변):
`invalid`(형식 오류·Timeout) · `missing_required`(필요 묶음 누락) · `forbidden`(금지 쌍) · `unsupported`(허용·금지 어디에도 없는 쌍) · `contradiction`(모델 자신의 관계 판정과 모순: based_on 관계를 A로 판정했거나, 같은 조건에서 정지와 진행을 함께 답함) · **`reference_inconsistent`**(based_on 관계가 정답에서 A인 경우, 기존 "based_on disagrees with reference" 문장을 별도 코드로 분리)

## 5. 예외 처리 확인 결과 (`tests/test_exceptions.py`, 12 passed)

| 확인 항목 | 예시 입력 | 예상·실제 결과 |
|---|---|---|
| 형식 오류·Timeout이 목록에 남음 | example_002(잘린 JSON), example_003(timeout) | 요청 5건 유지, V1 = 3/5, V2 = 2/5, 대응은 `invalid` 실패, V12 분모 유지 ✅ |
| 결과 파일이 없는 요청 | example_001 예측 파일 삭제 | `not_returned`, V1 분모 5 유지 ✅ |
| Missing·미검수 정답 제외 | example_001을 Missing으로, example_004는 Draft | 이유와 함께 제외, V1/V2에는 남음 ✅ |
| 관계 한 칸만 Missing | R3 = null | 그 칸만 빠지고 V7 분모 −1 ✅ |
| U는 유효 정답 | R2 정답 U, 예측 U + 근거 | match = true, V8 분자 1, V4 R2 통과 ✅ |
| 방향 충돌은 V10–V12에서만 제외 | example_005 | 대응 분모에서 빠짐(3), 관계 V6 분모에는 남음(4) ✅ |
| 분모 0 → N/A | 정답이 없는 요청 1건 | V4/V6/V10/V12가 `not_applicable` + reason, value = null ✅ |
| V5 12칸 미충족 → N/A | 예시 Run | V5 = N/A + 빈 칸 목록 + Supported-class Macro-F1 ✅ |
| 재채점 결과 동일 | 같은 입력으로 두 번 채점 | `result_hash`·전체 JSON 동일 ✅ |
| Greedy가 아닌 최대 매칭 | Greedy면 1쌍, 최적은 2쌍인 Box | 2쌍(p1–r2, p2–r1) ✅ |

## 6. 실제 Run 조회 결과 (`RUN-PILOT6-BASE-001`)

- 요청 6, 형식 통과 6 → V1 = 1.0 (Wilson 95%: 0.61–1.0), V2 = 0.0
- 정답 제외 6건 (`reference_missing`) → V3–V12, A1, A2 = `not_applicable` ("no Reviewed reference in this run")
- 모델 예측 관계: pilot_001·006은 R1 = P, 나머지는 모두 A (정답이 없어 맞았는지는 판단할 수 없음)
- 참고: 원문(`raw_text`) 끝에 end-of-turn 토큰 `<turn|>`이 붙어 있습니다. 채점기는 special token을 제외하고 디코딩한 `output_text`를 읽습니다. 그 밖의 형식 복구(코드펜스 제거, 잘린 JSON 보정 등)는 하지 않습니다.

## 7. 실행 · 확인 방법

로컬:
```bash
pip install fastapi "uvicorn[standard]" scipy pytest httpx
python -m backend.tools.import_pilot          # Pilot 6 → store (origin/work/model-1115에서 읽음)
python -m backend.tools.make_example_run      # 합성 예시 Run
python -m pytest backend/tests -q             # 예외 테스트
IMAGE_ROOT=<이미지 폴더> uvicorn backend.app.main:app --port 8888
python -m backend.tools.dump_examples         # examples/ 응답 파일 다시 생성
```

EC2 (`ubuntu@32.196.229.237`): 코드는 `~/backend/262/backend`, venv는 `~/backend/.venv`. systemd 서비스 `road-vlm-api`가 0.0.0.0:8888에서 실행됩니다(`IMAGE_ROOT=/data/aihub_71784/images`).
```bash
sudo systemctl status road-vlm-api
curl http://32.196.229.237:8888/api/health
```
외부 접속 확인 완료 (2026-11-16, `http://32.196.229.237:8888/api/health` → 200). 문서 화면은 `http://32.196.229.237:8888/docs`입니다. 보안그룹이 닫히면 SSH 터널로 접속합니다: `ssh -i <pem> -L 8888:localhost:8888 ubuntu@32.196.229.237`.

## 8. 미구현 · 미산출 목록

| 항목 | 상태 | 이유 / 필요한 것 |
|---|---|---|
| Pilot 정답 | 없음 | GT 미작성. 태문님·유경님 검수가 끝나면 `references.jsonl`에 `Reviewed`로 넣고 `POST /rescore` |
| V13 · V14 | not_computed | 사람 진술 검수 입력이 없음. 자동 판정으로 대체하지 않음 |
| L1–L3 | not_computed | 2인 Annotation 없음 |
| Group Paired Bootstrap, Base vs Tuned 비교 | not_computed | Tuned Run이 없고 Source Group도 미배정 (`ci_status: not_computed`) |
| Wilson CI | V1, V2, V10, V12만 | 문항 단위 비율이 아닌 점수는 Bootstrap 대상 |
| Ci 일관성 규칙 | 해석 구현 (`contradiction`, `reference_inconsistent`) | 조건 Code → 필요 정답 판정 대응표(명세 App. A)를 데이터 파트와 확인해야 함 |
| Region 짝짓기 | bbox만 비교 | polygon Region은 측정 불가로 분리 |
| 누수 검사(§8) | 미구현 | Split·Source Group 버전이 아직 없음 |
| 썸네일 | `thumbnail_url: null` | 원본 `image_url`만 제공 |
| SQLite | 미사용 | 파일 저장으로 시작, 규모가 커지면 전환 |

## 9. 완료 / 미완료 / 다음에 필요한 것

- **완료**: 저장 구조, 형식 검사 + V3–V12·A1·A2 채점 코드, 예외 테스트 12건, Report API 7개, 실제 Run(Pilot 6) 연결, 정상·오류·Timeout 응답 예시, EC2 배포
- **미완료와 이유**: 정답 기반 실제 점수(GT 없음), V13/V14(검수 입력 없음), Bootstrap·비교(Tuned 없음), 누수 검사(Split 미정)
- **다음에 필요한 것**: Reviewed 정답(형식은 `examples/example_run/item_valid_action_fail.json`의 `reference` 참고), 조건 Code → 판정 대응표 확인, Source Group / Split 배정, 보안그룹 8888 개방 여부 결정
