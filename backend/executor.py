import duckdb
import pandas as pd
from sqlalchemy import create_engine, text

from data_sources import (
    get_execution_context_for_plan
)


def quote_identifier(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def render_external_table(table):
    real_table = quote_identifier(
        table["table"]
    )

    if table.get("schema"):
        return (
            f"{quote_identifier(table['schema'])}."
            f"{real_table}"
        )

    return real_table


def rewrite_sql_for_external_database(sql, tables):
    rewritten = sql

    for virtual_table, table in tables.items():
        virtual_identifier = quote_identifier(
            virtual_table
        )
        real_table = render_external_table(
            table
        )
        aliased_table = (
            f"{real_table} AS {virtual_identifier}"
        )

        rewritten = rewritten.replace(
            f"FROM {virtual_identifier}",
            f"FROM {aliased_table}"
        )
        rewritten = rewritten.replace(
            f"JOIN {virtual_identifier}",
            f"JOIN {aliased_table}"
        )

    return rewritten


def execute_external_query(sql, context):
    rewritten_sql = rewrite_sql_for_external_database(
        sql,
        context["tables"]
    )
    engine = create_engine(
        context["connection_url"]
    )

    try:
        return pd.read_sql_query(
            text(rewritten_sql),
            engine
        )
    finally:
        engine.dispose()


def execute_query(sql, plan=None):

    if plan:
        context = get_execution_context_for_plan(
            plan
        )

        if context:
            return execute_external_query(
                sql,
                context
            )

    from db_config import get_db_path

    conn = duckdb.connect(str(get_db_path()))

    result = conn.execute(sql).fetchdf()

    conn.close()

    return result
