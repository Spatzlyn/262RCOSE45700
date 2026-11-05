# QLoRA target・loss mask・adapter audit

단일 Draft example을 사용한 5-step training smoke입니다. Generalization이나 학습 성능 개선을 검증한 실험이 아닙니다.

실제 target은 `expected/prediction.example.json`입니다. Object 16개, prediction Region 2개(C 제외), attributes, R1–R4, conditional actions, unknowns, Track 2·3의 missing_input 구조 전체를 supervised learning했습니다. Object/Region ID만 train_obj_1…16, train_region_1…2로 일관되게 치환했습니다. 원본 target을 같은 mapping으로 바꾼 결과와 저장된 `target.json`이 완전히 같습니다. Input prefix에는 reference/target/GT ID/Box/C polygon이 없으며 assistant target에만 정답을 넣었습니다.

**6040 = masked prompt 3851 + supervised 2189**입니다. Supervised 2189는 **JSON 본문 2187 + `<turn|>`와 newline 2 token**입니다. Image placeholder 264개는 prompt 3851 안에 포함되므로 다시 더하지 않습니다. Real padding은 0, truncation은 없습니다.

| prompt 구성 | token 수 |
|---|---|
| chat_control_and_separators | 21 |
| system_rules | 1674 |
| json_schema | 1647 |
| id_coordinate_instruction | 61 |
| image_soft_token_placeholders | 264 |
| task_question | 184 |

| assistant JSON 구성 | token 수 |
|---|---|
| json_structural_boundary | 5 |
| item_id | 12 |
| track1.attributes | 28 |
| track1.objects | 1155 |
| track1.relations | 497 |
| track1.actions | 226 |
| track1.unknowns | 97 |
| track1.regions | 129 |
| track2 | 17 |
| track3 | 21 |

표는 실제 원본 `loss_mask.pt`(게시본에는 portable JSON 제공)의 input_ids를 decode한 뒤 다시 tokenize하여 6040개가 정확히 같음을 확인하고 offset으로 분해했습니다. Boundary를 걸치는 BPE token은 첫 문자 위치의 구성요소에 한 번만 배정했습니다. 따라서 구성별 수의 합이 정확하지만 독립 문장을 따로 tokenize한 길이와는 다를 수 있습니다. `training_tokens_and_mask.json`과 portable mask JSON에 재현 정보를 보존했습니다.

labels의 prompt 0…3850, image token, padding은 모두 -100입니다. Supervised positions 3851…6039를 예측하는 logits positions 3850…6038만 선택합니다. `shift_labels=labels[:, select+1]`이 실제 target IDs와 일치합니다. 첫 target token 14937을 prompt 마지막 position 3850에서 예측하므로 off-by-one 문제는 발견되지 않았습니다. 마지막 두 terminator token도 loss 대상입니다. 실제 padding이 없는 것과 별개로 기존 synthetic padding 3개 제외 검사는 통과했습니다.

Training 설정은 NF4 double quantization, BF16 compute, text attention q_proj/v_proj LoRA rank 8 / alpha 16 / dropout 0입니다. 실제 66 module, 132 tensor, 2,269,184 trainable parameters입니다. AdamW lr=1e-4, microbatch 1, gradient accumulation 1로 단일 Draft를 5 steps 학습했습니다.

기존 `qlora_280_5step_v2`에서 loss는 1.17743 → 1.12106으로 감소했고 132개 adapter tensor가 업데이트됐습니다. 저장 직후 tensor equality와 새 process reload의 132개 tensor exact match를 확인했습니다. [학습 검증](../audit/training_verification.json), [저장 검사](../training_audit/adapter_save_check.json), [재로드 검사](../runs/qlora_prompt_v1_first/adapter_reload_check.json)에 근거가 있습니다. Model/adapter weights는 포함하지 않습니다.

학습 loss가 감소해도 원래 prompt의 학습 후 inference는 regions 누락으로 schema에 실패했습니다. 수정 prompt에서는 schema가 통과했지만 Relation은 여전히 0/4입니다. Training target 재현, format 준수, generalization은 별개의 검증 항목입니다. 이 branch에는 adapter/model weights를 넣지 않고 검증 로그·hash·config·target·mask만 포함했습니다.
