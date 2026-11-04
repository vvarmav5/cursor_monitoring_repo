# Implementation TODO

Local demo from [requirements.md](requirements.md). Finish one section before the next. Each section is one small change, plus its security check and a short README note.

## 1. Project initialization and basic UI

- [x] Add `requirements.txt` with Flask, a `README.md`, and a `.gitignore` for `.venv/`, `__pycache__/`, `*.db`, and `.env`.
- [x] Add a minimal Flask app that listens on `127.0.0.1` only.
- [x] Add one server-rendered page: a header, a short title, and an empty server area. Style it with one plain CSS file so the page is readable on a desktop browser.
- [x] Security: put no passwords or host credentials in the repo. Do not bind the app on a public interface.
- [x] Docs: README lists the virtualenv, install, and the local URL to open.

## 2. Sign-in and unit tests

- [x] Add a first-run page that sets a password for the fixed username `admin`, then stores only a Werkzeug password hash in SQLite.
- [x] Add sign-in, sign-out, and a session cookie (`HttpOnly`, `SameSite=Lax`). After setup, every page except setup and sign-in requires that session.
- [x] Reject a wrong password with the same message as an unknown user. Keep the password out of logs, templates, and the database.
- [x] Set the Flask secret from an environment variable. Add a CSRF token on the setup and sign-in forms.
- [x] Add unit tests for: hash is stored, plaintext is not stored, setup cannot run twice, bad password fails, and a page without a session redirects to sign-in.
- [x] Security: tests must use a temporary database and a fake secret, never a real password file.
- [x] Docs: README describes first-run setup, sign-in, and sign-out.

## 3. CI/CD with GitHub Actions

- [x] Add `.github/workflows/ci.yml` on push and pull request: install the dependencies and run the unit tests.
- [x] Add a smoke step in that workflow that imports the app and checks it is configured for `127.0.0.1`.
- [x] Security: set `permissions: contents: read`. Do not put secrets, SSH keys, or passwords in the workflow.
- [x] Docs: README says the workflow runs tests and an import check, and that the demo itself is started locally.

## 4. Server inventory

- [x] Add a signed-in form to save a Linux server: display name, host, SSH port (default 22), SSH user, and SSH password.
- [x] List saved servers and remove one by id. The list remains after a restart.
- [x] Validate the host and port before save. Use parameterized SQL only.
- [x] Security: gitignore the SQLite file. Never print the SSH password in HTML, JSON, or logs. The password field is write-only.
- [x] Add unit tests for add, list, remove, a bad port, and a response that does not contain the SSH password.
- [x] Docs: README lists the inventory fields and states that removing a row only changes the local list.

## 5. Read-only metric collection

- [x] Add a collector that opens SSH with Paramiko and runs only fixed commands: `/proc/stat`, `free`, `/proc/net/dev`, and `ss` (fall back to `netstat` when `ss` is missing).
- [x] Parse those commands into CPU percent, memory used/free/total, per-interface bytes in/out, and listening ports (port, protocol, address, process name when present).
- [x] Set a short connect and command timeout. On failure, return a short error string and no partial crash.
- [x] Security: do not pass inventory text into a shell. Do not accept a command from the request. Disconnect when the read finishes.
- [x] Add unit tests with a fake SSH client for a good parse, a timeout, and an authentication failure.
- [x] Docs: README names the four metrics and states that the command list is fixed in code.

## 6. Live dashboard

- [x] Add a signed-in page for one server that shows the four metrics with plain labels.
- [x] Refresh that page’s data about every 5 seconds from a JSON route, without reloading the whole page.
- [x] Show unreachable, authentication failed, and timed out on that server only. The inventory page still loads.
- [x] Security: the JSON route requires a session. The payload has metrics and errors only, no SSH user or password.
- [x] Add a unit test that the metrics route redirects when signed out, and a test that a collector error becomes the error string on the page.
- [x] Docs: README describes opening a server and what a failed check looks like.

## 7. Local demo check

- [x] From a new virtualenv, install, set the admin password, sign in, add one reachable Linux host, and confirm the snapshot updates.
- [x] Confirm sign-out blocks the dashboard, and confirm the app has no control that changes the remote host.
- [x] Security: confirm `.env`, the SQLite file, and any SSH material are untracked.
- [x] Docs: README matches the steps that were just run.
