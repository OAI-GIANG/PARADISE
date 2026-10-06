# Phone Bridge V1

Status: SKELETON / NOT PRODUCTION.

Server-side skeleton for a phone client bridge.

## Scope
- Define a narrow phone-to-runtime transport boundary.
- Keep authentication, authorization, execution, and evidence owned by the server/runtime.
- Do not expose internal runtime state directly to the phone client.

## Files
- `bridge.py` — minimal bridge entry point skeleton.
- `protocol.md` — transport contract draft.

## Safety
This skeleton performs no privileged operation and is not a production endpoint.