# LOVE Autonomous Work Queue V1

## Queue policy
Work is processed in this order unless evidence changes the priority:

1. P0 execution/task integrity
2. P0 evidence/replay integrity
3. P0 capability/qualification/selection integrity
4. P0 authority/autonomy boundaries
5. P1 security
6. P1 runtime/server
7. P1 memory
8. P1 client/operability

## Per-item lifecycle
`QUEUED -> FORENSIC -> DESIGN -> IMPLEMENT -> TEST -> EVIDENCE -> VERIFIED | BLOCKED`

## Continuation rule
After a VERIFIED checkpoint, STT may continue automatically to the next in-scope item on the same feature branch.

After BLOCKED, STT must record the exact blocker and stop if resolving it would require governance expansion, missing external authority, production access, or human approval.

## Three-lookup rule
For a required capability/owner:
- lookup 1: canonical source;
- lookup 2: independent source-path/search;
- lookup 3: implementation/call-site/evidence cross-check.

If unresolved after three attempts, classify as a current-baseline GAP and evaluate a best-fit replacement/new implementation. Do not reconstruct legacy merely because it may have existed.

## Checkpoint requirements
Every completed item records:
- item identifier;
- decision;
- changed files;
- commit SHA;
- tests run;
- negative tests;
- static checks;
- evidence path;
- remaining verification debt;
- release impact.

## Stop conditions
Stop autonomous progression when:
- main merge would be required;
- release/version creation would be required;
- production deployment would be required;
- a governance/security boundary would need alteration;
- evidence contradicts the current semantic model and root cause cannot be established safely;
- scope is no longer unambiguously in the authorized mission.
