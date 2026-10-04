# PARADISE Runnable Runtime V0.1.0

This directory contains the first runnable application boundary for PARADISE. It wraps the existing semantic kernel without introducing new semantic primitives or invariants.

## Runtime surface

- `GET /healthz` — unauthenticated liveness check.
- `GET /v1/status` — authenticated runtime identity/status.
- `POST /v1/tasks` — authenticated bounded task submission.
- `GET /v1/tasks/<task_id>` — authenticated durable task state.

The initial runtime operation is deliberately bounded to `echo`. Arbitrary shell/process execution is not exposed by the HTTP surface.

## State

SQLite is used for durable runtime metadata, tasks, idempotency keys, and audit events. The database path is controlled by `PARADISE_DATA` and should live on persistent storage in deployment.

## Authentication

Production mode requires `PARADISE_API_TOKEN`. Anonymous access is disabled by default. `PARADISE_ALLOW_ANONYMOUS=1` is intended only for isolated local testing.

## Run locally

From repository root:

```powershell
$env:PYTHONPATH = "runtime"
$env:PARADISE_API_TOKEN = "replace-me"
python -m paradise.server
```

Default endpoint: `http://127.0.0.1:8787`.

## Smoke test

```powershell
curl.exe http://127.0.0.1:8787/healthz
curl.exe -H "Authorization: Bearer replace-me" http://127.0.0.1:8787/v1/status
curl.exe -X POST http://127.0.0.1:8787/v1/tasks `
  -H "Authorization: Bearer replace-me" `
  -H "Content-Type: application/json" `
  -d '{"operation":"echo","payload":{"message":"hello"},"idempotency_key":"demo-1"}'
```

## Deployment

The runtime is standard-library-only and can run directly under Python 3.11+. For a production deployment, bind it behind a TLS-terminating reverse proxy, provide a strong API token through the secret store, mount persistent storage for `PARADISE_DATA`, and bind the deployment to the exact source commit/tree identity through `PARADISE_COMMIT` and `PARADISE_TREE_SHA`.

Do not place tokens or database files in Git.
