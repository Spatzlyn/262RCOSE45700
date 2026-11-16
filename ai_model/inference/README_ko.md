# Kakao AI 모델 Pilot 추론 코드

담당 하경흠 · 2026년 11월 16일

## 목적과 출처

Pilot 6장 평가에 실제 사용한 새 로컬 추론 입구와 필요한 설정을 공유합니다. `source/run_gemma_pilot_smoke.py`는 원본 그대로이며 SHA-256은 `1437366263bec4ebc82cea42c543f0e290f220b8110c00d4c8d03f2f627e6fe8`입니다. 완료한 6개 run의 config.json에 기록된 hash와 같습니다.

이 코드는 공개되지 않은 과거 `infer.py`가 아닙니다. 과거 Linux 실행 환경을 완전히 재현했다고 주장하지 않습니다. 패키징 과정에서 모델을 재실행하거나 기존 예측을 수정하지 않았습니다.

`run_inference.py`는 경로만 연결하는 새 실행 래퍼입니다. 원본 스크립트 바이트나 Base 인자를 변경하지 않고 workspace, runtime 입력, model 디렉터리 위치만 지정합니다. 이 래퍼 자체로 새 GPU 추론을 검증한 것은 아니며, 이번 검사는 패키지 hash와 CPU 입력 분리 테스트입니다. 새 실행 시 원본·래퍼 hash를 별도 기록합니다.

## 포함 파일

- `source/run_gemma_pilot_smoke.py` 실제 사용한 입구 원본.
- `run_inference.py` 경로 지정 및 기존 결과 덮어쓰기 방지.
- `verify_model.py` 이미 확보한 모델의 SHA-256 검사. 다운로드하지 않음.
- `runtime_inputs/config.json` 고정 Base 설정. 내부 torch_version·과거 infer/common hash 등은 역사적 메타데이터이며 실제 환경은 아래 requirements와 각 Run 기록을 확인.
- `runtime_inputs/modified_system_full.txt`, `baseline_messages.json` 고정 System Prompt와 과제 템플릿. Schema가 이미 포함되어 있으므로 중복 삽입하지 않음.
- `runtime_inputs/prediction.schema.json`, `validate.py` 예측 구조·좌표·ID 참조 검사. validate.py는 필요한 validate_prediction 함수만 호출하며 원 샘플 패키지 전체 검사 CLI로 사용하지 않음.
- `runtime_inputs/model_file_hashes.json` 모델 파일명·크기·hash만 포함하며 weights는 없음.
- `requirements.txt`, `provenance.json`, `package_manifest.json`, CPU 테스트와 `.gitignore`.

모델 weights, 실제 Pilot 이미지, labels/GT/reference, C geometry, 기존 예측, 토큰·인증정보는 포함하지 않습니다. baseline_messages의 기존 이미지 경로는 공개 과제 템플릿의 문자열일 뿐이며 이미지 파일은 없습니다. 실제 실행에는 --image로 지정한 이미지 한 장만 사용합니다.

## 고정 Base 설정

| 항목 | 값 |
|---|---|
| Base name | nf4_prompt_v1_first |
| 모델 | google/gemma-4-E4B-it |
| revision | 4ecc2ba63bcac23ba4a767fc87025b1450f84c9c |
| 양자화 | 4-bit NF4, double quant, BF16 compute |
| Attention | text/vision SDPA, audio eager |
| 이미지 | 1장, RGB, soft-token budget 280 |
| 생성 | max_new_tokens=4096, seed=42, do_sample=false, enable_thinking=false |
| 기타 | batch=1, CPU offload=false, adapter 미사용 |

래퍼에는 모델·양자화·생성 인자를 바꾸는 옵션이 없습니다. 다른 조건을 시험하려면 별도 실험과 승인이 필요합니다.

## 환경 준비

Python 3.11 이상을 사용합니다. 실제 6개 실행은 Windows, Python 3.11.18, torch 2.6.0+cu124, torchvision 0.21.0+cu124, transformers 5.23.0, bitsandbytes 0.50.2, accelerate 1.15.0, huggingface-hub 2.4.0으로 기록되어 있습니다. requirements.txt는 확인된 핵심 패키지 6종을 고정한 목록이며 모든 전이 의존성의 과거 lockfile은 아닙니다. Python·GPU·드라이버 차이가 결과에 영향을 줄 수 있습니다.

아래 명령은 새 환경을 준비하는 예시이며 패키지 검토 중 실행하지 않았습니다. 이미 성공한 6장이나 기존 환경을 다시 실행·변경할 필요는 없습니다.

```powershell
py -3.11 -m venv .venv-gemma
.\.venv-gemma\Scripts\python.exe -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
.\.venv-gemma\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-gemma\Scripts\python.exe -m pip check
```

GPU는 BF16과 NF4 지원이 필요합니다. RTX 4070 Laptop에서 완료한 실행 기록이 있으나 기존 CUDA allocator 수치가 명목상 물리 VRAM보다 커 원인 미확인 상태입니다. 따라서 전용 VRAM 8GB 이내 실행을 보장하는 자료로 사용하지 않습니다. OOM·호환성 실패가 나면 그대로 기록하며 자동 offload나 파라미터 축소를 하지 않습니다.

## 외부 작업 디렉터리

개인 데이터는 저장소 밖에 둡니다. 다음은 예시이며 실제 이미지나 weights를 이 저장소에 복사·커밋하지 않습니다.

```text
C:\vlm-work\
  models\gemma-4-E4B-it\4ecc2ba63bcac23ba4a767fc87025b1450f84c9c\
    model.safetensors
    config.json
    processor_config.json
    tokenizer.json
    tokenizer_config.json
    chat_template.jinja
    generation_config.json
    README.md
  pilot-1115\
    model_download_verification.json
    private\Pilot\images\
      input.png
    runs\
```

이 패키지는 다운로드하지 않습니다. 이미 검증된 고정 revision의 전체 스냅샷을 별도로 준비합니다. 기존 verification report가 있으면 보존합니다. 새 작업 디렉터리에 보고서가 없는 경우에만 다음 명령으로 이미 있는 8개 파일의 hash를 확인합니다. 약 16GB weights를 읽지만 모델을 로드하거나 추론하지는 않습니다.

```powershell
.\.venv-gemma\Scripts\python.exe verify_model.py --workspace C:\vlm-work --model-dir C:\vlm-work\models\gemma-4-E4B-it\4ecc2ba63bcac23ba4a767fc87025b1450f84c9c
```

보고서 경로와 --model-dir가 일치해야 합니다. 런처는 기존 검증 보고서의 revision·hash·현재 파일 크기를 확인하며 매 추론마다 16GB hash를 반복 계산하지 않습니다. 모델 파일을 교체했다면 별도 새 검증을 수행해야 합니다.

## 모델 없이 패키지 확인

다음 검사는 표준 라이브러리만 사용하며 GPU, weights, 이미지, GT 또는 네트워크가 필요하지 않습니다.

```powershell
.\.venv-gemma\Scripts\python.exe -B run_inference.py --check-only
.\.venv-gemma\Scripts\python.exe -B tests/test_package.py
```

패키지의 hash, 원 스크립트 보존, 원 과제에서 중성 item_id만 변경되는지, GT 필드 거부와 이미지 파일명이 텍스트에 들어가지 않는지 검사합니다. 이것은 모델 성능 검사가 아닙니다.

## 새 이미지 한 장 실행

아래는 향후 새 실행용 예시입니다. 완료된 pilot_001_smoke_01부터 pilot_006_smoke_01을 반복 실행하지 않습니다. 출력 폴더는 반드시 새 경로이며 기존 경로가 있으면 시작하지 않습니다. 재시도도 별도 Run ID를 사용합니다.

```powershell
.\.venv-gemma\Scripts\python.exe run_inference.py `
  --workspace C:\vlm-work `
  --model-dir C:\vlm-work\models\gemma-4-E4B-it\4ecc2ba63bcac23ba4a767fc87025b1450f84c9c `
  --image C:\vlm-work\pilot-1115\private\Pilot\images\input.png `
  --item-id pilot_007 `
  --out C:\vlm-work\pilot-1115\runs\pilot_007_new_01
```

해당 Python 명령은 위 의존성을 설치한 interpreter로 실행합니다. 원 입구의 안전 검사를 유지하므로 이미지 경로는 workspace/pilot-1115/private/Pilot/images 바로 아래 PNG여야 합니다. 진행 의도는 고정 과제의 follow_visible_road_forward이며 파일명의 날씨·시나리오 정보는 텍스트에 넣지 않습니다.

## 출력과 평가 범위

원시·디코딩 출력, generated_ids, parsed_output(파싱 성공 시), config, status, input_audit, messages, 전체 Prompt, Schema, loaded_model, output_validation을 저장합니다. 래퍼 사용 정보는 launcher_provenance.json에 추가합니다. 실패는 phase·예외·traceback으로 보존합니다. 누락 필드나 관계 상태를 Parser가 보정하지 않습니다.

모델 요청에는 이미지와 고정 과제·공통 규칙만 사용하며 labels, GT, 정답 ID, C polygon은 읽지 않습니다. C의 개념 설명은 정답 geometry와 다릅니다. 구조 검사 통과는 관계나 대응이 맞다는 의미가 아닙니다. 이 패키지는 GT 채점 기능을 제공하지 않으며 정확도/F1을 생성하지 않습니다. 검수된 reference와 후속 채점은 데이터·백엔드 담당자와 별도로 진행합니다.

## 출처

- [기존 Base Pilot 결과 commit e5fc3d3](https://github.com/Spatzlyn/262RCOSE45700/commit/e5fc3d3e5b5d39c7c987ff037c5aa8d6b24df499)
- [기존 dry-run 자료 고정 commit](https://github.com/Spatzlyn/262RCOSE45700/tree/ef1ed254d4bbcb15d66c0ec96a02861ef1e7c681/kakao_dryrun)
- [공식 고정 모델 revision](https://huggingface.co/google/gemma-4-E4B-it/commit/4ecc2ba63bcac23ba4a767fc87025b1450f84c9c)

provenance.json과 package_manifest.json은 원 스크립트·설정의 출처 및 파일별 hash를 기록합니다. manifest 자신은 자기참조 hash에서 제외합니다. 이 문서는 코드 공유를 위한 설명이며 새 6장 실험이나 원 역사적 환경의 완전 재현을 뜻하지 않습니다.
