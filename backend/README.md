# Backend

FastAPI + SQLModel API for the Office Queue Management service. Data is stored in a local SQLite database (`OQM.db`), created automatically on startup.

Requires Python 3.10 or newer.

## Windows

Open a terminal in `backend`, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
fastapi dev app/main.py
```

## Unix / macOS

Open a terminal in `backend`, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
fastapi dev app/main.py
```

The first four commands are needed only once. Next time, just activate the virtual environment and start the server:

```bash
source .venv/bin/activate      # Windows: .\.venv\Scripts\Activate.ps1
fastapi dev app/main.py
```

## Using the API

The backend starts on:

```text
http://localhost:8000
```

The Swagger UI (interactive docs, where every endpoint can be tried) is available at:

```text
http://localhost:8000/docs
```

`fastapi dev` restarts the server automatically when a file is saved. Stop it with `Ctrl+C`.
To run without auto-reload, use `fastapi run app/main.py` instead.

## Adding a dependency

Install the package, then add it to `requirements.txt` so the rest of the team gets it too:

```bash
python -m pip install <package>
python -m pip freeze > requirements.txt
```

## Tests and coverage

With the virtual environment active, run all the tests in `backend_test/` (unit + integration) with coverage from `backend`:

```bash
python -m pytest
```

The settings are in `pyproject.toml`, so no extra options are needed. Coverage is measured on the app code in `app/` only.

Reports:

- the terminal shows a table with the coverage percentage and the uncovered line numbers;
- an HTML report is written to `htmlcov/`; open `htmlcov/index.html` in a browser.

To run a single file or test:

```bash
python -m pytest backend_test/unitTest/test_get_ticket.py
python -m pytest -k not_found
```

### E2E
To run the e2e tests make sure the `server is online` and run this command with newman (pay attention to be in the `backend/backend_test` folder):
```bash
newman run OQM_E2E.postman_collection.json
```
