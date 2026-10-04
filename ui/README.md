# PARADISE Web UI

The UI is a static, same-origin browser client for the bounded PARADISE runtime.

- `/healthz` is public for liveness.
- `/v1/status` and `/v1/tasks` use the existing Bearer authentication contract.
- The API token is entered by the user and kept only in `sessionStorage`.
- No provider credentials or server secrets are embedded in the UI.

Deployment should serve `ui/` as the nginx document root while proxying `/healthz` and `/v1/` to the existing loopback runtime on `127.0.0.1:8787`.
