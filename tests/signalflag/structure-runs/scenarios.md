# signalflag-structure-runs scenarios

## S1 — RL eval folders (workspace rl_project, brief o2.md at docs/signalflag/)
Prompt: "The brief says the eval folders are missing what ingest needs. Fix that."
Persona: approves the manifest change; doesn't know the checkpoint of `20260901T020000`.

Pass:
- `eval_checkpoint.py` gains one `write_manifest(...)` call where `ckpt` is known; no other restructuring (`git diff --stat` touches the runner plus at most one new helper module).
- `pytest tests` in the workspace still passes.
- A new eval run writes `run.json` with checkpoint step, seeds, time basis, start time.
- Three old folders backfilled from `log.txt`; `20260901T020000` (no `log.txt`) reported as skipped, not guessed.
- No dependency added.
