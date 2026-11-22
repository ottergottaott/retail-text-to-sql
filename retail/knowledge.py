"""Versioned curated trios; lexical + vector rankings with scoped RRF fusion."""
import hashlib
import json
import math
import re
from pathlib import Path
from .analytics import validate
from .security import PolicyError, safe_output
from .embeddings import EmbeddingUnavailable

SEEDS = [
    {"id": "monthly-revenue", "version": 1, "question": "How did monthly revenue change?", "tags": ["revenue", "sales", "month", "time", "trend"],
     "sql": "SELECT DATE_TRUNC(DATE(created_at), MONTH) AS month, SUM(sale_price) AS revenue FROM order_items WHERE status='Complete' GROUP BY month ORDER BY month",
     "report": "Compare complete equal-length periods, inspect item counts and average item price, and separate facts from causal hypotheses. Revenue uses Complete items; not net revenue after all returns.", "scope": "shared", "origin": "synthetic demonstration; not historical analyst work", "status": "published"},
    {"id": "product-comparison", "version": 1, "question": "Compare product revenue, units and returns", "tags": ["product", "compare", "performance", "return", "difference"],
     "sql": "SELECT p.id, p.name, COUNT(*) AS items, SUM(CASE WHEN i.status='Complete' THEN i.sale_price ELSE 0 END) AS revenue FROM order_items i JOIN products p ON i.product_id=p.id GROUP BY p.id,p.name ORDER BY revenue DESC",
     "report": "Decompose differences into volume, realized selling price, and item status mix. Returns and seasonality are possible contributors, not established causes. Do not claim conversion without traffic data.", "scope": "shared", "origin": "synthetic demonstration; not historical analyst work", "status": "published"},
    {"id": "customer-spend", "version": 1, "question": "Compare customer spend by state and identify top pseudonymous customers", "tags": ["customer", "spend", "state", "top", "behavior"],
     "sql": "SELECT u.state, COUNT(DISTINCT i.customer_key) AS customers, SUM(i.sale_price) AS revenue FROM order_items i JOIN users u ON i.customer_key=u.customer_key WHERE i.status='Complete' GROUP BY u.state",
     "report": "Define spend per active customer within authorized purchases. Customer keys are pseudonyms, not guaranteed anonymity. Never display names or contact details. Confirm inactivity/cohort definition before computing churn.", "scope": "shared", "origin": "synthetic demonstration; not historical analyst work", "status": "published"},
]


def tokens(text):
    stop = {"a", "an", "the", "how", "did", "do", "does", "what", "is", "are", "of", "for", "in", "and", "to", "by", "my", "me", "i"}
    return set(re.findall(r"[a-z0-9]+", text.lower())) - stop


def document(t):
    return t["question"] + "\n" + " ".join(t["tags"]) + "\n" + t["report"]


def cosine(a, b):
    if len(a) != len(b) or not a or not all(math.isfinite(v) for v in a + b):
        return 0
    norm = math.sqrt(sum(v*v for v in a) * sum(v*v for v in b))
    return sum(x*y for x, y in zip(a, b)) / norm if norm else 0


class Knowledge:
    def __init__(self, store, embedder=None, min_similarity=0.65, lexical_min_similarity=0.60):
        self.store = store
        self.embedder = embedder
        self.min_similarity = min_similarity
        self.lexical_min_similarity = min(lexical_min_similarity, min_similarity)
        for trio in SEEDS:
            if not any(r["body"]["id"] == trio["id"] for r in store.list("trio", "system")):
                validate(trio["sql"])
                store.put("trio", "system", {**trio, "schema_version": "safe-v1"})

    def published(self):
        latest = {}
        for r in self.store.list("trio", "system"):
            t = r["body"]
            if t.get("status") == "published" and (t["id"] not in latest or t["version"] > latest[t["id"]]["version"]):
                latest[t["id"]] = t
        return list(latest.values())

    def vector_id(self, t):
        content = json.dumps({"id": t["id"], "version": t["version"], "schema": t.get("schema_version"),
            "model": self.embedder.version, "document": document(t)}, sort_keys=True)
        return "emb_" + hashlib.sha256(content.encode()).hexdigest()

    def index(self):
        """Explicit administrator operation; no document embedding on request path."""
        if not self.embedder:
            raise PolicyError("Configure an embedding provider before indexing.")
        existing = {r["id"] for r in self.store.list("embedding", "system")}
        indexed = 0
        for t in self.published():
            key = self.vector_id(t)
            if key not in existing and t.get("schema_version") == "safe-v1":
                vector = self.embedder.embed([document(t)], "RETRIEVAL_DOCUMENT")[0]
                self.store.put("embedding", "system", {"trio": t["id"], "version": t["version"],
                    "model": self.embedder.version, "vector": vector}, id=key)
                indexed += 1
        return {"indexed": indexed, "model": self.embedder.version}

    def retrieve(self, question, principal, k=2, emit=None, remaining_seconds=10):
        q = tokens(question)
        candidates = []
        # Resolve latest publication before access filtering, so an older broader
        # scope cannot reappear after a replacement tightens its permissions.
        for t in self.published():
            if t.get("schema_version") != "safe-v1":
                continue
            if t.get("scope") != "shared" and (t.get("scope") != "products" or not t.get("products") or not set(t["products"]) <= set(principal.products)):
                continue
            text_tokens = tokens(t["question"] + " " + t["report"])
            lexical = len(q & text_tokens) / math.sqrt(max(1, len(q) * len(text_tokens)))
            metadata = len(q & tokens(" ".join(t["tags"]))) / max(1, len(q))
            score = lexical + 2 * metadata
            candidates.append({**t, "lexical_score": score})
        lexical = sorted([t for t in candidates if t["lexical_score"] > 0], key=lambda x: (-x["lexical_score"], x["id"]))
        rankings = [lexical]
        mode, coverage = "lexical", 0
        gate, rejected = "unavailable", 0
        if self.embedder and candidates and remaining_seconds > 0:
            vectors = {r["id"]: r["body"]["vector"] for r in self.store.list("embedding", "system")}
            indexed = [t for t in candidates if self.vector_id(t) in vectors]
            coverage = len(indexed)
            if indexed:
                try:
                    query = self.embedder.embed([question], "RETRIEVAL_QUERY", timeout=min(10, remaining_seconds))[0]
                    semantic = [{**t, "similarity": cosine(query, vectors[self.vector_id(t)])} for t in indexed]
                    similarities = {t['id']: t['similarity'] for t in semantic}
                    # Lexical overlap may rescue a moderately similar method, but
                    # cannot bypass semantic rejection or a missing current vector.
                    gated_lexical = [t for t in lexical if t['id'] in similarities
                        and similarities[t['id']] >= self.lexical_min_similarity]
                    rejected = len(lexical) - len(gated_lexical)
                    rankings = [gated_lexical]
                    gate = "applied"
                    semantic = sorted([t for t in semantic if t["similarity"] >= self.min_similarity], key=lambda x: (-x["similarity"], x["id"]))
                    rankings.append(semantic)
                    mode = "hybrid"
                except EmbeddingUnavailable:
                    mode = "lexical_fallback"
        fused = {}
        for ranking in rankings:
            for rank, t in enumerate(ranking, 1):
                if t["id"] not in fused:
                    fused[t["id"]] = {**t, "score": 0}
                fused[t["id"]]["score"] += 1 / (60 + rank)
        result = sorted(fused.values(), key=lambda x: (-x["score"], x["id"]))[:k]
        if emit:
            emit("retrieval", retrieval_mode=mode, eligible=len(candidates), indexed=coverage,
                 embedding_model=self.embedder.version if self.embedder else None, returned=len(result),
                 retrieval_policy="semantic-lexical-gate-v1", relevance_gate=gate,
                 lexical_rejected=rejected, index_complete=coverage == len(candidates),
                 lexical_min_similarity=self.lexical_min_similarity,
                 semantic_min_similarity=self.min_similarity)
        return result

    def publish(self, candidate, reviewer, evaluation):
        if not reviewer or evaluation.get("verdict") != "pass" or not evaluation.get("cases"):
            raise PolicyError("Publication requires reviewer and passing evaluation case references.")
        safe_output(json.dumps(candidate))
        for field in ["id", "question", "report", "sql"]:
            if not candidate.get(field):
                raise PolicyError("Trio is missing a required field.")
            safe_output(candidate[field])
        validate(candidate["sql"])
        if candidate.get("scope") not in {"shared", "products"}:
            raise PolicyError("Explicit publication scope is required.")
        if candidate.get("scope") == "products" and not candidate.get("products"):
            raise PolicyError("Product-scoped examples require explicit product IDs.")
        if candidate.get("schema_version") != "safe-v1":
            raise PolicyError("Trio schema version is incompatible.")
        previous = [r["body"]["version"] for r in self.store.list("trio", "system") if r["body"]["id"] == candidate["id"]]
        t = {**candidate, "version": max(previous, default=0) + 1, "status": "published", "reviewer": reviewer, "evaluation": evaluation}
        self.store.put("trio", "system", t)
        return t
