# 백엔드 · 문혜승 · v1.1

- [기존 백엔드 설명](README.md): API, Docker 및 GPU Worker 기초 구조.
- [v1.1 평가 코드](scorer/v11/), [공통 평가 처리](scorer/score.py), [API](app/), [신규 인수인계](../README_v11_HANDOFF.md).
- [스토어](store/): 기존 v1.0 실제 Base·예제 및 신규 v1.1 A/B Preview. 신규 Preview는 실제 미추론.
- [마이그레이션](tools/install_v11.py): 기존 운영 정답과 Run을 덮어쓰지 않는 dry-run·적용.
- [신규 테스트](tests/test_v11_integration.py) 및 기존 테스트: 전체 33개 통과(로컬).
- [이전 6장 v1.0 Draft 비교](examples/pilot6_draft_gt/): 기존 지표 비교용이며 새 v1.1 성능으로 간주하지 않음.

운영 배포 전 현재 스토어를 백업하고 동일 버전의 API/worker를 갱신. 실제 GPU와 사람 검수 전 신규 공식 점수 미산출. [실행·운영 인수인계](../README_v11_HANDOFF.md) 참조.

## 2026-11-25 · v1.1 Pilot A/B 채점

- 합의 GT `1.1-pilot6-reviewed-20261125` 가져오기(Reviewed 6건, 7개 판정만 검수). 모델팀 A/B Run `v11_a_e18f74ffcc`, `v11_b_9895a83702` 등록(`tools/import_v11_ab.py`).
- 문항별 결과·제외 사유·GT 버전: [docs/backend/v11_ab_scoring_20261125](../docs/backend/v11_ab_scoring_20261125/README.md) (`tools/export_v11_scoring.py`). 공식은 첫 응답 그대로(12건 형식 실패), 코드 펜스 제거 진단은 별도 표기.
- 테스트 36개 통과. 운영 서버는 아직 v1.0 코드이며 v1.1 배포는 별도(`tools/install_v11.py`).
