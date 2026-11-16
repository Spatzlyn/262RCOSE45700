# 백엔드 TODO (2026-11-16 갱신)

## 완료 (코드·테스트·배포)

| 영역 | 엔드포인트 / 모듈 |
|---|---|
| 조회 | `GET /api/health`, `/api/versions`, `/api/items`, `/api/items/{id}`, `/api/runs`, `/api/runs/{id}`, `/api/runs/{id}/items`, `/api/runs/{id}/items/{item}`, `/api/runs/{id}/report[?base=]`, `/api/runs/{id}/report/conditions?key=`, `/api/compare?base=&target=`, `/api/runs/{id}/export?format=json\|csv`, `/api/images/{id}[?size=thumb]` |
| 추론 | `POST /api/runs`, `GET /api/runs/{id}/progress`, `POST /api/runs/{id}/cancel`, `GET /api/jobs/next`, `POST /api/jobs/{run}/{item}/result`, GPU 워커(`worker/worker.py`, systemd) |
| 정답 품질·분할 | `GET /api/quality`(L1·L2·L3), `GET /api/datasets`, `GET /api/datasets/{v}/leak-check`, `POST /api/datasets/{v}/freeze` |
| 사람 검수 입력 | `POST /api/runs/{id}/statement-reviews`(V13·V14), `tools/import_references.py`(정답·2인 기록·진술 검수·Split) |
| 통계 | Wilson, Source Group 단위 bootstrap, paired bootstrap 차이 구간과 `improved`/`not_confirmed` |
| 운영 | Docker(부팅 시 자동 시작), 쓰기·워커 API 키 인증, store를 `/data/backend-store`로 분리 |

## 남은 일 (다른 파트 입력이 필요)

| 할 일 | 필요한 것 | 누구 |
|---|---|---|
| 정답 기반 실제 점수 (V3–V12, A1, A2) | Reviewed 정답 파일 | 데이터 (태문님·유경님) |
| L1·L2 | 2인 합의 전 기록 | 데이터 |
| V13·V14 | 사람 진술 검수 결과 | 데이터 / 검수자 |
| bootstrap 구간 실제 산출 | 문항별 `source_group_id` | 데이터 |
| 누수 검사·Test freeze 실행 | Split 배정 파일 | 데이터 + PM |
| Ci 대응 일관성 규칙 확정 | 조건 Code → 필요한 정답 판정 대응표 | 데이터 |
| 워커를 원본 추론 코드로 교체·대조 | `infer.py`, `common.py` | 모델 (경흠님) |
| Tuned(QLoRA) 실행과 Base 비교 | adapter 가중치 + 로딩 방식 | 모델 |
| 화면 연결 | 서버 주소, `examples/` | 프론트 (연오님) |

## 백엔드 단독으로 남은 개선 (선택)

- [ ] 워커 Docker화 (nvidia-container-toolkit)
- [ ] SQLite 전환 (Run·요청 수가 많아지면)
- [ ] 결과 변동(재추론 간) 자동 비교 리포트
