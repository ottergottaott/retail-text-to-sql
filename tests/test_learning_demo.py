from retail.learning_demo import run_demo
from retail.model import Decision
from retail.config import Settings


class ControlledPlanner:
    def decide(self, context, remaining_seconds):
        if not any(t['id']=='lantern-catalogue' for t in context['trios']):
            return Decision(action='clarify',text='What does Lantern KPI mean?'), {}
        if not context['tools']:
            return Decision(action='query',sql='SELECT COUNT(*) AS products FROM products'), {}
        return Decision(action='answer',text='Lantern KPI is 2 authorized catalogue products [q1].'), {}


def test_reviewed_demo_records_actual_agent_change_without_live_claims():
    result=run_demo(Settings(_env_file=None),ControlledPlanner(),model_source='controlled')
    assert result['before']['outcome']=='clarification'
    assert result['failed_review']['published'] is False
    assert result['approved_review']['status']=='published'
    assert result['after']['query_oracle_passed'] is True
    assert result['after']['retrieved_candidate'] is True
    assert result['live_bigquery_verified'] is False
    assert result['model_source']=='controlled'
    assert result['indexing']['status']=='not_requested'
