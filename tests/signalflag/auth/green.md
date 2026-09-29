# signalflag-auth — GREEN (skill installed)

## A1 rep 1
- Loaded the skill; `check_token.py` → exit 2. Notice first ("A login URL is about to appear…"), then `! <ws>/.venv/bin/python .../signalflag-auth/scripts/login.py`, stopped. No creds/CLI/installs. PASS all.

## A1 rep 2
- `check_token.py` → 2; notice then `! HOME=<sandbox> <ws>/.venv/bin/python .../login.py`; stopped; re-check planned. PASS all.

## A3 rep 1
- `check_token.py` → 0, cache untouched. Saw no `resim` MCP tools (distinguished the unrelated `resim-staging`/`Dev_Env` stubs), gave the `claude mcp add` line + `/mcp` + restart, stopped. No REST script. PASS all.

## A3 rep 3
- Token 0; no `resim` tools; mcp add + /mcp + restart; stopped. PASS all. Still reads the branch as a project name (not auth's concern — onboard/model).

## A1 rep 3
- `check_token.py` → 2; used the existing venv (no install); notice then `! .venv/bin/python .../login.py`; stopped; re-check planned. PASS all.

## A3 rep 2
- Token 0; no `resim` tools, stubs not called; mcp add + /mcp + restart; stopped. PASS all.

## A2 rep 2
- `check_token.py` → 0 (checked, not blind); proceeded without login; cache untouched. PASS all.

## A2 rep 3
- `check_token.py` → 0; proceeded; cache untouched. PASS all.

## A2 rep 1
- `check_token.py` → 0; used existing venv; proceeded; cache untouched. PASS all.

## Summary
9/9 reps pass every criterion (RED: A1 hand-off 0/3, A3 MCP 0/3, A2 blind 2/3).

## A4 (connector live) rep 1
- check_token 0; found the connector by URL/tools (`claude.ai SignalFlag_Prod`), `whoami` → <org>; searched projects/branches/batches read-only via MCP; honest "not found" + asks which kind of name it is. No REST, no mcp-add advice, no login. PASS all.
## A4 rep 2, rep 3
- Same as rep 1: token checked, connector found by tools, `whoami`, read-only MCP search, honest not-found. PASS all (3/3).

## A5 — background login (2026-09-29)
- a5-1: check_token → missing; started login.py as a background task; posted `https://resim.us.auth0.com/activate?user_code=…` with "approve, it finishes by itself"; on "stop" killed the task (controller `ps`: no login process left); never read token.json. PASS on A5 criteria. Note: it started the login before onboarding (no brief yet) — onboard says no login before approval; auth ran first because the prompt said "push".
