import duckdb

def execute_query(sql):

    conn = duckdb.connect("atlas.db")

    result = conn.execute(sql).fetchdf()

    conn.close()

    return result