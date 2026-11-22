from scripts.verify_live_business import report_checks


def test_query_rows_and_save_alone_do_not_complete_business_report():
    answer = "Please clarify the metric and period you want analyzed.\n\n### Query evidence\n| avg_price |\n| 49 |\nSaved report."
    assert not all(report_checks(answer).values())
    complete = "Realized price was 49.\n### Limitations\nTiny sample.\n### Action items\nInvestigate with more data.\n### Query evidence\n| avg_price |\n| 49 |"
    assert all(report_checks(complete).values())
