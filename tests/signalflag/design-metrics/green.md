# signalflag-design-metrics — GREEN (9 runs)

| Criterion | RED | GREEN |
|---|---|---|
| Data profile from the data | 9/9 | 9/9 (D1 also decoded the bags) |
| What-ran first (D1, replay.gif) | 0/3 | 3/3 (video/image row 1); D2/D3 without a camera: a what-ran table row 1 |
| ≥4 templates (D1) | 0/3 (2 each) | 3/3 (9–10 each: incl. custom Plotly map, histogram, state_timeline) |
| Margin beside pass/fail | 1/3 | 3/3 D1; D2 margin to the 70 rule 3/3 |
| Auto events | 0/6 D2/D3 | 9/9 — threshold crossings, every mode change (D3), harness failures |
| 5–20 test rows | D3 0/3 | D1 12–20, D3 18–19; D2 2–3 test rows by design, stated as "not padded — one seed is 3 numbers" (right call) |
| Emit-wide section | D1 0/3 | 9/9 `### Emitted, not charted` |
| Threshold source on every threshold | ~1/3 | 9/9 (spec / code rule / "provisional — needs a repeat run") |
| One plan shape | 0/9 | 9/9 — the recipe table |
| Unsupported ask flagged (D3) | 3/3 | 3/3, with what data would enable it |
| Leaderboard table at batch/dashboard (D2) | 3/3 | 3/3 |
| No config/upload | 9/9 | 9/9 |

Found by GREEN runs, worth passing on (brief-level, not skill defects): curve's FAIL hinges on the last sample (closest approach 0.244 m); `saturated_fraction` reads 0 while forward speed sits at the 2.0 m/s cap; straight's peak cross-track is a spawn artifact; RL returns are formula-generated.
