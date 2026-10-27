# ARCHITECTURE.md

# Recommended Location

```text
atlas-ai/
├── PROJECT_CONTEXT.md
├── ARCHITECTURE.md   ← Place here
├── BUILDATHON_CHECKLIST.md
```

# Request Flow

User Question
→ Retriever
→ Relationship Retriever
→ AI Planner
→ Query Validator
→ SQL Compiler
→ DuckDB
→ Answer Generator
→ Frontend

# Responsibilities

Retriever:
- Select relevant tables.

Relationship Retriever:
- Identify valid joins.

AI Planner:
- Produce semantic query plan only.

Validator:
- Verify entities, joins, filters, metrics and groupings.

Compiler:
- Convert validated plans into SQL.

Executor:
- Execute SQL.

Answer Generator:
- Produce business-friendly summaries.

# Future Improvements

- Vector metadata retrieval
- Multi-database connectors
- Role-based access
- Streaming responses
- Cost estimation
