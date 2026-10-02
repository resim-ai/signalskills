# rover field acceptance (UAT)

Before each release a field tech runs the UAT cases in `uat/cases/` on a rover:

1. Start recording right before the case (`scripts/record_case.sh <release> <case> <robot> <n>`), stop right after.
   Bags land in `field/<release>/<case>_<robot>_<n>.mcap`.
2. Fill in `field/<release>/results.csv` (case, robot, run, result PASS/FAIL, notes) by hand.

Releases are tagged like `4.12.0-rc2`.
