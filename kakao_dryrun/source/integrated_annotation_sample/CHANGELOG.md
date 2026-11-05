# 변경 내역

## integrated-sample-0.2 · 2026-11-05

원본 이미지와 Source JSON, 기존 객체 18개의 출처·좌표를 보존하면서 누락 객체와 출력·평가 구조를 보완했습니다. 이번 수정은 AI Draft이며 독립 Human Review나 실제 모델 추론은 수행하지 않았습니다.

| 변경 | 적용 내용 |
|---|---|
| 객체 보완 | F 6개, B 4개, L 1개, R 6개를 추가하여 전체 35개 |
| F 사람 | 배달 scooter 옆에 보이는 별도 사람 추가. 가려진 하체·접지는 추정하지 않음 |
| F 적치물·차량 | 오른쪽 적치 군집·봉투/포장물과 식별 가능한 원거리 차량 3대 추가 |
| 보조 시야 | 식별 가능한 차량·이륜차·적치물·cone/표지 시설물 등 11개 추가 |
| 라바콘 의심 부분 | F의 붉은 부분은 후미등·차체와 구분되지 않아 Object로 확정하지 않고 검수 후보로 기록 |
| R1 근거 | sedan 외 F_742187·189·190의 가시 타이어 접지점 보완. 장면 P 유지 |
| R2 근거 | 추가 사람을 연결하되 출입구 경계·C 연결 미확정으로 U 유지 |
| R4 근거 | F_742186을 영향 구간 검수 후보로 분리. C 비중첩을 제외 규칙으로 사용하지 않음 |
| 객체 속성 | 의미 역할·배치·이미지 잘림과 필드별 출처·근거·Draft 상태 추가 |
| speed_bump | `road_feature` 역할로 구분하고 Pilot R1 Actor/Obstacle 점유 대상에서 제외 |
| Sidewalk·노면 | 전역 좌우 U 유지. 가까운 가시 범위와 녹색 노면 존재·용도 불확실성 구분 |
| Time of Day | 분석용 Annotation에 유지하고 모델 출력 요구에서 제거 |
| Region·근거 역할 | 상세 Annotation의 기존 Region·역할을 보존하고 모델 출력 Schema·예시까지 확장 |
| 평가 진단 | ID 문자열 대신 Class·IoU 대응과 역할을 비교. 기하 없는 Region은 평가 보류 |
| 문서·HTML | 상세 Annotation과 출력 예시를 구분하고 추가 객체·검수 후보·미해결 기준을 반영 |

C Polygon은 v0.1 비교 기준으로 동결한 Draft이며 새 경계가 확정된 것은 아닙니다. 폭·깊이와 평가 범위는 `ANNOTATION_GUIDELINE.md`에 따라 검수해야 합니다. 현재 객체 목록도 완전한 검출 정답으로 선언하지 않습니다. 따라서 검수 완료 표본은 0개이고 공식 V3/V4 점수는 `null`입니다.

F/B/L/R은 하나의 Source Group을 유지합니다. B/L/R의 R1–R4 `null`, Track 2·3의 `missing_input` 및 `null` 처리도 유지했습니다.

## integrated-sample-0.1

방향별 Source 객체 18개와 F 문항의 Relation·Action Draft를 통합한 최초 실행 예시입니다. 상세 Annotation에는 C·출입구 후보·가려진 Region과 근거 역할이 있었으나 모델 출력 예시는 축약되어 있었고, 평가 코드는 네 Relation과 Action 규칙 비교에 한정되었습니다.
