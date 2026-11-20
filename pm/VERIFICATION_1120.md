# 11/20 종합 브랜치 검증 및 원본 이력

## 로컬 결과

| 검토 | 결과 |
|---|---|
| `python -m pytest -q backend/tests ai_model/inference/tests` | 37 passed (백엔드 33, 기존 모델 패키지 4), 경고 2개 |
| vscode 없이 로컬 API + 실제 Pilot 이미지 연결 | F1~F5 및 기존 v1.0 전환, 7개 확인 항목 통과 ([기록](../browser_verification.json)) |
| `python -m backend.tools.build_blind_viewer --images <원본 경로> --forms data_v11` | 해시 일치한 3개 사진으로 빈 독립 라벨링 폼 생성 |
| `node check_blind_form.mjs` | R2 적용 여부, R3 합성, JSONL 및 미채움 확인 |

2026-11-20 재검증. 실제 GPU v1.1 A/B 추론, 사람 간 합의, AWS 운영 배포는 미실행. 원본 이미지와 실제 독립 답안·비공개 AI 참고 답안은 공개 브랜치에 포함하지 않음.

## 작업 원본

| 출처 | 기준 커밋 및 처리 |
|---|---|
| `kakao_meeting_1120` | `dbe7b24` 기반으로 새 브랜치 생성, 발표 및 기존 자료 보존 |
| `work/data-1115` 및 PM 데이터 검토 | `b08b750`, `9f3fd07`의 초안·manifest·가이드 유지. 원본 파일은 기존 경로 참조 |
| `work/model-1115` | `14f110c`의 기존 모델 실행 패키지와 실제 출력·정리 자료 보존 |
| `work/backend-1115` 및 PM 백엔드 검토 | `5027937`의 기존 비교 예시 및 `0b8ab35` 기반 v1.1 통합 코드. v1.0 저장 데이터 보존 |
| `work/frontend-1115` 및 PM 프론트 검토 | `9115f59`, `4bdd10d` 기반 v1.1 F1~F5 Viewer 보존 |
| `feat/benchmark-v0` | 초기 8문항·데이터 목록·채점기·뷰어 코드 보존, 영상 프레임은 기존 경로 사용 |
