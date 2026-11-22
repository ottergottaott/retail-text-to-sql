"""Deterministic, inert report HTML. Model text is data, never executable markup."""
from datetime import datetime, timezone
import base64
import hashlib
import math
from html import escape
from pathlib import Path
import re
from string import Template


# The only active code is a fixed, hash-authorized sizing bridge in the preview.
# It sends a pixel height, never report contents or credentials, to the parent.
_RESIZE_SCRIPT = """(()=>{const root=document.querySelector('.shell');const resize=()=>parent.postMessage({type:'iframe:height',height:Math.min(1100,Math.ceil(root.getBoundingClientRect().height)+4)},'*');new ResizeObserver(resize).observe(root);window.addEventListener('resize',resize);resize()})()"""
_RESIZE_HASH = base64.b64encode(hashlib.sha256(_RESIZE_SCRIPT.encode()).digest()).decode()


def _escape(value):
    # Backticks must not terminate the Markdown fence carrying an Artifact.
    return escape(str(value), quote=True).replace("`", "&#96;")


_SQL_TOKEN = re.compile(
    r"(?P<comment>--[^\n]*|/\*[\s\S]*?\*/)"
    r"|(?P<string>'(?:''|\\.|[^'\\])*')"
    r'|(?P<identifier>`(?:``|[^`])*`|"(?:""|[^"])*")'
    r"|(?P<number>\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)"
    r"|(?P<word>\b[A-Za-z_][A-Za-z_0-9]*\b)")
_SQL_KEYWORDS = frozenset("SELECT FROM WHERE GROUP BY ORDER HAVING LIMIT OFFSET AS WITH JOIN LEFT RIGHT FULL INNER OUTER CROSS ON AND OR NOT IN IS NULL TRUE FALSE CASE WHEN THEN ELSE END DISTINCT UNION ALL EXCEPT INTERSECT OVER PARTITION ASC DESC BETWEEN EXISTS QUALIFY UNNEST INTERVAL CURRENT_DATE DATE TIMESTAMP CAST SAFE_CAST EXTRACT COUNT SUM AVG MIN MAX COALESCE ROUND DATE_TRUNC NULLIF".split())


def highlight_sql(sql):
    """Lossless display lexer; never rewrites or validates the executed SQL."""
    parts, position = [], 0
    for token in _SQL_TOKEN.finditer(sql):
        parts.append(_escape(sql[position:token.start()]))
        kind = token.lastgroup
        if kind == "word":
            kind = "keyword" if token.group().upper() in _SQL_KEYWORDS else None
        value = _escape(token.group())
        parts.append(f'<span class="sql-{kind}">{value}</span>' if kind else value)
        position = token.end()
    parts.append(_escape(sql[position:]))
    return "".join(parts)


def _inline(text):
    parts = re.split(r"(`[^`\n]+`|\*\*[^*\n]+\*\*)", text)
    return "".join("<code>" + _escape(p[1:-1]) + "</code>" if p.startswith("`") and p.endswith("`")
        else "<strong>" + _escape(p[2:-2]) + "</strong>" if p.startswith("**") and p.endswith("**")
        else _escape(p) for p in parts)


def _markdown(text):
    """Small allowlisted Markdown subset: text, headings, lists, tables and code."""
    lines, output, i = text.splitlines(), [], 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i]); i += 1
            output.append("<pre><code>" + _escape("\n".join(code)) + "</code></pre>")
        elif line.startswith("|") and i + 1 < len(lines) and re.fullmatch(r"[\s|:\-]+", lines[i + 1]):
            rows = []
            headers = [x.strip() for x in line.strip("|").split("|")]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([x.strip() for x in lines[i].strip().strip("|").split("|")]); i += 1
            output.append(_table(headers, rows, inline=True))
            continue
        elif re.match(r"^#{1,6}\s", line):
            heading = re.sub(r"^#+\s+", "", line)
            output.append("<h2>" + _inline(heading) + "</h2>")
        elif re.match(r"^(?:[-*]|\d+[.)])\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*(?:[-*]|\d+[.)])\s+", lines[i]):
                items.append("<li>" + _inline(re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", lines[i])) + "</li>")
                i += 1
            output.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif line in {"---", "***"}:
            output.append("<hr>")
        else:
            output.append("<p>" + _inline(line) + "</p>")
        i += 1
    return "\n".join(output)


def _table(columns, rows, inline=False):
    cell = _inline if inline else _escape
    return '<div class="table-wrap"><table><thead><tr>' + "".join("<th>" + cell(c) + "</th>" for c in columns) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join("<td>" + cell("—" if v is None else v) + "</td>" for v in row) + "</tr>" for row in rows) + "</tbody></table></div>"


def _chart(evidence):
    """One descriptive chart of returned revenue rows, with no inferred totals."""
    for e in evidence:
        rows = e.get("rows") or []
        if not 2 <= len(rows) <= 16:
            continue
        metric = next((k for k in rows[0] if k.lower() in {"revenue", "completed_revenue", "total_revenue"}), None)
        dimensions = [k for k in rows[0] if k != metric and not any(t in k.lower() for t in ("count", "items", "price", "revenue", "cost"))]
        if set(dimensions) == {"product_id", "product_name"}:
            dimensions = ["product_name"]
        if not metric or len(dimensions) != 1:
            continue
        dimension = dimensions[0]
        values = [r.get(metric) for r in rows]
        if not all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values) or max(values) == 0:
            continue
        bars = []
        for i, (row, value) in enumerate(zip(rows, values)):
            y = 12 + i * 40
            label = str(row.get(dimension, "—"))
            short_label = label if len(label) <= 18 else label[:17] + "…"
            bars.append(f'<text x="0" y="{y + 17}" class="chart-label"><title>{_escape(label)}</title>{_escape(short_label)}</text>'
                f'<rect x="140" y="{y}" width="330" height="24" rx="5" fill="#edf4f1"/>'
                f'<rect x="140" y="{y}" width="{330 * value / max(values):.2f}" height="24" rx="5" fill="#138779"/>'
                f'<text x="485" y="{y + 17}" class="chart-value">{_escape(format(value, ".8g"))}</text>')
        heading = metric.replace("_", " ").capitalize() + " by " + dimension
        note = "Truncated sample" if e.get("truncated") else "Returned rows"
        return f'<section class="visual"><div class="section-label">In view · {_escape(e.get("query_id") or "query")}</div><h2>{_escape(heading)}</h2>' + \
            f'<p class="muted">{note} · values from query evidence; no inferred totals.</p><svg viewBox="0 0 590 {len(rows) * 40 + 16}" role="img" aria-label="{_escape(heading)}">' + \
            "".join(bars) + '</svg></section>'
    return ""


def render_report(body, report_id=None, created=None):
    """Return full Artifact and expandable embedded preview from authorized data."""
    title = body.get("title") or "Retail analysis"
    evidence = body.get("provenance") or []
    modes = {e.get("mode") for e in evidence}
    source = "Live BigQuery" if modes == {"live"} else "Fixture data" if modes == {"fixture"} else "Recorded evidence"
    state = "Saved report" if report_id else "Not saved"
    if isinstance(created, (float, int)):
        date = datetime.fromtimestamp(created, timezone.utc).strftime("%d %b %Y · %H:%M UTC")
    else:
        date = created or "Time not recorded"
    content = body.get("content", "").split("### Query evidence", 1)[0].strip()
    analysis = _markdown(content)
    queries = []
    for n, e in enumerate(evidence, 1):
        rows = e.get("rows") or []
        columns = list(rows[0]) if rows else []
        grid = _table(columns, [[r.get(c) for c in columns] for r in rows]) if rows else '<p class="muted">No rows returned.</p>'
        actual_bytes = e.get("bytes_processed")
        byte_text = f"{actual_bytes:,}" if isinstance(actual_bytes, int) else "Not recorded"
        truncated = '<span class="pill warning">Truncated · sample only</span>' if e.get("truncated") else '<span class="pill">Returned rows</span>'
        queries.append(f'<section class="query"><header><h3>{_escape(e.get("query_id") or f"Query {n}")}</h3>{truncated}</header>{grid}'
            f'<details class="sql"><summary>SQL &amp; execution details</summary><pre><code class="language-sql">{highlight_sql(e.get("sql") or "SQL not recorded")}</code></pre>'
            f'<dl><dt>Query job</dt><dd>{_escape(e.get("job_id") or "Not recorded")}</dd><dt>Bytes processed · measured</dt><dd>{byte_text}</dd></dl></details></section>')
    values = dict(title=_escape(title), source=_escape(source), state=state,
        date=_escape(date), report_id=_escape(report_id or "Unsaved analysis"),
        scope=_escape(", ".join(map(str, body.get("products", []))) or "See query evidence"),
        query_count=str(len(evidence)), row_count=str(sum(len(e.get("rows") or []) for e in evidence)),
        analysis=analysis, chart=_chart(evidence), queries="".join(queries) or '<p class="muted">No query evidence recorded.</p>')
    template = Template((Path(__file__).parent / "templates/report.html").read_text())
    html = template.substitute(values, view_class="full", preview_open="", preview_close="",
        script_policy="", resize_script="")
    preview = template.substitute(values, view_class="preview",
        preview_open='<details class="inline-report"><summary>Read report &amp; explore evidence <span>↗</span></summary><div class="inline-content">',
        preview_close="</div></details>", script_policy=f"; script-src 'sha256-{_RESIZE_HASH}'",
        resize_script="<script>" + _RESIZE_SCRIPT + "</script>")
    return {"title": title, "report_id": report_id, "html": html, "preview_html": preview}
