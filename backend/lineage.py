from datetime import datetime, timezone
from uuid import uuid4


def create_query_id():
    return f"qry_{uuid4().hex[:12]}"


def build_lineage(query_id, question, tables, relationships, plan, sql):
    return {
        "query_id": query_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "retrieved_tables": tables,
        "relationships": relationships,
        "planner_intent": plan.get("intent"),
        "entity": plan.get("entity"),
        "filters": plan.get("filters", []),
        "joins": plan.get("joins", []),
        "sql": sql,
    }
