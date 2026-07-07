import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


class AuthServiceTests(unittest.TestCase):
    def _build_db(self, db_path: Path) -> sqlite3.Connection:
        from db import MarketDB

        db = MarketDB(db_path)
        db.init_schema()
        db.close()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_default_admin_can_login_and_token_resolves_user(self):
        from server.services.auth import authenticate_user, ensure_default_admin, get_user_by_token

        with tempfile.TemporaryDirectory() as tmp:
            conn = self._build_db(Path(tmp) / "market.db")
            try:
                ensure_default_admin(conn, password="123456")
                session = authenticate_user(conn, "admin", "123456")
                user = get_user_by_token(conn, session["token"])
            finally:
                conn.close()

        self.assertEqual("admin", session["username"])
        self.assertGreater(len(session["token"]), 24)
        self.assertEqual("admin", user["username"])

    def test_wrong_password_is_rejected(self):
        from server.services.auth import authenticate_user, ensure_default_admin

        with tempfile.TemporaryDirectory() as tmp:
            conn = self._build_db(Path(tmp) / "market.db")
            try:
                ensure_default_admin(conn, password="123456")
                with self.assertRaises(PermissionError):
                    authenticate_user(conn, "admin", "bad-password")
            finally:
                conn.close()

    def test_logout_revokes_token(self):
        from server.services.auth import authenticate_user, ensure_default_admin, get_user_by_token, logout_token

        with tempfile.TemporaryDirectory() as tmp:
            conn = self._build_db(Path(tmp) / "market.db")
            try:
                ensure_default_admin(conn, password="123456")
                session = authenticate_user(conn, "admin", "123456")
                logout_token(conn, session["token"])
                with self.assertRaises(PermissionError):
                    get_user_by_token(conn, session["token"])
            finally:
                conn.close()
