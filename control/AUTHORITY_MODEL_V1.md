# PARADISE AUTHORITY MODEL V1

## Authority layers
1. GitHub LOVE main + pinned commit — LOVE source authority.
2. PARADISE control — local governance authority.
3. Workspace — mutable execution state, never canonical by default.
4. Runtime — derived operational state.
5. Evidence — verification state bound to source/workspace/runtime.
6. Knowledge — selected reference/derived knowledge.
7. Archive — retained history, not authority.
8. Secrets — protected credentials, never authority.

## Required binding
COMMIT -> WORKSPACE/WORKTREE -> RUNTIME -> EVIDENCE

## Promotion rule
A non-canonical artifact may not be promoted to canonical without explicit governance authorization plus provenance and verification.

## OG rule
OG is historical lineage/reference only. No OG artifact creates a dependency on OG. Selected knowledge may be absorbed only through provenance and fit/evidence review.

## Safety gates
No implicit reset, stash, delete, overwrite, commit, push, process termination, restart, deployment, or secret exposure is authorized by topology or registry state alone.
