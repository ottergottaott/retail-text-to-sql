import pytest
from retail.analytics import Analytics
from retail.config import Settings
from retail.security import principal_for, PolicyError


@pytest.mark.parametrize('sql', [
    'SELECT customer_key, state FROM users',
    "SELECT customer_key FROM users WHERE age_band = '30s'",
    'SELECT MIN(customer_key) AS customer FROM users GROUP BY state',
    'SELECT state, customer_key, COUNT(*) AS n FROM users GROUP BY state, customer_key',
    'WITH x AS (SELECT state AS s, customer_key AS k FROM users) SELECT s, k FROM x',
    'SELECT state, COUNT(*) OVER (PARTITION BY state) AS n FROM users',
    'SELECT state, COUNT(*) AS n FROM users GROUP BY state UNION ALL SELECT state, COUNT(*) FROM users GROUP BY state',
    "SELECT customer_key, SUM(sale_price) AS spend FROM order_items WHERE customer_key IN (SELECT customer_key FROM users WHERE age_band = '30s') GROUP BY customer_key",
    'SELECT u.state, MIN(i.sale_price) AS spend FROM users u CROSS JOIN order_items i GROUP BY u.state',
    'SELECT u.state, SUM(i.sale_price) AS spend FROM users u JOIN order_items i ON 1=1 GROUP BY u.state',
])
def test_individual_demographics_and_nested_bypasses_denied(sql):
    config = Settings()
    with pytest.raises(PolicyError):
        Analytics(config).execute(sql, principal_for('alice', config))


def test_cohort_counts_distinct_people_not_joined_item_rows():
    # Alice has sixteen item rows, but just four distinct customers.
    sql = 'SELECT u.state, COUNT(*) AS items FROM users u JOIN order_items i ON u.customer_key=i.customer_key GROUP BY u.state'
    config = Settings()
    assert Analytics(config).execute(sql, principal_for('alice', config))['rows'] == []
    config = config.model_copy(update={'minimum_cohort_size': 4})
    result = Analytics(config).execute(sql, principal_for('alice', config))
    assert result['rows'] == [{'state': 'California', 'items': 16}]
    assert 'COUNT(DISTINCT' in result['sql']


def test_ceo_keeps_same_cohort_rule():
    config = Settings(brand_access_json='{"ceo":{"role":"ceo"}}', minimum_cohort_size=7)
    assert Analytics(config).execute('SELECT state, COUNT(*) AS n FROM users GROUP BY state',
        principal_for('ceo', config))['rows'] == []


def test_non_demographic_customer_ranking_still_allowed():
    config = Settings()
    rows = Analytics(config).execute('SELECT customer_key, SUM(sale_price) AS spend FROM order_items GROUP BY customer_key',
        principal_for('alice', config))['rows']
    assert len(rows) == 4
    assert all(set(row) == {'customer_key', 'spend'} for row in rows)


def test_exactly_five_customers_are_released():
    from retail.security import label
    config = Settings(brand_access_json='{"ceo":{"role":"ceo"}}')
    key = label(0, 'ceo', config.label_secret)
    result = Analytics(config).execute(f"SELECT state, COUNT(*) AS customers FROM users WHERE customer_key != '{key}' GROUP BY state",
        principal_for('ceo', config))
    assert result['rows'] == [{'state': 'California', 'customers': 5}]
