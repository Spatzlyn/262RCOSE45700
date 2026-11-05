# Object denominator와 좌표 audit

`Object match 3/16`은 `sample_front_001`의 유일한 입력인 **F 이미지**에서 `annotations/view_F.json.objects` 전부를 대상으로 계산했습니다. Source Box 10개와 AI-added Draft Box 6개입니다. Source Box의 class도 별도 codebook 확인 없이 visual normalization한 Draft입니다. B 8개, L 3개, R 8개는 제외됐고, F Region 3개와 review_candidates도 분모에 없습니다. C 내부 여부·크기·class에 따른 Object 필터는 없습니다. 따라서 R1 대상이 아닌 speed_bump도 Object 분모에 포함됩니다.

매칭은 **class exact match + IoU ≥ 0.5 + one-to-one maximum cardinality, 이후 total IoU 최대화**입니다. ID 문자열은 점수 기준이 아닙니다. 아래 best geometry는 실패 원인을 찾는 후보이며 실제 match가 아닙니다. 0 overlap에서는 임의 후보 ID를 표시하지 않았습니다.

| # | GT / class | 실제 match / class | match IoU | best geometry / class / IoU | 결과 |
|---|---|---|---|---|---|
| 1 | F_742182 / powered_two_wheeler | — / — | — | — / — / 0.0000 | 동일 class 예측 없음; 해당 대상 누락 |
| 2 | F_742183 / truck | — / — | — | — / — / 0.0000 | 동일 class의 해당 위치 Box 없음 / IoU < 0.5 |
| 3 | F_742184 / bicycle | — / — | — | — / — / 0.0000 | 동일 class 예측 없음; 해당 대상 누락 |
| 4 | F_742185 / powered_two_wheeler | — / — | — | — / — / 0.0000 | 동일 class 예측 없음; 해당 대상 누락 |
| 5 | F_742186 / truck | — / — | — | obj_4 / car / 0.7803 | class mismatch; geometry는 threshold 통과 |
| 6 | F_742187 / truck | — / — | — | obj_1 / car / 0.0541 | 동일 class의 해당 위치 Box 없음 / IoU < 0.5 |
| 7 | F_742188 / car | obj_1 / car | 0.8592 | obj_1 / car / 0.8592 | match: class 일치 + IoU ≥ 0.5 |
| 8 | F_742189 / car | obj_2 / car | 0.7730 | obj_2 / car / 0.7730 | match: class 일치 + IoU ≥ 0.5 |
| 9 | F_742190 / truck | obj_3 / truck | 0.6443 | obj_3 / truck / 0.6443 | match: class 일치 + IoU ≥ 0.5 |
| 10 | F_742191 / speed_bump | — / — | — | obj_3 / truck / 0.0059 | 동일 class 예측 없음; 해당 대상 누락 |
| 11 | F_added_001 / pedestrian | — / — | — | — / — / 0.0000 | 동일 class 예측 없음; 해당 대상 누락 |
| 12 | F_added_002 / stored_items | — / — | — | — / — / 0.0000 | 동일 class 예측 없음; 해당 대상 누락 |
| 13 | F_added_003 / bag_or_bundle | — / — | — | — / — / 0.0000 | 동일 class 예측 없음; 해당 대상 누락 |
| 14 | F_added_004 / car | — / — | — | obj_1 / car / 0.0815 | 동일 class의 해당 위치 Box 없음 / IoU < 0.5 |
| 15 | F_added_005 / car | — / — | — | obj_1 / car / 0.0420 | 동일 class의 해당 위치 Box 없음 / IoU < 0.5 |
| 16 | F_added_006 / car | — / — | — | obj_3 / truck / 0.0058 | 동일 class의 해당 위치 Box 없음 / IoU < 0.5 |

Source Box만 분리하면 3/10, added Draft만 보면 0/6입니다. R1 근거로 지정된 4개 차량 중에서는 3개가 geometry/class match입니다. 이 값들은 원래 점수를 대체하지 않는 subset diagnostic입니다. 이미 찾은 3개 차량도 Relation evidence로 연결하지 않았으므로 낮은 Relation 점수를 Object 누락만으로 설명할 수 없습니다.

좌표는 `x_pixel=x_norm×1920`, `y_pixel=y_norm×1080`입니다. `bbox_xywh_pixels`는 `[x,y,x+w,y+h]`로 변환하여 대조했습니다. normalized 좌표가 소수 6자리로 저장돼 생긴 최대 차이는 0.000960 pixel입니다. 원본→processed(1056×576)→원본에는 축별 scale만 있으며 crop/letterbox offset은 없습니다. Patch padding은 image 공간 padding이 아닙니다. Native `box_2d`의 0–1000 yxyx 변환은 이 명시적 ZIP schema 출력에 적용하지 않았습니다.

`coordinates_original.png`는 원본 크기의 좌표 overlay이고 `object_crops_16.png`는 16개 대상별 확대입니다. Green은 matched GT, orange는 unmatched GT, cyan은 실제 prediction입니다. GT class나 Box를 바꾸지 않았습니다. Left truck은 best geometry IoU가 threshold 이상이나 car로 출력하여 탈락했습니다. 원본 GT Box는 위쪽 적재물도 포함하므로 Box 범위 자체의 Human Review도 필요합니다.

64개 pair의 IoU를 독립 rectangle 식으로 검산하고 가능한 assignment를 완전 탐색했습니다. package 결과와 동일합니다. 평가 코드 변경은 없으며 수정 전후 점수는 3/16, 0/4, Action=False로 동일합니다.

추가로 실제 새 run의 `image_position_ids`를 검산했습니다. Valid patch 2376개, padding patch 144개(-1,-1), patch size16에서 processed 576×1056을 복원했으며 기록된 resolution과 같습니다. Image soft tokens는 264개입니다. `audit/processor_coordinate_verification.json`에 저장했습니다.
