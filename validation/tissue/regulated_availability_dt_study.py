"""The coupling operator's qualification generator: A1, A4, A5 and their controls, as records.

docs/INVENTORY_COUPLING_DESIGN.md §9 (milestone 3) and §10 (milestone 4, the protocol). The engine
(cells.model.resolved_pump_composite@1 over cells.model.resolved_pump_tissue@3 with cells.operator.species_regulated_availability@1, and
D150's turnover for A5's regulator) is run against the independent references of
validation/coupling, used through REFERENCES_USAGE.md's API only. This module writes records; it
computes no order and no verdict. The judge (validation/tissue/regulated_availability_judge.py)
reads the records and the protocol (validation/tissue/regulated_availability_protocol.json).

Parts:
* `a1`: the operator's factors (route_factors and element_product) on the host (NumPy) and on the
  device (jitted), over a grid of x, K, n, b and s, against R-fac's exact path (fr.exact_grid,
  fr.exact_side_factor): each point's absolute error in eps (fr.eps_error) beside its a priori
  bound.
* `a4`, `a5`: the dt studies of A4 (R-feedback) and A5 (R-cell), arms uncoupled and coupled (and
  A4's fast arm). For each dt of the ladder (1, 0.5, 0.25 and 0.125 ms, one window program per
  world), every record's |engine - reference| for V, the amounts, a_eff, s, U and F; the
  reference's floor (rc.floor) and the largest |value| of each observable; whether every contact
  gate stayed at 1; row 0 against the reference's start; the reference's sensitivity of each
  observable to the δ-controls' parameter (the basal level).
* `controls`: the same records for planted defects that must lower the order: the regulatory
  state at first order and the factor one step stale (validation/tissue/
  regulated_availability_controls), on A4's coupled arm, and the basal level times (1 + δ) on A4's
  and A5's coupled arms (δ registered in a judged run; in a development run, δ is set from this
  run's own records so the control's plateau is 10 times the finest error).

Modes:
  python -m validation.tissue.regulated_availability_dt_study dev OUT_DIR [PART ...]
  python -m validation.tissue.regulated_availability_dt_study judged PROTOCOL OUT_DIR [PART ...]
A judged run is refused, before anything is computed or written, unless the protocol is registered
(its status and its registration record), the source is a clean execution snapshot and OUT_DIR is
new (D150's and MG0c's guard). Each run writes OUT_DIR/results.json.
"""

import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.operators import species_regulated_availability as sra
from validation.coupling import cells_reference as rc
from validation.coupling import factor_reference as fr
from validation.tissue import regulated_availability_controls as controls
from validation.tissue import regulated_availability_references as rr

ROOT = Path(__file__).resolve().parents[2]
DTS = (1e-3, 5e-4, 2.5e-4, 1.25e-4)
WINDOW = 1000
OBSERVABLES = ("V", "amounts", "a_eff", "s", "U", "F")
PROBE = 1e-3  # The reference's sensitivity probe for the δ-controls' parameter.
DELTA_PLATEAU = 10.0  # A development δ puts the control's plateau at 10 x the finest error.
PARTS = ("a1", "a4", "a5", "controls")

A4 = dict(end=2.0, every=0.1, relax=0.05, fast=dict(k_on=750.0, k_off=150.0), basal=0.2)
A5 = dict(
    end=1.0,
    every=0.05,
    basal=0.1,
    baseline=dict(enabled=0, population_schedule=((0.0, 1.0), (0.2, 0.3), (0.5, 1.0))),
)


def a4_world():
    return rr.relaxed(rr.feedback_world, A4["relax"])


def grid_records(end, every, dt):
    """Record times on the engine's grid (k * dt), every `every`, from the first after 0."""
    stride = round(every / dt)
    return [k * stride * dt for k in range(1, round(end / every) + 1)]


# ------------------------------------------------------------------ the engine and the comparison


def engine_run(world, *, dt, end, every, initial, control=None):
    """{time: row} from the engine's windowed run (one program per world and control): V,
    amounts, a_eff, s, U and F at every record; and the run's checks."""
    times = [0.0, *grid_records(end, every, dt)]
    raw = rr.engine_definition(world, dt=dt, end=end, times=times, initial=initial)
    if control is not None:
        raw = controls.as_control(raw, control)
    spec = parse_spec(raw)
    m = spec.model
    cells = [c.id for c in m.cells]
    species = list(m.species_ids)
    ions = [species.index(s) for s in rr.SPECIES]
    anchor = np.asarray([[c.initial_amount_fmol[i] for c in m.cells] for i in range(len(species))])
    junctions = [j.id for j in m.junctions]
    channels = [c.id for c in m.channels]
    rows, history, gates = {}, {}, []
    started = time.perf_counter()
    for window in iter_windows(spec, WindowPolicy(WINDOW, "full")):
        h = window.history
        for i, t in enumerate(np.asarray(window.times)):
            history[round(float(t) / dt)] = (
                np.asarray(h.amount_increment)[i],
                np.asarray(h.regulatory_state)[i] if hasattr(h, "regulatory_state") else None,
                np.asarray(h.regulatory_input_integral)[i]
                if hasattr(h, "regulatory_input_integral")
                else None,
            )
        if junctions:
            gates.append(np.asarray(h.junction_gate))
        obs = vars(window.observations)
        for j, t in enumerate(np.asarray(obs["times"])):
            rows[float(t)] = dict(
                V=np.asarray(obs["cell_potential_V"])[j],
                junction=np.asarray(obs["junction_availability"])[j],
                channel=np.asarray(obs["channel_availability"])[j],
                F=np.asarray(obs["coupling_factor"])[j] if "coupling_factor" in obs else None,
            )
    wall = time.perf_counter() - started
    out = {}
    for t, row in rows.items():
        increment, s, u = history[round(t / dt)]
        amounts = anchor + increment
        out[t] = dict(
            V={c: float(row["V"][i]) for i, c in enumerate(cells)},
            amounts={c: tuple(float(amounts[k, i]) for k in ions) for i, c in enumerate(cells)},
            a_eff={
                **{e: float(row["junction"][i]) for i, e in enumerate(junctions)},
                **{q: float(row["channel"][i]) for i, q in enumerate(channels)},
            },
            s=s,
            U=u,
            F=row["F"],
        )
    gate_ok = all(np.all(g == 1.0) for g in gates)
    return out, dict(wall_s=wall, gate_held_at_1=bool(gate_ok), steps=round(end / dt))


def route_products(world, engine_F):
    """The engine's routes multiplied per (coupling, element), sides in order: the reference's F."""
    out, k = {}, 0
    for name, c in world.couplings.items():
        width = 2 if c.side == "both" else 1
        value = 1.0
        for j in range(width):
            value = value * float(engine_F[k + j])
        out[(name, c.target)] = value
        k += width
    return out


def record_errors(world, engine, reference, record, slots):
    """{observable: [|engine - reference| at each record, the largest over its entries]}."""
    out = {x: [] for x in OBSERVABLES}
    for t in record:
        a, b = engine[t], reference.at[t]
        out["V"].append(max(abs(a["V"][c] - b["V"][c]) for c in world.cells))
        out["amounts"].append(
            max(
                abs(x - y)
                for c in world.cells
                for x, y in zip(a["amounts"][c], b["amounts_fmol"][c], strict=True)
            )
        )
        out["a_eff"].append(
            max(abs(a["a_eff"][k] - b["elements"][k]["a_eff"]) for k in b["elements"])
        )
        if slots:
            out["s"].append(max(abs(float(a["s"][i]) - b["s"][x]) for i, x in enumerate(slots)))
            out["U"].append(max(abs(float(a["U"][i]) - b["U"][x]) for i, x in enumerate(slots)))
        else:
            out["s"].append(0.0)
            out["U"].append(0.0)
        if world.couplings and a["F"] is not None:
            products = route_products(world, a["F"])
            out["F"].append(max(abs(products[k] - b["routes"][k]["F"]) for k in products))
        else:
            out["F"].append(0.0)
    return out


def magnitudes(world, reference, record):
    """The largest |value| of each observable over the records (the judge's rounding scale)."""
    out = dict.fromkeys(OBSERVABLES, 0.0)
    for t in record:
        b = reference.at[t]
        out["V"] = max(out["V"], max(abs(v) for v in b["V"].values()))
        out["amounts"] = max(
            out["amounts"], max(abs(x) for c in world.cells for x in b["amounts_fmol"][c])
        )
        out["a_eff"] = max(out["a_eff"], max(abs(v["a_eff"]) for v in b["elements"].values()))
        if b["s"]:
            out["s"] = max(out["s"], max(abs(v) for v in b["s"].values()))
            out["U"] = max(out["U"], max(abs(v) for v in b["U"].values()))
        if b["routes"]:
            out["F"] = max(out["F"], max(abs(v["F"]) for v in b["routes"].values()))
    return out


def scalar_floor(floor):
    return {k: float(v) for k, v in floor.items() if np.isscalar(v)}


def arm_records(world, *, end, every, control=None, initial=None):
    """One arm's records over the ladder: its reference, floor, magnitudes and per-dt errors."""
    record = tuple(grid_records(end, every, DTS[0]))
    reference = rc.simulate(world, end, record=record)
    if initial is None:
        initial = {
            c: (reference.initial[c]["V"], reference.initial[c]["background_fmol"])
            for c in world.cells
        }
    _, _, floor = rc.floor(world, end, record)
    runs = []
    for dt in DTS:
        engine, info = engine_run(
            world, dt=dt, end=end, every=every, initial=initial, control=control
        )
        errors = record_errors(world, engine, reference, record, reference.slots)
        row0 = max(abs(engine[0.0]["V"][c] - initial[c][0]) for c in world.cells)
        runs.append(dict(dt=dt, errors=errors, row0_V_difference=row0, **info))
        largest = {x: f"{max(v):.3e}" for x, v in errors.items()}
        print(control or "engine", dt, largest, f"{info['wall_s']:.1f} s", flush=True)
    return (
        dict(
            record_times=list(record),
            floor=scalar_floor(floor),
            magnitudes=magnitudes(world, reference, record),
            runs=runs,
        ),
        reference,
        initial,
    )


def sensitivity(make, key, value, reference, end, every):
    """The reference's change per unit relative change of `key`, largest over the records."""
    record = tuple(grid_records(end, every, DTS[0]))
    moved = rc.simulate(make(**{key: value * (1 + PROBE)}), end, record=record)
    out = {}
    for x in ("V", "amounts", "a_eff"):
        worst = 0.0
        for t in record:
            a, b = moved.at[t], reference.at[t]
            if x == "V":
                d = max(abs(a["V"][c] - b["V"][c]) for c in a["V"])
            elif x == "amounts":
                d = max(
                    abs(p - q)
                    for c in a["amounts_fmol"]
                    for p, q in zip(a["amounts_fmol"][c], b["amounts_fmol"][c], strict=True)
                )
            else:
                d = max(
                    abs(a["elements"][k]["a_eff"] - b["elements"][k]["a_eff"])
                    for k in a["elements"]
                )
            worst = max(worst, d)
        out[x] = worst / PROBE
    return out


# ------------------------------------------------------------------ the parts


def part_a4(context):
    make = a4_world()
    out = {}
    base, _, _ = arm_records(make(enabled=0), end=A4["end"], every=A4["every"])
    out["baseline"] = base
    coupled, reference, initial = arm_records(make(), end=A4["end"], every=A4["every"])
    out["coupled"] = coupled
    out["fast"], _, _ = arm_records(make(**A4["fast"]), end=A4["end"], every=A4["every"])
    out["sensitivity_to_basal"] = sensitivity(
        make, "basal", A4["basal"], reference, A4["end"], A4["every"]
    )
    context["a4"] = dict(make=make, initial=initial, coupled=coupled, out=out)
    return out


def part_a5(context):
    make = rr.cell_world
    out = {}
    out["baseline"], _, _ = arm_records(make(**A5["baseline"]), end=A5["end"], every=A5["every"])
    coupled, reference, initial = arm_records(make(), end=A5["end"], every=A5["every"])
    out["coupled"] = coupled
    out["sensitivity_to_basal"] = sensitivity(
        make, "basal", A5["basal"], reference, A5["end"], A5["every"]
    )
    context["a5"] = dict(make=make, initial=initial, coupled=coupled, out=out)
    return out


def development_delta(arm, sensitivity_V):
    """δ putting the δ-control's plateau in V at DELTA_PLATEAU times the finest error in V."""
    finest = max(arm["runs"][-1]["errors"]["V"])
    return DELTA_PLATEAU * finest / sensitivity_V


def part_controls(context, registered_deltas=None):
    """The planted defects on the coupled arms (A4 and A5 must have run in this process)."""
    out = {}
    a4, a5 = context.get("a4"), context.get("a5")
    if a4 is None or a5 is None:
        raise SystemExit("Refused: the controls part needs the a4 and a5 parts in the same run")
    for kind in ("first_order_state", "lagged_factor"):
        with controls.registered(kind):
            out[kind], _, _ = arm_records(
                a4["make"](), end=A4["end"], every=A4["every"], control=kind, initial=a4["initial"]
            )
    for name, world, spec_, entry in (
        ("delta_basal_a4", a4, A4, a4["out"]),
        ("delta_basal_a5", a5, A5, a5["out"]),
    ):
        if registered_deltas is not None:
            delta = registered_deltas[name]
        else:
            delta = development_delta(world["coupled"], entry["sensitivity_to_basal"]["V"])
        out[name] = dict(delta=delta, **moved_records(world, spec_, delta))
    return out


def moved_records(world, spec_, delta):
    """A δ-control's records: the engine runs the world with its basal level times (1 + δ); its
    errors are against the reference of the world as declared (the coupled arm's floor and
    magnitudes; the coupled arm's start)."""
    make, initial = world["make"], world["initial"]
    record = tuple(grid_records(spec_["end"], spec_["every"], DTS[0]))
    reference = rc.simulate(make(), spec_["end"], record=record)
    moved = make(basal=spec_["basal"] * (1 + delta))
    runs = []
    for dt in DTS:
        engine, info = engine_run(
            moved, dt=dt, end=spec_["end"], every=spec_["every"], initial=initial
        )
        errors = record_errors(make(), engine, reference, record, reference.slots)
        row0 = max(abs(engine[0.0]["V"][c] - initial[c][0]) for c in initial)
        runs.append(dict(dt=dt, errors=errors, row0_V_difference=row0, **info))
        largest = {x: f"{max(v):.3e}" for x, v in errors.items()}
        print("delta", delta, dt, largest, f"{info['wall_s']:.1f} s", flush=True)
    coupled = world["coupled"]
    return dict(
        record_times=list(record),
        floor=coupled["floor"],
        magnitudes=coupled["magnitudes"],
        runs=runs,
    )


# ------------------------------------------------------------------ A1: the factor values


A1_X = (0.0, 1e-300, 1e-10, 1e-4, 0.0123, 0.37, 1.0, 12.0, 1e3, 1e10)
A1_K = (1e-4, 0.37, 12.0)
A1_N = (0.5, 1.0, 2.0, 4.0, 8.0)
A1_B = (0.0, 0.2)
A1_S = (0.0, 0.25, 0.5, 0.75, 1.0)


def a1_bound(law, x, K, n):
    """The a priori bound in eps of |engine - exact| for one Hill route: the log-space form's z =
    n (ln x - ln K) carries at most 2 n (|ln x| + |ln K| + 1) eps, and |df/dz| = f (1 - f), plus 4
    eps for exp, logaddexp and the basal combination; exact (0) at x = 0."""
    if x == 0.0:
        return 0.0
    f = fr.law_value(law, x=x, K=K, n=n)
    return 4.0 + 2.0 * f * (1.0 - f) * n * (abs(math.log(x)) + abs(math.log(K)) + 1.0)


def a1_layout(points):
    """A route per point, each in its own 1 pL cell: (state, p) namespaces for route_factors."""
    m = len(points)
    law = np.asarray([sra.SPECIES_LAWS.get(q[0], sra.STATE_FACTOR_LAWS.get(q[0])) for q in points])
    x = np.asarray([q[1] for q in points], dtype=float)
    p = SimpleNamespace(
        coupling_route_law=law.astype(np.int64),
        coupling_route_row=np.zeros(m, dtype=np.int64),
        coupling_route_cell=np.arange(m, dtype=np.int64),
        coupling_route_slot=np.arange(m, dtype=np.int64),
        coupling_route_half_saturation_mM=np.asarray([q[2] for q in points], dtype=float),
        coupling_route_coefficient=np.asarray([q[3] for q in points], dtype=float),
        coupling_route_basal=np.asarray([q[4] for q in points], dtype=float),
        coupling_route_coupling=np.zeros(m, dtype=np.int64),
        regulatory_slot_cell=np.arange(m, dtype=np.int64),
        amount_reference=x[None, :],
        volume=np.ones(m),
    )
    state = SimpleNamespace(
        amount_increment=np.zeros((1, m)),
        regulatory_state=np.asarray([q[5] for q in points], dtype=float),
        coupling_enabled=np.ones(1),
    )
    return state, p


def part_a1(context):
    points, exact, bounds = [], [], []
    for law in ("hill_activation", "hill_inhibition"):
        for x in A1_X:
            for K in A1_K:
                for n in A1_N:
                    for b in A1_B:
                        points.append((law, x, K, n, b, 0.0))
                        exact.append(float(fr.exact_grid(law, b, x=x, K=K, n=n)))
                        bounds.append(a1_bound(law, x, K, n))
    for law in ("state_fraction", "state_complement"):
        for s in A1_S:
            for b in A1_B:
                points.append((law, 1.0, 1.0, 1.0, b, s))
                exact.append(float(fr.exact_grid(law, b, s=s)))
                bounds.append(4.0)
    state, p = a1_layout(points)
    with np.errstate(divide="ignore"):  # log(0) = -inf: the exact x = 0 points.
        host = np.asarray(sra.route_factors(state, p, xp=np))
    jstate = jax.tree.map(jnp.asarray, vars(state))
    jp = jax.tree.map(jnp.asarray, vars(p))
    device = np.asarray(
        jax.jit(
            lambda s_, p_: sra.route_factors(SimpleNamespace(**s_), SimpleNamespace(**p_), xp=jnp)
        )(jstate, jp)
    )
    exact = np.asarray(exact)
    host_eps = np.asarray(fr.eps_error(host, exact), dtype=float)
    device_eps = np.asarray(fr.eps_error(device, exact), dtype=float)
    bounds = np.asarray(bounds)

    # The products of two routes on one element (element_product), over the Hill points.
    hill = sum(1 for q in points if q[0].startswith("hill"))
    pairs = [(i, (7 * i + 13) % hill) for i in range(0, hill, 5)]
    table = np.asarray(pairs, dtype=np.int64)
    product_host = np.asarray(sra.element_product(host, table, xp=np))
    product_exact, product_bound = [], []
    for i, j in pairs:
        d = fr.exact_product(
            [
                fr.exact_side_factor(
                    "first",
                    points[i][0],
                    points[i][4],
                    first=points[i][1],
                    K=points[i][2],
                    n=points[i][3],
                ),
                fr.exact_side_factor(
                    "first",
                    points[j][0],
                    points[j][4],
                    first=points[j][1],
                    K=points[j][2],
                    n=points[j][3],
                ),
            ]
        )
        product_exact.append(fr.to_float(d))
        product_bound.append(bounds[i] + bounds[j] + 1.0)
    product_eps = np.asarray(fr.eps_error(product_host, np.asarray(product_exact)), dtype=float)

    def ratio(errors, bound):
        exact_points = bound == 0
        over = errors[~exact_points] / bound[~exact_points]
        return dict(
            max_ratio=float(np.max(over)) if over.size else 0.0,
            exact_points_exact=bool(np.all(errors[exact_points] == 0)),
            max_eps=float(np.max(errors)),
            points=int(errors.size),
        )

    return dict(
        host=ratio(host_eps, bounds),
        device=ratio(device_eps, bounds),
        products=ratio(product_eps, np.asarray(product_bound)),
        grid=dict(x=list(A1_X), K=list(A1_K), n=list(A1_N), b=list(A1_B), s=list(A1_S)),
    )


# ------------------------------------------------------------------ the run


def snapshot_identity(root=ROOT):
    manifest = Path(root) / "SNAPSHOT.json"
    if manifest.exists():
        snapshot = json.loads(manifest.read_text())
        return dict(
            kind="snapshot",
            git_revision=snapshot.get("git_revision"),
            patch_sha256=snapshot.get("patch_sha256"),
            status=snapshot.get("status"),
        )

    from validation import executed_sources  # noqa: PLC0415
    executed_sources.refuse_untracked(  # D259
        root, "regulated_availability_dt_study's source record"
    )

    def git(*args):
        done = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
        )
        return done.stdout.strip()

    return dict(
        kind="checkout", git_revision=git("rev-parse", "HEAD"), dirty=git("status", "--porcelain")
    )


def judged_run_refusal(protocol, root=ROOT):
    """Why a judged run may not start (None: it may) (MG0c's and D150's guard)."""
    status = protocol.get("status")
    if not (isinstance(status, str) and status.lower().startswith("registered")):
        return "the protocol is not registered (its status does not begin 'registered')"
    record = protocol.get("registration")
    if not (isinstance(record, dict) and record.get("status") == status):
        return "the protocol's registration record is missing or does not match its status"
    manifest = Path(root) / "SNAPSHOT.json"
    if not manifest.exists():
        return "a judged run comes from a clean execution snapshot of main, not a checkout"
    snapshot = json.loads(manifest.read_text())
    clean = snapshot.get("patch_sha256") == hashlib.sha256(b"").hexdigest()
    if snapshot.get("status") != "complete" or not clean:
        return "the execution snapshot is incomplete or carries uncommitted changes"
    return None


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def main(argv):
    jax.config.update("jax_enable_x64", True)
    mode = argv[0]
    if mode == "judged":
        protocol_path, out_dir, requested = argv[1], Path(argv[2]), list(argv[3:]) or list(PARTS)
        protocol = json.loads(Path(protocol_path).read_text())
        refusal = judged_run_refusal(protocol)
        if refusal is None and out_dir.exists():
            refusal = "the output directory exists (each attempt writes its own)"
        if refusal:
            raise SystemExit("Refused: " + refusal)
        status = "Judged run of " + protocol["id"]
        deltas = protocol["registered_control_deltas"]
    elif mode == "dev":
        out_dir, requested = Path(argv[1]), list(argv[2:]) or list(PARTS)
        if out_dir.exists():
            raise SystemExit("Refused: the output directory exists")
        status, deltas = "Development run", None
    else:
        raise SystemExit("Usage: dev OUT_DIR [PART ...] | judged PROTOCOL OUT_DIR [PART ...]")
    unknown = sorted(set(requested) - set(PARTS))
    if unknown:
        raise SystemExit(f"Refused: unknown parts {unknown}")
    if "controls" in requested and not {"a4", "a5"} <= set(requested):
        raise SystemExit("Refused: the controls part runs with the a4 and a5 parts")
    out_dir.mkdir(parents=True)
    results = dict(
        status=status,
        source=snapshot_identity(),
        requested_parts=requested,
        complete=False,
        ladder=list(DTS),
        parts={},
    )
    context, functions = {}, dict(a1=part_a1, a4=part_a4, a5=part_a5)
    for name in [p for p in PARTS if p in requested]:
        started = time.perf_counter()
        if name == "controls":
            value = part_controls(context, deltas)
        else:
            value = functions[name](context)
        value["wall_s"] = time.perf_counter() - started
        results["parts"][name] = value
        (out_dir / "results.json").write_text(json.dumps(plain(results), indent=1) + "\n")
    results["complete"] = True
    (out_dir / "results.json").write_text(json.dumps(plain(results), indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
