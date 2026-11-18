# 생활도로 위험 판단 VLM · Team 1

보도 없는 생활도로의 전방 사진에서 객체를 찾고, 진행 공간과 객체 사이의 관계 및 그 판단 근거를 평가하는 벤치마크입니다.

## 진행 현황

2026년 11월 19일 기준 · GitHub 공개 작업 기록

- **데이터** — Track 1 공통 Pilot 6건에 진행 공간, 객체 박스, R1–R4 관계와 근거 객체 ID의 1인 초안 라벨 작성.
- **모델** — 동일 Pilot 6건의 Base 추론 결과 저장. 6건 모두 출력 형식 검사 통과.
- **백엔드** — 추론 Run 저장·조회 및 평가 결과 API 구현. 1인 라벨 초안과 Base의 R1–R4 관계 값 24개 중 16개가 일치했으며, R1은 6건 중 3건에서 일치. 검수 완료 정답의 평가는 팀 합의 후 진행.
- **프론트엔드** — 실행·리포트·오류 목록·비교·장면 상세 화면으로 Run과 판정 근거를 확인할 수 있는 Viewer 구현.
- **Track 2** — 사고 대상 보행자를 선택하는 초기 문항과 채점 흐름을 v0에서 구성. 영상별 충돌 시점과 대상 ID를 검수한 뒤 판단 시점까지의 입력으로 평가할 계획.

## 파트별 작업 기록

| 파트 | 확인할 수 있는 자료 |
| --- | --- |
| 기획·평가 명세 | [벤치마크 및 개발 명세서](docs/benchmark/Kakao_Road_VLM_Benchmark_Spec_Final.pdf) |
| 데이터 | [Pilot 산출물과 라벨링 자료](https://github.com/Spatzlyn/262RCOSE45700/blob/work/data-1115/docs/data/pilot_1115/README.md) |
| 모델 | [Base 추론 실행 방법과 코드](https://github.com/Spatzlyn/262RCOSE45700/blob/work/model-1115/ai_model/inference/README_ko.md) |
| 백엔드 | [API·채점·저장 구조](https://github.com/Spatzlyn/262RCOSE45700/blob/work/backend-1115/backend/README.md) · [Pilot 6건 관계 대조 결과](https://github.com/Spatzlyn/262RCOSE45700/blob/work/backend-1115/backend/examples/pilot6_draft_gt/README.md) |
| 프론트엔드 | [평가 Viewer 구현](https://github.com/Spatzlyn/262RCOSE45700/tree/work/frontend-1115/frontend/f3-f5) |
| 초기 벤치마크 | [v0 문항과 실행 자료](https://github.com/Spatzlyn/262RCOSE45700/tree/feat/benchmark-v0) |
| 발표 자료 | [11월 6일 초기 발표자료](https://github.com/Spatzlyn/262RCOSE45700/blob/kakao_meeting_1106/docs/presentations/Kakao_VLM_Benchmark_Initial_Results.pdf) · [공개 자료 목록](docs/mentoring/2026-11-20/PUBLIC_MATERIALS.md) |

## 다음 단계

Track 1은 합의한 정답을 등록하고 촬영 그룹 기준으로 Test를 고정한 뒤 Base 지표와 오류 사례를 정리합니다. Track 2는 검수 가능한 사고 영상이 확보되면 사고 전 입력으로 대상 보행자를 선택하는 사례를 시연합니다.
