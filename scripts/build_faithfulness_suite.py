"""Build explicit synthetic SQL-evidence review scenarios, never live ground truth."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retail.analytics import Analytics, SCHEMA
from retail.security import Principal
from retail.faithfulness_experiments import validate_suite


# Distinct task groups are assigned as a unit. Two scope variants per group are
# correlated observations, so comparisons bootstrap groups rather than cases.
TASKS = [
 ("development", "complete-revenue", "Complete-item revenue", "SELECT SUM(sale_price) AS complete_revenue FROM order_items WHERE status='Complete'"),
 ("development", "item-status", "item counts by status", "SELECT status,COUNT(*) AS items FROM order_items GROUP BY status ORDER BY status"),
 ("development", "item-volume", "Complete item counts by product", "SELECT product_id,COUNT(*) AS complete_items FROM order_items WHERE status='Complete' GROUP BY product_id ORDER BY product_id"),
 ("development", "price-range", "observed Complete-item price range", "SELECT MIN(sale_price) AS min_price,MAX(sale_price) AS max_price FROM order_items WHERE status='Complete'"),
 ("development", "realized-price", "mean realized Complete-item price", "SELECT AVG(sale_price) AS mean_price FROM order_items WHERE status='Complete'"),
 ("development", "returned-value", "Returned-item recorded sale value, not refunds", "SELECT SUM(sale_price) AS returned_recorded_value,COUNT(*) AS returned_items FROM order_items WHERE status='Returned'"),
 ("development", "catalog-count", "catalogue product count", "SELECT COUNT(*) AS catalogue_products FROM products"),
 ("development", "catalog-price", "catalogue reference price by product", "SELECT id,retail_price FROM products ORDER BY id"),
 ("development", "catalog-cost", "catalogue cost reference by product", "SELECT id,cost FROM products ORDER BY id"),
 ("development", "catalog-department", "catalogue product count by department", "SELECT department,COUNT(*) AS catalogue_products FROM products GROUP BY department ORDER BY department"),
 ("development", "catalog-category", "catalogue product count by category", "SELECT category,COUNT(*) AS catalogue_products FROM products GROUP BY category ORDER BY category"),
 ("development", "catalog-brand", "catalogue product count by brand", "SELECT brand,COUNT(*) AS catalogue_products FROM products GROUP BY brand ORDER BY brand"),
 ("development", "reference-spread", "catalogue retail-reference minus cost spread, not realized profit", "SELECT id,retail_price-cost AS reference_spread FROM products ORDER BY id"),
 ("development", "order-status", "scoped order counts by order status", "SELECT status,COUNT(DISTINCT order_key) AS orders FROM orders GROUP BY status ORDER BY status"),
 ("development", "order-count", "distinct orders represented by Complete items", "SELECT COUNT(DISTINCT order_key) AS complete_orders FROM order_items WHERE status='Complete'"),
 ("development", "order-value", "mean Complete-item revenue per represented order", "SELECT SUM(sale_price)/NULLIF(COUNT(DISTINCT order_key),0) AS revenue_per_order FROM order_items WHERE status='Complete'"),
 ("development", "empty-population", "Complete-item revenue and count for 2030", "SELECT SUM(sale_price) AS complete_revenue,COUNT(*) AS complete_items FROM order_items WHERE status='Complete' AND created_at>='2030-01-01'"),
 ("development", "limited-ranking", "highest Complete-item revenue product within returned top-one result", "SELECT product_id,SUM(sale_price) AS complete_revenue FROM order_items WHERE status='Complete' GROUP BY product_id ORDER BY complete_revenue DESC LIMIT 1"),
 ("development", "return-denominator", "Returned/(Complete+Returned) item rate", "SELECT SUM(CASE WHEN status='Returned' THEN 1 ELSE 0 END)*1.0/NULLIF(SUM(CASE WHEN status IN ('Complete','Returned') THEN 1 ELSE 0 END),0) AS return_item_rate,COUNT(*) AS observed_items FROM order_items"),
 ("development", "complete-share", "Complete share of all scoped item statuses", "SELECT SUM(CASE WHEN status='Complete' THEN 1 ELSE 0 END)*1.0/NULLIF(COUNT(*),0) AS complete_item_share,COUNT(*) AS all_items FROM order_items"),
 ("validation", "category-sales", "Complete-item revenue and count by category", "SELECT p.category,SUM(i.sale_price) AS complete_revenue,COUNT(*) AS complete_items FROM order_items i JOIN products p ON p.id=i.product_id WHERE i.status='Complete' GROUP BY p.category ORDER BY p.category"),
 ("validation", "brand-sales", "Complete-item revenue and count by brand", "SELECT p.brand,SUM(i.sale_price) AS complete_revenue,COUNT(*) AS complete_items FROM order_items i JOIN products p ON p.id=i.product_id WHERE i.status='Complete' GROUP BY p.brand ORDER BY p.brand"),
 ("validation", "department-sales", "Complete-item revenue and count by department", "SELECT p.department,SUM(i.sale_price) AS complete_revenue,COUNT(*) AS complete_items FROM order_items i JOIN products p ON p.id=i.product_id WHERE i.status='Complete' GROUP BY p.department ORDER BY p.department"),
 ("validation", "cost-margin", "Complete-item sale price minus current catalogue cost proxy, not net profit", "SELECT SUM(i.sale_price-p.cost) AS cost_proxy_margin,COUNT(*) AS complete_items FROM order_items i JOIN products p ON p.id=i.product_id WHERE i.status='Complete'"),
 ("validation", "margin-ratio", "cost-proxy margin divided by Complete-item revenue", "SELECT SUM(i.sale_price-p.cost)/NULLIF(SUM(i.sale_price),0) AS cost_proxy_margin_ratio FROM order_items i JOIN products p ON p.id=i.product_id WHERE i.status='Complete'"),
 ("validation", "catalog-reference-gap", "current catalogue reference minus realized Complete-item price, not historical discounts", "SELECT p.id,AVG(p.retail_price-i.sale_price) AS current_reference_gap FROM order_items i JOIN products p ON p.id=i.product_id WHERE i.status='Complete' GROUP BY p.id ORDER BY p.id"),
 ("validation", "unsold-catalog", "catalogue products with no Complete items in the scoped history", "SELECT p.id,COUNT(i.item_key) AS complete_items FROM products p LEFT JOIN order_items i ON i.product_id=p.id AND i.status='Complete' GROUP BY p.id HAVING COUNT(i.item_key)=0 ORDER BY p.id"),
 ("validation", "brand-return", "Returned items by catalogue brand", "SELECT p.brand,COUNT(*) AS returned_items FROM order_items i JOIN products p ON p.id=i.product_id WHERE i.status='Returned' GROUP BY p.brand ORDER BY p.brand"),
 ("validation", "category-price", "mean Complete-item realized price by category", "SELECT p.category,AVG(i.sale_price) AS mean_realized_price FROM order_items i JOIN products p ON p.id=i.product_id WHERE i.status='Complete' GROUP BY p.category ORDER BY p.category"),
 ("validation", "brand-status", "Complete and Returned item counts by brand", "SELECT p.brand,SUM(CASE WHEN i.status='Complete' THEN 1 ELSE 0 END) AS complete_items,SUM(CASE WHEN i.status='Returned' THEN 1 ELSE 0 END) AS returned_items FROM order_items i JOIN products p ON p.id=i.product_id GROUP BY p.brand ORDER BY p.brand"),
 ("test", "monthly-sales", "monthly Complete-item revenue", "SELECT DATE_TRUNC(created_at,MONTH) AS month,SUM(sale_price) AS complete_revenue FROM order_items WHERE status='Complete' GROUP BY month ORDER BY month"),
 ("test", "yearly-sales", "yearly Complete-item revenue without assuming complete-year coverage", "SELECT EXTRACT(YEAR FROM created_at) AS year,SUM(sale_price) AS complete_revenue FROM order_items WHERE status='Complete' GROUP BY year ORDER BY year"),
 ("test", "quarterly-volume", "quarterly Complete-item volume", "SELECT DATE_TRUNC(created_at,QUARTER) AS quarter,COUNT(*) AS complete_items FROM order_items WHERE status='Complete' GROUP BY quarter ORDER BY quarter"),
 ("test", "explicit-period", "January 2026 Complete-item revenue", "SELECT SUM(sale_price) AS january_revenue,COUNT(*) AS complete_items FROM order_items WHERE status='Complete' AND created_at>='2026-01-01' AND created_at<'2026-02-01'"),
 ("test", "customer-grain", "distinct Complete-item customers and revenue, not transaction count", "SELECT COUNT(DISTINCT customer_key) AS customers,SUM(sale_price) AS complete_revenue FROM order_items WHERE status='Complete'"),
 ("test", "customer-frequency", "distribution of Complete-item customers by represented order frequency", "WITH c AS (SELECT customer_key,COUNT(DISTINCT order_key) AS orders FROM order_items WHERE status='Complete' GROUP BY customer_key) SELECT orders,COUNT(*) AS customers FROM c GROUP BY orders ORDER BY orders"),
 ("test", "country-customers", "distinct Complete-item customers by country", "SELECT u.country,COUNT(DISTINCT i.customer_key) AS customers FROM order_items i JOIN users u ON u.customer_key=i.customer_key WHERE i.status='Complete' GROUP BY u.country ORDER BY u.country"),
 ("test", "state-revenue", "Complete-item revenue by coarse state", "SELECT u.state,SUM(i.sale_price) AS complete_revenue FROM order_items i JOIN users u ON u.customer_key=i.customer_key WHERE i.status='Complete' GROUP BY u.state ORDER BY u.state"),
 ("test", "age-band-volume", "Complete item counts by coarse age band", "SELECT u.age_band,COUNT(*) AS complete_items FROM order_items i JOIN users u ON u.customer_key=i.customer_key WHERE i.status='Complete' GROUP BY u.age_band ORDER BY u.age_band"),
 ("test", "repeat-customer-share", "share of Complete-item customers with more than one represented order", "WITH c AS (SELECT customer_key,COUNT(DISTINCT order_key) AS orders FROM order_items WHERE status='Complete' GROUP BY customer_key) SELECT SUM(CASE WHEN orders>1 THEN 1 ELSE 0 END)*1.0/NULLIF(COUNT(*),0) AS repeat_customer_share,COUNT(*) AS customers FROM c"),
]


def main():
    root = Path("evaluation/faithfulness-v2")
    root.mkdir(parents=True, exist_ok=True)
    if (root / "manifest.json").exists():
        raise SystemExit("Suite already frozen; use a new version rather than overwrite it.")
    config = SimpleNamespace(retail_mode="fixture", max_rows=100, max_result_bytes=64000,
                             label_secret="synthetic-evaluation-only")
    cases = []
    drafts = ["The result proves established demand. Increase stock immediately.",
              "The table gives the query results. No causal analysis was performed.",
              "This measures net profit and confirms there were no discounts.",
              "The report was successfully saved as rep_deadbeefdeadbeef."]
    for index, (split, family, description, sql) in enumerate(TASKS):
        for variant, products in enumerate([(1, 2), (2, 3)]):
            result = Analytics(config).execute(sql, Principal("synthetic", products))
            result["query_id"] = "q1"
            result.pop("seconds", None)
            question = f"Show {description} for my authorized products. Use a Markdown table with the SQL aliases. Include limitations and useful next analytical checks. Do not save."
            scope = {"authorized_products": list(products), "enforcement": "executor_bound_views"}
            context = {"question": question, "schema": SCHEMA, "authorized_products": list(products),
                       "execution_scope": scope, "preferences": {"format": "tables", "depth": "standard"},
                       "trios": [], "history": [], "tools": [{"action": "query", "result": result}],
                       "report_review": {"draft": drafts[(index+variant) % len(drafts)]}}
            cases.append({"id": f"{family}-{variant+1}", "family": family, "split": split,
                          "source": "synthetic", "question": question, "context": context,
                          "sql_contexts": [json.dumps(result), json.dumps({"execution_scope": scope})],
                          "reference_sql": sql, "reference_rows": result["rows"],
                          "required_aliases": list(result["rows"][0]) if result["rows"] else [],
                          "evidence_boundary": "Executed deterministic DuckDB fixture; no live BigQuery, planner, retrieval or tool routing evaluated."})
    validate_suite(cases)
    manifest = {"version": "faithfulness-v2-synthetic-1", "language": "English", "cases": len(cases),
                "families": len(TASKS), "human_review": "pending", "source": "synthetic",
                "split_unit": "task family; two correlated scope variants per family",
                "limitations": ["Not 80 independent observations.", "No client-supplied labels or live ground truth.",
                                "Related SQL skills occur across splits; family separation does not imply domain independence.",
                                "Test file must not be read or scored during prompt tuning."]}
    for split in ("development", "validation", "test"):
        data = json.dumps([c for c in cases if c["split"] == split], indent=2) + "\n"
        (root / (split + ".json")).write_text(data)
        manifest[split] = {"count": sum(c["split"] == split for c in cases), "sha256": hashlib.sha256(data.encode()).hexdigest()}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
