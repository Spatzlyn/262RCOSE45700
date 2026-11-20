# 백엔드 — 채점기 · 저장 구조 · Report API · 추론 워커 (work/backend-1115)

담당: 문혜승 · 기준 문서: `참고자료/Role_Backend.pdf` §3–9 (`kakao_meeting_1106` 브랜치). 명세서와 다르면 명세서를 따릅니다.

## 1. 한눈에 보기

| 항목 | 상태 |
|---|---|
| 서버 | **http://32.196.229.237:8888** (EC2 g5.xlarge · A10G). API는 Docker, 워커는 systemd. 둘 다 부팅 시 자동 시작. Swagger 문서 `/docs` |
| 실제 Run | `RUN-PILOT6-BASE-001`: 경흠님 Pilot 6건(RTX 4070), 6/6 형식 통과 · **`RUN-PILOT6-A10G-002`: 같은 6건을 서버 A10G에서 API로 다시 추론**, 6/6 형식 통과, 관계 판정 6/6 동일 (§6.1) · `RUN-PILOT6-A10G-001`: 원본과 맞추기 전 워커 시험(1건 완료, 5건 취소) |
| 정답(GT) | 아직 작성 전 → 6건 모두 `Missing`. 정답 기반 지표는 N/A와 이유를 반환하고 0점으로 채우지 않음 |
| 예시 Run | `EXAMPLE-RUN-001`: 화면 개발용 합성 5건 (정상 / 형식 오류 / Timeout / Draft 정답 / 방향 충돌), `data_kind: "example"` |
| 테스트 | `python -m pytest backend/tests -q` → 27 passed (Docker 빌드 중에도 실행) |
| 남은 일 | [TODO.md](TODO.md) — 대부분 다른 파트의 입력(정답, Split, Source Group, adapter)을 기다리는 항목 |

## 2. 처리 흐름

`review_scope: "relations_only"`인 Reference는 사람이 확인한 관계 값만 비교합니다. `Draft`는 표시용이고, `Reviewed`에서는 null이 아닌 관계만 채점합니다. 박스·영역은 화면에서 볼 수 있으며, 근거·속성·대응 채점과 최종 Test 동결에서는 부분 Reference가 제외됩니다.

```
POST /api/runs (문항 목록·모델·프롬프트·디코딩 고정) → 큐 → GPU 워커가 1건씩 추론 → 원문 그대로 저장
  (또는 tools/import_pilot.py로 외부 결과 가져오기)
→ ① 형식 검사 (V1, V2)        JSON · 필수 항목 · 허용 값 · 0–1 좌표 · 참조 ID 선언. 실패·Timeout·취소도 목록에 남음
→ 정답 게이트                  Reviewed만 통과. Missing / Draft는 이유와 함께 제외. U는 유효한 정답
→ ② 근거 대조 (V3, V4)        같은 Class + IoU ≥ 0.5, Hungarian(M+IoU) 1:1 짝짓기 → 모델 ID를 정답 ID로 변환
→ ③ 관계·속성 (V5–V9, A1, A2) 12칸 Macro-F1 (12칸이 다 차지 않으면 N/A + Supported-class F1)
→ ④ 대응 (V10–V12)           필요/허용/금지 + 일관성(Ci). Direction Match=Conflicting 장면은 여기서만 제외
→ ⑤ 진술 검수 (V13, V14)       사람 검수 입력만 집계. 자동 판정하지 않음
→ ⑥ 신뢰구간·비교             Wilson / Source Group bootstrap / Base 대비 paired bootstrap → improved | not_confirmed
→ 결과 저장 (result_hash, 입력 fingerprint) → Report API → 화면
```

### 설명할 원칙
- **형식 오류를 요청 수에서 빼지 않는 이유**: 요청 목록은 실행 전에 고정합니다. 실패를 빼면 실패율이 낮게 집계되어 형식을 자주 깨는 모델이 유리해집니다. Invalid·Timeout·취소는 V1/V2 분모에 남고, 관계에서는 FN, V10/V11에서는 실패, V12에서는 분모에만 들어갑니다.
- **U와 Missing의 차이**: U는 "입력만으로 판정할 수 없음"이라는 정답 값이라 채점합니다. Missing은 정답이 없거나 검수 전이라 제외하고 수와 이유를 보고합니다.
- **검수 완료 정답만 채점**: Draft로 점수를 내면 정답이 바뀔 때 비교가 흔들립니다.
- **재채점 vs 재추론**: 같은 예측·정답·채점 코드는 같은 `result_hash`를 냅니다(테스트). 재추론은 GPU·환경에 따라 달라질 수 있어 `run.json`에 설정과 워커 환경을 기록하고 변동을 따로 보고합니다(§6).
- **개선 판정**: Base와 같은 요청 목록에서, 같은 Source Group 재표본으로 구한 차이의 95% 구간이 0을 넘을 때만 `improved` (낮을수록 좋은 V2·V7·V9·V12·A2는 구간 상한 < 0).

## 3. 저장 구조

서버에서는 `/data/backend-store`(코드 폴더 밖)에 두어 재배포해도 실행 기록이 유지됩니다. 저장소의 `backend/store`는 초기 데이터입니다.

| 위치 | 내용 |
|---|---|
| `items.jsonl` | 모델 입력: item_id, 이미지 파일·sha256·크기, 조건 태그(`conditions`), `source_group_id`. **C·GT 없음** |
| `references.jsonl` + `reference_history/<item>/<version>.json` | 현재 정답과 모든 버전 (같은 버전 번호로 내용을 바꾸면 거부) |
| `annotation_rounds.jsonl` | 2인 합의 전 기록 (L1, L2) |
| `splits/<version>.json`, `<version>.freeze.json` | Split 배정, 고정된 Test manifest |
| `runs/<run_id>/run.json` · `requests.json` · `predictions/` · `jobs.json` · `statement_reviews.jsonl` | 실행 설정과 워커 환경, 고정 요청 목록, 원문 출력(실패 포함), 큐 상태, 진술 검수 |
| `results/`, `cache/` | 자동 생성 (git 제외) |

데이터 파트 파일 가져오기 (검증 후 저장, `--dry-run` 지원):
```bash
python -m backend.tools.import_references references refs.jsonl
python -m backend.tools.import_references rounds rounds.jsonl
python -m backend.tools.import_references statements <run_id> reviews.jsonl
python -m backend.tools.import_references split split.json
```
입력 형식은 `scorer/quality.py`, `scorer/score.py::statement_metrics`, 예시 정답은 `examples/example_run/item_valid_action_fail.json`의 `reference`.

## 4. API

| 메서드 · 경로 | 용도 |
|---|---|
| `GET /api/health`, `/api/versions` | 상태, 채점·schema·prompt·정답·split 버전 |
| `GET /api/items`, `/api/items/{id}` | 문항 목록과 입력 (F1) |
| `GET /api/runs`, `/api/runs/{id}`, `/api/runs/{id}/progress` | 실행 목록·설정·진행률 |
| `GET /api/runs/{id}/items` | **F3** 문항 목록. 필터 `relation`, `fail_reason`, `annotation_status`, `prediction_status`, `data_kind` |
| `GET /api/runs/{id}/items/{item}` | **F5** 문항 상세 (입력 / 원문 예측 / 정답(뷰어 전용) / 채점 / 진술 검수) |
| `GET /api/runs/{id}/report[?base=<run>]` | **F2** 지표·분모·제외·신뢰구간, base를 주면 차이 구간과 판정 |
| `GET /api/runs/{id}/report/conditions?key=weather` | 조건별 점수 (n < 30이면 `exploratory`) |
| `GET /api/compare?base=&target=` | **F4** 문항별 나란히 비교 + 요약 |
| `GET /api/runs/{id}/export?format=json\|csv` | 결과 내려받기 |
| `GET /api/quality`, `/api/datasets`, `/api/datasets/{v}/leak-check` | L1–L3, Split 목록, 누수 검사 |
| `GET /api/images/{id}[?size=thumb]` | 입력 이미지 / 320px 썸네일 |
| `POST /api/runs` 🔑 | 추론 실행 생성. 예: `{"item_ids": ["pilot_001"], "prompt_version": "prompt_v1", "timeout_s": 900}` (모델·디코딩 기본값 = Pilot 설정) |
| `POST /api/runs/{id}/cancel` · `/rescore` · `/statement-reviews` 🔑 | 취소(대기 중 요청은 `cancelled`로 남음), 재채점, 진술 검수 입력 |
| `POST /api/datasets/{v}/freeze` 🔑 | 누수 검사 통과 + Test 전부 Reviewed일 때만 고정 |
| `GET /api/jobs/next`, `POST /api/jobs/{run}/{item}/result` 🔧 | 워커 전용 |

🔑 = `X-API-Key: API_WRITE_KEY`, 🔧 = `WORKER_KEY`. 키는 서버 `~/backend/262/backend/.env`에만 있고 git에는 없습니다. 키가 없으면 쓰기 API는 503.

지표 형식 `{status, value, numerator, n, reason, ci95, ci_status, ci_reason}` — `status`가 `computed`가 아니면 `value`는 항상 null이고 `reason`이 붙습니다. 모든 응답에 `data_kind`("real" / "example")와 `versions`(scorer commit, schema, 정답 버전, result_hash)가 있습니다.

`fail_reasons`: `invalid` · `missing_required` · `forbidden` · `unsupported` · `contradiction`(모델 자신의 판정과 모순) · `reference_inconsistent`(based_on 관계가 정답에서 A).

응답 예시: `examples/example_run/`(합성), `examples/real_pilot/`(실제 Run). API를 실제로 호출해 저장한 파일입니다(`python -m backend.tools.dump_examples`).

## 5. 확인 결과 (테스트 25건)

| 확인 항목 | 결과 |
|---|---|
| 형식 오류·Timeout·결과 없음·취소가 요청 목록에 남음 | V1 분모 유지, 상태별 집계 ✅ |
| Missing·Draft 정답 제외, 관계 한 칸 Missing은 그 칸만 제외 | ✅ |
| U는 유효 정답 (V8, V4 R2 통과) | ✅ |
| Direction Match=Conflicting은 V10–V12에서만 제외 | ✅ |
| 분모 0, V5 12칸 미충족 → N/A + 이유 | ✅ |
| 같은 입력 재채점 → 같은 result_hash | ✅ |
| Hungarian이 Greedy보다 많은 짝을 찾음, Class가 다르면 짝 없음 | ✅ |
| bootstrap 재현성(seed 고정), Group 없음/1개면 N/A | ✅ |
| paired 비교: 전부 개선 → `improved`, 동일 → `not_confirmed`, 요청 목록 다르면 N/A | ✅ |
| V13/V14: 검수 입력이 없으면 not_computed, 미완료 검수 제외 | ✅ |
| L1·κ 계산, pe=1이면 κ N/A | ✅ |
| 누수 검사(Group이 여러 Split, 판단 시점 이후 Frame), Draft가 있으면 freeze 거부 | ✅ |
| 큐: 첫 응답만 보관(두 번째는 409), 입력에 GT 없음, timeout·취소 집계 | ✅ |
| 쓰기 API 키 없으면 401 | ✅ |
| 정답 가져오기: 잘못된 값 거부, 같은 버전 내용 변경 거부 | ✅ |

## 6. 추론 재현 (A10G)

- 추론 코드는 경흠님 원본 `work/model-1115:ai_model/inference/source/run_gemma_pilot_smoke.py`(sha256 `14373662…`, Pilot 기록과 일치)와 같은 방식으로 맞췄습니다: 같은 system prompt·과제 JSON, processor `max_soft_tokens=280`, `Gemma4ForConditionalGeneration` + sdpa, 입력 부동소수 텐서 BF16 변환, greedy, seed 42.
- 서버 환경: Python 3.11.18, torch 2.6.0+cu124, transformers 5.23.0, bitsandbytes 0.50.2 (Pilot과 같은 버전), 모델 revision `4ecc2ba…`, NVIDIA 595.91.07.
- 입력 재현 확인: pilot_001 rendered prompt sha256이 Pilot 기록(`4ffd9603…`)과 같고, 입력 4176 토큰, pixel_values `[1, 2520, 768]`도 같습니다.

### 6.1 Pilot 재추론 결과 (`RUN-PILOT6-BASE-001` RTX 4070 vs `RUN-PILOT6-A10G-002` A10G)

| item | 형식 | 생성 토큰 | 생성 시간(초) | R1–R4 | Object 수 |
|---|---|---|---|---|---|
| pilot_001 | valid / valid | 1111 / 1049 | 277 / 96 | P A A A 동일 | 6 / 6 |
| pilot_002 | valid / valid | 690 / 681 | 178 / 62 | A A A A 동일 | 2 / 2 |
| pilot_003 | valid / valid | 1001 / 893 | 240 / 81 | A A A A 동일 | **6 / 5** |
| pilot_004 | valid / valid | 608 / 615 | 155 / 57 | A A A A 동일 | 1 / 1 |
| pilot_005 | valid / valid | 653 / 654 | 168 / 59 | A A A A 동일 | 2 / 2 |
| pilot_006 | valid / valid | 885 / 892 | 208 / 82 | P A A A 동일 | 4 / 4 |

- **관계 판정 6/6 동일, 출력 문장은 0/6 바이트 동일.** 같은 입력·같은 greedy 설정이어도 GPU가 다르면 수치 연산 차이로 문장·Box·Object 수가 달라질 수 있습니다. 재추론 간 변동으로 기록하고, 모델 비교는 같은 장비의 실행끼리 합니다.
- 원본 코드와 맞추기 전 워커(입력을 float32로 넣음, `RUN-PILOT6-A10G-001`의 pilot_001)는 R1이 P → A로 달랐습니다. BF16 변환을 원본과 맞춘 뒤 6건 모두 관계가 일치했습니다.
- A10G가 RTX 4070 노트북보다 약 2.9배 빠릅니다 (1건 57–96초).
- 비교 원자료: `examples/real_pilot/rerun_variation_rtx4070_vs_a10g.json` (`python -m backend.tools.compare_reruns <서버> <run_a> <run_b>`).

## 7. 실행 · 배포

로컬:
```bash
pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -q
uvicorn backend.app.main:app --port 8888        # IMAGE_ROOT=<이미지 폴더>
```

EC2 (`ubuntu@32.196.229.237`):
```bash
cd ~/backend/262/backend
sudo SCORER_COMMIT=<scorer/app 마지막 commit> docker compose up -d --build   # API (빌드 중 테스트)
sudo systemctl restart road-vlm-worker                                        # GPU 워커
sudo docker logs road-vlm-api --tail 50; journalctl -u road-vlm-worker -n 50
```
- API 컨테이너: `restart: unless-stopped`, store는 `/data/backend-store`, 이미지는 `/data/aihub_71784/images`(읽기 전용).
- 워커: `deploy/road-vlm-worker.service`, `~/infer/.venv`, 모델 `/data/models/gemma-4-E4B-it`. 모델 로딩 약 2분, 1건 생성 약 1.5분, 최대 GPU 메모리 약 9.4GB.
