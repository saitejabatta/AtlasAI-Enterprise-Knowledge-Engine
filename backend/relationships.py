import duckdb

from db_config import get_db_path


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
    from data_sources import read_sources

    connection = duckdb.connect(str(get_db_path()))
    try:
        available_tables = {
            row[0]
            for row in connection.execute("SHOW TABLES").fetchall()
        }
    finally:
        connection.close()
    relationships = [
        relationship
        for relationship in RELATIONSHIPS
        if relationship["from_table"] in available_tables
        and relationship["to_table"] in available_tables
    ]
    for source in read_sources():
        relationships.extend(source.get("relationships", []))
    return relationships
