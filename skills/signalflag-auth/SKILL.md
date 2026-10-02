---
name: signalflag-auth
description: Use when about to call the SignalFlag (formerly ReSim) API or SDK — pushing batches, syncing metrics config, reading results — or when a SignalFlag call fails with 401/403, a device-code login appears, or batch results need reading back through the SignalFlag MCP.
---

# signalflag-auth

Before the first SignalFlag API call of a session: the SDK needs a token, and the MCP must be connected if results will be read back.

During onboarding, auth runs only after the user's go (signalflag-onboard). An unknown project before then is an open item in the brief, not a reason to log in; look it up here, after the go, with a paged `list_projects`.

## 1. Check the token

```bash
python3 <this skill's dir>/scripts/check_token.py
```

Stdlib only; never prints the token. Don't `cat` the cache — it's a credential file.

| Exit | Meaning | Do |
|---|---|---|
| 0 `valid until …` | Usable | Go on. Don't touch the cache. |
| 1 `expired` | Expires within 1 h — the SDK would start a new login | Log in (step 2) |
| 2 `missing` | No cache (`~/.signalflag/token.json`, or legacy `~/.resim/` when only that exists) | Log in (step 2) |

## 2. Log in: start it in the background, hand the user the link

`DeviceCodeClient()` prints a URL, then blocks until someone approves it (up to ~15 min). In the foreground or an upload script, the URL reaches no one and the shell hangs.

1. Start `<venv>/bin/python <this skill's dir>/scripts/login.py` as a **background task** (Bash `run_in_background`).
2. Read its output until `Please navigate to: https://…` appears. Post it: "Open this link and approve the SignalFlag login: <url>. It finishes by itself." The link is meant for them; the token and `token.json` are never shown.
3. Wait for the task to finish (you're notified). Exit 0 → re-run `check_token.py`; go on only on 0. Timed out or failed → say so and offer a fresh link.
4. They won't log in now, or the session is ending → stop the task. Leave no polling process behind.

No background tasks here? Ask them to run `! <venv>/bin/python <this skill's dir>/scripts/login.py` and wait.

Never call the API "and let it prompt if needed". No usernames, passwords, client secrets, credential files or CLI.

**`<venv>`**: the environment the brief names. If none yet, create `.venv-signalflag/` in the repo root, `pip install signalflag==1.8.0` into it, and add it to `.gitignore`. Install nothing outside a venv.

## 3. The MCP, for reading results

Reading what a batch shows goes through the SignalFlag MCP, not hand-written REST scripts: whichever server points at `https://bff.resim.ai/mcp`: often a claude.ai connector (tools named like `…SignalFlag_Prod__whoami`), sometimes a local one. Find it by its tools — `whoami`, `list_batches`, `get_metrics_summary` — not by its name. Call `whoami` once and check the org.

A server offering only `authenticate` is not connected: have the user finish it in `/mcp`. No such server at all: tell the user

```
claude mcp add --transport http -s user signalflag https://bff.resim.ai/mcp
```

then `/mcp` to authenticate it, and restart the session if its tools don't appear.

## On a 401 mid-work

Stop. Re-run `check_token.py`, then step 2. Never delete the cache.
