from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import sqlite3


from phone_bridge.bridge import *
from runtime.paradise.store import RuntimeStore

now = int(datetime.now(timezone.utc).timestamp())

def raw(op="echo", request_id=None, nonce=None):
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id or str(uuid4()),
        "operation": op,
        "timestamp": now,
        "nonce": nonce or str(uuid4()),
        "payload": {},
    }

def auth(token):
    return AuthenticatedPrincipal("p1", "cred-ref") if token == "valid" else None

def decision(outcome, request):
    return AuthorizationDecision(f"auth-{request.request_id}", outcome)

def submit(s):
    return ExecutionIdentity(f"exec-{s.request_id}")

def run(raw_request, outcome=GateOutcome.ALLOW, store=None, submitter=submit):
    return handle(
        raw_request,
        credential="valid",
        verify_auth=auth,
        authorize=lambda r, _: decision(outcome, r),
        replay_guard=ReplayGuard(store or InMemoryReplayStore()),
        submit_execution=submitter,
    )

# H-01 canonical raw-ingress
positive = run(raw())
assert positive.status == "SUBMITTED"
assert positive.payload["authorization_id"] != positive.payload["execution_id"]

bad_schema = raw()
del bad_schema["nonce"]
assert run(bad_schema).error["code"] == "REQUEST_SCHEMA_INVALID"

bad_auth = handle(raw(), credential="bad", verify_auth=auth,
                  authorize=lambda r, _: decision(GateOutcome.ALLOW, r),
                  replay_guard=ReplayGuard(InMemoryReplayStore()),
                  submit_execution=submit)
assert bad_auth.error["code"] == "AUTHENTICATION_FAILED"

# Fail closed on all non-ALLOW decisions.
for outcome in (GateOutcome.DENY, GateOutcome.BLOCKED, GateOutcome.CONFLICT, GateOutcome.UNKNOWN):
    called = []
    result = run(raw(), outcome, submitter=lambda s: called.append(s) or submit(s))
    assert result.status == "REJECTED"
    assert result.error["code"] == f"AUTHORIZATION_{outcome.value}"
    assert not called

# Privileged operation remains governance-controlled.
assert run(raw(op="shell.exec"), GateOutcome.DENY).error["code"] == "AUTHORIZATION_DENY"
# In-process duplicate
store = InMemoryReplayStore()
same = raw(request_id=str(uuid4()), nonce="duplicate")
assert run(same, store=store).status == "SUBMITTED"
assert run(same, store=store).error["code"] == "REQUEST_REPLAYED"

# Replay-store failure is fail-closed.
class BrokenStore:
    def claim(self, key, seen_at):
        raise RuntimeError("down")
    def prune(self, cutoff):
        raise RuntimeError("down")

assert run(raw(), store=BrokenStore()).error["code"] == "REPLAY_STORE_UNAVAILABLE"

# H-02 canonical persistent adapter + restart
with TemporaryDirectory() as td:
    db = Path(td) / "runtime.db"
    persistent = RuntimeStore(db)
    adapter1 = RuntimeStoreReplayAdapter(persistent)
    persisted = raw(request_id=str(uuid4()), nonce="restart")
    assert run(persisted, store=adapter1).status == "SUBMITTED"

    # New store/adapter instance simulates process restart.
    persistent2 = RuntimeStore(db)
    adapter2 = RuntimeStoreReplayAdapter(persistent2)
    assert run(persisted, store=adapter2).error["code"] == "REQUEST_REPLAYED"

# H-02 atomic concurrency: exactly one winner.
with TemporaryDirectory() as td:
    db = Path(td) / "runtime.db"
    winner_key = str(uuid4())
    winner = raw(request_id=winner_key, nonce="concurrent")

    def attempt():
        local_store = RuntimeStore(db)
        return RuntimeStoreReplayAdapter(local_store)

    adapters = [attempt() for _ in range(16)]
    def claim(adapter):
        try:
            return adapter.claim(f"{winner['request_id']}:{winner['nonce']}", float(now))
        except sqlite3.Error:
            return False

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(claim, adapters))
    assert sum(1 for x in results if x) == 1, results

# No second DurableExecution / Evidence authority introduced by bridge module.
bridge_text = Path(__file__).parents[1].joinpath("phone_bridge", "bridge.py").read_text(encoding="utf-8-sig")
assert "class DurableExecution" not in bridge_text
assert "class Evidence" not in bridge_text or "EvidenceCorrelation" in bridge_text

store_text = Path(__file__).parents[1].joinpath("runtime", "paradise", "store.py").read_text(encoding="utf-8-sig")
assert "CREATE TABLE IF NOT EXISTS phone_bridge_replay" not in store_text
assert "INSERT OR IGNORE INTO replay_records" in store_text

print("H01_RAW_INGRESS=PASS")
print("N_SCHEMA_FAIL_CLOSED=PASS")
print("N_AUTH=PASS")
print("N_DENY=PASS")
print("N_BLOCKED=PASS")
print("N_CONFLICT=PASS")
print("N_UNKNOWN=PASS")
print("N_DUPLICATE=PASS")
print("N_RESTART=PASS")
print("N_CONCURRENCY_EXACTLY_ONE=PASS")
print("N_REPLAY_STORE_FAILURE_FAIL_CLOSED=PASS")
print("N_IDENTITY_SEPARATION=PASS")
print("N_NO_DURABLE_EXECUTION_DUPLICATE=PASS")
print("N_NO_EVIDENCE_AUTHORITY_DUPLICATE=PASS")
print("V11_BLOCKER_IMPLEMENTATION_TEST=PASS")
