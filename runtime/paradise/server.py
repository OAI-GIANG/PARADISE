from __future__ import annotations
import json
import os
import secrets
import socket
import sys
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from projects.LOVE.stt_love.task_contract import TaskContract, TaskContractError
from projects.LOVE.stt_love.durable_execution import DurableExecution, DurableExecutionError
from .cognitive import CognitiveService
from phone_bridge.bridge import (
    AuthenticatedPrincipal, BridgeResponse, ExecutionIdentity, GateOutcome,
    ReplayGuard, RuntimeStoreReplayAdapter, handle as handle_phone_bridge,
)

VERSION = "0.1.1"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "runtime" / "data" / "paradise.sqlite3"

def utc_now() -> str: return datetime.now(timezone.utc).isoformat()
def env_bool(name: str, default: bool = False) -> bool:
    value=os.getenv(name); return default if value is None else value.lower() in {"1","true","yes","on"}

class RuntimeConfig:
    def __init__(self) -> None:
        self.host=os.getenv("PARADISE_HOST","127.0.0.1"); self.port=int(os.getenv("PARADISE_PORT","8787"))
        self.api_token=os.getenv("PARADISE_API_TOKEN",""); self.allow_anonymous=env_bool("PARADISE_ALLOW_ANONYMOUS",False)
        self.data_path=Path(os.getenv("PARADISE_DATA",str(DEFAULT_DATA))).resolve(); self.commit=os.getenv("PARADISE_COMMIT","unknown")
        self.tree=os.getenv("PARADISE_TREE_SHA","unknown"); self.environment=os.getenv("PARADISE_ENV","local")
    def validate(self) -> None:
        if self.port<0 or self.port>65535: raise ValueError("PARADISE_PORT must be 0..65535")
        if not self.allow_anonymous and not self.api_token: raise ValueError("PARADISE_API_TOKEN is required unless anonymous mode is explicitly enabled")

class ParadiseApplication:
    """PARADISE runtime. TaskContract owns intent; Submission owns submitted work; DurableExecution owns execution state."""
    def __init__(self, config: RuntimeConfig):
        config.validate(); self.config=config
        from .store import RuntimeStore
        self.store=RuntimeStore(config.data_path)
        self.durable=DurableExecution(self.store)
        self.cognitive=CognitiveService(self.store,config.commit,config.tree,config.environment)
        self._bridge_submit_lock=threading.RLock()
        self.durable.recover_orphans()
        self.store.set_meta("version",VERSION); self.store.set_meta("commit",config.commit); self.store.set_meta("tree",config.tree); self.store.set_meta("started_at",utc_now())

    def authenticate(self, token: str|None)->bool:
        if self.config.allow_anonymous: return True
        return bool(token and self.config.api_token and secrets.compare_digest(token,self.config.api_token))

    def bridge_principal(self, token: str|None) -> AuthenticatedPrincipal|None:
        if not self.authenticate(token):
            return None
        return AuthenticatedPrincipal("paradise-client", "bearer-token")

    def handle_phone_bridge(self, raw: dict[str, Any], token: str|None) -> BridgeResponse:
        principal = self.bridge_principal(token)
        if principal is None:
            request_id = str(raw.get("request_id", "")) if isinstance(raw, dict) else ""
            return BridgeResponse(request_id, "REJECTED", error={"code":"AUTHENTICATION_FAILED","message":"Request rejected","retryable":False})

        def verify_auth(_credential: str):
            return principal

        def authorize(request, _principal):
            if request.operation != "echo":
                return __import__("phone_bridge.bridge", fromlist=["AuthorizationDecision"]).AuthorizationDecision(f"AUTH-{request.request_id}", GateOutcome.DENY)
            try:
                authorization_id = self.cognitive.authorize(request.request_id, request.operation)
                return __import__("phone_bridge.bridge", fromlist=["AuthorizationDecision"]).AuthorizationDecision(authorization_id, GateOutcome.ALLOW)
            except PermissionError:
                return __import__("phone_bridge.bridge", fromlist=["AuthorizationDecision"]).AuthorizationDecision(f"AUTH-{request.request_id}", GateOutcome.DENY)
            except Exception:
                return __import__("phone_bridge.bridge", fromlist=["AuthorizationDecision"]).AuthorizationDecision(f"AUTH-{request.request_id}", GateOutcome.UNKNOWN)

        def submit_execution(submission):
            with self._bridge_submit_lock:
                body={"task_id": submission.request_id, "operation": raw["operation"], "payload": raw["payload"], "idempotency_key": submission.request_id}
                task=self.submit(body)
                if task.get("state") != "COMPLETED":
                    raise RuntimeError("canonical durable execution did not complete")
                evidence_id = (task.get("result") or {}).get("evidence_id")
                return ExecutionIdentity(str(task.get("id") or submission.request_id), evidence_id)

        return handle_phone_bridge(
            raw, credential=token or "", verify_auth=verify_auth, authorize=authorize,
            replay_guard=ReplayGuard(RuntimeStoreReplayAdapter(self.store)),
            submit_execution=submit_execution,
        )

    def status(self)->dict[str,Any]:
        return {"name":"PARADISE","version":VERSION,"status":"RUNNING","host":socket.gethostname(),"commit":self.config.commit,"tree":self.config.tree,"environment":self.config.environment,"data_path":str(self.config.data_path),"started_at":self.store.get_meta("started_at"),"operations":["echo"],"integration":"LOVE_COGNITIVE_SUBSTRATE"}

    def execute(self, task_id:str, operation:str, payload:dict[str,Any])->dict[str,Any]:
        request=__import__("runtime.paradise.contracts",fromlist=["CognitiveRequest"]).CognitiveRequest(task_id,operation,payload,self.config.commit,self.config.tree,self.config.environment)
        advice=self.cognitive.advise(request); self.cognitive.authorize(task_id,operation); output=self.cognitive.invoke_model(task_id,operation,payload)
        evidence=self.cognitive.emit_evidence(task_id,"MODEL_EXECUTION","model execution completed")
        replay=self.cognitive.emit_replay(task_id,"MODEL_EXECUTION",{"operation":operation,"output":output,"evidence_id":evidence["evidence_id"]})
        memory=self.cognitive.observe_memory(task_id,payload,evidence["evidence_id"])
        result={**output,"task_id":task_id,"cognitive":{"advice":advice.recommendation,"memory_ids":list(advice.memory_ids),"evidence_ids":list(advice.evidence_ids)},"evidence_id":evidence["evidence_id"],"replay_id":replay["replay_id"]}
        if memory: result.update({"memory_id":memory["memory_id"],"memory_key":memory["normalized_key"],"memory_scope":memory["scope"]})
        return result

    def submit(self, body:dict[str,Any])->dict[str,Any]:
        task_id=str(body.get("task_id") or f"TASK-{uuid.uuid4().hex}")
        operation=str(body.get("operation") or "").strip().lower(); payload=body.get("payload")
        idem=str(body.get("idempotency_key") or task_id)
        if not operation: raise ValueError("operation is required")
        if not isinstance(payload,dict): raise ValueError("payload must be an object")
        if len(idem)>200: raise ValueError("idempotency_key too long")
        contract=TaskContract(goal=operation,metadata={"operation":operation,"payload":payload}).validate()
        submission=contract.submit(submission_id=task_id,idempotency_key=idem,execution_mode="SYNC")
        task,reused=self.durable.enqueue_submission(submission)
        if reused and task.get("state") in {"COMPLETED","FAILED","CANCELLED","TIMED_OUT","ABORTED_BY_KILL"}: return task
        self.store.add_event(task_id,"SUBMISSION_ACCEPTED",submission.to_dict(),utc_now())
        claimed=self.durable.claim(task_id)
        if claimed is None: return self.store.get_task(task_id) or {}
        metadata=claimed.get("metadata") or {}
        operation=str(metadata.get("operation") or operation); payload=dict(metadata.get("payload") or payload)
        try:
            if operation!="echo": raise ValueError("unsupported operation; allowed operations: echo")
            result=self.execute(task_id,operation,payload)
            final=self.durable.finalize(task_id,int(claimed["fence_token"]),"COMPLETED",report=result)
            self.store.add_event(task_id,"EXECUTION_COMPLETED",result,utc_now())
            return final
        except Exception as exc:
            final=self.durable.finalize(task_id,int(claimed["fence_token"]),"FAILED",error={"type":type(exc).__name__,"message":str(exc)})
            self.store.add_event(task_id,"EXECUTION_FAILED",{"error":str(exc)},utc_now())
            return final

class Handler(BaseHTTPRequestHandler):
    server_version="PARADISE/0.1"
    @property
    def app(self)->ParadiseApplication: return self.server.app # type: ignore[attr-defined]
    def _json(self,status:int,payload:dict[str,Any])->None:
        encoded=json.dumps(payload,ensure_ascii=False,sort_keys=True).encode("utf-8"); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(encoded))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(encoded)
    def _authorized(self)->bool:
        auth=self.headers.get("Authorization",""); return self.app.authenticate(auth[7:] if auth.startswith("Bearer ") else None)
    def _body(self)->dict[str,Any]:
        length=int(self.headers.get("Content-Length","0"))
        if length<=0 or length>256*1024: raise ValueError("request body must be 1..262144 bytes")
        value=json.loads(self.rfile.read(length).decode("utf-8"));
        if not isinstance(value,dict): raise ValueError("JSON body must be an object")
        return value
    def do_GET(self)->None:
        if self.path=="/healthz": self._json(HTTPStatus.OK,{"status":"ok","version":VERSION}); return
        if not self._authorized(): self._json(HTTPStatus.UNAUTHORIZED,{"error":"unauthorized"}); return
        if self.path=="/v1/status": self._json(HTTPStatus.OK,self.app.status()); return
        if self.path == "/v1/bridge":
            self._json(HTTPStatus.METHOD_NOT_ALLOWED,{"error":"POST required"}); return
        if self.path.startswith("/v1/tasks/"):
            task=self.app.store.get_task(self.path.rsplit("/",1)[-1]); self._json(HTTPStatus.NOT_FOUND,{"error":"task not found"} if task is None else task); return
        self._json(HTTPStatus.NOT_FOUND,{"error":"not found"})
    def do_POST(self)->None:
        if not self._authorized(): self._json(HTTPStatus.UNAUTHORIZED,{"error":"unauthorized"}); return
        if self.path=="/v1/bridge":
            try: result=self.app.handle_phone_bridge(self._body(), self.headers.get("Authorization","")[7:] if self.headers.get("Authorization","").startswith("Bearer ") else None)
            except (ValueError,json.JSONDecodeError) as exc: self._json(HTTPStatus.BAD_REQUEST,{"error":str(exc)}); return
            status=HTTPStatus.OK if result.status=="SUBMITTED" else HTTPStatus.UNAUTHORIZED if result.error and result.error.get("code")=="AUTHENTICATION_FAILED" else HTTPStatus.UNPROCESSABLE_ENTITY
            self._json(status,{"request_id":result.request_id,"status":result.status,"payload":result.payload,"error":result.error}); return
        if self.path!="/v1/tasks": self._json(HTTPStatus.NOT_FOUND,{"error":"not found"}); return
        try: task=self.app.submit(self._body())
        except (ValueError,json.JSONDecodeError,TaskContractError,DurableExecutionError) as exc: self._json(HTTPStatus.BAD_REQUEST,{"error":str(exc)}); return
        status=HTTPStatus.OK if task.get("state")=="COMPLETED" else HTTPStatus.UNPROCESSABLE_ENTITY; self._json(status,task)
    def log_message(self,format:str,*args:Any)->None: sys.stderr.write("PARADISE "+(format%args))

def create_server(config:RuntimeConfig|None=None)->ThreadingHTTPServer:
    config=config or RuntimeConfig(); app=ParadiseApplication(config); server=ThreadingHTTPServer((config.host,config.port),Handler); server.app=app  # type: ignore[attr-defined]
    return server

def main()->int:
    config=RuntimeConfig(); server=create_server(config); print(f"PARADISE {VERSION} listening on http://{config.host}:{config.port}")
    try: server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt: pass
    finally: server.server_close()
    return 0

if __name__=="__main__": raise SystemExit(main())
