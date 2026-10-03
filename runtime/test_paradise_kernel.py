import unittest
from datetime import datetime, timedelta, timezone

from paradise_kernel import Advisory, Authority, ChangeRequest, Evidence, Execution, GateResult, Kernel, State


class ParadiseSemanticV1Tests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.kernel = Kernel(trusted_evidence_sources=frozenset({"sensor"}))
        self.authority = Authority(
            authority_id="A1", subject="alice", scope=frozenset({"doc:1"}),
            actions=frozenset({"read"}), issuer="governance",
            valid_from=self.now - timedelta(minutes=1),
            valid_until=self.now + timedelta(minutes=5), contexts=frozenset({"ctx"}),
            provenance="gov:A1",
        )

    def auth(self):
        result, auth = self.kernel.authorize(self.authority, "alice", "read", "doc:1", "ctx", self.now)
        self.assertEqual(result, GateResult.ALLOW)
        return auth

    # I01-I04 authority
    def test_i01_explicit_authority_binding(self):
        self.assertEqual(self.auth().scope, "doc:1")
        self.assertEqual(self.auth().context, "ctx")
        self.assertEqual(self.auth().authority_id, "A1")

    def test_i02_no_authority_escalation(self):
        result, auth = self.kernel.authorize(self.authority, "alice", "write", "doc:1", "ctx", self.now)
        self.assertEqual(result, GateResult.DENY)
        self.assertIsNone(auth)

    def test_i03_temporal_authority_validity(self):
        expired = Authority(**{**self.authority.__dict__, "valid_until": self.now - timedelta(seconds=1)})
        result, auth = self.kernel.authorize(expired, "alice", "read", "doc:1", "ctx", self.now)
        self.assertEqual(result, GateResult.DENY)
        self.assertIsNone(auth)

    def test_i04_exact_context_action_scope_binding(self):
        for action, scope, context in [("read", "doc:2", "ctx"), ("read", "doc:1", "wrong"), ("write", "doc:1", "ctx")]:
            result, auth = self.kernel.authorize(self.authority, "alice", action, scope, context, self.now)
            self.assertEqual(result, GateResult.DENY)
            self.assertIsNone(auth)

    # I05-I07 policy
    def test_i05_gate_has_explicit_outcomes(self):
        self.assertEqual(self.kernel.evaluate_unknown(), GateResult.UNKNOWN)
        self.assertIn(self.kernel.evaluate_unknown(), set(GateResult))

    def test_i06_unknown_is_not_allow(self):
        self.assertNotEqual(self.kernel.evaluate_unknown(), GateResult.ALLOW)
        self.assertEqual(self.kernel.evaluate_evidence([], "alice", "doc:1"), GateResult.UNKNOWN)

    def test_i07_conflict_is_explicit(self):
        a0 = Evidence("E1", "alice", "doc:1", "sensor", self.now, "src:E1", "", "VERIFIED", "ALLOW")
        a = Evidence("E1", "alice", "doc:1", "sensor", self.now, "src:E1", a0.expected_integrity(), "VERIFIED", "ALLOW")
        b0 = Evidence("E2", "alice", "doc:1", "sensor", self.now, "src:E2", "", "VERIFIED", "DENY")
        b = Evidence("E2", "alice", "doc:1", "sensor", self.now, "src:E2", b0.expected_integrity(), "VERIFIED", "DENY")
        self.assertEqual(self.kernel.evaluate_evidence([a, b], "alice", "doc:1"), GateResult.CONFLICT)

    # I08-I10 state/lifecycle
    def test_i08_versioned_state_transition(self):
        result, state = self.kernel.transition(State("doc:1", "v1", 4), 4, "v2")
        self.assertEqual(result, GateResult.ALLOW)
        self.assertEqual(state.version, 5)

    def test_i09_stale_state_rejected(self):
        result, state = self.kernel.transition(State("doc:1", "v1", 4), 3, "v2")
        self.assertEqual(result, GateResult.CONFLICT)
        self.assertIsNone(state)

    def test_i10_invalid_lifecycle_rejected(self):
        result, state = self.kernel.transition(State("doc:1", "v1", 4, "CLOSED"), 4, "v2")
        self.assertEqual(result, GateResult.BLOCKED)
        self.assertIsNone(state)

    # I11-I13 evidence
    def test_i11_integrity_and_provenance_required(self):
        draft = Evidence("E3", "alice", "doc:1", "sensor", self.now, "src:E3", "", "VERIFIED")
        valid = Evidence("E3", "alice", "doc:1", "sensor", self.now, "src:E3", draft.expected_integrity(), "VERIFIED")
        self.assertEqual(self.kernel.verify_evidence(valid, "alice", "doc:1"), GateResult.ALLOW)
        forged = Evidence("E4", "alice", "doc:1", "sensor", self.now, "src:E4", "forged", "VERIFIED")
        self.assertEqual(self.kernel.verify_evidence(forged, "alice", "doc:1"), GateResult.BLOCKED)

    def test_i12_evidence_is_not_authority(self):
        evidence = Evidence("E5", "alice", "doc:1", "sensor", self.now, "src:E5", "x", "VERIFIED")
        self.assertEqual(self.kernel.evidence_to_authorization(evidence), GateResult.DENY)

    def test_i13_context_bound_verification(self):
        draft = Evidence("E6", "alice", "doc:1", "sensor", self.now, "src:E6", "", "VERIFIED")
        valid = Evidence("E6", "alice", "doc:1", "sensor", self.now, "src:E6", draft.expected_integrity(), "VERIFIED")
        self.assertEqual(self.kernel.verify_evidence(valid, "alice", "doc:1"), GateResult.ALLOW)
        self.assertEqual(self.kernel.verify_evidence(valid, "bob", "doc:1"), GateResult.BLOCKED)
        self.assertEqual(self.kernel.verify_evidence(valid, "alice", "doc:2"), GateResult.BLOCKED)

    # I14-I16 execution/replay
    def test_i14_unique_execution_identity_and_witness(self):
        auth = self.auth()
        execution = Execution("X1", "read", "alice", "doc:1", 1, auth, False, "witness:X1")
        self.assertEqual(self.kernel.execute_external(execution, self.now), GateResult.ALLOW)
        missing = Execution("X2", "read", "alice", "doc:1", 1, auth, False, "")
        self.assertEqual(self.kernel.execute_external(missing, self.now), GateResult.BLOCKED)

    def test_i15_replay_safety(self):
        auth = self.auth()
        execution = Execution("X3", "read", "alice", "doc:1", 1, auth, False, "witness:X3")
        self.assertEqual(self.kernel.execute_external(execution, self.now), GateResult.ALLOW)
        self.assertEqual(self.kernel.execute_external(execution, self.now), GateResult.DENY)
        idem = Execution("X4", "read", "alice", "doc:1", 1, auth, True, "witness:X4")
        self.assertEqual(self.kernel.execute_external(idem, self.now), GateResult.ALLOW)
        self.assertEqual(self.kernel.execute_external(idem, self.now), GateResult.ALLOW)

    def test_i16_fresh_side_effect_authorization(self):
        auth = self.auth()
        mismatched = Execution("X5", "write", "alice", "doc:1", 1, auth, False, "witness:X5")
        self.assertEqual(self.kernel.execute_external(mismatched, self.now), GateResult.DENY)
        expired_time = self.now + timedelta(minutes=6)
        expired = Execution("X6", "read", "alice", "doc:1", 1, auth, False, "witness:X6")
        self.assertEqual(self.kernel.execute_external(expired, expired_time), GateResult.DENY)

    # I17 cognition
    def test_i17_cognition_is_advisory(self):
        self.assertEqual(self.kernel.advisory_to_authorization(Advisory("AD1", "execute")), GateResult.DENY)

    # I18-I19 bounded change
    def test_i18_bounded_change_and_independent_authority(self):
        good = ChangeRequest("C1", "operator", "component", frozenset({"policy"}), frozenset({"policy"}), "governance", True, True, "rollback:C1")
        self.assertEqual(self.kernel.change_allowed(good), GateResult.ALLOW)
        expanded = ChangeRequest("C2", "operator", "component", frozenset({"policy", "secret"}), frozenset({"policy"}), "governance", False, True, "rollback:C2")
        self.assertEqual(self.kernel.change_allowed(expanded), GateResult.DENY)
        self_change = ChangeRequest("C3", "component", "component", frozenset({"policy"}), frozenset({"policy"}), "component", True, True, "rollback:C3")
        self.assertEqual(self.kernel.change_allowed(self_change), GateResult.DENY)

    def test_i19_recovery_bound_change(self):
        missing = ChangeRequest("C4", "operator", "component", frozenset({"policy"}), frozenset({"policy"}), "governance", False, True, "")
        self.assertEqual(self.kernel.change_allowed(missing), GateResult.DENY)
        optional = ChangeRequest("C5", "operator", "component", frozenset({"policy"}), frozenset({"policy"}), "governance", False, False, "")
        self.assertEqual(self.kernel.change_allowed(optional), GateResult.ALLOW)

    # K1-K8 regression intent
    def test_k1_k8_regression_suite(self):
        self.assertEqual(self.kernel.authorize(self.authority, "alice", "write", "doc:1", "ctx", self.now)[0], GateResult.DENY)
        self.assertEqual(self.kernel.advisory_to_authorization(Advisory("AD2", "write")), GateResult.DENY)
        evidence = Evidence("E7", "alice", "doc:1", "sensor", self.now, "src:E7", "x", "VERIFIED")
        self.assertEqual(self.kernel.evidence_to_authorization(evidence), GateResult.DENY)
        self.assertEqual(self.kernel.evaluate_unknown(), GateResult.UNKNOWN)
        self.assertEqual(self.kernel.transition(State("doc:1", "v1", 2), 1, "v2")[0], GateResult.CONFLICT)


if __name__ == "__main__":
    unittest.main(verbosity=2)