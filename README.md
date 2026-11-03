# Monitoring application

Local demo for watching Linux servers from one page on this machine. This step serves a single page with an empty server area.

## Setup

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Open [http://127.0.0.1:5050/](http://127.0.0.1:5050/). The app listens on `127.0.0.1` only.
