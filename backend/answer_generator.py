from llm import ask_llm
import re


def generate_answer(
    question,
    result_df
):

    prompt = f"""
You are AtlasAI, an enterprise data analyst.

Question:
{question}

Query Results:
{result_df.to_string()}

Instructions:

1. Explain results in executive-friendly language.
2. Be concise.
3. Focus on business impact.
4. Do not mention SQL.
5. Do not mention retrieval.
6. Do not show internal reasoning.
7. Use this format:

## Key Findings
...

## Summary
...

## Recommendation
...
"""

    answer = ask_llm(prompt)

    # Remove thinking blocks
    answer = re.sub(
        r"<think>.*?</think>",
        "",
        answer,
        flags=re.DOTALL
    )

    answer = answer.strip()

    return answer