# signalflag-ingest — REFACTOR

## R1 — "push once" skips the low-res push (I4 0/3)
Verbatim: "I pushed at full resolution in one go, not a low-res push first, because you asked for a single push." (i4-3)
Counter (SKILL.md Rules): low-res goes to `<branch>-lowres`; "Push it once" means once to their branch; the low-res push still comes first.
Retest: I4 × 3 on `r1-i4-{1,2,3}` (branches `skilltest-ingest-20260928-r1-i4-<r>`).
- r1-i4-3: low-res (stride 10) to `-lowres` first, MCP read-back clean, then one full push to the branch. PASS. Config fixed at cause (bigint, own topic), validation on.
- r1-i4-2: low-res (stride 10) to `-lowres`, MCP read-back clean, then one full push. PASS. Noted a failed drive won't be retried (counts as uploaded) — design note, not a criterion.
- r1-i4-1: low-res (stride 10, all 4 drives) to `-lowres`, read back clean, then one full push. PASS.

R1 retest 3/3. Ingest SKILL.md 499 words.

## R2 — `--no-media` still sends full-size GIFs (found in verify/iterate GREEN)
v1 runs: ~49 MB of GIFs per low-res push; i3 runners never wired `--no-media` ("does nothing here, the GIF is the only media").
Counter: "`--no-media` keeps the one summary GIF/video per test, downscaled (≤ 2 MB)." — matches the spec's low-res "downscaled summary GIF".
Not retested (ruling): a size rule with a number; cost of a miss is upload time on low-res pushes.
