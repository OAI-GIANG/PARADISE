# PARADISE MEMORY CLOSURE PHASE 2 — IMPLEMENTATION SPEC V1

Status: IMPLEMENTED / TESTED
Source baseline: 904b40a

## Canonical owners
- Memory: `MemoryCore` semantic memory + `RuntimeStore.memory_records` persistence.
- Experience: `CognitiveLifecycle` + `experience_records`.
- Evaluation: `CognitiveLifecycle` + `evaluation_records`.
- Pattern: `CognitiveLifecycle` + `pattern_records`.
- Distillation: `CognitiveLifecycle` + `distillation_records`.
- Consolidation: `CognitiveLifecycle` + `consolidation_records`.
- Cognitive State: `RuntimeStore.cognitive_state`; lifecycle is the only semantic transition writer.
- Model-facing Memory: `RuntimeStore.model_memory`; lifecycle derives it and marks it `DERIVED_NOT_VERIFIED`.
- Execution state: `DurableExecution`; `RuntimeStore.upsert_task()` is explicitly blocked.
- Persistence: `RuntimeStore` only; no second MemoryStore.
- Authorization: PARADISE Kernel.
- Model invocation: ModelGateway only.

## Canonical chain
Memory -> Experience -> Evaluation -> Pattern -> Distillation -> Consolidation -> Cognitive State -> Model-facing Memory -> ModelGateway reasoning request.

## Authority boundary
Evidence does not become authority. Consolidated model-facing memory is advisory/derived and remains `authority: none` and `trust_status: DERIVED_NOT_VERIFIED` until an independent governed verifier exists.

## Promotion rules
- Experience is durable after a memory write.
- Evaluation is `ACCEPT` only when evidence exists and source memory is `VERIFIED`; otherwise `UNCERTAIN`.
- Pattern requires at least two independently observed verified experiences sharing a normalized semantic key.
- Distillation and consolidation require a supported pattern with evidence.
- Model-facing memory is created only from consolidation and never receives authority automatically.
- Unverified experiences cannot consolidate.

## Persistence / restart
All lifecycle artifacts are durable in the existing RuntimeStore SQLite database and survive RuntimeStore reconstruction.

## Negative boundaries
- Direct RuntimeStore execution-state mutation is rejected.
- Unverified memory cannot consolidate.
- Model-facing memory cannot authorize execution.
- Model invocation remains downstream of PARADISE Kernel authorization and ModelGateway.
