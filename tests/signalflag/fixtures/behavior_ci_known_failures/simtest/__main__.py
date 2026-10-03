import argparse
from pathlib import Path
from simtest.runner import run_all

ap = argparse.ArgumentParser(prog="simtest")
sub = ap.add_subparsers(dest="cmd", required=True)
r = sub.add_parser("run")
r.add_argument("scenarios", type=Path)
r.add_argument("--out", type=Path, default=Path("results"))
r.add_argument("--filter", default="", help="substring of scenario ids to run")
a = ap.parse_args()
raise SystemExit(run_all(a.scenarios, a.out, a.filter))
