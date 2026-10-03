# PARADISE REGISTRY SCHEMA V1

All registries are governance records. They identify state; they do not silently authorize mutations.

## canonical registry
Required fields: canonical_id, domain, source_uri, repository, branch, commit_sha, tree_sha, authority, status, verified_at.

## project registry
Required fields: project_id, name, domain, canonical_id, repository, workspace_policy, runtime_policy, evidence_policy, lifecycle_status.

## provenance registry
Required fields: provenance_id, source_id, source_path_or_uri, artifact_id, transformation, destination, source_hash_or_commit, destination_hash, actor, timestamp, status.

## runtime registry
Required fields: runtime_id, project_id, worktree_path, commit_sha, tree_sha, process_identity, endpoint, environment, observed_at, status.

## evidence registry
Required fields: evidence_id, project_id, task_id, test_id, commit_sha, tree_sha, worktree_path, runtime_id, command, result, timestamp, artifact_hashes, status.

## migration registry
Required fields: migration_id, source, destination, classification, ownership, provenance_id, source_hash, destination_hash, verification, rollback_reference, authorization_status, status.

## Status vocabulary
DESIGN | CANDIDATE | VERIFIED | ACTIVE | SUPERSEDED | BLOCKED | RETAINED | RETIRED | UNVERIFIED

## Safety rule
No registry entry alone authorizes deletion, overwrite, reset, commit, deployment, process termination, or secret exposure.
