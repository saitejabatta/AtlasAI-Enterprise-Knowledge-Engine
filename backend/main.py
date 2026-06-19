from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from retriever import (
    retrieve_tables,
    retrieve_relationships
)

from ai_planner import create_ai_plan

from query_validator import (
    validate_query_plan
)

from query_compiler import (
    compile_sql
)

from executor import execute_query

from answer_generator import (
    generate_answer
)


app = FastAPI(
    title="AtlasAI API",
    description="Retrieval-Augmented Enterprise Knowledge Engine",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def root():

    return {
        "message": "AtlasAI API Running",
        "version": "2.0.0"
    }


@app.post("/ask")
def ask(request: QuestionRequest):

    try:

        question = request.question

        # ---------------------------------
        # Step 1: Retrieve Relevant Tables
        # ---------------------------------

        tables = retrieve_tables(
            question
        )

        # ---------------------------------
        # Step 2: Retrieve Relationships
        # ---------------------------------

        relationships = retrieve_relationships(
            tables
        )

        # ---------------------------------
        # Step 3: AI Query Planning
        # ---------------------------------

        plan = create_ai_plan(
            question,
            tables,
            relationships
        )

        # ---------------------------------
        # Step 4: Validate Query Plan
        # ---------------------------------

        validation = validate_query_plan(
            plan
        )

        if not validation["valid"]:

            return {
                "success": False,
                "error": "Query validation failed",
                "validation": validation,
                "query_plan": plan
            }

        # ---------------------------------
        # Step 5: Compile SQL
        # ---------------------------------

        sql = compile_sql(
            plan
        )

        # ---------------------------------
        # Step 6: Execute Query
        # ---------------------------------

        result = execute_query(
            sql
        )

        # ---------------------------------
        # Step 7: Generate Business Answer
        # ---------------------------------

        answer = generate_answer(
            question,
            result
        )

        # ---------------------------------
        # Response
        # ---------------------------------

        return {
            "success": True,
            "question": question,
            "tables": tables,
            "relationships": relationships,
            "query_plan": plan,
            "validation": validation,
            "trust_score": validation[
                "trust_score"
            ],
            "sql": sql,
            "result": result.to_dict(
                orient="records"
            ),
            "answer": answer
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }