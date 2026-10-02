# diffusion-policy-robomimic

Diffusion policy on robomimic `lift`, `can`, `square` (PH, low-dim). Training writes `ckpts/epoch_<n>.pt`
(not in git). Rollouts:

```
python rollout.py --ckpt ckpts/epoch_300.pt
```

writes `rollouts/epoch_<n>.hdf5`: 50 rollouts per task, robomimic layout
(`data/demo_<i>/{obs,actions,rewards,dones}`, attrs `success`, `task`).
