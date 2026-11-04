import unittest

import store
from tests.support import SSH_PASSWORD, build_app, csrf_from, save_admin, sign_in


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.app, self.directory, self.database = build_app()
        self.client = self.app.test_client()
        save_admin(self.client)
        sign_in(self.client)

    def tearDown(self):
        self.directory.cleanup()

    def server_form(self, **overrides):
        page = self.client.get("/")
        payload = {
            "csrf_token": csrf_from(page),
            "display_name": "Web",
            "host": "10.1.1.8",
            "port": "22",
            "ssh_user": "monitor",
            "ssh_password": SSH_PASSWORD,
        }
        payload.update(overrides)
        return payload

    def test_add_list_remove_and_restart(self):
        saved = self.client.post("/servers", data=self.server_form())
        self.assertEqual(saved.status_code, 302)

        listed = self.client.get("/")
        body = listed.get_data(as_text=True)
        self.assertIn("Web", body)
        self.assertIn("10.1.1.8:22", body)
        self.assertIn("Monitored Linux servers", body)
        self.assertNotIn(SSH_PASSWORD, body)
        self.assertNotIn(">monitor<", body)

        connection = store.connect(self.database)
        try:
            rows = store.list_servers(connection)
            server_id = rows[0]["id"]
        finally:
            connection.close()

        removed = self.client.post(
            f"/servers/{server_id}/delete",
            data={"csrf_token": csrf_from(listed)},
        )
        self.assertEqual(removed.status_code, 302)
        after = self.client.get("/")
        self.assertIn("No servers yet.", after.get_data(as_text=True))
        self.assertNotIn(">Web<", after.get_data(as_text=True))

        self.client.post("/servers", data=self.server_form(display_name="Kept"))
        restarted, directory, _database = build_app_with_same_db(self.database)
        try:
            client = restarted.test_client()
            sign_in(client)
            again = client.get("/")
            text = again.get_data(as_text=True)
            self.assertIn("Kept", text)
            self.assertNotIn(SSH_PASSWORD, text)
        finally:
            directory.cleanup()

    def test_bad_port_is_rejected(self):
        response = self.client.post("/servers", data=self.server_form(port="70000"))
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Enter a port from 1 to 65535.", body)
        self.assertIn("No servers yet.", body)
        self.assertNotIn(SSH_PASSWORD, body)
        connection = store.connect(self.database)
        try:
            self.assertEqual(list(store.list_servers(connection)), [])
        finally:
            connection.close()


def build_app_with_same_db(database):
    import os
    import tempfile

    from app import create_app
    from tests.support import FAKE_SECRET

    directory = tempfile.TemporaryDirectory()
    os.makedirs(directory.name, exist_ok=True)
    app = create_app(
        {
            "SECRET_KEY": FAKE_SECRET,
            "DATABASE": database,
            "TESTING": True,
        }
    )
    return app, directory, database


if __name__ == "__main__":
    unittest.main()
