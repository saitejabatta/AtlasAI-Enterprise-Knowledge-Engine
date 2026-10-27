def generate_answer(
    question,
    result_df
):
    """Create a concise answer using only values present in query results.

    Natural language generation can add plausible but unsupported
    interpretations. Keep this user-facing summary deterministic until an
    answer-generation path can verify every claim against the result set.
    """
    if result_df is None or result_df.empty:
        return "## Key Findings\nNo rows matched the question."

    if len(result_df.index) == 1 and len(result_df.columns) == 1:
        value = result_df.iloc[0, 0]
        return (
            "## Key Findings\n"
            f"The result for “{question.strip()}” is **{value}**.\n\n"
            "## Summary\n"
            "This answer reflects the returned query result."
        )

    # Render the actual returned rows; do not infer causes, trends, or
    # recommendations that are absent from the data.
    columns = [str(column) for column in result_df.columns]
    rows = [
        [
            str(value).replace("|", "\\|").replace("\n", " ")
            for value in row
        ]
        for row in result_df.itertuples(index=False, name=None)
    ]
    table = "| " + " | ".join(columns) + " |\n"
    table += "| " + " | ".join("---" for _ in columns) + " |\n"
    table += "\n".join(
        "| " + " | ".join(row) + " |"
        for row in rows
    )
    return (
        "## Key Findings\n"
        f"Results for “{question.strip()}”:\n\n"
        f"{table}\n\n"
        f"## Summary\n{len(result_df.index)} row(s) returned."
    )
