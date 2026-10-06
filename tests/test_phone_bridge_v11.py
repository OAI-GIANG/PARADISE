from datetime import datetime, timezone
from uuid import uuid4
from phone_bridge.bridge import *

now = int(datetime.now(timezone.utc).timestamp())
req = BridgeRequest(PROTOCOL_VERSION, str(uuid4()), "echo", now, "n-1", {})

def auth(token):
    return AuthenticatedPrincipal("p1", "cred-ref") if token == "valid" else None

def allow(request, principal):
    return request.operation == "echo"

g = ReplayGuard()
r = handle(req, credential="valid", verify_auth=auth, authorize=allow, replay_guard=g)
assert r.status == "SUBMITTED"

replay = handle(req, credential="valid", verify_auth=auth, authorize=allow, replay_guard=g)
assert replay.error["code"] == "REQUEST_REPLAYED"

bad_auth = handle(BridgeRequest(PROTOCOL_VERSION, str(uuid4()), "echo", now, "n-2", {}), credential="bad", verify_auth=auth, authorize=allow, replay_guard=ReplayGuard())
assert bad_auth.error["code"] == "AUTHENTICATION_FAILED"

deny = handle(BridgeRequest(PROTOCOL_VERSION, str(uuid4()), "echo", now, "n-3", {}), credential="valid", verify_auth=auth, authorize=lambda *_: False, replay_guard=ReplayGuard())
assert deny.error["code"] == "AUTHORIZATION_DENIED"

expired = handle(BridgeRequest(PROTOCOL_VERSION, str(uuid4()), "echo", now-9999, "n-4", {}), credential="valid", verify_auth=auth, authorize=allow, replay_guard=ReplayGuard())
assert expired.error["code"] == "REQUEST_EXPIRED"

shell = BridgeRequest(PROTOCOL_VERSION, str(uuid4()), "shell.exec", now, "n-5", {"cmd": "whoami"})
shell_result = handle(shell, credential="valid", verify_auth=auth, authorize=lambda *_: False, replay_guard=ReplayGuard())
assert shell_result.error["code"] == "AUTHORIZATION_DENIED"

print("V11_REGRESSION=PASS")
print("N01_AUTH=PASS")
print("N04_EXPIRED=PASS")
print("N05_REPLAY=PASS")
print("N09_AUTHZ_DENY=PASS")
print("N10_SHELL_NO_EXECUTION=PASS")
