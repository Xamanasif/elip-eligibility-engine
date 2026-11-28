# Deployment and verification

## Local presentation

Run the Windows commands in the [README](../README.md). The browser interface and the API use the same FastAPI server. Build the frontend from this revision before starting FastAPI. After the build, FastAPI serves the UI and API from one process.

For a clean presentation on Windows PowerShell:

```powershell
$env:ELIP_DB_PATH = Join-Path $env:TEMP ("elip-demo-" + [guid]::NewGuid() + ".sqlite3")
.venv\Scripts\python.exe -m uvicorn elip.app:app --host 127.0.0.1 --port 8765
```

For macOS or Linux:

```bash
ELIP_DB_PATH="$(mktemp -d)/demo.sqlite3" .venv/bin/python -m uvicorn elip.app:app --host 127.0.0.1 --port 8765
```

## Docker

```bash
docker build -t elip-eligibility .
docker volume create elip-demo-data
docker run --rm -p 127.0.0.1:8765:8765 -v elip-demo-data:/app/var elip-eligibility
```

The Dockerfile builds the React bundle and serves it with FastAPI. Docker was unavailable in the verification environment. The browser checks ran against the local FastAPI process. ## Public demo

Set `ELIP_READ_ONLY=1` in the service environment, then deploy the built app. This mode loads the checked-in fixtures, skips SQLite initialization, and rejects profile and evidence writes. A visitor can change criteria in their tab and preview matches, and refreshing returns to the reference profile. Local mode keeps the editable SQLite workflow. Host editable instances behind authentication and HTTPS.

`Download evidence` exports the currently filtered list as JSON, with the snapshot date, source links, check outcomes, and possible duplicate group IDs. The JSON contains no candidate profile. Use the All filter to export all 31 audit cards.

The public browser check targets a protected local instance on port 8766:

```bash
ELIP_READ_ONLY=1 python -m uvicorn elip.app:app --port 8766
# In another shell after installing Chromium:
python docs/browser-public-smoke.py
```

## Reproduce the browser checks

Start the server with a disposable SQLite database. The test changes profile fields, then restores the original profile. Run the commands below from the project root with the active Python environment.

```bash
python -m pip install playwright
python -m playwright install chromium
python docs/browser-smoke.py
```

Set `ELIP_TEST_URL` if the server uses another host or port. Set `ELIP_CHROMIUM_PATH` if you already have a compatible Chromium executable. The script takes real application screenshots in `docs/screenshots/`.

The browser checks cover all 31 real cards, each eligibility category, the baseline, rank order, filters, duplicate groups, per-job explanations, profile forms, persistence, recovery from a server error and version conflicts, six walkthrough cases, and responsive layouts. Mobile-width checks use Chromium viewport emulation.

## Evaluation interpretation

The real audit snapshot remains 9 ineligible, 21 needing confirmation, 1 closed and 0 verified eligible. The baseline top 10 still contains 10 unresolved cards. Rates for an empty verified shortlist have no denominator. The synthetic fixture demonstrates behavior with complete evidence. See `evaluation-current.json` for measured local outputs and `evaluation.json` for the original benchmark.
