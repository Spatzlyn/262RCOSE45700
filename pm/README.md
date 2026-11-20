# PM · 윤유경

## 최신 검토 자료

- [v1.1 개정 명세](SPEC_v11.md): 관계 정의, 동시 충족, 보조 속성과 판정 기준.
- [인수인계·실행 가이드](../README_v11_HANDOFF.md): 데이터·모델·백엔드·프론트 변경 및 담당별 후속 작업.
- [이전 역할별 명세 PDF](role_specs/): 변경 전 역할 범위 참고. v1.1의 정의와 상태는 위 최신 명세를 우선한다.
- [11/20 카카오 미팅 발표](../docs/mentoring/2026-11-20/Team1_Kakao_Mentoring_2026-11-20.pdf): 재설계 직전 발표·진행자료로 보존. 개정 후 변경 설명은 최신 명세 및 인수인계 참조.
- [11/6 초기 발표](../docs/presentations/Kakao_VLM_Benchmark_Initial_Results.pdf) · [기존 평가 명세](../docs/benchmark/Kakao_Road_VLM_Benchmark_Spec_Final.pdf) · [용어·해외 벤치마크 비교](../docs/mentoring/1120-terminology-and-benchmarks.md).

## 마감 흐름

1. 데이터: Draft 검토 → 사람 독립 검수 → 합의 정답·Test split.
2. 모델: 실제 GPU에서 v1.1 A/B 동일 6장 추론, 원시 결과 보존. 필요한 경우 별도 Tuned 비교.
3. 백엔드: 버전 별도 적용·재채점·검수 상태 및 split 확인. 공식 성능 비교는 합의 정답과 동일 버전에서만.
4. 프론트: 운영 API 및 이미지 경로 연결, 실제 Run·실패·대기·미검수 표시 검증.
5. PM: 결과·한계·멘토 피드백 정리, Track 2/3의 추가 입력과 범위 확정.
