from metadata import extract_metadata
from relationships import get_relationships


ALLOWED_INTENTS = {
    "list",
    "count",
    "aggregate",
}

ALLOWED_AGGREGATIONS = {
    "",
    "COUNT",
    "SUM",
    "AVG",
    "MAX",
    "MIN",
}

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


def column_exists(metadata, table, column):
    return column in [
        col[0]
        for col in metadata.get(
            table,
            []
        )
    ]


def parse_reference(reference):
    parts = str(reference).split(".")

    if len(parts) != 2:
        return None, None

    return parts[0], parts[1]


def relationship_allowed(left, right):
    relationships = get_relationships()

    for rel in relationships:
        forward = (
            f"{rel['from_table']}.{rel['from_column']}",
            f"{rel['to_table']}.{rel['to_column']}",
        )
        reverse = (
            forward[1],
            forward[0],
        )

        if (left, right) in (forward, reverse):
            return True

    return False


def reachable_tables(entity, joins):
    reachable = {entity}
    pending = list(joins)

    while pending:
        progress_made = False

        for join in pending[:]:
            left_table, _ = parse_reference(
                join.get("left", "")
            )
            right_table, _ = parse_reference(
                join.get("right", "")
            )

            if left_table in reachable and right_table:
                reachable.add(right_table)
                pending.remove(join)
                progress_made = True
            elif right_table in reachable and left_table:
                reachable.add(left_table)
                pending.remove(join)
                progress_made = True

        if not progress_made:
            break

    return reachable


def add_check(checks, label):
    if label not in checks:
        checks.append(label)


def validate_query_plan(plan):
    metadata = extract_metadata()
    errors = []
    checks = []

    intent = plan.get("intent")
    entity = plan.get("entity")
    aggregation = str(
        plan.get("aggregation", "") or ""
    ).upper()
    joins = plan.get("joins", []) or []
    filters = plan.get("filters", []) or []

    if intent not in ALLOWED_INTENTS:
        errors.append(
            f"Unsupported intent '{intent}'"
        )

    if entity not in metadata:
        errors.append(
            f"Table '{entity}' does not exist"
        )
    else:
        add_check(
            checks,
            "Entity Valid"
        )

    join_errors_before = len(errors)

    for join in joins:
        left = join.get("left")
        right = join.get("right")
        left_table, left_column = parse_reference(left)
        right_table, right_column = parse_reference(right)

        if not left_table or not right_table:
            errors.append(
                f"Invalid join definition {join}"
            )
            continue

        if not column_exists(metadata, left_table, left_column):
            errors.append(
                f"Join column '{left}' not found"
            )

        if not column_exists(metadata, right_table, right_column):
            errors.append(
                f"Join column '{right}' not found"
            )

        if not relationship_allowed(left, right):
            errors.append(
                f"Join '{left} = {right}' is not an approved relationship"
            )

    if len(errors) == join_errors_before:
        add_check(
            checks,
            "Joins Valid"
        )

    reachable = reachable_tables(
        entity,
        joins
    )

    filter_errors_before = len(errors)

    for filter_obj in filters:
        table = filter_obj.get("table")
        column = filter_obj.get("column")
        operator = str(
            filter_obj.get("operator", "=")
        ).upper()

        if table not in metadata:
            errors.append(
                f"Filter table '{table}' not found"
            )
            continue

        if table not in reachable:
            errors.append(
                f"Filter table '{table}' is not reachable from entity '{entity}'"
            )

        if not column_exists(metadata, table, column):
            errors.append(
                f"Column '{column}' not found in table '{table}'"
            )

        if operator not in ALLOWED_OPERATORS:
            errors.append(
                f"Unsupported filter operator '{operator}'"
            )

    if len(errors) == filter_errors_before:
        add_check(
            checks,
            "Filters Valid"
        )

    metric_errors_before = len(errors)
    metric = plan.get("metric", "")

    if intent == "aggregate":
        if aggregation not in ALLOWED_AGGREGATIONS or not aggregation:
            errors.append(
                f"Unsupported aggregation '{aggregation}'"
            )

        if not metric:
            errors.append(
                "Aggregate query requires a metric"
            )
        elif not column_exists(metadata, entity, metric):
            errors.append(
                f"Metric '{metric}' not found in table '{entity}'"
            )

    elif metric and not column_exists(metadata, entity, metric):
        errors.append(
            f"Metric '{metric}' not found in table '{entity}'"
        )

    if len(errors) == metric_errors_before:
        add_check(
            checks,
            "Metric Valid"
        )

    group_by_errors_before = len(errors)
    group_by = plan.get("group_by", "")

    if intent == "aggregate":
        group_table, group_column = parse_reference(group_by)

        if not group_table:
            errors.append(
                f"Invalid Group By format '{group_by}'"
            )
        elif group_table not in reachable:
            errors.append(
                f"Group By table '{group_table}' is not reachable from entity '{entity}'"
            )
        elif not column_exists(metadata, group_table, group_column):
            errors.append(
                f"Group By column '{group_by}' not found"
            )

    elif group_by:
        group_table, group_column = parse_reference(group_by)

        if not group_table or not column_exists(metadata, group_table, group_column):
            errors.append(
                f"Invalid Group By column '{group_by}'"
            )

    if len(errors) == group_by_errors_before:
        add_check(
            checks,
            "Group By Valid"
        )

    trust_score = max(
        0,
        100 - (len(errors) * 15)
    )

    return {
        "valid": len(errors) == 0,
        "trust_score": trust_score,
        "checks": checks,
        "errors": errors
    }
