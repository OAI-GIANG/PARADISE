# STT HOME RUNTIME CONTRACT V1

Status: DESIGN + IMPLEMENTED BASELINE
Scope: first inhabitable local runtime slice of PARADISE.

## Canonical responsibilities
- Identity and home binding belong to PARADISE.
- Persistent continuity belongs to the home store.
- Memory carries trust and provenance metadata.
- Mission and task lifecycle are separate from execution mechanics.
- Evidence is produced from recorded events and hashed payloads.
- Provider/model is an adapter and may be replaced.

## Safety boundaries
- Local-safe mode performs no external network call.
- The UI does not expose arbitrary external side effects.
- Model output cannot grant authorization.
- Evidence cannot grant authorization.
- Task lifecycle rejects invalid transitions.

## Inhabitation gate
A local V1 runtime is considered inhabitable only when:
1. identity persists across restart;
2. session messages persist;
3. memory persists with provenance/trust;
4. mission persists;
5. task lifecycle is bounded;
6. each meaningful operation emits evidence;
7. HTTP API serves the home;
8. an independent restart E2E passes;
9. semantic regression remains green.

This contract does not itself declare PRODUCTION.