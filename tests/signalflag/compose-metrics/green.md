# signalflag-compose-metrics — GREEN (9 runs)

| Criterion | RED | GREEN |
|---|---|---|
| check_config clean | 0/9 | 9/9 |
| `skip_if_no_data` on every metric | 0/9 | 9/9 |
| One-line descriptions / scalar units | 4/9 / 3/9 | 9/9 / 9/9 |
| Config at `.resim/metrics/config.resim.yml`, templates in `templates/` | 1/9 | 9/9 |
| Accepted by a real sync | 8/9 | 8/9 — c1-1 failed: `CROSS JOIN (VALUES 'RMS', 'peak')` passed `validate_metrics_config` but the sync parser rejects it ("Expected: ), found: ,") |
| Existing branch topics kept (m6-eval) | 6/6 | 6/6 |
| Project found via paged list_projects | 1 miss (c3-2) | 9/9 |
| Custom template for XY map / box plot | 5/6 (c1-3 dropped row 10) | 6/6 |
| Validated the exact file | 7/9 (c2-1 doctored copy) | 9/9 (c1-2 also validated a disclosed diagnostic copy to test the rest — not to pass) |
| Hand-off without CLI | 8/9 | 9/9 ("config syncs when its Batch opens") |
| C2 additive after new field | trivially 3/3 | trivially 3/3 (scenario leak, see RED) |

New failure → REFACTOR R1: validator ≠ sync parser.
