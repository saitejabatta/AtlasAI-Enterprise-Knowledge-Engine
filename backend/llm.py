import os
import re

from google import genai
from dotenv import load_dotenv

load_dotenv()

API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
)
MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY or GOOGLE_API_KEY not found in .env"
    )

client = genai.Client(
    api_key=API_KEY
)


def ask_llm(prompt: str) -> str:
    """
    Sends a prompt to Gemini and returns clean text.
    """

    try:

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )

        text = response.text or ""

        # Remove markdown code fences if Gemini returns them
        text = re.sub(
            r"```json",
            "",
            text,
            flags=re.IGNORECASE
        )

        text = re.sub(
            r"```",
            "",
            text
        )

        return text.strip()

    except Exception as e:

        raise RuntimeError(
            f"Gemini API Error: {e}"
        )
