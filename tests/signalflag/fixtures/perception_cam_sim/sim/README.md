# Sim replays

The same perception stack (`acme/perception`, tag in ../compose.yaml) run on drives rendered in the yard
digital twin. `python ../replay/run_replay.py --source sim` writes `sim/outputs/<scenario>/`. Labels come
straight from the simulator, so they're exact. The real-drive replays are in ../outputs/.
