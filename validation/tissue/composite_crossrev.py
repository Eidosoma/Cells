"""Cross-revision guard of a thin composition (D143): compiled programs and bindings.

When a frozen model's module becomes a thin composition, its earlier implementation
exists only in an earlier revision. This tool runs in each revision (the earlier one
from its execution snapshot, validation/source_snapshot.py) and saves, for a set of
frozen-format definitions:

* jaxprs: the text of the traced checked step, right-hand side and device row
  checks (tracing only, no XLA compile), and beside each text the dtype, shape and
  SHA-256 of every constant the traced program closes over, at any depth
  (NAME.KIND.consts.json). jaxpr text does not print a closed-over array's values: two
  programs that differ only in such a constant print identically, so the constants are
  compared separately. The device row checks close over the model's check constants.
  Identical text and constants mean identical compiled programs for every world of
  those shapes and static choices; the step size is a traced input, so it covers every dt;
* bindings: every initial state, layout and control array (at every schedule time), and
  the model's device-check constants (check.FIELD).

compare checks the two saved sets: jaxpr text equality, constant digests (dtype, shape
and bytes, in tracing order) and binding arrays (dtype, shape and bytes). Identical
programs on identical inputs run identically on a CPU. Outputs written before constants
were recorded (13 November 2026) have no .consts.json files: compare says so, and its
verdict then covers the texts and bindings only.

Three world sets: base (small worlds of every structure: routes, sheets, RK4, events,
donors, padding), qualification (the guarded qualification worlds themselves:
W1's trajectories, W2's arms and G2-Q1's cases) and injection (electrode injection
without a field-input provider, the Rm1 egg included). For the qualification set, bindings
are also saved at every step size of the dt studies the guards did not repeat (W1's
and Q5's), since dt enters the bound inputs (step counts, event steps) as well as
the traced program.

Usage (PYTHONPATH at the revision under test; SET is base, the default, qualification or
injection):
  python -m validation.tissue.composite_crossrev jaxprs DIR [SET]
  python -m validation.tissue.composite_crossrev bindings DIR [SET]
  python -m validation.tissue.composite_crossrev compare A B
"""

import hashlib
import json
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


def injection_worlds():
    """electrode_current_injection@1 without a field-input provider, as its runs use it: the
    heredity cell with both polarities, and the Rm1 egg at its judged step (1 ms)."""
    from cells.core import pump_composite_spec as cs
    from validation.tissue import injection_rm1 as rm1
    from validation.tissue import pump_water_fixtures as wfx

    base = wfx.heredity_cell("H", dt=1e-3, end_time=0.004)
    base["experiment"]["observation_times"] = [0.0, 0.004]
    raw = cs.frozen_definition(base)
    cell = raw["model"]["cells"][0]["id"]
    carriers = {"K": 0.4912, "M": 0.5088}
    raw["model"]["operators"] = [
        dict(
            law="electrode_current_injection@1", electrodes=[dict(cell_id=cell, carriers=carriers)]
        )
    ]
    schedule = [dict(time=0.0, current_A=1e-12), dict(time=0.002, current_A=-1e-12)]
    raw["experiment"]["injection_controls"] = [dict(cell_id=cell, schedule=schedule)]
    return dict(injection_cell=raw, injection_rm1=rm1.definition(1e-3))


def _worlds(world_set, all_steps):
    if world_set == "base":
        return worlds()
    if world_set == "qualification":
        return qualification_worlds(all_steps)
    if world_set == "injection":
        return injection_worlds()
    raise SystemExit(f"Unknown world set {world_set!r} (base, qualification or injection)")


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
        for kind, closed in _traced(*_setup(raw)).items():
            (directory / f"{name}.{kind}.txt").write_text(str(closed))
            (directory / f"{name}.{kind}.consts.json").write_text(const_record(closed))
        print(name, flush=True)


def _traced(spec, model, arrays):
    """Closed jaxprs of the checked step, right-hand side and device row checks."""
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
        checked_step=jax.make_jaxpr(step)(s, dt, c, p),
        rhs=jax.make_jaxpr(rhs)(s, c, p),
        device_checks=jax.make_jaxpr(checks)(s, p),
    )


def closed_consts(closed):
    """Every constant a closed jaxpr holds, at any depth, in tracing order, each once.

    The parameters that hold jaxprs (jit, scan, cond branches) are visited. JAX 0.11's
    make_jaxpr returns a closed jaxpr that may be its own .jaxpr, so an object's equations
    are walked even after its constants are taken.
    """
    found, seen, taken = [], set(), set()

    def visit(value):
        if isinstance(value, (tuple, list)):
            for item in value:
                visit(item)
            return
        if not (hasattr(value, "eqns") or hasattr(value, "jaxpr")) or id(value) in seen:
            return
        seen.add(id(value))
        for const in getattr(value, "consts", None) or ():
            if id(const) not in taken:
                taken.add(id(const))
                found.append(const)
        inner = getattr(value, "jaxpr", None)
        if inner is not None and inner is not value:
            visit(inner)
        for eqn in getattr(value, "eqns", None) or ():
            for param in eqn.params.values():
                visit(param)

    visit(closed)
    return found


def const_record(closed):
    """Canonical JSON of the dtype, shape and SHA-256 of each closed-over constant."""
    rows = []
    for const in closed_consts(closed):
        array = np.ascontiguousarray(np.asarray(const))
        digest = hashlib.sha256(array.tobytes()).hexdigest()
        rows.append(dict(dtype=str(array.dtype), shape=list(array.shape), sha256=digest))
    return json.dumps(dict(count=len(rows), consts=rows), indent=1, sort_keys=True) + "\n"


def check_constants(model, spec):
    """(name, array) of the model's device-check constants; none for a model without them."""
    import jax

    if not hasattr(model, "device_check_constants"):
        return []
    leaves, _ = jax.tree_util.tree_flatten_with_path(model.device_check_constants(spec))
    return [(jax.tree_util.keystr(path).lstrip("."), np.asarray(leaf)) for path, leaf in leaves]


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
        model = get_model(spec.model)
        state, layout = model.initial_values(spec)
        times = sorted({0.0, *(c.time for c in spec.experiment.changes), spec.experiment.end_time})
        arrays = {}
        for prefix, tree in (
            ("state.", state),
            ("layout.", layout),
            ("control.", control_values(spec, times)),
        ):
            for key, value in tree._asdict().items():
                arrays[prefix + key] = np.asarray(value)
        for key, value in check_constants(model, spec):
            arrays["check." + key] = value
        np.savez(directory / f"{name}.npz", **arrays)
        print(name, len(arrays), flush=True)


def compare(a, b):
    """Print each saved item's verdict; True when every item is identical.

    Every jaxpr text of A is compared with B's, and so are its constants. If neither side
    recorded a text's constants (outputs from before they were recorded), that is
    reported and the verdict covers the texts and bindings only. If only one side recorded
    them, they differ.
    """
    a, b = Path(a), Path(b)
    same, unrecorded = True, 0
    counts = {"jaxpr texts": [0, 0], "constants": [0, 0], "bindings": [0, 0]}
    for path in sorted(a.glob("*.txt")):
        other = b / path.name
        equal = other.exists() and path.read_text() == other.read_text()
        same &= equal
        counts["jaxpr texts"][0] += equal
        counts["jaxpr texts"][1] += 1
        print(path.name, "identical" if equal else "DIFFERS")
        mine = a / (path.name[: -len(".txt")] + ".consts.json")
        theirs = b / mine.name
        if not mine.exists() and not theirs.exists():
            unrecorded += 1
            continue
        both = mine.exists() and theirs.exists()
        equal = both and json.loads(mine.read_text()) == json.loads(theirs.read_text())
        same &= equal
        counts["constants"][0] += equal
        counts["constants"][1] += 1
        print(mine.name, "identical" if equal else "DIFFERS" + ("" if both else " (one side)"))
    for path in sorted(a.glob("*.npz")):
        counts["bindings"][1] += 1
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
        counts["bindings"][0] += not diffs
        print(path.name, "identical" if not diffs else f"DIFFERS {diffs[:8]}", len(names))
    if unrecorded:
        print("constants not recorded on either side for", unrecorded, "texts")
    print("summary", ", ".join(f"{k} {n} of {m} identical" for k, (n, m) in counts.items()))
    note = " (texts and bindings; constants not recorded)" if unrecorded and same else ""
    print("verdict", ("identical" if same else "differs") + note)
    return same


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "jaxprs":
        jaxprs(*sys.argv[2:4])
    elif action == "bindings":
        bindings(*sys.argv[2:4])
    else:
        sys.exit(0 if compare(sys.argv[2], sys.argv[3]) else 1)
