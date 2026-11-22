"""Report display must preserve evidence without executing model-provided markup."""
from html.parser import HTMLParser

from retail.report_presentation import render_report


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags, self.text, self.attrs = [], [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(attrs)

    def handle_data(self, data):
        self.text.append(data)


def sample():
    return {"title": "Monthly revenue", "content": "## Findings\n\nCompleted sales only.\n\n| Month | Revenue |\n| --- | --- |\n| Jan | 98 |\n\n## Limitations\n\nTiny sample.\n\n### Query evidence\n\nDuplicate evidence text",
            "provenance": [{"query_id": "q1", "sql": "SELECT month, revenue FROM order_items", "rows": [{"month": "Jan", "revenue": 98}], "mode": "live", "truncated": True, "job_id": "job-1", "bytes_processed": 1024}]}


def test_report_displays_brand_scope_and_ceo_scope():
    body = {**sample(), 'brands': ['North', 'South'], 'products': []}
    assert 'Brands: North, South' in ' '.join(Document(render_report(body)['html']).text)
    body.update(all_brands=True)
    assert 'All brands' in ' '.join(Document(render_report(body)['html']).text)


def test_report_preserves_business_content_and_exposes_exact_sql_evidence():
    view = render_report(sample(), report_id="rep_test", created="2026-11-21T12:00:00Z")
    doc = Document(view["html"])
    text = " ".join(doc.text)
    assert "Monthly revenue" in text and "Completed sales only." in text
    assert "Tiny sample." in text and "Duplicate evidence text" not in text
    assert "SELECT month, revenue FROM order_items" in "".join(doc.text)
    assert "job-1" in text and "1,024" in text and "Truncated" in text
    assert "rep_test" in text and "Live BigQuery" in text
    assert doc.tags.count("table") == 2 and "details" in doc.tags
    assert "script" not in doc.tags
    assert "Snapshot" in " ".join(Document(view["preview_html"]).text)


def test_all_model_markup_data_and_metadata_are_inert():
    attack = '</code><script>alert(1)</script><img src=x onerror=alert(2)> ```html'
    body = sample()
    body.update(title=attack, content="## " + attack + "\n\n[click](javascript:alert(3))")
    body["provenance"][0].update(sql=attack, rows=[{attack: attack}], job_id=attack)
    view = render_report(body, report_id=attack, created=attack)
    for field in ("html", "preview_html"):
        doc = Document(view[field])
        assert not {"img", "iframe", "object", "form"}.intersection(doc.tags)
        assert doc.tags.count("script") == (1 if field == "preview_html" else 0)
        if field == "preview_html":
            assert 'script-src &#x27;sha256-' not in view[field]
            assert "script-src 'sha256-" in view[field]
        assert not any(k.startswith("on") or k in {"src", "srcdoc"} for k, _ in doc.attrs)
        assert not any(k == "href" and not v.startswith("#") for k, v in doc.attrs)
        assert "```" not in view[field]  # Cannot break the outer HTML Artifact fence.


def test_draft_fixture_and_empty_results_are_honestly_labeled():
    body = sample()
    body["provenance"] = [{"query_id": "q1", "mode": "fixture", "sql": "SELECT 1", "rows": [], "truncated": False}]
    view = render_report(body)
    text = " ".join(Document(view["html"]).text)
    assert "Fixture data" in text and "Not saved" in text
    assert "No rows returned" in text and "Live BigQuery" not in text
    assert "not recorded" in text.lower()


def test_embedded_preview_uses_only_a_hash_authorized_height_bridge():
    import base64
    import hashlib
    import re
    html = render_report(sample())["preview_html"]
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert len(scripts) == 1
    expected = base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
    assert "script-src 'sha256-" + expected + "'" in html
    assert "iframe:height" in scripts[0] and "ResizeObserver" in scripts[0]
    assert "connect-src" not in scripts[0] and "fetch(" not in scripts[0]


def test_revenue_chart_uses_returned_values_without_inventing_totals():
    body = sample()
    body["provenance"][0]["rows"] = [{"product_id": 1, "revenue": 49.0}, {"product_id": 2, "revenue": 69.5}]
    html = render_report(body)["html"]
    doc = Document(html)
    assert "svg" in doc.tags
    assert "49" in doc.text and "69.5" in doc.text
    assert "Revenue by product_id" in " ".join(doc.text)
    assert "118.5" not in html  # No synthetic total or interpretation.
    body["provenance"][0]["rows"][0]["product_name"] = "First product"
    body["provenance"][0]["rows"][1]["product_name"] = "Second product"
    named = render_report(body)["html"]
    assert "svg" in Document(named).tags and "First product" in named
    body["provenance"][0]["rows"][1]["revenue"] = -1
    assert "svg" not in Document(render_report(body)["html"]).tags


def test_sql_highlighting_is_lossless_and_escapes_every_token():
    from retail.report_presentation import highlight_sql
    sql = "-- SELECT <script>\nSELECT `project.dataset.table`, 'it''s <safe>', 12.5 FROM t WHERE x >= 2 /* end */"
    html = highlight_sql(sql)
    doc = Document(html)
    assert ''.join(doc.text) == sql
    assert set(doc.tags) == {'span'}
    for kind in ('keyword', 'string', 'number', 'comment', 'identifier'):
        assert ('class', 'sql-' + kind) in doc.attrs
    assert '<script>' not in html and '```' not in html
