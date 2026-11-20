# Team 1 · 생활도로 VLM 평가 벤치마크

2026-11-20 카카오모빌리티 멘토링 대비 부분 재설계(v1.1-review)의 종합 개발·검토 브랜치: `kakao1120_revision`.

기존 Track 1 의도 및 데이터·모델·채점·서비스 구조를 유지하면서 R1(점유), R2(연결부), R3(가림)과 보조 속성 4개(연결부 이용자, 전방 가림, 측방 가림, 병목)를 분리한다. v1.0 Run·정답·출력 기록은 별도 버전으로 보존하며 v1.0과 v1.1 점수를 섞지 않는다.

## 역할별 최신 작업 위치

| 담당 | 폴더 | 주요 자료 |
|---|---|---|
| 윤유경 · PM | [pm/](pm/) | [진행 요약·인수인계](README_v11_HANDOFF.md), [개정 명세](pm/SPEC_v11.md), 역할 명세 원본, 발표자료 링크 |
| 한태문 · 데이터 | [data_v11/](data_v11/) | 6장 v1.1 Draft, 후보 6장 카탈로그, 3장 독립 라벨링 양식, 수집 그룹 분리 및 이전 라벨 자료 |
| 하경흠 · 모델 | [ai_model/](ai_model/) | 기존 실제 Base 추론 패키지, [v1.1 모델 프롬프트 명세](ai_model/MODEL_PROMPT_v11.md), GPU 워커의 신규 A/B 프롬프트 링크 |
| 문혜승 · 백엔드 | [backend/](backend/) | FastAPI, 평가·대응 채점, 데이터 버전, 저장·조회, 마이그레이션, 33개 자동 테스트. [개정 안내](backend/REVISION_README.md) |
| 고연오 · 프론트 | [frontend/](frontend/) | [v1.1 F1~F5 API 연결 Viewer](frontend/f3-f5/app.html), 원형·템플릿·검증 코드. [개정 안내](frontend/REVISION_README.md) |
| 이전 산출물·발표 자료 | [docs/](docs/) · [benchmark/](benchmark/) | [11/20 발표 PDF](docs/mentoring/2026-11-20/Team1_Kakao_Mentoring_2026-11-20.pdf), [11/6 발표 PDF](docs/presentations/Kakao_VLM_Benchmark_Initial_Results.pdf), [기존 벤치마크 명세 PDF](docs/benchmark/Kakao_Road_VLM_Benchmark_Spec_Final.pdf), 기존 데이터·모델 실험 기록, v0 문항 및 채점기 |

## 실행 및 상태

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
export IMAGE_ROOT=/data/aihub_71784/images
export BOOTSTRAP_B=20
python -m pytest backend/tests -q
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8888
```

브라우저에서 `frontend/f3-f5/app.html`을 열고 `http://localhost:8888` 연결. v1.1 A/B Preview는 추론을 실행하지 않은 검토용 Run. 실제 저장 v1.0 Base와 함께 조회 가능. 상세 실행, 배포 및 데이터 적용 순서는 [인수인계](README_v11_HANDOFF.md) 참조.

| 확인된 사항 | 아직 필요한 사항 |
|---|---|
| 기존 Pilot 6개 Draft + 6개 후보 카탈로그, 독립 라벨링 도구, 버전 분할 | 2인 검수·합의, Reviewed GT, 독립 그룹 Test 확보·freeze |
| 신규 A/B 프롬프트 및 스키마와 기존 GPU 워커 연결 | 실제 GPU A/B 각 6장 추론, Tuned 모델 별도 실험 |
| 로컬 백엔드 테스트 및 F1~F5 실제 사진/API 연결 검증 | AWS 운영 적용·운영 환경 회귀 검증 |
| v1.1 핵심 9칸·보조 지표, 부분 검수와 미산출 처리 | 공식 성능 점수, 금지 대응 및 사람 진술 검수, Track 2/3 별도 입력 |

통합 브랜치 재검증: 백엔드 33개 + 기존 모델 CPU 패키지 검사 4개 = 37개 통과. F1~F5 브라우저 검사 및 독립 라벨링 양식 검사 통과. 근거는 [검증 기록](pm/VERIFICATION_1120.md) 참고.

## 기존 역할별 브랜치와 자료 보존

- [데이터 원본 작업](https://github.com/Spatzlyn/262RCOSE45700/tree/work/data-1115/docs/data/pilot_1115): 원본 이미지·AI Hub 원본 라벨은 기존 작업 브랜치 또는 승인된 AWS 데이터 경로 사용. 공개 종합 브랜치에 새로 복제하지 않음.
- [모델](https://github.com/Spatzlyn/262RCOSE45700/tree/work/model-1115), [백엔드](https://github.com/Spatzlyn/262RCOSE45700/tree/work/backend-1115), [프론트](https://github.com/Spatzlyn/262RCOSE45700/tree/work/frontend-1115): 기존 브랜치 변경 없음.
- [초기 v0 벤치마크](https://github.com/Spatzlyn/262RCOSE45700/tree/feat/benchmark-v0): 이전 실험 및 Track 2의 초기 작업 기록.
- 원본 데이터·실제 키/인증 정보·모델 가중치·비공개 AI 독립 답안·개별 라벨러 답안·생성 캐시 제외. 새 GPU 실행 및 운영 배포는 하지 않음.
