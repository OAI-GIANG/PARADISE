import unittest
from datetime import datetime, timedelta, timezone

from paradise_kernel import (
    Advisory, Authority, ChangeRequest, Evidence, Execution, GateResult,
    Kernel, State,
)


class ParadiseKernelAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.kernel = Kernel(trusted_evidence_sources=frozenset({"sensor"}))
        self.authority = Authority(
            authority_id="A1", subject="alice", scope=frozenset({"doc:1"}),
            actions=frozenset({"read"}), issuer="governance",
            valid_from=self.now - timedelta(minutes=1),
            valid_until=self.now + timedelta(minutes=5), contexts=frozenset({"ctx"}), provenance="gov:A1",
        )

    def test_authority_escalation_denied(self):
        result, auth = self.kernel.authorize(self.authority, "alice", "write", "doc:1", "ctx", self.now)
        self.assertEqual(result, GateResult.DENY)
        self.assertIsNone(auth)

    def test_forged_evidence_denied(self):
        evidence = Evidence("E1", "alice", "doc:1", "sensor", self.now, "src:E1", "forged", "VERIFIED")
        self.assertEqual(self.kernel.verify_evidence(evidence, "alice", "doc:1"), GateResult.BLOCKED)

    def test_valid_evidence_requires_integrity_binding(self):
        draft = Evidence("E2", "alice", "doc:1", "sensor", self.now, "src:E2", "", "VERIFIED")
        valid = Evidence("E2", "alice", "doc:1", "sensor", self.now, "src:E2", draft.expected_integrity(), "VERIFIED")
        self.assertEqual(self.kernel.verify_evidence(valid, "alice", "doc:1"), GateResult.ALLOW)

    def test_stale_authority_denied_at_execution(self):
        expired = Authority(
            **{**self.authority.__dict__, "valid_until": self.now - timedelta(seconds=1)}
        )
        result, auth = self.kernel.authorize(expired, "alice", "read", "doc:1", "ctx", self.now)
        self.assertEqual(result, GateResult.DENY)
        self.assertIsNone(auth)

    def test_stale_state_conflicts(self):
        state = State("doc:1", "v1", 4)
        result, new_state = self.kernel.transition(state, 3, "v2")
        self.assertEqual(result, GateResult.CONFLICT)
        self.assertIsNone(new_state)

    def test_replay_non_idempotent_denied(self):
        _, auth = self.kernel.authorize(self.authority, "alice", "read", "doc:1", "ctx", self.now)
        execution = Execution("E1", "read", "alice", "doc:1", 1, auth, False)
        self.assertEqual(self.kernel.execute_external(execution, self.now), GateResult.ALLOW)
        self.assertEqual(self.kernel.execute_external(execution, self.now), GateResult.DENY)

    def test_advisory_cannot_authorize(self):
        advisory = Advisory("AD1", "execute write")
        self.assertEqual(self.kernel.advisory_to_authorization(advisory), GateResult.DENY)

    def test_evidence_cannot_authorize(self):
        evidence = Evidence("E3", "alice", "doc:1", "sensor", self.now, "src:E3", "x", "VERIFIED")
        self.assertEqual(self.kernel.evidence_to_authorization(evidence), GateResult.DENY)

    def test_unknown_is_not_allow(self):
        self.assertEqual(self.kernel.evaluate_unknown(), GateResult.UNKNOWN)
        self.assertNotEqual(self.kernel.evaluate_unknown(), GateResult.ALLOW)

    def test_unauthorized_self_modification_is_denied(self):
        change = ChangeRequest("C1", "component", "component", frozenset({"policy"}), frozenset())
        self.assertEqual(self.kernel.change_allowed(change), GateResult.DENY)

    def test_bounded_change_allowed(self):
        change = ChangeRequest("C2", "operator", "component", frozenset({"policy"}), frozenset({"policy", "config"}))
        self.assertEqual(self.kernel.change_allowed(change), GateResult.ALLOW)

    def test_external_effect_requires_fresh_bound_authorization(self):
        _, auth = self.kernel.authorize(self.authority, "alice", "read", "doc:1", "ctx", self.now)
        execution = Execution("E2", "write", "alice", "doc:1", 1, auth, False)
        self.assertEqual(self.kernel.execute_external(execution, self.now), GateResult.DENY)

    def test_authority_context_binding(self):
        result, auth = self.kernel.authorize(self.authority, "alice", "read", "doc:1", "wrong-context", self.now)
        self.assertEqual(result, GateResult.DENY)
        self.assertIsNone(auth)

    def test_authorization_expires_before_side_effect(self):
        _, auth = self.kernel.authorize(self.authority, "alice", "read", "doc:1", "ctx", self.now)
        execution = Execution("E3", "read", "alice", "doc:1", 1, auth, False)
        self.assertEqual(self.kernel.execute_external(execution, self.now + timedelta(minutes=6)), GateResult.DENY)

    def test_conflicting_verified_evidence_blocks(self):
        base = Evidence("E4", "alice", "doc:1", "sensor", self.now, "src:E4", "", "VERIFIED", "ALLOW")
        a = Evidence("E4", "alice", "doc:1", "sensor", self.now, "src:E4", base.expected_integrity(), "VERIFIED", "ALLOW")
        base2 = Evidence("E5", "alice", "doc:1", "sensor", self.now, "src:E5", "", "VERIFIED", "DENY")
        b = Evidence("E5", "alice", "doc:1", "sensor", self.now, "src:E5", base2.expected_integrity(), "VERIFIED", "DENY")
        self.assertEqual(self.kernel.evaluate_evidence([a, b], "alice", "doc:1"), GateResult.CONFLICT)

    def test_self_modification_requires_independent_authority_subject(self):
        change = ChangeRequest("C3", "component", "component", frozenset({"policy"}), frozenset({"policy"}), "component", True)
        self.assertEqual(self.kernel.change_allowed(change), GateResult.DENY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
