# PARADISE FOUNDATION V1

Status: DESIGN LOCK
Physical Root: F:\OAI\PARADISE

## 1. Authority
PARADISE is the local governance and execution root. It does not replace remote project source-of-truths.

## 2. Topology
- control-plane/ — governance, registries, policies, state manifests.
- projects/ — project boundaries and canonical-source references. LOVE and OG are separate domains.
- workspace/ — mutable working copies, experiments, patches, and isolated execution workspaces.
- runtime/ — runtime instances, runtime metadata, launch/config references, and operational state.
- evidence/ — verification evidence, test results, provenance bindings, and audit records.
- knowledge/ — external intelligence, research, learned/reference material.
- archive/ — historical artifacts and retained snapshots that are not active source-of-truth.
- secrets/ — protected local credentials and secret material; never canonical Git content.

## 3. Source-of-truth policy
- LOVE source: GitHub Sauthienthu89/LOVE, with an explicitly pinned commit for each execution baseline.
- OG source: its separately identified canonical repository/state; do not infer it from archive contents.
- PARADISE governance state: control-plane registries/manifests.
- Runtime truth: runtime registry plus independently observed process/runtime evidence.
- Evidence truth: evidence records bound to commit/worktree/runtime identities.

## 4. Registries
### canonical registry
Identity of canonical sources and pinned commits/trees. No "latest" as identity.

### project registry
Project identity, repository, canonical branch, ownership boundary, and lifecycle state.

### provenance registry
Source -> artifact -> transformation -> destination relationships, with hashes/commit IDs where applicable.

### runtime registry
Runtime ID, project, worktree, commit/tree identity, PID/process identity when observed, endpoint, environment, and lifecycle state.

### evidence registry
Evidence ID, task/test ID, commit, tree, worktree, runtime identity, command, result, timestamp, and artifact hashes.

### migration registry
Source path, destination path, classification, ownership, provenance, migration status, verification status, and rollback/reference information. No migration is implicit.

## 5. Governance invariants
1. Canonical source is never inferred from a working directory name.
2. A dirty worktree cannot be a canonical execution anchor.
3. Runtime is not canonical unless bound to a verified worktree and commit/tree identity.
4. Evidence is not VERIFIED unless its source/runtime binding is reproducible.
5. Secrets are outside canonical source and must not be copied into public/project repositories.
6. Migration requires explicit classification and provenance; no blind bulk copy.
7. Historical artifacts remain preserved until authority/provenance review permits retirement.
8. Decision does not equal authorization for destructive or production actions.

## 6. Current foundation state
- Root exists and is verified: F:\OAI\PARADISE
- Topology directories exist and are empty at foundation level except for this control-plane design record.
- No LOVE data migrated.
- No OG data migrated.
- No runtime moved.
- No GitHub state changed.
- No deployment performed.

## 7. Gate status
FOUNDATION_DESIGN: LOCKED
MIGRATION: NOT AUTHORIZED
RUNTIME_REBIND: NOT AUTHORIZED
DEPLOYMENT: NOT AUTHORIZED
PRODUCTION: NOT AUTHORIZED
