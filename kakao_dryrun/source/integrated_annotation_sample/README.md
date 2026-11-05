# Integrated Annotation Sample · v0.2

방향별 원본 이미지 4장과 Annotation을 제공하는 Track 1 실행 예시입니다. 원본 객체 18개를 보존하고 누락 대상 17개를 AI Draft로 추가하여 현재 객체는 35개입니다. 모든 Label은 검수 전이며 Human Reviewed 표본은 0개입니다. 실제 모델 호출이나 성능 측정은 수행하지 않았습니다.

이번 버전은 객체 보완, 근거 역할, Region 출력, 필드별 검수 정보와 평가 진단을 서로 맞췄습니다. C 경계·출입구 연결·작은 원거리 대상 등은 검수 대기로 남아 있으며, 공식 V3/V4 점수는 산출하지 않습니다. 세부 기준은 [ANNOTATION_GUIDELINE.md](ANNOTATION_GUIDELINE.md), 변경 내역은 [CHANGELOG.md](CHANGELOG.md)를 참조하십시오.

## 바로 실행하기

Python 3.10 이상에서 ZIP을 풀고 이 README가 있는 폴더로 이동합니다.

```bash
python scripts/validate.py
python scripts/test_evaluation.py
python scripts/evaluate.py --prediction expected/prediction.example.json --allow-draft
python scripts/build_request.py --model YOUR_MODEL
```

`validate.py`는 구조·좌표·ID·역할 참조를 확인합니다. `test_evaluation.py`는 ID 변경, 잘못된 위치·역할, 미완료 Reference 등의 평가 동작을 검사합니다. `evaluate.py`의 `--allow-draft`는 시험 비교를 허용할 뿐 검수 상태를 바꾸지 않습니다. 출력 예시와 Reference의 일치는 실제 VLM 성능이 아닙니다. `build_request.py`는 이미지가 들어간 요청 파일을 만들며 이 명령만으로 외부 모델을 호출하지 않습니다.

모델 서버를 직접 지정해 실행할 때만 다음과 같이 호출합니다. 서버가 `messages`와 `image_url` 형식을 지원하는지 먼저 확인하십시오.

```bash
python scripts/build_request.py --model YOUR_MODEL --send --endpoint FULL_ENDPOINT_URL
python scripts/validate.py --prediction runs/prediction.json
python scripts/evaluate.py --prediction runs/prediction.json --allow-draft
```

인증이 필요한 서버에는 `API_KEY` 환경변수를 사용합니다. 서버 형식이 다르면 원본 이미지, `prompts/system.txt`, `schema/prediction.schema.json`을 해당 모델의 입력 함수에 맞게 전달합니다.

## 파일과 입력 범위

| 파일 | 용도 | 기본 F 모델 입력 |
|---|---|---|
| `images/view_F.png` | 전방 원본 이미지 | 포함 |
| `data/items.jsonl` | 문항·Intent·입력 조건 | 허용 Field만 포함 |
| `prompts/system.txt` | 공통 판정·출력 규칙 | 포함 |
| `schema/prediction.schema.json` | 출력 형식 | 포함 |
| `images/view_B.png`, `view_L.png`, `view_R.png` | 보조 방향 원본 | 제외 |
| `annotations/view_*.json` | View별 상세 Annotation | 제외 |
| `data/annotations.jsonl` | 같은 상세 Annotation의 JSONL | 제외 |
| `data/references.jsonl` | Relation·허용 근거 집합·Action 비교 기준 | 제외 |
| `expected/prediction.example.json` | 출력 구조와 시험 비교 예시 | 제외 |
| `source/source_*.json` | 제공된 Source JSON 보존 | 제외 |
| `data/source_mapping.json` | 원본 대응·해시 | 제외 |
| `sample.html` | Box·Region·검수 후보·JSON 시각화 | 제외 |

상세 Annotation과 모델 출력 예시는 다른 구조입니다. 상세 Annotation에는 평가 전용 C, Time of Day 등 분석 속성, 출처와 검수 상태가 들어갑니다. 모델 출력에는 관측 객체·출입구/가림 Region·Relation의 근거 역할이 들어가며 C의 정답 좌표와 분석 전용 Time of Day를 요구하지 않습니다. Reference Box가 그려진 이미지는 모델에 보내지 않습니다.

## 네 방향과 세 Track

| View | 원본 객체 | 추가 Draft | 현재 객체 | 용도 |
|---|---:|---:|---:|---|
| F | 10 | 6 | 16 | 기본 전방 Track 1 문항 |
| B | 4 | 4 | 8 | 후방 보조 Annotation |
| L | 2 | 1 | 3 | 좌측 보조 Annotation |
| R | 2 | 6 | 8 | 우측 보조 Annotation |
| 합계 | 18 | 17 | 35 | 하나의 Source Group |

F/B/L/R은 방향이며 시간 순서가 아닙니다. 촬영 경로와 Token이 같아 하나의 Source Group으로 묶었지만 정확한 시각과 동기화 오차는 확인되지 않았습니다. Token과 `info.date_created`를 촬영 Timestamp나 Frame Index로 해석하지 않습니다.

B/L/R의 R1–R4는 전방 Intent를 기준으로 판정하지 않고 `null`을 유지합니다. Track 2의 미래 사건과 Track 3의 Ego Motion에 필요한 Sequence·측정 근거가 없으므로 두 Track은 `missing_input`, 정답은 `null`입니다. 이는 미래 대상이 없거나 자차가 정지했다는 뜻이 아닙니다.

## F에서 달라진 근거

| Relation | 현재 Draft | 반영 내용 |
|---|---|---|
| R1 Occupancy | P | sedan 외에 좌측 소형 truck과 우측 SUV·box truck의 관측 바퀴 접지점을 추가했습니다. Box 하단 겹침 비율로 판정하지 않습니다. |
| R2 Entrance | U | scooter 옆 별도 사람을 추가했습니다. 출입구의 안/경계 여부와 C 연결은 미확정이므로 P로 바꾸지 않았습니다. |
| R3 Occlusion | P | Occluder와 `F_hidden_road_ahead`의 역할 연결을 유지했습니다. 숨은 영역의 정확한 Polygon은 관측할 수 없어 `null`입니다. |
| R4 Restriction | P | 명확한 차량 배치 근거를 유지했습니다. 왼쪽 가장자리 truck `F_742186`은 영향 구간 검수 전까지 `evidence_candidates`로 분리했습니다. C 비중첩을 제외 조건으로 사용하지 않았습니다. |

기존 C Polygon은 이전 버전과의 비교 기준으로 보존했습니다. 이를 도로 전체 폭이나 자차 차선의 확정 경계라고 해석하지 않습니다. 도로 구조를 기준으로 폭·깊이를 독립 검수한 뒤 모든 대상 관계를 다시 확인해야 합니다. 검수 전 상태를 숨기기 위해 Polygon을 임의로 바꾸거나 기존 P에 맞춰 경계를 조절하지 않습니다.

Traffic Direction과 Direction Match는 Unknown을 유지합니다. Sidewalk는 가까운 가시 구간과 전체 평가 범위를 구분하여 좌우 U를 유지합니다. 오른쪽 녹색 노면의 존재는 분석 속성에 P로 기록하고, 그 공간의 보행 전용 지정 여부는 U로 구분했습니다. Time of Day는 상세 Annotation에만 유지합니다.

F의 라바콘 의심 부분은 소형 truck의 후미등·차체와 구분되지 않아 새 Object 수에 포함하지 않았습니다. `review_candidates`에 위치와 불확실성을 남겼습니다. 적치물은 연속된 가시 군집 단위이고, 봉투 내부를 쓰레기라고 추정하지 않습니다.

## 객체·근거·평가의 차이

원본 Source 파일과 기존 객체 좌표는 보존했습니다. 새 객체는 가려진 전체 외형을 복원하지 않은 가시 범위 Box이며 별도 추가 ID와 출처를 가집니다. 객체에는 `semantic_role`, `placement`, `truncated`와 각 필드의 출처·근거·Draft 상태를 기록했습니다. `roadside`는 배치이며 정차 상태를 뜻하지 않습니다. 길가 차량도 Actor 점유 조건을 만족하면 현재 R1 Action 규칙을 적용합니다.

`speed_bump`는 Object로 보존하고 의미 역할을 `road_feature`로 구분했습니다. 이 Pilot에서는 R1의 Actor/Obstacle 점유 대상에 넣지 않습니다. 도로 시설물이라는 분류가 실제 주행에 영향이 없다는 의미는 아닙니다.

Object 목록의 완전성과 Relation의 충분한 근거는 구분합니다. R1은 명확한 P 근거 하나만으로 장면 P가 될 수 있으며, 허용된 충분 근거 집합을 여러 대안으로 기록합니다. 다른 객체의 U는 별도로 보존합니다. 객체를 추가했다고 전체 검출 정답이 완성된 것으로 선언하지 않습니다.

| 검사·진단 | 현재 처리 |
|---|---|
| Schema·참조 검증 | 타입·좌표·중복 ID·선언된 객체/Region과 역할 참조를 검사합니다. |
| Relation·Action 비교 | R1–R4 값, 필수 대안, Allowed/Forbidden Pair, `based_on`을 비교합니다. |
| Object 매칭 진단 | Class와 IoU로 일대일 대응을 찾아 ID 문자열 차이를 허용합니다. |
| Region·Evidence 진단 | 관측 가능한 기하와 역할을 대조합니다. 측정할 수 없는 Region은 미평가 사유를 남깁니다. |
| 공식 V3/V4 | Draft·불완전한 객체 범위·미확정 Region 때문에 `null`입니다. |

가려진 Region의 ID나 이름이 같다는 이유만으로 위치 매칭 성공으로 처리하지 않습니다. `null` 기하에서 계산할 수 없는 근거 평가는 보류합니다. 진단 결과는 `diagnostics.grounding.objects/regions`의 매칭 목록과 `diagnostics.evidence.R1`–`R4`의 `matched/mismatch/deferred` 등 상태로 확인합니다. `diagnostics.benchmark`에는 `eligible=false`, `V3=null`, `V4=null`과 차단 이유가 기록됩니다. 이 샘플 평가기는 공식 V3/V4 집계 활성화 기능을 제공하지 않습니다. 정식 평가 전환에는 Reference 검수와 함께 별도의 집계 구현·검증이 필요합니다. 한 Source Group의 시험 실행용이므로 Macro-F1, Confidence Interval, 모델 순위도 제공하지 않습니다.

## 정식 평가로 전환할 조건

독립 Annotator가 C 범위, 평가 대상 Class·영역, 가림·잘림 기준, 추가 객체와 접지 근거를 검수해야 합니다. 이어 출입구 경계·연결, R4 영향 구간, Region 매칭 기준과 허용 근거 집합, Action Rule을 확정합니다. 각 Label의 검수자·검수일·Guideline 버전을 기록한 뒤 검수한 항목만 Reviewed로 바꿉니다. 객체 Coverage와 필수 근거가 준비되지 않았다면 문서 전체 상태만 바꿔 공식 점수를 활성화해서는 안 됩니다.

이 Schema는 `integrated-sample-0.2`인 독립 예시이며 기존 저장소 평가기의 즉시 대체 Schema가 아닙니다. 공식 입력·출력 계약으로 채택할 때에는 본 패키지의 미해결 항목을 먼저 확정해야 합니다.

## 수정본 검증 기록

패키지 구조 검사와 평가 회귀 테스트 30개를 통과했습니다. 원본 이미지·Source JSON 바이트 보존, View JSON과 JSONL 일치, 모델 요청에 Reference ID·C 정답 좌표가 포함되지 않음을 확인했습니다. HTML의 내장 이미지·JSON 일치, JavaScript 문법, 네 방향 SVG 좌표 표시도 확인했습니다. 브라우저 실행 환경을 사용할 수 없어 실제 브라우저 레이아웃과 버튼 상호작용은 검증하지 못했습니다. 자세한 결과는 `runs/`의 검증 JSON에 있습니다.

HTML을 JSON에서 다시 생성하려면 `python scripts/render_sample.py --standalone ../Integrated_Annotation_Sample.html`을 실행합니다. ZIP 내부 `sample.html`과 이미지 내장 HTML이 함께 갱신됩니다.
