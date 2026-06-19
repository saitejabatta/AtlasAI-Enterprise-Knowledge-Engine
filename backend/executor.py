import duckdb

def execute_query(sql):

    from db_config import DB_PATH

    conn = duckdb.connect(str(DB_PATH))

    result = conn.execute(sql).fetchdf()

    conn.close()

    return result