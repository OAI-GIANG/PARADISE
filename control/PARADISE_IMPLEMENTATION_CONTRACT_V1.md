# PARADISE IMPLEMENTATION CONTRACT V1

Status: CANONICAL IMPLEMENTATION CONTRACT — PENDING VERIFICATION
Authority: F:\OAI\PARADISE\control\PARADISE_CONTROL_MODEL_V1.md
Semantic authority: F:\OAI\PARADISE\control\PARADISE_MINIMAL_SEMANTIC_KERNEL_V1.md
Historical predecessor: 7 primitives + 5 obligations + K1-K8
Current semantic target: 7 primitives + 5 obligations + I01-I19

## 1. Scope

This contract is the implementation boundary for the canonical PARADISE semantic kernel V1. It does not introduce semantic primitives or invariants outside the canonical semantic kernel.

## 2. Primitive contracts

P1 Authority — authority binds issuer, subject, action, scope, context, validity, status, and provenance.
P2 Policy / Gate — gates return only ALLOW, DENY, BLOCKED, CONFLICT, or UNKNOWN; UNKNOWN never becomes ALLOW.
P3 State / Lifecycle — transitions bind expected state/version and reject stale state.
P4 Evidence / Provenance — evidence binds source, subject, scope, capture time, provenance, integrity, and verification status.
P5 Execution / Replay — execution binds unique identity, authorization, input state/version, result witness, and replay policy.
P6 Cognition / Advisory — cognition is structurally non-authoritative.
P7 Bounded Change — change scope is bounded, independently authorized where self-modification is involved, and recovery-bound.

## 3. Obligation enforcement

O1 Canonicality -> canonical identity/source gate.
O2 Independent Verification -> verifier/evidence separation where required.
O3 External Side-Effect -> fresh authorization immediately before side-effect commit.
O4 Contradiction Resolution -> explicit CONFLICT/BLOCKED; no silent selection.
O5 Temporal Validity -> validity checked at authorization and side-effect boundary.

## 4. Canonical invariant enforcement

I01 Explicit Authority Binding.
I02 No Authority Escalation.
I03 Temporal Authority Validity.
I04 Context/Action/Scope Binding.
I05 Explicit Gate Outcome.
I06 Unknown Is Not Allow.
I07 Conflict Is Explicit.
I08 Versioned State Transition.
I09 Stale State Rejection.
I10 Lifecycle Boundary.
I11 Evidence Integrity and Provenance.
I12 Evidence Is Not Authority.
I13 Context-Bound Verification.
I14 Unique Execution Identity.
I15 Replay Safety.
I16 Side-Effect Authorization Freshness.
I17 Cognition Is Advisory.
I18 Bounded Change and Independent Authority.
I19 Recovery-Bound Change.

## 5. Required forbidden-transition rejection

Implementation MUST reject/block:
- advisory -> authorization;
- evidence -> authorization;
- UNKNOWN -> ALLOW;
- CONFLICT -> silent selection;
- expired/revoked authority -> external effect;
- stale state -> mutation;
- non-idempotent replay;
- scope expansion;
- self-modification without independent authority;
- unverifiable evidence -> VERIFIED;
- decision -> authorization without applicable gate;
- runtime/evidence/archive -> canonical source authority;
- governed change without recovery/rollback reference.

## 6. Verification boundary

Implementation is TESTED only when positive and negative tests cover I01-I19 and the forbidden transitions.

Implementation is VERIFIED only when evidence binds exact source commit/tree, worktree, runtime identity, test identity, result, and artifact hashes.

## 7. Regression compatibility

The predecessor K1-K8 suite remains a required regression layer. Passing K1-K8 does not by itself prove I01-I19.

## 8. Freeze rule

Implementation may refine data structures and enforcement mechanisms but MUST NOT introduce a new semantic primitive or invariant outside I01-I19 without a separate governed semantic review.