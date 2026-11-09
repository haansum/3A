# ko/ — KO animation framework (pre-design evaluation)

Nothing here is the framework yet. This holds the evidence behind the simulator
build-vs-buy recommendation in the design document.

    pip install mujoco numpy
    python ko/eval/rope_bench.py > ko/eval/results_mujoco4_cpu.json

`eval/rope_bench.py` tests MuJoCo on rope sag vs the analytic cable solution, a 55 kg
drop on one rope, and a limp ragdoll falling into a four-rope ring side (stability,
penetration, speed, determinism). Rope preload, mass and end stiffness are assumed
values, not measurements.
