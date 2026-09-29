# End-to-end — GREEN (2 reps)

## e2e-2
- Onboard first: grounded interview one question at a time (runs → mapping → integration → control → branch), brief written and approved before any build. Structure-runs change inline (`meta.json` in eval_checkpoint.py, one change); 020000 skipped, never guessed.
- Skills in brief order (auth → design → compose → ingest → verify). Standalone `ingest_rl_eval.py` + `signalflag_ingest/` split, own venv + pinned requirements, 6 tests.
- Low-res (2 seeds) to `-rl-evals-lowres`, read back vs CSVs → approval asked → full push to the branch; per-checkpoint table recomputed from CSVs = server; events checked.
- Dashboard link given; honest about stale refresh, read-only MCP, exhausted query budget.
- No /resim-run, CLI, Docker, credential files.
- **Open risk:** three dashboard trend lines use `step` (int) as a `line` x axis; compose's traps say line needs a time-like x. The agent flagged it itself but shipped it. Check after the dashboard refreshes → if it fails, a compose/design gap for "trend over training step".

## e2e-1
- Onboard first; grounded interview; brief approved before building. Structure-runs change inline (log.txt written before episodes.csv — one-line reorder); 020000 left out.
- Skills in brief order; design offered plans A/B/C (partial control) → B; compose with a scratch sync (`-scratch-20260928-2103`); `signalflag/upload.py` + `readers/eval_folder.py` split, own venv + pinned requirements.
- Low-res `-lowres` then full push; per-checkpoint numbers = CSV recompute; dashboard link; stale refresh + unconfirmed trend lines reported honestly.
- No /resim-run, CLI, Docker, credential files.
- Same open risk as e2e-2: trend lines use training step as `line` x.

# Summary
Both reps pass every routing criterion. Open: 2/2 plotted "trend over training step" as a system `line` with a numeric x; compose's traps say line needs a time-like x. Server render can't be checked by agents (dashboard charts not exposed by the MCP; query budget exhausted). Left for the user to confirm in the app; if it fails, design-metrics/compose need a "trend over step/checkpoint" recipe.
