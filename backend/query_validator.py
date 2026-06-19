from metadata import extract_metadata


def validate_query_plan(plan):

    metadata = extract_metadata()

    errors = []
    checks = []

    # -------------------------
    # Validate Entity/Table
    # -------------------------

    entity = plan.get("entity")

    if entity not in metadata:

        errors.append(
            f"Table '{entity}' does not exist"
        )

    else:

        checks.append(
            "Entity Valid"
        )

    # -------------------------
    # Validate Filters
    # -------------------------

    for filter_obj in plan.get(
        "filters",
        []
    ):

        table = filter_obj["table"]
        column = filter_obj["column"]

        if table not in metadata:

            errors.append(
                f"Filter table '{table}' not found"
            )

            continue

        available_columns = [
            col[0]
            for col in metadata[table]
        ]

        if column not in available_columns:

            errors.append(
                f"Column '{column}' not found in table '{table}'"
            )

    if not errors:

        checks.append(
            "Filters Valid"
        )

    # -------------------------
    # Validate Metric
    # -------------------------

    metric = plan.get(
        "metric",
        ""
    )

    if metric:

        entity_columns = [
            col[0]
            for col in metadata.get(
                entity,
                []
            )
        ]

        if metric not in entity_columns:

            errors.append(
                f"Metric '{metric}' not found in table '{entity}'"
            )

        else:

            checks.append(
                "Metric Valid"
            )

    # -------------------------
    # Validate Group By
    # -------------------------

    group_by = plan.get(
        "group_by",
        ""
    )

    if group_by:

        try:

            table_name, column_name = (
                group_by.split(".")
            )

            available_columns = [
                col[0]
                for col in metadata.get(
                    table_name,
                    []
                )
            ]

            if column_name not in available_columns:

                errors.append(
                    f"Group By column '{group_by}' not found"
                )

            else:

                checks.append(
                    "Group By Valid"
                )

        except Exception:

            errors.append(
                f"Invalid Group By format '{group_by}'"
            )

    # -------------------------
    # Validate Joins
    # -------------------------

    for join in plan.get(
        "joins",
        []
    ):

        left = join["left"]
        right = join["right"]

        try:

            left_table, left_column = (
                left.split(".")
            )

            right_table, right_column = (
                right.split(".")
            )

            left_columns = [
                col[0]
                for col in metadata.get(
                    left_table,
                    []
                )
            ]

            right_columns = [
                col[0]
                for col in metadata.get(
                    right_table,
                    []
                )
            ]

            if left_column not in left_columns:

                errors.append(
                    f"Join column '{left}' not found"
                )

            if right_column not in right_columns:

                errors.append(
                    f"Join column '{right}' not found"
                )

        except Exception:

            errors.append(
                f"Invalid join definition {join}"
            )

    if not errors:

        checks.append(
            "Joins Valid"
        )

    # -------------------------
    # Trust Score
    # -------------------------

    trust_score = max(
        0,
        100 - (len(errors) * 20)
    )

    return {
        "valid": len(errors) == 0,
        "trust_score": trust_score,
        "checks": checks,
        "errors": errors
    }