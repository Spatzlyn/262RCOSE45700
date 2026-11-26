# T2 · Track 2 영상 화면

`f3-f5/app.html` 상단 **T2 영상** 탭. 기준은 [명세서 App. D.1](../docs/benchmark/Kakao_Road_VLM_Benchmark_Spec_Final.pdf), 응답 구조는 백엔드 `/api/track2/*` ([`backend/app/track2_api.py`](../backend/app/track2_api.py), 예시 [`backend/examples/track2/`](../backend/examples/track2/)).

| 기능 | 내용 |
|---|---|
| 영상 재생 | ▶/⏸(스페이스), 1프레임 이동(← → 또는 , .), 0.25·0.5·1x, **판단 시점에서 멈춤**. 영상은 `video_url` 직접 재생(Range), 구간 이동이 안 되면 한 번 통째로 받아 재생 |
| 판단 시점 선택 | 영상별 ◆ 버튼(시각 · τ · 결과) 또는 타임라인 ◆. 같은 영상의 판단 시점을 한 타임라인에 |
| 타임라인 | 파란 구간 = 모델 입력(t까지), 노란 막대 = 예측 기간 H, 빨간 선 = 최초 충돌 tc |
| Box 비교 | 판단 시점 프레임에서: 후보 번호(흰색), 정답·라벨 초안(초록), 예측 Box(보라 점선), 예측이 고른 번호(보라 "선택"). **모델 입력 프레임** 버튼 = `numbered_frame_url` 이미지 |
| 영상이 없을 때 | `frame_url`(판단 시점 프레임)을 배경으로 Box만 비교 |
| 채점 결과 | 선택 맞음/틀림, IoU·Acc.5, 선택 번호 Box ↔ 예측 Box IoU — **백엔드 값 그대로**. 제외 문항은 `excluded_reason` 문구로 |
| 리포트 | T2-1 TargetAcc, T2-2 mIoU·Acc.5, T2-3 사고 여부, T2-4 Lead Time, 기준선(가장 아래·가장 큰 Box·무작위), 형식 통과, 채점 제외 수, τ 구간별 표. `official=false` Run은 "공식 결과 아님" |
| 시점 복사 | `{clip_id, frame_index, time_s, fps}` 복사 (판단 시점 기록용) |

## 읽는 순서
1. API: `GET /api/track2/runs` → `/runs/{run}/report` + `/runs/{run}/items` + `/items`(입력: 후보·fps) → 문항 고르면 `/runs/{run}/items/{item}`
2. 서버가 꺼져 있으면 **예시 응답·영상 열기**로 `backend/examples/track2/*.json` 7개를 한 번에 선택 (MP4는 파일 이름 = `clip_id`)

## 화면이 쓰는 값 (`template.html`의 `t2Item()`)
| 값 | 필드 |
|---|---|
| 판단 시점 | `decision_time_s`, `input.decision_frame_index`(0부터), `input.label_frame`(AI Hub 번호) |
| 사건 | `scoring.gt.{label, tau_s, bin, horizon_s, eligible, excluded_reason}`, `reference.{event_time_s, event_time_status, target_visible}` |
| 정답 | `reference.{target_candidate_ids, target_box_xyxy_px, annotation_status, reference_version}` |
| 예측·채점 | `scoring.selection.{status, target_id, correct, errors}`, `scoring.localization.{status, bbox_xyxy_px, iou, acc50}`, `scoring.selection_box_agree_iou`, `prediction_raw.{select,box}.output_text` |
| 영상 | `video_url`, `frame_url`, `numbered_frame_url`, `input.{fps, n_frames}`, `width`, `height`, `candidates[].bbox_xyxy_px` |

현재 실제 Run `t2_pilot28_gemma_base`는 GT가 Draft(충돌 시점 미검수)라 28건 모두 채점 제외 → 공식 점수 N/A. 화면에서는 라벨 초안과 예측을 나란히 보기만 함.
