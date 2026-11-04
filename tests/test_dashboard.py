import json
import unittest

from tests.support import SSH_PASSWORD, build_app, csrf_from, save_admin, sign_in


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.app, self.directory, self.database = build_app()
        self.client = self.app.test_client()
        save_admin(self.client)
        sign_in(self.client)
        page = self.client.get("/")
        self.client.post(
            "/servers",
            data={
                "csrf_token": csrf_from(page),
                "display_name": "Web",
                "host": "10.1.1.8",
                "port": "22",
                "ssh_user": "monitor",
                "ssh_password": SSH_PASSWORD,
            },
        )

    def tearDown(self):
        self.directory.cleanup()

    def test_metrics_route_redirects_when_signed_out(self):
        signed_out = self.app.test_client()
        response = signed_out.get("/servers/1/metrics")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/signin", response.headers["Location"])

    def test_collector_error_is_shown_on_the_page(self):
        self.app.config["COLLECT_METRICS"] = lambda server: {"error": "timed out"}
        page = self.client.get("/servers/1")
        body = page.get_data(as_text=True)
        self.assertEqual(page.status_code, 200)
        self.assertIn("timed out", body)
        self.assertNotIn(SSH_PASSWORD, body)
        self.assertNotIn("monitor", body)

        metrics = self.client.get("/servers/1/metrics")
        payload = metrics.get_json()
        self.assertEqual(payload["error"], "timed out")
        self.assertNotIn("ssh_password", payload)
        self.assertNotIn("ssh_user", payload)
        self.assertNotIn(SSH_PASSWORD, json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
