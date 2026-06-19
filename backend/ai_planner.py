import json

from llm import ask_llm


def create_ai_plan(
    question,
    tables,
    relationships
):

    prompt = f"""
You are an expert enterprise data analyst.

Question:
{question}

Available Tables:
{json.dumps(tables, indent=2)}

Relationships:
{json.dumps(relationships, indent=2)}

Return ONLY valid JSON.

Format:

{{
  "tables": [],
  "joins": [],
  "filters": [],
  "aggregations": [],
  "reasoning": ""
}}

Do not return markdown.
Do not return explanations outside JSON.
"""

    response = ask_llm(prompt)

    try:
        return json.loads(response)

    except Exception as e:

        print("Planner Parsing Error")

        print(response)

        raise e