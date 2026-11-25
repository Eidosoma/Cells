"""FR-2 version 1's engine-side comparison with its code-blind references (D224: the user's choice
(b), 19 November 2026; validation/membrane_trafficking/references/REFERENCES_USAGE.md).

It reads only the four interface files: REFERENCES_USAGE.md, which is read by hand, never at run
time; reference_inputs.json (the stress worlds); designs/membrane_trafficking_reference_values.json
(T5's exact N at 4 ms); and interface/comparison_bands.json. It never reads the references' design
file, their code, or their own tests. The engine builds every declared world from its own
fixtures, the same calls its tests make, and each stress world from that declared world with the
stress record's nodes and routes laid over it (reference_inputs.json -> stress_worlds). It drives
scheduled_membrane_trafficking@1 on every registered drive and reads each row's quantity as
comparison_bands.json's `checks` define it.

A row passes when |engine - reference| <= band, the band being the file's own. The reference is a
50-digit string, compared in Decimal, against the engine's float64. A plant must fail its named row
wherever `must_refuse` is true. A zero-power plant row carries its kind's reason and is reported,
never asserted. No tolerance of this lane's enters.

The registered comparison (comparison_bands.json `counts`: 782 rows, 3 criteria, 322 plants, of
which 273 must be refused), and the test that evaluates each part:

Each part, its rows, and the test (under tests/unit/) that evaluates it:
- the T3, T4 and T6 rows of the 15 drives (d01-d15), 514 rows; T5's cycle_N and cycle_R on d09,
  32; and T5's both_N (Kir's N at n = 8 and 16), 2: test_membrane_trafficking_comparison.py,
  test_row;
- T5's three criteria, and the Lie split's plant, which is its criterion:
  test_membrane_trafficking_comparison.py, test_criterion;
- the operator-level plants, 12 kinds, 251 rows: test_membrane_trafficking_comparison.py,
  test_plant;
- T5's compiled rows on the 5 ms cycle world, 48: test_membrane_trafficking_runs.py,
  test_compiled_cycle_row;
- T5's compiled rows on T7's batch worlds (retrieval 0.05, 0.1 and 0.15), 144:
  test_membrane_trafficking_batch.py, test_batch_world_row;
- T8's start and factor rows, 42: test_membrane_trafficking_sheet.py, test_t8_row;
- the plants T8 without the coupling and without the retrieval, 70 rows:
  test_membrane_trafficking_sheet.py, test_t8_plant.

The engine side's mapping, reconciled with REFERENCES_USAGE.md ("How each test compares") and the
bands file's `checks` table before the first run:
1. Potentials and voltages come from the engine's own field solve (adapter.node_potentials and
   patch_voltages) on the operator's capacitor view: potential_unchanged is phi after less before
   at the node, V_b_after and V_k_after the patch voltage after, and V_b_kept the pool patch's
   voltage after less before (its references are 0).
2. dU_view, and the residual's ΔU, is the change of 1/2 sum C V^2 over the active patches (the
   view's capacitances, those voltages). view_capacitor_terms' energy alone is measured against
   @3's own term, and its change differs.
3. dG_chem is @3's chemical term per element (adapter.species_chemical_free_energy_pJ, anchor the
   amount before, change the move: the stable change), over the cells and the free outside nodes.
4. heat and heat_total, W_res, W_elec, electrode_transfer, image_charge and W_carriers(_route) are
   the changes of the engine's bookings over the half-step.
5. N_plus_R is the operator's own P0 ledger; dA_sum and dC_sum the change of its per-cell ledgers.
6. cleft_share is |the amount moved into the route's pool| over the sum, on the route's first
   declared carrier row.
7. A stress world is its declared world with the record's nodes and routes laid over it; its cells,
   patches and held potentials are asserted equal to the declared ones.
8. The batch worlds' rows are read on each world's own run, which the batch test checks the
   vmapped batch against (the batch keeps final states only).
9. The criteria take the engine's err(n) against the values file's exact N at 4 ms.
10. The plants: R1 zeroes the kernel's plate charge; the wrong-sign heat, carriers' work and
    electrode work negate each stage's booking; the reservoir work without z F phi_b loses
    1e-3 sum z F phi_b x supplied per stage; the dropped unit leaves the record at every half-step;
    e and e_r scale by 1 + 1e-6; carriers without their valence scale by z; the swapped t exchange
    each route's two numbers; the cleft's whole change is booked on one route (all, or none) by
    its share. A zero-power row passes once its kind's reason is asserted present.

The rows per check are 68 N_plus_R, 21 V_b_after, 9 V_b_kept, 9 V_k_after, 33 W_carriers, 2
W_carriers_route, 29 W_elec, 29 W_res, 2 both_N, 2 cleft_share, 192 compiled, 16 cycle_N, 16
cycle_R, 34 dA_sum, 34 dC_sum, 33 dG_chem, 33 dU_view, 29 electrode_transfer, 35 factor, 30 heat,
33 heat_total, 29 image_charge, 24 potential_unchanged, 33 residual and 7 start.
"""

import contextlib
import math
from decimal import Decimal, localcontext
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from cells.definitions.specs import parse_spec
from cells.laws.electrochemistry import F
from cells.models import pump_composite_adapter as adapter
from cells.operators import membrane_state
from cells.operators import membrane_trafficking as trafficking
from cells.registry.models import get_model
from validation import id_table
from validation.tissue import membrane_trafficking_fixtures as fx

REFERENCES = Path(__file__).resolve().parents[1] / "membrane_trafficking" / "references"
H = fx.DT / 2  # The operator-level tests' half-step.
CYCLE_E = {"kir_0": 1.0, "nav_0": 0.5}  # T5's enrichments (held_bath_cell_cycle_enrichments).
CYCLE_E_R = {"kir_0": 2.0, "nav_0": 1.0}
T8_PLANTS = ("T8 without the coupling", "T8 without the retrieval")
LIE = "the Lie split S_ret(h) S_rec(h)"


@lru_cache(maxsize=None)
def interface():
    """(bands, values, inputs): the three interface files read at run time."""
    return (
        id_table.load(REFERENCES / "interface/comparison_bands.json"),
        id_table.load(REFERENCES / "designs/membrane_trafficking_reference_values.json"),
        id_table.load(REFERENCES / "reference_inputs.json"),
    )


def rows(part):
    """The compared rows of one part: "operator", "compiled_cycle", "batch" or "t8"."""
    bands = interface()[0]["rows"]
    if part == "operator":
        return [r for r in bands if r["check"] not in ("compiled", "start", "factor")]
    if part == "compiled_cycle":
        return [r for r in bands if r["check"] == "compiled" and r["block"] == "compiled_cycle"]
    if part == "batch":
        return [r for r in bands if r["check"] == "compiled" and r["block"] != "compiled_cycle"]
    if part == "t8":
        return [r for r in bands if r["check"] in ("start", "factor")]
    raise ValueError(part)


def plants(part):
    """The plant rows of one part: "operator" (the Lie split's is its criterion's) or "t8"."""
    every = interface()[0]["plants"]
    if part == "t8":
        return [p for p in every if p["plant"] in T8_PLANTS]
    return [p for p in every if p["plant"] not in T8_PLANTS and p["plant"] != LIE]


def row_by_id():
    return {r["id"]: r for r in interface()[0]["rows"]}


def verdict(row, engine):
    """The row's verdict: |engine - reference| <= band, in Decimal (the reference's 50 digits)."""
    with localcontext() as ctx:
        ctx.prec = 60
        value = Decimal(float(engine))
        deviation = abs(value - Decimal(row["reference"]))
        band = Decimal(row["band"])
        margin = deviation / band if band else Decimal("Infinity")
        return dict(
            id=row["id"],
            engine=float(engine),
            deviation=float(deviation),
            band=row["band"],
            margin=float(margin),
            passed=bool(math.isfinite(float(engine)) and deviation <= band),
        )


# ------------------------------------------------------------------ worlds (engine fixtures)


def laws_world(*, plasma="membrane_0", bath_V=0.02, cleft=False, **changes):
    """The laws test's world(): one heredity cell, its pool and one route, the schedule zero."""
    raw = fx.pooled_cells(1, bath_V=bath_V, cleft=cleft)
    entry = fx.route(raw, 0, plasma=plasma, **changes)
    return fx.with_trafficking(raw, [entry], [fx.schedule(entry["id"], [(0.0, 0.0)])])


def shared_cleft_world():
    """The laws test's shared_cleft(): both furrows on cleft_0."""
    raw = fx.pooled_cells(2, cleft=True)
    m, x = raw["model"], raw["execution"]
    next(q for q in m["membranes"] if q["id"] == "furrow_1")["outside"] = "cleft_0"
    m["extracellular"] = [o for o in m["extracellular"] if o["id"] != "cleft_1"]
    m["faces"] = [f for f in m["faces"] if f["id"] != "access_1"]
    x.update(
        extracellular_capacity=x["extracellular_capacity"] - 1,
        face_capacity=x["face_capacity"] - 1,
    )
    routes = [fx.route(raw, i, plasma=f"furrow_{i}") for i in range(2)]
    return fx.with_trafficking(raw, routes, [fx.schedule(r["id"], [(0.0, 0.0)]) for r in routes])


DECLARED = {
    "held_bath_cell": lambda: laws_world(),
    "held_bath_cell_cycle_enrichments": lambda: laws_world(retrieval=CYCLE_E, recycling=CYCLE_E_R),
    "cleft_cell": lambda: laws_world(plasma="furrow_0", cleft=True),
    "two_routes_one_cleft": shared_cleft_world,
}


def stress_world(name):
    """A stress world: its declared world with the stress record's nodes and routes laid over it
    (every node's volume, amounts, fixed charge and anchor; every route's carriers, floors,
    enrichments and R0). Every other number is the declared one, which is asserted."""
    record = interface()[2]["stress_worlds"][name]
    raw = DECLARED[record["derived_from"]]()
    m = raw["model"]
    nodes = {o["id"]: o for o in m["extracellular"]}
    for node in record["nodes"]:
        o = nodes[node["id"]]
        assert o["reservoir"] == node["held"], node["id"]
        o["volume_pL"] = node["volume"]["value"]
        o["initial_amount_fmol"] = {s: v["value"] for s, v in node["initial_amounts"].items()}
        o["fixed_charge_equivalent_fmol"] = node["fixed_charge_equivalent"]["value"]
        o["initial_charge_C"] = node["charge_anchor"]["value"]
    for node in record["nodes"]:  # A held node's potential is the declared one.
        if node["held"]:
            assert nodes[node["id"]]["boundary_potential_V"] == node["held_potential"]["value"]
    for cell, declared in zip(record["cells"], m["cells"], strict=True):
        assert (cell["id"], cell["volume"]["value"], cell["charge_anchor"]["value"]) == (
            declared["id"],
            declared["volume_pL"],
            declared["initial_charge_C"],
        ), cell["id"]
        assert {s: v["value"] for s, v in cell["initial_amounts"].items()} == declared[
            "initial_amount_fmol"
        ], cell["id"]
    for patch in record["patches"]:
        q = fx.patch(raw, patch["id"])
        assert (q["area_m2"], q["capacitance_F"]) == (
            patch["area"]["value"],
            patch["capacitance"]["value"],
        ), patch["id"]
    block = next(op for op in m["operators"] if op["law"] == fx.LAW)
    by_id = {r["id"]: r for r in block["routes"]}
    for route in record["routes"]:
        r = by_id[route["id"]]
        r["carriers"] = {s: v["value"] for s, v in route["carriers"].items()}
        r["plasma_area_floor_m2"] = route["plasma_area_floor"]["value"]
        r["pool_area_floor_m2"] = route["pool_area_floor"]["value"]
        r["retrieval_enrichment"] = {
            c: v["value"] for c, v in route["retrieval_enrichment"].items()
        }
        r["recycling_enrichment"] = {
            c: v["value"] for c, v in route["recycling_enrichment"].items()
        }
        r["internalised_units"] = {c: v["value"] for c, v in route["R0"].items()}
    return raw


def world_raw(name):
    return stress_world(name) if name.startswith("stress_") else DECLARED[name]()


class World:
    """A bound world: spec, model, initial state, layout, and its names' slots."""

    def __init__(self, raw):
        self.raw = raw
        self.spec = parse_spec(raw)
        self.model = get_model(self.spec.model)
        self.state, self.p = self.model.initial_values(self.spec)
        m = raw["model"]  # The declared order, which the parser keeps (asserted below).
        self.op = next(op for op in self.model.operators if op.LAW_ID == fx.LAW)
        cells = [c["id"] for c in m["cells"]]
        outside = [o["id"] for o in m["extracellular"]]
        self.node = {name: i for i, name in enumerate(cells + outside)}
        self.outside = {name: i for i, name in enumerate(outside)}
        self.cell = {name: i for i, name in enumerate(cells)}
        self.patch = {q["id"]: i for i, q in enumerate(m["membranes"])}
        self.population = {c["id"]: i for i, c in enumerate(m["channels"])}
        self.species = [s["id"] for s in m["species"]]
        block = next(op for op in m["operators"] if op["law"] == fx.LAW)
        self.routes = [r["id"] for r in block["routes"]]
        self.carriers = [list(r["carriers"]) for r in block["routes"]]
        p = self.p
        assert p.active.size == len(cells) and p.outside_active.size == len(outside)
        assert np.array_equal(p.volume, [c["volume_pL"] for c in m["cells"]])
        assert np.array_equal(p.extracellular_volume, [o["volume_pL"] for o in m["extracellular"]])
        assert np.array_equal(p.membrane_area, [q["area_m2"] for q in m["membranes"]])
        assert np.asarray(p.valence).shape[0] == len(self.species)

    def area(self, state, name):
        return float(membrane_state.area(state, self.p, xp=np)[self.patch[name]])


@lru_cache(maxsize=None)
def world(name):
    return World(world_raw(name))


# ------------------------------------------------------------------ drives


def control(retrieval, recycling):
    return SimpleNamespace(
        trafficking_retrieval_rate_m2_s=np.asarray(retrieval, dtype=float),
        trafficking_recycling_rate_m2_s=np.asarray(recycling, dtype=float),
    )


def drive_steps(key, w):
    """The drive's half-steps, each a function of the state before it giving its control: the
    declared tests' rules (a fraction of a patch's declared area per half-step H; one recycling
    half-step at a fraction of the pool's current area), or a stress record's explicit rates."""
    name, test = key.split(":", 1)
    p = w.p
    if name.startswith("stress_"):
        record = interface()[2]["stress_worlds"][name]
        (drive,) = [d for d in record["stress_drives"] if d["id"] == test]
        assert drive["H"]["value"] == H, key
        steps = []
        for hs in drive["half_steps"]:
            ret = [hs["retrieval"].get(r, {"value": 0.0})["value"] for r in w.routes]
            rec = [hs["recycling"].get(r, {"value": 0.0})["value"] for r in w.routes]
            steps.append(lambda state, ret=ret, rec=rec: control(ret, rec))
        return steps
    k = [int(s) for s in p.trafficking_route_plasma]
    b = [int(s) for s in p.trafficking_route_pool]

    def declared(slot, fraction):
        return fraction * float(p.membrane_area[slot]) / H

    def fixed(ret, rec):
        return lambda state: control(ret, rec)

    retrieve = fixed([declared(k[0], 0.03)], [0.0])
    retrieve_02 = fixed([declared(k[0], 0.02)], [0.0])
    if test.startswith("test_retrieval_moves_only_the_pool") or test in (
        "test_the_energy_closes_exactly_and_the_carriers_work_is_their_free_energy[retrieval from a"
        " free node]",
        "test_the_energy_closes_exactly_and_the_carriers_work_is_their_free_energy[retrieval from a"
        " held bath at 20 mV]",
        "test_a_held_bath_books_its_electrode_and_reservoir_work_at_its_potential",
    ):
        return [retrieve]
    if test == "test_recycling_keeps_the_pool_and_merges_into_the_plasma_closed_form":
        current = lambda state: control(  # noqa: E731
            [0.0], [0.2 * float(membrane_state.area(state, p, xp=np)[b[0]]) / H]
        )
        return [retrieve_02] * 3 + [current]
    if test.endswith("[both directions at once]"):
        return [retrieve_02] * 2 + [fixed([declared(k[0], 0.02)], [declared(b[0], 0.1)])]
    if test.endswith("[recycling into the held bath's patch]"):
        return [retrieve_02] * 3 + [fixed([0.0], [declared(b[0], 0.2)])]
    if test == "test_a_cycle_follows_the_closed_forms_piecewise":
        return [retrieve_02] * 4 + [fixed([0.0], [declared(b[0], 0.05)])] * 4
    if test == "test_two_routes_on_one_free_node_close_and_share_its_free_energy_by_amount":
        return [fixed([declared(k[0], 0.03), declared(k[1], 0.06)], [0.0, 0.0])]
    raise KeyError(key)


# ------------------------------------------------------------------ plants


def _stage_plant(transform):
    """A context replacing the operator's stage by one whose new state `transform` rewrites."""
    real = trafficking.stage

    def planted(state, tau, rate, p, retrieval, *, xp):
        new, ok = real(state, tau, rate, p, retrieval, xp=xp)
        return transform(state, new, p), ok

    @contextlib.contextmanager
    def context():
        trafficking.stage = planted
        try:
            yield
        finally:
            trafficking.stage = real

    return context


def _negated(field):
    def transform(state, new, p):
        old = getattr(state, field)
        return new._replace(**{field: 2 * old - getattr(new, field)})

    return transform


def _without_z_f_phi(state, new, p):
    supplied = np.asarray(new.reservoir_supplied) - np.asarray(state.reservoir_supplied)
    electric = 1e-3 * np.sum(
        np.asarray(p.valence) * F * np.asarray(p.boundary_V)[None, :] * supplied, axis=0
    )
    return new._replace(reservoir_work_pJ=np.asarray(new.reservoir_work_pJ) - electric)


@contextlib.contextmanager
def _uncharged():
    """R1: the kernel's transfer at fixed charges, no carriers written."""
    real = trafficking.adapter.charge_following_transfer

    def planted(*args, **kwargs):
        out = real(*args, **kwargs)
        return out._replace(plate_C=0.0 * out.plate_C)

    trafficking.adapter.charge_following_transfer = planted
    try:
        yield
    finally:
        trafficking.adapter.charge_following_transfer = real


def _swapped_scale(w):
    """Each route's two transference numbers swapped: t_s/(z_s F) with t exchanged."""
    z = {s: v for s, v in zip(w.species, np.asarray(w.p.valence)[:, 0], strict=True)}
    scale = np.array(w.p.trafficking_carrier_scale, dtype=float)
    block = next(op for op in w.raw["model"]["operators"] if op["law"] == fx.LAW)
    for i, route in enumerate(block["routes"]):
        (a, ta), (c, tc) = route["carriers"].items()
        scale[i, w.species.index(a)] = tc / (z[a] * F)
        scale[i, w.species.index(c)] = ta / (z[c] * F)
    return scale


LAYOUT_PLANTS = {
    "e (or e_r) off by 1 part in 10^6": lambda w: w.p._replace(
        trafficking_retrieval_enrichment=np.asarray(w.p.trafficking_retrieval_enrichment)
        * (1 + 1e-6),
        trafficking_recycling_enrichment=np.asarray(w.p.trafficking_recycling_enrichment)
        * (1 + 1e-6),
    ),
    "carriers without their valence (delta = t dq/F)": lambda w: w.p._replace(
        trafficking_carrier_scale=np.asarray(w.p.trafficking_carrier_scale)
        * np.asarray(w.p.valence)[:, 0][None, :]
    ),
    "the two transference numbers swapped": lambda w: w.p._replace(
        trafficking_carrier_scale=_swapped_scale(w)
    ),
}
STAGE_PLANTS = {
    "a merge heat of the wrong sign": _negated("trafficking_dissipated_energy_pJ"),
    "the carriers' work with the wrong sign": _negated("trafficking_work_pJ"),
    "the electrode work with the wrong sign": _negated("electrode_work_pJ"),
    "the reservoir work without z F phi_b": _without_z_f_phi,
}
R1_PLANTS = (
    "R1 at a held bath: the owner's potential moves by V_k dC/(C_k - dC)",
    "R1 at a free node: the outside node's potential moves by -V_k dC/(C_k - dC)",
)
DROP = "a unit dropped from the record"
CLEFT_PLANTS = {
    "the whole cleft change on one route (this route takes all)": "all",
    "the whole cleft change on one route (this route takes none)": "none",
}


def run_drive(key, plant=None, population=None):
    """[(before, after)] over the drive's half-steps, with `plant` in place (a plant kind)."""
    w = world(key.split(":", 1)[0])
    p = LAYOUT_PLANTS[plant](w) if plant in LAYOUT_PLANTS else w.p
    if plant in STAGE_PLANTS:
        context = _stage_plant(STAGE_PLANTS[plant])()
    elif plant in R1_PLANTS:
        context = _uncharged()
    else:
        context = contextlib.nullcontext()
    pairs, state = [], w.state
    with context:
        for step in drive_steps(key, w):
            new, ok = w.op.half_step(state, H, step(state), p, xp=np)
            assert bool(ok), (key, plant, len(pairs) + 1)
            if plant == DROP:  # One unit leaves the population's record at every half-step.
                record = np.array(new.trafficking_internalised_units)
                record[0, w.population[population]] -= 1.0
                new = new._replace(trafficking_internalised_units=record)
            pairs.append((state, new))
            state = new
    return pairs


# ------------------------------------------------------------------ readings (the checks)


def potentials(w, state):
    view, _ = trafficking.capacitor_view(state, w.p, xp=np)
    phi = adapter.node_potentials(state, view, xp=np)
    return np.asarray(phi), np.asarray(adapter.patch_voltages(phi, view, xp=np))


def capacitor_energy(w, state):
    """1/2 sum C V^2 (pJ) over the active patches: the view's capacitances and the engine's patch
    voltages from its field solve. view_capacitor_terms' energy alone is not it: that term is
    measured against @3's own at the current charges, so its change is not this change."""
    view, _ = trafficking.capacitor_view(state, w.p, xp=np)
    _, v = potentials(w, state)
    c = np.where(np.asarray(view.membrane_active), np.asarray(view.membrane_capacitance), 0.0)
    return 0.5e12 * math.fsum((c * v**2).tolist())


def chemical_change(w, before, after, nodes=None):
    """The engine's ΔG_chem (pJ): @3's term per element, anchor the amount before and change the
    move, summed over the cells and the free outside nodes (or the outside nodes `nodes`)."""
    p, terms = w.p, []
    t = float(p.temperature)
    if nodes is None:
        amount = np.asarray(p.amount_reference) + np.asarray(before.amount_increment)
        change = np.asarray(after.amount_increment) - np.asarray(before.amount_increment)
        volume = np.asarray(p.volume)[None, :]
        live = np.broadcast_to(np.asarray(p.active)[None, :], amount.shape) & (amount > 0)
        terms.append((amount, change, volume, live))
    free = np.asarray(p.outside_active) & ~np.asarray(p.reservoir)
    if nodes is not None:
        free = free & np.isin(np.arange(free.size), [w.outside[n] for n in nodes])
    amount = np.asarray(p.extracellular_amount_reference) + np.asarray(
        before.extracellular_amount_increment
    )
    change = np.asarray(after.extracellular_amount_increment) - np.asarray(
        before.extracellular_amount_increment
    )
    volume = np.asarray(p.extracellular_volume)[None, :]
    live = np.broadcast_to(free[None, :], amount.shape) & (amount > 0)
    terms.append((amount, change, volume, live))
    out = []
    for amount, change, volume, live in terms:
        anchor = np.where(live, amount, 1.0)
        moved = np.where(live, change, 0.0)
        dg = adapter.species_chemical_free_energy_pJ(
            anchor, moved, np.broadcast_to(volume, anchor.shape), t, xp=np
        )
        out.extend(np.asarray(dg)[live].tolist())
    return math.fsum(out)


def change(before, after, field):
    return np.asarray(getattr(after, field), dtype=float) - np.asarray(
        getattr(before, field), dtype=float
    )


def cleft_terms(w, before, after):
    """Per route: (share, the engine's ΔG at its own pool, the cleft's ΔG), on the route's first
    declared carrier row, at the shared cleft (the node both plasma patches face)."""
    p = w.p
    (cleft,) = {int(p.membrane_outside[int(s)]) for s in p.trafficking_route_plasma}
    names = {i: n for n, i in w.outside.items()}
    pools = [int(p.membrane_outside[int(s)]) for s in p.trafficking_route_pool]
    s = w.species.index(w.carriers[0][0])
    moved = np.abs(change(before, after, "trafficking_carrier_fmol")[s, pools])
    shares = moved / math.fsum(moved)
    own = [chemical_change(w, before, after, nodes=[names[j]]) for j in pools]
    return shares, own, chemical_change(w, before, after, nodes=[names[cleft]])


def reading(row, w, before, after):
    """The engine's value of a drive's row over its half-step (before -> after)."""
    check = row["check"]
    p = w.p
    if check in ("potential_unchanged", "V_b_after", "V_b_kept", "V_k_after"):
        phi0, v0 = potentials(w, before)
        phi1, v1 = potentials(w, after)
        if check == "potential_unchanged":
            i = w.node[row["node"]]
            return phi1[i] - phi0[i]
        j = w.patch[row["patch"]]
        return v1[j] - v0[j] if check == "V_b_kept" else v1[j]
    if check in ("heat", "heat_total"):
        return math.fsum(change(before, after, "trafficking_dissipated_energy_pJ"))
    if check == "dG_chem":
        return chemical_change(w, before, after)
    if check == "dU_view":
        return capacitor_energy(w, after) - capacitor_energy(w, before)
    if check == "W_res":
        return math.fsum(change(before, after, "reservoir_work_pJ"))
    if check == "W_elec":
        return change(before, after, "electrode_work_pJ")[w.outside[row["node"]]]
    if check == "electrode_transfer":
        return change(before, after, "electrode_charge_transferred_C")[w.outside[row["node"]]]
    if check == "image_charge":
        return change(before, after, "trafficking_image_charge_C")[w.outside[row["node"]]]
    if check == "W_carriers":
        return math.fsum(change(before, after, "trafficking_work_pJ"))
    if check == "W_carriers_route":
        return change(before, after, "trafficking_work_pJ")[w.routes.index(row["route"])]
    if check == "cleft_share":
        shares, _, _ = cleft_terms(w, before, after)
        return shares[w.routes.index(row["route"])]
    if check == "residual":
        terms = (
            chemical_change(w, before, after),
            capacitor_energy(w, after) - capacitor_energy(w, before),
            math.fsum(change(before, after, "trafficking_dissipated_energy_pJ")),
            -math.fsum(change(before, after, "reservoir_work_pJ")),
            -math.fsum(change(before, after, "electrode_work_pJ")),
            -math.fsum(change(before, after, "trafficking_work_pJ")),
        )
        return math.fsum(terms)
    if check == "N_plus_R":
        ledger = trafficking.own_ledgers(after, p, xp=np)["trafficking_units"]
        return np.asarray(ledger)[w.population[row["population"]]]
    if check in ("dA_sum", "dC_sum"):
        name = "trafficking_area" if check == "dA_sum" else "trafficking_capacitance"
        a = np.asarray(trafficking.own_ledgers(after, p, xp=np)[name])
        b = np.asarray(trafficking.own_ledgers(before, p, xp=np)[name])
        return (a - b)[w.cell[row["cell"]]]
    if check == "cycle_N":
        return np.asarray(membrane_state.units(after, p, xp=np))[w.population[row["population"]]]
    if check == "cycle_R":
        return np.asarray(after.trafficking_internalised_units)[0, w.population[row["population"]]]
    raise KeyError(check)


# ------------------------------------------------------------------ T5's both directions at once


def both_directions(n, lie=False):
    """Kir's N at 4 ms after n equal steps h on held_bath_cell_cycle_enrichments, at r1 = 0.05
    A(membrane_0)/dt and r2 = 0.4 A(pool_membrane_0)/dt from R0 = 0: the palindrome, or the Lie
    split S_ret(h) S_rec(h) (the plant)."""
    w = world("held_bath_cell_cycle_enrichments")
    p = w.p
    k, b = int(p.trafficking_route_plasma[0]), int(p.trafficking_route_pool[0])
    rate = control(
        [0.05 * float(p.membrane_area[k]) / fx.DT], [0.4 * float(p.membrane_area[b]) / fx.DT]
    )
    h, state = 4 * fx.DT / n, w.state
    for _ in range(n):
        if lie:
            state, _ = trafficking.stage(
                state, h, rate.trafficking_retrieval_rate_m2_s, p, True, xp=np
            )
            state, _ = trafficking.stage(
                state, h, rate.trafficking_recycling_rate_m2_s, p, False, xp=np
            )
        else:
            state, ok = trafficking.trafficked(state, h, rate, p, xp=np)
            assert bool(ok)
    return float(np.asarray(membrane_state.units(state, p, xp=np))[w.population["kir_0"]])


def criteria():
    """T5's criteria on Kir's N, against the exact N at 4 ms (the values file): the engine's
    err(8)/err(16) in (3.5, 4.5), err(16) < 1e-4, and the Lie plant's ratio below 2.5."""
    values = interface()[1]
    exact = Decimal(values["T5"]["both_directions"]["populations"]["kir_0"]["exact"]["N"])

    def err(n, lie=False):
        return float(abs(Decimal(both_directions(n, lie)) - exact) / exact)

    e8, e16, l8, l16 = err(8), err(16), err(8, True), err(16, True)
    out = {}
    for c in interface()[0]["criteria"]:
        if c["id"].endswith("ratio_8_16") and "lie" not in c["id"]:
            out[c["id"]] = dict(engine=e8 / e16, passed=3.5 < e8 / e16 < 4.5)
        elif c["id"].endswith("err16"):
            out[c["id"]] = dict(engine=e16, passed=e16 < 1e-4)
        else:
            r = l8 / l16
            out[c["id"]] = dict(engine=r, passed=r < 2.5 and not 3.5 < r < 4.5)
    return out


# ------------------------------------------------------------------ the operator-level verdicts


@lru_cache(maxsize=None)
def operator_verdicts():
    """{row id: verdict} for every operator-level row."""
    out, pairs = {}, {}
    for row in rows("operator"):
        if row["check"] == "both_N":
            n = 8 if "after 8 " in row["quantity"] else 16
            assert f"after {n} palindromic" in row["quantity"], row["quantity"]
            out[row["id"]] = verdict(row, both_directions(n))
            continue
        key = row["drive"]
        if key not in pairs:
            pairs[key] = run_drive(key)
            assert len(pairs[key]) == len(interface()[1]["drives"][key]["half_steps"]), key
        w = world(key.split(":", 1)[0])
        before, after = pairs[key][row["half_step"] - 1]
        out[row["id"]] = verdict(row, reading(row, w, before, after))
    return out


@lru_cache(maxsize=None)
def plant_verdicts():
    """{(plant kind, row id): the planted row's verdict, with must_refuse and the reason}."""
    by_id, kinds = row_by_id(), interface()[0]["plant_kinds"]
    out, runs = {}, {}
    for plant in plants("operator"):
        row = by_id[plant["row"]]
        kind, key = plant["plant"], row["drive"]
        w = world(key.split(":", 1)[0])
        if kind in CLEFT_PLANTS:
            if (None, key) not in runs:
                runs[(None, key)] = run_drive(key)
            before, after = runs[(None, key)][row["half_step"] - 1]
            booked = reading(row, w, before, after)
            shares, _, cleft = cleft_terms(w, before, after)
            share = shares[w.routes.index(row["route"])]
            value = (
                booked + (1 - share) * cleft
                if CLEFT_PLANTS[kind] == "all"
                else booked - share * cleft
            )
        else:
            run = (kind, key, row.get("population") if kind == DROP else None)
            if run not in runs:
                runs[run] = run_drive(key, plant=kind, population=run[2])
            before, after = runs[run][row["half_step"] - 1]
            value = reading(row, w, before, after)
        v = verdict(row, value)
        out[(kind, row["id"])] = dict(
            v,
            must_refuse=plant["must_refuse"],
            refused=not v["passed"],
            registered_size=plant["size"],
            reason=kinds[kind].get("zero_power"),
        )
    return out


# ------------------------------------------------------------------ the compiled and T8 rows


def history_row(history, j):
    return type(history)(*(np.asarray(v)[j] for v in history))


def compiled_value(row, raw, p, history):
    """A compiled row's engine value: the run's history at its observation (N and R per
    population, A and C of the plasma patch k and the pool patch b)."""
    state = history_row(history, row["observation"])
    name = row["quantity"].split(" at ")[0]
    population = {c["id"]: i for i, c in enumerate(raw["model"]["channels"])}
    k, b = int(p.trafficking_route_plasma[0]), int(p.trafficking_route_pool[0])
    if name.startswith("N|"):
        return np.asarray(membrane_state.units(state, p, xp=np))[population[name[2:]]]
    if name.startswith("R|"):
        return np.asarray(state.trafficking_internalised_units)[0, population[name[2:]]]
    area = np.asarray(membrane_state.area(state, p, xp=np))
    capacitance = np.asarray(membrane_state.capacitance(state, p, xp=np))
    return {"A_k": area[k], "A_b": area[b], "C_k_F": capacitance[k], "C_b_F": capacitance[b]}[name]


def t8_value(row, raw, spec, model, p, result, controls):
    """A T8 row's engine value: F x availability x abundance x area of its Kir population, @3's
    conductance factor in m^2, at t = 0 (start) or at its observation (factor)."""
    population = {c["id"]: i for i, c in enumerate(raw["model"]["channels"])}[row["population"]]
    j = 0 if row["check"] == "start" else row["observation"]
    state = history_row(result.history, j)
    control = model.CONTROL_TYPE(*(np.asarray(v)[j] for v in controls))
    view = model.view(p, state, xp=np)
    effective = np.asarray(model.control_view(control, state, p, xp=np).channel)[population]
    patch = int(np.asarray(p.channel_membranes)[population])
    return (
        effective
        * np.asarray(view.channel_abundance)[population]
        * np.asarray(view.membrane_area)[patch]
    )
