# PARADISE DIRECTIVE & ACCOUNTABILITY FRAMEWORK V1

Status: IMPLEMENTATION TARGET
Authority: PARADISE_CONTROL_MODEL_V1 + PARADISE_MINIMAL_SEMANTIC_KERNEL_V1

## 1. Purpose

Govern execution of an authoritative directive so that instruction, responsibility, execution, evidence, verification, and accountability cannot silently diverge.

This framework does NOT create a new semantic primitive or engine. It composes existing P1 Authority, P2 Policy/Gate, P3 State/Lifecycle, P4 Evidence/Provenance, and P5 Execution/Replay.

## 2. Canonical chain

DIRECTIVE -> AUTHORITY -> OBLIGATION OWNER -> EXECUTION -> EVIDENCE -> VERIFICATION -> ACCOUNTABILITY

## 3. Ownership

- Authority/Authorization: P1
- Directive policy gate: P2
- Obligation lifecycle: P3
- Compliance evidence: P4
- Execution/replay: P5
- Remediation/sanction/appeal: governance policy outcome; no new execution owner

## 4. Required directive fields

A directive must identify:
- directive_id
- issuer
- responsible_actor
- action
- scope
- context
- authority_id
- issued_at
- due_at
- acceptance_criteria
- status
- provenance

## 5. Compliance outcomes

ALLOW = directive is currently executable within authority and time boundaries.
DENY = authority/scope/actor requirement fails.
BLOCKED = required evidence, acceptance criteria, recovery, or execution witness is absent.
CONFLICT = authoritative requirements or compliance evidence contradict.
UNKNOWN = required governance/evidence information is unresolved.

## 6. Non-compliance taxonomy

N0 NO_VIOLATION
N1 NOT_AUTHORIZED
N2 SCOPE_DEVIATION
N3 ACTOR_MISMATCH
N4 LATE_OR_EXPIRED
N5 NON_EXECUTION
N6 INCOMPLETE_EXECUTION
N7 EVIDENCE_MISSING
N8 EVIDENCE_INSUFFICIENT
N9 VERIFICATION_FAILED
N10 CONTRADICTORY_EVIDENCE
N11 FALSE_COMPLETION
N12 UNAUTHORIZED_SIDE_EFFECT

## 7. Accountability rule

A compliance failure must identify the responsible actor and the failed obligation. The failure does not itself authorize a sanction. Remediation/sanction/appeal require an applicable governance policy gate and evidence.

## 8. Forbidden transitions

- directive -> execution without applicable authorization
- issuer -> responsible actor substitution without explicit authority
- execution -> completion without result witness
- completion -> verified without verification
- evidence -> authorization
- late/expired directive -> new side effect without fresh authorization
- violation -> sanction without governance authorization/evidence
- unknown compliance -> compliant
- conflict -> silent resolution

## 9. Acceptance criteria

Implementation is TESTED when positive and negative directive-compliance cases cover N0-N12 and the forbidden transitions.

Implementation is VERIFIED only when exact source commit/tree, worktree, runtime, test identity, result, and artifact hashes are bound in evidence.

No production promotion is implied by this framework.
