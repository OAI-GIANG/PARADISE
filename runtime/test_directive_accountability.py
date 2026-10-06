import unittest
from datetime import datetime, timedelta, timezone
from paradise_kernel import Authority, Evidence, Execution, GateResult, Kernel

class DirectiveAccountabilityTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.kernel = Kernel(trusted_evidence_sources=frozenset({"sensor"}))
        self.authority = Authority("AUTH-D1","alice",frozenset({"doc:1"}),frozenset({"write"}),"governance",self.now-timedelta(minutes=1),self.now+timedelta(minutes=10),frozenset({"ctx"}),"ACTIVE","gov:D1")
        result, self.auth = self.kernel.authorize(self.authority,"alice","write","doc:1","ctx",self.now)
        self.assertEqual(result,GateResult.ALLOW)
        draft=Evidence("E-D1","alice","doc:1","sensor",self.now,"src:D1","","VERIFIED","accepted")
        self.evidence=Evidence("E-D1","alice","doc:1","sensor",self.now,"src:D1",draft.expected_integrity(),"VERIFIED","accepted")
        self.directive={"directive_id":"D1","issuer":"governance","responsible_actor":"alice","action":"write","scope":"doc:1","context":"ctx","authority_id":"AUTH-D1","issued_at":self.now-timedelta(minutes=1),"due_at":self.now+timedelta(minutes=5),"acceptance_criteria":"accepted","status":"ACTIVE","provenance":"gov:D1"}
    def execution(self,**kw):
        v={"execution_id":"X-D1","action":"write","subject":"alice","scope":"doc:1","input_version":1,"authorization":self.auth,"idempotent":False,"result_witness":"w:X-D1"}; v.update(kw); return Execution(**v)
    def check(self,d,e,expected,reason,at=None):
        result,actual=self.kernel.evaluate_directive_compliance(d,e,[self.evidence],at or self.now); self.assertEqual((result,actual),(expected,reason))
    def test_compliant_directive(self): self.check(self.directive,self.execution(),GateResult.ALLOW,"COMPLIANT")
    def test_actor_mismatch_is_denied(self): self.check(self.directive,self.execution(subject="bob"),GateResult.DENY,"ACTOR_MISMATCH")
    def test_scope_deviation_is_denied(self): self.check(self.directive,self.execution(scope="doc:2"),GateResult.DENY,"SCOPE_OR_ACTION_DEVIATION")
    def test_context_mismatch_is_denied(self):
        bad=dict(self.directive); bad["context"]="other"; result,reason=self.kernel.evaluate_directive_compliance(bad,self.execution(),[self.evidence],self.now); self.assertEqual((result,reason),(GateResult.DENY,"CONTEXT_MISMATCH"))
    def test_late_directive_is_denied(self): self.check(self.directive,self.execution(),GateResult.DENY,"LATE_OR_EXPIRED",self.now+timedelta(minutes=6))
    def test_missing_witness_is_blocked(self): self.check(self.directive,self.execution(result_witness=""),GateResult.BLOCKED,"NON_EXECUTION_OR_MISSING_WITNESS")
    def test_unverified_evidence_is_blocked(self):
        u=Evidence(self.evidence.evidence_id,self.evidence.subject,self.evidence.scope,self.evidence.source,self.evidence.captured_at,self.evidence.provenance,self.evidence.integrity,"UNVERIFIED",self.evidence.claim); result,reason=self.kernel.evaluate_directive_compliance(self.directive,self.execution(),[u],self.now); self.assertEqual((result,reason),(GateResult.BLOCKED,"EVIDENCE_NOT_VERIFIED"))
    def test_conflicting_evidence_is_conflict(self):
        d=Evidence("E-D2","alice","doc:1","sensor",self.now,"src:D2","","VERIFIED","rejected"); c=Evidence("E-D2","alice","doc:1","sensor",self.now,"src:D2",d.expected_integrity(),"VERIFIED","rejected"); result,reason=self.kernel.evaluate_directive_compliance(self.directive,self.execution(),[self.evidence,c],self.now); self.assertEqual((result,reason),(GateResult.CONFLICT,"CONTRADICTORY_EVIDENCE"))
    def test_missing_required_field_is_unknown(self):
        bad=dict(self.directive); bad.pop("responsible_actor"); result,reason=self.kernel.evaluate_directive_compliance(bad,self.execution(),[self.evidence],self.now); self.assertEqual((result,reason),(GateResult.UNKNOWN,"MISSING_DIRECTIVE_FIELD"))

if __name__ == "__main__": unittest.main()

