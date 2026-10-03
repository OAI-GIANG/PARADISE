# LOVE Autonomous Work Loop V1

Status: DESIGN / GOVERNANCE BOUNDARY
Scope: feature branches only

## Purpose
Enable STT to continue LOVE engineering work autonomously while preserving evidence-first governance and human ownership of release authority.

## Allowed autonomous actions
- inspect current canonical source and evidence;
- apply the 3-lookup Evolution-First rule;
- classify KEEP / REPLACE / RECONCILE / RETIRE / GAP;
- implement changes inside an authorized feature branch;
- run focused tests, regression tests, negative tests, and static checks;
- create and update evidence for work performed;
- perform iterative forensic/root-cause analysis when tests fail;
- continue to the next in-scope work item after a verified checkpoint.

## Hard boundaries
STT MUST NOT autonomously:
- merge into main;
- push/alter protected canonical branches except through explicitly authorized feature-branch operations;
- create a LOVE version/release;
- deploy production;
- change governance or canonical authority boundaries without explicit authorization;
- expose, rotate, or retrieve secrets for the purpose of bypassing controls;
- convert evidence into authority without the governing gate;
- silently broaden task scope.

## Work loop
1. Select the highest-priority unresolved in-scope work item.
2. Read current canonical source/evidence.
3. Search up to three independent times for the required owner/capability.
4. If still unresolved, treat it as a current-baseline GAP; do not claim historical absence.
5. Prefer existing semantic owners before creating new ones.
6. Implement only on the feature branch.
7. Run focused regression and negative tests.
8. If FAIL: record finding/root cause, repair only when inside authorized scope, then rerun regression.
9. If PASS: record evidence with commit SHA and test results.
10. Stop at governance/release boundaries and create a checkpoint.
11. Continue with the next in-scope work item only when the previous checkpoint is coherent.

## Autonomous repair rule
A failure may be repaired autonomously only when:
- the root cause is evidenced;
- the change is inside the current work item's scope;
- no governance/security/authority boundary is crossed;
- regression and negative tests can be rerun.

Otherwise stop and checkpoint.

## Evidence states
DESIGN -> IMPLEMENTED -> TESTED -> VERIFIED -> PRODUCTION

No state may be inferred merely from intent. Runtime/production claims require corresponding execution evidence.

## Human gate
Human authorization remains required for:
- main merge;
- release/version creation;
- production deployment;
- governance/canonical contract changes that alter authority;
- scope expansion beyond the current mission.

## Non-goals
This document does not create a new runtime subsystem. It defines an operating/governance loop over existing LOVE capabilities and engineering tooling.
