# Core Boundaries

## STT
Owns: identity, goal, context, intent, decision.
Does not own: shell, Git mutation, subprocess authorization.

## OG
Owns: capability registry, routing, permission gates, task graph and verification contracts.
Does not own: desktop UX or raw machine lifecycle.

## LOVE
Owns: workspace lifecycle, files, processes, test execution and substrate adapters.
Does not override OG permission decisions.

## Evidence
Owns: observed execution records and hash chaining.
Does not manufacture VERIFIED status.

## Model Inference (DeepSeek)
Owns: bounded text inference and advisory proposals (`ModelPlanner`).
Does not own: authorization, the capability registry, execution, or verification state.
The model never bypasses OG governance: every proposed command must already exist in
the registry and pass `OGCore.authorize`; unknown or malformed proposals are rejected.
Model records are observational (`authority: none`) and never grant permission.

## Protected actions
Main/master/canonical mutation, auto-push and destructive operations require an explicit governance path.
