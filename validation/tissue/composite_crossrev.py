"""Cross-revision guard of a thin composition (D143): compiled programs and bindings.

When a frozen model's module becomes a thin composition, its earlier implementation
exists only in an earlier revision. This tool runs in each revision (the earlier one
from its execution snapshot, validation/source_snapshot.py) and saves, for a set of
frozen-format definitions:

* jaxprs: the text of the traced checked step, right-hand side and device row
  checks (tracing only, no XLA compile). Identical text means identical compiled
  programs for every world of those shapes and static choices; the step size is a
  traced input, so it covers every dt;
* bindings: every initial state, layout and control array (at every schedule time).

compare checks the two saved sets: jaxpr text equality, and array dtype, shape and
bytes. Identical programs on identical inputs run identically on a CPU.

Two world sets: base (small worlds of every structure: routes, sheets, RK4, events,
donors, padding) and qualification (the guarded qualification worlds themselves:
W1's trajectories, W2's arms and G2-Q1's cases). For the qualification set, bindings
are also saved at every step size of the dt studies the guards did not repeat (W1's
and Q5's), since dt enters the bound inputs (step counts, event steps) as well as
the traced program.

Usage (PYTHONPATH at the revision under test; SET is base, the default, or qualification):
  python -m validation.tissue.composite_crossrev jaxprs DIR [SET]
  python -m validation.tissue.composite_crossrev bindings DIR [SET]
  python -m validation.tissue.composite_crossrev compare A B
"""

import sys
from pathlib import Path

import numpy as np


def worlds():
    """Frozen-format definitions: water@1, water@2 (routes, none, sheets, RK4) and replacement@1."""
    from cells.core.cell_replacement_spec import exact_event_times
    from validation.tissue import cell_replacement_fixtures as rfx
    from validation.tissue import pump_water_fixtures as wfx
    from validation.tissue import surface_pump_v3_fixtures as v3fx

    out = {}
    raw = wfx.heredity_cell("D", end_time=0.1)
    raw["experiment"]["observation_times"] = [0.0, 0.1]
    out["water"] = wfx.with_water(raw, pf_m_s=5e-4, bath_pressure_Pa=12.5)
    sheet = wfx.with_water(wfx.gated_sheet(end_time=0.01), pf_m_s=5e-4)
    sheet["model"]["junction_heat_booking"] = "trapezoid_nonnegative@1"
    out["water_sheet"] = sheet
    out["symport"] = wfx.with_symport(out["water"], flux_mmol_L_h=15.0, steepness=0.12)
    out["symport_none"] = wfx.with_symport(out["water"], membranes=[])
    out["symport_sheet"] = wfx.with_symport(sheet, flux_mmol_L_h=4.0)
    rk4 = wfx.with_water(
        wfx.heredity_cell("D", dt=2.5e-6, end_time=1e-4, solver="rk4"), pf_m_s=5e-4
    )
    rk4["experiment"]["observation_times"] = [0.0, 1e-4]
    out["water_rk4"] = rk4
    out["symport_rk4"] = wfx.with_symport(rk4, flux_mmol_L_h=15.0, steepness=0.12)
    dt = 1e-3
    t1, t2, t3 = exact_event_times((10, 20, 30), dt)
    cells = rfx.heredity_sheet(1, 0, dt=dt, end_time=0.05)
    cells["experiment"]["observation_times"] = [0.0, 0.05]
    templates = [
        rfx.template_from_cell(cells, "cell_1", "h"),
        rfx.template_from_cell(cells, "cell_3", "d"),
    ]
    events = ((t1, "cell_0", "h", "n1"), (t2, "cell_2", "h", "n2"), (t3, "cell_0", "d", "n4"))
    out["replacement"] = rfx.with_replacement(cells, templates, events)
    fast = dict(rfx.NO_ROUTES, channel_permeability_m_per_s={"nav1p2_m3h_regularized@1": 3e-7})
    donor_events = (
        (t1, "cell_0", None, "c1", "cell_3"),
        (t2, "cell_4", "fast_nav", "c2", "cell_3"),
    )
    out["replacement_donors"] = rfx.with_replacement(
        cells, [*templates, rfx.route_template("fast_nav", fast)], donor_events
    )
    steady = dict(rfx.FORMATION, initial_abundance=1.0, lag_s=0.0, gate_at_arrival="law_steady")
    out["replacement_steady"] = rfx.with_replacement(cells, templates, events, formation=steady)
    drawn = rfx.template_from_cell(cells, "cell_1", "drawn")
    drawn["route_values"].update(
        channel_permeability_m_per_s={"nav1p2_m3h_regularized@1": 3.0e-7},
        membrane_permeability_m_per_s={"Na": 8e-11},
        pump_capacity_fmol_per_s_m2=1.2e8,
    )
    out["replacement_routes"] = rfx.with_replacement(
        cells, [drawn], [(t1, "cell_0", "drawn", "n1")]
    )
    padded = v3fx.definition("release", solver="imex_ars222_face_electromigration@1")
    padded["experiment"]["end_time"] = 0.0012
    padded["experiment"]["observation_times"] = [0.0, 0.0012]
    p1, p2 = exact_event_times((4, 9), padded["execution"]["dt"])
    own = [
        rfx.template_from_cell(padded, "cell_0", "own_0"),
        rfx.template_from_cell(padded, "cell_1", "own_1"),
    ]
    out["replacement_padded"] = rfx.with_replacement(
        padded, own, ((p1, "cell_0", "own_0", "n1"), (p2, "cell_0", "own_0", "n2"))
    )
    return out


def qualification_worlds(all_steps=False):
    """The guarded qualification worlds, as their guards run them.

    W1's judged trajectories, W2's arms, G2-Q1's cases, W37, and the 825-node world with
    closed water and with event-free replacement, each at its guarded step size (W1,
    G2-Q1, W37 and the 825-node world at 1 ms, W2 at its definition's). With all_steps,
    also W1's trajectories at every step size of W1's dt study and Q5's cases at every
    step size of Q5.
    """
    import json

    from validation.tissue import cell_replacement_fixtures as rfx
    from validation.tissue import cell_replacement_judge as judge
    from validation.tissue import cell_replacement_qualification as g2q
    from validation.tissue import pump_water_fixtures as wfx
    from validation.tissue import pump_water_kcc_qualification as w2q
    from validation.tissue import pump_water_qualification as w1q
    from validation.tissue import surface_pump_v3_study as study

    root = Path(w1q.__file__).parent  # The predictions of the revision under test.
    w1, w2, g2 = (
        json.loads((root / name).read_text())
        for name in (
            "pump_water_predictions.json",
            "pump_water_kcc_predictions.json",
            "cell_replacement_q1_predictions.json",
        )
    )
    out = {}
    for name, path in w1q.TRAJECTORIES.items():
        raw = w1q.item(w1, path)["definition"]
        for dt in w1q.STEPS_S if all_steps else (1e-3,):
            out[f"W1_{name}@{dt:g}"] = w1q.with_step(raw, dt)
    for arm in w2["arms"]:
        out["W2_" + arm] = w2q.definition(w2, arm)
    for case, entry in g2["cases"].items():
        for dt in judge.Q5_DTS if all_steps and case in judge.Q5_CASES else (1e-3,):
            out[f"G2_{case.replace('/', '_')}@{dt:g}"] = g2q.at_dt(entry["definition"], dt)
    out["W37"] = _w37()
    tissue = study.tissue_definition(dt=1e-3, end_time=0.2, observation_times=[0.0, 0.1, 0.2])
    out["S825_closed_water"] = wfx.with_water(tissue, availability=0.0)
    out["S825_event_free"] = rfx.with_replacement(tissue)
    return out


def _w37():
    """The W37 world of composite_guard.part_w37: rim and inner replacements."""
    from cells.core.cell_replacement_spec import exact_event_times
    from validation.stationary import worlds as hexagons
    from validation.tissue import cell_replacement_fixtures as rfx
    from validation.tissue import cell_replacement_judge as judge
    from validation.tissue import cell_replacement_qualification as g2q

    registered = judge.REGISTERED
    raw = rfx.heredity_sheet(6, 3, scale=0.3, dt=1e-3, end_time=3.0)
    raw["experiment"]["observation_times"] = [0.0, 3.0]
    raw["model"]["junction_heat_booking"] = g2q.BOOKING
    cells, _ = hexagons.hexagon(6)
    rings = [hexagons.ring(c) for c in cells]
    rims = [i for i, r in enumerate(rings) if r == 3]
    inners = [i for i, r in enumerate(rings) if r == 1]
    slots = [*(rims[k] for k in registered["w37_rim"]), inners[registered["w37_inner"]]]
    h = next(i for i, r in enumerate(rings) if r == 6)
    (t,) = exact_event_times((registered["w37_step"],), 1e-3)
    template = rfx.template_from_cell(raw, f"cell_{h}", "h")
    events = [(t, f"cell_{i}", "h", f"n{i}") for i in slots]
    return rfx.with_replacement(raw, [template], events)


def _worlds(world_set, all_steps):
    if world_set == "base":
        return worlds()
    if world_set == "qualification":
        return qualification_worlds(all_steps)
    raise SystemExit(f"Unknown world set {world_set!r} (base or qualification)")


def _setup(raw):
    import jax
    import jax.numpy as jnp

    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.models.registry import get_model

    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(np.asarray(v[0]) for v in controls))
    return spec, model, jax.tree.map(jnp.asarray, (state, control, p))


def jaxprs(directory, world_set="base"):
    import jax

    jax.config.update("jax_enable_x64", True)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in _worlds(world_set, all_steps=False).items():
        for kind, text in _traced(*_setup(raw)).items():
            (directory / f"{name}.{kind}.txt").write_text(text)
        print(name, flush=True)


def _traced(spec, model, arrays):
    """jaxpr text of the checked step, right-hand side and device row checks."""
    import jax
    import jax.numpy as jnp

    s, c, p = arrays
    dt = jnp.asarray(spec.execution.dt)  # Traced, as in the runner's rollout.
    constants = model.device_check_constants(spec)

    def step(s, dt, c, q):
        return model.checked_step(s, dt, c, q, q.active)

    def rhs(s, c, q):
        return model.rhs(s, c, q, q.active)

    def checks(s, q):
        return model.device_checks(s, s, q, constants, 3)

    return dict(
        checked_step=str(jax.make_jaxpr(step)(s, dt, c, p)),
        rhs=str(jax.make_jaxpr(rhs)(s, c, p)),
        device_checks=str(jax.make_jaxpr(checks)(s, p)),
    )


def bindings(directory, world_set="base"):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.models.registry import get_model

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in _worlds(world_set, all_steps=True).items():
        spec = parse_spec(raw)
        state, layout = get_model(spec.model).initial_values(spec)
        times = sorted({0.0, *(c.time for c in spec.experiment.changes), spec.experiment.end_time})
        arrays = {}
        for prefix, tree in (
            ("state.", state),
            ("layout.", layout),
            ("control.", control_values(spec, times)),
        ):
            for key, value in tree._asdict().items():
                arrays[prefix + key] = np.asarray(value)
        np.savez(directory / f"{name}.npz", **arrays)
        print(name, len(arrays), flush=True)


def compare(a, b):
    """Print each saved item's verdict; True when every item is identical."""
    a, b = Path(a), Path(b)
    same = True
    for path in sorted(a.glob("*.txt")):
        other = b / path.name
        equal = other.exists() and path.read_text() == other.read_text()
        same &= equal
        print(path.name, "identical" if equal else "DIFFERS")
    for path in sorted(a.glob("*.npz")):
        if not (b / path.name).exists():
            same = False
            print(path.name, "DIFFERS (missing in", b, ")")
            continue
        x, y = np.load(path), np.load(b / path.name)
        names = set(x.files) | set(y.files)
        diffs = [
            k
            for k in sorted(names)
            if k not in x.files
            or k not in y.files
            or x[k].dtype != y[k].dtype
            or x[k].shape != y[k].shape
            or x[k].tobytes() != y[k].tobytes()
        ]
        same &= not diffs
        print(path.name, "identical" if not diffs else f"DIFFERS {diffs[:8]}", len(names))
    print("verdict", "identical" if same else "differs")
    return same


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "jaxprs":
        jaxprs(*sys.argv[2:4])
    elif action == "bindings":
        bindings(*sys.argv[2:4])
    else:
        sys.exit(0 if compare(sys.argv[2], sys.argv[3]) else 1)
