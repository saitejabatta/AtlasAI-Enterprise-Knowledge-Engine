import duckdb

from db_config import DB_PATH
def get_connection():
    return duckdb.connect(str(DB_PATH))


def initialize_database():

    conn = get_connection()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id INTEGER,
        diagnosis VARCHAR,
        state VARCHAR
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS providers (
        provider_id INTEGER,
        provider_name VARCHAR
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        claim_id INTEGER,
        patient_id INTEGER,
        provider_id INTEGER,
        claim_amount DOUBLE
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        payment_id INTEGER,
        claim_id INTEGER,
        payment_amount DOUBLE
    )
    """)

    conn.close()

    print("Tables created.")


def seed_data():

    conn = get_connection()

    conn.execute("""
    INSERT INTO patients VALUES
    (1,'Diabetes','Texas'),
    (2,'Diabetes','Texas'),
    (3,'Hypertension','California'),
    (4,'Diabetes','Florida'),
    (5,'Asthma','Texas')
    """)

    conn.execute("""
    INSERT INTO providers VALUES
    (101,'Houston Medical'),
    (102,'Dallas Care'),
    (103,'Texas Health')
    """)

    conn.execute("""
    INSERT INTO claims VALUES
    (1001,1,101,5000),
    (1002,2,101,8000),
    (1003,4,102,12000),
    (1004,5,103,2000)
    """)

    conn.execute("""
    INSERT INTO payments VALUES
    (1,1001,4500),
    (2,1002,7500),
    (3,1003,11000),
    (4,1004,1800)
    """)

    conn.close()