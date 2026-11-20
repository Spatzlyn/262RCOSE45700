# 모델 · 하경흠

이 폴더에는 팀원이 제출한 기존 실제 Base 추론 코드와 현재 v1.1 개정 프롬프트 명세를 함께 보존한다.

- [기존 추론 패키지](inference/README_ko.md) / [실제 Base 결과와 원시 출력](../docs/model/pilot_1115/) (`work/model-1115` 14f110c).
- [기존 A/B 계획과 오류 분석](../docs/model/pilot_1122/): v1.0 기준 참고자료.
- [v1.1 프롬프트 작성 명세](MODEL_PROMPT_v11.md) / [예측 스키마](../backend/scorer/v11/prediction.schema.json).
- API와 GPU 워커가 읽는 실제 파일: [prompt_v11_a](../backend/worker/prompts/prompt_v11_a/), [prompt_v11_b](../backend/worker/prompts/prompt_v11_b/), [worker.py](../backend/worker/worker.py). 중복 파일에 의해 프롬프트가 어긋나지 않도록 운영 코드 위치를 단일 원본으로 유지한다.

v1.1 A/B 실제 GPU 추론은 아직 미실행. 두 버전의 Preview는 결과가 아닌 검토용이며 기존 실제 v1.0 Base를 v1.1 예측으로 취급하지 않는다. 동일 모델·revision·seed·decoding 설정으로 신규 Run을 생성해 원시 출력을 기록한다. Tuned 가중치 및 실제 adapter 로딩·평가는 별도 작업.
