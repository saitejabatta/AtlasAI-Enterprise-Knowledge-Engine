import duckdb

from data_sources import read_sources
from db_config import get_db_path


def quote_identifier(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def extract_metadata():

    conn = duckdb.connect(str(get_db_path()))

    tables = conn.execute(
        "SHOW TABLES"
    ).fetchall()

    metadata = {}

    for table in tables:

        table_name = table[0]

        columns = conn.execute(
            f"DESCRIBE {quote_identifier(table_name)}"
        ).fetchall()

        metadata[table_name] = columns

    conn.close()

    for source in read_sources():
        if source.get("type") != "DATABASE":
            continue

        for table in source.get("tables", []):
            metadata[table["virtual_table"]] = [
                (
                    column["name"],
                    column["type"],
                )
                for column in table.get(
                    "columns",
                    []
                )
            ]

    return metadata
