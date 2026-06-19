import json

from llm import ask_llm
from schema_loader import get_schema_text


def create_ai_plan(
    question,
    tables,
    relationships
):

    schema = get_schema_text()

    prompt = f"""
You are AtlasAI's Enterprise Query Planner.

Your job is to convert a natural language question into a structured query plan.

Question:
{question}

Available Tables:
{json.dumps(tables, indent=2)}

Relationships:
{json.dumps(relationships, indent=2)}

Database Schema:
{schema}

IMPORTANT RULES:

1. Use ONLY tables from Available Tables.
2. Use ONLY columns from Database Schema.
3. Never invent tables.
4. Never invent columns.
5. If the user says diabetic, use:
   diagnosis = 'Diabetes'
6. Return ONLY valid JSON.
7. No markdown.
8. No explanations outside JSON.

Return this EXACT structure:

{{
  "intent": "",
  "entity": "",
  "aggregation": "",
  "metric": "",
  "group_by": "",
  "filters": [],
  "joins": [],
  "reasoning": ""
}}

Definitions:

intent:
- list
- count
- aggregate

aggregation:
- COUNT
- SUM
- AVG
- MAX
- MIN
- ""

metric:
Column being aggregated.

group_by:
Column used for grouping.

filters format:

[
  {{
    "table": "",
    "column": "",
    "operator": "=",
    "value": ""
  }}
]

joins format:

[
  {{
    "left": "",
    "right": ""
  }}
]

Example:

Question:
How many diabetic patients are located in Texas?

Output:

{{
  "intent":"count",
  "entity":"patients",
  "aggregation":"COUNT",
  "metric":"",
  "group_by":"",
  "filters":[
    {{
      "table":"patients",
      "column":"diagnosis",
      "operator":"=",
      "value":"Diabetes"
    }},
    {{
      "table":"patients",
      "column":"state",
      "operator":"=",
      "value":"Texas"
    }}
  ],
  "joins":[],
  "reasoning":"Count diabetic patients in Texas"
}}

Question:
Which providers generated the highest diabetic treatment costs in Texas?

Output:

{{
  "intent":"aggregate",
  "entity":"claims",
  "aggregation":"SUM",
  "metric":"claim_amount",
  "group_by":"providers.provider_name",
  "filters":[
    {{
      "table":"patients",
      "column":"diagnosis",
      "operator":"=",
      "value":"Diabetes"
    }},
    {{
      "table":"patients",
      "column":"state",
      "operator":"=",
      "value":"Texas"
    }}
  ],
  "joins":[
    {{
      "left":"patients.patient_id",
      "right":"claims.patient_id"
    }},
    {{
      "left":"claims.provider_id",
      "right":"providers.provider_id"
    }}
  ],
  "reasoning":"Find providers with highest diabetic treatment costs in Texas"
}}

Return JSON only.
"""

    response = ask_llm(prompt)

    try:

        start = response.find("{")
        end = response.rfind("}") + 1

        clean_json = response[start:end]

        return json.loads(clean_json)

    except Exception as e:

        print("\nPLANNER PARSING ERROR\n")
        print(response)

        raise e