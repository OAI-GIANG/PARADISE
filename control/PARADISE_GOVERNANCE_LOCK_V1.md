# PARADISE GOVERNANCE LOCK V1

Status: ACTIVE DESIGN LOCK

## Active authority
- PARADISE root: F:\OAI\PARADISE
- PARADISE control authority: F:\OAI\PARADISE\control
- LOVE source authority: GitHub Sauthienthu89/LOVE main @ 0c4e40f95b2d3c20289a4a5e99983ceec93a6b8d
- OG: historical lineage/reference only

## Canonicality rule
Filesystem location, process state, runtime state, or evidence file naming does not independently confer canonical authority.

## Execution rule
Verified execution must bind:
COMMIT -> WORKTREE/WORKSPACE -> RUNTIME -> EVIDENCE

## Protected actions
The following are blocked unless a specific governance gate and authorization permit them:
- delete
- move
- rename
- overwrite canonical artifacts
- git reset/stash/commit/push
- kill/restart processes
- deploy/promote production
- expose or copy secrets

## Legacy state
control-plane/ is preserved legacy governance input and is not active authority.
projects/LOVE/ is a provenance-preserved distilled source/design snapshot; it is not a LOVE source mirror or runtime authority. projects/OG/ remains a legacy placeholder.

## Promotion rule
A decision or design document is not by itself authorization for destructive or production actions.

## Evidence rule
Claims remain UNVERIFIED when required evidence is absent.
