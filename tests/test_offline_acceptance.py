import json
from pathlib import Path

from retail.evaluate import run


def test_documented_offline_evaluation_matches_current_privacy_policy():
    root = Path('evaluation')
    report = run(json.loads((root/'sql-cases.json').read_text()),
                 json.loads((root/'retrieval-cases.json').read_text()))
    assert report['summary']['failed'] == 0, [
        case for case in report['cases'] if case['status'] == 'failed']
    state = next(case for case in report['cases'] if case['name'] == 'Alice customer-state spend')
    assert state['detail']['actual_rows'] == []  # Four customers are below the default cohort of five.
