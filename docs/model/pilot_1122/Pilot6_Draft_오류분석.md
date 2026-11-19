# Pilot 6장 Draft 대조 기반 오류 분석 검토초안

담당 하경흠 · AI Model / Algorithm · 갱신일 2026-11-19 KST

## 현재 상태

백엔드 공개 Draft 대조표와 보존된 6개 parsed_output.json을 비교했습니다. 24개 행의 예측 상태·reason 및 match 산술이 원 예측과 일치합니다. Draft와 예측이 다른 관계는 8개이며, 이는 불일치 기록 수입니다. 검수된 모델 오류 수나 정확도는 아닙니다. Reviewed 결과 및 객체·영역·대응 정답의 검수는 아직 확인되지 않았습니다.

기존 출력은 A 22개, P 2개, U 0개이고 JSON/Schema는 6장 모두 통과했습니다. 형식 통과는 정답 판정이 아닙니다. GT.csv 원본이나 사적 이미지, C 정답 geometry를 이번 작업에서 읽지 않았습니다. 아래 GT 값과 ID는 사용자 지정 공개 Draft CSV에서만 가져왔습니다. Notion 현장 사진은 접근 권한이 없어 확인하지 못했습니다.

## 확인할 자료와 버전

- [Draft 대조표 고정 버전](https://github.com/Spatzlyn/262RCOSE45700/blob/5027937024befa61189428e25a15cba86cce4b81/backend/examples/pilot6_draft_gt/comparison.csv)
- [최종 명세 고정 버전](https://github.com/Spatzlyn/262RCOSE45700/blob/42a16024033db9acd79931f3b142d3a246cb2bac/docs/benchmark/Kakao_Road_VLM_Benchmark_Spec_Final.pdf), §2.4–2.5와 App. B.1–B.3, PDF 6쪽 및 17–19쪽
- [채점 로직 수정 36766ee](https://github.com/Spatzlyn/262RCOSE45700/commit/36766eed9415a93037ba48412556493177f68041)
- [보존된 원 예측](https://github.com/Spatzlyn/262RCOSE45700/tree/e5fc3d3e5b5d39c7c987ff037c5aa8d6b24df499/docs/model/pilot_1115/backend_handoff)
- [실제 사용 코드와 Prompt](https://github.com/Spatzlyn/262RCOSE45700/tree/d6553eae923d77c052f994f4fa75b3f87a82bb8c/ai_model/inference)

원 run은 pilot_001_smoke_01부터 pilot_006_smoke_01이며, 대조표의 외부 Run ID는 RUN-PILOT6-BASE-001입니다. 새 추론은 없습니다. 고정 Base와 원 Prompt는 유지합니다.

## 백엔드 결과 수령 시 확인

| 항목 | 확인 내용과 남은 일 |
|---|---|
| Draft 출처 | backend 5027937, 공개 24행, 전부 gt_status=Draft |
| 평가기 | 36766ee의 backend-scorer-0.2.1 변경 확인. 이 CSV가 그 평가기의 공식 채점 결과라는 실행 기록은 미확인 |
| Reviewed 여부 | 대기. 관계별 검수자·버전·확정일 요청 |
| 평가 범위 | relations_only이면 Reviewed의 확정 관계만 비교. 속성·근거·대응 평가나 최종 Test 동결에 사용하지 않음 |
| 영상 대응 | 샘플 ID·원 예측 상태·reason은 확인. CSV 이미지명과 실행 요약의 파일명 일치 확인 |
| 출입구·접지 검토 | 002 현장 사진과 004 U 사유는 데이터 담당자 확인 필요 |
| 공식 점수 | 산출하지 않음. Draft 비교의 match를 공식 V5나 F1로 전환하지 않음 |

## 샘플별 비교표

순서는 R1 / R2 / R3 / R4입니다. 일치하는 행도 관계 상태만 같다는 뜻이며 객체·근거·대응의 정확성을 보장하지 않습니다.

| 샘플 | 보존된 예측 | 공개 Draft GT | 상태 차이 | 검수 상태 |
|---|---|---|---|---|
| pilot_001 | P / A / A / A | P / A / A / A | 상태 차이 없음 | Draft / 검토 대기 |
| pilot_002 | A / A / A / A | P / P / P / P | R1, R2, R3, R4 | Draft / 검토 대기 |
| pilot_003 | A / A / A / A | A / A / A / A | 상태 차이 없음 | Draft / 검토 대기 |
| pilot_004 | A / A / A / A | P / A / P / U | R1, R3, R4 | Draft / 검토 대기 |
| pilot_005 | A / A / A / A | P / A / A / A | R1 | Draft / 검토 대기 |
| pilot_006 | P / A / A / A | P / A / A / A | 상태 차이 없음 | Draft / 검토 대기 |

## 오류 분석표

실패 단계 후보는 형식, 객체·영역 인식, 근거 연결, 관계 판정, 대응 적용으로 구분합니다. 이번 표에서는 원인 확정 없이 검토 후보만 적습니다. 단순 ID 개수 차이는 객체 누락의 확정 근거가 아닙니다.

| 샘플 / 관계 | Draft와 예측 차이 | 실패 단계 후보 | 확인 근거와 관측 | 다음 검토 | 상태 |
|---|---|---|---|---|---|
| pilot_002 / R1 | Draft P, 예측 A | 객체·영역 인식 또는 관계 판정, 미확정 | `track1.relations.R1`; CSV 근거 ID 16457. 차량 pred_obj_1·pred_obj_2는 선언했지만 접지와 C 중첩이 없다고 설명합니다. 어느 예측 객체가 GT 근거와 대응하는지 확인되지 않았습니다. | 앞바퀴 가시성과 C 경계를 데이터 담당자와 검토. Box만으로 접지를 대체하지 않음. | 미확정 |
| pilot_002 / R2 | Draft P, 예측 A | 객체·영역 인식 또는 관계 판정, 미확정 | `track1.relations.R2`; CSV 근거 ID 16457. 관계 근거가 비어 있고 entrance_candidate_id=null, regions=[]입니다. 출입구가 관측되지 않았다는 이유를 제시합니다. | 확정 출입구인지 후보인지, 보이는 Actor와 출입구 경계를 검토. 후보를 확정 출입구로 강제하지 않음. | 미확정 |
| pilot_002 / R3 | Draft P, 예측 A | 객체·영역 인식 또는 관계 판정, 미확정 | `track1.relations.R3`; CSV 근거 ID 16458. occluder_ids=[], occluded_region_id=null입니다. Draft 근거 16458의 예측 대응은 미확정입니다. | 진행 판단에 필요한 가려진 영역과 가림 객체의 존재·근거 연결을 검토. | 미확정 |
| pilot_002 / R4 | Draft P, 예측 A | 관계 판정 또는 객체·영역 인식, 미확정 | `track1.relations.R4`; CSV 근거 ID 16457|16458. restricting_object_ids=[]입니다. 제한 배치가 관측되지 않았다고 설명합니다. | 직접 C 중첩과 별도로 통행 공간 제한 여부를 검토. 실제 통과 불가능과 혼동하지 않음. | 미확정 |
| pilot_004 / R1 | Draft P, 예측 A | 객체·영역 인식 또는 관계 판정, 미확정 | `track1.relations.R1`; CSV 근거 ID 333737|333738|333741. pedestrian obj_1 하나를 선언했지만 C 중첩은 없다고 설명합니다. GT의 세 객체와 동일성은 미확정입니다. | 접지 및 C 판단과 누락 객체 가능성을 분리 검토. GT ID 문자열로 객체를 강제 대응하지 않음. | 미확정 |
| pilot_004 / R3 | Draft P, 예측 A | 객체·영역 인식 또는 관계 판정, 미확정 | `track1.relations.R3`; CSV 근거 ID 333741. regions=[]이고 occluder_ids=[]입니다. Draft 근거 333741의 대응은 미확정입니다. | 가림 대상과 가려진 영역의 관측 근거, 객체 선언 누락 여부를 검토. | 미확정 |
| pilot_004 / R4 | Draft U, 예측 A | 관계 판정, 미확정 | `track1.relations.R4`; CSV 근거 ID 미기재. unknowns=[]이며 제한 배치가 없다는 A를 출력했습니다. Draft U의 구체적 불확실성 사유는 CSV에 없습니다. | 데이터 담당자에게 U 판단 사유 요청. A와 U의 구분을 검토하되 U가 정답이라고 확정하지 않음. | 미확정 |
| pilot_005 / R1 | Draft P, 예측 A | 객체·영역 인식 또는 관계 판정, 미확정 | `track1.relations.R1`; CSV 근거 ID 259504. car obj_1·obj_2를 선언했지만 명확한 점유 객체가 없다고 설명합니다. Draft 근거 259504와 동일성은 미확정입니다. | GT 대상의 클래스·접지와 C 경계, 예측 객체 대응을 검토. 객체 누락과 관계 오판을 분리. | 미확정 |

### 별도로 확인할 대응 기준 차이

원 Prompt는 R1=P인 Actor에 양보·보류를, 고정 Obstacle에 보류를 필수로 요구합니다. 최종 명세는 Obstacle 또는 Roadside Vehicle만 점유하면 같은 대상의 R4 통과 가능성 확인을 필수로 하고 보류는 허용으로 남깁니다. 차량은 여전히 actor입니다. 보행자 등 다른 Actor가 함께 점유하면 그 Actor의 양보·보류 요구도 남습니다.

이는 문서 간 확인된 규칙 차이입니다. 위 8개 관계 불일치의 원인이라고 단정하지 않습니다. 대응 문구 수정만으로 객체·영역 인식이 좋아진다고 주장하지 않습니다.

pilot_001과 pilot_006은 R1=P, R4=A를 출력했고 양보를 제시합니다. 해당 차량은 예측상 travel_space이며 실제 Roadside Vehicle 여부는 미확정입니다. 만약 검수에서 해당 점유 대상이 Roadside Vehicle 또는 Obstacle로 확정된다면, 같은 대상의 R4와 필요 대응도 함께 검토해야 합니다. Draft의 R4=A를 조용히 바꾸거나 원 예측을 고치지 않습니다. 002/004/005에서도 동일한 객체별 규칙 일관성 검토가 필요합니다.

## 결과 요약과 다음 작업

- Draft와 다른 관계는 002의 R1–R4, 004의 R1/R3/R4, 005의 R1입니다. 나머지 16행은 상태 문자열이 같습니다. 공식 점수는 계산하지 않았습니다.
- 관계 오판 후보와 대응 규칙 불일치를 별도로 관리합니다. 객체 정합·가림 근거·004의 U 사유를 검수한 뒤 오류 유형을 확정합니다.
- 후보 원인 유형은 C·접지/관계 판단과 가림·출입구 근거 처리의 두 가지 이내로 묶되, 두 조건에 부록 B를 동일하게 적용합니다. B에만 R1 접지 재확인 문장을 추가합니다.
- 공식 V5는 N/A입니다. 12개 관계·상태 칸과 검수 조건 충족을 확인하지 못했습니다.
- [다음 실험 계획](부록B_공통기준_AB_실험계획.md)과 [신규 Prompt 검토초안](A_부록B_공통_프롬프트.txt)을 팀에 검토 요청할 수 있습니다. 실행·Commit·Push는 하지 않았습니다.
