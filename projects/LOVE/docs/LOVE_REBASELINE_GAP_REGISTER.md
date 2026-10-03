# LOVE Rebaseline Gap Register

## Status
FEATURE BRANCH / ENGINEERING BASELINE.
No runtime behavior is changed by this register.

## Rule applied
The LOVE Evolution-First Rebaseline Rule is applied: after three materially different current-source/evidence lookup attempts without sufficient evidence, the item is treated as a baseline GAP for engineering purposes. This does not assert historical non-existence.

## Current decisions

| Item | Current evidence result | Decision | Next engineering action |
|---|---|---|---|
| TaskContract semantic owner | Not identified after repeated current-source lookup | GAP | Design a best-fit task semantic owner; do not reconstruct legacy blindly |
| Store semantic owner | Not identified after repeated current-source lookup | GAP | Establish a minimal durable persistence owner compatible with execution/evidence semantics |
| Capability registry exact owner | Not identified after repeated current-source lookup | GAP | Establish one canonical capability registry owner; reuse existing qualification/learning semantics where appropriate |
| DurableExecution | Exact implementation found | KEEP | Preserve proven execution primitives; verify integration |
| server.async_manager execution path | Referenced by autonomy; overlaps DurableExecution responsibility | RECONCILE | Determine one execution semantic owner and remove duplicate responsibility |
| EvidenceLedger / EvidenceCore | Exact implementation found | KEEP | Preserve integrity/trust semantics |
| ExecutionReplay | Exact implementation found | KEEP | Preserve replay integrity semantics |
| Learning -> Qualification -> Eligibility -> Selection | Exact implementation found at source level | KEEP | Runtime verify the closed path |
| AuthStore | Exact implementation found | KEEP | Runtime/security verify |
| Flutter ApiClient | Exact implementation found | KEEP | Verify endpoint contract against server implementation |

## Priority

### P0 — resolve before meaningful runtime replacement work
1. Task semantic owner
2. Durable execution ownership collision
3. Capability registry ownership

### P1 — resolve before production
1. Server endpoint implementation mapping
2. Client/server contract verification
3. Authentication runtime verification
4. Learning/qualification/selection runtime verification

## Constraints
- No legacy reconstruction unless later evidence proves a legacy artifact is the best-fit source.
- No duplicate subsystem when an existing semantic owner can safely absorb the responsibility.
- No runtime self-escalation.
- No automatic promotion from evidence or learning.
- No main merge or production release from this register.
