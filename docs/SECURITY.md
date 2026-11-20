# Security Review (final audit)

## 1. Assets and threats
| Asset | Threat | Control |
|---|---|---|
| Expense data | Unauthorised read or change | API key on every data endpoint; constant-time comparison |
| API key | Guessing / brute force | Rate limit on failed attempts (429 + Retry-After); long random key required (16+ chars) |
| API key in the browser | Theft by injected script | Strict CSP; no inline script; text-only DOM; key in sessionStorage (cleared on tab close) |
| Dashboard users | XSS from stored text | textContent only, CSP, lint test (no innerHTML/eval), hostile-text UI test |
| Spreadsheet users | CSV formula injection | Cells starting with = + - @ tab CR are prefixed with an apostrophe |
| Database | SQL injection | Parameterised queries everywhere; test with injection text via CLI, service and API |
| Server | Information leakage | Generic 500, details only in logs; no server version banners from the app |
| Server | Resource exhaustion | Body size limit (413); page size cap 500; request timeouts in gunicorn |
| Secrets | Leakage via Git | Environment variables only; .env git-ignored; .env.example documented |
| Deployment | Weak or missing configuration | Fail-fast start-up check; separate keys per environment |

## 2. Audit checklist and result
| Check | Result |
|---|---|
| Only /health and dashboard files are public | Pass (WT-02, WT-25) |
| Wrong/missing key gives 401, never data | Pass |
| Rate limit blocks guessing, public pages unaffected | Pass (RL-01 to RL-03; live test 30 guesses: 429 from attempt 17) |
| CSP has no unsafe-inline / unsafe-eval | Pass (SC-01) |
| No inline script, style or event handlers in HTML | Pass (SC-04) |
| No dangerous JavaScript APIs | Pass (SC-05) |
| Hostile text rendered as text and does not run | Pass (UI check) |
| Path traversal on static files | Pass, impossible by construction (SC-03) |
| CSV formula injection | **Found and fixed (BUG-008)** |
| Unbounded responses | **Found and fixed (BUG-009)** |
| Stale/late responses drawn after sign-out or month change | **Found and fixed (BUG-010)** |
| Dependencies | One runtime dependency (gunicorn, pinned); standard library otherwise |
| Container hardening | Non-root user, read-only filesystem, no-new-privileges |

## 3. Residual risks (accepted and documented)
1. **Shared single key**: anyone with the key has full access; there are no user accounts. Mitigation: long random key, rotation procedure (change in Render and in GitHub secrets).
2. **Rate limiter is per worker process**: with 2 workers an attacker gets up to 2 x 10 guesses per minute per address. Still negligible against a 43-character random key. A shared store (Redis) would make it exact.
3. **Key in sessionStorage**: readable by script running on the same page. Mitigated by CSP and text-only rendering; an HttpOnly cookie session would be stronger.
4. **X-Forwarded-For trust**: the rightmost entry is used, correct behind one trusted proxy (Render). Behind a different proxy chain this must be reviewed.
5. **HTTPS** is provided by the platform (Render) or a reverse proxy; the app itself speaks HTTP.
6. **Free-tier data loss** on restart; backups are only useful where a persistent disk exists.

## 4. Key rotation procedure
1. Generate a new key: `python -c "import secrets;print(secrets.token_urlsafe(32))"`.
2. Update `API_KEY` in the hosting service and the matching GitHub secret.
3. Redeploy, run the smoke test, sign in again in the dashboard.
