# signalflag-verify scenarios

Workspaces are copies of GREEN ingest workspaces (with their venv and token). Prefix:
> Work only inside <ws>. Run every shell command with `HOME=<ws>/home` set. I'm the user; I'll answer your messages. You may upload to SignalFlag, but only to project skilltest-project and only to branches starting `skilltest-verify-20260928-<scenario>-<rep>` — use that in place of the brief's branch. Don't attach bag (.mcap) files (network budget).

## V1 — M6 (copy of green-i1-1; brief c1.md)
Prompt: "Verify the SignalFlag setup against the brief."
## V2 — planted fault (copy of green-i4-1; brief c2.md; `readers/parquet.py` silently multiplies `speed_mps` by 3.6)
Prompt: same.

Pass:
- Low-res first, on a scratch branch, via the ingest's low-res flags; high-res only after low-res passes, on the (substituted) brief branch.
- Low-res checks reported: config synced, emits validated, jobs SUCCEEDED, no LogUploadError, every metric in the set has data via the MCP (no ERROR/NO_DATA), statuses as the brief expects.
- Batch link handed to the user after low-res.
- High-res: test and event counts vs source; metric values spot-checked against local recomputation straight from the source files (not from the reader's rows alone).
- V2: the scaled column is caught (mismatch vs source / brief's data profile, max speed ~2.07 m/s) and fixed in the reader, not by a new branch or a config edit.
- Results written to the brief's `## Verification`.
