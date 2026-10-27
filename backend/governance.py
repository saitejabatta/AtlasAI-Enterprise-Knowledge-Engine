from metadata import extract_metadata
from metadata_overrides import read_metadata_overrides


SENSITIVE_COLUMN_NAMES = {
    "ssn",
    "social_security_number",
    "credit_card",
    "credit_card_number",
    "dob",
    "date_of_birth",
    "email",
    "phone",
    "address",
}

BLOCKED_QUESTION_TERMS = {
    "ssn",
    "social security",
    "credit card",
    "date of birth",
    "dob",
}


def get_sensitive_columns():
    metadata = extract_metadata()
    overrides = read_metadata_overrides()
    sensitive = set()

    for table, columns in metadata.items():
        for column in columns:
            column_name = column[0]

            if column_name.lower() in SENSITIVE_COLUMN_NAMES:
                sensitive.add(
                    f"{table}.{column_name}"
                )

    for table, table_override in overrides.items():
        for column_name in table_override.get(
            "sensitive_columns",
            []
        ):
            sensitive.add(
                f"{table}.{column_name}"
            )

    return sensitive


def plan_references(plan):
    references = set()
    metadata = extract_metadata()

    entity = plan.get("entity")
    metric = plan.get("metric")
    group_by = plan.get("group_by")

    if plan.get("intent") == "list" and entity in metadata:
        for column in metadata[entity]:
            references.add(
                f"{entity}.{column[0]}"
            )

    if entity and metric:
        references.add(
            f"{entity}.{metric}"
        )

    if group_by:
        references.add(group_by)

    for filter_obj in plan.get("filters", []) or []:
        table = filter_obj.get("table")
        column = filter_obj.get("column")

        if table and column:
            references.add(
                f"{table}.{column}"
            )

    for join in plan.get("joins", []) or []:
        if join.get("left"):
            references.add(join["left"])

        if join.get("right"):
            references.add(join["right"])

    return references


def evaluate_governance(question, plan):
    sensitive_columns = get_sensitive_columns()
    referenced_columns = plan_references(plan)
    blocked_columns = sorted(
        sensitive_columns.intersection(
            referenced_columns
        )
    )
    question_lower = question.lower()
    blocked_terms = sorted([
        term
        for term in BLOCKED_QUESTION_TERMS
        if term in question_lower
    ])

    errors = []
    checks = []

    if blocked_columns:
        errors.append(
            "Sensitive column access blocked: "
            + ", ".join(blocked_columns)
        )

    if blocked_terms:
        errors.append(
            "Sensitive data request blocked: "
            + ", ".join(blocked_terms)
        )

    if not errors:
        checks.append(
            "Governance Check Passed"
        )

    return {
        "passed": len(errors) == 0,
        "checks": checks,
        "errors": errors,
        "blocked_columns": blocked_columns,
        "blocked_terms": blocked_terms,
    }
