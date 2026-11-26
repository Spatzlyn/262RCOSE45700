# 프론트엔드 11/13 제출물 — F3 → F5 화면 초안 · 필드 목록 · 상태 표기안

담당: 고연오 (프론트엔드/디자인) · 브랜치: `work/frontend-1115`

## 확인할 파일

| 파일 | 용도 |
|---|---|
| `frontend/f3-f5/index.html` | **F3 → F5 화면 초안.** 더블클릭하면 브라우저에서 바로 열림 (서버·설치 불필요) |
| `frontend/f3-f5/template.html` | 화면 코드 (데이터 제외) |
| `frontend/f3-f5/data.json` | 화면이 읽는 데이터. 실제 Run 1건 + 예시 13건 |
| `frontend/f3-f5/prep.py` | `data.json` 생성 스크립트 (실제 Run 파일 → 화면 형식 변환) |
| `frontend/FRONTEND_1113.md` | 이 문서 |

다시 만들기: `cd frontend/f3-f5 && python3 prep.py <실제 Run 파일 폴더> ../frontend/mock` → `data.json`, `index.html` 생성. 실제 Run 파일은 `dry_run_v1` 브랜치의 `kakao_dryrun/representative_inference/`와 `kakao_dryrun/source/integrated_annotation_sample/`에서 가져옴.

## 1. 화면별로 답하는 질문과 구현 상태

| 화면 | 사용자 질문 | 구현됨 | 예시 값으로 표시 |
|---|---|---|---|
| F1 평가 실행 | 어떤 모델·Test Version으로 실행하는가 | 모델 ID 입력, Test·입력 조건 선택, 진행률·V1·V2 표시 (팀 기존 프로토타입) | 실행 자체, 진행률, 실행 기록 전부 |
| F2 결과 Report | Base 대비 개선되었는가 | V5·V10 + CI + 판정, 진단 4군, 조건별 점수 레이아웃 | 모든 점수·구간·판정 (실제 Report API 없음) |
| **F3 오류 목록** | 어떤 장면에서 어떤 종류로 틀렸는가 | **관계 코드·실패 사유·검수 상태·데이터 출처 필터, 문항 클릭 → F5** | 예시 13건. 실제 Run 1건은 실제 값 |
| F4 모델 비교 | 같은 장면에서 두 모델이 어떻게 다른가 | Base/Tuned 나란히 (팀 기존 프로토타입) | 전부 예시 (Tuned 실행 결과 없음) |
| **F5 장면 상세** | 이 판단의 근거는 무엇인가 | **원본 이미지 + C·GT·예측 레이어 토글, 관계 선택 → P/A/U·근거 ID, ID 클릭 → Box·Region 강조, Box 짝짓기, 대응 실패 이유** | 실제 Run 1건은 실제 이미지·예측·백엔드 채점 결과. 나머지는 예시 |

이번 주 우선 연결 범위는 **F3 → F5**. F1·F2·F4는 `frontend/frontend/prototype/index.html`(팀 기존 프로토타입)을 참고.

## 2. 샘플 1건으로 보는 흐름 (실제 Run)

대상: `sample_front_001` — `dry_run_v1@ef1ed25`의 `representative_inference` (Base NF4, adapter 없음, 첫 응답). 정답은 **Draft**(사람 검수 전)라 공식 점수가 아닌 진단이다.

1. **F3**에서 데이터 필터 "실제 Run" → `sample_front_001` 클릭
2. **F5 배너**: "실제 실행 결과 · Draft 정답 기준 진단 (공식 점수 아님)" + 공식 V3·V4·V5 미산출 이유(백엔드 `blockers`)
3. **관계 선택 R3 시야 가림**: GT **P** → 예측 **A**, 불일치
4. **근거 확인**: GT 근거 `F_742188, F_742190, F_742189, F_hidden_road_ahead` 클릭 → 이미지에서 전방 sedan·오른쪽 truck·SUV가 노란색으로 강조. 예측은 "근거 ID 없음". `F_hidden_road_ahead`는 가려진 범위라 Box를 그릴 수 없어 "측정 불가 Region"으로 표시
5. **Box 짝짓기**: 모델은 차량 5대를 찾았고 4대가 GT와 짝 (IoU 0.68~0.80). `obj_5`는 짝 없음이지만, 정답 객체 coverage가 불완전해서 오탐으로 단정하지 않음
6. **대응 실패 이유**: 모델은 "전방 관찰 · 조건 없음". GT 필요 묶음 4개(양보/보류, 불확실성 확인, 가림 확인, 통과 가능성 확인) 중 0개 충족 → **필요 대응 누락**, 허용 쌍 밖 → **근거 없는 대응**. 백엔드 원문 9건은 접어서 표시

→ 한 줄 요약: **모델은 차를 찾았지만(4/5 짝) 그 차들이 길을 막고 시야를 가린다는 관계를 연결하지 못해 모두 A로 답했고, 그래서 필요한 확인 대응을 하나도 내지 못했다.**

## 3. 필드 목록 — 화면 요소 / 필요한 데이터 / 백엔드 전달 필드 / 현재 확보 여부

확보 여부 기준: ✅ 실제 Run 파일에 있음 · ⚠️ 있지만 형식 합의 필요 · ❌ 없음

### F3 문항 목록 (`GET /runs/{run_id}/items?relation=&fail_reason=&review_status=`)

| 화면 요소 | 필요한 데이터 | 백엔드 전달 필드 (제안) | 확보 |
|---|---|---|---|
| 문항 ID | 문항 식별자 | `item_id` | ✅ items.jsonl |
| 실제/예시 구분 | 데이터 출처 | `data_kind: "real" \| "example"` | ❌ 필드 없음 (화면에서 임시 부여) |
| 검수 상태 | 정답 상태 | `annotation_status: Draft \| Reviewed \| Missing` | ✅ references.jsonl |
| 대응 채점 | 통과/실패/미적용 | `action_eval.pass: true \| false \| null` + `action_eval.excluded_reason` | ⚠️ `pass`만 있음. 미적용 이유 필드 없음 |
| 실패 사유 | 5종 코드 | `action_eval.fail_reasons: ["missing_required", ...]` | ⚠️ 현재 **영문 문장**(`errors[]`)만 있음 → 코드 필요 |
| 관계 불일치 | R별 일치 여부 | `relations.{R1..R4}.{expected, predicted, match}` | ✅ metrics.relations |
| 실행 출력 상태 | 형식 오류 여부 | `prediction_status: valid \| invalid \| timeout` | ⚠️ `strict_schema_valid`로 대체 가능 |
| 이미지 썸네일 | 작은 이미지 | `thumbnail_url` | ❌ |

### F5 장면 상세 (`GET /runs/{run_id}/items/{item_id}`)

| 화면 요소 | 필요한 데이터 | 백엔드 전달 필드 (제안) | 확보 |
|---|---|---|---|
| 원본 이미지 | 이미지 경로·크기 | `image_url`, `image_size{width,height}` | ⚠️ 경로·크기 있음, URL 접근 방식 미정 |
| C 레이어 | 평가 영역 다각형 | `reference.regions[type=driving_area].polygon_xy_norm` | ✅ (Draft) |
| GT Box | 객체 Box·ID·class | `reference.objects[].{object_id, class, bbox_xyxy_norm, semantic_role, placement}` | ✅ |
| GT Region | 영역 ID·Box/다각형·측정 가능 여부 | `reference.regions[].{region_id, type, bbox_xyxy_norm \| polygon_xy_norm, geometry_status}` | ✅ |
| 예측 Box·Region | 모델 출력 | `prediction.track1.objects[]`, `prediction.track1.regions[]` | ✅ parsed_output |
| 관계 선택 (GT) | R별 상태·근거 ID·이유 | `reference.relations.{R}.{state, object_ids, region_ids, reason}` | ✅ annotation track1.relations |
| 관계 선택 (예측) | R별 상태·근거 ID·이유 | `prediction.track1.relations.{R}.{state, object_ids, region_ids, reason}` | ✅ |
| 근거 일치 여부 | R별 근거 판정 | `diagnostics.evidence.{R}.status` | ✅ |
| ID 클릭 → 강조 | ID → 좌표 매핑 | 위 objects/regions의 ID·좌표 | ✅ |
| Box 짝짓기 | 예측↔GT 쌍, IoU | `diagnostics.grounding.objects.{pairs[], unmatched_prediction_ids, unmatched_reference_ids}` | ✅ |
| 측정 불가 Region | 가려진 영역 | `diagnostics.grounding.regions.unmeasurable_reference_ids` | ✅ |
| GT 대응 규칙 | 필요 묶음·허용·금지 | `reference.action_rules.{required_groups, allowed_pairs, forbidden_pairs}` | ✅ |
| 예측 대응 | (대응, 조건, based_on) | `prediction.track1.actions[]` | ✅ |
| 대응 실패 이유 | 5종 코드 + 원문 | `action_eval.fail_reasons[]` + `action_eval.errors[]` | ⚠️ 원문만 있음 |
| 필요 묶음 충족 수 | n / m | `action_eval.matched_required_groups`, `required_groups` | ✅ |
| 공식 점수 미산출 이유 | 차단 사유 | `diagnostics.benchmark.{eligible, blockers[]}` | ✅ |
| Run 정보 | 모델·양자화·adapter·commit | `run.{run_id, config.name, quant, adapter_source_run, commit}` | ⚠️ config에 있음, run_id 공통 구조 미정 |

### 혜승님께 요청 (우선순위 순)

1. **실패 사유 코드**: 지금 `errors[]`는 영문 문장이라 화면이 5종 이름표로 바꿀 수 없음. `fail_reasons: ["missing_required","forbidden","unsupported","contradiction","invalid"]` 코드 배열을 함께 주세요.
2. **`based_on Rk disagrees with reference relation` 분류**: 명세의 "관계 판정과의 모순"은 *모델 자신의* 관계 판정과 대응이 어긋나는 경우인데, 이 문장은 *정답* 관계와 다르다는 뜻이라 5종 중 어디에도 정확히 맞지 않음. 지금 화면에선 "분류 미정"으로 표시. 별도 코드로 둘지, 사유에서 뺄지 결정 필요.
3. **문항 목록 API**: F3 필터용으로 `relation`, `fail_reason`, `annotation_status` 쿼리 지원.
4. **`data_kind`**: 실제 실행 결과와 예시를 응답에서 구분.
5. **이미지 접근**: `image_url` 방식(정적 경로 / 서명 URL / 프록시)과 썸네일.

## 4. 상태 표기안

| 값 | 뜻 | 화면 표기 | 채점 |
|---|---|---|---|
| **P / A** | 성립 / 충분히 확인했고 불성립 | 진한 남색 / 회색 테두리 | 채점 |
| **U** | 입력만으로 판단할 수 없음. **유효한 정답 값** | 연한 남청 배지. **빨강 등 오류 색 사용 안 함** | 채점 (정답의 하나) |
| **Missing** | 정답 미작성·미검수 | 노랑 배지 "Missing · 미작성" + 제외 이유 | 제외 |
| **Invalid** | 모델 출력 형식 오류 | 빨강 배지 + 원문 일부 | 채점 불가, 대응은 실패로 집계 |
| **N/A** | 해당 장면에 적용되지 않는 질문 (예: 방향 충돌 장면의 대응) | 점선 테두리 배지 | 해당 항목 제외 |
| **Draft / Reviewed** | 정답 검수 단계 | Draft = 노랑 "검수 전", Reviewed = 초록 | Draft는 공식 점수 산출 불가 |
| **실제 Run / 예시** | 실행 결과 출처 | 파랑 "실제 Run" / 주황 "예시" — 모든 목록·상세에 항상 표시 | — |
| **미산출 점수** | 계산되지 않은 지표 | `0`이 아니라 "미산출" + 이유(`blockers`) | — |

색만으로 구분하지 않고 항상 글자 이름표를 함께 붙인다. GT는 초록 실선, 예측은 보라 점선, C는 빨강 점선, 선택한 근거는 노랑 강조.

## 5. 완료 / 미완료 / 필요한 것

- **완료**: F3 필터(관계·실패 사유·검수 상태·출처) → F5 이동, 레이어 토글, 관계 선택, 근거 ID 클릭 강조, Box 짝짓기, 실패 이유, 상태 표기, **실제 Run 1건(sample_front_001) 연결 — 파일 기반**
- **미완료**: API 연결 (현재는 실제 Run 파일을 `prep.py`로 변환해 내장), F1·F2·F4의 실제 데이터 연결, 썸네일
- **필요한 것**: 위 "혜승님께 요청" 1~5, 사람 검수(Reviewed)된 장면, Roadside/Obstacle 대응 규칙 기준 버전 확정(모델팀 문서에서 지적됨)

## 6. 11/16 추가 — API 연결 (`frontend/f3-f5/app.html`)

- `app.html`: 같은 화면의 **API 모드**. 데이터를 내장하지 않고 백엔드 Report API(`work/backend-1115`)를 호출한다. 더블클릭으로 열고, 상단 바에서 API 주소(기본 `http://localhost:8888`)와 Run을 고른다. `app.html?api=http://주소:8888`로도 지정 가능.
- 호출: `GET /api/runs` → `GET /api/runs/{run_id}/items`(필터 `relation`·`fail_reason`·`annotation_status`·`data_kind`는 백엔드 쿼리로 전달) → `GET /api/runs/{run_id}/items/{item_id}` → `GET /api/images/{item_id}`.
- 실패 사유는 `action_eval.fail_reasons` 코드 그대로 표시 (`reference_inconsistent` 포함, "분류 미정" 없음). Box 짝짓기는 IoU 0.5 기준 값을 읽는다.
- `index.html`은 기존 파일 모드(실제 Run 1건 + 예시 13건 내장)로 그대로 둔다. 두 파일 모두 `template.html` 하나에서 만든다(`prep.py`).
- 확인: 백엔드 `30c5b92`를 로컬에서 띄워 `EXAMPLE-RUN-001` 5건, `RUN-PILOT6-BASE-001` 6건 전부 열림. Pilot은 정답이 없어 예측만 표시되고 채점은 "정답 없음 · 채점 제외".
- **F1·F2·F4도 API 연결 (11/16 밤)**: `app.html` 상단 F1~F5 전부 동작.
  - F1 실행: `GET /api/runs`, `GET /api/runs/{run_id}` — Run 목록·진행·모델/버전 설정 + 새 실행·취소(쓰기 키 입력식, 아래 참고).
  - F2 리포트: `GET /api/runs/{run_id}/report[?base=]`, `/report/conditions?key=` — V5·V10 + CI + 판정, 진단 지표, 관계 12칸, 조건별. 값·구간·판정은 API 값 그대로, 미산출은 0이 아니라 "미산출/N/A + 이유".
  - F4 비교: `GET /api/compare?base=&target=` — 문항별 Base 예측 → Target 예측, 달라진 관계 강조, 문항 클릭 → Target Run의 F5.
- 확인: 백엔드 `30c5b92`를 로컬에서 띄워 Run 4개(원본 2 + 비교 확인용 복사본 2)로 F1~F5 전 화면 오류 없이 열림. Base 비교가 계산되는 경우와 "요청 목록이 달라 비교 불가"인 경우 모두 표시 확인.
- 미완료: 실제 사진이 붙은 상태·Docker 환경에서의 확인(내 쪽에 이미지·Docker 없음), Tuned Run이 없어 실제 Base vs Tuned 판정은 아직 못 봄.

### 켜는 방법 (Windows · PowerShell)

1. Docker Desktop을 실행하고 "Engine running"이 뜰 때까지 기다린다.
2. 팀 레포의 `backend` 폴더에서 (브랜치 `work/backend-1115`):
   ```powershell
   $env:STORE_DIR="$PWD\store"
   $env:IMAGE_DIR="$PWD\store"
   docker compose up -d --build
   ```
   `STORE_DIR`·`IMAGE_DIR`는 compose 기본값이 서버 경로(`/data/...`)라 로컬에서 바꿔주는 값이다. 이 설정에서는 사진 없이 Box만 보인다(사진 폴더가 있으면 `IMAGE_DIR`를 그 폴더로).
3. 크롬에서 `http://localhost:8888/api/health`가 `{"status":"ok"...}`이면 준비 끝.
4. `frontend/f3-f5/app.html`을 탐색기에서 더블클릭(크롬 주소창이 `file:///`로 시작해야 함. 앱 안 미리보기에서는 API 호출이 막힘).
5. 오른쪽 위 주소 칸: 로컬은 `http://localhost:8888`, 배포 서버는 `http://100.52.183.88:8888`(서버가 켜져 있을 때만, 사진 포함).
6. 끄기: `docker compose down`

### 새 실행 · 취소 (쓰기 키 입력식)

조회(GET)는 누구나 되지만, 새 Run 실행·취소(POST)는 백엔드가 `X-API-Key` 헤더에 쓰기 키(`API_WRITE_KEY`, 서버 `.env`에만 있고 git에 없음)를 요구한다.

- F1 아래 **+ 새 실행**: 문항 선택 → 이름(선택) → 쓰기 키 입력 → "실행 걸기" → 건수·예상 GPU 시간 확인 → `POST /api/runs`. 모델·프롬프트·디코딩은 백엔드 기본값(Pilot 설정)을 쓴다.
- 대기·실행 중인 Run을 고르면 **이 Run 취소**(`POST /api/runs/{run_id}/cancel`)가 나온다.
- **키는 파일·브라우저 저장소에 남기지 않는다.** 탭 메모리에만 두고, 새로고침하거나 API 주소를 바꾸면 지워진다(다른 서버로 키가 가지 않게).
- 서버에 키가 설정돼 있지 않으면(`/api/health`의 `write_api_enabled: false`, 로컬 도커 기본값) 버튼이 비활성으로 나온다. 키가 틀리면 "키가 틀렸거나 비어 있어요"로 표시.
- 대기·실행 중인 Run이 있으면 F1 목록이 10초마다 갱신된다. 아직 결과가 없는 요청은 오류가 아니라 "결과 대기", 취소된 요청은 "취소됨"으로 표시.
- 확인: 로컬에서 쓰기 키를 켠 백엔드로 틀린 키 → 거절, 맞는 키 → Run 생성(대기) → 취소까지 동작. **GPU 워커가 실제로 추론해 결과가 채워지는 과정은 로컬에 워커가 없어 확인하지 못함.**
