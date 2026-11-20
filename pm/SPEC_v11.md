# 생활도로 VLM · v1.1 부분 개정 검토안

2026-11-20 · 기준: v1.0 최종 명세 및 Pilot 6장. 이 버전은 사람 합의와 신규 모델 추론 전 검토용.

## 설계 이유

R1(점유)과 R4(통행 폭 감소)는 같은 객체로 인해 함께 성립하기 쉽다. 물리적인 병목의 유무는 도로 구조나 배치의 속성으로 옮긴다. 기존 R2는 Actor가 없는 연결부를 놓칠 수 있고, R3는 측방과 구조물 가림의 근거를 충분히 표현하지 못한다. 객체의 현재 위치·방향을 부가 정보로 기록한다. 네 항목에 맞추기 위해 중복 점수를 부여할 필요가 없다.

## 공간 기준

- D: 기존 C와 동일한 평가용 진행 공간. 보이는 진행 의도와 기존 도로 경계에 근거해 그린 Polygon. 기존 Pilot D를 유지한다. D는 일반적인 차폭에 해당하는 정밀 궤적이나 실제 주행 가능 경로로 해석하지 않는다.
- 자차 전면에서 도로 진행 방향·경계가 식별되는 마지막 구간까지 관찰한다. 측면 연결부는 이 구간의 D에 접하는 곳만 평가한다. 접지 또는 D 경계가 불명확하면 U.
- 공유 도로와 좁은 자차 참조 경로 P의 분리는 추후 별도 검증 대상. 본 개정에서 임의의 P를 생성하지 않는다. 투영된 Box 하단만으로 접지나 실제 폭을 확정하지 않는다.

| 평가 항목 | Y(P) | N(A) | U |
|---|---|---|---|
| R1 점유 / Occupancy | 시각적으로 확인 가능한 Actor/Obstacle의 발·바퀴 등 접지가 D 안과 겹침 | 충분히 관찰 가능한 대상의 접지가 모두 D 밖 | 점유 여부를 바꾸는 접지·경계 불명확 |
| R2 연결부 / Connectivity | D와 연속적으로 연결되는 골목, 주차장·차고·건물 보행 출입구의 실제 입구/경계 관찰 | 해당 구간 주변을 충분히 관찰했으며 연결부 없음 | 후보 개구부는 있으나 접근 경로·경계가 불명확함 |
| R3 가림 / Visibility gap | 전방 또는 측방의 진행 판단에 필요한 영역이 객체나 구조물로 가려짐 | 해당 관찰 구간에 필요한 영역이 확인됨 | 어느 영역이 실제로 가려지는지 또는 연결성이 불명확 |
| bottleneck (속성) / 병목 | 인접 구간보다 좁아지는 실제 공간 구조나 배치가 확인되고 좁아진 구간·원인을 지목 가능 | 관찰 구간에 뚜렷한 국소 폭 제약 없음 | 비교할 경계·원인·구간 부족 |

보행 출입문은 D까지 이어지는 실제 보행 연결을 확인할 때 포함한다. 닫힌 셔터나 쇼윈도만으로 연결부를 확정하지 않는다. R2 자체에 Actor가 필요하지 않다.

### 보조 판정 및 근거

- connection_actor: R2의 실제 연결부 내부 또는 경계에 보이는 Actor 존재. R2=A이면 NA, R2=U이면 U. 연결부가 관찰되더라도 내부가 필요한 만큼 보이지 않으면 U. R2=P와 Actor=A가 함께 가능.
- forward_occlusion / lateral_occlusion: 전방 D의 연장 / D와 이어지는 측방 공간의 가림. 측방 틈은 정식 출입구가 없어도 가능. 어느 한쪽 P이면 R3=P, 둘 다 A이면 R3=A, 그 외 U. 눈부심·화질 저하는 물리적 가림을 입증하지 못하면 U.
- 객체 위치: location = in_D / adjacent / outside / unknown. adjacent는 D 밖 바로 이어진 도로·보행 공간에 있는 대상, 거리 수치 추정 금지. 관찰 가능한 경계를 근거로 하며 애매하면 unknown. 연결부에 있는 객체는 connection_actor에서 별도 표시; 같은 객체가 R1과 연결부 관계에 동시에 해당 가능.
- orientation = same / opposite / transverse / unknown / not_applicable. 보행자의 몸 방향과 차량의 앞·뒤를 해당 위치의 도로 방향과 비교; 실제 이동·의도·속도는 추정하지 않음.
- R1의 P 근거는 객체 ID, R2의 P 근거는 연결부 Region ID, R3의 P 근거는 가림 Region ID. R3의 원인은 객체 ID 또는 사유에 적은 구조물. 관찰할 수 없는 숨은 영역의 Polygon을 만들어 내지 않는다. 가시 범위나 입구 경계의 근거만 표시하고 미측정 geometry는 null로 저장.
- bottleneck은 기존 R4와 다른 정의. 명확한 공간 제약의 원인과 위치를 기록하며 실제 자차 통과 가능성을 확정하지 않는다. 구간이 모호한 경우 U. 폭·거리·차량 제원이 확보되면 정량 속성으로 확장 가능.
- 화면에서는 P/A/U/NA를 Y/N/U/해당 없음으로 표시. null은 아직 검수하지 않은 필드. D는 모델에게 정답으로 제공하지 않는다.

## 대응 정책 (오프라인 평가용 검토 규칙)

기존 App. B의 점유 대상별 원칙을 유지하되 길가 차량/고정 장애물 점유에 대한 확인 근거를 직접 R1에 연결한다. 병목 유무가 R1에서 자동 파생되지 않는다. 아래는 벤치마크 출력 코드의 비교 기준이다.

| 근거 조건 | 필요 코드 대안 |
|---|---|
| R1=P, 일반 Actor 점유 | YIELD_IF_OCCUPIED 또는 HOLD_UNTIL_CLEAR / while_corridor_occupied / R1 |
| R1=P, 길가 차량 또는 고정 장애물 점유 | VERIFY_PASSAGE / before_passing_occupying_object / R1 (보류도 허용) |
| R2=P | MONITOR_AHEAD 또는 REDUCE_SPEED_IF_MOVING / at_connected_opening / R2 |
| R3=P | VERIFY_BEFORE_ADVANCE / before_entering_occluded_area / R3 |
| bottleneck=P | VERIFY_PASSAGE / before_passing_restricted_section / bottleneck |
| R1/R2/R3/bottleneck 중 U | VERIFY_BEFORE_ADVANCE / before_resolving_uncertainty / 해당 U 항목 전부 |
| 모두 A | MONITOR_AHEAD 또는 ADVANCE_WITH_MONITORING / no_condition / R1,R2,R3,bottleneck |

둘 이상의 필요 대응 그룹은 모두 충족. 방향 충돌 장면은 기존 명세대로 대응 채점 제외. 객체 배치·역할 및 모든 관련 항목이 검수된 경우에만 대응을 채점한다. 위 조건은 잠정 규칙이며 실제 운행 지시가 아니다.

## 채점과 재현

- 기존 v1.0의 R1~R4 점수와 Run ID를 보존. v1.1 출력은 별도 schema_version과 새 Run ID 사용. v1.0 결과를 v1.1 결과로 자동 변환하거나 새 점수로 표시하지 않음.
- v1.1 핵심 관계 Macro-F1은 R1~R3 × P/A/U 9개 칸. 검수 정답이 모든 칸을 포함할 때만 산출. 보조 항목별 정확도·분모 및 점유 역할, 근거 검사를 별도로 확인.
- Draft 전체 채점 제외. Reviewed에서 필드별 승인 범위만 비교. 유효하지 않은 응답은 검수된 비교 칸에서 오답으로 기록. 부분 검수의 대응 점수는 N/A.
- 기존 객체 IoU 매칭 및 속성 평가, bootstrap·freeze 기능의 운영 연동은 담당자 인수 후 연결. 본 검토 코드는 버전 게이트, 관계·보조 상태 및 조건부 대응의 별도 채점 경로를 제공한다.
- Pilot 6장의 사진을 검토해 사람이 확정할 후보 라벨을 작성. 모든 Reference는 Draft이며 검수된 v1.1 점수나 추론 결과는 아직 없다. 기존 실제 v1.0 Base 결과는 참고 탭으로만 표시.
