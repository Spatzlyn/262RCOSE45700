# 국내외 데이터셋 비교

| 항목 | AI Hub 71784 · 한국 | BDD100K · 미국 | KITTI · 독일 |
|---|---|---|---|
| 공식 자료·기관 | [생활도로 객체인식 자율주행 데이터](https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=71784) · AI Hub/NIA, LFIT | [BDD100K](https://arxiv.org/html/1805.04687v2) · UC Berkeley 연구팀 | [The KITTI Vision Benchmark Suite](https://www.cvlibs.net/datasets/kitti/) · KIT/TTIC |
| 입력 | 확보한 전방 PNG 1920×1080 | 전방 40초 영상·이미지 태스크용 추출 프레임 | 전방 이미지·[Raw 10 Hz 시퀀스](https://www.cvlibs.net/datasets/kitti/raw_data.php) |
| 선정 이유 | 한국 생활도로 대상 수집, Pilot 원본·라벨 확보 | 미국 도로와 다기상 장면 비교 | 무차선 도시 도로와 도로 영역 비교 |
| 재사용 라벨 | 로컬 JSON의 객체 ID·Box·분할 | [객체 Box·분할·Drivable Area](https://github.com/bdd100k/bdd100k/blob/master/doc/source/format.rst) | [Detection의 객체 Box](https://www.cvlibs.net/datasets/kitti/eval_object.php?obj_benchmark=3d), [Road의 도로 영역](https://www.cvlibs.net/datasets/kitti/eval_road.php) — 별도 태스크 |
| 추가 작업 | 기존 Box 검수 후 C·관계 근거 작성 | 목표 장면 선별·클래스/ID 변환, 기존 도로 영역을 참고해 C 작성 | 목표 장면 선별·클래스/ID 변환. Detection을 쓰면 C를, Road를 쓰면 필요한 객체 Box를 보완. 두 태스크 정합은 필수 아님 |
| Source Group | 원천 촬영 폴더 기준 | 영상 ID 기준; 동일 ride의 복수 클립도 확인 | Raw drive 기준; Road→Raw 매핑 제공 |
| 용도 제안 | **주 평가용** — 대상 환경과 일치하고 Pilot 준비됨 | **비교용** — 해외 장면에 같은 GT 기준 적용 | **비교용** — 무차선 도로에서도 관계 판단 비교 |

**공통 보완**: 비교한 원본 라벨에는 본 프로젝트의 C·R1–R4·Evidence·Action을 묶은 GT가 없습니다. 세 데이터 모두 관계·근거·대응 작성과 독립 검수가 필요합니다. 위 표는 작업 종류를 비교하며, 미측정 작업 시간을 ‘낮음/높음’으로 순위화하지 않습니다. 이번 Pilot의 Region 보류는 [작업 범위](ANNOTATION_GUIDELINE.md)에 따릅니다.

## 실제 장면 근거

| 자료·위치 | 확인한 장면 | 비교에서 확인할 점 |
|---|---|---|
| AI Hub `01021252`·`01010324`·`01114394` | 좁은 골목 혼재·근거리 차량 가림·개방형 주차 공간 | 한국 대상 장면 확보. 원래 Box만으로 관계 정답은 정해지지 않음 |
| BDD [Fig. 6, b2102d00-a8c09be1](https://arxiv.org/html/1805.04687v2/images/drivable_jpg/b2102d00-a8c09be1.jpg) | 야간 양측 길가 차량과 중앙의 주행가능영역 | 해외에도 길가 차량 장면이 있음. 이 mask가 본 프로젝트 C·R4 GT인 것은 아님 |
| BDD [Fig. 6, b20b69d2-bd242bf0](https://arxiv.org/html/1805.04687v2/images/drivable_jpg/b20b69d2-bd242bf0.jpg) | 좌측 보도 위 보행자, 우측 차량 공간, 곡선 도로 | 보도·차도 분리 비교에 활용. 무보도 혼재 사례로 세지 않음 |
| KITTI [Road 공식 예시의 UU·UM](https://www.cvlibs.net/datasets/kitti/images/header_road.jpg) | UU는 중앙선 없는 주택가 도로, UM은 노면 표시와 길가 차량이 있는 도로 | 무차선 도로도 제공됨. 차선 부재를 보도 부재로 간주하지 않음 |

해외 예시는 공식 공개 그림을 확인한 것이며 전체 데이터의 비율 조사가 아닙니다. 이 예시들만으로는 출입구–Actor 관계, 진행 판단 영역의 가림, 무보도 혼재가 모두 확인되지 않아 해당 유형의 비교용 샘플은 추가 선별이 필요합니다.

## 이용 조건

| 항목 | AI Hub | BDD100K | KITTI |
|---|---|---|---|
| 다운로드·학습 | 로컬 확보; 승인 목적·이용정책 준수 | 공식 배포; 연구·교육 등 허용 범위 준수 | 로그인 다운로드; 비상업적 이용 |
| 가공본 공개 | 제3자 제공·국외 반출 제한 적용 | 허용 범위 내 수정·배포, 고지문 유지 | 저작자 표시·비상업·동일조건변경허락 |
| 외부 API | 국외 반출 등 승인 조건 확인 필요 | 서비스의 보유·재이용 약관과 함께 확인 | 서비스 이용 방식과 비상업 등 조건 대조 |

근거: [AI Hub 정책](https://aihub.or.kr/intrcn/guid/usagepolicy.do) · [BDD100K 데이터 라이선스](https://github.com/bdd100k/bdd100k/blob/master/doc/source/license.rst) · [KITTI 라이선스](https://www.cvlibs.net/datasets/kitti/).
