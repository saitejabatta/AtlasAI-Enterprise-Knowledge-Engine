def build_where_clause(filters):
    if not filters:
        return ""

    conditions = []

    for f in filters:

        value = f["value"]

        if isinstance(value, str):
            value = f"'{value}'"

        conditions.append(
            f"{f['table']}.{f['column']} "
            f"{f['operator']} "
            f"{value}"
        )

    return " WHERE " + " AND ".join(conditions)

def build_join_clause(
    joins,
    base_table
    ):

    if not joins:
        return ""

    sql = ""

    joined_tables = {base_table}

    for join in joins:

        left_table = join["left"].split(".")[0]
        right_table = join["right"].split(".")[0]

        if left_table in joined_tables and right_table not in joined_tables:

            sql += f"""

    JOIN {right_table}
    ON {join['left']} = {join['right']}
    """
            joined_tables.add(right_table)

        elif right_table in joined_tables and left_table not in joined_tables:

            sql += f"""

    JOIN {left_table}
    ON {join['left']} = {join['right']}
    """
            joined_tables.add(left_table)

    return sql

def compile_count(plan):

   
    sql = f"""

    SELECT COUNT(*) AS total_count
    FROM {plan['entity']}
    """

    sql += build_join_clause(
        plan.get("joins", []),
        plan["entity"]
    )

    sql += build_where_clause(
        plan.get("filters", [])
    )

    return sql

def compile_list(plan):
    sql = f"""

    SELECT *
    FROM {plan['entity']}
    """
    sql += build_join_clause(
        plan.get("joins", []),
        plan["entity"]
    )

    sql += build_where_clause(
        plan.get("filters", [])
    )

    return sql

def compile_aggregate(plan):

    sql = f"""

    SELECT
    {plan['group_by']},
    {plan['aggregation']}(
    {plan['entity']}.{plan['metric']}
    ) AS result
    FROM {plan['entity']}
    """

    
    sql += build_join_clause(
        plan.get("joins", []),
        plan["entity"]
    )

    sql += build_where_clause(
        plan.get("filters", [])
    )

    sql += f"""


    GROUP BY {plan['group_by']}
    ORDER BY result DESC
    """

    return sql

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
