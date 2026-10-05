from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from paradise.server import ParadiseApplication, RuntimeConfig

class Phase2CognitiveLifecycleTests(unittest.TestCase):
    def cfg(self,path):
        c=RuntimeConfig(); c.api_token='secret'; c.data_path=path; return c
    def test_memory_to_consolidation_to_model_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=ParadiseApplication(self.cfg(Path(tmp)/'state.sqlite3'))
            payload=lambda mid:{'message':'learn','memory':{'memory_id':mid,'claim':'user requires evidence first','normalized_key':'evidence-first','trust':'VERIFIED','scope':'conversation'}}
            a=app.submit({'operation':'echo','payload':payload('M1'),'idempotency_key':'p2-1'})
            b=app.submit({'operation':'echo','payload':payload('M2'),'idempotency_key':'p2-2'})
            self.assertEqual(a['status'],'SUCCEEDED'); self.assertEqual(b['status'],'SUCCEEDED')
            self.assertEqual(len(app.store.list_experiences('evidence-first')),2)
            self.assertEqual(len(app.store.list_evaluations()),2)
            self.assertGreaterEqual(len(app.store.list_patterns()),1)
            self.assertGreaterEqual(len(app.store.list_distillations()),1)
            self.assertGreaterEqual(len(app.store.list_consolidations()),1)
            model=app.store.load_model_memory('evidence-first')
            self.assertEqual(len(model),1)
            self.assertEqual(model[0]['trust_status'],'DERIVED_NOT_VERIFIED')
            state=app.store.get_cognitive_state('evidence-first')
            self.assertEqual(state['active_model_memory_id'],model[0]['model_memory_id'])
    def test_unverified_memory_does_not_consolidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=ParadiseApplication(self.cfg(Path(tmp)/'state.sqlite3'))
            for i in range(2):
                t=app.submit({'operation':'echo','payload':{'message':'x','memory':{'memory_id':f'U{i}','claim':'unverified claim','normalized_key':'u-key','scope':'conversation'}},'idempotency_key':f'u-{i}'})
                self.assertEqual(t['status'],'SUCCEEDED')
            self.assertEqual(app.store.list_consolidations(),[])
            self.assertEqual(app.store.load_model_memory('u-key'),[])
    def test_model_facing_memory_reaches_reasoning_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=ParadiseApplication(self.cfg(Path(tmp)/'state.sqlite3'))
            for i in range(2): app.submit({'operation':'echo','payload':{'message':'x','memory':{'memory_id':f'F{i}','claim':'model should receive derived context','normalized_key':'model-context','trust':'VERIFIED'}},'idempotency_key':f'f-{i}'})
            advice=app.cognitive.advise(__import__('runtime.paradise.contracts',fromlist=['CognitiveRequest']).CognitiveRequest('Q','echo',{'memory_key':'model-context','memory_scope':'conversation'},'c','t','local'))
            self.assertTrue(advice.model_memory_ids)
            self.assertEqual(advice.model_memory_context[0]['authority'],'none')

    def test_model_gateway_receives_model_facing_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=ParadiseApplication(self.cfg(Path(tmp)/'state.sqlite3'))
            for i in range(2): app.submit({'operation':'echo','payload':{'message':'x','memory':{'memory_id':f'G{i}','claim':'gateway context','normalized_key':'gateway-context','trust':'VERIFIED'}},'idempotency_key':f'g-{i}'})
            seen={}
            original=app.cognitive.models.invoke
            def capture(req):
                seen['context']=req.payload.get('_model_memory_context')
                return original(req)
            app.cognitive.models.invoke=capture
            app.submit({'operation':'echo','payload':{'message':'use','memory_key':'gateway-context','memory_scope':'conversation'},'idempotency_key':'g-3'})
            self.assertTrue(seen['context'])
            self.assertEqual(seen['context'][0]['authority'],'none')

    def test_restart_preserves_full_cognitive_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.sqlite3'; app=ParadiseApplication(self.cfg(path))
            for i in range(2): app.submit({'operation':'echo','payload':{'message':'x','memory':{'memory_id':f'R{i}','claim':'restart chain','normalized_key':'restart-chain','trust':'VERIFIED'}},'idempotency_key':f'r-{i}'})
            before=(len(app.store.list_experiences()),len(app.store.list_evaluations()),len(app.store.list_patterns()),len(app.store.list_distillations()),len(app.store.list_consolidations()),len(app.store.load_model_memory('restart-chain')))
            app2=ParadiseApplication(self.cfg(path))
            after=(len(app2.store.list_experiences()),len(app2.store.list_evaluations()),len(app2.store.list_patterns()),len(app2.store.list_distillations()),len(app2.store.list_consolidations()),len(app2.store.load_model_memory('restart-chain')))
            self.assertEqual(before,after)

if __name__=='__main__': unittest.main(verbosity=2)
