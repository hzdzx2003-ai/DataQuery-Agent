# DataQuery UI

Credential-free Streamlit viewer for the frozen nl-v3-93 release. Keep this directory alongside `releases/nl-v3-93`; the local development layout under `public_release_20261006` is also supported.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m streamlit run app.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
```

Run commands inside the UI directory. No key or private environment file is required. The original app entry point is not overwritten.

## Modes

- Saved case replay displays the recorded understanding and fixed-backend synthetic results. It makes no model/database request. All 100 cases remain accessible, not just successful ones.
- Real-time questions are visibly disabled pending live integration. Editing a saved question does not reuse a similar answer.
- Clarification input retains a draft only. It does not execute a candidate or claim completed multi-turn understanding.

## Tests

```powershell
.venv/Scripts/python -B -X utf8 -m unittest discover -s . -p "test_*.py" -v
```

UI checks are separate from historical evaluation scores. Browser visual validation and deployment status are recorded in PROGRESS.md.
