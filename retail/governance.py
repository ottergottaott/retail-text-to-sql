"""Explicit feedback → evaluation → reviewer publication; no automatic learning."""
import hashlib
import json
from .analytics import Analytics, validate
from .knowledge import Knowledge
from .security import PolicyError, clean, safe_output, principal_for


class Governance:
    def __init__(self, config, store):
        self.config, self.store = config, store

    def feedback(self, principal, conversation, trace_id, comment, rating):
        history = self.store.get("conversation", principal.user_id, conversation)["body"]["messages"]
        if trace_id not in {m["trace"] for m in history}:
            raise PolicyError("Feedback must reference a visible turn in your conversation.")
        return self._record_feedback(principal, conversation, trace_id, comment, rating)

    def _record_feedback(self, principal, conversation, trace_id, comment, rating):
        if rating not in {"helpful", "unhelpful", "correction"} or len(comment) > 4000:
            raise PolicyError("Provide a supported rating and a comment of at most 4000 characters.")
        comment = comment.strip() or {'helpful':'Marked helpful.', 'unhelpful':'Marked unhelpful.',
            'correction':'Requested correction.'}[rating]
        return self.store.put("feedback", principal.user_id, {"conversation": conversation,
            "trace_id": trace_id, "comment": clean(comment), "rating": rating, "status": "unreviewed"})

    def candidate(self, source_user, feedback_id, trio):
        self.store.get("feedback", source_user, feedback_id)
        allowed = {"id", "question", "sql", "report", "tags", "scope", "products", "schema_version", "origin"}
        if set(trio) - allowed:
            raise PolicyError("Candidate contains unsupported fields.")
        validate(trio.get("sql", ""))
        if not all(trio.get(k) for k in ["id", "question", "report", "tags", "origin"]):
            raise PolicyError("A candidate needs ID, question, SQL, report, tags and origin.")
        return self.store.put("candidate", "system", {"trio": trio, "source_user": source_user,
            "feedback_id": feedback_id, "status": "pending"})

    def review(self, candidate_id, reviewer, cases):
        if not reviewer.strip() or not cases:
            raise PolicyError("A reviewer and nonempty evaluation cases are required.")
        row = self.store.get("candidate", "system", candidate_id)
        body = row["body"]
        if body["status"] != "pending":
            raise PolicyError("Candidate is already reviewed; create a new candidate.")
        trio = body["trio"]
        results = []
        for case in cases:
            # Expected rows are an explicit analyst-authored regression oracle,
            # never generated from the just-produced result by this command.
            principal = principal_for(case["user"], self.config)
            actual = Analytics(self.config).execute(trio["sql"], principal)
            if actual["truncated"]:
                raise PolicyError("Review cases must produce complete bounded results.")
            passed = actual["rows"] == case["expected_rows"]
            results.append({"name": case["name"], "passed": passed, "mode": actual["mode"],
                "job_id": actual["job_id"], "actual_rows": actual["rows"], "expected_rows": case["expected_rows"]})
        evaluation = {"verdict": "pass" if all(r["passed"] for r in results) else "fail",
            "cases": results, "oracle": "reviewer-authored expected rows",
            "candidate_digest": hashlib.sha256(json.dumps(trio, sort_keys=True).encode()).hexdigest()}
        evaluation_id = self.store.put("evaluation", "system", evaluation)
        if evaluation["verdict"] != "pass":
            return {"status": "rejected", "evaluation_id": evaluation_id, "published": False}
        published = Knowledge(self.store).publish(trio, reviewer, {**evaluation, "evaluation_id": evaluation_id})
        body.update(status="published", reviewer=reviewer, evaluation_id=evaluation_id,
            published_version=published["version"])
        self.store.replace("candidate", "system", candidate_id, body)
        return {"status": "published", "id": published["id"], "version": published["version"], "evaluation_id": evaluation_id}

    def persona(self, tone, reviewer):
        if not reviewer.strip() or not tone.strip() or len(tone) > 2000:
            raise PolicyError("Persona needs a reviewer and a tone of at most 2000 characters.")
        safe_output(tone)
        versions = self.store.list("persona", "system")
        value = {"version": max([r["body"]["version"] for r in versions], default=0) + 1,
            "tone": tone, "reviewer": reviewer}
        self.store.put("persona", "system", value)
        return value
