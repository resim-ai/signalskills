"""PPO on ReachTarget-v1. Logs progress.csv every 10k steps."""
import argparse, csv, json
from pathlib import Path

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lr", type=float, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--total-steps", type=int, default=1_000_000)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    import gymnasium as gym
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import EvalCallback
    a.out.mkdir(parents=True, exist_ok=True)
    cfg = {"algo": "ppo", "env": "ReachTarget-v1", "lr": a.lr, "seed": a.seed, "total_steps": a.total_steps,
           "n_envs": 8, "batch_size": 256, "gamma": 0.99}
    (a.out / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
    env = gym.make_vec("ReachTarget-v1", num_envs=8)
    model = PPO("MlpPolicy", env, learning_rate=a.lr, seed=a.seed, batch_size=256)
    f = open(a.out / "progress.csv", "w", newline="")
    w = csv.writer(f)
    w.writerow(["step", "mean_return", "success_rate"])
    def log(cb):
        w.writerow([cb.num_timesteps, round(cb.last_mean_reward, 3), round(cb.last_success_rate, 3)])
        f.flush()
    model.learn(a.total_steps, callback=EvalCallback(gym.make("ReachTarget-v1"), eval_freq=10_000 // 8, callback_after_eval=log))

if __name__ == "__main__":
    main()
