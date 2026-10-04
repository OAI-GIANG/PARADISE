# PARADISE CORE PRODUCT CAPABILITY AUDIT — 2026-10-04

Status: IMPLEMENTATION IN PROGRESS / EVIDENCE-GATED
Repository: OAI-GIANG/PARADISE
Branch: feature/stt-home-inference-20261004

## Scope

P0 product capabilities audited:
1. Code Environment
2. Image
3. Video
4. Text/Document Execution
5. Human-like Natural Language
6. Plugin Integration

G1-G4 semantic/deep-processing work is not reopened.

## Findings

| Capability | Existing evidence | Current state | P0/P1 gap |
|---|---|---|---|
| Code Environment | LOVE inventory already identifies workspace/filesystem/process/test primitives; STT Home previously had no user-facing workspace API | IMPLEMENTED LOCAL | browser workspace UX + richer project/git/test/debug flow still needed |
| Image | No image upload/analysis/edit/generation runtime contract found in current STT Home | MISSING | upload + media contract + model/tool adapter + UI |
| Video | No video runtime contract found in current STT Home | MISSING | upload + inspection + analysis/transform/generation adapter + UI |
| Text/Document | Chat exists; artifact/document pipeline is not exposed by STT Home | PARTIAL | document artifact creation/export and verification |
| Human-like Natural Language | Provider abstraction + continuity/memory context exist | PARTIAL | dedicated natural-language evaluation suite and style controls |
| Plugin Integration | LOVE capability registry/governance concepts exist; STT Home has no plugin discovery/authorization/invocation surface | MISSING | plugin contract, registry adapter, auth/policy, invocation, observation, revoke |

## Implementation performed in this audit

- Added bounded `runtime/stt_home/capabilities.py`.
- Added `code.workspace` capability with sandboxed list/read/write/run-python operations.
- Added explicit confirmation for workspace write/run side effects.
- Added evidence events for workspace write/run.
- Added `/api/capabilities`, `/api/workspace/list`, `/api/workspace/read`, `/api/workspace/write`, `/api/workspace/run`.
- Added STT Home regression coverage for capability catalog and workspace guardrails.
- Added UI code-workspace controls and fixed the missing token/save-token DOM dependency.

## Regression

Before/after core regression remains green in the local execution boundary:
- I01-I19 + K1-K8: 20/20 PASS
- PARADISE runtime: 5/5 PASS
- semantic contract: 8/8 PASS
- STT Home: 4/4 PASS
- Total: 37/37 PASS across these four suites.

The 37 count is a suite-total after adding one STT Home test; it is not a claim about production verification.

## Residual order

1. Code Environment — complete current P0 baseline; next P1: project/git/test/debug integration.
2. Image — P0 missing.
3. Video — P0 missing.
4. Text/Document — P0 artifact execution missing.
5. Natural Language — P0 evaluation/quality gate missing.
6. Plugin Integration — P0 contract/runtime/UI missing.

Production deployment remains independently blocked by the VPS pairing authority; this audit does not bypass that boundary.
