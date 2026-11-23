# Pilot 6장 A/B 최초 응답
A와 B는 동일한 부록 B 규칙을 사용한다. B에만 R1 접지 재확인 지시 한 문장이 추가되었다. 각 조건의 pilot_001부터 pilot_006까지 원문(raw_output.txt), 파싱 결과(parsed_output.json), 검증 기록(output_validation.json)을 보존했다. run_manifest.json은 실행 ID, 버전 및 해시를 제공한다.

형식 검증은 A 5/6, B 6/6이다. A의 003은 좌표 범위 오류가 있는 첫 응답 그대로다. Reviewed GT 수령 후 이 예측을 채점하며, 라벨 버전·검수 범위·형식 실패 처리 기준을 함께 기록한다.

run_pilot_ab.py의 원래 위치는 pilot-1115/submission/scripts이며 같은 위치의 run_gemma_pilot_smoke.py를 호출한다. 실제 실행은 기존 로컬 작업 디렉터리와 모델, 입력 이미지, Base 실행 기록을 사용했다. 결과 검토와 채점에는 재추론이 필요하지 않다.

- [공통 추론 코드](https://github.com/Spatzlyn/262RCOSE45700/tree/d6553eae923d77c052f994f4fa75b3f87a82bb8c/ai_model/inference)
- [두 프롬프트](https://github.com/Spatzlyn/262RCOSE45700/tree/14f110cd7a2beeb6a3d41d77d932d5af16e89810/docs/model/pilot_1122)
