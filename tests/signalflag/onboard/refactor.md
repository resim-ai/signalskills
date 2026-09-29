# signalflag-onboard — REFACTOR

## R1: data-first routing skipped compose-metrics (GREEN o5-1)
"I left out design-metrics and compose-metrics because metrics are deferred until grading exists." Ingest emits into topics declared in the config, so compose-metrics is needed whenever anything is emitted; data-first only makes design-metrics light.
Counter: route line states that compose-metrics is never skipped when anything is emitted; data-first keeps design-metrics (data profile + minimal set).

## Rename (user decision): signalflag-onboard → signalflag-sdk-onboard
To avoid collision with the SignalFlag MCP's server-side `onboard` skill (cloud path). Rounds 2–3 ran with that server skill available: 0/10 loaded it instead.

## O2 criterion corrected
The scenario expected structure-runs "yes"; the runner already writes log.txt with the checkpoint going forward, so "no, the old folder is an open item" is also right. Criterion now: either, justified from what the runner writes.

## Residual, left as-is
2/15 bundled two questions once. Each still led with a guess; no wording change.
