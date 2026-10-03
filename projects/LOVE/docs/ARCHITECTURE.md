# STT-LOVE Architecture

## 1. Layers

1. STT Core
   - identity
   - goal normalization
   - decision intent

2. LOVE Core
   - workspace
   - filesystem
   - process execution
   - timeout
   - stdout/stderr/exit code

3. OG Core
   - capability selection
   - bounded planning
   - governance checks

4. Evidence Core
   - append-only records
   - hash chaining
   - observed results

5. Model Inference (optional, feature-gated)
   - DeepSeek chat-completion provider (model `deepseek-flash`)
   - bounded ModelPlanner: proposes registry commands and drafts answers
   - strictly advisory: never authorizes, never executes, never bypasses OG

## 2. Required path

STT -> LOVE -> OG Core -> LOVE execution -> Evidence

## 3. Boundary rule

LOVE must never decide business authorization.
OG decides whether an operation is allowed.
STT decides what outcome is desired.

## 4. Migration rule

Existing OG is a source of proven patterns, not a codebase to copy wholesale.
Only explicitly selected capabilities enter the new core.

## 5. Model inference boundary

DeepSeek (`deepseek-flash`) is the optional model inference backend. It is
disabled by default and only builds when `LOVE_LLM_ENABLED=1` and a credential
(`DEEPSEEK_API_KEY` or `DEEPSEEK_API_KEY_FILE`) is present.

Flow:

    goal
      -> STT.normalize_goal
      -> ModelPlanner.propose            (advisory only)
      -> registry whitelist validation   (every proposed command must already exist)
      -> OG AEGR authorize               (mandatory; never bypassed)
      -> CommandRouter route             (capability registry)
      -> LOVE execution                  (existing execution whitelist)
      -> IndependentVerifier + Evidence + replay cassette
      -> ModelPlanner.respond            (advisory answer grounded in observed report)

Rules:

- The model only proposes; it holds no authority and no execution rights.
- OG authorization, the capability registry and the execution whitelist remain the
  only authority. `OGCore.authorize` runs before every execution.
- Unknown, malformed or low-confidence proposals are rejected and fall back to the
  deterministic capability selector.
- Model output is non-deterministic, so `prompt_sha256` / `response_sha256` and a
  bounded replay cassette are recorded; model records are marked `authority: none`.
- A model failure never upgrades or blocks a verified execution; the task result is
  decided by observed execution and independent verification.
- Secrets are read from environment/file and never appear in evidence, logs or API
  responses. `GET /api/v1/model` exposes status only.
