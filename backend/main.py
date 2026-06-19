from fastapi import FastAPI

from retriever import (
    retrieve_tables,
    retrieve_relationships
)

from planner import create_query_plan

from sql_generator import generate_sql

from executor import execute_query

from answer_generator import generate_answer

from validator import validate_plan

app = FastAPI()


@app.post("/ask")
def ask(question: str):

    tables = retrieve_tables(question)

    relationships = retrieve_relationships(tables)

    plan = create_query_plan(
        question,
        tables,
        relationships
    )

    validation = validate_plan(plan)

    sql = generate_sql(plan)

    result = execute_query(sql)

    answer = generate_answer(
        question,
        result
    )

    return {
        "question": question,
        "tables": tables,
        "relationships": relationships,
        "trust_score": validation,
        "sql": sql,
        "result": result.to_dict(
            orient="records"
        ),
        "answer": answer
    }