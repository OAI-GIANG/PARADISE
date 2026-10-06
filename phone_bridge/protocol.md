# Phone Bridge V1 Protocol

Status: DESIGN SKELETON — UNVERIFIED

## Boundary
Phone client -> authenticated transport -> Phone Bridge -> governed runtime.

The bridge is a transport boundary only. It must not become the owner of:
- policy decisions;
- execution authorization;
- durable execution state;
- evidence truth;
- model/provider credentials.

## Request
A request MUST carry:
- `request_id`
- `operation`
- `payload`

Production authentication, replay protection, authorization and schema validation remain mandatory before execution is enabled.

## Response
A response MUST carry:
- `request_id`
- `status`
- `payload`

## Explicit non-goals
- No privileged shell execution from the phone.
- No direct access to GitHub credentials.
- No bypass of governance or evidence controls.
- No production claim from this skeleton.