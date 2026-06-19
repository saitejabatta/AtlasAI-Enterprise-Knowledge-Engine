import json
import re

from llm import ask_llm


def load_metadata():

    with open("metadata_store.json", "r") as f:
        return json.load(f)


def retrieve_tables_with_rag(question):

    metadata = load_metadata()

    prompt = f"""
You are a database retrieval system.

Question:
{question}

Metadata:
{json.dumps(metadata, indent=2)}

Return ONLY a JSON array.

Example:

["patients","claims","providers"]

No reasoning.
No markdown.
No explanations.
"""

    response = ask_llm(prompt)

    print("\nRAW LLM RESPONSE:")
    print(response)

    # Remove thinking tags
    response = re.sub(
        r"<think>.*?</think>",
        "",
        response,
        flags=re.DOTALL
    )

    response = response.strip()

    # Extract JSON array
    match = re.search(
        r"\[.*?\]",
        response,
        re.DOTALL
    )

    if not match:
        raise Exception(
            f"No JSON array found in:\n{response}"
        )

    json_text = match.group(0)

    return json.loads(json_text)