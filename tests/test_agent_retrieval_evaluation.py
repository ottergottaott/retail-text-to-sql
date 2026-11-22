from retail.config import Settings
from retail.model import Decision
from retail.agent_retrieval_evaluation import run_ablation


class Model:
    def decide(self, context, remaining_seconds):
        if not context["tools"]:
            return Decision(action="query", sql="SELECT SUM(sale_price) AS revenue FROM order_items WHERE status='Complete'"), {"usage_source":"controlled"}
        return Decision(action="answer", text="Completed-item revenue is 210. Check product mix before changing pricing."), {"usage_source":"controlled"}


def test_ablation_executes_real_scoped_fixture_sql_and_labels_mixed_evidence():
    report = run_ablation(Settings(_env_file=None, embedding_provider="none"), Model(), None,
        model_source="controlled", cases=[{"id":"sum", "question":"Calculate completed revenue", "expected_rows":[{"revenue":210.0}]}])
    assert report["data_mode"] == "fixture"
    assert report["model_source"] == "controlled"
    assert report["modes"]["none"]["cases"][0]["query_oracle_passed"] is True
    assert report["modes"]["lexical"]["cases"][0]["query_oracle_passed"] is True
    assert report["modes"]["hybrid"]["status"] == "untested"
    assert report["report_faithfulness"] == "pending_human_review"
    assert report["live_bigquery_verified"] is False


def test_plausible_answer_without_matching_query_evidence_is_not_a_pass():
    report = run_ablation(Settings(_env_file=None, embedding_provider="none"), Model(), None,
        model_source="controlled", cases=[{"id":"wrong", "question":"Calculate completed revenue", "expected_rows":[{"revenue":999.0}]}])
    assert report["modes"]["none"]["cases"][0]["query_oracle_passed"] is False
