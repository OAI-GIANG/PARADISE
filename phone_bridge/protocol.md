# Phone Bridge V1.1 Protocol

Status: IMPLEMENTATION CHECKPOINT — NOT PRODUCTION

## Boundary
Phone client -> authenticated transport -> Phone Bridge -> governance/AEGR -> governed runtime.

The bridge is a transport/capability adapter. It does **not** own policy, execution,
durable execution state, evidence truth, or provider credentials.

## Request
Required fields:
- `protocol_version`
- `request_id` (UUID)
- `operation`
- `timestamp`
- `nonce`
- `payload` (object)

Authentication is supplied out-of-band to the bridge handler. The bridge validates
schema, authentication, replay window, and then hands authorization to the canonical
governance owner.

## Replay
A `(request_id, nonce)` pair may be accepted only once inside the configured clock
window. Expired and replayed requests fail closed.

## Authorization
The bridge calls an injected authorization handoff. A denial is terminal for the
submission. The bridge never converts DENY to ALLOW and never executes an operation.

## Response
Success at this layer means `SUBMITTED` after authorization handoff. It does **not**
mean execution completed or evidence was verified.

Rejection uses stable error codes without stack traces, secrets, internal paths, or
provider credentials.

## State boundary
Phone owns client/UI state. Bridge owns only transient transport validation state.
Governance owns authorization state. Runtime owns execution state. Evidence authority
owns evidence truth.

## Explicit non-goals
- No privileged shell execution.
- No GitHub credential access.
- No governance bypass.
- No evidence-status override from the phone.
- No durable execution implementation inside the bridge.
- No production endpoint claim from this checkpoint.
