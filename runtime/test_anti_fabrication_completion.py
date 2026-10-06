import unittest
from datetime import datetime, timezone

from paradise_kernel import Evidence, GateResult, Kernel


class AntiFabricationCompletionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.kernel = Kernel(trusted_evidence_sources=frozenset({"paradise.runtime"}))

    def make_evidence(self, status="UNVERIFIED", claim="model execution completed", integrity=None):
        e = Evidence(
            "E-AF-1", "task-1", "runtime", "paradise.runtime", self.now,
            "commit:tree:local", integrity or "", status, claim
        )
        if integrity == "AUTO":
            e = Evidence(
                e.evidence_id, e.subject, e.scope, e.source, e.captured_at,
                e.provenance, e.expected_integrity(), e.verification_status, e.claim
            )
        return e

    def test_unverified_evidence_never_allows_verification(self):
        e = self.make_evidence(status="UNVERIFIED", integrity="AUTO")
        self.assertEqual(
            self.kernel.verify_evidence(e, "task-1", "runtime"),
            GateResult.BLOCKED,
        )

    def test_verified_status_with_forged_integrity_is_blocked(self):
        e = self.make_evidence(status="VERIFIED", integrity="forged")
        self.assertEqual(
            self.kernel.verify_evidence(e, "task-1", "runtime"),
            GateResult.BLOCKED,
        )

    def test_admission_does_not_equal_verification(self):
        e = self.make_evidence(status="UNVERIFIED", integrity="AUTO")
        self.assertEqual(
            self.kernel.evidence_admission_status(e, "task-1", "runtime"),
            GateResult.ALLOW,
        )
        self.assertEqual(
            self.kernel.verify_evidence(e, "task-1", "runtime"),
            GateResult.BLOCKED,
        )


if __name__ == "__main__":
    unittest.main()
