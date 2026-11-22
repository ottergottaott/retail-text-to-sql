"""Isolated, reproducible review loop. Fixture SQL is never BigQuery evidence."""
import tempfile
from pathlib import Path
from .agent import Agent
from .analytics import Analytics
from .governance import Governance
from .knowledge import Knowledge
from .security import Principal
from .store import Store

QUESTION='Calculate our Lantern KPI for my authorized catalogue. Return exactly one row with a column named products containing the KPI value, and explain the definition.'
TRIO={'id':'lantern-catalogue','question':QUESTION,'tags':['lantern','kpi','catalogue','products'],
    'sql':'SELECT COUNT(*) AS products FROM products',
    'report':'Lantern KPI is our synthetic business definition: count authorized catalogue products, not sold items. It is not a standard industry KPI.',
    'scope':'shared','schema_version':'safe-v1','origin':'synthetic operator-reviewed learning demonstration'}


def run_demo(config, model, model_source, embedder=None):
    if model_source not in {'controlled','live'}:
        raise ValueError('Explicit model source required.')
    with tempfile.TemporaryDirectory(prefix='retail-learning-demo-') as directory:
        cfg=config.model_copy(update={'database_url':f'sqlite:///{directory}/demo.db',
            'log_path':str(Path(directory)/'events.jsonl'),'embedding_provider':'none',
            'langfuse_public_key':'','langfuse_secret_key':'','max_queries':2,'max_model_calls':4})
        fixture=cfg.model_copy(update={'retail_mode':'fixture'})
        store=Store(cfg.database_url)
        try:
            agent=Agent(cfg,store,model=model,review_model=model,analytics=Analytics(fixture))
            knowledge=Knowledge(store,embedder)
            agent.knowledge=knowledge
            initial_index=knowledge.index() if embedder else None
            principal=Principal('alice',(1,2))
            def execute():
                events=[]
                response=agent.chat(principal,QUESTION,sink=events.append)
                return response, {'outcome':response['outcome'],'answer':response['answer'],
                    'query_oracle_passed':response['outcome']=='succeeded' and any(
                        e['mode']=='fixture' and not e['truncated'] and e['rows']==[{'products':2}]
                        for e in response['evidence']),
                    'evidence':response['evidence'],
                    'retrieved_candidate':any(t['id']==TRIO['id'] for e in events
                        if e['stage']=='context_versions' for t in e['trios']),
                    'model_usage':[e for e in events if e['stage']=='model_usage']}
            raw,before=execute()
            governance=Governance(fixture,store)
            feedback=governance.feedback(principal,raw['conversation_id'],raw['trace_id'],
                'Our Lantern KPI means the authorized catalogue product count, not sold units.','correction')
            candidate=governance.candidate('alice',feedback,TRIO)
            failed=governance.review(candidate,'demo-operator',[
                {'name':'deliberately incorrect oracle','user':'alice','expected_rows':[{'products':999}]}])
            assert not any(t['id']==TRIO['id'] for t in knowledge.published())
            approved=governance.review(candidate,'demo-operator',[
                {'name':'authorized Alice catalogue','user':'alice','expected_rows':[{'products':2}]},
                {'name':'authorized Bob catalogue','user':'bob','expected_rows':[{'products':1}]}])
            indexing=knowledge.index() if embedder else {'status':'not_requested'}
            _,after=execute()  # New conversation: no feedback leakage through history.
            return {'model_source':model_source,'data_mode':'fixture','live_bigquery_verified':False,
                'question':QUESTION,'before':before,'failed_review':failed,'approved_review':approved,
                'initial_indexing':initial_index,'indexing':indexing,'after':after,
                'limitations':['One synthetic business definition, one run per condition; not general accuracy.',
                    'Exact SQL oracle does not establish report faithfulness; human review pending.',
                    'No live application data or shared knowledge was modified.']}
        finally:
            store.engine.dispose()
