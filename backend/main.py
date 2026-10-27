import hashlib
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

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

from governance import (
    evaluate_governance
)

from lineage import (
    build_lineage,
    create_query_id
)

from audit_logger import (
    read_audit_events,
    write_audit_event
)

from metadata_overrides import (
    get_table_override,
    update_table_override
)

from data_sources import (
    connect_database,
    delete_data_source,
    ingest_csv,
    list_public_data_sources
)
from metadata import extract_metadata
from relationships import get_relationships
from auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    authenticate_user,
    check_auth_rate_limit,
    cookie_is_secure,
    clear_auth_rate_limit,
    create_session,
    require_production_auth_configuration,
    register_user,
    revoke_session,
)
from auth_middleware import WorkspaceAuthMiddleware
from db_config import get_db_path
from workspace_context import reset_workspace_id, set_workspace_id

load_dotenv()


def get_allowed_origins():
    origins = os.getenv("ATLAS_ALLOWED_ORIGINS")
    if origins is None:
        origins = (
            "http://localhost:3000,http://localhost:3001,"
            "http://127.0.0.1:3000,http://127.0.0.1:3001"
        )

    if origins == "*":
        if os.getenv("ATLAS_ENV", "development").lower() == "production":
            raise RuntimeError(
                "Wildcard CORS origins are not allowed in production"
            )
        return ["*"]

    return [
        origin.strip()
        for origin in origins.split(",")
        if origin.strip()
    ]


app = FastAPI(
    title="AtlasAI API",
    description="Retrieval-Augmented Enterprise Knowledge Engine",
    version="2.0.0"
)

# CORS wraps authentication so rejected API requests still receive CORS headers.
app.add_middleware(
    WorkspaceAuthMiddleware
)


@app.on_event("startup")
def validate_runtime_configuration():
    require_production_auth_configuration()

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(LoginRequest):
    workspace_name: str


class DatabaseConnectionRequest(BaseModel):
    name: str
    database_type: str
    connection_url: str


class MetadataOverrideRequest(BaseModel):
    description: str = ""
    columns: dict = Field(
        default_factory=dict
    )
    sensitive_columns: list[str] = Field(
        default_factory=list
    )


@app.get("/")
def root():

    return {
        "message": "AtlasAI API Running",
        "version": "2.0.0"
    }


@app.get("/health")
def health():

    return {
        "status": "healthy",
        "service": "atlas-ai-api",
        "version": "2.0.0"
    }


def set_session_cookie(response, token):
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=cookie_is_secure(),
        samesite="lax",
        path="/",
    )


def auth_attempt_key(scope: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{scope}:{digest}"


def request_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit_response(retry_after: int):
    response = JSONResponse(
        {"success": False, "error": "Too many attempts. Please try again later."},
        status_code=429,
    )
    response.headers["Retry-After"] = str(retry_after)
    return response


@app.post("/auth/register")
def register(payload: RegisterRequest, http_request: Request):
    registration_key = auth_attempt_key("register-ip", request_ip(http_request))
    retry_after = check_auth_rate_limit(
        registration_key,
        limit=5,
        window_seconds=60 * 60,
    )
    if retry_after:
        return rate_limit_response(retry_after)

    try:
        user = register_user(
            payload.email,
            payload.password,
            payload.workspace_name,
        )
        workspace_token = set_workspace_id(user["workspace_id"])
        try:
            get_db_path()
        finally:
            reset_workspace_id(workspace_token)
        token = create_session(user["id"])
        response = JSONResponse({"success": True, "user": user})
        set_session_cookie(response, token)
        return response
    except ValueError as exc:
        status = 409 if "already exists" in str(exc).lower() else 400
        return JSONResponse(
            {"success": False, "error": str(exc)},
            status_code=status,
        )


@app.post("/auth/login")
def login(payload: LoginRequest, http_request: Request):
    ip = request_ip(http_request)
    ip_key = auth_attempt_key("login-ip", ip)
    account_key = auth_attempt_key(
        "login-account",
        f"{ip}:{payload.email.strip().lower()}",
    )
    for key, limit in ((ip_key, 30), (account_key, 8)):
        retry_after = check_auth_rate_limit(
            key,
            limit=limit,
            window_seconds=15 * 60,
        )
        if retry_after:
            return rate_limit_response(retry_after)

    user = authenticate_user(payload.email, payload.password)
    if not user:
        return JSONResponse(
            {"success": False, "error": "Email or password is incorrect"},
            status_code=401,
        )
    clear_auth_rate_limit(account_key)
    token = create_session(user["id"])
    response = JSONResponse({"success": True, "user": user})
    set_session_cookie(response, token)
    return response


@app.get("/auth/me")
def current_user(request: Request):
    return {"success": True, "user": request.state.user}


@app.post("/auth/logout")
def logout(request: Request):
    revoke_session(request.cookies.get(SESSION_COOKIE_NAME))
    response = JSONResponse({"success": True})
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=cookie_is_secure(),
        samesite="lax",
        path="/",
    )
    return response


@app.get("/data-sources")
def data_sources():

    return {
        "success": True,
        "sources": list_public_data_sources()
    }


@app.get("/schema")
def workspace_schema():
    metadata = extract_metadata()
    return {
        "success": True,
        "tables": [
            {
                "name": table_name,
                "columns": [
                    {"name": column[0], "type": str(column[1])}
                    for column in columns
                ],
            }
            for table_name, columns in metadata.items()
        ],
        "relationships": get_relationships(),
    }


@app.get("/audit-events")
def audit_events(limit: int = 100):

    safe_limit = max(
        1,
        min(limit, 500)
    )

    return {
        "success": True,
        "events": read_audit_events(
            safe_limit
        )
    }


@app.get("/metadata-overrides/{table_name}")
def metadata_override(table_name: str):

    return {
        "success": True,
        "table": table_name,
        "override": get_table_override(
            table_name
        )
    }


@app.put("/metadata-overrides/{table_name}")
def save_metadata_override(
    table_name: str,
    request: MetadataOverrideRequest
):

    override = update_table_override(
        table_name,
        request.model_dump()
    )

    write_audit_event({
        "status": "metadata_updated",
        "table": table_name
    })

    return {
        "success": True,
        "table": table_name,
        "override": override
    }


@app.post("/data-sources/upload")
async def upload_data_source(
    file: UploadFile = File(...)
):

    try:
        source = await ingest_csv(file)

        write_audit_event({
            "status": "data_source_connected",
            "source_id": source["id"],
            "table": source["table"],
            "rows": source["rows"]
        })

        return {
            "success": True,
            "source": source
        }

    except Exception as e:

        write_audit_event({
            "status": "data_source_connection_failed",
            "filename": file.filename,
            "error": str(e)
        })

        return {
            "success": False,
            "error": str(e)
        }


@app.post("/data-sources/database")
def connect_database_source(
    request: DatabaseConnectionRequest
):

    try:
        source = connect_database(
            request.name,
            request.database_type,
            request.connection_url
        )

        write_audit_event({
            "status": "database_connected",
            "source_id": source["id"],
            "name": source["name"],
            "tables": len(
                source.get(
                    "tables",
                    []
                )
            )
        })

        return {
            "success": True,
            "source": source
        }

    except Exception as e:

        write_audit_event({
            "status": "database_connection_failed",
            "name": request.name,
            "database_type": request.database_type,
            "error": str(e)
        })

        return {
            "success": False,
            "error": str(e)
        }


@app.delete("/data-sources/{source_id}")
def remove_data_source(source_id: str):

    try:
        result = delete_data_source(
            source_id
        )

        write_audit_event({
            "status": "data_source_deleted",
            "source_id": source_id,
            "table": result["source"]["table"]
        })

        return {
            "success": True,
            **result
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


@app.post("/ask")
def ask(request: QuestionRequest):

    query_id = create_query_id()

    try:

        question = request.question.strip()

        if not question:

            return {
                "success": False,
                "question": request.question,
                "query_id": query_id,
                "error": "Question cannot be empty"
            }

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

            write_audit_event({
                "query_id": query_id,
                "question": question,
                "status": "validation_failed",
                "validation": validation,
                "query_plan": plan
            })

            return {
                "success": False,
                "question": question,
                "query_id": query_id,
                "tables": tables,
                "relationships": relationships,
                "error": "Query validation failed",
                "validation": validation,
                "trust_score": validation[
                    "trust_score"
                ],
                "query_plan": plan
            }

        # ---------------------------------
        # Step 5: Governance Check
        # ---------------------------------

        governance = evaluate_governance(
            question,
            plan
        )

        if not governance["passed"]:

            write_audit_event({
                "query_id": query_id,
                "question": question,
                "status": "governance_blocked",
                "governance": governance,
                "query_plan": plan
            })

            return {
                "success": False,
                "question": question,
                "query_id": query_id,
                "tables": tables,
                "relationships": relationships,
                "error": "Sensitive data access blocked",
                "validation": validation,
                "governance": governance,
                "trust_score": 0,
                "query_plan": plan
            }

        # ---------------------------------
        # Step 6: Compile SQL
        # ---------------------------------

        sql = compile_sql(
            plan
        )

        # ---------------------------------
        # Step 7: Execute Query
        # ---------------------------------

        result = execute_query(
            sql,
            plan
        )

        # ---------------------------------
        # Step 8: Generate Business Answer
        # ---------------------------------

        answer = generate_answer(
            question,
            result
        )

        lineage = build_lineage(
            query_id,
            question,
            tables,
            relationships,
            plan,
            sql
        )

        execution_summary = {
            "rows_returned": len(result),
            "retrieved_tables": len(tables),
            "trust_score": validation[
                "trust_score"
            ],
            "validation_status": validation[
                "valid"
            ],
            "governance_status": governance[
                "passed"
            ]
        }

        write_audit_event({
            "query_id": query_id,
            "question": question,
            "status": "success",
            "tables": tables,
            "trust_score": validation[
                "trust_score"
            ],
            "rows_returned": len(result),
            "governance": governance
        })

        # ---------------------------------
        # Response
        # ---------------------------------

        return {
            "success": True,
            "query_id": query_id,
            "question": question,
            "tables": tables,
            "relationships": relationships,
            "query_plan": plan,
            "validation": validation,
            "governance": governance,
            "trust_score": validation[
                "trust_score"
            ],
            "sql": sql,
            "result": result.to_dict(
                orient="records"
            ),
            "answer": answer,
            "lineage": lineage,
            "execution_summary": execution_summary
        }

    except Exception as e:

        write_audit_event({
            "query_id": query_id,
            "status": "error",
            "error": str(e)
        })

        return {
            "success": False,
            "query_id": query_id,
            "error": str(e)
        }
