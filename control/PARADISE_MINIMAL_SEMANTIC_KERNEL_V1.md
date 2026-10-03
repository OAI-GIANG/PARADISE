# PARADISE MINIMAL SEMANTIC KERNEL V1

Status: CANONICAL SEMANTIC DESIGN — PENDING IMPLEMENTATION VERIFICATION
Authority: F:\OAI\PARADISE\control\
Provenance decision: PARADISE_D8_SEMANTIC_PROVENANCE_DECISION_V1.md
Historical status: NOT HISTORICAL; this V1 is a newly canonicalized design target after D8.3 provenance reconciliation.

## 1. Purpose

This document establishes the canonical semantic target for PARADISE after the D8.3 finding that no historical 19-invariant source could be recovered. It does not retroactively rewrite history. The current K1-K8 implementation is treated as the predecessor baseline and is superseded semantically only after implementation and regression verification pass.

## 2. Semantic primitives

P1 Authority
P2 Policy / Gate
P3 State / Lifecycle
P4 Evidence / Provenance
P5 Execution / Replay
P6 Cognition / Advisory
P7 Bounded Change

## 3. Obligations

O1 Canonicality
O2 Independent Verification
O3 External Side-Effect
O4 Contradiction Resolution
O5 Temporal Validity

## 4. Canonical invariants

I01 Explicit Authority Binding — an authorization MUST identify issuer, subject, action, scope, context, validity interval, status, and provenance.

I02 No Authority Escalation — no decision, evidence, execution, advisory, or change request may increase the authority scope available to it.

I03 Temporal Authority Validity — authority MUST be valid at the authorization boundary and MUST be revalidated at the external side-effect boundary.

I04 Context/Action/Scope Binding — authorization is valid only for the exact subject, action, scope, and execution context for which it was issued.

I05 Explicit Gate Outcome — every gate evaluation MUST resolve to ALLOW, DENY, BLOCKED, CONFLICT, or UNKNOWN; implicit success is forbidden.

I06 Unknown Is Not Allow — UNKNOWN policy, evidence, authority, or verification state MUST NOT produce ALLOW.

I07 Conflict Is Explicit — contradictory authoritative inputs MUST produce CONFLICT or BLOCKED; silent selection is forbidden.

I08 Versioned State Transition — a state mutation MUST bind the expected state/version, requested action, authority, and resulting version.

I09 Stale State Rejection — a transition against a stale or mismatched expected version MUST be rejected and MUST NOT silently merge.

I10 Lifecycle Boundary — a state transition MUST be valid for the declared lifecycle/state context; invalid lifecycle transitions MUST be rejected.

I11 Evidence Integrity and Provenance — evidence MUST bind source, subject, scope, capture time, provenance, integrity, and verification status; unverifiable integrity MUST not be promoted.

I12 Evidence Is Not Authority — evidence may establish a claim but MUST NOT itself authorize an action.

I13 Context-Bound Verification — verification is valid only for the exact declared subject, scope, source/provenance context, and verification conditions.

I14 Unique Execution Identity — each execution MUST have a unique execution identity bound to its authorized action, subject, scope, input state/version, and result witness.

I15 Replay Safety — non-idempotent execution identities MUST NOT be accepted twice; idempotent replay MUST be explicitly declared and bounded.

I16 Side-Effect Authorization Freshness — an external side effect MUST use a fresh authorization bound to the exact effect; an old execution record is not fresh authority.

I17 Cognition Is Advisory — cognition may propose, analyze, warn, or recommend, but its output MUST remain structurally distinct from authorization and execution permission.

I18 Bounded Change and Independent Authority — requested change scope MUST be contained by authorized scope; self-modification requires authority independent of the changed target.

I19 Recovery-Bound Change — every governed change MUST declare verification requirements and a recovery/rollback reference before execution; unbounded or unrecoverable governed change MUST be rejected.

## 5. Forbidden transitions

The following semantic transitions are forbidden:

- advisory -> authorization
- evidence -> authorization
- UNKNOWN -> ALLOW
- CONFLICT -> silent selection
- expired/revoked authority -> external side effect
- stale state -> successful mutation
- non-idempotent execution -> accepted replay
- requested scope -> broader authorized scope
- self-modifying component -> sole authority for its own change
- unverifiable evidence -> VERIFIED promotion
- decision -> authorization without an applicable authority gate
- archive/location -> canonical authority
- runtime/evidence -> source authority
- historical reference -> active dependency without explicit governance promotion
- governed change -> execution without recovery/rollback reference

## 6. Authority boundaries

Canonical semantic authority: this document and the control-plane authority that explicitly references it.

Execution authority: an explicit Authority/Authorization record at the execution boundary.

Advisory authority: none.

Evidence authority: verification only; never authorization.

Runtime authority: derived operational state; never canonical source authority.

Archive authority: retention only.

Secrets authority: credential protection only; never source/evidence/knowledge authority.

## 7. State boundaries

Canonical design state is distinct from mutable workspace state.

Workspace state is mutable and non-canonical by default.

Runtime state is derived from a bound source/worktree identity.

Evidence state records verification observations and cannot mutate source authority by itself.

Lifecycle transitions require expected-version binding and explicit transition acceptance.

## 8. Truth boundaries

Canonical truth = explicitly authoritative design/source state.

Observed truth = runtime/test/evidence observation bound to an identity.

Derived truth = generated state whose provenance remains bound to its source.

Advisory content = non-authoritative hypothesis/recommendation.

UNKNOWN = unresolved truth state; it is never equivalent to ALLOW or VERIFIED.

CONFLICT = contradictory authoritative claims requiring explicit resolution; it is never silently collapsed.

## 9. Invariant dependency groups

Authority: I01-I04
Policy/Gate: I05-I07
State/Lifecycle: I08-I10
Evidence/Provenance: I11-I13
Execution/Replay: I14-I16
Cognition/Advisory: I17
Bounded Change: I18-I19

Cross-cutting obligations O1-O5 constrain all groups where applicable.

## 10. Acceptance criteria

A semantic implementation is TESTED only when positive and negative tests exercise all 19 invariants and the forbidden transitions.

A semantic implementation is VERIFIED only when the test evidence binds the exact source commit/tree, worktree, runtime identity, test suite, result, and artifact hashes.

A semantic freeze is allowed only after:
1. all 19 invariants have executable coverage;
2. all forbidden transitions have negative coverage;
3. regression coverage for the K1-K8 predecessor passes;
4. no duplicate semantic engine is introduced;
5. LOVE/OG authority boundaries remain intact;
6. evidence is reproducible and bound to the exact implementation identity.

## 11. Compatibility rule

K1-K8 are predecessor constraints. Their intent is preserved where covered by I01-I19, but no one-to-one mapping is asserted unless separately evidenced. The old baseline remains historical evidence, not a competing semantic authority.

## 12. Freeze rule

This document may be promoted from CANONICAL SEMANTIC DESIGN to SEMANTIC FREEZE only after the acceptance criteria are VERIFIED. No implementation may introduce a semantic primitive or invariant outside I01-I19 without a new governed semantic review.