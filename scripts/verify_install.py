"""
verify_install.py
=================
Smoke-test the RatInABox training environment.

Exercises the specific API surface used throughout the tutorials + solutions so
that (a) the pixi environment is proven working, and (b) we have a single place
that documents the *verified* API for the pinned RatInABox library.

Run:  pixi run verify
"""
import sys
import importlib.metadata as _md
import numpy as np
import matplotlib

matplotlib.use("Agg")  # headless: never pop a window
import matplotlib.pyplot as plt

import ratinabox
from ratinabox.Environment import Environment
from ratinabox.Agent import Agent
from ratinabox.Neurons import (
    PlaceCells,
    GridCells,
    BoundaryVectorCells,
    ObjectVectorCells,
    HeadDirectionCells,
    VelocityCells,
    SpeedCell,
    FeedForwardLayer,
    Neurons,
)

ok = []
def check(label, cond):
    ok.append(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")


print(f"Python           : {sys.version.split()[0]}")
print(f"numpy            : {np.__version__}")
print(f"matplotlib       : {matplotlib.__version__}")
print(f"ratinabox        : {_md.version('ratinabox')}")
print("-" * 60)

# Keep RiaB from auto-styling / auto-saving during the smoke test.
ratinabox.stylize_plots = False
ratinabox.autosave_plots = False

# ---------------------------------------------------------------- Environments
print("Environment")
env2d = Environment(params={"scale": 1.0, "boundary_conditions": "solid"})
check("2D env default dimensionality", env2d.dimensionality == "2D")

env1d = Environment(params={"dimensionality": "1D", "scale": 2.0})
check("1D env", env1d.dimensionality == "1D")

# Structured environment: add a wall + a hole + an object.
env_maze = Environment(params={"scale": 1.0})
env_maze.add_wall([[0.5, 0.0], [0.5, 0.6]])
check("add_wall", len(env_maze.walls) >= 1)
env_maze.add_object([0.2, 0.8])  # object at a location
check("add_object", np.asarray(env_maze.objects["objects"]).shape[0] >= 1)

# ---------------------------------------------------------------------- Agent
print("Agent")
Ag = Agent(env2d, params={"speed_mean": 0.08, "dt": 0.05})
for _ in range(200):
    Ag.update()
check("Agent.update populates history pos", len(Ag.history["pos"]) == 200)
check("Agent.pos is 2-vector", np.asarray(Ag.pos).shape == (2,))
check("Agent.history has head_direction", "head_direction" in Ag.history)
pos_arr = np.array(Ag.history["pos"])
vel_arr = np.array(Ag.history["vel"])
check("history pos array shape", pos_arr.shape == (200, 2))
check("history vel array shape", vel_arr.shape == (200, 2))

# Import a trajectory (drive the agent along known positions).
Ag_imp = Agent(env2d)
times = np.linspace(0, 10, 50)
positions = np.stack([np.linspace(0.1, 0.9, 50), 0.5 * np.ones(50)], axis=1)
Ag_imp.import_trajectory(times=times, positions=positions)
Ag_imp.update()
check("import_trajectory + update", len(Ag_imp.history["pos"]) == 1)

# ------------------------------------------------------------------ PlaceCells
print("PlaceCells")
Ag2 = Agent(env2d, params={"dt": 0.05})
pc = PlaceCells(Ag2, params={"n": 12, "description": "gaussian", "widths": 0.2})
check("PlaceCells n", pc.n == 12)
fr = pc.get_state()
# Convention: get_state() returns (n, n_positions); at the current pos that is (n, 1).
check("get_state returns (n, 1) at current pos", np.asarray(fr).shape == (12, 1))
# Drive + collect firing history.
for _ in range(300):
    Ag2.update()
    pc.update()
check("Neuron firingrate history length", len(pc.history["firingrate"]) == 300)
fr_hist = np.array(pc.history["firingrate"])
check("firingrate history shape (T,n)", fr_hist.shape == (300, 12))

# Spikes (Poisson) — used for the spiking module.
spikes = np.array(pc.history["spikes"])
check("spikes history present", spikes.shape == (300, 12))

# Rate map computation (analytic) at a grid of positions.
rm = pc.get_state(evaluate_at="all")
check("get_state(evaluate_at='all') -> (n, n_pos)", rm.ndim == 2 and rm.shape[0] == 12)

# Other place-cell descriptions must all construct.
for desc in ["gaussian_threshold", "diff_of_gaussians", "top_hat", "one_hot"]:
    _pc = PlaceCells(Ag2, params={"n": 5, "description": desc})
    _ = _pc.get_state()
check("all place-cell descriptions construct", True)

# --------------------------------------------- Head direction / velocity cells
print("HeadDirection / Velocity / Speed")
hd = HeadDirectionCells(Ag2, params={"n": 8})
check("HeadDirectionCells", np.asarray(hd.get_state()).shape == (8, 1))
vc = VelocityCells(Ag2)
check("VelocityCells get_state (n,1)", np.asarray(vc.get_state()).ndim == 2)
sc = SpeedCell(Ag2)
check("SpeedCell get_state", np.asarray(sc.get_state()).ndim >= 1)

# ---------------------------------------------------------- The wider cell zoo
print("Grid / BVC / OVC")
gc = GridCells(Ag2, params={"n": 9})
check("GridCells", np.asarray(gc.get_state()).shape == (9, 1))
bvc = BoundaryVectorCells(Ag2, params={"n": 8})
check("BoundaryVectorCells", np.asarray(bvc.get_state()).shape == (8, 1))
ovc = ObjectVectorCells(Ag_maze := Agent(env_maze), params={"n": 4})
_ = ovc.get_state()
check("ObjectVectorCells", True)

# --------------------------------------------------- FeedForwardLayer (network)
print("FeedForwardLayer")
ff = FeedForwardLayer(Ag2, params={"n": 3, "input_layers": [pc]})
check("FeedForwardLayer get_state", np.asarray(ff.get_state()).shape == (3,))

# ------------------------------------------------------------------- Plotting
print("Plotting")
fig, ax = env2d.plot_environment()
check("Environment.plot_environment", fig is not None)
plt.close("all")
fig, ax = Ag2.plot_trajectory()
check("Agent.plot_trajectory", fig is not None)
plt.close("all")
fig, ax = pc.plot_rate_map(chosen_neurons="1")
check("Neurons.plot_rate_map", fig is not None)
plt.close("all")

print("-" * 60)
if all(ok):
    print(f"ALL {len(ok)} CHECKS PASSED  —  ratinabox {_md.version('ratinabox')} ready.")
    sys.exit(0)
else:
    print(f"{ok.count(False)}/{len(ok)} CHECKS FAILED")
    sys.exit(1)
