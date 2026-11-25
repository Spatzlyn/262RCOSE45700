# 공통 Pilot 6장 합의 GT

공통 6장의 핵심 관계와 보조 항목 판정을 합의하여 정리했다.

| 자료 | 내용 |
|---|---|
| [공통 6장 합의 GT](pilot6_reviewed_gt.jsonl) | 백엔드에서 참조할 JSONL. 문항별 R1–R3 및 보조 4개 항목의 합의 판정과 근거를 담았다. |
| [라벨링 가이드](ANNOTATION_GUIDELINE.md) | 연결부 이용자, 전방·측방 가림, 병목과 기록 기준을 정리했다. |

## 공통 6장

| 문항 | R1 | R2 | R3 | 연결부 이용자 | 전방 가림 | 측방 가림 | 병목 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 001 | P | U | P | U | A | P | A |
| 002 | P | U | P | U | P | P | P |
| 003 | A | P | A | A | A | A | A |
| 004 | P | P | P | A | P | P | P |
| 005 | U | P | A | P | A | A | A |
| 006 | P | P | P | P | P | A | A |

005의 연결부 이용자는 차량 `259504`의 왼쪽 바퀴 접지점을 근거로 P에 합의했다. R1은 D 경계와의 관계가 불분명해 U로 유지했다. 001·002의 측방 가림은 근거 Region ID를 연결했다. 사진에서 범위를 측정할 수 없는 경우 좌표는 `null`로 기록했다.

백엔드 참조 정답 가져오기 검증은 6건 모두 통과했다. 채점 범위는 `reviewed_fields`의 핵심 관계와 보조 항목 판정이다. 객체 속성, 근거 매칭, 대응의 채점 범위는 별도 검수 후 설정한다.

[공통 6장 초안 대조 기록](https://github.com/Spatzlyn/262RCOSE45700/blob/fd36acf8c2ef186ad1338c7e768db1f8a12fe4be/docs/data/pilot_review/README.md) · [11/24 검토 기록](https://github.com/Spatzlyn/262RCOSE45700/blob/9afc3e87d095184b43ff588181a87db82c19f4d1/docs/data/pilot_review/pm_1124/README.md)
