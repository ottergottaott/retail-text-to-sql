"""Only trusted code can bind logical tables to physical data sources.

No generated SQL is ever passed directly to BigQuery. Fully qualified names,
table functions, scripts and unapproved SQL functions are rejected.
"""
import datetime as dt
import json
import time
import threading
import duckdb
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope
from .security import PolicyError, label, clean

SCHEMA = {
    "products": {"id": "INT", "name": "VARCHAR", "category": "VARCHAR", "brand": "VARCHAR", "department": "VARCHAR", "retail_price": "DOUBLE", "cost": "DOUBLE"},
    "order_items": {"item_key": "VARCHAR", "order_key": "VARCHAR", "customer_key": "VARCHAR", "product_id": "INT", "status": "VARCHAR", "created_at": "TIMESTAMP", "sale_price": "DOUBLE"},
    "orders": {"order_key": "VARCHAR", "customer_key": "VARCHAR", "status": "VARCHAR", "created_at": "TIMESTAMP"},
    "users": {"customer_key": "VARCHAR", "state": "VARCHAR", "country": "VARCHAR", "age_band": "VARCHAR"},
}
FUNCTIONS = {"COUNT", "SUM", "AVG", "MIN", "MAX", "ROUND", "ABS", "COALESCE", "NULLIF", "CAST", "TRY_CAST", "DATE", "DATE_TRUNC", "TIMESTAMP_TRUNC", "EXTRACT", "CURRENT_DATE", "CURRENT_TIMESTAMP", "DATE_SUB", "DATE_ADD", "TIMESTAMP_SUB", "TIMESTAMP_ADD", "LOWER", "UPPER", "ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD", "SAFE_DIVIDE", "IF", "CASE", "IFNULL", "GREATEST", "LEAST", "FLOOR", "CEIL"}
SENSITIVE_COLUMNS = {"email", "first_name", "last_name", "phone", "phone_number",
    "street_address", "postal_code", "ip_address", "latitude", "longitude",
    "user_id", "customer_id"}


class QueryError(Exception):
    pass


class QueryUnavailable(Exception):
    """Dependency/configuration failure; SQL repair cannot fix this."""


def validate(sql):
    try:
        trees = sqlglot.parse(sql, read="bigquery")
        if len(trees) != 1 or not isinstance(trees[0], (exp.Select, exp.Union)):
            raise PolicyError("Only a single analytical SELECT query is allowed.")
        tree = trees[0]
        if len(list(tree.walk())) > 1200:
            raise PolicyError("Query complexity limit exceeded.")
        if tree.find(exp.Into) or tree.find(exp.Lock) or tree.find(exp.Command):
            raise PolicyError("Unsupported query operation.")
        for fn in tree.find_all(exp.Func):
            # SQLGlot models these boolean operators as Func subclasses.
            # They combine validated predicates; their children are still walked.
            if isinstance(fn, (exp.And, exp.Or, exp.Not)):
                continue
            if isinstance(fn, exp.Anonymous) or fn.sql_name() not in FUNCTIONS:
                raise PolicyError("Unsupported SQL function.")
        for table in tree.find_all(exp.Table):
            if table.catalog or table.db or not isinstance(table.this, exp.Identifier):
                raise PolicyError("Only logical analytical tables are accessible.")
        # A privacy violation is terminal; it must not become a repairable
        # unknown-column error from the schema resolver below.
        if any(column.name.casefold() in SENSITIVE_COLUMNS for column in tree.find_all(exp.Column)):
            raise PolicyError("Sensitive and raw customer fields are outside the analytical schema.")
        # Resolve CTE scopes, aliases and nested subqueries; reject missing columns.
        tree = qualify(tree, dialect="bigquery", schema=SCHEMA, validate_qualify_columns=True)
        base = []
        for scope in traverse_scope(tree):
            for _, (_, source) in scope.selected_sources.items():
                if isinstance(source, exp.Table):
                    if source.name not in SCHEMA:
                        raise PolicyError("Table is outside the analytical schema.")
                    base.append(source)
        if not base:
            raise PolicyError("An analytical query must use an approved table.")
        return tree, base
    except PolicyError:
        raise
    except Exception:
        # Never forward SQLGlot's raw diagnostic, which may quote sensitive literals.
        raise QueryError("SQL could not be resolved against the approved schema. Check columns, aliases and aggregation.") from None


def physical_sources(config):
    dataset = "bigquery-public-data.thelook_ecommerce"
    # Parameter values are supplied separately, never interpolated into SQL.
    def key(field):
        return f"TO_HEX(SHA256(CONCAT(@label_salt, CAST({field} AS STRING))))"
    scoped_items = f"SELECT * FROM `{dataset}.order_items` WHERE product_id IN UNNEST(@products)"
    return {
        "products": f"SELECT id,name,category,brand,department,retail_price,cost FROM `{dataset}.products` WHERE id IN UNNEST(@products)",
        "order_items": f"SELECT {key('id')} AS item_key,{key('order_id')} AS order_key,{key('user_id')} AS customer_key,product_id,status,created_at,sale_price FROM ({scoped_items})",
        "orders": f"SELECT {key('o.order_id')} AS order_key,{key('o.user_id')} AS customer_key,o.status,o.created_at FROM `{dataset}.orders` o WHERE EXISTS (SELECT 1 FROM ({scoped_items}) i WHERE i.order_id=o.order_id)",
        "users": f"SELECT {key('u.id')} AS customer_key,u.state,u.country,CONCAT(CAST(DIV(u.age,10)*10 AS STRING), 's') AS age_band FROM `{dataset}.users` u WHERE EXISTS (SELECT 1 FROM ({scoped_items}) i WHERE i.user_id=u.id)",
    }


def bind(tree, sources):
    tree = tree.copy()
    for scope in traverse_scope(tree):
        for alias, (_, source) in scope.selected_sources.items():
            if isinstance(source, exp.Table):
                relation = sqlglot.parse_one(sources[source.name], read="bigquery")
                source.replace(exp.Subquery(this=relation, alias=exp.TableAlias(this=exp.to_identifier(alias))))
    return tree


class Analytics:
    def __init__(self, config):
        self.config = config

    def execute(self, sql, principal, remaining_seconds=40):
        tree, _ = validate(sql)
        start = time.monotonic()
        if remaining_seconds <= 0:
            raise QueryUnavailable("Query time budget exhausted. No result was inferred.")
        if self.config.retail_mode == "fixture":
            rows = self.fixture(tree, principal, remaining_seconds)
            self.check_payload(rows[:self.config.max_rows])
            return {"rows": rows[:self.config.max_rows], "mode": "fixture", "job_id": None, "bytes_processed": None, "sql": tree.sql(dialect="bigquery"), "truncated": len(rows) > self.config.max_rows, "seconds": time.monotonic() - start}
        from google.cloud import bigquery
        client = None
        bound = bind(tree, physical_sources(self.config))
        wrapped = f"SELECT * FROM ({bound.sql(dialect='bigquery')}) LIMIT {self.config.max_rows + 1}"
        parameters = [bigquery.ArrayQueryParameter("products", "INT64", list(principal.products)), bigquery.ScalarQueryParameter("label_salt", "STRING", label(0, principal.user_id, self.config.label_secret))]
        cfg = bigquery.QueryJobConfig(query_parameters=parameters, use_legacy_sql=False, maximum_bytes_billed=self.config.maximum_bytes_billed)
        job = None
        deadline = start + remaining_seconds
        def timeout(cap):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise QueryUnavailable("Query time budget exhausted. No result was inferred.")
            return min(cap, remaining)
        try:
            client = bigquery.Client(project=self.config.google_cloud_project)
            cfg.dry_run = True
            dry = client.query(wrapped, job_config=cfg, timeout=timeout(15), retry=None, job_retry=None)
            if dry.total_bytes_processed and dry.total_bytes_processed > self.config.maximum_bytes_billed:
                raise PolicyError("Query exceeds the configured byte budget.")
            cfg.dry_run = False
            cfg.job_timeout_ms = max(1, int(timeout(40) * 1000))
            job = client.query(wrapped, job_config=cfg, timeout=timeout(15), retry=None, job_retry=None)
            rows = [dict(r) for r in job.result(timeout=timeout(40), max_results=self.config.max_rows + 1, retry=None, job_retry=None)]
            payload = json.loads(json.dumps(rows, default=str))
            self.check_payload(payload[:self.config.max_rows])
            return {"rows": payload[:self.config.max_rows], "mode": "live", "job_id": job.job_id, "bytes_processed": job.total_bytes_processed, "estimated_bytes": dry.total_bytes_processed, "sql": tree.sql(dialect="bigquery"), "truncated": len(rows) > self.config.max_rows, "seconds": time.monotonic() - start}
        except PolicyError:
            raise
        except Exception as e:
            if job:
                try:
                    job.cancel(retry=None, timeout=2)
                except Exception:
                    pass
            # Service messages can contain SQL literals; expose categories only.
            if type(e).__name__ == "BadRequest":
                raise QueryError("BigQuery rejected the query. Check supported types and SQL syntax.") from None
            raise QueryUnavailable("BigQuery unavailable, timed out, or access not configured. No results were inferred.") from None
        finally:
            if client:
                client.close()

    def check_payload(self, rows):
        serialized = json.dumps(rows)
        if len(serialized.encode()) > self.config.max_result_bytes:
            raise PolicyError("Query result exceeds the response-size budget. Request a smaller aggregation.")
        if clean(serialized) != serialized:
            raise PolicyError("Query result failed the disclosure check.")

    def fixture(self, tree, principal, remaining_seconds):
        """Deterministic approved-schema fixtures, never claimed as BigQuery."""
        deadline = time.monotonic() + remaining_seconds
        c = duckdb.connect()
        timer = None
        try:
            for table, columns in SCHEMA.items():
                c.execute(f"CREATE TABLE {table} ({','.join(k+' '+v for k,v in columns.items())})")
            products = [(1, "Trail Jacket", "Outerwear", "North", "Men", 100., 40.), (2, "City Jacket", "Outerwear", "South", "Women", 80., 30.), (3, "Hidden Boots", "Footwear", "West", "Men", 200., 70.)]
            for p in products:
                if p[0] in principal.products:
                    c.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?)", p)
            for i in range(1, 25):
                pid = (i - 1) % 3 + 1
                if pid not in principal.products:
                    continue
                customer = label(i % 6, principal.user_id, self.config.label_secret)
                order = label(1000 + i, principal.user_id, self.config.label_secret)
                item = label(2000 + i, principal.user_id, self.config.label_secret)
                date = dt.datetime(2026, 1 if i <= 12 else 2, i % 12 + 1)
                status = "Returned" if i % 8 == 0 else "Complete"
                c.execute("INSERT INTO order_items VALUES (?,?,?,?,?,?,?)", [item, order, customer, pid, status, date, float(pid * 10)])
                c.execute("INSERT INTO orders VALUES (?,?,?,?)", [order, customer, status, date])
            users = c.execute("SELECT DISTINCT customer_key FROM orders").fetchall()
            for (customer,) in users:
                c.execute("INSERT INTO users VALUES (?,?,?,?)", [customer, "California", "United States", "30s"])
            query = tree.sql(dialect="duckdb")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise QueryUnavailable("Query time budget exhausted. No result was inferred.")
            timer = threading.Timer(remaining, c.interrupt)
            timer.daemon = True
            timer.start()
            result = c.execute(f"SELECT * FROM ({query}) LIMIT {self.config.max_rows + 1}")
            columns = [r[0] for r in result.description]
            rows = [dict(zip(columns, r)) for r in result.fetchall()]
            return json.loads(json.dumps(rows, default=str))
        except duckdb.InterruptException:
            raise QueryUnavailable("Query time budget exhausted. No result was inferred.") from None
        except duckdb.Error:
            raise QueryError("Fixture SQL execution failed. Check SQL types, functions and grouping.") from None
        finally:
            if timer:
                timer.cancel()
                timer.join()
            c.close()
