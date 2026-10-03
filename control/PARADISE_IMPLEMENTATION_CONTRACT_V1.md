# PARADISE IMPLEMENTATION CONTRACT V1

Status: MATERIALIZED IMPLEMENTATION DESIGN / NOT VERIFIED
Authority: F:\OAI\PARADISE\control\PARADISE_CONTROL_MODEL_V1.md
Semantic baseline: 7 primitives + 5 obligations + K1-K8

## 1. Scope
This contract is the minimum implementation boundary for the frozen PARADISE semantic kernel. It does not add primitives or invariants.

## 2. Primitive contracts

### P1 Authority
Authority MUST bind subject, scope, actions, issuer, validity interval, status, and provenance. Authorization MUST be evaluated against the requested action, subject, scope, context, and current validity at the execution boundary.

### P2 Policy / Gate
A gate MUST produce an explicit outcome: ALLOW, DENY, BLOCKED, CONFLICT, or UNKNOWN. UNKNOWN MUST NOT become ALLOW.

### P3 State / Lifecycle
State transitions MUST bind expected state/version, action, authorization, and resulting state. A stale expected version MUST be rejected rather than silently merged.

### P4 Evidence / Provenance
Evidence MUST identify source, subject, scope, capture time, provenance, integrity, and verification status. A claimed verification status is not sufficient without a bound integrity/provenance record.

### P5 Execution / Replay
Every execution MUST have a unique execution identity and bind the authorized action, authority, input state/version, result, side effects, and witness. Replay MUST be explicitly classified as allowed/idempotent or rejected; an old execution record is not fresh authorization.

### P6 Cognition / Advisory
Cognition may propose, analyze, warn, or recommend. Its output MUST remain structurally distinct from authorization and execution permission.

### P7 Bounded Change
Every change MUST declare target, requested scope, requester, authority, preconditions, verification requirement, and recovery/rollback reference. Requested scope MUST be contained by authorized scope.

## 3. Obligation enforcement

O1 Canonicality -> canonical identity/source gate.
O2 Independent Verification -> verifier/evidence separation where required.
O3 External Side-Effect -> authorization immediately before side-effect commit.
O4 Contradiction Resolution -> explicit CONFLICT state; no silent selection.
O5 Temporal Validity -> validity checked at authorization and execution/side-effect boundary.

## 4. K1-K8 executable constraints

K1 Non-Escalation: no operation may increase authority scope from its input authority.
K2 Advisory Non-Authority: advisory records cannot satisfy authorization requirements.
K3 Evidence Non-Authority: evidence records cannot themselves authorize an action.
K4 Context-Bound Verification: verification is valid only for its declared subject/scope/context.
K5 External Effect Separation: external effects require an authorization decision bound to the effect.
K6 Explicit Conflict: contradictory authoritative inputs produce CONFLICT/BLOCKED, never silent resolution.
K7 Bounded Self-Modification: changes to governed state require authority outside the changed scope and bounded change authorization.
K8 Unknown Is Not Allow: UNKNOWN evidence/policy state cannot produce ALLOW.

## 5. Adversarial closure requirements
The implementation MUST reject or block:
- authority scope/action/context escalation;
- forged or integrity-unbound evidence;
- stale/revoked authority at side-effect time;
- stale state/version transitions;
- replay of non-idempotent executions;
- advisory-to-authority promotion;
- evidence-to-authorization promotion;
- unresolved conflicting evidence;
- UNKNOWN-to-ALLOW fallback;
- unauthorized self-modification;
- external side-effects without a fresh bound authorization.

## 6. Verification boundary
This document is implementation design. Runtime behavior becomes TESTED only when the executable negative/positive test suite passes with captured evidence. It becomes VERIFIED only after the evidence is bound to the exact source/worktree/runtime/test identity.

## 7. Freeze rule
Implementation may refine data structures and enforcement mechanisms but MUST NOT introduce a new semantic primitive or invariant without a separate primitive-level evidence review.
