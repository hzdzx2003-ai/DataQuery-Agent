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

UI checks are separate from historical evaluation scores. See the validation status below.

## Integration verification

The local suite contains 24 tests, including rendering all 100 saved cases, public-directory portability, corrupt artifact refusal, clarification state isolation, and the injected parser boundary. `test_backend_integration.py` generates a fresh fictional database in a temporary directory and checks all 100 saved decisions against the original outputs. The fixture is opened read-only and removed after testing.

`query_service.py` accepts an explicitly supplied client and executor; it does not load credentials or provide an HTTP transport. Its fake-client integration test exercises the unchanged parser and fixed SQL backend. This is not evidence of new model accuracy or completed live UI integration.

Current validation: automated interaction and synthetic integration tests passed. Browser screenshot inspection could not be completed because the local browser automation runtime failed to initialize. No public hosted application has been deployed. The root legacy app remains available independently.
