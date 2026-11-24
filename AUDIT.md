# PyQuotex-Core — technical audit

Audit date: 2026-11-24

## Confirmed repository state
- FastAPI backend is at the repository root.
- Render web service is linked to branch `main` with automatic deploys.
- Hatchable dashboard calls the Render API at `https://pyquotex-core-api.onrender.com`.
- The original `pyquotex/` package directory from the supplied ZIP is not present in this repository yet.
- Therefore the API process can start, but the broker engine cannot load. A healthy HTTP process is not proof of a working Quotex session.

## Confirmed issues in the supplied ZIP
1. `pyquotex/stable_api.py`: `connect()` assigns a new `QuotexAPI` to `self.api` and immediately calls `await self.close()`. Since `close()` closes `self.api`, this closes the newly created connection object before authentication/connect.
2. The same `connect()` method recursively calls itself when `check_connect()` fails, without a retry limit. A persistent broker/network failure can recurse indefinitely.
3. `pyquotex/http/login.py`: OTP handling uses Python `input()`. This blocks a headless Render service and needs a non-interactive callback/OTP handoff before server use.
4. `pyquotex/config.py`: missing credentials trigger an interactive `input()`; the server must always receive credentials from environment variables and must never reach that prompt.
5. Candle/history loops in the ZIP wait on state without a maximum timeout in multiple methods. Server requests need bounded waits and clean cancellation.

## Backend changes committed
- DEMO/PRACTICE-only connection enforced.
- Broker connection timeout and candle/asset request timeouts added.
- Candidate client is closed after connection failure or timeout.
- Application shutdown closes the active client.
- Health/status endpoints distinguish package availability from connection state.
- CORS default narrowed to the deployed Hatchable origin; override with `CORS_ORIGINS`.
- `.gitignore` excludes credentials/session artifacts.
- Regression tests and GitHub Actions workflow added.

## Verification
- GitHub Actions regression suite passed on commit `76f570312072768d9e71e3ac5098fa6192ede142`.
- Render auto-deploy for that commit was still in progress at the time of this audit.
- Live broker login, candles, and assets have not been verified because the supplied `pyquotex/` package is not yet in the repository.

## Next required engineering steps
1. Transfer the exact 35 Python source files from the supplied ZIP into `pyquotex/`, excluding `__pycache__` and `.pyc`.
2. Patch the ZIP's `connect()` lifecycle bug and replace unbounded recursion with bounded retry/backoff.
3. Replace terminal OTP input with an asynchronous callback or secure out-of-band challenge flow.
4. Confirm package dependencies and Python runtime against the exact ZIP version; do not silently replace it with a different upstream release.
5. Test import, DEMO login, disconnect, assets, and candles against a Quotex DEMO account before enabling any order endpoint.

## Reference documentation
- Render web services: https://render.com/docs/web-services
- Render health checks: https://render.com/docs/health-checks
- Render environment variables and secrets: https://render.com/docs/configure-environment-variables
- PyQuotex installation: https://cleitonleonel.github.io/pyquotex/pt/1.%20Instala%C3%A7%C3%A3o%20e%20Configura%C3%A7%C3%A3o.html
- PyQuotex connection/authentication: https://cleitonleonel.github.io/pyquotex/pt/2.%20Conex%C3%A3o%20e%20Autentica%C3%A7%C3%A3o.html
