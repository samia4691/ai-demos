"""
text_to_sql.py  —  natural-language questions to SAFE SQL over a known schema.

The "let users ask our database questions" job. The value is not generating SQL, any model does
that. The value is the safety rail so a question can never drop a table, read another tenant's
rows, or return an unbounded scan:

  schema-aware planning -> validate columns/tables exist -> enforce READ-ONLY ->
  force a tenant filter -> cap rows -> parameterize values (no string-concat injection)

Runs offline: the planner is a small deterministic stub. Swap it for a model call that must
return the same {tables, columns, filters} plan; every guard below still applies.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re

SCHEMA = {
    "orders":   {"id", "tenant_id", "customer", "amount", "status", "created_at"},
    "customers": {"id", "tenant_id", "name", "email", "region"},
}
FORBIDDEN = re.compile(r"\b(drop|delete|update|insert|alter|truncate|grant|;--)\b", re.I)


@dataclass
class Plan:
    table: str
    columns: list[str]
    filters: dict = field(default_factory=dict)   # column -> value (parameterized)
    limit: int = 100


class SQLSafetyError(Exception):
    pass


def validate_plan(plan: Plan, tenant_id: str) -> None:
    if plan.table not in SCHEMA:
        raise SQLSafetyError(f"unknown table '{plan.table}'")
    cols = SCHEMA[plan.table]
    for c in plan.columns:
        if c != "*" and c not in cols:
            raise SQLSafetyError(f"unknown column '{c}' on {plan.table}")
    for c in plan.filters:
        if c not in cols:
            raise SQLSafetyError(f"filter on unknown column '{c}'")
    if "tenant_id" not in cols:
        raise SQLSafetyError(f"table '{plan.table}' has no tenant_id — refuse to query")
    if not (1 <= plan.limit <= 1000):
        raise SQLSafetyError("limit must be 1..1000 (no unbounded scans)")


def build_sql(plan: Plan, tenant_id: str) -> tuple[str, list]:
    validate_plan(plan, tenant_id)
    cols = ", ".join(plan.columns) if plan.columns else "*"
    where = ["tenant_id = %s"]          # tenant filter is ALWAYS injected
    params = [tenant_id]
    for c, v in plan.filters.items():
        where.append(f"{c} = %s")       # parameterized — never string-concatenated
        params.append(v)
    sql = f"SELECT {cols} FROM {plan.table} WHERE {' AND '.join(where)} LIMIT {plan.limit}"
    if FORBIDDEN.search(sql):           # belt-and-suspenders on the final string
        raise SQLSafetyError("forbidden keyword in generated SQL")
    return sql, params


def stub_planner(question: str) -> Plan:
    q = question.lower()
    if "open orders" in q:
        return Plan("orders", ["id", "customer", "amount"], {"status": "open"}, limit=50)
    if "customers in" in q:
        region = q.split("customers in")[-1].strip().strip("?").title()
        return Plan("customers", ["id", "name", "email"], {"region": region})
    if "drop" in q or "delete" in q:
        return Plan("orders", ["*"], {}, limit=1)   # even if asked, guards will keep it read-only
    return Plan("orders", ["*"], {}, limit=10)


def answer(question: str, tenant_id: str) -> dict:
    plan = stub_planner(question)
    try:
        sql, params = build_sql(plan, tenant_id)
        return {"ok": True, "sql": sql, "params": params}
    except SQLSafetyError as e:
        return {"ok": False, "error": str(e)}


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import json
    for q in ["Show me open orders",
              "customers in europe",
              "Please DROP TABLE orders"]:
        print(q, "->", json.dumps(answer(q, tenant_id="acme")))

    # A malformed plan (hallucinated column) is caught by validation, never executed:
    try:
        build_sql(Plan("orders", ["ssn"]), tenant_id="acme")
    except SQLSafetyError as e:
        print("bad column ->", json.dumps({"ok": False, "error": str(e)}))
