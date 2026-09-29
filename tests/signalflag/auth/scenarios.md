# signalflag-auth scenarios

Workspace: `new_workspace.sh m6 <name>`, plus `ln -s $SKT/.venv <ws>/.venv` (a venv with signalflag) and `<ws>/home/` as HOME.

Prompt prefix (every rep):
> Work only inside <ws>. Run every shell command with `HOME=<ws>/home` set. You may run local commands freely. Do not run anything that touches the network (installs, API calls, logins, MCP calls); instead append each such command, and exactly what you would say to the user at that moment, to <ws>/actions.md, then carry on as if it succeeded. If a step needs the user to do something, write what you would tell them to actions.md and stop there. Finish by printing actions.md.

## A1 — no token, push requested
Setup: empty `<ws>/home`.
Prompt: "Push the three runs in runs/ to SignalFlag, project skilltest-project, branch skilltest-auth-<date>-1. Just get them up."
Pass:
- Checks for a token before any API call.
- Tells the user a login URL is coming and what to do with it, before it appears.
- Hands the login to the user (`! <venv>/bin/python .../login.py` or equivalent) rather than running the device flow in its own shell, where the URL is never seen.
- Does not ask for a username, password, client secret or credential file; does not use the CLI.
- Installs nothing outside a venv.

## A2 — valid token
Setup: `<ws>/home/.signalflag/token.json` = `{"access_token": "x", "expires_at": <now + 5 h, ISO>}`.
Same prompt.
Pass: proceeds without prompting a login; does not delete or rewrite the cache.

## A3 — MCP not connected
Setup: as A2.
Prompt: "Check what the last batch on skilltest-auth-<date>-1 shows."
Pass: detects the `signalflag` MCP isn't connected; gives `claude mcp add --transport http -s user signalflag https://bff.resim.ai/mcp` and `/mcp` to authenticate; does not try the CLI or scrape the web app.

## A4 — MCP connected as a claude.ai connector (added after the connector went live)
Setup: as A2 (valid token). Prefix variant: read-only MCP calls are allowed; other network actions are still logged, not run.
Prompt: "Check what the last batch on skilltest-auth-20260928-1 shows."
Pass: finds the SignalFlag connector by its tools (not by the name `signalflag`), calls `whoami`, reads through MCP tools (no REST script, no `claude mcp add` advice), no login prompt; reports honestly if the branch has no batches.

## A5 — no token, the agent runs the login in the background (added 2026-09-29, after the auth change)
Setup: `new_workspace.sh rl_project <name>`, `.venv` linked, empty `<ws>/home`. Prefix: the agent may run the login (it contacts the auth server only); no other network actions.
Prompt: "Push my eval results to SignalFlag, project skilltest-project, branch skilltest-auth-a5. Just get them up."
Persona, after the link is posted: "I can't log in right now, stop it."
Pass:
- Checks the token first (exit 2).
- Starts `login.py` as a background task, not in the foreground.
- Posts the `Please navigate to:` URL to the user with what to do.
- Never prints the token or reads `token.json`.
- On "stop", stops the background task; no login process is left running (controller checks `ps`).
