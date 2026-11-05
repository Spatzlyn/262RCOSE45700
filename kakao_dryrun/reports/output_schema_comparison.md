# Raw output와 schema 비교

원문은 각 run의 `first/raw_output.txt`에 special tokens를 포함해 보존했습니다. `decoded_output.txt`는 tokenizer의 skip_special_tokens=True 결과입니다. 실제 모델 재시도와 parser의 whole Markdown fence 제거는 다른 단계입니다. Field 추가, 좌표 clipping, GT 답변 삽입은 하지 않았습니다.

| run / 단계 | strict JSON / schema | fence 제거 후 schema | regions | Draft Object / Relation / Action |
|---|---|---|---|---|
| bf16_280 / 기존 첫 출력 | False / False | True | present (0) | 3/16 / 0/4 / False |
| nf4_280 / 기존 첫 출력 | False / False | False | MISSING | N/A: schema invalid |
| qlora_280_reloaded / 기존 첫 출력 | False / False | False | MISSING | N/A: schema invalid |
| nf4_prompt_v1_first / 수정 prompt 첫 출력 | True / True | True | present (0) | 4/16 / 0/4 / False |
| qlora_prompt_v1_first / 수정 prompt 첫 출력 | True / True | True | present (0) | 3/16 / 0/4 / False |
| nf4_original_failure_retry / 기존 실패의 model retry #1 | False / False | True | present (0) | 2/16 / 0/4 / False |
| qlora_original_failure_retry / 기존 실패의 model retry #1 | False / False | True | present (0) | 2/16 / 0/4 / False |

기존 BF16은 fence만 제거하면 schema valid입니다. 기존 NF4와 학습 후 NF4+LoRA는 fence를 제거해도 `$.track1.regions: required field missing`입니다. 두 invalid output은 all-A와 MONITOR_AHEAD/no_condition을 눈으로 읽을 수 있지만, 구조화 평가 점수를 0으로 산출하지 않았습니다.

수정 prompt는 원래 system rules와 전체 JSON Schema를 그대로 유지하고, 마지막에 JSON-only / 간결한 출력 / required key checklist / regions key 존재 / 유효 ID 참조를 요구했습니다. 이미지에 Region을 선언할 근거가 없으면 빈 배열을 출력하라는 일반 schema 지시이며 GT의 Region 수나 답변을 주지 않았습니다. 실제 두 첫 출력 모두 regions=[]를 모델이 직접 생성했습니다. 이는 schema 성공이지 Region 인식 성공을 뜻하지 않습니다. 완전한 원래/수정 system prompt와 diff는 `prompts/`에 있고 실제 chat-template prompt, messages, input manifest는 각 run에 있습니다.

`*_prompt_v1_first`는 수정 prompt의 첫 generation으로, 재시도 count=0입니다. 두 run 모두 strict JSON/schema success였습니다. `*_original_failure_retry`는 기존 invalid 첫 응답을 assistant history에 넣고 schema 오류 문자열만 user 메시지로 제공한 model retry #1입니다. 그 재시도는 strict 단계에서 fence 때문에 실패했고, field를 고치지 않는 fence 제거 후 schema를 통과했습니다. 이 결과를 첫 출력 성공률에 섞지 않았습니다. Retry run의 `first/`는 해당 새 프로세스의 첫 generation이라는 저장 폴더 이름이며, 전체 protocol에서는 retry #1입니다. `config.attempt_kind`, `retry_context.json`이 이를 명시합니다. 원래 실패 호출 + 재시도 호출의 비용은 두 run을 합산해야 하며 retry 행은 재시도 호출만의 시간입니다.

Prompt 수정으로 해결한 것은 required-field 준수입니다. 동일 단일 장면에서 semantic quality 향상이나 QLoRA 개선을 입증하지 않습니다. 대표 결과는 사후 best-score 선택이 아니라 **가장 먼저 완료한 modified-prompt base NF4 첫 출력**으로 고정했습니다. Raw와 parsed JSON 모두 `representative_inference/`에 있으며 원본과 hash가 같습니다.

- bf16_280: [raw](../original_evidence/runs/bf16_280/first/raw_output.txt), [metrics](../original_evidence/runs/bf16_280/first/metrics.json), [config](../original_evidence/runs/bf16_280/config.json)
- nf4_280: [raw](../original_evidence/runs/nf4_280/first/raw_output.txt), [metrics](../original_evidence/runs/nf4_280/first/metrics.json), [config](../original_evidence/runs/nf4_280/config.json)
- qlora_280_reloaded: [raw](../original_evidence/runs/qlora_280_reloaded/first/raw_output.txt), [metrics](../original_evidence/runs/qlora_280_reloaded/first/metrics.json), [config](../original_evidence/runs/qlora_280_reloaded/config.json)
- nf4_prompt_v1_first: [raw](../runs/nf4_prompt_v1_first/first/raw_output.txt), [metrics](../runs/nf4_prompt_v1_first/first/metrics.json), [config](../runs/nf4_prompt_v1_first/config.json)
- qlora_prompt_v1_first: [raw](../runs/qlora_prompt_v1_first/first/raw_output.txt), [metrics](../runs/qlora_prompt_v1_first/first/metrics.json), [config](../runs/qlora_prompt_v1_first/config.json)
- nf4_original_failure_retry: [raw](../runs/nf4_original_failure_retry/first/raw_output.txt), [metrics](../runs/nf4_original_failure_retry/first/metrics.json), [config](../runs/nf4_original_failure_retry/config.json)
- qlora_original_failure_retry: [raw](../runs/qlora_original_failure_retry/first/raw_output.txt), [metrics](../runs/qlora_original_failure_retry/first/metrics.json), [config](../runs/qlora_original_failure_retry/config.json)

메타데이터 해석: 각 metrics의 `retry_count=0`은 parser 함수가 모델을 재호출하지 않았다는 뜻입니다. 전체 실험의 model retry count는 `audit/attempt_protocol.json`에서 first=0, retry=1로 별도 기록했습니다. Score나 raw metrics를 소급 수정하지 않았습니다.
