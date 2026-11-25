# T2 · Track 2 영상 화면 (11/25, 임시 구조)

`f3-f5/app.html` 상단 **T2 영상** 탭. 서버가 꺼져 있어도 예시 파일로 볼 수 있음 (`index.html`에서도 동작).

| 기능 | 내용 |
|---|---|
| 영상 재생 | ▶/⏸(스페이스), 1프레임 이동(← → 또는 , .), 0.25·0.5·1x, **판단 시점에서 멈춤** |
| 판단 시점 선택 | 위쪽 영상별 ◆ 버튼 또는 타임라인 ◆. 같은 영상의 여러 판단 시점을 한 타임라인에 표시 |
| 타임라인 | 파란 구간 = 모델 입력(판단 시점까지), 빗금 = 입력 아님, 눈금 = 입력 프레임, 초록 점 = 라벨 프레임, 빨간 선 = 최초 충돌 |
| Box 비교 | 판단 시점 프레임에서만: 후보 번호(흰색), 정답(초록 실선), 예측 Box(보라 점선), 예측이 고른 번호(보라 "선택"). 라벨 프레임에서는 라벨 Box |
| 채점 결과 | 선택 맞음/틀림, Box IoU·기준·통과 — **백엔드 값 그대로**. 정답 검수 전·정답 없음은 "채점 제외", 결과 없으면 "결과 대기" |
| 시점 복사 | `{clip_id, frame, time_s, fps}`를 복사 (판단 시점 기록용) |

## 데이터 읽는 순서

1. 백엔드 API (임시 경로, 혜승님 확정 시 `T2API`만 수정)
   - `GET /api/track2/runs`, `/api/track2/runs/{run}/report`, `/items`, `/items/{item}`
2. **예시 응답·영상 열기**: JSON 여러 개를 한 번에 선택. 내용으로 구분 — `runs[]` / `metrics`(리포트) / `items[]`(목록) / `item_id`(문항 상세). MP4는 파일 이름이 `clip_id`와 같으면 그 영상에 붙음
3. **임시 예시로 보기**: 가상 값 5문항 (정상·선택 오답·형식 오류·검수 전·결과 대기). 같은 내용이 `f3-f5/track2_mock/`에 JSON으로 있음 → 혜승님 예시 오면 삭제

API의 `video.url`은 한 번 통째로 받아 blob으로 재생 (서버가 Range를 안 줘도 프레임 이동 가능).

## 화면이 쓰는 값 (`t2Item()`이 변환)

| 값 | 읽는 필드 (앞에서부터 있는 것) |
|---|---|
| 문항·영상 | `item_id`, `clip_id`, `video.{url,fps,n_frames,width,height}` |
| 판단 시점·충돌 | `decision.{frame,time_s}`, `first_collision.{frame,time_s}` |
| 입력 프레임 | `input_frames_s` 또는 `input_record.frame_times` (`run_track2.py`의 input_record.json) |
| 후보 번호 | `candidates[].{candidate_id, bbox_xyxy}` |
| 정답 | `reference.{annotation_status, reference_version, target_candidate_id, target_bbox_xyxy}` |
| 예측 | `prediction.select.{status, target_id, raw_text, format_errors}`, `prediction.box.{status, bbox_xyxy, raw_text, format_errors}` |
| 채점 | `scoring.select.{status, correct, reason}`, `scoring.box.{status, iou, threshold, pass, reason}`, `scoring.excluded_reason`, (선택) `scoring.consistency` |
| 라벨 프레임 | `frame_labels[].{frame, boxes[].{bbox_xyxy, is_target}}` |
| 리포트 | `metrics.<key>.{status, value, numerator, n, ci95, reason}` — 모르는 key도 이름 그대로 표시 |

Box는 원본 해상도 픽셀 `[x1,y1,x2,y2]` (`run_track2.py`와 같음). 0~1 값이면 정규화 좌표로 보고 변환.

**혜승님 예시가 오면**: 필드 이름이 다르면 `template.html`의 `t2Item()`·`T2MET`·`T2API`만 고치고 `python3 prep.py --html-only`.
