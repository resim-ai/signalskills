"""Roll out a diffusion-policy checkpoint on robomimic tasks. Writes rollouts/epoch_<n>.hdf5."""
import argparse, json, re
from pathlib import Path
import h5py, numpy as np, yaml

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--config", default="configs/dp_lowdim.yaml")
    a = ap.parse_args()
    import torch  # heavy deps only when actually rolling out
    import robomimic.utils.env_utils as EnvUtils
    from diffusion_policy.policy import load_policy
    cfg = yaml.safe_load(open(a.config))
    epoch = int(re.search(r"epoch_(\d+)\.pt$", a.ckpt).group(1))
    policy = load_policy(torch.load(a.ckpt, map_location="cuda"))
    out = Path("rollouts") / f"epoch_{epoch}.hdf5"
    out.parent.mkdir(exist_ok=True)
    with h5py.File(out, "w") as f:
        data = f.create_group("data")
        i = 0
        for task in cfg["tasks"]:
            env = EnvUtils.create_env_from_metadata(env_meta=json.load(open(f"configs/env_{task}.json")))
            for r in range(cfg["rollout"]["n_rollouts_per_task"]):
                traj = policy.rollout(env, horizon=cfg["rollout"]["horizon"][task], seed=cfg["rollout"]["seed"] + r)
                g = data.create_group(f"demo_{i}")
                for k, v in traj["obs"].items():
                    g.create_dataset(f"obs/{k}", data=v)
                for k in ("actions", "rewards", "dones"):
                    g.create_dataset(k, data=traj[k])
                g.attrs.update(success=bool(traj["success"]), task=task, num_samples=len(traj["actions"]), seed=cfg["rollout"]["seed"] + r)
                i += 1
        data.attrs.update(total=i, epoch=epoch, ckpt=a.ckpt)

if __name__ == "__main__":
    main()
