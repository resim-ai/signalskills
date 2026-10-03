# behavior-sim

Nightly behavior regression: ~400 scenarios in `scenarios/<family>/<scenario_id>.yaml`, run by `simtest`.

```
python -m simtest run scenarios/ --out results/
```

Writes `results/<scenario_id>.json` (pass, min_ttc_s, max_decel, collisions, route_completion),
`results/junit.xml` and `results/summary.json`. Scenario ids never change once added.

CI: `.github/workflows/nightly.yml` (every night on main) and `.github/workflows/release.yml`
(release candidate tags `rc-*`).

## Known failures

`known_failures.yaml` lists scenarios that fail for ticketed reasons. They still run every night, but the
release job ignores them when deciding pass/fail. Nobody checks the list regularly, so some entries may already pass.
