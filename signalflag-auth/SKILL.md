---
name: signalflag-auth
description: Use when about to call the SignalFlag (formerly ReSim) API or SDK — pushing batches, syncing metrics config, reading results — or when a SignalFlag call fails with 401/403, a device-code login appears, or batch results need reading back through the SignalFlag MCP.
---

# signalflag-auth

Run this before the first SignalFlag API call of a session. Two things must be true: the SDK has a token, and the SignalFlag MCP is connected if results will be read back.

## 1. Check the token

```bash
python3 <this skill's dir>/scripts/check_token.py
```

Stdlib only; never prints the token. Don't `cat` the cache yourself — it is a credential file and permission checks may block it.

| Exit | Meaning | Do |
|---|---|---|
| 0 `valid until …` | Usable | Go on. Don't touch the cache. |
| 1 `expired` | Expires within 1 h — the SDK would start a new login | Log in (step 2) |
| 2 `missing` | No cache (`~/.signalflag/token.json`, or legacy `~/.resim/` when only that exists) | Log in (step 2) |

## 2. Log in: the user runs it, not you

`DeviceCodeClient()` prints a URL and blocks until someone approves it in a browser. Run in your shell, or inside an upload script, the URL never reaches the user and the call hangs for ~15 min.

So:
1. Tell the user first: "A login URL is about to appear. Open it, approve, and it finishes by itself."
2. Ask them to run, in this session:
   ```
   ! <venv>/bin/python <this skill's dir>/scripts/login.py
   ```
3. Wait for them. Re-run `check_token.py`; continue only on exit 0.

Never start the device flow yourself. Never call the API "and let it prompt if needed". No usernames, passwords, client secrets, credential files or CLI.

**`<venv>`**: the environment the brief names. If none yet, create `.venv-signalflag/` in the repo root, `pip install signalflag==1.8.0` into it, and add it to `.gitignore`. Install nothing outside a venv.

## 3. The MCP, for reading results

Reading what a batch shows — metrics, statuses, dashboards — goes through the SignalFlag MCP, not hand-written REST scripts. It is whichever server points at `https://bff.resim.ai/mcp`: often a claude.ai connector (tools named like `…SignalFlag_Prod__whoami`), sometimes a local one. Find it by its tools — `whoami`, `list_batches`, `get_metrics_summary` — not by its name. Call `whoami` once and check the org.

A server offering only `authenticate` is not connected: have the user finish it in `/mcp`. No such server at all: tell the user

```
claude mcp add --transport http -s user signalflag https://bff.resim.ai/mcp
```

then `/mcp` to authenticate it, and restart the session if its tools don't appear.

## On a 401 mid-work

Stop. Re-run `check_token.py`, then step 2. Don't delete the cache and re-run the upload.
