RELATIONSHIPS = [
    {
        "from_table": "patients",
        "from_column": "patient_id",
        "to_table": "claims",
        "to_column": "patient_id"
    },
    {
        "from_table": "claims",
        "from_column": "provider_id",
        "to_table": "providers",
        "to_column": "provider_id"
    },
    {
        "from_table": "claims",
        "from_column": "claim_id",
        "to_table": "payments",
        "to_column": "claim_id"
    }
]

def get_relationships():
    return RELATIONSHIPS