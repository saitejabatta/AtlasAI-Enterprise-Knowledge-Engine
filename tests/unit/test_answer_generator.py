import sys
import unittest
from pathlib import Path

import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from answer_generator import generate_answer


class AnswerGeneratorTests(unittest.TestCase):
    def test_scalar_summary_uses_returned_value_without_inference(self):
        answer = generate_answer(
            "How many diabetic patients are located in Texas?",
            pd.DataFrame([{"total_count": 2}]),
        )

        self.assertIn("is **2**", answer)
        self.assertIn("returned query result", answer)
        self.assertNotIn("incomplete", answer.lower())
        self.assertNotIn("recommendation", answer.lower())

    def test_multirow_summary_renders_returned_rows(self):
        answer = generate_answer(
            "Which providers had the highest costs?",
            pd.DataFrame(
                [
                    {"provider": "North", "cost": 100},
                    {"provider": "South", "cost": 80},
                ]
            ),
        )

        self.assertIn("| provider | cost |", answer)
        self.assertIn("| North | 100 |", answer)
        self.assertIn("| South | 80 |", answer)
        self.assertIn("2 row(s) returned", answer)

    def test_empty_result_is_explicit(self):
        answer = generate_answer(
            "Show matching patients",
            pd.DataFrame(columns=["patient_id"]),
        )

        self.assertIn("No rows matched", answer)


if __name__ == "__main__":
    unittest.main()
