# PARADISE — STT HOME

STT Home is the first inhabitable runtime slice of PARADISE.

It is deliberately small, local-first and dependency-free. The home owns:
- STT identity
- persistent sessions and conversation continuity
- memory with provenance/trust
- mission and task lifecycle
- evidence-bound event recording
- provider abstraction

A model/provider is an instrument, not the home.

## Start
From F:\OAI\PARADISE:

    python runtime\stt_home\server.py

Open: http://127.0.0.1:8787

## Optional model provider
By default the home runs in local-safe mode and does not call the network.
For an OpenAI-compatible provider, configure PARADISE_PROVIDER, PARADISE_MODEL_API_KEY, PARADISE_MODEL_NAME and PARADISE_MODEL_BASE_URL at runtime.
Secrets are never stored in PARADISE source files by this component.

## Data
Default database: runtime/stt_home/data/paradise_home.sqlite3
Override with PARADISE_HOME_DATA=<path>.

## API
GET  /api/health
GET  /api/state
GET  /api/events
GET  /api/session/<session_id>
POST /api/session
POST /api/chat
POST /api/memory
POST /api/task
POST /api/task/transition

## Verification
Run:
    python runtime\test_stt_home.py
    python runtime\test_paradise_kernel.py
    python runtime\test_semantic_kernel_contract.py

The final residency claim is evidence-gated.