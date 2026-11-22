"""An unsupported draft must not become the saved analytical answer."""
import pytest
from retail.agent import Agent
from retail.analytics import Analytics
from retail.config import Settings
from retail.model import Decision, ModelError
from retail.security import principal_for
from retail.store import Store


@pytest.mark.parametrize('failure',[False, True])
def test_live_review_precedes_last_analysis_and_save(tmp_path, failure):
    c=Settings(_env_file=None, retail_mode='live', embedding_provider='none',
               database_url=f'sqlite:///{tmp_path}/state.db',log_path=str(tmp_path/'events.jsonl'))
    store=Store(c.database_url); alice=principal_for('alice',c)
    class Planner:
        def __init__(self): self.calls=0; self.review_context=None
        def decide(self,context,remaining_seconds):
            self.calls+=1
            if self.calls==1:return Decision(action='query',sql='SELECT COUNT(*) AS n FROM products'),{}
            if self.calls==2:return Decision(action='save_report',title='Reviewed products'),{}
            if self.calls==3:return Decision(action='answer',text='The 2 products are discounted.'),{}
            self.review_context=context
            if failure:raise ModelError('Model unavailable; no reviewed report.')
            return Decision(action='answer',text='There are 2 authorized products [q1]. Discounts were not measured.\n\n### Action items\nProposed: query realized prices before assessing discounts.'),{}
    planner=Planner()
    fixture_analytics=Analytics(c.model_copy(update={'retail_mode':'fixture'}))
    result=Agent(c,store,model=planner,analytics=fixture_analytics).chat(alice,'Count my products, analyze and save')
    assert planner.calls==4
    assert planner.review_context['execution_scope']['enforcement']=='executor_bound_views'
    assert planner.review_context['execution_scope']['products']==[1,2]
    assert planner.review_context['report_review']['draft']=='The 2 products are discounted.'
    assert planner.review_context['tools'][0]['result']['rows']==[{'n':2}]
    if failure:
        assert result['outcome']=='dependency_error'
        assert not store.reports(alice)
        assert 'last_analysis' not in store.get('conversation','alice',result['conversation_id'])['body']
    else:
        assert result['outcome']=='succeeded'
        saved=store.reports(alice)
        assert len(saved)==1
        assert 'products are discounted' not in saved[0]['body']['content']
        assert 'Discounts were not measured' in saved[0]['body']['content']


def test_review_budget_exhaustion_never_saves_draft(tmp_path):
    c=Settings(_env_file=None, retail_mode='live', embedding_provider='none',max_model_calls=2,
               database_url=f'sqlite:///{tmp_path}/state.db',log_path=str(tmp_path/'events.jsonl'))
    store=Store(c.database_url); alice=principal_for('alice',c)
    class Planner:
        calls=0
        def decide(self,context,remaining_seconds):
            self.calls+=1
            if self.calls==1:return Decision(action='query',sql='SELECT COUNT(*) AS n FROM products'),{}
            return Decision(action='answer',text='There are 2 products.'),{}
    planner=Planner()
    result=Agent(c,store,model=planner,analytics=Analytics(c.model_copy(update={'retail_mode':'fixture'}))).chat(alice,'Count products')
    assert planner.calls==2
    assert result['outcome']=='budget_exhausted'
    assert not store.reports(alice)
    assert 'last_analysis' not in store.get('conversation','alice',result['conversation_id'])['body']


def test_provider_schema_requires_answer_content():
    from retail.deepinfra import decision_schema
    schema=decision_schema()
    assert 'text' in schema['required']
    conditional=next(rule for rule in schema['allOf'] if rule['if']['properties']['action']['const']=='answer')
    assert conditional['then']['properties']['text']['minLength']==1


def test_shared_decision_schema_remains_google_sdk_compatible():
    from google.genai import types
    types.Schema.model_validate(Decision.model_json_schema())


def test_dedicated_reviewer_receives_draft_and_supplies_saved_content(tmp_path):
    c=Settings(_env_file=None,retail_mode='live',embedding_provider='none',
        database_url=f'sqlite:///{tmp_path}/state.db',log_path=str(tmp_path/'events.jsonl'))
    store=Store(c.database_url);alice=principal_for('alice',c)
    class Planner:
        calls=0
        def decide(self,context,remaining_seconds):
            self.calls+=1
            if self.calls==1:return Decision(action='query',sql='SELECT COUNT(*) AS n FROM products'),{}
            if self.calls==2:return Decision(action='save_report',title='Reviewed'),{}
            return Decision(action='answer',text='Draft'),{}
    class Reviewer:
        calls=0
        def decide(self,context,remaining_seconds):
            self.calls+=1
            assert context['report_review']['draft']=='Draft'
            assert remaining_seconds>0
            return Decision(action='answer',text='2 products [q1]. Discounts not measured.'),{}
    planner=Planner();reviewer=Reviewer()
    result=Agent(c,store,model=planner,review_model=reviewer,
        analytics=Analytics(c.model_copy(update={'retail_mode':'fixture'}))).chat(alice,'Count and save products')
    assert result['outcome']=='succeeded'
    assert planner.calls==3 and reviewer.calls==1
    assert 'Discounts not measured' in store.reports(alice)[0]['body']['content']
