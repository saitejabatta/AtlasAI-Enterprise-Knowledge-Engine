def create_query_plan(
    question,
    tables,
    relationships
):

    question = question.lower()

    plan = {
        "tables": tables,
        "joins": [],
        "filters": [],
        "aggregations": []
    }

    # Build joins

    for rel in relationships:

        join_statement = (
            f"{rel['from_table']}.{rel['from_column']} = "
            f"{rel['to_table']}.{rel['to_column']}"
        )

        plan["joins"].append(join_statement)

    # Detect filters

    if "diabetes" in question or "diabetic" in question:
        plan["filters"].append(
            "patients.diagnosis = 'Diabetes'"
        )

    if "texas" in question:
        plan["filters"].append(
            "patients.state = 'Texas'"
        )

    # Detect aggregations

    if (
        "highest" in question
        or
        "top" in question
    ):
        plan["aggregations"].append(
            "SUM(claims.claim_amount)"
        )

    return plan