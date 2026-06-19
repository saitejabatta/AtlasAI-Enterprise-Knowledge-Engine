import duckdb

from db_config import DB_PATH
def extract_metadata():

    conn = duckdb.connect(str(DB_PATH))

    tables = conn.execute(
        "SHOW TABLES"
    ).fetchall()

    metadata = {}

    for table in tables:

        table_name = table[0]

        columns = conn.execute(
            f"DESCRIBE {table_name}"
        ).fetchall()

        metadata[table_name] = columns

    conn.close()

    return metadata