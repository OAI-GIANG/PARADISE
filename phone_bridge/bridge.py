"""Phone Bridge V1.1 protocol boundary.

Transport-independent implementation. Authentication and authorization are injected
so the bridge does not become an authority or credential store.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Any, Callable, Mapping
from uuid import UUID

PROTOCOL_VERSION = "1.1"
MAX_CLOCK_SKEW_SECONDS = 300


class BridgeError(Exception):
    """Safe, stable bridge error."""

    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def as_dict(self, request_id: str) -> dict[str, Any]:
        return {
            "request_id": request_id,
            "status": "REJECTED",
            "error": {"code": self.code, "message": self.message, "retryable": self.retryable},
        }


@dataclass(frozen=True)
class BridgeRequest:
    protocol_version: str
    request_id: str
    operation: str
    timestamp: int
    nonce: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    principal_id: str
    credential_reference: str


@dataclass(frozen=True)
class BridgeResponse:
    request_id: str
    status: str
    payload: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


AuthVerifier = Callable[[str], AuthenticatedPrincipal | None]
AuthorizationHandoff = Callable[[BridgeRequest, AuthenticatedPrincipal], bool]


def parse_request(raw: Mapping[str, Any]) -> BridgeRequest:
    required = ("protocol_version", "request_id", "operation", "timestamp", "nonce", "payload")
    if any(key not in raw for key in required):
        raise BridgeError("REQUEST_SCHEMA_INVALID", "Request schema invalid")
    if raw["protocol_version"] != PROTOCOL_VERSION:
        raise BridgeError("REQUEST_SCHEMA_INVALID", "Unsupported protocol version")
    try:
        UUID(str(raw["request_id"]))
        timestamp = int(raw["timestamp"])
    except (ValueError, TypeError):
        raise BridgeError("REQUEST_SCHEMA_INVALID", "Request schema invalid") from None
    if not isinstance(raw["operation"], str) or not raw["operation"]:
        raise BridgeError("REQUEST_SCHEMA_INVALID", "Request schema invalid")
    if not isinstance(raw["nonce"], str) or not raw["nonce"]:
        raise BridgeError("REQUEST_SCHEMA_INVALID", "Request schema invalid")
    if not isinstance(raw["payload"], dict):
        raise BridgeError("REQUEST_SCHEMA_INVALID", "Request schema invalid")
    return BridgeRequest(PROTOCOL_VERSION, str(raw["request_id"]), raw["operation"], timestamp, raw["nonce"], raw["payload"])


class ReplayGuard:
    """In-memory replay guard; production durability belongs outside the bridge."""

    def __init__(self, clock: Callable[[], float] = time, window_seconds: int = MAX_CLOCK_SKEW_SECONDS) -> None:
        self._clock = clock
        self._window = window_seconds
        self._seen: dict[str, float] = {}

    def check_and_record(self, request: BridgeRequest) -> None:
        now = self._clock()
        if abs(now - request.timestamp) > self._window:
            raise BridgeError("REQUEST_EXPIRED", "Request outside acceptance window")
        key = f"{request.request_id}:{request.nonce}"
        if key in self._seen:
            raise BridgeError("REQUEST_REPLAYED", "Request replayed")
        self._seen[key] = now
        cutoff = now - self._window
        self._seen = {k: v for k, v in self._seen.items() if v >= cutoff}


def handle(
    request: BridgeRequest,
    *,
    credential: str,
    verify_auth: AuthVerifier,
    authorize: AuthorizationHandoff,
    replay_guard: ReplayGuard,
) -> BridgeResponse:
    """Authenticate, validate replay, hand off authorization; never execute."""
    try:
        principal = verify_auth(credential)
        if principal is None:
            raise BridgeError("AUTHENTICATION_FAILED", "Request authentication failed")
        replay_guard.check_and_record(request)
        if not authorize(request, principal):
            raise BridgeError("AUTHORIZATION_DENIED", "Request authorization denied")
        return BridgeResponse(
            request.request_id,
            "SUBMITTED",
            payload={"authorization": "APPROVED", "principal_id": principal.principal_id},
        )
    except BridgeError as exc:
        return BridgeResponse(request.request_id, "REJECTED", error=exc.as_dict(request.request_id)["error"])


def safe_error(request_id: str, code: str, retryable: bool = False) -> BridgeResponse:
    allowed = {
        "AUTHENTICATION_FAILED", "REQUEST_SCHEMA_INVALID", "REQUEST_EXPIRED",
        "REQUEST_REPLAYED", "OPERATION_NOT_ALLOWED", "AUTHORIZATION_DENIED",
        "GOVERNANCE_UNAVAILABLE", "RUNTIME_UNAVAILABLE", "EXECUTION_REJECTED", "INTERNAL_ERROR",
    }
    if code not in allowed:
        code = "INTERNAL_ERROR"
    return BridgeResponse(request_id, "REJECTED", error={"code": code, "message": "Request rejected", "retryable": retryable})


if __name__ == "__main__":
    raise SystemExit("Phone Bridge V1.1 is transport-independent; no server is started.")
