"""Q4's circuit and symmetric limits, measured (development; S5 design §7.3, §8.3 Q4).

tests/unit/test_division_limits_runs.py asserts each limit to its stated tolerance. This driver
runs the same worlds through the test file's own helpers and records each measured quantity
beside its prediction, unasserted, so the protocol can disclose the margins:
* the closed bridge's T-network: coupling V2/V1, the cleft over d1, the input resistance, and
  the closed bridge's response against the bridge-free world's;
* the sealed cleft: the coupling, and R_j = (dV1 - dV2) / I_furrow (the current into d2 through
  its furrow; the readout's membrane flux is positive from the cell to its outside node)
  against 1/G_f1 + 1/G_f2;
* the symmetric daughters: each field's largest |d1 - d2| and its scale, and the potentials'.

Usage: python -m validation.division.q4_limits_measure OUTPUT_JSON (seven compiled runs, a few
minutes; through scripts/run_detached.sh).
"""

import importlib.util
import json
import math
import sys
from pathlib import Path

import jax
import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests import partition_fixtures as fx

ROOT = Path(__file__).resolve().parents[2]


def limits():
    """The test file's module (its helpers and constants)."""
    path = ROOT / "tests/unit/test_division_limits_runs.py"
    spec = importlib.util.spec_from_file_location("division_limits", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def t_network(t):
    closed, base, _ = t.response(bridge=True)
    alone, _, _ = t.response(bridge=False)
    spec, model, p, state, _ = base
    g = t.network(spec, model, p, state, sealed=False)
    v1, v2, vc = t.predicted(g)
    return dict(
        conductances_S=g,
        measured=dict(
            coupling=closed["d2"] / closed["d1"],
            cleft_over_d1=closed["cleft"] / closed["d1"],
            input_ohm=closed["d1"] / t.CURRENT_A,
        ),
        predicted=dict(coupling=v2 / v1, cleft_over_d1=vc / v1, input_ohm=v1),
        closed_vs_no_bridge_relative={
            k: abs(closed[k] - alone[k]) / abs(alone[k]) for k in ("d1", "d2", "cleft")
        },
        aperture_end=float(np.max(np.asarray(state.bridge_aperture_m))),
    )


def sealed(t):
    delta, base, hot = t.response(bridge=False, sealed=True)
    spec, model, p, state, _ = base
    g = t.network(spec, model, p, state, sealed=True)
    v1, v2, _ = t.predicted(g)
    k = [m.id for m in spec.model.membranes].index("furrow_d2")
    currents = []
    for _, m, layout, x, control in (base, hot):
        flux = np.asarray(m.readouts(x, control, layout, xp=np).field.rates.membrane_flux_fmol_s)
        currents.append(-CHARGE_PER_FMOL * float(np.sum(np.ravel(layout.valence) * flux[:, k])))
    rj = (delta["d1"] - delta["d2"]) / (currents[1] - currents[0])
    return dict(
        conductances_S=g,
        measured=dict(coupling=delta["d2"] / delta["d1"], rj_ohm=rj),
        predicted=dict(coupling=v2 / v1, rj_ohm=1 / g["Gf1"] + 1 / g["Gf2"]),
    )


def symmetric(t):
    raw = fx.divided(end=0.05)
    raw["experiment"]["observation_times"] = [0.0, 0.05]
    raw["execution"].update(dt=t.DT, max_steps=int(math.ceil(0.05 / t.DT)) + 8)
    spec = parse_spec(raw)
    model = get_model(spec.model)
    result = run(spec)
    after = np.asarray(result.times) > fx.EVENT
    cells = [c.id for c in spec.model.cells]
    membranes = [m.id for m in spec.model.membranes]
    channels = [c.id for c in spec.model.channels]
    fields = {}
    for name, axes in model.STATE_AXES.items():
        values = np.asarray(getattr(result.history, name))[after]
        axis = axes[-1]
        if axis == "cell_slot":
            pairs = [(cells.index("d1"), cells.index("d2"))]
        elif axis == "membrane_slot":
            pairs = [(membranes.index("membrane_0_d1"), membranes.index("membrane_0_d2"))]
        elif axis == "channel_slot":
            pairs = [
                (channels.index(f"{c}_d1"), channels.index(f"{c}_d2"))
                for c in channels
                if f"{c}_d1" in channels
            ]
        else:
            continue
        scale = float(np.max(np.abs(values))) if values.size else 0.0
        difference = max(float(np.max(np.abs(values[..., i] - values[..., j]))) for i, j in pairs)
        fields[name] = dict(difference=difference, scale=scale)
    _, p = model.initial_values(spec)
    largest = 0.0
    for row in np.flatnonzero(after):
        state = model.STATE_TYPE(*(np.asarray(v[row]) for v in result.history))
        phi = adapter.node_potentials(state, model.view(p, state, xp=np), xp=np)
        a, b = phi[cells.index("d1")], phi[cells.index("d2")]
        largest = max(largest, abs(a - b) / (t.EPS * abs(a)))
    return dict(fields=fields, potential_difference_in_eps=largest)


def main(output):
    jax.config.update("jax_enable_x64", True)
    t = limits()
    report = dict(t_network=t_network(t), sealed=sealed(t), symmetric=symmetric(t))
    Path(output).write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
