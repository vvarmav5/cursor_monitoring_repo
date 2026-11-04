import os
import re
import tempfile

from app import create_app

ADMIN_PASSWORD = "admin-plain-secret-77"
SSH_PASSWORD = "ssh-secret-XYZZY-99"
FAKE_SECRET = "fake-test-secret"


def build_app():
    directory = tempfile.TemporaryDirectory()
    database = os.path.join(directory.name, "test.db")
    app = create_app(
        {
            "SECRET_KEY": FAKE_SECRET,
            "DATABASE": database,
            "TESTING": True,
        }
    )
    return app, directory, database


def csrf_from(response):
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    if match is None:
        raise AssertionError("missing csrf token")
    return match.group(1)


def save_admin(client, password=ADMIN_PASSWORD):
    page = client.get("/setup")
    return client.post(
        "/setup",
        data={
            "password": password,
            "confirm": password,
            "csrf_token": csrf_from(page),
        },
    )


def sign_in(client, username="admin", password=ADMIN_PASSWORD):
    page = client.get("/signin")
    return client.post(
        "/signin",
        data={
            "username": username,
            "password": password,
            "csrf_token": csrf_from(page),
        },
    )
