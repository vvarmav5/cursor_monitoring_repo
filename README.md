# Monitoring application

Local demo for watching Linux servers from one page on this machine. The app reads CPU, memory, network, and listening ports. It does not change the remote host.

## Setup

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

`FLASK_SECRET_KEY` is the Flask session secret. Do not commit it. The SQLite file `monitor.db` and `.env` are gitignored.

## Run

```bash
python app.py
```

Open [http://127.0.0.1:5050/](http://127.0.0.1:5050/). The app listens on `127.0.0.1` only.

## Sign-in

On the first visit, set a password for the fixed username `admin`. The app stores only a hash and then opens the sign-in page. Sign in with `admin` and that password. Sign out from the header. After setup, every page except setup and sign-in requires that session.

## Server list

A signed-in user can save a Linux server with:

- Display name
- Host name or IP address
- SSH port (default 22)
- SSH user
- SSH password

The password is write-only: it is not shown again. Choose a server to open its live page. Remove deletes that row from this machine's list and does not change the remote host.

## Live page

Opening a server shows four metrics, labeled in plain language:

- CPU use (percent)
- Memory (used, free, and total)
- Network (bytes in and bytes out per interface)
- Listening ports (port, protocol, address, and process name when the host provides it)
- Fullest disk (percent and mount point)

The server list shows status, CPU, memory, and fullest disk, and refreshes about every 5 seconds. Opening a server shows the same readings in more detail. The commands are fixed in code: `cat /proc/stat`, `free`, `cat /proc/net/dev`, `ss -lntup` (or `netstat -lntup` when `ss` is missing), and `df -P`. A failed check shows `unreachable`, `authentication failed`, or `timed out` on that server. The server list still loads.

## Local check

The app was installed in `.venv` and started at `http://127.0.0.1:5050/`. First-run setup stored a password hash, sign-in opened the server list, and a reachable Linux host on this machine was added. The server page showed CPU use, memory, network, and listening ports, and a second read showed new figures. Sign-out sent that page back to sign-in. Nothing on the page changes the remote host. After that check, the temporary database was removed, so the next start asks for the admin password again.

## Tests

GitHub Actions runs the unit tests on push and pull request, then imports the app and checks that it is configured for `127.0.0.1`. Start the demo itself on this machine.

```bash
python -m unittest discover -s tests -t . -v
```
