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


def retrieve_tables(question):

    question = question.lower()

    relevant_tables = set()

    for table, keywords in TABLE_KEYWORDS.items():

        for keyword in keywords:

            if keyword in question:
                relevant_tables.add(table)

    return list(relevant_tables)


from relationships import get_relationships


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