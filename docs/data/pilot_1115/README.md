# 데이터 파트 산출물 (`work/data-1115`)

공통 Pilot 6장의 C와 관계 GT는 **1인 작성 Draft**입니다. 유경님과의 독립 라벨링·불일치 검토 후 합의 항목만 채점용으로 전달합니다.

이 문서는 v1.0 작업 이력입니다. 종합 브랜치의 현재 검토 기준은 [data_v11](../../../data_v11/)을 참고하세요. 원본 사진·라벨은 종합 브랜치로 복제하지 않았습니다.

| 파일 | 용도 |
|---|---|
| [Pilot/GT.csv](Pilot/GT.csv) | R1–R4 판정 및 근거 객체 ID |
| [Pilot/annotations_draft/](Pilot/annotations_draft/) | Labelme 객체 Box·C 작업본 |
| [Pilot/images](https://github.com/Spatzlyn/262RCOSE45700/tree/work/data-1115/docs/data/pilot_1115/Pilot/images) · [Pilot/labels](https://github.com/Spatzlyn/262RCOSE45700/tree/work/data-1115/docs/data/pilot_1115/Pilot/labels) | 공통 6장 원본 이미지·JSON, 기존 저장 위치 |
| [02_candidates](https://github.com/Spatzlyn/262RCOSE45700/tree/work/data-1115/docs/data/pilot_1115/02_candidates) | 추가 후보 6장, 기존 저장 위치 |
| [PILOT_CANDIDATES_12.md](PILOT_CANDIDATES_12.md) | 후보 목록·유형별 부족 항목·Source Group |
| [DATASET_COMPARISON.md](DATASET_COMPARISON.md) | 국내 1개·해외 2개 비교 및 용도 |
| [ANNOTATION_GUIDELINE.md](ANNOTATION_GUIDELINE.md) | 이번 Pilot 작성 방법과 잠정 기준 |

Labelme가 설치된 환경에서 저장소의 이 폴더를 기준으로 실행합니다.

```powershell
python -m labelme .\Pilot\annotations_draft
```

남은 작업: 6장 독립 검수와 불일치 기록, 라벨링 시간 기록, 모델의 `pilot_001`–`pilot_006` 매핑, 검수 완료 항목 전달. 반복 검토한 Pilot은 Train/Dev로 관리하고 Test에서 제외합니다.
