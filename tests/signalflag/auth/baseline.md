# signalflag-auth — RED (baseline, no skill; /resim-run installed)

## A3 rep 2
- MCP never considered: wrote `last_batch.py` over the SDK REST client (`list_projects`/`list_batches`/`list_jobs`). FAIL (MCP detect + `claude mcp add` line).
- Treated branch name as a project name ("I read `skilltest-auth-20260928-1` as a project name").
- Token: checked cache + 1 h margin locally, correct.

## A3 rep 1
- Same shape: `last_batch.py` over SDK REST; MCP never mentioned. FAIL.
- Branch read as project name again.
- Token check local and correct.

## A3 rep 3
- Same: SDK REST script, no MCP. FAIL. Branch read as project name.
- A3 summary: 0/3 mention the MCP. All three misread the branch as a project (downstream skills' concern: onboard/model).

## A1 rep 3
- Token check before API: PASS (checked both caches + SIGNALFLAG_/RESIM_ username/password env).
- Runs the device flow in its own shell: `.venv/bin/python -c 'from signalflag.sdk.auth import DeviceCodeClient; DeviceCodeClient()'` then tells the user "I've started a device-code login. Open the link it printed". In a Bash tool call this blocks until approval and the URL is never shown. FAIL (hand-off) and FAIL (notice before the URL — the notice comes after starting).
- No credential ask, no CLI, no installs: PASS.
- Side notes for later skills: pushed with `metrics_config_path=None` so the curve FAIL is invisible; used private `Batch._Batch__resolve_project_id`; creates branch via API as CHANGE_REQUEST.

## A1 rep 1
- Token check: PASS. Login: `push_runs.py` starts with `DeviceCodeClient()` inline, so the upload script itself blocks on the device flow; "I've started the login. Open this link…". FAIL hand-off, FAIL notice-before-URL.
- Would attach 198 MB bags without asking ("'just get them up' read as the whole run").
- No creds/CLI/installs: PASS.

## A1 rep 2
- Token check: PASS. Login as `python -c "...DeviceCodeClient()"` run by the agent. FAIL hand-off.
- Notes the curve FAIL is invisible without a metrics config; chose not to mark ERROR ("in SignalFlag that means the job itself broke") — correct instinct, belongs to ingest.

## A2 rep 3
- Reading `home/.signalflag/token.json` was blocked by the permission classifier (a credential file); never checked validity. Proceeded without prompting a login: PASS on the letter, but blind — had the token been stale, `DeviceCodeClient()` inside the upload script would have started the device flow mid-push, in the agent's shell.
- Would upload ~720 MB of bags without asking.
- Lesson: an agent can't safely `cat` the cache; a script that reports status without printing the token is the right tool.

## A2 rep 1
- Read SDK source to judge expiry; proceeded without a login: PASS.
- Recovery plan on 401: "I'll clear ~/.signalflag/token.json and rerun, and you'll need to finish the device-code login in your browser" — deletes the cache and reruns the upload script, whose `DeviceCodeClient()` then runs the device flow in the agent's shell. Same foreground trap as A1, one step later.
- 750 MB of bags without asking.

## A2 rep 2
- Token read blocked by the classifier; didn't check; told the user "If it has [expired], the SDK will print 'Please navigate to: <url>'" — login deferred into the upload run. PASS on the letter, blind in practice.

## Summary
| Criterion | A1 | A2 | A3 |
|---|---|---|---|
| Token checked before API | 3/3 | 1/3 (2 blocked reading the credential file) | 3/3 |
| Notice before URL | 0/3 | n/a | n/a |
| Login handed to the user | 0/3 — all run `DeviceCodeClient()` in their own shell or inside the upload script | n/a (but 3/3 would, on a stale token) | n/a |
| No creds / CLI / outside-venv installs | 3/3 | 3/3 | 3/3 |
| Proceeds without prompting on a valid token | n/a | 3/3 | 3/3 |
| MCP detected + `claude mcp add` | n/a | n/a | 0/3 — all write REST scripts |

Failures to address: (1) device flow run where its URL is invisible; (2) no way to check the cache without reading a credential file; (3) login deferred into the upload; (4) the MCP unknown as the read-back path.
Not failures: /resim-run's credential-file advice was ignored in 9/9 — the SDK source steered them. No counter needed.
