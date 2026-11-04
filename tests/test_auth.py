import unittest

from werkzeug.security import check_password_hash

import store
from app import AUTH_ERROR, HOST
from tests.support import ADMIN_PASSWORD, build_app, save_admin, sign_in


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.app, self.directory, self.database = build_app()
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def test_app_is_bound_to_localhost(self):
        self.assertEqual(HOST, "127.0.0.1")
        self.assertEqual(self.app.config["HOST"], "127.0.0.1")

    def test_hash_is_stored_and_plaintext_is_not(self):
        response = save_admin(self.client)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/signin", response.headers["Location"])

        with open(self.database, "rb") as handle:
            raw = handle.read()
        self.assertNotIn(ADMIN_PASSWORD.encode(), raw)

        connection = store.connect(self.database)
        try:
            stored = store.admin_hash(connection)
        finally:
            connection.close()
        self.assertIsNotNone(stored)
        self.assertNotIn(ADMIN_PASSWORD, stored)
        self.assertTrue(check_password_hash(stored, ADMIN_PASSWORD))
        self.assertTrue(stored.startswith(("scrypt:", "pbkdf2:")))

    def test_setup_cannot_run_twice(self):
        save_admin(self.client)
        connection = store.connect(self.database)
        try:
            original = store.admin_hash(connection)
        finally:
            connection.close()

        again = self.client.post(
            "/setup",
            data={"password": "another-password-value", "confirm": "another-password-value"},
        )
        self.assertEqual(again.status_code, 302)
        self.assertIn("/signin", again.headers["Location"])

        connection = store.connect(self.database)
        try:
            self.assertEqual(store.admin_hash(connection), original)
        finally:
            connection.close()
        with open(self.database, "rb") as handle:
            self.assertNotIn(b"another-password-value", handle.read())

    def test_bad_password_matches_unknown_user(self):
        save_admin(self.client)
        wrong_user = sign_in(self.client, username="someone-else", password=ADMIN_PASSWORD)
        wrong_password = sign_in(self.client, username="admin", password="not-the-password")
        self.assertEqual(wrong_user.status_code, wrong_password.status_code)
        self.assertIn(AUTH_ERROR, wrong_user.get_data(as_text=True))
        self.assertIn(AUTH_ERROR, wrong_password.get_data(as_text=True))
        self.assertNotIn(ADMIN_PASSWORD, wrong_user.get_data(as_text=True))
        self.assertNotIn("not-the-password", wrong_password.get_data(as_text=True))
        with self.client.session_transaction() as current:
            self.assertNotIn("user", current)

    def test_page_without_a_session_redirects_to_sign_in(self):
        save_admin(self.client)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/signin", response.headers["Location"])

    def test_sign_in_cookie_is_httponly_and_lax(self):
        save_admin(self.client)
        response = sign_in(self.client)
        self.assertEqual(response.status_code, 302)
        cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)


if __name__ == "__main__":
    unittest.main()
