import sys
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4


BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import auth


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth.db"
        self.path_patch = patch.object(auth, "AUTH_DB_PATH", self.db_path)
        self.path_patch.start()
        self.secret_patch = patch.dict(
            os.environ,
            {"ATLAS_SESSION_SECRET": "unit-test-session-secret"},
        )
        self.secret_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.secret_patch.stop()
        self.temp_dir.cleanup()

    def test_account_password_and_revocable_session(self):
        user = auth.register_user(
            "owner@example.com",
            "a-long-test-password",
            "Test Workspace",
        )

        self.assertEqual(
            auth.authenticate_user("OWNER@example.com", "a-long-test-password")["id"],
            user["id"],
        )
        self.assertIsNone(
            auth.authenticate_user("owner@example.com", "wrong-password")
        )

        token = auth.create_session(user["id"])
        self.assertEqual(auth.get_session_user(token)["id"], user["id"])
        auth.revoke_session(token)
        self.assertIsNone(auth.get_session_user(token))

    def test_password_policy_and_duplicate_email(self):
        with self.assertRaises(ValueError):
            auth.register_user("owner@example.com", "short", "Workspace")

        auth.register_user(
            "owner@example.com",
            "a-long-test-password",
            "Workspace",
        )
        with self.assertRaisesRegex(ValueError, "already exists"):
            auth.register_user(
                "OWNER@example.com",
                "another-long-password",
                "Another Workspace",
            )

    def test_authentication_rate_limit_can_block_and_be_cleared(self):
        key = "login-test:hashed-key"
        self.assertEqual(
            auth.check_auth_rate_limit(key, limit=2, window_seconds=60),
            0,
        )
        self.assertEqual(
            auth.check_auth_rate_limit(key, limit=2, window_seconds=60),
            0,
        )
        self.assertGreater(
            auth.check_auth_rate_limit(key, limit=2, window_seconds=60),
            0,
        )
        self.assertGreater(
            auth.check_auth_rate_limit(key, limit=2, window_seconds=60),
            0,
        )
        auth.clear_auth_rate_limit(key)
        self.assertEqual(
            auth.check_auth_rate_limit(key, limit=2, window_seconds=60),
            0,
        )

        expired_key = "login-expired:hashed-key"
        auth.check_auth_rate_limit(expired_key, limit=1, window_seconds=60)
        self.assertGreater(
            auth.check_auth_rate_limit(expired_key, limit=1, window_seconds=60),
            0,
        )
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "UPDATE auth_attempts SET blocked_until = 1 WHERE attempt_key = ?",
                (expired_key,),
            )
        self.assertEqual(
            auth.check_auth_rate_limit(expired_key, limit=1, window_seconds=60),
            0,
        )

    def test_production_requires_long_secrets_and_secure_cookie(self):
        with patch.dict(
            os.environ,
            {
                "ATLAS_ENV": "production",
                "ATLAS_SESSION_SECRET": "short",
                "ATLAS_SECRET_KEY": "short",
                "ATLAS_COOKIE_SECURE": "true",
                "ATLAS_ALLOWED_ORIGINS": "https://app.example.com",
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "ATLAS_SESSION_SECRET"):
                auth.require_production_auth_configuration()

        with patch.dict(
            os.environ,
            {
                "ATLAS_ENV": "production",
                "ATLAS_SESSION_SECRET": "s" * 48,
                "ATLAS_SECRET_KEY": "e" * 48,
                "ATLAS_COOKIE_SECURE": "false",
                "ATLAS_ALLOWED_ORIGINS": "https://app.example.com",
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "ATLAS_COOKIE_SECURE"):
                auth.require_production_auth_configuration()

        with patch.dict(
            os.environ,
            {
                "ATLAS_ENV": "production",
                "ATLAS_SESSION_SECRET": "s" * 48,
                "ATLAS_SECRET_KEY": "e" * 48,
                "ATLAS_COOKIE_SECURE": "true",
                "ATLAS_ALLOWED_ORIGINS": "http://localhost:3001",
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "must use HTTPS"):
                auth.require_production_auth_configuration()

        with patch.dict(
            os.environ,
            {
                "ATLAS_ENV": "production",
                "ATLAS_SESSION_SECRET": "s" * 48,
                "ATLAS_SECRET_KEY": "e" * 48,
                "ATLAS_COOKIE_SECURE": "true",
                "ATLAS_ALLOWED_ORIGINS": "https://app.example.com",
            },
        ):
            auth.require_production_auth_configuration()

        with patch.dict(
            os.environ,
            {
                "ATLAS_ENV": "production",
                "ATLAS_SESSION_SECRET": "s" * 48,
                "ATLAS_SECRET_KEY": "e" * 48,
                "ATLAS_COOKIE_SECURE": "true",
                "ATLAS_ALLOWED_ORIGINS": "https://app.example.com, *",
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "exact production"):
                auth.require_production_auth_configuration()


if __name__ == "__main__":
    unittest.main()
