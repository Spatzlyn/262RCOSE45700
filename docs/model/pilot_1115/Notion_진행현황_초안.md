## AI 모델 Pilot 6장 진행 현황

담당 하경흠

### 완료

고정 revision 4ecc2ba63bcac23ba4a767fc87025b1450f84c9c의 Gemma-4-E4B-it Base로 공통 Pilot 6장의 로컬 추론을 완료했습니다. NF4/BF16/SDPA, soft-token budget 280, max_new_tokens 4096, seed 42를 유지했으며 adapter와 명시적 CPU offload는 사용하지 않는 설정입니다. 새 로컬 입구이며 과거 infer.py의 완전 재현은 아닙니다.

6개 run 모두 JSON/Schema 통과, retry_count=0, format_repair=false입니다. 기존 출력의 CPU 형식 재검증과 전달 JSON의 원본 일치를 확인했으며 재추론이나 GT 채점은 하지 않았습니다. 기록된 생성 구간 합계는 1225.75초, 출력은 총 4,948 token입니다. 원시 출력·설정·입력 감사·상태 기록은 보존되어 있습니다.

### 채점 대기 및 한계

관계 출력 24개는 A 22개, P 2개입니다. 이는 분포 관측이며 정확도·F1 또는 오류율이 아닙니다. 6개 전체 예측과 Run 자료는 로컬 전달 준비가 끝났지만 아직 백엔드에 발송하거나 채점 결과를 받지 않았습니다.

CUDA allocator 로그가 명목상 8GB 물리 VRAM을 초과하므로 전용 VRAM 사용량이나 8GB 이내 실행 실측으로 해석하지 않습니다. 기록은 수정하지 않았으며 측정 범위와 원인은 추가 확인이 필요합니다. 실제 Transformers는 5.23.0으로 과거 환경과 다릅니다.

### 다음 작업

사용자 검토 후 허용 파일만 work/model-1115에 Commit·Push하고 최종 링크를 추가하겠습니다. 백엔드의 검수된 reference 채점을 받은 뒤 단계별 오류표를 작성하고 독립 Dev용 Prompt A/B 실험을 구체화하겠습니다. 현재 accuracy·F1·공식 V5는 보고하지 않습니다.

기존 branch [work/model-1115](https://github.com/Spatzlyn/262RCOSE45700/tree/work/model-1115)

기존 금요일 자료 commit [7205ee4](https://github.com/Spatzlyn/262RCOSE45700/commit/7205ee4f9518dc75d30a05389e5e6977000a987a). 새 Pilot 결과는 아직 이 commit에 포함되어 있지 않습니다.
