# 데이터 · 한태문

v1.1 부분 재설계 기준의 검토용 데이터. 사람 합의 전 정답은 Draft, 추가 3장의 두 사람 독립 라벨은 미작성 상태. 원래 데이터 작업은 [이전 Pilot 1115 자료](../docs/data/pilot_1115/) 및 [원본 작업 브랜치](https://github.com/Spatzlyn/262RCOSE45700/tree/work/data-1115/docs/data/pilot_1115) 참조.

| 파일 | 용도 |
|---|---|
| [pilot6_v11_draft.jsonl](pilot6_v11_draft.jsonl) | 기존 6장 D·Box 유지, 신규 7개 관찰 필드, Draft 참조 정답 |
| [pilot_draft.json](pilot_draft.json) | 초기 v1.1 초안 생성 자료 |
| [candidate_blank_all6.jsonl](candidate_blank_all6.jsonl) | 추가 후보 6장 빈 양식 |
| [independent_blind_3.jsonl](independent_blind_3.jsonl) | 독립 검수할 후보 3장 빈 양식 |
| [blind_labeling_template.html](blind_labeling_template.html) | 독립 라벨링 화면 생성용 템플릿 |
| [Source Group split](../backend/store/splits/v11-pilot-dev.json) | 7장 dev, 5장 미배정. Test freeze 없음 |
| [이전 manifest](../docs/data/pilot_1115/pilot_manifest.csv) | 12개 이미지 파일명·해시·그룹 |

### 독립 라벨링 화면 생성

프로젝트 루트에서 실행:

```bash
python -m backend.tools.build_blind_viewer --images /data/aihub_71784/images --forms data_v11
```

기존 AI Hub 데이터의 `K`/`V` 폴더 또는 후보 이미지를 모아둔 폴더를 `--images`로 지정. 생성되는 `Pilot3_v11_Blind_Labeling.html`을 브라우저에서 열어 각자 입력 후 JSONL로 저장. 독립 답안 및 원본 사진 내장 HTML은 공개 저장소에 커밋하지 않음. 두 사람 답안이 모두 완료된 후 합의본 생성. 처리 절차는 [인수인계](../README_v11_HANDOFF.md) 참조.
