import re

from metadata import extract_metadata


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALLOWED_OPERATORS = {
    "=",
    "!=",
    "<>",
    ">",
    ">=",
    "<",
    "<=",
    "LIKE",
}


def quote_identifier(identifier):
    if not IDENTIFIER_PATTERN.match(identifier):
        raise ValueError(
            f"Unsafe SQL identifier: {identifier}"
        )

    return f'"{identifier}"'


def quote_reference(reference):
    parts = reference.split(".")

    if len(parts) != 2:
        raise ValueError(
            f"Invalid column reference: {reference}"
        )

    return ".".join(
        quote_identifier(part)
        for part in parts
    )


def literal(value):
    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    if isinstance(value, (int, float)):
        return str(value)

    escaped = str(value).replace(
        "'",
        "''"
    )

    return f"'{escaped}'"


def normalize_operator(operator):
    normalized = str(
        operator or "="
    ).upper()

    if normalized not in ALLOWED_OPERATORS:
        raise ValueError(
            f"Unsupported operator: {operator}"
        )

    return normalized


def get_table_columns(table):
    metadata = extract_metadata()

    return [
        column[0]
        for column in metadata.get(
            table,
            []
        )
    ]


def build_where_clause(filters):
    if not filters:
        return ""

    conditions = []

    for filter_obj in filters:
        reference = (
            f"{filter_obj['table']}."
            f"{filter_obj['column']}"
        )

        conditions.append(
            f"{quote_reference(reference)} "
            f"{normalize_operator(filter_obj.get('operator'))} "
            f"{literal(filter_obj.get('value'))}"
        )

    return "WHERE " + " AND ".join(
        conditions
    )


def build_join_clause(joins, base_table):
    if not joins:
        return ""

    pending = list(joins)
    joined_tables = {base_table}
    clauses = []

    while pending:
        progress_made = False

        for join in pending[:]:
            left = join["left"]
            right = join["right"]
            left_table = left.split(".")[0]
            right_table = right.split(".")[0]

            if left_table in joined_tables and right_table not in joined_tables:
                clauses.append(
                    f"JOIN {quote_identifier(right_table)} "
                    f"ON {quote_reference(left)} = {quote_reference(right)}"
                )
                joined_tables.add(right_table)
                pending.remove(join)
                progress_made = True

            elif right_table in joined_tables and left_table not in joined_tables:
                clauses.append(
                    f"JOIN {quote_identifier(left_table)} "
                    f"ON {quote_reference(left)} = {quote_reference(right)}"
                )
                joined_tables.add(left_table)
                pending.remove(join)
                progress_made = True

            elif left_table in joined_tables and right_table in joined_tables:
                pending.remove(join)
                progress_made = True

        if not progress_made:
            raise ValueError(
                "Unable to compile joins from query plan"
            )

    return "\n".join(clauses)


def compile_count(plan):
    sql_parts = [
        "SELECT COUNT(*) AS total_count",
        f"FROM {quote_identifier(plan['entity'])}",
    ]

    joins = build_join_clause(
        plan.get("joins", []),
        plan["entity"]
    )

    where = build_where_clause(
        plan.get("filters", [])
    )

    if joins:
        sql_parts.append(joins)

    if where:
        sql_parts.append(where)

    return "\n".join(sql_parts)


def compile_list(plan):
    entity = plan["entity"]
    selected_columns = [
        f"{quote_identifier(entity)}.{quote_identifier(column)}"
        for column in get_table_columns(entity)
    ]

    if not selected_columns:
        raise ValueError(
            f"No selectable columns found for table: {entity}"
        )

    sql_parts = [
        "SELECT",
        "  " + ",\n  ".join(selected_columns),
        f"FROM {quote_identifier(entity)}",
    ]

    joins = build_join_clause(
        plan.get("joins", []),
        entity
    )

    where = build_where_clause(
        plan.get("filters", [])
    )

    if joins:
        sql_parts.append(joins)

    if where:
        sql_parts.append(where)

    sql_parts.append("LIMIT 100")

    return "\n".join(sql_parts)


def compile_aggregate(plan):
    group_by = plan["group_by"]
    metric_reference = (
        f"{plan['entity']}."
        f"{plan['metric']}"
    )

    sql_parts = [
        "SELECT",
        f"  {quote_reference(group_by)},",
        (
            f"  {plan['aggregation'].upper()}"
            f"({quote_reference(metric_reference)}) AS result"
        ),
        f"FROM {quote_identifier(plan['entity'])}",
    ]

    joins = build_join_clause(
        plan.get("joins", []),
        plan["entity"]
    )

    where = build_where_clause(
        plan.get("filters", [])
    )

    if joins:
        sql_parts.append(joins)

    if where:
        sql_parts.append(where)

    sql_parts.extend([
        f"GROUP BY {quote_reference(group_by)}",
        "ORDER BY result DESC",
        "LIMIT 100",
    ])

    return "\n".join(sql_parts)


def compile_sql(plan):
    intent = plan["intent"]

    if intent == "count":
        return compile_count(plan)

    if intent == "list":
        return compile_list(plan)

    if intent == "aggregate":
        return compile_aggregate(plan)

    raise ValueError(
        f"Unknown intent: {intent}"
    )
