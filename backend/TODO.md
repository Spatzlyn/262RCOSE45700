# 백엔드 TODO — 추가로 필요한 엔드포인트 (2026-11-16)

현재 있는 것: `GET /api/health`, `GET /api/runs`, `GET /api/runs/{id}`, `GET /api/runs/{id}/items`, `GET /api/runs/{id}/items/{item}`, `GET /api/runs/{id}/report`, `POST /api/runs/{id}/rescore`, `GET /api/images/{item}`.

우선순위: **P0** = 이번 주 추론 연결에 필요 · **P1** = 정답이 들어오면 바로 필요 · **P2** = 4주차 비교·리포트 · **P3** = 운영 편의

## P0 — 추론 실행 (F1 화면, GPU 워커)

| 엔드포인트 | 용도 | 막힌 것 |
|---|---|---|
| `POST /api/runs` | Run 생성: 모델·revision·양자화, prompt 버전, 디코딩·seed, 문항 목록을 받아 `run.json`·`requests.json`을 고정하고 `queued` 상태로 만듦 | — |
| `GET /api/runs/{id}/progress` | 진행률 (queued / running / done / failed / timeout 수, 경과 시간) | — |
| `POST /api/runs/{id}/cancel` | 남은 요청 취소. 취소된 요청도 `cancelled`로 목록에 남김 | — |
| `GET /api/jobs/next` *(내부, 토큰)* | GPU 워커가 다음 요청 1건을 가져감 (lease 시간 포함) | — |
| `POST /api/jobs/{job_id}/result` *(내부, 토큰)* | 워커가 raw/output text, 상태(ok/timeout/error), 생성 시간·토큰 수, GPU·패키지 정보를 보냄 → 저장 후 자동 채점 | — |
| GPU 워커 프로세스 | `/data/models/gemma-4-E4B-it`로 NF4 추론. 컨테이너에서 GPU를 쓰려면 nvidia-container-toolkit 필요 | **경흠님 `infer.py`·`common.py`** (지금은 dry_run_v1 자료로 재구성 가능, rendered prompt hash로 검증 예정) |
| `POST /api/runs/import` | 외부(경흠님 노트북 등)에서 돌린 결과 묶음을 업로드해 Run으로 등록. 지금 `tools/import_pilot.py`가 하는 일을 API로 | — |

## P1 — 정답·검수 입력 (데이터 파트 → 채점)

| 엔드포인트 | 용도 | 막힌 것 |
|---|---|---|
| `GET /api/items` · `GET /api/items/{item_id}` | 문항 목록과 입력 정보 (Run과 무관하게). F1에서 Test Version 고르기 | — |
| `PUT /api/references/{item_id}` · `POST /api/references:bulk` | 검수 정답 등록. Schema 검사, `annotation_status`·`reference_version` 필수, 이전 버전 보존 | GT 형식 확정 (태문님·유경님) |
| `GET /api/references/{item_id}?version=` | 정답 조회 (뷰어 전용, 모델 입력 경로와 분리) | — |
| `POST /api/runs/{id}/statement-reviews` · `GET` | V13/V14용 사람 진술 검수 결과 입력 (최소 진술, 오류 여부, 검수자) | 검수 양식 합의 |
| `POST /api/annotations/agreement` | 2인 Annotation 입력 → L1·L2(κ) 계산 | 2인 검수 일정 |

## P2 — 비교·리포트 (F2, F4)

| 엔드포인트 | 용도 | 막힌 것 |
|---|---|---|
| `GET /api/runs/{id}/report?base={base_id}` | Base 대비 차이 + 차이의 95% 구간 + `judgement` (명세 §9 형식) | Group Paired Bootstrap 구현, Tuned Run |
| `GET /api/compare?base=&target=` | 같은 문항에서 두 모델 결과를 나란히 (F4) | Tuned Run |
| `GET /api/runs/{id}/report/conditions` | 조건별 점수 (야간·비 등). 사람 Annotation으로 미리 정한 장면 집합 사용 | 조건 태그 |
| `GET /api/datasets/{version}/leak-check` | Source Group이 여러 Split에 걸쳤는지, 판단 시점 이후 Frame이 있는지 | Split·Source Group 배정 |
| `POST /api/datasets/{version}/freeze` | Test 입력·정답·채점 규칙 고정 (Test freeze) | Split 확정 |

## P3 — 운영 편의

| 엔드포인트 | 용도 |
|---|---|
| `GET /api/images/{item_id}?size=thumb` | F3 목록용 썸네일 (지금은 원본 3MB PNG) |
| `GET /api/runs/{id}/export?format=json|csv` | 채점 결과 파일 다운로드 |
| `GET /api/versions` | scorer·schema·reference·data 버전 목록 |
| 쓰기 API 인증 | `POST`/`PUT` 엔드포인트에 API Key (지금 `POST /rescore`가 인증 없이 열려 있음) |

## 엔드포인트 외 할 일

- [ ] Ci 일관성 규칙(조건 Code → 필요한 정답 판정) 데이터 파트와 확인
- [ ] Group Paired Bootstrap (2,000회, Source Group 단위) 구현
- [ ] 재구성한 입력을 Pilot rendered prompt hash(`4ffd9603…`)와 대조 → pilot_001 재생성 비교 (A10G vs RTX 4070 변동 기록)
- [ ] GPU 워커용 Docker 이미지 (nvidia-container-toolkit 설치 필요)
- [ ] SQLite 전환 여부 (Run·요청 수가 늘면)
