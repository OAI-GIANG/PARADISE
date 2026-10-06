# Phone Bridge V1.1 — Reconciled Protocol

## Boundary
Phone Bridge is a device/transport adapter. It does not own Governance, AEGR, Evidence Authority, Durable Execution, or Runtime State.

## Identity
`request_id` = Bridge request identity.
`authorization_id` = Governance/AEGR decision identity.
`execution_id` = Durable Execution identity.
`evidence_id` = Evidence authority identity.
These identities MUST NOT be aliased.

## GateOutcome
Canonical authorization outcomes are `ALLOW`, `DENY`, `BLOCKED`, `CONFLICT`, `UNKNOWN`. Only `ALLOW` may create a governed execution submission. All other outcomes fail closed.

## Replay
Bridge enforces transport replay safety through `ReplayStore`. The Bridge owns enforcement; the store owns persistence. The in-memory store is test/dev only. Production requires durable persistence. Store failure is `REPLAY_STORE_UNAVAILABLE` and MUST fail closed.

## Execution boundary
A `GovernedExecutionSubmission` is created only after `ALLOW`. Bridge never calls execution directly and never owns execution state.

## Evidence
Bridge carries correlation references only. It MUST NOT accept client-supplied evidence truth such as `VERIFIED`. Canonical chain: `request_id -> authorization_id -> execution_id -> evidence_id`.

## Errors
Stable safe error codes are returned. Internal stack traces, credentials, filesystem paths, governance internals, and provider secrets MUST NOT cross the boundary.

## Production gate
This protocol is implemented/tested on staging only. Runtime, durable replay, real AEGR, real Durable Execution, EvidenceLedger, device E2E, and production transport remain separate verification gates.
