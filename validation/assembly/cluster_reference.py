"""Event-union oracle using the independent spatial equations and adaptive SciPy solvers.

The caller supplies independently reconstructed scalar pool histories. This
module imports no Cells/JAX production law, layout, integrator or observer.
"""

import copy
import importlib.util
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

_path = Path(__file__).resolve().parents[1] / "betse/spatial_cluster/reference.py"
_spec = importlib.util.spec_from_file_location("cluster_independent_spatial_reference", _path)
spatial = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(spatial)


def integrate(raw, events, *, method="DOP853", horizon=None):
    ionic = raw["ionic"]
    context = spatial.bind(ionic)
    horizon = ionic["experiment"]["end_time"] if horizon is None else horizon
    cell_ids = [c["cell"]["id"] for c in ionic["model"]["cells"]]
    bindings = {b["cell_id"]: b for b in raw["pools"]}
    controls = spatial.control_at(ionic, 0.0)
    masks, bonds = [], []
    # Explicit initial bond lists are required here; normalization is a caller
    # responsibility, independent of the event/ODE calculation below.
    for name in cell_ids:
        definition = bindings[name]["pool"]
        masks.append(sum(1 << n for n in definition["initial_nodes"]))
        bonds.append(sum(1 << n for n in definition["initial_bond_indices"]))
    boundaries = sorted(
        {
            0.0,
            horizon,
            *(e[0] for name in cell_ids for e in events[name] if e[0] <= horizon),
        }
    )
    cursors = [0] * len(cell_ids)
    exposure = np.zeros(len(cell_ids))
    value, calls = spatial.initial(context), 0
    for start, end in zip(boundaries[:-1], boundaries[1:], strict=True):
        held = copy.deepcopy(controls)
        for i, name in enumerate(cell_ids):
            while cursors[i] < len(events[name]) and events[name][cursors[i]][0] <= start:
                event = events[name][cursors[i]]
                masks[i], bonds[i] = event[1:3]
                cursors[i] += 1
            coupling = bindings[name]["coupling"]
            opening = coupling[
                "active_availability"
                if bonds[i].bit_count() >= masks[i].bit_count()
                else "inactive_availability"
            ]
            channel = ionic["model"]["cells"][i]["channel"]["id"]
            held[channel, "schedule"]["availability"] *= opening
            exposure[i] += opening * (end - start)

        def rhs(_, current, control=held):
            nonlocal calls
            calls += 1
            if calls > 200000:
                raise ValueError("Independent cluster reference RHS budget exceeded")
            return spatial.rhs(context, control, current)

        solution = solve_ivp(
            rhs,
            (start, end),
            value,
            method=method,
            rtol=1e-11,
            atol=1e-14,
            max_step=0.0005,
        )
        if not solution.success or not np.isfinite(solution.y).all():
            raise ValueError("Independent cluster solve failed: " + solution.message)
        value = solution.y[:, -1]
    return {
        "state": value,
        "exposure_s": exposure,
        "rhs_calls": calls,
        "voltage_V": spatial.voltage(context, spatial.unpack(context, value)["amount_increment"]),
        "segments": len(boundaries) - 1,
    }
