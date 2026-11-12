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

Usage (PYTHONPATH at the revision under test):
  python -m validation.tissue.composite_crossrev jaxprs DIR
  python -m validation.tissue.composite_crossrev bindings DIR
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


def jaxprs(directory):
    import jax

    jax.config.update("jax_enable_x64", True)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in worlds().items():
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


def bindings(directory):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.models.registry import get_model

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in worlds().items():
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
        jaxprs(sys.argv[2])
    elif action == "bindings":
        bindings(sys.argv[2])
    else:
        sys.exit(0 if compare(sys.argv[2], sys.argv[3]) else 1)
