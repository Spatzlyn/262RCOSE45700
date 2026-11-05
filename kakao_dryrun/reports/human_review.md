# Human adjudication 검토표

모든 항목은 pending입니다. 두 reviewer가 독립 판정한 뒤 차이를 합의하고 rule version·근거·최종 값을 기록하도록 작성했습니다. 이 audit에서는 GT나 판정을 수정하지 않았습니다. 입력 가능한 원본 표는 [human_review.csv](human_review.csv)입니다.

| ID | 현재 Draft | 확정할 내용 | 영향 | 상태 |
|---|---|---|---|---|
| OBJ_F_742182 | powered_two_wheeler / 354.00,373.00,450.00,512.00 | 좌측 건물 전면 가까이 있는 scooter. 정차·이동 상태는 확인되지 않습니다. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_742183 | truck / 1847.00,366.00,1920.00,484.00 | 화면 오른쪽 가장자리에 일부만 보이는 truck. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_742184 | bicycle / 1843.00,545.00,1919.00,686.00 | 화면 오른쪽 가장자리에 일부만 보이는 bicycle. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_742185 | powered_two_wheeler / 501.00,338.00,562.00,453.00 | 좌측 건물 전면 가까이 있는 delivery scooter. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_742186 | truck / 0.00,93.00,346.00,881.00 | 왼쪽 전경의 pickup과 위로 뻗은 적재물. Source Box는 적재물까지 포함합니다. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_742187 | truck / 580.00,284.00,713.00,453.00 | 왼쪽 앞 도로 가장자리에 배치된 truck. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_742188 | car / 703.00,327.00,914.00,471.00 | 전방의 검은 sedan. 차량 앞면이 카메라 쪽을 향하지만 이동 방향·속도는 확인되지 않습니다. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_742189 | car / 1113.00,297.00,1403.00,519.00 | 오른쪽 도로 가장자리에 배치된 SUV. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_742190 | truck / 988.00,208.00,1211.00,469.00 | 오른쪽 앞의 box truck. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_742191 | speed_bump / 911.00,388.00,1000.00,400.00 | 차량들 사이로 일부 보이는 황백색 speed bump. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_added_001 | pedestrian / 540.00,353.00,567.00,429.00 | 배달 scooter 뒤쪽에 머리·얼굴·상체 일부가 보이는 별도 사람입니다. 발·하체는 가려져 있고 정확한 접지 위치와 출입구 경계 관계는 미확정입니다. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_added_002 | stored_items / 1407.00,366.00,1521.00,518.00 | 오른쪽 건물 앞의 흰 포장재·상자와 검은 판재가 붙어 있는 적치 군집입니다. 개별 조각 대신 연속된 하나의 적치 군집을 기록했습니다. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_added_003 | bag_or_bundle / 1628.00,421.00,1698.00,500.00 | 오른쪽 건물 앞 봉투 또는 덮개로 싸인 묶음입니다. 내용물을 쓰레기라고 단정하지 않습니다. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_added_004 | car / 712.00,323.00,760.00,379.00 | 전방 sedan 왼쪽 뒤의 흰 차량입니다. 소형 트럭·sedan에 가려져 접지 부위를 충분히 확인하지 못합니다. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_added_005 | car / 890.00,324.00,939.00,368.00 | 전방 sedan 오른쪽 뒤에 보이는 후면 방향의 밝은 차량입니다. 주변 차량과의 가림 때문에 Footprint 검수가 필요합니다. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| OBJ_F_added_006 | car / 926.00,325.00,984.00,379.00 | 오른쪽 box truck 왼쪽 뒤에 보이는 전면 방향의 밝은 차량입니다. 원거리이며 일부가 가려져 정확한 접지 범위는 추가 검수합니다. Class, 가시 Box 범위, Source codebook 대응 및 평가 대상 포함 여부를 확정하십시오. | Object denominator/class/IoU; 아직 변경하지 않음 | pending |
| C | C polygon | 도로 구조와 Intent로 경계·먼 쪽 종료를 독립 검수하십시오. | R1/R4 및 근거 집합 | pending |
| R1 | P / F_742187,188,189,190 | 4개 접지점과 non-roadside F_742188 점유/placement를 확정하십시오. | PDF Roadside-only 예외 적용 여부 | pending |
| R2 | U | 보이는 pedestrian/scooter의 footprint, entrance 경계와 C 연결을 확정하십시오. 사람 존재만으로 P로 변경하지 마십시오. | A/U/P와 uncertainty Action | pending |
| R3 | P / hidden geometry=null | 진행 판단에 필요한 가림의 범위와 occluder 집합을 확정하고 관측 불가 geometry의 scoring policy를 정하십시오. | Region evidence deferred 정책 | pending |
| R4 | P | 통행 제한 구간과 F_742186 후보 포함 여부, 충분한 대안 evidence set을 확정하십시오. | exact-set evidence 및 VERIFY_PASSAGE | pending |
| ACTION_RULE | PDF vs ZIP | Roadside/Obstacle R1 예외 및 REDUCE_SPEED_IF_MOVING 허용 규칙을 하나의 version으로 고정하십시오. | required/allowed set | pending |
| ATTR | Unknown / Unknown / U / U | Traffic sign 판독 가능성과 좌우 Sidewalk 평가 범위를 검수하십시오. 녹색 노면을 보도로 자동 치환하지 마십시오. | attributes | pending |
| COVERAGE | partial_draft | 원거리 객체 개체 분리·누락과 포함 기준을 확정하십시오. | 완전 GT 및 공식 V3 | pending |
| EVIDENCE | R1 15 alternatives, R2/R3/R4 each 1 | 충분한 대안 근거와 역할을 독립적으로 등록하십시오. | V4 exact-set 과도한 제한 방지 | pending |
