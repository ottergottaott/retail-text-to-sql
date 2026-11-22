"""Generate a standalone, dependency-free architecture viewer."""
from html import escape
from pathlib import Path


def n(id, title, subtitle, x, y, detail):
    return dict(id=id, title=title, subtitle=subtitle, x=x, y=y, detail=detail)


VIEWS = [
    ("Overview", "Logical modules", "One backend; Agent is one box. Select a component for details.", [
        n("clients", "Open WebUI / CLI", "User interfaces", 20, 20, "Both clients call the same API. The WebUI Pipe transports identity, question and progress; it does not run its own agent."),
        n("api", "API", "FastAPI · HTTP / SSE", 230, 20, "Authenticate, resolve trusted entitlements, bind conversations, expose reports/preferences and stream progress."),
        n("agent", "Agent", "LangGraph + Gemini", 440, 20, "Load safe context, plan bounded steps, invoke backend tools and return grounded analysis or clarification."),
        n("analytics", "Analytics", "Safe SQL execution", 650, 20, "Resolve logical SQL, bind every physical source to a scoped projection, enforce byte/time/row budgets and return evidence."),
        n("bq", "BigQuery", "Transaction evidence", 650, 220, "External thelook tables: orders, order_items, products, users. Current integration is unverified without credentials."),
        n("knowledge", "Knowledge", "Curated trios + retrieval", 20, 220, "Latest approved version and access/schema filtering, lexical/vector retrieval and rank fusion. Synthetic seeds are labeled."),
        n("reports", "Reports", "Ownership + confirmation", 230, 220, "Independent saved reports and transactional deletion proposals. Reports survive chat deletion."),
        n("configuration", "Configuration", "Preferences + persona", 440, 220, "Read at turn start. Presentation data stays subordinate to fixed security/tool policy; it is not an execution stage in the main query path."),
    ], [("clients", "api"), ("api", "agent"), ("agent", "analytics"), ("analytics", "bq"), ("agent", "knowledge"), ("agent", "reports"), ("agent", "configuration")], 340),
    ("Agent", "LangGraph request path", "Privacy and authorization apply before context and during tools; output checking is supplemental.", [
        n("context", "Context", "Scoped history + knowledge", 20, 20, "Exclude revoked or unknown-scope history. Load permitted trios, preference and persona versions. Sanitize user text before model context."),
        n("plan", "Plan", "Structured Gemini decision", 230, 20, "Choose a query, clarification, answer, schema or owned-report operation. Bound calls, query attempts and elapsed time."),
        n("tool", "Tool", "Trusted backend policy", 440, 20, "Analytics validates and scopes SQL. Reports enforce ownership. Policy denials terminate; one SQL repair is permitted."),
        n("answer", "Answer / Clarification", "Safe response + provenance", 230, 220, "Respond using actual evidence; append deterministic rows in the user's preferred format. Save only completed, currently accessible analysis."),
        n("confirm", "Confirmation", "Explicit application command", 650, 220, "The user sends /confirm ID or /cancel ID outside model planning. The persisted proposal is revalidated transactionally."),
    ], [("context", "plan"), ("plan", "tool"), ("tool", "plan"), ("plan", "answer")], 340),
    ("Storage", "Storage and independent lifecycles", "SQL stores application records; raw transactions remain in BigQuery.", [
        n("db", "Application database", "PostgreSQL / local SQLite", 335, 20, "Prototype uses a generic records table. Production should normalize, index and migrate independently owned data with explicit retention."),
        n("conversations", "Conversations", "History + brand scope", 20, 180, "Owner-scoped history and last completed analysis. Old context is filtered when access shrinks. No mid-turn graph checkpointing."),
        n("reports", "Reports", "Saved content + provenance", 335, 180, "Independent report IDs, owner, scope and source conversation; exact versioned deletion proposals and minimal audit."),
        n("versions", "Versioned records", "Knowledge / persona / review", 650, 180, "Preferences, curated trios, embedding cache, feedback, candidates, evaluations and persona versions."),
        n("bq", "BigQuery", "External transaction store", 20, 340, "Not a local replica. Only trusted scoped projections may enter the agent's evidence."),
        n("webui", "Open WebUI database", "Separate UI history", 335, 340, "Deleting UI chat does not delete backend reports or automatically erase backend history. Production needs coordinated retention."),
        n("bucket", "Golden source bucket", "Production versioned objects", 650, 340, "Proposed Cloud Storage source of immutable curated trios and release manifests. Prototype source records are in application SQL."),
    ], [("db", "conversations"), ("db", "reports"), ("db", "versions")], 460),
    ("RAG", "Hybrid retrieval", "Approved historical methodology guides analysis; current query results supply the facts.", [
        n("question", "Question", "Sanitized user intent", 20, 20, "Only the sanitized question is embedded at request time. Document embeddings are built explicitly by an operator."),
        n("filter", "Eligible trios", "Latest + scope + schema", 230, 20, "Resolve latest published version before permission filtering, preventing an old broader version from reappearing."),
        n("lexical", "Keyword search", "Terms + analytical tags", 440, 20, "Useful for exact metric names, products and dimensions. Unsupported/irrelevant requests can return no examples."),
        n("vectors", "Vector search", "Gemini embeddings", 440, 220, "Compare against permitted precomputed vectors; record model/index coverage. Fall back to lexical search if unavailable."),
        n("fusion", "Rank fusion", "Reciprocal rank fusion", 650, 20, "Combine lexical and semantic ranks, apply a semantic threshold and select at most two trios. Threshold needs live calibration."),
        n("agent", "Agent", "Question → SQL → Report", 650, 220, "Use selected trios as untrusted examples of analytical reasoning, not authority or current numeric evidence."),
    ], [("question", "filter"), ("filter", "lexical"), ("filter", "vectors"), ("lexical", "fusion"), ("vectors", "fusion"), ("fusion", "agent")], 340),
    ("Deletion", "Strict report deletion", "The model can request a preview. It cannot manufacture the user's confirmation.", [
        n("select", "Selection", "Phrase / IDs / this chat", 20, 20, "Match only owned reports that remain accessible under current entitlements. No broad unscoped deletion."),
        n("preview", "Preview", "Exact report titles and IDs", 335, 20, "No deletion has happened. Show the concrete selected set and cancellation/confirmation commands."),
        n("proposal", "Proposal", "Owner + versions + expiry", 650, 20, "Persist the exact targets, user, conversation and a ten-minute expiry. Proposal survives application restart."),
        n("confirm", "User confirmation", "/confirm ID or /cancel ID", 650, 220, "Explicit application protocol. Wrong owner/conversation, expired proposal or changed targets cannot execute."),
        n("transaction", "Transaction", "Recheck → delete → audit", 335, 220, "Claim pending proposal, revalidate scope and versions, delete only exact target IDs and record the actual outcome atomically."),
        n("outcome", "Outcome", "Deleted / cancelled / denied", 20, 220, "Replay cannot delete new reports. Report-library deletion does not claim erasure of prior chat copies or backups."),
    ], [("select", "preview"), ("preview", "proposal"), ("proposal", "confirm"), ("confirm", "transaction"), ("transaction", "outcome")], 340),
    ("Learning", "Reviewed system improvement", "Personal preferences are stored separately; production system changes require automatic evaluation gates; the optional demo remains operator-driven.", [
        n("feedback", "Feedback", "Owned turn reference", 20, 20, "User feedback remains untrusted. It may suggest a better method but never directly changes published knowledge or policy."),
        n("candidate", "Candidate", "Sanitized analyst example", 230, 20, "Operator links a trio candidate to feedback and records origin. Synthetic demonstrations are explicitly identified."),
        n("evaluation", "Evaluation", "Independent expected results", 440, 20, "Run reviewer-authored SQL cases for configured users. Production adds held-out retrieval, safety, report and UX gates with automated low-risk publication and exception review."),
        n("publication", "Publication", "Reviewer + new version", 650, 20, "Passing evaluation permits publication with provenance. Retain prior versions for reviewed rollback."),
        n("index", "Index", "Versioned document vectors", 650, 220, "Explicitly rebuild changed approved documents. A stale model/content/version cache entry cannot silently serve a new document."),
        n("retrieval", "Retrieval", "Next-turn approved context", 440, 220, "New published knowledge can change the examples selected for future questions; that alone is not proof of better generated reports."),
        n("rejected", "Rejected evaluation", "No publication", 230, 220, "Failing cases remain evidence for review; they do not become trusted knowledge."),
    ], [("feedback", "candidate"), ("candidate", "evaluation"), ("evaluation", "publication"), ("publication", "index"), ("index", "retrieval"), ("evaluation", "rejected")], 340),
    ("Evaluation", "Evaluation before release", "Keep retrieval mechanics, semantic relevance, report quality and UX evidence separate.", [
        n("cases", "Evaluation cases", "Versioned independent oracles", 20, 20, "SQL result oracles, relevant-trio labels, adversarial requests, follow-up scenarios and executive task scripts."),
        n("runner", "Evaluation runner", "Offline and live suites", 230, 20, "Offline fixtures cover deterministic invariants. Real-model and real-service runs have separate labels and evidence."),
        n("metrics", "Results", "Correctness + retrieval + safety", 440, 20, "Intent/result correctness, grounded claims, Recall@2/MRR, negative retrieval rate, budgets and ownership/PII regressions."),
        n("gate", "Release review", "Human approval + regression gate", 650, 20, "Any confirmed safety failure blocks release. Do not average security failures into a general quality score."),
        n("ux", "Executive UX review", "CLI and actual WebUI tasks", 230, 220, "Observe task completion, clarification burden, progress/error comprehension and accidental destructive actions. No human score is currently claimed."),
        n("monitor", "Production monitoring", "Versioned outcomes + rollback", 650, 220, "Track failure rates, p95 duration, repair/empty/fallback rates, bytes and measured usage. Alert and roll back a harmful release."),
    ], [("cases", "runner"), ("runner", "metrics"), ("metrics", "gate"), ("runner", "ux"), ("gate", "monitor")], 340),
    ("Deployment", "Deployment services", "Compose locally; GCP services are the proposed production deployment.", [
        n("webui", "Open WebUI", "Separate service · thin Pipe", 20, 20, "Pinned slim image in Compose; production service needs durable shared UI state and appropriate websocket coordination when scaled."),
        n("api", "API + Agent", "Container · Cloud Run target", 335, 20, "One Python deployment contains API, LangGraph, policy, analytics and application tools. Production ingress verifies OIDC."),
        n("ops", "Operations", "Logging + optional Langfuse", 650, 20, "Metadata-only traces. Add Secret Manager, workload identity, retention, dashboards and incident runbooks in production."),
        n("sql", "PostgreSQL", "Cloud SQL target", 20, 220, "Persistent application records. Before multiple API replicas, use distributed conversation serialization and bounded admission."),
        n("gemini", "Gemini", "External model + embeddings", 335, 220, "Explicit configured model, finite calls and timeouts. No credentials are needed for the clearly labeled offline fixtures."),
        n("bq", "BigQuery", "External read-only analytics", 650, 220, "Public thelook demonstration; private production data additionally needs governed access and least-privilege database policy."),
    ], [("webui", "api"), ("api", "ops"), ("api", "sql"), ("api", "gemini"), ("api", "bq")], 340),
]


def svg(nodes, edges, height, prefix):
    lookup = {node["id"]: node for node in nodes}
    paths = []
    for a, b in edges:
        p, q = lookup[a], lookup[b]
        if p["y"] == q["y"]:
            forward = q["x"] > p["x"]
            x1, x2 = p["x"] + (180 if forward else 0), q["x"] + (0 if forward else 180)
            y = p["y"] + (24 if forward else 48)
            path = f'M{x1},{y} H{x2}'
        elif q["y"] < p["y"] and q["x"] > p["x"]:
            x1, x2 = p["x"] + 180, q["x"]
            y1, y2 = p["y"] + 36, q["y"] + 36
            middle = (x1 + x2) / 2
            path = f'M{x1},{y1} H{middle} V{y2} H{x2}'
        else:
            down = q["y"] > p["y"]
            x1, x2 = p["x"] + 90, q["x"] + 90
            y1, y2 = p["y"] + (72 if down else 0), q["y"] + (0 if down else 72)
            middle = (y1 + y2) / 2
            path = f'M{x1},{y1} V{middle} H{x2} V{y2}'
        paths.append(f'<path d="{path}" marker-end="url(#{prefix})"/>')
    boxes = []
    for item in nodes:
        boxes.append(f'''<g class="node" tabindex="0" role="button" aria-label="{escape(item['title'])}"
          data-detail="{escape(item['detail'], quote=True)}" transform="translate({item['x']},{item['y']})">
          <rect width="180" height="72" rx="10"/>
          <text x="90" y="29" text-anchor="middle">{escape(item['title'])}</text>
          <text x="90" y="51" text-anchor="middle" class="sub">{escape(item['subtitle'])}</text></g>''')
    return f'''<svg viewBox="0 0 850 {height}" role="img" aria-label="Architecture diagram">
      <defs><marker id="{prefix}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10z"/></marker></defs>
      <g class="edges">{''.join(paths)}</g>{''.join(boxes)}</svg>'''


def build():
    buttons, sections = [], []
    for i, (label, title, subtitle, nodes, edges, height) in enumerate(VIEWS):
        buttons.append(f'<button role="tab" id="tab-{i}" aria-controls="view-{i}" aria-selected="{str(i == 0).lower()}" data-tab="{i}">{label}</button>')
        sections.append(f'''<section id="view-{i}" role="tabpanel" aria-labelledby="tab-{i}" {'hidden' if i else ''}>
          <h2>{title}</h2><p class="muted">{subtitle}</p>{svg(nodes, edges, height, f'arrow-{i}')}
          <div class="detail" aria-live="polite">Select a component to inspect its responsibility and limits.</div></section>''')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1"><title>Retail Assistant architecture</title>
      <style>
      *{box-sizing:border-box}body{margin:0;color:var(--foreground,#182334);font:14px/1.5 var(--font-sans,system-ui,sans-serif)}
      h1{font-size:23px;margin:0 0 4px}h2{font-size:19px;margin:18px 0 4px}p{margin:5px 0 14px}.muted{color:var(--muted-foreground,#536176)}
      nav{display:flex;flex-wrap:wrap;gap:7px;margin:18px 0}button{font:inherit;cursor:pointer;border:1px solid var(--border,#cbd5e1);background:var(--card,#f8fafc);color:inherit;border-radius:8px;padding:7px 12px}
      button[aria-selected=true]{border-color:var(--primary,#4868bd);font-weight:650;background:var(--accent,#e9efff)}
      [hidden]{display:none!important}svg{width:100%;display:block}svg text{font-size:15px;fill:var(--foreground,#182334);font-weight:650}.sub{font-size:11px;font-weight:400;fill:var(--muted-foreground,#536176)}
      .node{cursor:pointer}.node rect{fill:var(--card,#f8fafc);stroke:var(--border,#b9c6d7);stroke-width:1.4}.node:focus rect,.node:hover rect{stroke:var(--primary,#4868bd);stroke-width:2.5}
      .edges path{fill:none;stroke:var(--muted-foreground,#708198);stroke-width:1.5}marker path{fill:var(--muted-foreground,#708198)}
      .detail{padding:16px;border-radius:var(--radius,10px);background:var(--muted,#edf1f7);min-height:76px}a{color:var(--primary,#355bb7)}
      .status{font-size:12px;padding:10px 16px;border-radius:8px;background:var(--muted,#edf1f7)}
      @media(max-width:520px){svg text{font-size:16px}.sub{font-size:12px}button{padding:7px 9px}.diagram-scroll{overflow-x:auto}svg{min-width:650px}}
      </style></head><body>
      <h1>Retail Assistant</h1><p class="muted">Architecture, request paths and independent lifecycles</p>
      <div class="status">Verified fixture workflow: Docker, PostgreSQL persistence, CLI and Open WebUI progress/tables/report saving. Gemini, real embeddings and BigQuery await live verification.</div>
      <nav role="tablist" aria-label="Architecture views">''' + ''.join(buttons) + '</nav><main>' + ''.join(sections) + '''</main>
      <p class="muted" style="margin-top:18px">Each view is intentionally focused. Security applies at identity/context, query sources, persistence and output. Telemetry observes the whole request. See architecture.md for all eight requirements and production boundaries.</p>
      <script>
      const tabs=[...document.querySelectorAll('[data-tab]')];
      function activate(index){tabs.forEach((b,i)=>{b.setAttribute('aria-selected',String(i===index));document.getElementById('view-'+i).hidden=i!==index})}
      tabs.forEach((b,i)=>{b.addEventListener('click',()=>activate(i));b.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();const next=(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;activate(next);tabs[next].focus()}})});
      document.querySelectorAll('.node').forEach(node=>{const show=()=>{node.closest('section').querySelector('.detail').textContent=node.dataset.detail};node.addEventListener('click',show);node.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show()}})});
      document.querySelectorAll('svg').forEach(svg=>{const wrap=document.createElement('div');wrap.className='diagram-scroll';svg.before(wrap);wrap.append(svg)});
      </script></body></html>'''


if __name__ == "__main__":
    Path(__file__).with_name("architecture.html").write_text(build())
