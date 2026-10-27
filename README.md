# AtlasAI Enterprise Knowledge Engine

AtlasAI is an enterprise natural-language analytics platform. It turns a business question into a governed, explainable analytics workflow:

1. retrieve relevant metadata and tables
2. discover relationship paths
3. create an AI query plan
4. validate tables, columns, metrics, filters, and joins
5. enforce governance checks
6. compile safe SQL
7. execute against DuckDB
8. generate an executive-friendly answer
9. return lineage, trust, SQL, result rows, and audit metadata

The current demo domain is healthcare, but the backend pipeline is domain-agnostic.

## Product capabilities

- Natural-language analytics over enterprise tables
- Schema-aware AI query planning
- SQL generation from structured query plans
- Join-path validation against approved relationships
- Trust score derived from validation checks
- Governance blocking for sensitive fields and sensitive requests
- Query lineage with query IDs
- Local append-only audit log
- CSV data-source upload and table creation
- Live database connection through SQLAlchemy URLs
- Metadata-first database introspection for large databases
- Query pushdown to connected databases
- Encrypted local storage for database connection credentials
- Email/password accounts with revocable, HTTP-only sessions
- Separate DuckDB, uploads, source catalog, metadata overrides, and audit log per workspace
- Business metadata enrichment for tables and sensitive columns
- Live Security Center audit history
- Connected-source catalog with schema inspection
- Source deletion/removal from the workspace
- Professional dark enterprise analyst UI
- Copyable generated SQL
- Result table rendering
- Validation and governance display

## Architecture

```text
Question
  -> metadata retrieval
  -> relationship retrieval
  -> AI planner
  -> query validator
  -> governance layer
  -> SQL compiler
  -> DuckDB executor
  -> answer generator
  -> lineage + audit
  -> frontend
```

## Backend response contract

`POST /ask` returns the original response fields and includes product metadata:

```json
{
  "success": true,
  "query_id": "qry_...",
  "question": "...",
  "tables": ["patients", "claims", "providers"],
  "relationships": [],
  "query_plan": {},
  "validation": {
    "valid": true,
    "trust_score": 100,
    "checks": [],
    "errors": []
  },
  "governance": {
    "passed": true,
    "checks": ["Governance Check Passed"],
    "errors": [],
    "blocked_columns": [],
    "blocked_terms": []
  },
  "trust_score": 100,
  "sql": "SELECT ...",
  "result": [],
  "answer": "...",
  "lineage": {},
  "execution_summary": {}
}
```

## Local setup

Backend:

```bash
cd backend
python -m venv ../venv
../venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Add your Gemini key to `backend/.env`:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
ATLAS_SECRET_KEY=replace_with_a_long_random_secret
```

Run:

```bash
../venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

Frontend:

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 3000
```

On first launch, create an account and workspace. Use a password with at least 12 characters. The browser receives an HTTP-only session cookie; the API does not store session tokens in browser storage. Workspace data lives under `backend/workspaces/<workspace-id>/` and is excluded from Git.

Development workspaces start with a small synthetic healthcare dataset. Production workspaces start empty; the app never clones a shared local database into a new customer workspace.

Run the repeatable backend unit checks without calling Gemini:

```bash
../venv/bin/python -B -m unittest discover -s tests/unit -v
```

If port `3000` is busy, Vite will use the next available port.

## Deploy to Render

The root `render.yaml` defines an API web service and a Node SSR web service. The API mounts `/var/data` as its persistent storage directory; set `ATLAS_DATA_DIR` to this path so workspace DuckDB files, uploads, auth sessions, audit logs, and encryption material survive deploys. The frontend uses the generated Nitro Node server rather than serving only the client bundle.

1. Push the root repository and frontend submodule commits to GitHub, making sure the root repository includes `.gitmodules` and points at the frontend commit containing the current UI.
2. In Render, connect the root GitHub repository and create a Blueprint from `render.yaml`.
3. Enter `GEMINI_API_KEY`, `ATLAS_ALLOWED_ORIGINS` (the exact HTTPS frontend URL), `ATLAS_DATABASE_HOST_ALLOWLIST` (comma-separated exact database hostnames; leave empty only if no external database will be connected yet), and `VITE_API_BASE_URL` (the full HTTPS API URL) when prompted.
4. Keep the generated `ATLAS_SESSION_SECRET` and `ATLAS_SECRET_KEY` private. Do not commit them or put them in client-side `VITE_*` variables.
5. After deployment, verify `/health`, register a disposable account, connect a non-production source, run a query, and confirm data persists after a redeploy before inviting real users.

The Blueprint uses a paid web-service plan and a persistent disk. It is a single-instance pilot deployment: account/session state and rate limits still use local SQLite, and workspace data is file-backed. Add managed identity, database/object storage, backups, shared rate limiting, monitoring, and a security review before using it for sensitive or business-critical data. Review the hosting provider's current pricing and retention/back-up settings before creating resources.

## Connect your own data

### CSV files

1. Open the Data Catalog page.
2. Click **Connect CSV**.
3. Upload a `.csv` file.
4. AtlasAI creates a DuckDB table from the file, profiles its rows and columns, and adds it to the connected workspace.
5. Open AI Analyst and ask questions about the uploaded table or its columns.

Uploaded source metadata, files, and DuckDB tables are stored inside the signed-in workspace directory.

### Live databases

1. Open the Data Catalog page.
2. Click **Connect Database**.
3. Enter a source name, database type, and SQLAlchemy connection URL.
4. AtlasAI introspects schemas, tables, and columns without copying the full database.
5. AtlasAI registers virtual table names for planning and pushes generated SQL back to the connected database at query time.

Example connection URLs:

```bash
postgresql+psycopg://user:password@host:5432/database
mysql+pymysql://user:password@host:3306/database
sqlite:////absolute/path/to/database.db
```

For very large databases, AtlasAI should rely on metadata, governance, and query pushdown. It should not ingest the entire database into the app server.
SQLite connections are development-only; production rejects server-local SQLite files. Configure network egress restrictions for the application host before allowing user-supplied database URLs.
Authentication endpoints are rate-limited (login by IP and IP/email pair; registration by IP). Defaults are 30 login attempts per IP per 15 minutes, 8 attempts per IP/email pair per 15 minutes, and 5 registrations per IP per hour. These counters use the local auth SQLite database, so multi-instance deployments must move them to a shared rate-limit store. In production, database connections are also restricted to exact hostnames configured with `ATLAS_DATABASE_HOST_ALLOWLIST`; keep outbound network egress restricted at the deployment layer as a second boundary.

## Metadata enrichment

Connected sources can be enriched from the Data Catalog:

- add table descriptions
- select sensitive columns
- improve planner context for business terms
- feed sensitivity tags into governance blocking

Metadata overrides are stored inside the signed-in workspace directory.

## Security and audit

- Database connection URLs are encrypted before being stored in each workspace’s source catalog.
- Local development encryption uses `backend/.atlas_secret` if `ATLAS_SECRET_KEY` is not set.
- Production startup requires independent 32+ character `ATLAS_SECRET_KEY` and `ATLAS_SESSION_SECRET` values and `ATLAS_COOKIE_SECURE=true`; load them from a real secret manager.
- Production deployments must set `ATLAS_ALLOWED_ORIGINS` to the exact frontend origins; wildcard origins are rejected.
- Login-protected HTTP-only sessions and origin checks guard mutating requests.
- Query, connector, governance, and metadata events are written to the signed-in workspace audit log.
- Security Center reads live audit events from `GET /audit-events`.

## Demo questions

- Which providers generated the highest diabetic treatment costs in Texas?
- How many diabetic patients are located in Texas?
- Show diabetic patients in Texas.
- Which providers have the highest treatment costs?

## Production hardening already added

- no raw `SELECT *` for list queries
- SQL identifiers are quoted and validated
- literal values are escaped
- filter operators are allowlisted
- joins must match approved relationship definitions
- filter/group-by tables must be reachable from the query entity
- sensitive data governance blocks unsafe requests before execution
- each request gets a query ID
- account uploads, source catalogs, metadata overrides, DuckDB files, and audit events are workspace-scoped
- new workspaces receive synthetic demo rows in development and start empty in production
- CSV upload ingestion is streamed and capped at 250 MB by default
- audit events are written to the signed-in workspace audit log
- connected CSV sources are converted into queryable DuckDB tables
- live databases are introspected via SQLAlchemy and queried through pushdown
- Gemini integration uses the current `google-genai` SDK
- database credentials are encrypted at rest in local development
- user-defined metadata descriptions are injected into planner schema context
- user-marked sensitive columns are enforced by governance

## Remaining production milestones

- Replace local DuckDB with a warehouse connector abstraction
- Add workspace invitations, role-based access control, account recovery, and email verification
- Store audit logs and account/session data in durable managed storage
- Move auth rate limits to a shared store for multi-instance deployments
- Add shared-workspace membership and administration
- Add semantic synonyms per domain
- Add observability, tracing, and request metrics
- Expand automated regression tests with mocked LLM responses and connector-specific integration tests

The local account and workspace boundary is a development foundation, not a substitute for a security review, managed identity provider, managed database, or deployment controls before internet-facing production.
