"""Phone Bridge V1 skeleton."""

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class BridgeRequest:
    request_id: str
    operation: str
    payload: dict[str, Any]

@dataclass(frozen=True)
class BridgeResponse:
    request_id: str
    status: str
    payload: dict[str, Any]

def handle(request: BridgeRequest) -> BridgeResponse:
    """Reject execution until the production protocol is implemented."""
    return BridgeResponse(request_id=request.request_id, status="NOT_IMPLEMENTED", payload={"operation": request.operation})

if __name__ == "__main__":
    raise SystemExit("Phone Bridge V1 is a skeleton; no server is started.")