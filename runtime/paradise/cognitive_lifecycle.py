"""Canonical Memory -> Experience -> Evaluation -> Pattern -> Distillation -> Consolidation pipeline."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from dataclasses import dataclass
from typing import Any

def _now(): return datetime.now(timezone.utc).isoformat()
def _id(prefix,*parts): return prefix+"-"+sha256("|".join(parts).encode()).hexdigest()[:24]
@dataclass(frozen=True)
class LifecycleResult:
    experience_id:str; evaluation_id:str; pattern_id:str|None; distillation_id:str|None; consolidation_id:str|None; model_memory_id:str|None
class CognitiveLifecycle:
    """Sole semantic owner for post-memory cognitive transitions; RuntimeStore owns persistence."""
    def __init__(self,store,source_commit,source_tree_sha,environment): self.store=store; self.source_commit=source_commit; self.source_tree_sha=source_tree_sha; self.environment=environment
    def ingest_memory(self,task_id,memory,evidence_refs):
        claim=str(memory.get("claim") or "").strip()
        if not claim: raise ValueError("memory claim is required")
        key=str(memory.get("normalized_key") or " ".join(claim.lower().split())[:240])
        eid=_id("EXP",task_id,str(memory["memory_id"]))
        exp={"experience_id":eid,"task_id":task_id,"memory_id":memory["memory_id"],"normalized_key":key,"claim":claim,"source":memory.get("source_actor","unknown"),"authority":memory.get("authority","unknown"),"trust_status":memory.get("trust_status","UNVERIFIED"),"evidence_refs":list(evidence_refs),"provenance":{"source_commit":self.source_commit,"source_tree_sha":self.source_tree_sha,"environment":self.environment},"observed_at":_now()}
        self.store.save_experience(exp,exp["observed_at"])
        result="ACCEPT" if evidence_refs and memory.get("trust_status")=="VERIFIED" else "UNCERTAIN"
        vid=_id("EVAL",eid,result); ev={"evaluation_id":vid,"experience_id":eid,"task_id":task_id,"result":result,"method":"canonical-memory-evidence-v1","evaluator":"paradise-runtime","evidence_refs":list(evidence_refs),"authority_effect":"NONE","evaluated_at":_now()}
        self.store.save_evaluation(ev,ev["evaluated_at"])
        accepted=[e for e in self.store.list_experiences(key) if e.get("experience_id")!=eid and e.get("trust_status")=="VERIFIED" and e.get("evidence_refs")]
        pattern_id=distillation_id=consolidation_id=model_memory_id=None
        if result=="ACCEPT" and accepted:
            ids=sorted({e["experience_id"] for e in accepted}|{eid}); pattern_id=_id("PAT",key,*ids); refs=sorted({r for x in ids for r in self.store.experience_by_id(x).get("evidence_refs",[])})
            pat={"pattern_id":pattern_id,"normalized_key":key,"experience_ids":ids,"support_count":len(ids),"claim":claim,"evidence_refs":refs,"status":"CANDIDATE","created_at":_now()}; self.store.save_pattern(pat,pat["created_at"])
            distillation_id=_id("DST",pattern_id); dst={"distillation_id":distillation_id,"pattern_id":pattern_id,"normalized_key":key,"canonical_claim":claim,"support_count":len(ids),"evidence_refs":refs,"authority":"NONE","status":"DERIVED","created_at":_now()}; self.store.save_distillation(dst,dst["created_at"])
            consolidation_id=_id("CON",distillation_id); con={"consolidation_id":consolidation_id,"distillation_id":distillation_id,"normalized_key":key,"canonical_claim":claim,"status":"CONSOLIDATED","authority":"NONE","evidence_refs":refs,"source_experience_ids":ids,"created_at":_now()}; self.store.save_consolidation(con,con["created_at"])
            model_memory_id=_id("MMEM",key,consolidation_id); mm={"model_memory_id":model_memory_id,"normalized_key":key,"content":claim,"consolidation_id":consolidation_id,"evidence_refs":refs,"authority":"NONE","trust_status":"DERIVED_NOT_VERIFIED","source_experience_ids":ids,"created_at":_now()}; self.store.save_model_memory(mm,mm["created_at"])
            self.store.set_cognitive_state(key,{"state_id":_id("STATE",key),"normalized_key":key,"active_model_memory_id":model_memory_id,"consolidation_id":consolidation_id,"authority":"NONE","updated_at":mm["created_at"]})
        return LifecycleResult(eid,vid,pattern_id,distillation_id,consolidation_id,model_memory_id)
