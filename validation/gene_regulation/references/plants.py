"""The plants: the sheet's eight (§5.4 for A1, §5.2 for A1-M) and the references' own.

Each plant is the exact edit it names (model.SHEET_EDITS, model.OWN_EDITS), run as the full ODE
at the same tolerance as the reference. It is compared with the reference at the same potential
set and reported as:
- the largest change in every readout over the horizon, relative to the reference's scale (its
  largest magnitude), and readouts the plant lacks;
- every identity of §4.8 on the plant's own trajectory (residual over its t_end scale);
- the closed-form items: A1's phase-1 gaps against ε_A1 (§5.1), A1-M's J̄, E and F against ε_M
  (§5.2), each against the unplanted closed forms;
- each item the sheet names for the plant, with its margin (measure over tolerance).
The sheet declares no tolerance for judging an engine's trajectory (G6 sets it). A trajectory
item's margin is reported against the references' own resolution, 10⁻⁹ of the scale, and, for
scale, against ε_A1; it counts as failing only at a margin above RESOLVED = 10.
"""

from __future__ import annotations

import numpy as np

from . import sheet

SKIP = ("t", "u")
# A trajectory change counts as a plant's failure only beyond ten times the references' own
# resolution, 10⁻⁹ of the scale (the judge and its 100× tighter check differ by less).
RESOLVED = 10


def _sheet_plants() -> list[dict]:
    pol = [f"pol T={T}" for T in sheet.SWEEP_T] + ["two-gene"]
    rib = [f"rib n_R={n}" for n in sheet.SWEEP_NR]
    a1 = ["A1"]
    return [
        {"id": "A1-1", "edits": ["m_tx_6"], "worlds": a1, "source": "§5.4 plant 1",
         "named": [("trajectory", "E_tx"), ("trajectory", "C_tx_1"), ("trajectory", "n_R")]},
        {"id": "A1-2", "edits": ["v_tx_40"], "worlds": a1, "source": "§5.4 plant 2",
         "named": [("trajectory", "E_tx"), ("trajectory", "n_R")]},
        {"id": "A1-3", "edits": ["S_tl_fuel_zero"], "worlds": a1, "source": "§5.4 plant 3",
         "named": [("trajectory", "n_ATP"), ("trajectory", "n_ADP"), ("trajectory", "n_Pi"),
                   ("identity", "energy")]},
        {"id": "A1-4", "edits": ["Q_tx_no_return"], "worlds": a1, "source": "§5.4 plant 4",
         "named": [("identity", "machines_pol")]},
        {"id": "A1-5", "edits": ["u_squared"], "worlds": a1, "source": "§5.4 plant 5",
         "named": [("trajectory", "n_R"), ("trajectory", "n_P")]},
        {"id": "A1-6", "edits": ["S_tl_A_49"], "worlds": a1, "source": "§5.4 plant 6",
         "named": [("identity", "moiety_amino acid"), ("identity", "residues_tl"),
                   ("trajectory", "n_A")]},
        {"id": "A1M-1", "edits": ["init_total_machines"], "worlds": ["pol T=5"],
         "source": "§5.2 plant 1, registered at T = 5", "named": [("machine", "J_bar_tx")]},
        {"id": "A1M-2", "edits": ["Q_tx_no_return"], "worlds": pol,
         "source": "§5.2 plant 2 (polymerase-limited and two-gene worlds)",
         "named": [("identity", "machines_pol"), ("machine", "J_bar")]},
        {"id": "A1M-2", "edits": ["Q_tl_no_return"], "worlds": rib,
         "source": "§5.2 plant 2 (ribosome-limited worlds)",
         "named": [("identity", "machines_rib"), ("machine", "J_bar")]},
    ]


def _own_plants() -> list[dict]:
    """The references' own plants, for power on how the four potentials enter. Each names the
    items the references expect it to fail; an item a world does not have is skipped there."""
    return [
        {"id": "own-1", "edits": ["rc_sign_flip"], "worlds": ["A1", "pol T=10"],
         "source": "own: E_rc's sign in recharging's law and heat",
         "named": [("identity", "energy"), ("trajectory", "int_J_C")]},
        {"id": "own-2", "edits": ["rc_share_1"], "worlds": ["A1", "pol T=10"],
         "source": "own: recharging's share 1 in place of 2",
         "named": [("trajectory", "int_J_C"), ("trajectory", "n_M")]},
        {"id": "own-3", "edits": ["deg_no_back"], "worlds": ["A1", "pol T=10", "rib n_R=1"],
         "source": "own: degradation's per-residue back term dropped",
         "named": [("trajectory", "int_D_R"), ("trajectory", "int_D_P")]},
        {"id": "own-4", "edits": ["rel_heat_dropped"], "worlds": ["A1", "pol T=10"],
         "source": "own: the release's heat not booked in H_tx", "named": [("identity", "energy")]},
        {"id": "own-5", "edits": ["per_chain_factor"], "worlds": ["A1", "pol T=10", "rib n_R=1"],
         "source": "own: a per-chain elongation factor (1 − e^(r x)), expected invisible",
         "named": [("trajectory", "E_tx"), ("trajectory", "E_tl")]},
    ]


PLANTS = _sheet_plants() + _own_plants()
# Extra, unregistered: §5.2 plant 1 where the sheet says it is not registered (F goes negative).
EXTRA = [{"id": "A1M-1x", "edits": ["init_total_machines"], "worlds": ["pol T=10", "pol T=100"],
          "source": "§5.2 plant 1 at T ≥ 10, not registered: reported for F's sign", "named": []}]


def changes(ref: dict, plant: dict) -> tuple[dict, list]:
    """Largest |plant − reference| over the horizon, relative to the reference's scale."""
    out, missing = {}, []
    for k, a in ref.items():
        if k in SKIP or k.startswith("rate_"):
            continue
        if k not in plant:
            missing.append(k)
            continue
        a, b = np.asarray(a, float), np.asarray(plant[k], float)
        scale = float(np.max(np.abs(a)))
        d = float(np.max(np.abs(a - b)))
        out[k] = d / scale if scale > 0 else (0.0 if d == 0 else float("inf"))
    return out, missing


def identity_levels(ids: dict) -> dict:
    return {k: float(np.max(np.abs(r)) / abs(s)) if s else float(np.max(np.abs(r)))
            for k, (r, s) in ids.items()}


def a1_gaps(ro: dict, limit: dict) -> dict:
    """§5.1's gaps of an A1 trajectory to the (unplanted) closed forms on [0, t_off)."""
    n = len(limit["series"]["n_R"])
    out = {}
    for key in ("n_R", "n_P", "E_tx", "E_tl"):
        cf = np.array([float(x) for x in limit["series"][key]])
        st = float(limit["steady"][key])
        out[key] = float(np.max(np.abs(cf - np.asarray(ro[key][:n]))) / st)
    return out


def machine_gaps(ro: dict, closed: dict, routes: list[str], pool: str) -> dict:
    """§5.2's gaps of J̄, E and F at t_end to the (unplanted) closed forms, relative."""
    out = {}
    for r in routes:
        J = float(closed[f"J_{r}"])
        E = float(closed[f"E_{r}"])
        out[f"J_bar_{r}"] = abs(float(ro[f"J_bar_{r}"][0]) - J) / J
        out[f"E_{r}"] = abs(float(ro[f"E_{r}"][-1]) - E) / E
    F = float(closed["F"])
    out[f"F_{pool}"] = abs(float(ro[f"F_{pool}"][-1]) - F) / F
    return out


def verdicts(plant: dict, ch: dict, ids: dict, gaps: dict, world: str) -> list[dict]:
    """Each named item of the plant: its measure, tolerance and margin (measure/tolerance)."""
    out = []
    for kind, name in plant["named"]:
        if kind == "trajectory":
            m = ch.get(name)
            if m is None:  # the world has no such readout
                continue
            out.append({"item": f"trajectory {name}", "measure": m,
                        "tolerance": sheet.TOL_TRAJECTORY,
                        "margin": None if m is None else m / sheet.TOL_TRAJECTORY,
                        "margin_vs_eps_A1": None if m is None else m / sheet.EPS_A1,
                        "fails": m is not None and m > RESOLVED * sheet.TOL_TRAJECTORY})
        elif kind == "identity":
            m = ids.get(name)
            if m is None:
                continue
            out.append({"item": f"identity {name}", "measure": m, "tolerance": sheet.TOL_IDENTITY,
                        "margin": None if m is None else m / sheet.TOL_IDENTITY,
                        "fails": m is not None and m > sheet.TOL_IDENTITY})
        elif kind == "machine":
            keys = [k for k in gaps if k.startswith(name)]
            for k in keys:
                m = gaps[k]
                out.append({"item": f"closed form {k}", "measure": m, "tolerance": sheet.EPS_M,
                            "margin": m / sheet.EPS_M, "fails": m > sheet.EPS_M})
    return out
