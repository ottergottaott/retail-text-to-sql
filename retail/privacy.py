"""Conservative release policy for demographic SQL, enforced before execution.

Only flat grouped demographic queries are supported. Unsupported query shapes
are denied rather than relying on the model to supply a correct HAVING clause.
"""
from sqlglot import exp
from .security import PolicyError

DEMOGRAPHICS = {"city", "state", "country", "age", "age_band", "gender", "traffic_source"}
IDENTIFIERS = {"customer_key", "order_key", "item_key"}


def guard_demographics(tree, minimum):
    users = [t for t in tree.find_all(exp.Table) if t.name == "users"]
    if not users:
        return tree
    deny = "Demographics require grouped aggregates with a sufficient distinct-customer cohort. Individual demographic listings and complex demographic SQL are not supported."
    # This restriction also prevents filtered-customer subqueries from feeding
    # individual rankings in an outer query, and ambiguous join lineage.
    if (not isinstance(tree, exp.Select) or len(users) != 1 or
            tree.find(exp.With) or tree.find(exp.Subquery) or tree.find(exp.Window) or
            tree.find(exp.Union) or not tree.args.get("group")):
        raise PolicyError(deny)
    alias = users[0].alias_or_name
    relations = {t.alias_or_name: t.name for t in tree.find_all(exp.Table)}
    # Disconnected joins could inflate the cohort with unrelated customers.
    # Require each join to connect to a previously introduced relation using a
    # known key equality. Arbitrary ON predicates and outer joins fail closed.
    introduced = {tree.args["from_"].this.alias_or_name}
    for join in tree.args.get("joins", []):
        right = join.this.alias_or_name
        on = join.args.get("on")
        if join.args.get("side") or join.args.get("kind") not in {None, "", "INNER"} or on is None or on.find(exp.Or):
            raise PolicyError(deny)
        def conjuncts(node):
            if isinstance(node, exp.Paren):
                yield from conjuncts(node.this)
            elif isinstance(node, exp.And):
                yield from conjuncts(node.this)
                yield from conjuncts(node.expression)
            else:
                yield node
        connected = False
        for condition in conjuncts(on):
            if not isinstance(condition, exp.EQ):
                continue
            a, b = condition.this, condition.expression
            if not isinstance(a, exp.Column) or not isinstance(b, exp.Column):
                continue
            if a.table != right:
                a, b = b, a
            if a.table != right or b.table not in introduced:
                continue
            tables = {relations.get(a.table), relations.get(b.table)}
            same_customer = a.name == b.name == "customer_key" and tables <= {"users", "orders", "order_items"}
            same_order = a.name == b.name == "order_key" and tables == {"orders", "order_items"}
            product = ((relations.get(a.table), a.name, relations.get(b.table), b.name) in {
                ("products", "id", "order_items", "product_id"), ("order_items", "product_id", "products", "id")})
            connected |= same_customer or same_order or product
        if not connected:
            raise PolicyError(deny)
        introduced.add(right)
    groups = tree.args["group"].expressions
    if any(not isinstance(g, exp.Column) or g.name in IDENTIFIERS for g in groups):
        raise PolicyError(deny)
    grouped = {g.sql() for g in groups}
    for select in tree.expressions:
        value = select.this if isinstance(select, exp.Alias) else select
        if isinstance(value, exp.Column) and value.sql() in grouped:
            continue
        if not isinstance(value, (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)):
            raise PolicyError(deny)
        for col in value.find_all(exp.Column):
            if col.name in DEMOGRAPHICS or col.name in IDENTIFIERS:
                # Counting distinct pseudonyms is safe; printing their extrema,
                # concatenations or scalar transformations is not.
                if not (isinstance(value, exp.Count) and
                        isinstance(value.this, exp.Distinct) and
                        value.this.expressions == [col] and col.name == "customer_key"):
                    raise PolicyError(deny)
    # WHERE/JOIN/HAVING may filter but must not introduce further SELECTs.
    # A mandatory trusted guard is ANDed with (never replaced by) user HAVING.
    count = exp.Count(this=exp.Distinct(expressions=[exp.column("customer_key", table=alias)]))
    guard = exp.GTE(this=count, expression=exp.Literal.number(minimum))
    result = tree.copy()
    previous = result.args.get("having")
    result.set("having", exp.Having(this=exp.and_(previous.this, guard) if previous else guard))
    return result
