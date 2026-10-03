# PARADISE CONTROL MODEL V1

Status: CANONICAL CONSOLIDATED GOVERNANCE DESIGN
Root: F:\OAI\PARADISE\control\

## 1. Purpose
PARADISE is the local governance and evolution control root for the current system. LOVE is the active canonical project. OG is historical lineage/reference only.

## 2. Topology
F:\OAI\PARADISE\
- control/       canonical governance and registry records
- workspace/     mutable, non-canonical execution areas
- runtime/       derived runtime identity/state
- evidence/      verification records and derived evidence artifacts
- knowledge/     selected, provenance-aware knowledge/reference
- archive/       retained history; non-canonical
- secrets/       protected local credentials; never canonical source

projects/LOVE may contain a provenance-preserved distilled source/design snapshot. It is not the LOVE source authority, not a source mirror, and not a runtime authority.

## 3. Authority model
A. LOVE source authority: GitHub Sauthienthu89/LOVE, main @ 0c4e40f95b2d3c20289a4a5e99983ceec93a6b8d.
B. PARADISE local governance authority: F:\OAI\PARADISE\control.
C. PARADISE semantic authority: F:\OAI\PARADISE\control\PARADISE_MINIMAL_SEMANTIC_KERNEL_V1.md.
C. Workspace/worktrees are mutable execution state and are non-canonical by default.
D. Runtime is derived from a bound source/worktree identity.
E. Evidence is verification state and must bind to source, worktree, runtime, and test identity.
F. Archive is retention only; it does not become authority by location.
G. Secrets are protected and never become source/evidence/knowledge authority.

## 4. Canonical execution provenance chain
COMMIT -> WORKTREE/WORKSPACE -> RUNTIME -> EVIDENCE

Every verified execution claim should identify the commit/tree, execution worktree, runtime identity, command/test, result, and evidence artifacts. A runtime or evidence artifact cannot promote itself to canonical source.

## 5. Registry model
The control plane logically owns:
- Canonical Registry: canonical_id, source, branch, commit_sha, tree_sha, authority, status, verification time.
- Project Registry: project identity, canonical reference, workspace/runtime/evidence policy, lifecycle state.
- Provenance Registry: source, artifact, transformation, destination, source/destination identity, actor, timestamp, verification.
- Runtime Registry: project, worktree, commit/tree, process/runtime identity, endpoint/environment, observation time, status.
- Evidence Registry: task/test, commit/tree, worktree, runtime, command, result, timestamp, artifact hashes, status.
- Migration Registry: source/destination, classification, provenance, hashes, verification, rollback reference, authorization, status.

Registry records identify and govern state; they do not by themselves authorize destructive actions, commit/push, deployment, process termination, restart, or secret exposure.

## 6. LOVE boundary
LOVE is the active canonical project governed by PARADISE. GitHub remains LOVE source authority. PARADISE must not create a duplicate LOVE repository or silently promote a local worktree to canonical.

Canonical execution anchor currently identified by governance:
C:\LOVE\canonical-execution-anchor
Pinned source-authority reference:
0c4e40f95b2d3c20289a4a5e99983ceec93a6b8d

Distillation snapshot:
projects/LOVE @ source commit 41db094dcad8a857bf6dfc255e37ec889dd2515f

The 0c4e... identity and 41db... distillation snapshot are intentionally distinct until Git lineage between them is independently verified.

This record is a governance reference; it does not authorize deployment or runtime mutation.

## 7. OG lineage boundary
OG is not a PARADISE project, build dependency, runtime dependency, repository dependency, or deployment dependency.

OG may be referenced as historical lineage. A concept, design, lesson, or evidence item from OG may enter PARADISE knowledge/provenance only after value, fit, provenance, and evidence review. Do not bulk-copy or migrate OG merely for historical completeness.

## 8. Governance gates
G0 Scope Gate: artifact belongs to PARADISE purpose and has clear ownership.
G1 Canonical Gate: source-of-truth is explicit; location alone cannot confer canonical status.
G2 Execution Gate: commit/tree -> worktree -> runtime identity is explicit before execution is treated as evidenced.
G3 Evidence Gate: evidence binds to the exact execution identity and result.
G4 Promotion Gate: non-canonical state requires explicit authorization, provenance, and verification before promotion.
G5 Destructive Gate: reset, stash, delete, overwrite, rename, move, process kill/restart, commit/push, or deployment requires explicit authorization appropriate to the operation.
G6 Production Gate: production promotion requires separate verified evidence and authorization; design/registry state alone is insufficient.

## 9. Classification vocabulary
CANONICAL = authoritative state/record.
NON-CANONICAL = mutable or retained state without source authority.
DERIVED = generated from another bound state.
EPHEMERAL = temporary execution/debug state.
REFERENCE = contextual or historical information that does not govern execution.
SUPERSEDED = retained only for history and no longer active authority.
UNVERIFIED = observed/declared but lacking sufficient evidence for promotion.

## 10. Current legacy boundary
F:\OAI\PARADISE\control-plane\ is a legacy governance source, not an active authority. Its contents must be reconciled semantically before any retirement. No deletion, move, rename, or overwrite is implied by this model.

## 11. Safety invariants
1. No implicit destructive action.
2. No duplicate canonical source.
3. No OG dependency.
4. No secret leakage into canonical/evidence/knowledge state.
5. No production claim without evidence.
6. Decision is not authorization unless the applicable governance gate explicitly grants authority.
7. When evidence is missing, state remains UNVERIFIED.
8. Prefer the smallest state change that satisfies the objective.