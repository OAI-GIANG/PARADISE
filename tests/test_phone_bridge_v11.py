from datetime import datetime,timezone
from uuid import uuid4
from phone_bridge.bridge import *
now=int(datetime.now(timezone.utc).timestamp())
def req(op='echo',nonce=None): return BridgeRequest(PROTOCOL_VERSION,str(uuid4()),op,now,nonce or str(uuid4()),{})
def auth(token): return AuthenticatedPrincipal('p1','cred-ref') if token=='valid' else None
def decision(outcome,r): return AuthorizationDecision(f'auth-{r.request_id}',outcome)
def submit(s): return ExecutionIdentity(f'exec-{s.request_id}')
def run(r,outcome=GateOutcome.ALLOW,store=None,submitter=submit): return handle(r,credential='valid',verify_auth=auth,authorize=lambda x,_:decision(outcome,x),replay_guard=ReplayGuard(store or InMemoryReplayStore()),submit_execution=submitter)
positive=run(req()); assert positive.status=='SUBMITTED'; assert positive.payload['authorization_id']!=positive.payload['execution_id']
bad=handle(req(),credential='bad',verify_auth=auth,authorize=lambda r,_:decision(GateOutcome.ALLOW,r),replay_guard=ReplayGuard(InMemoryReplayStore()),submit_execution=submit); assert bad.error['code']=='AUTHENTICATION_FAILED'
assert parse_request({'protocol_version':PROTOCOL_VERSION,'request_id':str(uuid4()),'operation':'echo','timestamp':now,'nonce':'n','payload':{}}).operation=='echo'
for outcome in (GateOutcome.DENY,GateOutcome.BLOCKED,GateOutcome.CONFLICT,GateOutcome.UNKNOWN):
    called=[]; result=run(req(),outcome,submitter=lambda s:called.append(s) or submit(s)); assert result.status=='REJECTED' and result.error['code']==f'AUTHORIZATION_{outcome.value}' and not called
store=InMemoryReplayStore(); r=req(nonce='persistent'); assert run(r,store=store).status=='SUBMITTED'; assert run(r,store=store).error['code']=='REQUEST_REPLAYED'
class BrokenStore:
    def contains(self,key): raise RuntimeError('down')
    def record(self,key,seen_at): raise RuntimeError('down')
assert run(req(),store=BrokenStore()).error['code']=='REPLAY_STORE_UNAVAILABLE'
assert run(req('shell.exec'),GateOutcome.DENY).error['code']=='AUTHORIZATION_DENY'
print('V11_RECONCILIATION=PASS'); print('N_AUTH=PASS'); print('N_SCHEMA=PASS'); print('N_DENY=PASS'); print('N_BLOCKED=PASS'); print('N_CONFLICT=PASS'); print('N_UNKNOWN=PASS'); print('N_REPLAY_SHARED_STORE=PASS'); print('N_REPLAY_STORE_FAILURE_FAIL_CLOSED=PASS'); print('N_IDENTITY_SEPARATION=PASS'); print('N_SHELL_AUTHZ=PASS')
