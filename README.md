# Elip Eligibility Engine

An internship-matching prototype by Zaman Asif, BITS Pilani. The real dataset contains 31 Elip recommendation cards audited on 27 November 2026 for a January–June 2027 internship.

## Run the demo

The original Dashboard Update ZIP contains a built interface. For this revision, build the updated React interface with Node.js 22 before launching FastAPI. The Dockerfile also builds the frontend.

```bash
npm ci --prefix web
npm run build --prefix web
```

Python 3.11 or 3.12 can then run the app.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn elip.app:app --host 127.0.0.1 --port 8765
```

On macOS or Linux, use `python3 -m venv .venv` and `.venv/bin/python` in place of the Windows interpreter path. Open <http://127.0.0.1:8765/>. FastAPI’s API documentation is at <http://127.0.0.1:8765/docs>.

Each new SQLite database is seeded once. Set `ELIP_DB_PATH` to a separate database file to keep a clean demo or use your existing candidate profile. Use the updated project source and its frontend bundle together. Set `ELIP_READ_ONLY=1` for a public demo.

## Demonstrate in 90 seconds

1. Start in **Match review**. The real audit has zero verified jobs, 21 needing confirmation, 9 ineligible and 1 closed. Show the separate ranked Needs confirmation list and the breakdown of baseline and audit outcomes.
2. Open **Guided demo**. The reference profile stays fixed so a reviewer can reproduce the Infineon, Agoda, Celonis, Google and CommerceIQ cases even after editing the saved profile.
3. On the **Synthetic** step, open the eligible fixture and inspect the passed checks. Select **Open synthetic matches** to see it in the shortlist with a test-data label.
4. Return to **Candidate profile** to show the degree editor and preference chips. A saved change persists across refresh and updates matching. The **Elip posting** dataset shows conditional remote work and separate internship stipend and PPO figures.

## Develop and test

Requires Node.js 20.19+ or 22.12+ for frontend builds.

```bash
npm ci --prefix web
npm run build --prefix web
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m elip.evaluation
```

Browser checks are documented in [Deployment and verification](docs/DEPLOYMENT.md). Measured outputs are in [Pytest](docs/test-results.txt), [browser checks](docs/browser-results.json), [frontend build](docs/build-results.txt), and [evaluation](docs/evaluation-current.json). See [screenshots](docs/screenshots/), [design and API](docs/DESIGN.md), and [demo notes](docs/DEMO.md).

## Repository map

| Path | Purpose |
|---|---|
| `elip/engine.py`, `elip/models.py` | Eligibility rules, ranking, duplicate detection and typed schemas |
| `elip/store.py`, `elip/schema.sql` | SQLite persistence and verification history |
| `elip/app.py` | FastAPI and the compiled React dashboard |
| `data/` | Real audit, separate synthetic fixtures, Elip regression record and seed profile |
| `web/src/` | React/TypeScript UI |
| `tests/`, `docs/browser-smoke.py` | Engine, API and browser regression checks |
| `docs/` | Evidence, test outputs, screenshots and deployment instructions |
