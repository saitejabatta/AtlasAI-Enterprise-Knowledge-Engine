import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("GEMINI_API_KEY", "unit-test-key")

import auth
import audit_logger
import data_sources
import db_config
import metadata_overrides
from main import app


class AuthApiTests(unittest.TestCase):
    def test_login_required_and_workspace_data_isolated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backend_root = root / "backend"
            auth_db = root / "auth.db"
            with (
                patch.object(auth, "AUTH_DB_PATH", auth_db),
                patch.object(audit_logger, "BASE_DIR", backend_root),
                patch.object(db_config, "BASE_DIR", backend_root),
                patch.object(data_sources, "BASE_DIR", backend_root),
                patch.object(metadata_overrides, "BASE_DIR", backend_root),
                patch.dict(
                    os.environ,
                    {
                        "ATLAS_ENV": "development",
                        "ATLAS_DEMO_SEED": "true",
                        "ATLAS_SESSION_SECRET": "unit-test-session-secret",
                    },
                ),
                TestClient(app) as first_client,
                TestClient(app) as second_client,
            ):
                unauthenticated = first_client.get("/data-sources")
                self.assertEqual(unauthenticated.status_code, 401)
                cross_origin = first_client.post(
                    "/auth/login",
                    headers={"Origin": "https://untrusted.example"},
                    json={"email": "nobody@example.com", "password": "wrong"},
                )
                self.assertEqual(cross_origin.status_code, 403)
                with patch("main.check_auth_rate_limit", return_value=60):
                    rate_limited = first_client.post(
                        "/auth/login",
                        json={
                            "email": "nobody@example.com",
                            "password": "incorrect-password",
                        },
                    )
                self.assertEqual(rate_limited.status_code, 429)
                self.assertEqual(rate_limited.headers.get("retry-after"), "60")

                first_registration = first_client.post(
                    "/auth/register",
                    headers={"Origin": "http://127.0.0.1:3001"},
                    json={
                        "email": "first@example.com",
                        "password": "first-long-test-password",
                        "workspace_name": "First workspace",
                    },
                )
                self.assertEqual(first_registration.status_code, 200)
                self.assertEqual(
                    first_registration.headers.get("access-control-allow-origin"),
                    "http://127.0.0.1:3001",
                )
                self.assertEqual(
                    first_registration.headers.get("access-control-allow-credentials"),
                    "true",
                )
                workspace_schema = first_client.get("/schema").json()
                self.assertIn(
                    "patients",
                    {table["name"] for table in workspace_schema["tables"]},
                )
                session_cookie = first_registration.headers.get("set-cookie", "")
                self.assertIn("httponly", session_cookie.lower())
                self.assertIn("samesite=lax", session_cookie.lower())

                plan = {
                    "intent": "count",
                    "entity": "patients",
                    "aggregation": "COUNT",
                    "metric": "",
                    "group_by": "",
                    "filters": [
                        {
                            "table": "patients",
                            "column": "diagnosis",
                            "operator": "=",
                            "value": "Diabetes",
                        },
                        {
                            "table": "patients",
                            "column": "state",
                            "operator": "=",
                            "value": "Texas",
                        },
                    ],
                    "joins": [],
                }
                with patch("main.create_ai_plan", return_value=plan):
                    ask_response = first_client.post(
                        "/ask",
                        json={
                            "question": "How many diabetic patients are in Texas?"
                        },
                    )
                self.assertEqual(ask_response.status_code, 200)
                self.assertTrue(ask_response.json()["success"], ask_response.text)
                self.assertEqual(ask_response.json()["result"][0]["total_count"], 2)
                self.assertIn("is **2**", ask_response.json()["answer"])

                upload = first_client.post(
                    "/data-sources/upload",
                    files={
                        "file": (
                            "private.csv",
                            "name,region\nAlpha,West\n",
                            "text/csv",
                        )
                    },
                )
                self.assertEqual(upload.status_code, 200)
                self.assertTrue(upload.json()["success"])

                with patch.object(data_sources, "MAX_CSV_UPLOAD_BYTES", 4):
                    oversized_upload = first_client.post(
                        "/data-sources/upload",
                        files={
                            "file": (
                                "too-large.csv",
                                "name,region\nAlpha,West\n",
                                "text/csv",
                            )
                        },
                    )
                self.assertFalse(oversized_upload.json()["success"])
                self.assertIn("upload limit", oversized_upload.json()["error"])

                second_registration = second_client.post(
                    "/auth/register",
                    json={
                        "email": "second@example.com",
                        "password": "second-long-test-password",
                        "workspace_name": "Second workspace",
                    },
                )
                self.assertEqual(second_registration.status_code, 200)

                first_sources = first_client.get("/data-sources").json()["sources"]
                second_sources = second_client.get("/data-sources").json()["sources"]
                self.assertEqual(len(first_sources), 1)
                self.assertEqual(second_sources, [])
                self.assertEqual(
                    len(first_client.get("/audit-events").json()["events"]),
                    3,
                )
                self.assertEqual(
                    second_client.get("/audit-events").json()["events"],
                    [],
                )

                first_client.post("/auth/logout")
                self.assertEqual(
                    first_client.get("/data-sources").status_code,
                    401,
                )


if __name__ == "__main__":
    unittest.main()
