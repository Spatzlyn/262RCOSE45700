# Team1 · v1.1 재설계 통합 검토본 (2026-11-20)

## 무엇이 바뀌었는가

기존 백엔드 `0b8ab35`, 프론트엔드 `4bdd10d`를 바탕으로 수정한 통합 복사본이다. 기존 팀 브랜치나 운영 서버에는 반영하지 않았다. v1.0 저장 Run, GT, 프롬프트, 채점 및 화면의 기존 관계 4개는 유지한다. v1.1에는 R1 점유 / R2 연결부 / R3 가림 및 연결부 이용자·전방 가림·측방 가림·병목을 추가하고 별도 스키마, 참조 정답, 프롬프트, 리포트로 분리한다. R4 병목은 핵심 관계가 아닌 보조 속성이다.

- 데이터: 실제 Pilot 6장과 기존 D 6개·Box 56개 재사용, 신규 핵심·보조 관찰 42개를 Draft로 등록. 각 이미지 SHA-256 확인. 원본 AI Hub 정답을 Reviewed로 승격하지 않음.
- 추가 후보: 6장 카탈로그 배치. Pilot과 동일 Source Group의 후보 1장도 dev로 묶음(총 dev 7장), 나머지 5장은 미배정. Test freeze 없음.
- 모델: prompt_v11_a/b, 스키마 및 해시 등록. 기존 GPU 워커가 새 프롬프트를 읽고 item_id만 교체하는 메시지 구성 검증. 두 프롬프트 모두 실제 GPU 추론 미실행. 이전 Base 추론 결과 유지. Track 2/3은 입력 없음(missing_input)으로 명시; 해당 Track의 모델 성능 주장은 없음.
- 백엔드: 3×3 핵심 관계 점수, 보조 4개 지표, 조건·근거 일치 및 관계 기반 대응, 항목별 사람 검수 여부, V13/14 사람 검수 입력 경로, 버전 라우팅, API·CSV 및 비교·freeze 검증. 사람 검수되지 않은 값은 미채점. 명시적 금지 대응 목록(V12)은 합의 전 미산출. 서로 다른 스키마 Run은 성능 비교 차단.
- 프론트: 기존 실제 API 기반 `frontend/f3-f5/app.html`에서 F1 새 실행 프롬프트·문항 선택, F2 핵심 9칸과 보조 지표, F3 검토/오류 목록 구분, F4 동일 버전 비교, F5 실제 사진·D Polygon·Box·핵심 및 보조 관계·객체 위치/방향 표시. v1.0 Run 선택 시 12칸과 기존 4개 관계로 복원.

## 빠른 검토 (운영 서버를 건드리지 않는 로컬 모드)

`kakao1120_revision`을 별도 폴더에 체크아웃. `backend/store`는 검토용 데이터 저장소다. 원본 사진을 공개 종합 브랜치에 복제하지 않았으므로 실제 사진 표시에는 기존 AI Hub `images/K`, `images/V` 경로가 필요하다. 기존 운영 저장소에 이 브랜치의 `backend/store` 전체를 덮어쓰지 말 것.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
export IMAGE_ROOT=/data/aihub_71784/images
export BOOTSTRAP_B=20
python -m pytest backend/tests -q
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8888
```

`frontend/f3-f5/app.html` 파일을 브라우저에서 열고 API 주소를 `http://localhost:8888`로 선택. Run `RUN-PILOT6-V11-A-PREVIEW`를 선택. B도 검토 전용. F1~F5 동작을 확인할 수 있으나 실제 새 예측은 없음. F3에서 pilot_002 클릭 → F5 사진, 진행 공간 D, Box, R1–R3와 보조 항목 확인. v1.0 `RUN-PILOT6-BASE-001`을 선택하면 기존 기록 확인 가능. 새로운 실제 추론은 preview Run에 덧붙이지 않고 별도 Run을 생성.

`python -m backend.tools.build_blind_viewer --images /data/aihub_71784/images --forms data_v11`로 `data_v11/Pilot3_v11_Blind_Labeling.html`을 로컬에서 생성(이미지 3장 포함, GitHub 업로드 제외). 각각 다른 브라우저 프로필에서 작성자 이름·D·판정 및 근거·시간을 입력한 후 JSONL 저장. R3 자동 합성, R2에 따른 이용자 적용 여부 자동 처리. PM/AI 참고 답안은 공유 브랜치에 넣지 않음. 두 인간의 독립 답안은 `python -m backend.tools.import_references rounds <file.jsonl>`로 따로 입력. 이때 사람이 작성한 기록만 사람 간 일치도에 사용. 이후 합의본을 별도의 새 reference_version으로 기록하고 명시적으로 Reviewed 처리.

## 실제 서버 적용 순서 (혜승님 확인)

1. 현재 백엔드·프론트·GPU 워커 브랜치와 수정 복사본을 diff로 검토하고 충돌 해결. 기존 최신 변경이 있다면 우선 보존. 현재 운영의 store를 백업한 뒤 API와 worker를 멈춰 추가 쓰기가 없는 상태에서 적용.
2. 저장소 마이그레이션 스크립트 dry-run 후 적용 (기존 v1.0 정답·Run 파일 바이트 변경 없음, 샘플에서 반복 적용 시 추가 변경 없음 확인). 운영의 실제 mount 경로를 확인하여 지정.

```bash
python -m backend.tools.install_v11 --target /data/backend-store
python -m backend.tools.install_v11 --target /data/backend-store --apply
```

3. 기존 도커 환경 설정과 서비스 키 보존. `backend/docker-compose.yml`의 기존 배포 절차로 API를 새 코드로 빌드하고 GPU 워커 코드/프롬프트 경로를 같은 버전으로 갱신. 기존 키는 별도로 전달·노출하지 않음. `/api/versions`, `/api/runs`, `/api/items?schema_version=1.1-review&data_kind=real` 확인.
4. 기존 API 주소를 연결한 프론트에서 A/B Preview, 기존 Base, 그림 및 미추론 표시 확인. 화면을 재사용하면서 새 버전 선택 가능.

## 실제 A/B 추론 및 검수 순서 (경흠님·태문님 확인)

1. 경흠님: 실제 GPU에 설치된 Gemma 버전, 모델 revision·양자화·동일 seed/decoding 조건 확인. F1 또는 API를 통해 동일 Pilot 6개에 `prompt_v11_a`, `prompt_v11_b`를 각 별도 실행. 기존 원시 출력 보존. A/B 두 Run 모두 6건의 상태·원시 텍스트·스키마 결과 기록. 형식 통과율은 정답 정확도가 아님. Tuned adapter 학습/로딩/평가 실험은 별도 작업이며 현재 worker에는 실제 adapter 로딩 미구현.
2. 태문님·유경님: 기존 6개 Draft를 근거 ID와 D/Box까지 대조. 002 흰 차량 접지와 D, 연결 후보, 003 D 원단·주차 공간의 관계를 합의. 새 후보 3장은 서로 답을 보지 않고 작성, 이후 불일치 합의 및 원본 보존. 모든 필드·객체 역할·대응·장면 속성의 실제 검수 범위를 표시. 부족한 Y/N/U 셀을 채워 독립 Source Group으로 최종 Test 배정. 정량 폭 기준은 아직 확정하지 않음.
3. 혜승님: 합의 참조 정답 import 후 공식 점수 재계산. V12 금지 대응 후보 목록 및 V13/V14 사람의 문장 검수 입력 확인. 실제 데이터의 검수 기록과 split freeze, source group 누수 점검. 프론트의 점수와 API 수치 일치 여부 확인.
4. 연오님: 실제 배포 주소로 새 HTML의 F1~F5 전체 동작 확인. 네트워크 오류·취소·실행 대기·Draft·미산출과 예측 부재 구분. 기존 Run도 회귀 확인. 실서비스 URL 연결 결과 캡처.

## 핵심 파일

| 담당 | 파일 |
|---|---|
| 데이터 | `data_v11/pilot6_v11_draft.jsonl`, `data_v11/Pilot3_v11_Blind_Labeling.html`, `data_v11/candidate_blank_all6.jsonl`, `backend/store/splits/v11-pilot-dev.json` |
| 모델 | `backend/worker/prompts/prompt_v11_a/`, `prompt_v11_b/`, `backend/scorer/v11/prediction.schema.json` |
| 백엔드 | `backend/scorer/v11/`, `backend/scorer/score.py`, `backend/app/`, `backend/tools/install_v11.py`, `backend/tools/import_references.py` |
| 프론트 | `frontend/f3-f5/template.html`, `app.html` (API), `index.html` (기존 단일 파일 모드) |
| 검증 | `backend/tests/test_v11_integration.py`, `browser_verification.json`, `check_f1_f5.mjs`, `check_blind_form.mjs` |

검증은 로컬 CPU API/브라우저에서 수행. 새 GPU 추론, 실제 사람 합의·라벨 품질 수치, 운영 인스턴스 배포 및 Tuned 성능은 수행하지 않았음. 코드·테스트·검토본 근거로 미팅에서 시연 가능하나 신규 VLM 성능으로 발표해서는 안 됨.
