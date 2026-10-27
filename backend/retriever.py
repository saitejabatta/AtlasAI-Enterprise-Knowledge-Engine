from metadata import extract_metadata
from relationships import get_relationships


TABLE_KEYWORDS = {
    "patients": [
        "patient",
        "diagnosis",
        "disease",
        "diabetic",
        "diabetes",
        "member"
    ],

    "claims": [
        "claim",
        "cost",
        "expense",
        "treatment",
        "charges"
    ],

    "providers": [
        "provider",
        "doctor",
        "hospital",
        "clinic"
    ],

    "payments": [
        "payment",
        "reimbursement",
        "paid"
    ]
}


def normalize_token(value):
    return (
        value
        .lower()
        .replace("_", " ")
    )


def retrieve_tables(question):

    normalized_question = question.lower()

    relevant_tables = set()

    for table, keywords in TABLE_KEYWORDS.items():

        for keyword in keywords:

            if keyword in normalized_question:
                relevant_tables.add(table)

    if relevant_tables:
        return sorted(relevant_tables)

    metadata = extract_metadata()

    for table, columns in metadata.items():
        table_token = normalize_token(table)

        if table_token in normalized_question:
            relevant_tables.add(table)
            continue

        for column in columns:
            column_token = normalize_token(column[0])

            if column_token in normalized_question:
                relevant_tables.add(table)
                break

    if relevant_tables:
        return sorted(relevant_tables)

    return sorted(metadata.keys())


def retrieve_relationships(retrieved_tables):

    relationships = get_relationships()

    relevant_relationships = []

    for rel in relationships:

        if (
            rel["from_table"] in retrieved_tables
            and
            rel["to_table"] in retrieved_tables
        ):
            relevant_relationships.append(rel)

    return relevant_relationships
