def generate_sql(plan):

    sql = """
    SELECT
        providers.provider_name,
        SUM(claims.claim_amount) AS total_cost
    FROM claims
    """

    sql += """
    JOIN patients
        ON claims.patient_id = patients.patient_id
    """

    sql += """
    JOIN providers
        ON claims.provider_id = providers.provider_id
    """

    filters = plan["filters"]

    if filters:

        sql += "\nWHERE "

        sql += " AND ".join(filters)

    sql += """
    GROUP BY providers.provider_name
    ORDER BY total_cost DESC
    """

    return sql