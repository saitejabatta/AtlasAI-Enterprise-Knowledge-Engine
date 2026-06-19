def validate_plan(plan):

    score = 100

    checks = []

    if len(plan["tables"]) == 0:
        score -= 50
        checks.append("No tables found")

    else:
        checks.append("Tables Found")

    if len(plan["joins"]) == 0:
        score -= 30
        checks.append("No joins found")

    else:
        checks.append("Join Path Valid")

    if len(plan["filters"]) > 0:
        checks.append("Filters Applied")

    if len(plan["aggregations"]) > 0:
        checks.append("Aggregation Found")

    return {
        "trust_score": score,
        "checks": checks
    }