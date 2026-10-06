from dataclasses import dataclass
from enum import Enum
from time import time
from typing import Any, Callable, Mapping, Protocol
from uuid import UUID

PROTOCOL_VERSION='1.1'
MAX_CLOCK_SKEW_SECONDS=300
class BridgeError(Exception):
    def __init__(self,code,message,retryable=False): super().__init__(message); self.code=code; self.message=message; self.retryable=retryable
    def as_dict(self,request_id): return {'request_id':request_id,'status':'REJECTED','error':{'code':self.code,'message':self.message,'retryable':self.retryable}}
class GateOutcome(str,Enum): ALLOW='ALLOW'; DENY='DENY'; BLOCKED='BLOCKED'; CONFLICT='CONFLICT'; UNKNOWN='UNKNOWN'
@dataclass(frozen=True)
class BridgeRequest: protocol_version:str; request_id:str; operation:str; timestamp:int; nonce:str; payload:dict[str,Any]
@dataclass(frozen=True)
class AuthenticatedPrincipal: principal_id:str; credential_reference:str
@dataclass(frozen=True)
class AuthorizationDecision: authorization_id:str; outcome:GateOutcome
@dataclass(frozen=True)
class ExecutionIdentity: execution_id:str
@dataclass(frozen=True)
class EvidenceCorrelation: evidence_id:str
@dataclass(frozen=True)
class GovernedExecutionSubmission: request_id:str; authorization_id:str; execution:ExecutionIdentity; evidence:EvidenceCorrelation|None=None
@dataclass(frozen=True)
class BridgeResponse: request_id:str; status:str; payload:dict[str,Any]|None=None; error:dict[str,Any]|None=None
AuthVerifier=Callable[[str],AuthenticatedPrincipal|None]
AuthorizationHandoff=Callable[[BridgeRequest,AuthenticatedPrincipal],AuthorizationDecision]
ExecutionSubmitter=Callable[[GovernedExecutionSubmission],ExecutionIdentity]
class ReplayStore(Protocol):
    def claim(self,key:str,seen_at:float)->bool: ...
    def prune(self,cutoff:float)->None: ...

class InMemoryReplayStore:
    '''Test/dev adapter; production must use a persistent atomic implementation.'''
    def __init__(self): self._seen={}; self._lock=__import__('threading').RLock()
    def claim(self,key,seen_at):
        with self._lock:
            if key in self._seen: return False
            self._seen[key]=seen_at; return True
    def prune(self,cutoff):
        with self._lock: self._seen={k:v for k,v in self._seen.items() if v>=cutoff}

class RuntimeStoreReplayAdapter:
    '''Canonical persistent replay/idempotency adapter backed by RuntimeStore.'''
    def __init__(self,store): self._store=store
    def claim(self,key,seen_at): return self._store.claim_phone_bridge_replay(key,seen_at)
    def prune(self,cutoff): self._store.prune_phone_bridge_replay(cutoff)

class ReplayGuard:
    '''Replay enforcement only; persistence remains owned by the canonical store.'''
    def __init__(self,store:ReplayStore,clock:Callable[[],float]=time,window_seconds:int=MAX_CLOCK_SKEW_SECONDS): self._store=store; self._clock=clock; self._window=window_seconds
    def check_and_record(self,request):
        now=self._clock()
        if abs(now-request.timestamp)>self._window: raise BridgeError('REQUEST_EXPIRED','Request outside acceptance window')
        key=f'{request.request_id}:{request.nonce}'
        try:
            if not self._store.claim(key,now): raise BridgeError('REQUEST_REPLAYED','Request replayed')
            self._store.prune(now-self._window)
        except BridgeError: raise
        except Exception as exc: raise BridgeError('REPLAY_STORE_UNAVAILABLE','Replay protection unavailable',True) from exc
def parse_request(raw:Mapping[str,Any])->BridgeRequest:
    required=('protocol_version','request_id','operation','timestamp','nonce','payload')
    if any(k not in raw for k in required) or raw['protocol_version']!=PROTOCOL_VERSION: raise BridgeError('REQUEST_SCHEMA_INVALID','Request schema invalid')
    try: UUID(str(raw['request_id'])); timestamp=int(raw['timestamp'])
    except (ValueError,TypeError): raise BridgeError('REQUEST_SCHEMA_INVALID','Request schema invalid') from None
    if not isinstance(raw['operation'],str) or not raw['operation'] or not isinstance(raw['nonce'],str) or not raw['nonce'] or not isinstance(raw['payload'],dict): raise BridgeError('REQUEST_SCHEMA_INVALID','Request schema invalid')
    return BridgeRequest(PROTOCOL_VERSION,str(raw['request_id']),raw['operation'],timestamp,raw['nonce'],raw['payload'])
def handle(raw_request,*,credential,verify_auth,authorize,replay_guard,submit_execution=None):
    request_id = str(raw_request.get('request_id','')) if isinstance(raw_request,Mapping) else ''
    try:
        request = parse_request(raw_request)
        principal=verify_auth(credential)
        if principal is None: raise BridgeError('AUTHENTICATION_FAILED','Request authentication failed')
        replay_guard.check_and_record(request); decision=authorize(request,principal)
        if decision.outcome is not GateOutcome.ALLOW: raise BridgeError(f'AUTHORIZATION_{decision.outcome.value}',f'Request authorization {decision.outcome.value.lower()}',decision.outcome is GateOutcome.UNKNOWN)
        if submit_execution is None: raise BridgeError('EXECUTION_SUBMISSION_REJECTED','Execution submission unavailable',True)
        execution=submit_execution(GovernedExecutionSubmission(request.request_id,decision.authorization_id,ExecutionIdentity('pending')))
        return BridgeResponse(request.request_id,'SUBMITTED',{'authorization_id':decision.authorization_id,'execution_id':execution.execution_id,'principal_id':principal.principal_id})
    except BridgeError as exc:
        return BridgeResponse(request_id,'REJECTED',error=exc.as_dict(request_id)['error'])
    except Exception:
        return BridgeResponse(request_id,'REJECTED',error={'code':'INTERNAL_ERROR','message':'Request rejected','retryable':False})
def safe_error(request_id,code,retryable=False):
    allowed={'AUTHENTICATION_FAILED','REQUEST_SCHEMA_INVALID','REQUEST_EXPIRED','REQUEST_REPLAYED','REPLAY_STORE_UNAVAILABLE','OPERATION_NOT_ALLOWED','AUTHORIZATION_DENY','AUTHORIZATION_BLOCKED','AUTHORIZATION_CONFLICT','AUTHORIZATION_UNKNOWN','GOVERNANCE_UNAVAILABLE','RUNTIME_UNAVAILABLE','EXECUTION_SUBMISSION_REJECTED','INTERNAL_ERROR'}
    if code not in allowed: code='INTERNAL_ERROR'
    return BridgeResponse(request_id,'REJECTED',error={'code':code,'message':'Request rejected','retryable':retryable})
if __name__=='__main__': raise SystemExit('Phone Bridge V1.1 is transport-independent; no server is started.')
