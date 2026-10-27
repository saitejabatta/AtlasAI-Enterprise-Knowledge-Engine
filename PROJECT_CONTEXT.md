# PROJECT_CONTEXT.md

# AtlasAI – Enterprise Knowledge Engine

## Recommended Repository Location

Place this file at the **root of the repository**:

```text
atlas-ai/
├── PROJECT_CONTEXT.md   ← Place here
├── ARCHITECTURE.md
├── BUILDATHON_CHECKLIST.md
├── backend/
├── frontend/
└── README.md
```

## Project Goal

AtlasAI is an enterprise Natural Language → SQL platform that enables business users to query enterprise data without writing SQL.

Pipeline:

Natural Language Question
↓
Table Retriever
↓
Relationship Retriever
↓
AI Planner (Gemini)
↓
Query Validator
↓
SQL Compiler
↓
DuckDB
↓
Answer Generator
↓
React Frontend

## Core Design Principles

- AI is responsible only for semantic planning.
- SQL generation is deterministic.
- Validation is deterministic.
- AI never generates SQL directly.
- AI never invents tables or joins.

## Backend Modules

- main.py — FastAPI entrypoint
- retriever.py — Retrieves relevant tables
- metadata.py — Loads schema
- relationship_retriever.py — Discovers joins
- ai_planner.py — Produces semantic query plan
- query_validator.py — Validates plans and computes trust score
- query_compiler.py — Compiles plans into SQL
- executor.py — Executes SQL against DuckDB
- answer_generator.py — Generates executive summaries
- llm.py — Central LLM wrapper (Gemini)

## Frontend

- api.ts — Backend communication
- analyst.tsx — Main analyst UI

## Current Status

Completed:
- Retrieval
- Relationship discovery
- AI planner
- SQL compiler
- Validator
- Executor
- Answer generator
- FastAPI integration
- React integration

Remaining:
- Replace Featherless completely with Gemini
- Improve planner robustness
- Improve validation
- Improve trust scoring
- Frontend polish
- Logging
- End-to-end tests
- Demo polish

## Non-negotiable Rules

1. Planner stays AI-driven.
2. SQL generation stays deterministic.
3. Validator stays deterministic.
4. Do not merge planner and compiler.
5. Do not generate SQL inside ai_planner.py.
6. Only llm.py talks to the LLM.
7. Preserve public APIs unless absolutely necessary.

## Expected Queries

Show all claims
→ SELECT * FROM claims

List all providers
→ SELECT * FROM providers

Count diabetic patients in Texas
→ COUNT(*) FROM patients WHERE diagnosis='Diabetes' AND state='Texas'

Highest diabetic treatment costs in Texas
→ Aggregate query joining claims, patients, and providers.

## Instructions for AI Coding Agents

Read this document before modifying code.

Do not redesign the architecture.

List every changed file and explain every change before completion.
