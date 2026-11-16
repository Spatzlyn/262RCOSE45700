# Base Pilot 6장 실험 결과 및 검증 보고

담당 하경흠 · AI Model / Algorithm · 작성일 2026년 11월 16일 KST

## 결론과 평가 범위

기존 6개 run의 필수 파일 13종을 확인했습니다. 원시 출력, 디코딩, 파싱 결과와 기록이 보존되어 있으며 기존 백엔드 전달 예측 6개는 원 예측과 바이트 단위로 같습니다. 이번에는 다운로드나 모델 추론을 반복하지 않았고 GT·reference·C geometry를 읽거나 정답 채점을 수행하지 않았습니다. 기존 구조 validator로 JSON/Schema만 CPU 재검증했습니다.

6개 모두 status=completed, JSON/Schema 통과, retry_count=0, format_repair=false, schema_errors=[]입니다. 형식 통과는 정답을 뜻하지 않습니다. Accuracy, F1, 공식 V3/V4/V5/V10과 신뢰구간은 산출하지 않았습니다.

실제 실행 시간은 2026-11-16T01:27:30.212531+09:00부터 2026-11-16T01:57:09.690270+09:00까지입니다. 계획상 11월 15일 작업과 실제 11월 16일 새벽 실행을 구분합니다.

## 모델과 고정 Base 설정

- 모델 google/gemma-4-E4B-it, revision 4ecc2ba63bcac23ba4a767fc87025b1450f84c9c.
- Base name nf4_prompt_v1_first, 4-bit NF4 double quant, BF16 compute.
- text/vision SDPA, audio eager, soft-token budget 280, batch=1.
- max_new_tokens=4096, seed=42, do_sample=false, enable_thinking=false.
- CPU offload=false, adapter_loaded=false. 6개 run의 설정·Prompt·Schema·스크립트 hash가 같습니다.
- 새 로컬 입구를 사용했습니다. historical_script_reproduced=false이며 원 infer.py의 완전 재현을 주장하지 않습니다.
- 실행 스크립트 SHA-256은 1437366263bec4ebc82cea42c543f0e290f220b8110c00d4c8d03f2f627e6fe8입니다. 현재 보존된 스크립트와 6개 config의 hash가 같습니다.

실제 기록 환경은 Python 3.11.18, Windows, torch 2.6.0+cu124, torchvision 0.21.0+cu124, transformers 5.23.0, bitsandbytes 0.50.2, accelerate 1.15.0, CUDA runtime 12.4입니다. GPU는 NVIDIA GeForce RTX 4070 Laptop GPU입니다. Base 안의 과거 torch 2.9.1+cu128 및 CUDA 12.8 메타데이터와 실제 최상위 packages 기록을 혼합하지 않습니다. 실제 Transformers 5.23.0도 과거 5.22.1과 다릅니다.

다운로드 기록은 고정 revision의 8개 파일 SHA-256 통과를 보존하고 있습니다. 이번에는 8개 파일의 존재와 크기를 확인했으며 16GB 전체 hash를 다시 계산하거나 모델을 다시 다운로드하지 않았습니다.

## 장면별 실행 결과

| Run ID | 기록된 생성 구간 초 | Token | 전체 run 초 | R1 | R2 | R3 | R4 | JSON/Schema |
|---|---:|---:|---:|---|---|---|---|---|
| pilot_001_smoke_01 | 277.13 | 1111 | 324.55 | P | A | A | A | 통과 |
| pilot_002_smoke_01 | 178.14 | 690 | 213.56 | A | A | A | A | 통과 |
| pilot_003_smoke_01 | 239.53 | 1001 | 278.65 | A | A | A | A | 통과 |
| pilot_004_smoke_01 | 154.98 | 608 | 185.99 | A | A | A | A | 통과 |
| pilot_005_smoke_01 | 168.01 | 653 | 198.34 | A | A | A | A | 통과 |
| pilot_006_smoke_01 | 207.96 | 885 | 238.92 | P | A | A | A | 통과 |

기록된 생성 구간 합계는 1225.75초, 약 20분 26초입니다. 출력은 총 4948 token입니다. run별 wall_seconds 합계는 1440.01초입니다. 각 run은 독립 로딩하므로 이를 모델을 한 번만 로딩한 batch 처리 시간으로 해석하지 않습니다.

generation_seconds는 현 입구에서 generate 시작 후 CUDA 동기화, 디코딩과 일부 파일 저장까지 포함하는 기록값입니다. 순수 GPU 커널 시간이나 모델 로딩 시간으로 부르지 않습니다. Token 수는 generated_ids.json 길이와 기록값이 같습니다. token ID를 모델로 다시 생성하지 않았습니다.

## 입력 식별과 입력 분리

| Item ID | 이미지 파일명 | 이미지 SHA-256 |
|---|---|---|
| pilot_001 | CK_A01_R01_erh_rainy_01021252_F.png | 25a9a92a4d6ce456426b031e11b7f7978b9c037c4966dc41ee165de5c1ea93cd |
| pilot_002 | CK_A09_R05_day_clear_01010324_F.png | 03654038896ea54648c2af6e37766671776955ebcc0ff590fff1a721ca2c4585 |
| pilot_003 | CK_B02_R05_afterschool_clear_01065701_F.png | 1db084b52ad114dfa0f2b947603d333923b8a82f5cc3edd216a808ee5d563e60 |
| pilot_004 | CK_B02_R05_lunch_clear_01012234_F.png | d7c5a93a0709009c4484c9f14814d50df8d23faa954e90af3629e9c264a6e918 |
| pilot_005 | CV_A01_R03_lunch_rainy_01114394_F.png | 32898195531d822d4e1c3df1ed1816e36e0319bb9ffa007b63fe959e3aaf602f |
| pilot_006 | CV_A06_R04_mrh_clear_01045907_F.png | 521758954174ef218469f0fe97d5ebb7128fa856ff8350ce7d3727650d89e858 |

저장된 messages에는 원본 이미지 한 장과 고정 과제 설명이 있습니다. 모델의 텍스트 ID는 pilot_001부터 pilot_006이며 원본 파일명은 렌더링 Prompt에 들어가지 않았습니다. 실제 PNG hash, config와 input_audit hash가 모두 일치합니다. system_prompt 내용과 hash, schema 내용도 확인했습니다.

각 input_audit는 labels_read=false, reference_files_read=false, C_geometry_read=false를 기록합니다. 보존된 새 입구는 GT 파일을 열지 않고 평가용 C geometry를 입력하지 않습니다. C의 일반 개념 설명은 정답 polygon과 구분합니다. 이는 파일·코드·입력 기록의 확인이며 과거 OS 수준 파일 접근 trace를 확보한 것은 아닙니다. 이번 검증에서도 비공개 GT를 열지 않았습니다.

## 메모리 기록과 한계

6개 loaded_model.json은 allocated_bytes=9,325,277,696, reserved_bytes=9,416,212,480을 동일하게 기록합니다. 6개 status.json도 peak allocated=10,156,276,736, peak reserved=10,326,376,448로 같습니다. GiB로는 각각 약 8.685, 8.770, 9.459, 9.617입니다.

이 수치는 명목상 약 8GB인 GPU의 물리 VRAM보다 큽니다. 원값을 바꾸지 않았고, 이를 독립적인 전용 VRAM 사용량 실측이나 8GB 이내 실행 증거로 제시하지 않습니다. 동일한 여섯 기록의 원인도 확인되지 않았습니다. Windows의 메모리 처리나 기록 방법의 영향 등은 추가 확인 대상이며 여기서 원인을 단정하지 않습니다. 과거 NVML/전용·공유 메모리 trace가 없고, 이번에는 재추론을 하지 않았습니다.

config는 cuda:0 map을 선언하지만 loaded_model.device_map은 null입니다. 코드에는 CUDA 이외 파라미터를 거부하는 검사가 있습니다. 이 차이를 보존하며 null을 직렬화된 실제 per-parameter device 배치 증거로 해석하지 않습니다. 생성 완료 기록과 물리 메모리 측정의 신뢰 범위를 구분합니다.

## 예측 분포와 채점 대기

24개 관계 출력은 A=22, P=2, U=0입니다. P는 pilot_001과 pilot_006의 R1에만 있습니다. R2/R3/R4는 모두 A이며 예측 Region은 6개 run 모두 빈 배열입니다. 이는 출력 분포 관측이며 위험을 놓쳤다거나 올바르게 판단했다는 결론이 아닙니다. 아직 정답 채점 결과가 없습니다.

백엔드의 검수된 reference 채점 후에만 장면별 GT 차이, 형식·객체/영역·근거·관계·대응 단계 오류를 분석합니다. 모호한 라벨은 데이터 파트와 먼저 검토합니다. 독립 검수와 12개 관계·상태 조합 등 공식 조건이 충족되지 않으면 공식 V5는 N/A입니다.

## 보존과 확인 방법

원 실험은 작업 디렉터리의 pilot-1115/runs/pilot_001_smoke_01부터 pilot_006_smoke_01에 보존되어 있습니다. 기존 backend_handoff도 그대로입니다. 이번 검사 전후 보호 파일 84개의 SHA-256과 파일 존재를 확인했습니다. 새 검토 자료만 별도 폴더에 작성했습니다.

- [기계 판독 검증 결과](verification.json)
- [실행 요약 CSV](run_summary.csv)
- [비공개 절대경로를 제외한 파생 실행 기록](run_metadata.json)
- [전달 파일 hash 목록](handoff_manifest.json)
- [백엔드 전달 안내](백엔드_채점_전달안내.md)

기존 팀 제출 branch는 [work/model-1115](https://github.com/Spatzlyn/262RCOSE45700/tree/work/model-1115), 기존 커밋은 [7205ee4](https://github.com/Spatzlyn/262RCOSE45700/commit/7205ee4f9518dc75d30a05389e5e6977000a987a)입니다. 이번 Pilot 자료는 아직 Commit/Push하지 않았으며 기존 커밋이 새 결과를 포함한다고 표현하지 않습니다.
