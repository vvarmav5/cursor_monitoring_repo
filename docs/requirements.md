# Demo Monitoring Infrastructure — Requirements

Local demo for watching Linux servers without signing in to each host. One Flask app, running on this machine, shows a live read-only snapshot of CPU, memory, network, and listening ports.

## Problem

Infrastructure and application teams currently open a shell on each server to check memory, CPU, network, and port usage. This demo replaces that routine check with one local web page.

## Users

Internal L1, L2, and L3 teams across infrastructure and application development. For this demo they share one account: username `admin`.

## Demo boundaries

In scope:

- Sign in on this machine
- Add and remove Linux servers in the app inventory
- Show a live snapshot for a selected server

Out of scope:

- Windows or other operating systems
- Charts, history, and alerting
- Separate roles or extra user accounts
- Any change to the remote server (files, packages, services, firewall)

The app may add and remove rows in its own inventory. It must not change the monitored host.

## Tech stack

- Python 3
- Flask (server, pages, and sign-in)
- Server-rendered pages with a small amount of browser script for refresh
- SQLite in the project directory for the admin password hash and the server list
- Paramiko for SSH

Run it only on the machine where this project lives. No separate front-end build and no remote hosting.

## Feature 1 — Readable live dashboard

A signed-in user opens a server and sees the current snapshot:

- CPU use (percent)
- Memory use (used, free, total)
- Network use (bytes in and out per interface since boot, or the latest counters the host reports)
- Listening ports (port, protocol, address, process name when the host provides it)

The page refreshes about every 5 seconds without a full reload. Each value is labeled in plain language. A failed check shows a short error on that server (unreachable, authentication failed, or timed out) and leaves the rest of the app usable.

The dashboard does not offer actions that run on the remote host.

## Feature 2 — Admin sign-in

Username is always `admin`.

First visit, when no password hash exists:

1. The app shows a setup page.
2. The user chooses a password and confirms it.
3. The app stores only a one-way hash (Werkzeug or bcrypt) and sends the user to sign-in.

Later visits show a sign-in form. A correct password starts a session. Sign-out ends it. Pages other than setup and sign-in require a session.

The plaintext password is never written to the database, logs, or the page.

## Feature 3 — Linux server inventory

A signed-in user can add a Linux server with:

- Display name
- Host name or IP address
- SSH port (default 22)
- SSH user name
- SSH password

The list supports remove. Choosing a server opens its live dashboard.

Connection details stay in the local SQLite file and are used only to open SSH and run read-only commands, for example `cat /proc/stat`, `free`, interface counters under `/proc/net/dev`, and `ss` (or `netstat` if `ss` is missing). Commands are fixed by the app. User-typed shell input is not accepted.

## Local run

From the project directory:

1. Create a virtual environment and install dependencies (`flask`, `paramiko`, and the password-hash library if it is not Werkzeug).
2. Start the Flask app bound to `127.0.0.1` and a local port.
3. Open that address in a browser.
4. Set the admin password on first run, then sign in.
5. Add a Linux host that this machine can reach over SSH, and confirm the snapshot refreshes.

## Done when

- First run stores a password hash and later sign-in works only for `admin` plus that password.
- A server can be added and removed, and the list survives an app restart.
- The dashboard shows CPU, memory, network, and listening ports for that host, updating about every 5 seconds.
- The UI can change the inventory and cannot change the remote host.
- The app is usable in a desktop browser on this machine without extra services.
