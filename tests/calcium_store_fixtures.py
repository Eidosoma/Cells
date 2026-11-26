"""What the compiled calcium store rows share (docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md, section
14, rows 13 and 14): a windowed run of a world of validation/calcium_store/worlds.py, read back
(Run); this file's own forms of the laws, from section 2 of
validation/calcium_store/reference_spec/SPEC.md (none of the laws' kernels is called); and the
criteria that hold the two together at every recorded row and step, as functions that return what
misses, so that a planted world or criterion can be shown to miss:
- misses_potentials: each node's potential is the one a dense capacitor solve of the row's
  charges gives;
- misses_factors: each condition's factor is its product of Hill factors;
- misses_moved: each mover's transfer over a step is the trapezoid of its rate at the step's two
  rows (the routes and the releases, the pumps and the exchangers, the channels, the junction's
  calcium and the patches' own ions), within MOVED_BAND: the two rules differ by about (dt x
  rate)^2 / 12, 3e-6 at the fastest rate of these worlds (460 per s);
- misses_sums: each ion, moiety and inert row keeps its whole-world amount;
- within_bounds: every ledger @3 checks is within its bound; restarts: a restart from a written
  checkpoint repeats the run bit for bit.
"""

import copy
import math

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.schedule import control_values
from cells.execution.windows import WindowPolicy, iter_windows
from cells.records.io import load_snapshot, write_snapshot
from cells.registry.models import get_model
from validation.calcium_store import worlds

F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23
FMOL_CHARGE = 1e-15 * F
DT, STEPS, WINDOW = 1.25e-5, 10, 5
POLICY = WindowPolicy(window_steps=WINDOW)
MOVED_BAND = 1e-4  # Of each mover's largest transfer over a step.
POTENTIAL_BAND_V = 1e-11
FACTOR_BAND = 1e-12
SUM_BAND = 64 * np.finfo(float).eps  # Of each whole-world amount, per step.


# ------------------------------------------------------------------ the laws' forms (SPEC 2)


def bernoulli(x):
    x = np.asarray(x, dtype=float)
    small = np.abs(x) < 1e-6
    safe = np.where(small, 1.0, x)
    return np.where(small, 1.0 - x / 2.0, safe / np.expm1(safe))


def constant_field(c_in, c_out, voltage, z, area, permeability, opening, rt):
    """fmol/s, positive from the inside to the outside (2.1)."""
    x = z * F * voltage / rt
    return 1e15 * area * permeability * opening * (c_in * bernoulli(-x) - c_out * bernoulli(x))


def factor(reads, concentrations):
    """One condition's factor (2.2)."""
    total = 0.0
    for r in reads:
        z = r["hill_coefficient"] * (
            math.log(concentrations[r["species"]]) - math.log(r["half_saturation_mM"])
        )
        total -= np.logaddexp(0.0, -z if r["form"] == "activation" else z)
    return math.exp(total)


def pump(c_n, c_p, v_np, fuel, data, potentials, rt, *, electrical=True):
    """Cycles, fmol/s (2.4; calcium, z = 2)."""
    n = data["stoichiometry"]
    x = potentials["ADP"] + potentials["Pi"] - potentials["ATP"]
    x = x + np.log(fuel["ADP"] * fuel["Pi"] / fuel["ATP"]) + n * np.log(c_p / c_n)
    x = x - (n * 2 * F * v_np / rt if electrical else 0.0)
    s = 1.0 / (1.0 + (data["K_role_mM"] / c_n) ** n) / (1.0 + data["K_ATP_mM"] / fuel["ATP"])
    return data["capacity_fmol_per_s"] * s * -np.expm1(x)


def exchanger(na_n, na_p, ca_n, ca_p, v_np, data, rt):
    """Cycles, fmol/s (2.5)."""
    a, b = na_n / data["K_Na_mM"], na_p / data["K_Na_mM"]
    c, d = ca_n / data["K_Ca_mM"], ca_p / data["K_Ca_mM"]
    u = F * v_np / rt
    top = b**3 * c * np.exp(-u / 2) - a**3 * d * np.exp(u / 2)
    return data["capacity_fmol_per_s"] * top / ((1 + a**3 + b**3) * (1 + c + d))


# ------------------------------------------------------------------ a run, read back


class Start:
    """A world at its start, read back by the definition's names: one observed row, with no step
    and no compile. The criteria read the honest world: its cells' numbers (`blocks`) and its
    definition (`raw`, where `planted` is the one the engine takes)."""

    def __init__(self, raw, blocks, *, planted=None):
        self.raw, self.blocks = raw, blocks
        self.spec = parse_spec(copy.deepcopy(raw if planted is None else planted))
        self.observed = self.observations()
        m = raw["model"]
        self.species = [s["id"] for s in m["species"]]
        self.cells = [c["id"] for c in m["cells"]]
        self.outside = [o["id"] for o in m["extracellular"]]
        self.patches = {p["id"]: p for p in m["membranes"]}
        declared = dict(self.spec.model.kinds)  # Each kind's entities, in its own order.
        self.routes = [r.id for r in declared["cells.kind.passive_routes@1"]]
        self.populations = [t.id for t in declared["cells.kind.transporter@1"]]
        self.conditions = [c.id for c in declared["cells.kind.species_condition@1"]]
        self.channels = [c["id"] for c in m["channels"]]
        self.rt = R * m["temperature_K"]
        self.volumes = {n["id"]: n["volume_pL"] for n in (*m["cells"], *m["extracellular"])}

    def observations(self):
        model, at = get_model(self.spec.model), np.zeros(1)
        state, p = model.initial_values(self.spec)
        history = type(state)(*(np.asarray(x)[None] for x in state))
        return [model.observe_history(at, history, p, at, self.spec)]

    def column(self, name):
        """An observed column over every observed row: [row, ...]."""
        return np.concatenate([np.asarray(getattr(o, name)) for o in self.observed])

    def amounts(self):
        """{node: [row, species]} fmol."""
        cell, out = self.column("amount"), self.column("extracellular_amount")
        found = {name: cell[:, :, i] for i, name in enumerate(self.cells)}
        return found | {name: out[:, :, i] for i, name in enumerate(self.outside)}

    def potentials(self):
        """{node: [row]} V."""
        cell, out = self.column("cell_potential_V"), self.column("extracellular_potential_V")
        found = {name: cell[:, i] for i, name in enumerate(self.cells)}
        return found | {name: out[:, i] for i, name in enumerate(self.outside)}

    def concentrations(self):
        return {
            node: {s: n[:, i] / self.volumes[node] for i, s in enumerate(self.species)}
            for node, n in self.amounts().items()
        }


class Run(Start):
    """A windowed run of a world, in two windows of WINDOW steps."""

    def observations(self):
        self.windows = list(iter_windows(self.spec, POLICY))
        return [window.observations for window in self.windows]


def bound(spec):
    """(model, state, control, layout) of a definition at its start, in NumPy."""
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    return model, state, type(controls)(*(np.asarray(v[0]) for v in controls)), p


def host_step(model, state, dt, control, p):
    """One composite step in NumPy, as split_step takes it: each operator's half-step, the inner
    model's IMEX step at the view, the half-steps in reverse."""
    valid = True
    for op in model.splits:
        state, ok = model._half_step(op, state, 0.5 * dt, control, p, xp=np)
        valid &= bool(ok)
    moved, ok = model.inner.imex_step(
        model.inner.inner_state(state),
        dt,
        model.control_view(control, state, p, xp=np),
        model.view(p, state, xp=np),
        xp=np,
    )
    valid &= bool(ok)
    state = state._replace(**moved._asdict())
    for op in reversed(model.splits):
        state, ok = model._half_step(op, state, 0.5 * dt, control, p, xp=np)
        valid &= bool(ok)
    return state, valid


def run_one():
    """The one-cell store world, its store at -5 mV."""
    volts = worlds.STORE_VOLTAGE_V
    raw = worlds.store_world(dt=DT, steps=STEPS, observe=range(STEPS + 1), v_store_V=volts)
    return Run(raw, [worlds.store_data(v_store_V=volts)])


TWO = dict(dt=DT, steps=STEPS, observe=range(STEPS + 1))


def two_blocks():
    blocks = [worlds.store_data(v_store_V=worlds.STORE_VOLTAGE_V), worlds.second_data()]
    for data in blocks:
        data["outside"] = "local"
    return blocks


def run_two(edit=None):
    """The two-cell world; edit(data_0, data_1), where given, plants numbers in the world that the
    engine runs and leaves the honest one to the criteria."""
    planted = None if edit is None else worlds.two_cells(**TWO, edit=edit)
    return Run(worlds.two_cells(**TWO), two_blocks(), planted=planted)


def start_two(plant=None):
    """The two-cell world's start; plant(model block), where given, changes the definition that the
    engine takes."""
    planted = worlds.two_cells(**TWO)
    if plant is not None:
        plant(planted["model"])
    return Start(worlds.two_cells(**TWO), two_blocks(), planted=planted)


# ------------------------------------------------------------------ the criteria


def misses_potentials(run, *, capacitance=1.0):
    """The (node, row) pairs whose potential is not that of a dense capacitor solve of the row's
    charges (SPEC 2.8): every node that a patch charges, the gauge at its own. `capacitance` plants
    a factor on the first patch's."""
    m = run.raw["model"]
    gauge = m["closure"]["gauge_reference"]
    nodes = sorted({end for p in m["membranes"] for end in (p["inside"], p["outside"])} - {gauge})
    index = {n: i for i, n in enumerate(nodes)}
    matrix = np.zeros((len(nodes), len(nodes)))
    for k, p in enumerate(m["membranes"]):
        c = p["capacitance_F"] * (capacitance if k == 0 else 1.0)
        ends = [index.get(p["inside"]), index.get(p["outside"])]
        for a, b in (ends, ends[::-1]):
            if a is not None:
                matrix[a, a] += c
                if b is not None:
                    matrix[a, b] -= c
    fixed = {n["id"]: n["fixed_charge_equivalent_fmol"] for n in (*m["cells"], *m["extracellular"])}
    valence = np.array([s["valence"] for s in m["species"]], dtype=float)
    amounts, found = run.amounts(), run.potentials()
    charge = np.stack([FMOL_CHARGE * (amounts[n] @ valence + fixed[n]) for n in nodes])
    solved = np.linalg.solve(matrix, charge)  # [node, row]
    off = np.stack([np.abs(found[n] - found[gauge] - solved[i]) for n, i in index.items()])
    return [(nodes[i], int(row)) for i, row in np.argwhere(~(off <= POTENTIAL_BAND_V))]


def misses_factors(run, *, node_of=None, reads_of=None):
    """The (condition, row) pairs whose observed factor is not its closed form. node_of and reads_of
    plant another node or other reads for a condition."""
    concentrations, observed = run.concentrations(), run.column("species_condition_factor")
    declared = {c["id"]: c for c in run.raw["model"]["species_conditions"]}
    form = {law: name for name, law in worlds.FORMS.items()}
    out = []
    for k, name in enumerate(run.conditions):
        node = (node_of or {}).get(name, declared[name]["node"])
        reads = [dict(r, form=form[r["form"]]) for r in declared[name]["reads"]]
        reads = (reads_of or {}).get(name, reads)
        for row in range(observed.shape[0]):
            at = {s: c[row] for s, c in concentrations[node].items()}
            if not abs(observed[row, k] - factor(reads, at)) <= FACTOR_BAND:
                out.append((name, row))
    return out


def rates(run, *, stores_exchanged=False, junction_turned=False, voltage_dropped=False,
          ions_exchanged=False):  # fmt: skip
    """{mover: [row] fmol/s, or cycles} at the recorded rows, by this file's forms: a route's
    inward, as passive_transferred is (a junction's into its sender), a channel's and a patch's own
    ions' outward, cycles forward. Each keyword plants one thing in the forms."""
    c, v = run.concentrations(), run.potentials()
    potentials = worlds.specification()["store_world"]["fuel_potentials_RT"]
    gates = run.column("channel_gate")  # [row, gate, channel]
    factors, rt, out = run.column("species_condition_factor"), run.rt, {}
    for k, data in enumerate(run.blocks):
        cell, store = f"cell_{k}", f"store_{1 - k if stores_exchanged else k}"
        outside, channel = data["outside"], data["calcium_channel"]
        far = dict(plasma=outside, bounding=store)
        area = {side: run.patches[f"{side}_{k}"]["area_m2"] for side in far}
        volts = {side: v[cell] - v[node] for side, node in far.items()}

        def flux(species, side, permeability, opening=1.0):
            z = worlds.VALENCE[species]
            ends = c[cell][species], c[far[side]][species]  # noqa: B023 (called in this pass)
            return constant_field(*ends, volts[side], z, area[side], permeability, opening, rt)  # noqa: B023

        for side in far:
            for s, permeability in data["patches"][side]["permeability_m_per_s"].items():
                out[f"{side}_{k} {s}"] = flux(s, side, permeability)
        for name, route in data["calcium_routes"].items():
            own = [run.conditions.index(f"{f}_{k}") for f in route.get("factors", ())]
            opening = np.prod(factors[:, own], axis=1)
            out[f"{name}_{k}"] = -flux("Ca", route["patch"], route["permeability_m_per_s"], opening)
        m, h = gates[:, :, run.channels.index(f"channel_{k}")].T
        permeability = channel["max_permeability_m_per_s"] * channel["abundance"]
        out[f"channel_{k}"] = flux("Ca", "plasma", permeability, m**2 * h)
        fuel = {s: c[cell][s] for s in ("ATP", "ADP", "Pi")}
        for name, numbers in data["pumps"].items():
            side = numbers["patch"]
            ends = c[cell]["Ca"], c[far[side]]["Ca"], volts[side]
            electrical = not voltage_dropped
            out[f"{name}_{k}"] = pump(*ends, fuel, numbers, potentials, rt, electrical=electrical)
        na, ca = ("Ca", "Na") if ions_exchanged else ("Na", "Ca")
        ends = c[cell][na], c[outside][na], c[cell][ca], c[outside][ca], volts["plasma"]
        out[f"exchanger_{k}"] = exchanger(*ends, data["exchanger"], rt)
    if "junction_calcium" in run.routes:
        j, gate = worlds.JUNCTION, run.column("junction_gate")[:, 0]
        ends = c["cell_0"]["Ca"], c["cell_1"]["Ca"], v["cell_0"] - v["cell_1"]
        out_flux = constant_field(*ends, 2, j["area_m2"], j["calcium_m_per_s"], gate, rt)
        out["junction_calcium"] = out_flux if junction_turned else -out_flux
    return out


def moved(run):
    """{mover: [step] fmol, or cycles} as the run's own accumulators give them."""
    ca, rows = run.species.index("Ca"), {}
    passive = run.column("passive_transferred")[:, ca, :]
    cycles = run.column("cycle_count")[:, 0, :]
    channels = run.column("channel_transferred")[:, ca, :]
    own = run.column("membrane_transferred")
    for names, series in (
        (run.routes, passive),
        (run.populations, cycles),
        (run.channels, channels),
    ):
        rows |= {name: series[:, i] for i, name in enumerate(names)}
    for i, (name, patch) in enumerate(run.patches.items()):
        for s, permeability in patch["permeability_m_per_s"].items():
            if permeability > 0:
                rows[f"{name} {s}"] = own[:, run.species.index(s), i]
    return {name: np.diff(series) for name, series in rows.items()}


def misses_moved(run, **plant):
    """{mover: its largest difference, relative} of those whose transfer over some step is not the
    trapezoid of their rate (rates, with its plants)."""
    given, accumulated, out = rates(run, **plant), moved(run), {}
    assert set(given) == set(accumulated)  # Every mover of the world, and no other.
    for name, rate in given.items():
        expected = 0.5 * DT * (rate[1:] + rate[:-1])
        worst = np.max(np.abs(accumulated[name] - expected)) / np.max(np.abs(expected))
        if not worst <= MOVED_BAND:
            out[name] = float(worst)
    return out


SUMS = dict(
    Na={"Na": 1}, K={"K": 1}, Cl={"Cl": 1}, calcium={"Ca": 1, "CaB": 1, "Ca2B": 2},
    buffer={"B": 1, "CaB": 1, "Ca2B": 1}, ATP={"ATP": 1}, ADP={"ADP": 1}, Pi={"Pi": 1},
    IP3={"IP3": 1},
)  # fmt: skip


def misses_sums(run, *, left_out=()):
    """{amount: its largest relative move} of the whole-world amounts that move by more than
    rounding. left_out plants nodes outside the sum."""
    amounts, out = run.amounts(), {}
    for name, terms in SUMS.items():
        total = sum(
            k * n[:, run.species.index(s)]
            for node, n in amounts.items()
            if node not in left_out
            for s, k in terms.items()
        )
        worst = np.max(np.abs(total - total[0])) / abs(total[0])
        if not worst <= SUM_BAND * STEPS:
            out[name] = float(worst)
    return out


def within_bounds(run):
    for window in run.windows:
        d = window.diagnostics
        assert d["max_energy_balance_relative"] <= 2e-3
        assert d["max_balance_error_fmol"] <= worlds.ION_FLOOR_FMOL
        assert d["max_extracellular_balance_error_fmol"] <= worlds.ION_FLOOR_FMOL
        assert d["max_electrode_charge_error_C"] == 0.0  # A closed world has no electrode.


def agrees(run):
    """Every criterion, at every row and step."""
    assert misses_potentials(run) == []
    assert misses_factors(run) == []
    assert misses_moved(run) == {}
    assert misses_sums(run) == {}
    within_bounds(run)


def bits(a):
    a = np.asarray(a)
    return a.dtype.str, a.shape, a.tobytes()


def restarts(run, folder):
    """A restart from the first window's written checkpoint repeats the second window."""
    write_snapshot(folder / "checkpoint", run.spec, run.windows[0].final)
    loaded = load_snapshot(folder / "checkpoint")
    (again,) = iter_windows(loaded.spec, POLICY, loaded.checkpoint)
    for name in type(again.history)._fields:
        a, b = getattr(again.history, name), getattr(run.windows[1].history, name)
        assert bits(a) == bits(b), name
