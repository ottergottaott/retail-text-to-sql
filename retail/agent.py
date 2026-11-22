"""One LangGraph per application; all mutable turn state is invocation-local."""
from .security import scope_snapshot, scope_allowed
import json
import time
import threading
import hashlib
import datetime as dt
from weakref import WeakValueDictionary
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .analytics import Analytics, QueryError, QueryUnavailable, SCHEMA, FUNCTIONS, validate
from sqlglot import exp
from .knowledge import Knowledge
from .model import Decision, FixtureModel, GeminiModel, ModelError
from .security import PolicyError, FORBIDDEN_REQUEST, clean, safe_output
from .telemetry import Trace
from .providers import model_for, embeddings_for


class Turn(TypedDict, total=False):
    principal: object
    conversation: str
    question: str
    context: dict
    decision: Decision
    trace: Trace
    started: float
    calls: int
    queries: int
    repairs: int
    evidence: list
    tools: list
    answer: str
    stop: bool
    management: object
    completed_analysis: bool
    outcome: str
    save_title: str
    draft_answer: str


def table(rows):
    if not rows:
        return "No rows matched the query."
    columns = list(rows[0])
    def cell(v):
        return str(v).replace("|", "\\|").replace("\n", " ") if v is not None else "NULL"
    return "\n".join(["| " + " | ".join(map(cell, columns)) + " |",
        "| " + " | ".join("---" for _ in columns) + " |"] +
        ["| " + " | ".join(cell(r.get(c)) for c in columns) + " |" for r in rows])


def present(rows, preference):
    if preference["format"] == "tables" or not rows:
        return table(rows)
    lines = ["; ".join(f"{column}: {value if value is not None else 'NULL'}" for column, value in row.items()) for row in rows]
    return "\n".join("- " + line for line in lines) if preference["format"] == "bullets" else "\n\n".join(lines)


class Agent:
    def __init__(self, config, store, model=None, analytics=None, review_model=None):
        self.config, self.store = config, store
        self._conversation_locks = WeakValueDictionary()
        self._lock_guard = threading.Lock()
        self.analytics = analytics or Analytics(config)
        self.knowledge = Knowledge(store,
            embeddings_for(config) if config.retail_mode == "live" else None,
            config.retrieval_min_similarity, config.retrieval_lexical_min_similarity)
        self.model = model or model_for(config)
        self.review_model = review_model or self.model
        self.review_model_name = config.deepinfra_model if config.llm_provider == "deepinfra" else config.gemini_model
        if (review_model is None and model is None and config.retail_mode == "live"
                and config.llm_provider == "deepinfra" and config.deepinfra_review_model):
            self.review_model = model_for(config.model_copy(update={"deepinfra_model": config.deepinfra_review_model}))
            self.review_model_name = config.deepinfra_review_model
        graph = StateGraph(Turn)
        graph.add_node("context", self.context)
        graph.add_node("plan", self.plan)
        graph.add_node("tool", self.tool)
        graph.add_node("review", self.review)
        graph.add_edge(START, "context")
        graph.add_conditional_edges("context", lambda s: "done" if s.get("stop") else "plan", {"done": END, "plan": "plan"})
        graph.add_conditional_edges("plan", lambda s: "done" if s.get("stop") else "review" if s.get("draft_answer") else "tool", {"done": END, "tool": "tool", "review": "review"})
        graph.add_conditional_edges("tool", lambda s: "done" if s.get("stop") else "plan", {"done": END, "plan": "plan"})
        graph.add_edge("review", END)
        self.graph = graph.compile()

    def remaining(self, s):
        return self.config.max_seconds - (time.monotonic() - s["started"])

    def context(self, s):
        trace = s["trace"]
        if FORBIDDEN_REQUEST.search(s["question"]):
            return {"answer": "I can analyze authorized retail data, but cannot disclose customer names, contacts or precise locations.", "stop": True, "outcome": "denied"}
        with trace.stage("context"):
            conversation = self.store.get("conversation", s["principal"].user_id, s["conversation"])["body"]
            profile = self.store.profile(s["principal"].user_id)
            trios = self.knowledge.retrieve(s["question"], s["principal"], emit=trace.event, remaining_seconds=self.remaining(s))
            persona = self.store.list("persona", "system")
            persona = persona[-1]["body"] if persona else {"version": 0, "tone": "Clear, practical, professional."}
            # A user's entitlements can shrink between turns. Legacy history with
            # no recorded scope is excluded rather than assumed safe.
            history = [m for m in conversation["messages"] if scope_allowed(m, s["principal"])]
            bounded_history = []
            history_size = 0
            for message in reversed(history[-8:]):
                size = len(json.dumps(message))
                if history_size + size > self.config.max_context_chars // 4:
                    break
                bounded_history.insert(0, message)
                history_size += size
            prior_analysis = conversation.get("last_analysis")
            if not (prior_analysis and prior_analysis.get("provenance") and
                    scope_allowed(prior_analysis, s["principal"])):
                prior_analysis = None
            context = {"question": s["question"], "history": bounded_history,
                "prior_analysis": prior_analysis,
                "schema": SCHEMA,
                "business_defaults": {"revenue_statuses": ["Complete"],
                    "revenue_definition": "Sum sale_price for Complete items; other statuses excluded. Not net profit.",
                    "churn_window_days": self.config.churn_window_days,
                    "churn_population": "Previously purchasing customers of authorized brands only; no completed purchase within the window.",
                    "as_of_date": dt.datetime.now(dt.timezone.utc).date().isoformat(),
                    "user_analytical_override_allowed": True,
                    "instruction": "Use explicit user definitions when supplied; state the actual definition, as-of date and spend/churn denominator in the answer."},
                "privacy_policy": {"minimum_distinct_customers": self.config.minimum_cohort_size,
                    "demographics": "Grouped aggregates only. Flat SELECT/GROUP BY with direct grouping columns; no individual demographics, demographic-filtered customer rankings, nested queries or windows. Executor adds COUNT DISTINCT cohort guard.",
                    "user_override_allowed": False},
                "sql_capabilities": {"dialect": "bigquery", "allowed_functions": sorted(FUNCTIONS),
                    "conditional_count_example": "SUM(CASE WHEN condition THEN 1 ELSE 0 END)",
                    "month_bucket_example": "DATE_TRUNC(DATE(created_at), MONTH)",
                    "notes": "Function names are validator-normalized. Boolean AND/OR/NOT are supported. "
                        "COUNTIF and FORMAT_DATE/FORMAT_TIMESTAMP are unsupported; format dates in the final answer."},
                "preferences": profile, "persona": persona,
                "trios": trios, "authorized_products": list(s["principal"].products),
                "execution_scope": {"enforcement": "executor_bound_views",
                    **scope_snapshot(s["principal"]),
                    "note": "All logical tables are already restricted by the trusted executor. "
                        "Brand/CEO or legacy product scope is bound outside the model. "
                        "Absence of a product predicate in logical SQL does not imply unscoped results."},
                "mode": self.config.retail_mode, "tools": []}
            trace.event("context_versions", preference_version=profile["version"],
                persona_version=persona["version"], trios=[{"id": t["id"], "version": t["version"]} for t in trios],
                history_turns=len(context["history"]), schema_version="safe-v1")
            return {"context": context}

    def plan(self, s):
        if self.remaining(s) <= 0 or s["calls"] >= self.config.max_model_calls:
            return {"stop": True, "outcome": "budget_exhausted", "answer": "The analysis reached its execution budget. No further operations were attempted. Please narrow the question."}
        context = {**s["context"], "tools": s["tools"]}
        if len(json.dumps(context, default=str)) > self.config.max_context_chars:
            return {"stop": True, "outcome": "budget_exhausted",
                "answer": "The analysis context exceeds its size budget. Request a smaller aggregation or start a narrower analysis."}
        s["trace"].event("model_context", system_prompt_version="retail-v9-client-policy",
            model_call_id=f"{s['trace'].id}:model:{s['calls'] + 1}",
            context_digest=hashlib.sha256(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest(),
            tool_results=len(s["tools"]))
        try:
            with s["trace"].stage("model"):
                decision, usage = self.model.decide(context, self.remaining(s))
                # Applies to every generated field before any storage or tools.
                safe_output(decision.model_dump_json())
                s["trace"].event("model_usage",
                    model=("fixture" if self.config.retail_mode == "fixture" else
                        self.config.deepinfra_model if self.config.llm_provider == "deepinfra" else self.config.gemini_model),
                    provider="fixture" if self.config.retail_mode == "fixture" else self.config.llm_provider,
                    model_call_id=f"{s['trace'].id}:model:{s['calls'] + 1}", **usage)
            if decision.action in {"answer", "clarify"}:
                if decision.action == "answer" and not decision.text.strip():
                    s["trace"].event("answer_validation", outcome="failed", error_category="EmptyAnalysis")
                    return {"calls": s["calls"] + 1, "stop": True, "outcome": "failed",
                        "answer": "The model did not produce a completed analysis. No report was saved; please retry."}
                if decision.action == "answer" and not s["evidence"] and not s["context"]["prior_analysis"]:
                    s["trace"].event("answer_validation", outcome="failed", error_category="MissingQueryEvidence")
                    return {"calls": s["calls"] + 1, "stop": True, "outcome": "failed",
                        "answer": "I could not establish this analysis from query data. Please retry or narrow the metric and period."}
                if decision.action == "answer" and self.config.retail_mode == "live":
                    return {"calls": s["calls"] + 1, "draft_answer": decision.text}
                return {"calls": s["calls"] + 1, "stop": True,
                    "answer": decision.text or "Please clarify the metric and period you want analyzed.",
                    "completed_analysis": decision.action == "answer",
                    "outcome": "clarification" if decision.action == "clarify" else "succeeded"}
            return {"calls": s["calls"] + 1, "decision": decision}
        except (ModelError, PolicyError) as e:
            return {"calls": s["calls"] + 1, "stop": True, "answer": str(e),
                "outcome": "denied" if isinstance(e, PolicyError) else "dependency_error"}

    def review(self, s):
        """One bounded revision against original evidence before any persistence."""
        if self.remaining(s) <= 0 or s["calls"] >= self.config.max_model_calls:
            return {"stop": True, "outcome": "budget_exhausted",
                    "answer": "The report review budget was exhausted. No completed report was saved."}
        context = {**s["context"], "tools": s["tools"],
                   "report_review": {"draft": s["draft_answer"]}}
        if len(json.dumps(context, default=str)) > self.config.max_context_chars:
            return {"stop": True, "outcome": "budget_exhausted",
                    "answer": "The report review exceeds the context budget. No completed report was saved."}
        call_id = f"{s['trace'].id}:model:{s['calls'] + 1}"
        s["trace"].event("model_context", system_prompt_version="retail-v9-client-policy", phase="report_review",
                         model_call_id=call_id, context_digest=hashlib.sha256(
                             json.dumps(context, sort_keys=True, default=str).encode()).hexdigest())
        try:
            with s["trace"].stage("report_review"):
                decision, usage = self.review_model.decide(context, self.remaining(s))
                safe_output(decision.model_dump_json())
                s["trace"].event("model_usage", model_call_id=call_id,
                    model=self.review_model_name, phase="report_review",
                    provider=self.config.llm_provider, **usage)
            if decision.action != "answer" or not decision.text.strip():
                return {"calls": s["calls"] + 1, "stop": True, "outcome": "failed",
                        "answer": "The model did not finish report review. No completed report was saved."}
            return {"calls": s["calls"] + 1, "stop": True, "outcome": "succeeded",
                    "answer": decision.text, "completed_analysis": True}
        except (ModelError, PolicyError) as error:
            return {"calls": s["calls"] + 1, "stop": True,
                    "outcome": "denied" if isinstance(error, PolicyError) else "dependency_error",
                    "answer": str(error)}

    def tool(self, s):
        trace = s["trace"]
        tool_id = f"{trace.id}:tool:{len(s['tools']) + 1}"
        start = time.monotonic()
        trace.event("tool", tool_call_id=tool_id, tool=s["decision"].action, outcome="started")
        try:
            result = self._tool(s)
            trace.event("tool", tool_call_id=tool_id, tool=s["decision"].action,
                outcome=result.get("outcome", "retry" if result.get("repairs") else "succeeded"),
                seconds=time.monotonic() - start)
            return result
        except Exception:
            trace.event("tool", tool_call_id=tool_id, tool=s["decision"].action,
                outcome="failed", error_category="InternalError", seconds=time.monotonic() - start)
            raise

    def _tool(self, s):
        d, p, trace = s["decision"], s["principal"], s["trace"]
        if self.remaining(s) <= 0:
            return {"stop": True, "outcome": "budget_exhausted", "answer": "The execution time budget was reached; no further tool was run."}
        try:
            if d.action == "query":
                if s["queries"] >= self.config.max_queries:
                    return {"stop": True, "outcome": "budget_exhausted", "answer": "The query budget was reached. Please narrow the analysis."}
                try:
                    query_tree, _ = validate(d.sql)
                    demographic = any(t.name == "users" for t in query_tree.find_all(exp.Table))
                    if s["evidence"] and (demographic or any(e.get("demographic") for e in s["evidence"])):
                        raise PolicyError("Demographic reports support one grouped query per answer, without separate totals or individual lists. Request a single safe aggregate.")
                    result = self.analytics.execute(d.sql, p, self.remaining(s))
                except QueryError as e:
                    trace.event("query", outcome="failed", retry_count=s["repairs"], error_category="QueryError")
                    if s["repairs"] >= 1:
                        return {"stop": True, "queries": s["queries"] + 1, "answer": str(e), "outcome": "query_error"}
                    return {"queries": s["queries"] + 1, "repairs": s["repairs"] + 1,
                        "tools": s["tools"] + [{"action": "query", "error": str(e)}]}
                result["query_id"] = f"q{s['queries'] + 1}"
                result["demographic"] = demographic
                trace.event("query", outcome="completed", query_id=result["query_id"],
                    job_id=result["job_id"], bytes_processed=result["bytes_processed"],
                    estimated_bytes=result.get("estimated_bytes"), rows=len(result["rows"]),
                    sql_digest=hashlib.sha256(result["sql"].encode()).hexdigest(),
                    truncated=result["truncated"], seconds=result["seconds"], retry_count=s["repairs"])
                # Do not combine fresh demographic releases with prior totals in
                # model context. Cross-question inference remains design scope.
                context = ({**s["context"], "history": [], "prior_analysis": None}
                           if demographic else s["context"])
                return {"context": context, "queries": s["queries"] + 1, "evidence": s["evidence"] + [result],
                    "tools": s["tools"] + [{"action": "query", "result": result}]}
            if d.action == "schema":
                return {"stop": True, "answer": "Approved analytical schema (customer identifiers are pseudonymous):\n\n" +
                    "\n".join(f"- **{name}**: {', '.join(columns)}" for name, columns in SCHEMA.items())}
            if d.action == "list_reports":
                result = [{"id": r["id"], "title": r["body"]["title"]} for r in self.store.reports(p)]
                return {"stop": True, "management": result, "answer": table(result) if result else "You have no saved reports."}
            if d.action == "open_report":
                matches = [r for r in self.store.reports(p) if r["id"] == d.report_id]
                if not matches:
                    raise PolicyError("Report not found or not accessible.")
                return {"stop": True, "management": {"report_id": d.report_id}, "answer": matches[0]["body"]["content"]}
            if d.action == "delete_reports":
                proposal = self.store.propose_delete(p, s["conversation"], phrase=d.phrase or None, current=d.current_conversation)
                message = proposal.get("message") or ("Deletion preview:\n\n" + table(proposal["reports"]) +
                    f"\n\nConfirm with `/confirm {proposal['proposal_id']}` or cancel with `/cancel {proposal['proposal_id']}`. Nothing has been deleted.")
                return {"stop": True, "management": proposal, "answer": message}
            if d.action == "preference":
                result = self.store.preference(p.user_id, d.format, d.depth)
                return {"stop": True, "management": result, "answer": f"Saved your preference: {d.depth} {d.format}."}
            if d.action == "save_report":
                previous = self.store.get("conversation", p.user_id, s["conversation"])["body"].get("last_analysis")
                if s["evidence"]:
                    # Defer persistence until a completed final answer is available.
                    return {"save_title": d.title, "tools": s["tools"] + [
                        {"action": "save_report", "result": {"status": "pending_final_answer",
                            "instruction": "Finish the analysis with insights and action items; it will then be saved."}}]}
                if not previous:
                    raise PolicyError("Complete an analysis in this conversation before saving a report.")
                if not scope_allowed(previous, p):
                    raise PolicyError("Access changed since this analysis. Run it again before saving.")
                rid = self.store.save_report(p, s["conversation"], d.title, previous["content"], previous["provenance"])
                return {"stop": True, "management": {"report_id": rid}, "answer": f"Saved report **{d.title}** (`{rid}`)."}
            raise PolicyError("Unsupported operation.")
        except PolicyError as e:
            trace.event("tool", outcome="denied", error_category="PolicyError")
            return {"stop": True, "answer": str(e), "outcome": "denied"}
        except QueryUnavailable as e:
            trace.event("tool", outcome="failed", error_category="QueryUnavailable")
            return {"stop": True, "answer": str(e), "outcome": "dependency_error"}

    def chat(self, principal, question, conversation=None, sink=None):
        if not question.strip() or len(question) > 16000:
            raise PolicyError("Provide a question of at most 16000 characters.")
        conversation = self.store.conversation(principal, conversation)
        # One API process serializes turns for each conversation. Multiple API
        # replicas require a distributed admission/locking mechanism (see HLD).
        with self._lock_guard:
            lock = self._conversation_locks.get(conversation)
            if lock is None:
                lock = threading.Lock()
                self._conversation_locks[conversation] = lock
        with lock:
            return self._chat(principal, question, conversation, sink)

    def _chat(self, principal, question, conversation, sink):
        trace = Trace(self.config, principal.user_id, conversation, sink)
        start = time.monotonic()
        try:
            # Explicit application command, never extracted from model output.
            parts = question.strip().split()
            if parts[0] in {"/confirm", "/cancel"}:
                if len(parts) != 2:
                    raise PolicyError("Use /confirm PROPOSAL_ID or /cancel PROPOSAL_ID.")
                with trace.stage("report_confirmation"):
                    result = self.store.confirm_delete(principal, conversation, parts[1], parts[0] == "/confirm")
                trace.event("report_confirmation_outcome", tool_call_id=f"{trace.id}:tool:1",
                    proposal_id=parts[1], outcome=result["status"], deleted=result["deleted"])
                answer = f"Deletion {result['status']}; {result['deleted']} reports deleted."
                final = {"answer": answer, "management": result, "evidence": [], "outcome": "succeeded"}
            else:
                final = self.graph.invoke({"principal": principal, "conversation": conversation,
                    "question": clean(question), "trace": trace, "started": start,
                    "calls": 0, "queries": 0, "repairs": 0, "evidence": [], "tools": [], "stop": False},
                    {"recursion_limit": self.config.max_model_calls * 3 + 8})
                answer = final["answer"]
                if final["evidence"]:
                    answer += "\n\n### Query evidence\n\n" + "\n\n".join(
                        f"**{e['query_id']}** ({e['mode']}; {'truncated sample' if e['truncated'] else 'returned rows'})\n\n" + present(e["rows"], self.store.profile(principal.user_id))
                        for e in final["evidence"])
                    if final.get("completed_analysis"):
                        body = self.store.get("conversation", principal.user_id, conversation)["body"]
                        body["last_analysis"] = {"content": safe_output(answer), "provenance": final["evidence"],
                            **scope_snapshot(principal)}
                        self.store.replace("conversation", principal.user_id, conversation, body)
                        if final.get("save_title"):
                            rid = self.store.save_report(principal, conversation, final["save_title"], answer, final["evidence"])
                            final["management"] = {"report_id": rid}
                            trace.event("report_save", outcome="succeeded", report_id=rid)
                            answer += f"\n\nSaved report **{final['save_title']}** (`{rid}`)."
            safe_output(answer)
            self.store.append(principal, conversation, clean(question), answer, trace.id)
            outcome = final.get("outcome", "succeeded")
            trace.event("response", outcome=outcome, seconds=time.monotonic() - start)
            return {"conversation_id": conversation, "trace_id": trace.id, "mode": self.config.retail_mode,
                "answer": answer, "outcome": outcome, "evidence": final["evidence"], "management": final.get("management"),
                "completed_analysis": bool(final.get("completed_analysis"))}
        except PolicyError:
            trace.event("response", outcome="denied", error_category="PolicyError")
            raise
        except Exception:
            trace.event("response", outcome="failed", error_category="InternalError")
            return {"conversation_id": conversation, "trace_id": trace.id, "mode": self.config.retail_mode,
                "answer": "The request could not complete. No successful result can be confirmed; check your saved reports before retrying a save or deletion.", "outcome": "failed", "evidence": [], "management": None}
        finally:
            trace.close()
