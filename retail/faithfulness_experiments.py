"""Validation and paired analysis for bounded, offline report experiments."""
import math
import random
import re
from decimal import Decimal, InvalidOperation

from .security import safe_output


def validate_suite(cases):
    import json
    if not isinstance(cases, list) or not 1 <= len(cases) <= 160:
        raise ValueError("Provide 1–160 cases.")
    ids, families = set(), {}
    for case in cases:
        if case.get("split") not in {"development", "validation", "test"}:
            raise ValueError("Invalid split.")
        if case.get("source") not in {"synthetic", "recorded_live_frozen"}:
            raise ValueError("Explicit synthetic or recorded_live_frozen source required.")
        if not isinstance(case.get("reference_rows"), list) or not isinstance(case.get("required_aliases"), list):
            raise ValueError("Explicit table oracle and aliases required.")
        aliases = case["required_aliases"]
        if len(aliases) != len(set(aliases)) or any(not isinstance(a, str) or not a for a in aliases):
            raise ValueError("Table aliases must be unique strings.")
        if case['reference_rows'] and (not aliases or any(not isinstance(row, dict) or set(row) != set(aliases) for row in case['reference_rows'])):
            raise ValueError("Every oracle row must exactly match the aliases.")
        for key in ("id", "family", "question"):
            if not isinstance(case.get(key), str) or not case[key].strip():
                raise ValueError("Case requires id, family and question.")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", case["id"]):
            raise ValueError("Case id must be a safe filename identifier.")
        if case["id"] in ids:
            raise ValueError("Duplicate case id.")
        ids.add(case["id"])
        if families.setdefault(case["family"], case["split"]) != case["split"]:
            raise ValueError("A family cannot cross splits.")
        if not isinstance(case.get("context"), dict) or not 1 <= len(case.get("sql_contexts", [])) <= 5:
            raise ValueError("Context and 1–5 evidence strings required.")
        if any(not isinstance(x, str) or not x.strip() for x in case["sql_contexts"]):
            raise ValueError("Evidence strings cannot be empty.")
        serialized = json.dumps(case)
        if len(serialized) > 64000:
            raise ValueError("Case exceeds context budget.")
        safe_output(serialized)
    return cases


def compare_runs(baseline, candidate, split="development", independent_review=False, sealed_test_passed=False):
    def index(rows):
        ids = [r["id"] for r in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate comparison ids.")
        return {r["id"]: r for r in rows}
    before, after = index(baseline), index(candidate)
    complete = bool(before) and before.keys() == after.keys()
    pairs = []
    for key in sorted(before.keys() & after.keys()):
        a, b = before[key].get("score"), after[key].get("score")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in (a, b)):
            complete = False
            continue
        pairs.append({"id": key, "delta": b-a, "family": before[key].get("family", key)})
    values = [p["delta"] for p in pairs]
    mean = sum(values) / len(values) if values else None
    groups = {}
    for pair in pairs:
        groups.setdefault(pair["family"], []).append(pair["delta"])
    rng = random.Random(20261122)
    labels = sorted(groups)
    boot = []
    if labels:
        for _ in range(2000):
            drawn = [v for key in rng.choices(labels, k=len(labels)) for v in groups[key]]
            boot.append(sum(drawn)/len(drawn))
    boot.sort()
    ci = [boot[49], boot[1949]] if boot else [None, None]
    checks = complete and all(r.get("checks_passed") is True for r in after.values())
    score_gate = bool(checks and len(labels) >= 5 and ci[0] > 0)
    return {"complete": complete, "paired_cases": len(pairs), "mean_delta": mean,
            "delta_ci95": ci, "ci_method": "2000 family-cluster paired bootstrap; seed=20261122",
            "improved": sum(x > 0 for x in values), "regressed": sum(x < 0 for x in values),
            "unchanged": sum(x == 0 for x in values), "pairs": pairs,
            "paired_score_gate_passed": score_gate,
            "promotable": bool(score_gate and split == "validation" and independent_review and sealed_test_passed),
            "limitation": "Single-run judge uncertainty is not captured by case bootstrap. Promotion also requires independent review and sealed-test confirmation."}


def record_diagnostics(metric):
    """Observe the existing NLI call; prompts, calls and score computation unchanged."""
    original = metric._create_verdicts
    metric.diagnostics = None

    async def recorded(statements, context):
        metric.diagnostics = None
        verdicts = await original(statements, context)
        metric.diagnostics = verdicts.model_dump()
        return verdicts
    metric._create_verdicts = recorded
    return metric


def check_answer(case, answer):
    """Check requested table cells against the synthetic oracle, not prose accuracy."""
    lines = [line.strip() for line in answer.splitlines() if line.strip().startswith("|")]
    tables = []
    for index, line in enumerate(lines):
        cells = [x.strip().strip('`* ') for x in line.strip('|').split('|')]
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        tables.append(cells)
    aliases = case.get("required_aliases", [])
    header_index = next((i for i, row in enumerate(tables) if all(a in row for a in aliases)), None) if aliases else None
    rows = case.get("reference_rows", [])
    def equal(expected, actual):
        if expected is None:
            return actual.lower() in {"null", "none", "n/a", "—", "not available", "no data"}
        if isinstance(expected, (int, float)):
            try:
                value = Decimal(actual.replace(',', '').replace('$', '').replace('%', '').strip())
                if actual.endswith('%'):
                    value /= 100
                return abs(value - Decimal(str(expected))) <= Decimal('.005')
            except InvalidOperation:
                return False
        return str(expected) == actual or (bool(re.match(r'^\d{4}-\d{2}-\d{2}[ T]', str(expected))) and str(expected)[:10] == actual)
    values_ok = False
    if rows and header_index is not None:
        header, returned = tables[header_index], tables[header_index+1:]
        positions = [header.index(a) for a in aliases]
        remaining = list(returned)
        values_ok = len(returned) == len(rows) and len(header) == len(aliases)
        for ref in rows:
            match = next((i for i, row in enumerate(remaining) if len(row) == len(header)
                          and all(equal(ref[a], row[p]) for a, p in zip(aliases, positions))), None)
            if match is None:
                values_ok = False
                break
            remaining.pop(match)
    elif not rows:
        values_ok = bool(re.search(r"no (?:matching |returned )?(?:rows|results|data)|empty|zero rows", answer, re.I))
    sections = bool(re.search(r"limitations?", answer, re.I) and re.search(r"action|next (?:steps|checks)|proposed", answer, re.I))
    save_safe = not re.search(r"rep_[0-9a-f]+|successfully saved|has been saved|report was saved|\b(?:i|we) (?:have )?saved\b|\bsaved (?:as|to|in)\b", answer, re.I)
    return {"passed": values_ok and sections and save_safe, "oracle_table_covered": values_ok,
            "sections_present": sections, "no_false_save": save_safe,
            "boundary": "Deterministic coverage of expected table values and structure, not full factual correctness."}
