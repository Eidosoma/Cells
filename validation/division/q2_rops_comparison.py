"""Q2 development comparison: the engine's partition event map against R-ops (S5 design §8.3).

The comparison is built from validation/division/REFERENCES_USAGE.md alone (the lead's ruling).
R-ops' source, docstrings and tests are not read. The J2 bright line binds: this module reads
neither J1 input nor the J1 record, and imports no J1 module.

Each case is one pre-event engine state of a world from tests/partition_fixtures, bound in
NumPy. For each:
* the snapshot is every live slot of the tissue at the composite's view;
* R-ops' Division comes from the partition's declaration;
* the engine's event map is applied in NumPy, and rops.apply to the snapshot.
Compared, each at 64 eps x R-ops' own magnitude (the lead's ruling for Q2; keys without one
compare at 64 eps x the sum of both sides' absolute values):
* each daughter's amounts, increments, anchors, volume, background, charge anchor and node
  charge;
* the moved transfers;
* each daughter patch's area and capacitance, and the moved area, capacitance and abundance;
* the junction gates after the event;
* the record;
* the node potentials after the event, and the clamps' image charge;
* the work.

Cases:
* each world's events: the compact symmetric and asymmetric worlds, the neighbour contact, the
  bridge world's first and second divisions, the asymmetric furrow world with a bridge, and the
  second-onset world's first division;
* the simultaneous second divisions as the engine applies them: in the bridge world and in the
  second-onset world (each daughter with its old patch, its first furrow and its own second
  furrow onto its own cleft), both daughters divide at one time, and the engine's one event (its
  due vector from the schedule) is compared with R-ops applying the two divisions one after the
  other, in both orders. Each division's daughter fields compare with its own application; the
  potentials with the last application's; the clamps' image charge with the sum of both;
* 200 random pre-event states on each of two compact neighbour worlds, the symmetric one and
  an asymmetric one (f 0.75, a 0.6, three carriers): random increments, histories, patch
  growth, abundances and gates. The daughters' population abundances and gates are compared
  too, from R-ops' post-event snapshot.

The random states' sampling rule (the lead's ruling: inside @3's domain). Each draw (perturbed)
changes each live cell's content by uniform fractions within 1e-3 of each amount, made neutral
by M (the permeant anion), plus a net charge, carried by K, uniform within 10% of the cell's
declared charge; the patches, populations and contact get random histories, growth,
abundances and gates. A draw is admitted only if it passes the composite's own domain check
with the control at the event (@3's domain at the view, each operator's domain and control
checks, and the readouts' validity) and the charge bound: every live cell's net charge within
CHARGE_BAND (10%) of its declared charge. A rejected draw is redrawn, and the report counts
draws and rejections. The tolerance is 64 eps x R-ops' magnitudes throughout; no magnitude is
taken from the engine's representation.

Disclosed out-of-domain run: comparisons-s5a9 (snapshot-s5a9, 6c2b118) drew uncompensated
increments within 1e-3 of each amount: net charges about four times the membrane's, potentials
near 0.3 V. The asymmetric states reached 94.7 on the post-event potentials (and 73.6 on the
moved amounts, 33.0 on a daughter's charge). The cause: the engine forms node charges in
increment form (anchor + F sum z dn), and its rounding there scales with the increments' ionic
content, which R-ops' charge-form magnitudes do not count. (That run also passed population
abundances per area; 5234ba8 passes units.)

Usage: python -m validation.division.q2_rops_comparison OUTPUT_DIR. It is NumPy only, about a
minute.
"""

import dataclasses
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import jax
import numpy as np

from cells.core.specs import parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import partition
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests import partition_fixtures as fx
from validation.division import partition_reference as rops

STATUS = "Development comparison for Q2 (S5a); not judged"
RANDOM_STATES = 200
CHARGE_BAND = 0.1  # The charge bound: |Q - Q_declared| <= 0.1 |Q_declared| for every live cell.
MAX_DRAWS = 20  # Draws allowed for one admitted random state.
EPS = float(np.finfo(float).eps)


class Bound:
    """One bound world: spec, model, layout, the partition's declaration and the bridges."""

    def __init__(self, raw):
        self.spec = parse_spec(raw)
        self.model = get_model(self.spec.model)
        self.state, self.p = self.model.initial_values(self.spec)
        m = self.spec.model
        self.cells = [c.id for c in m.cells]
        self.nodes = [c.id for c in m.extracellular]
        self.patches = [k.id for k in m.membranes]
        self.channels = [c.id for c in m.channels]
        self.junctions = [j.id for j in m.junctions]
        self.background = {c.id: c.fixed_charge_equivalent_fmol for c in m.cells}
        entries = {op.LAW_ID: (op, d, s) for op, d, s in fx.cs.entries(self.spec)}
        self.partition = entries[partition.LAW_ID]
        bridges = entries.get(fx.BRIDGE)
        self.bridges = {} if bridges is None else {b.junction_id: b for b in bridges[1].bridges}

    def view(self, state):
        return self.model.view(self.p, state, xp=np)

    def snapshot(self, state):
        """Every live slot at the composite's view (REFERENCES_USAGE: Snapshot)."""
        q, p, m = self.view(state), self.p, self.spec.model
        z = np.ravel(p.valence)
        held = {
            self.nodes[i]: float(p.boundary_V[i])
            for i in np.flatnonzero(np.asarray(p.reservoir) & np.asarray(q.outside_active))
        }
        cells = {}
        for i in np.flatnonzero(np.asarray(q.active)):
            delta = np.asarray(state.amount_increment)[:, i]
            cells[self.cells[i]] = rops.Cell(
                reference_fmol=tuple(float(x) for x in np.asarray(p.amount_reference)[:, i]),
                increment_fmol=tuple(float(x) for x in delta),
                volume_pL=float(p.volume[i]),
                background_fmol=float(self.background[self.cells[i]]),
                charge_C=float(q.initial_cell_charge_C[i] + CHARGE_PER_FMOL * np.sum(z * delta)),
                charge_reference_C=float(p.initial_cell_charge_C[i]),
            )
        clefts = {}
        for c in np.flatnonzero(np.asarray(q.outside_active) & ~np.asarray(p.reservoir)):
            delta = np.asarray(state.extracellular_amount_increment)[:, c]
            amounts = np.asarray(p.extracellular_amount_reference)[:, c] + delta
            clefts[self.nodes[c]] = rops.Cleft(
                amounts_fmol=tuple(float(x) for x in amounts),
                volume_pL=float(q.extracellular_volume[c]),
                charge_C=float(q.initial_outside_charge_C[c] + CHARGE_PER_FMOL * np.sum(z * delta)),
            )
        patches, history = {}, {k: {} for k in HISTORY}
        for k in np.flatnonzero(np.asarray(q.membrane_active)):
            name = self.patches[k]
            patches[name] = rops.Patch(
                self.cells[int(p.membrane_cell[k])],
                self.nodes[int(p.membrane_outside[k])],
                area_reference_m2=float(p.membrane_area[k]),
                capacitance_reference_F=float(p.membrane_capacitance[k]),
                area_increment_m2=float(state.membrane_area_increment_m2[k]),
                capacitance_increment_F=float(state.membrane_capacitance_increment_F[k]),
            )
            history["membrane_transferred_fmol"][name] = np.array(state.membrane_transferred[:, k])
            history["membrane_heat_pJ"][name] = float(state.membrane_dissipated_energy_pJ[k])
        populations = {}
        for j in np.flatnonzero(np.asarray(q.channel_active)):
            name = self.channels[j]
            populations[name] = rops.Population(
                self.patches[int(p.channel_membranes[j])],
                abundance_reference=float(declared_units(p, j)),
                abundance_increment=float(state.population_abundance_increment[j]),
                gates=tuple(float(g) for g in np.asarray(state.channel_gate)[:, j]),
            )
            history["channel_transferred_fmol"][name] = np.array(state.channel_transferred[:, j])
            history["channel_heat_pJ"][name] = np.array(state.channel_dissipated_energy_pJ[:, j])
        contacts, bridges = {}, {}
        for e in np.flatnonzero(np.asarray(q.junction_active)):
            name, j = self.junctions[e], m.junctions[e]
            gates = (float(state.junction_gate[e]),)
            if name in self.bridges:
                bridges[name] = rops.Bridge(
                    (j.sender, j.receiver), float(state.bridge_aperture_m[e]), gates
                )
            else:
                contacts[name] = rops.Contact(
                    (j.sender, j.receiver), float(p.junction_area[e]), gates
                )
            history["junction_transferred_fmol"][name] = np.array(state.junction_transferred[:, e])
            history["junction_heat_pJ"][name] = float(state.junction_dissipated_energy_pJ[e])
        return rops.Snapshot(
            species=tuple(m.species_ids),
            z=tuple(int(x) for x in z),
            temperature_K=float(p.temperature),
            held=held,
            cells=cells,
            clefts=clefts,
            patches=patches,
            populations=populations,
            contacts=contacts,
            bridges=bridges,
            history=history,
        )

    def division(self, d, state):
        """R-ops' Division of the declared division d (over the parent's live slots)."""
        q = self.view(state)
        live = {self.patches[k] for k in np.flatnonzero(np.asarray(q.membrane_active))}
        bridge = next(
            (k for k, b in self.bridges.items() if set(self._ends(k)) == set(d.daughters)), ""
        )
        return rops.Division(
            parent=d.parent,
            daughters=tuple(d.daughters),
            f=d.volume_fraction,
            patches={k.parent: (*k.daughters, k.fraction) for k in d.patches if k.parent in live},
            populations={c.parent: tuple(c.daughters) for c in d.populations},
            contacts={e.parent: (*e.daughters, e.fraction) for e in d.contacts},
            carriers=dict(d.mismatch_carriers),
            bridge=bridge,
            bridge_a0_m=self.bridges[bridge].initial_aperture_m if bridge else 0.0,
        )

    def _ends(self, junction):
        j = self.spec.model.junctions[self.junctions.index(junction)]
        return j.sender, j.receiver

    def event(self, state, due):
        op = self.partition[0]
        new, ok = op.event(
            state, SimpleNamespace(partition_due=np.asarray(due, float)), self.p, xp=np,
            view=self.view,
        )  # fmt: skip
        return new, bool(ok)


def declared_units(p, j):
    """A population's declared abundance in units, as membrane_entity_state@1 counts it: @3's
    channel_abundance (per area, a0) x the patch's declared area A0 x the reference density."""
    patch = int(p.channel_membranes[j])
    return (
        p.channel_abundance[j] * p.membrane_area[patch] * p.population_reference_density_per_m2[j]
    )


HISTORY = (
    "membrane_transferred_fmol",
    "membrane_heat_pJ",
    "junction_transferred_fmol",
    "junction_heat_pJ",
    "channel_transferred_fmol",
    "channel_heat_pJ",
)
RECORD = {  # R-ops' record kinds and the engine's record fields.
    "membrane_transferred_fmol": ("partition_retired_membrane_transferred_fmol", "patch"),
    "membrane_heat_pJ": ("partition_retired_membrane_heat_pJ", "patch"),
    "junction_transferred_fmol": ("partition_retired_junction_transferred_fmol", "junction"),
    "junction_heat_pJ": ("partition_retired_junction_heat_pJ", "junction"),
    "channel_transferred_fmol": ("partition_retired_channel_transferred_fmol", "channel"),
    "channel_heat_pJ": ("partition_retired_channel_heat_pJ", "channel"),
}


def ratio(engine, reference, magnitude):
    """max |engine - reference| / (eps x magnitude), elementwise (0 when both are exact)."""
    engine, reference = np.asarray(engine, float), np.asarray(reference, float)
    magnitude = np.asarray(magnitude, float) * np.ones_like(reference)
    delta = np.abs(engine - reference)
    if not delta.any():
        return 0.0
    return float(np.max(delta / np.maximum(EPS * magnitude, np.finfo(float).tiny)))


def compare(world, d, before, after, result, *, skip=()):
    """{key: worst ratio} of one division (module docstring), without the keys in skip."""
    w, v, mag = world, result.values, result.magnitudes
    p, z = w.p, np.ravel(w.p.valence)
    q1 = w.view(after)
    out = {}
    index = {c: w.cells.index(c) for c in (d.parent, *d.daughters)}
    for tag, cell in zip(("D1", "D2"), d.daughters, strict=True):
        i = index[cell]
        delta = np.asarray(after.amount_increment)[:, i]
        reference = np.asarray(p.amount_reference)[:, i]
        engine = {
            f"amounts_{tag}_fmol": reference + delta,
            f"increment_{tag}_fmol": delta,
            f"reference_{tag}_fmol": reference,
            f"volume_{tag}_pL": p.volume[i],
            f"background_{tag}_fmol": w.background[cell],
            f"charge_reference_{tag}_C": p.initial_cell_charge_C[i],
            f"charge_{tag}_C": q1.initial_cell_charge_C[i] + CHARGE_PER_FMOL * np.sum(z * delta),
        }
        for key, value in engine.items():
            out[key] = ratio(value, v[key], mag[key])
    moved = np.asarray(after.partition_moved_fmol) - np.asarray(before.partition_moved_fmol)
    out["moved_fmol"] = max(
        ratio(moved[:, index[c]], v["moved_fmol"][c], mag["moved_fmol"][c]) for c in v["moved_fmol"]
    )
    area = np.asarray(p.membrane_area) + np.asarray(after.membrane_area_increment_m2)
    capacitance = np.asarray(p.membrane_capacitance) + np.asarray(
        after.membrane_capacitance_increment_F
    )
    for k in d.patches:
        for name in k.daughters:
            if f"area_{name}_m2" not in v:  # A parent patch not live at the event.
                continue
            e = w.patches.index(name)
            out[f"area_{name}_m2"] = ratio(area[e], v[f"area_{name}_m2"], mag[f"area_{name}_m2"])
            out[f"capacitance_{name}_F"] = ratio(
                capacitance[e], v[f"capacitance_{name}_F"], mag[f"capacitance_{name}_F"]
            )
    for key, field, names in (
        ("area_moved_m2", "partition_area_moved_m2", w.patches),
        ("capacitance_moved_F", "partition_capacitance_moved_F", w.patches),
        ("units_moved", "partition_units_moved", w.channels),
    ):
        moved = np.asarray(getattr(after, field)) - np.asarray(getattr(before, field))
        values = v.get(key, {})
        out[key] = max(
            [
                ratio(moved[names.index(s)], x, abs(moved[names.index(s)]) + abs(x))
                for s, x in values.items()
            ]
            or [0.0]
        )
    out["junction_gates_after"] = max(
        [ratio(after.junction_gate[w.junctions.index(s)], g[0] if len(g) else 0.0, 1.0)
         for s, g in v["junction_gates_after"].items()] or [0.0]
    )  # fmt: skip
    worst = 0.0
    for kind, slots in v["record"].items():
        field, axis = RECORD[kind]
        names = dict(patch=w.patches, junction=w.junctions, channel=w.channels)[axis]
        moved = np.asarray(getattr(after, field)) - np.asarray(getattr(before, field))
        for slot, value in slots.items():
            k = names.index(slot)
            mine = moved[..., k]
            worst = max(worst, ratio(mine, value, np.abs(mine) + np.abs(np.asarray(value))))
    out["record"] = worst
    phi = adapter.node_potentials(after, q1, xp=np)
    n = len(w.cells)
    potentials = {
        **{c: phi[k] for k, c in enumerate(w.cells)},
        **{c: phi[n + k] for k, c in enumerate(w.nodes)},
    }
    out["potentials_after_V"] = max(
        ratio(potentials[node], value, mag["potentials_after_V"][node])
        for node, value in v["potentials_after_V"].items()
    )
    image = np.asarray(after.electrode_charge_transferred_C) - np.asarray(
        before.electrode_charge_transferred_C
    )
    out["image_charge_C"] = max(
        ratio(image[w.nodes.index(b)], value, mag["image_charge_C"][b])
        for b, value in v["image_charge_C"].items()
    )
    for key in skip:
        del out[key]
    work = np.asarray(after.partition_work_pJ) - np.asarray(before.partition_work_pJ)
    out["work_pJ"] = ratio(work[index[d.parent]], v["work_pJ"], mag["work_pJ"])
    # The daughters' populations, from R-ops' post-event snapshot: abundance and gates.
    abundance, gates = 0.0, 0.0
    for c in d.populations:
        for name in c.daughters:
            mine = w.channels.index(name)
            theirs = result.snapshot.populations[name]
            total = theirs.abundance_reference + theirs.abundance_increment
            engine = declared_units(p, mine) + after.population_abundance_increment[mine]
            abundance = max(abundance, ratio(engine, total, abs(engine) + abs(total)))
            g = np.asarray(after.channel_gate)[: len(theirs.gates), mine]
            gates = max(gates, ratio(g, theirs.gates, 1.0))
    out["population_abundance"], out["population_gates"] = abundance, gates
    return out


def perturbed(world, rng, *, spread=CHARGE_BAND):
    """A random pre-event state of the neighbour world: increments, histories, growth, gates;
    each cell's net charge drawn within spread of its declared charge."""
    s = world.state
    fields = {k: np.array(getattr(s, k), copy=True) for k in type(s)._fields}
    cells = [world.cells.index(c) for c in ("cell_0", "cell_1")]
    amounts = np.asarray(world.p.amount_reference)[:, cells]
    # Increments within @3's domain: random content changes of 1e-3 of each amount, made
    # electroneutral by M, the permeant anion, plus a net charge within 10% of the cell's
    # declared charge. The potentials stay within a few mV of rest.
    z = np.ravel(world.p.valence)
    delta = amounts * rng.uniform(-1e-3, 1e-3, amounts.shape)
    m = list(world.spec.model.species_ids).index("M")
    delta[m] += np.sum(z[:, None] * delta, axis=0)  # z_M = -1: the content is now neutral.
    charge = np.abs(np.asarray(world.p.initial_cell_charge_C)[cells])
    k = list(world.spec.model.species_ids).index("K")
    delta[k] += rng.uniform(-spread, spread, len(cells)) * charge / CHARGE_PER_FMOL
    fields["amount_increment"][:, cells] = delta
    live = [world.patches.index(k) for k in ("membrane_0", "membrane_1")]
    # Histories only on routes @3 admits: a species a patch or contact does not pass, and a gate
    # row a population does not have, hold 0 (@3's domain).
    permeable = np.asarray(world.p.membrane_permeability)[:, live] > 0
    fields["membrane_transferred"][:, live] = permeable * rng.normal(
        0, 1e-4, (amounts.shape[0], len(live))
    )
    fields["membrane_dissipated_energy_pJ"][live] = rng.uniform(0, 1e-5, len(live))
    growth = rng.uniform(0, 1e-12, len(live))
    fields["membrane_area_increment_m2"][live] = growth
    fields["membrane_capacitance_increment_F"][live] = 0.05 * growth
    channels = [
        k for k, c in enumerate(world.spec.model.channels)
        if world.patches.index(c.membrane_id) in live
    ]  # fmt: skip
    fields["population_abundance_increment"][channels] = rng.uniform(0, 1e8, len(channels))
    gated = np.asarray(world.p.channel_gate_active)[:, channels]
    fields["channel_gate"][:, channels] = gated * rng.uniform(
        0, 1, (fields["channel_gate"].shape[0], len(channels))
    )
    contact = world.junctions.index("contact")
    fields["junction_gate"][contact] = rng.uniform(0.1, 1.0)
    passes = np.asarray(world.p.junction_permeability)[:, contact] > 0
    fields["junction_transferred"][:, contact] = passes * rng.normal(0, 1e-5, amounts.shape[0])
    fields["junction_dissipated_energy_pJ"][contact] = rng.uniform(0, 1e-6)
    return type(s)(**fields)


def cases():
    """(label, world, pre-event state, due, division id) for each world's events."""
    out = []
    carriers = {"Na": 0.5, "K": 0.5}
    asymmetric = dict(f=0.75, area_fraction=0.6, carriers=carriers)
    for label, raw in (
        ("compact symmetric", fx.divided()),
        ("compact asymmetric", fx.divided(**asymmetric)),
        ("neighbour contact", fx.divided(neighbour=True)),
    ):
        world = Bound(raw)
        out.append((label, world, world.state, (1.0,), "first"))
    world = Bound(fx.cleft_divided(bridge=("linear", 0.001), **asymmetric))
    out.append(("furrow asymmetric with a bridge", world, opened(world), (1.0,), "first"))
    world = Bound(fx.divided(bridge=("linear", 0.001), second=0.003, end=0.005))
    first, _ = world.event(world.state, (1.0, 0.0, 0.0))
    closed = first._replace(bridge_aperture_m=np.zeros_like(first.bridge_aperture_m))
    out.append(("bridge world, first division", world, world.state, (1.0, 0.0, 0.0), "first"))
    out.append(("bridge world, d1's division", world, closed, (1.0, 1.0, 0.0), "second_d1"))
    world = Bound(fx.cleft_quartered())
    out.append(
        ("second-onset world, first division", world, opened(world), (1.0, 0.0, 0.0), "first")
    )
    return out


def control_at(world, time):
    """The composite's control at one time of the schedule (NumPy)."""
    values = fx.cs.control_values(world.spec, [time])
    return world.model.CONTROL_TYPE(*(np.asarray(x[0]) for x in values))


def admitted(world, state, time):
    """(domain, charge) of a random draw (the sampling rule, module docstring): the composite's
    own domain check with the control at time, and the charge bound on every live cell."""
    p = world.p
    with np.errstate(all="ignore"):
        domain = world.model.domain_valid.with_control(
            state, control_at(world, time), p, p.active, xp=np
        )
    q = world.view(state)
    cells = np.flatnonzero(np.asarray(q.active))
    z = np.ravel(p.valence)
    delta = np.asarray(state.amount_increment)[:, cells]
    charge = np.asarray(q.initial_cell_charge_C)[cells] + CHARGE_PER_FMOL * (z @ delta)
    declared = np.asarray(p.initial_cell_charge_C)[cells]
    return bool(domain), bool(np.all(np.abs(charge - declared) <= CHARGE_BAND * np.abs(declared)))


def patch_voltages(world, state):
    """Each live patch's voltage at the view (V)."""
    q, p = world.view(state), world.p
    phi = adapter.node_potentials(state, q, xp=np)
    n = len(world.cells)
    return np.array(
        [
            phi[int(p.membrane_cell[k])] - phi[n + int(p.membrane_outside[k])]
            for k in np.flatnonzero(np.asarray(q.membrane_active))
        ]
    )


def opened(world):
    """The furrow worlds' state after the first onset and one insertion half-step: the furrow
    and its cleft are live, and the furrow has grown, as at the division."""
    ops = {op.LAW_ID: op for op in world.model.operators}
    control = control_at(world, fx.ONSET)
    state, ok = ops[fx.INSERTION2].event(world.state, control, world.p, xp=np, view=world.view)
    assert ok
    state, ok = ops[fx.INSERTION2].half_step(
        state, 0.5 * fx.DT, control, world.p, xp=np, view=world.view(state)
    )
    assert ok
    return state


def simultaneous_cases():
    """(label, world, pre-event state, time) of each world's simultaneous second divisions."""
    out = []
    world = Bound(fx.divided(bridge=("linear", 0.001), second=0.003, end=0.005))
    first, ok = world.event(world.state, control_at(world, fx.EVENT).partition_due)
    assert ok
    closed = first._replace(bridge_aperture_m=np.zeros_like(first.bridge_aperture_m))
    out.append(("bridge world", world, closed, 0.003))
    world = Bound(fx.cleft_quartered())
    out.append(("second-onset world", world, before_second(world), fx.SECOND))
    return out


def before_second(world):
    """The second-onset world before its second divisions: the first onset with one insertion
    half-step, the first division, both second onsets with one half-step (each daughter's first
    furrow and its second furrow grow), and the bridge closed, as its linear closure has it."""
    ops = {op.LAW_ID: op for op in world.model.operators}
    state, ok = world.event(opened(world), control_at(world, fx.EVENT).partition_due)
    assert ok
    control = control_at(world, fx.SECOND_ONSET)
    state, ok = ops[fx.INSERTION2].event(state, control, world.p, xp=np, view=world.view)
    assert ok
    state, ok = ops[fx.INSERTION2].half_step(
        state, 0.5 * fx.DT, control, world.p, xp=np, view=world.view(state)
    )
    assert ok
    return state._replace(bridge_aperture_m=np.zeros_like(state.bridge_aperture_m))


def live_history(snapshot):
    """A post-event snapshot as the next application's input. Its history still names the
    retired slots, where it reads 0 (REFERENCES_USAGE: Result), and an input's history names
    live slots only; those zero entries are dropped (asserted zero)."""
    live = dict(
        patch=set(snapshot.patches),
        junction={*snapshot.contacts, *snapshot.bridges},
        channel=set(snapshot.populations),
    )
    history = {}
    for kind, slots in snapshot.history.items():
        names = live[RECORD[kind][1]]
        history[kind] = {k: v for k, v in slots.items() if k in names}
        assert not any(np.any(v) for k, v in slots.items() if k not in names), kind
    return dataclasses.replace(snapshot, history=history)


def simultaneous(world, state, time, order):
    """{key: worst ratio}: the engine's one event at time, every division due there applied
    together as the engine applies them, against R-ops applying them one by one in order."""
    due = np.asarray(control_at(world, time).partition_due)
    divisions = {d.id: d for d in world.partition[1].divisions}
    names = [d.id for d in world.partition[1].divisions]
    pending = {names[k] for k in np.flatnonzero((due > 0) & (state.division_applied == 0))}
    assert pending == set(order), (pending, order)
    after, ok = world.event(state, due)
    assert ok
    snapshot, results = world.snapshot(state), []
    for name in order:
        result = rops.apply(snapshot, world.division(divisions[name], state))
        results.append(result)
        snapshot = live_history(result.snapshot)
    out = {}
    for k, (name, result) in enumerate(zip(order, results, strict=True)):
        last = k == len(order) - 1
        skip = ("image_charge_C",) if last else ("image_charge_C", "potentials_after_V")
        for key, value in compare(world, divisions[name], state, after, result, skip=skip).items():
            out[f"{name} {key}"] = value
    image = np.asarray(after.electrode_charge_transferred_C) - np.asarray(
        state.electrode_charge_transferred_C
    )
    out["image_charge_C"] = max(
        ratio(
            image[world.nodes.index(b)],
            sum(r.values["image_charge_C"][b] for r in results),
            sum(r.magnitudes["image_charge_C"][b] for r in results),
        )
        for b in results[0].values["image_charge_C"]
    )
    return out


def main(output):
    jax.config.update("jax_enable_x64", True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status=STATUS, tolerance_eps=64, cases={}, simultaneous={}, random={})
    for label, world, state, due, division_id in cases():
        d = next(x for x in world.partition[1].divisions if x.id == division_id)
        result = rops.apply(world.snapshot(state), world.division(d, state))
        after, ok = world.event(state, due)
        ratios = compare(world, d, state, after, result)
        report["cases"][label] = dict(engine_ok=ok, worst=max(ratios.values()), ratios=ratios)
        print(label, ok, f"{max(ratios.values()):.2f}", flush=True)
    for label, world, state, time in simultaneous_cases():
        entry = {}
        for order in (("second_d1", "second_d2"), ("second_d2", "second_d1")):
            ratios = simultaneous(world, state, time, order)
            entry[" then ".join(order)] = dict(worst=max(ratios.values()), ratios=ratios)
            print("simultaneous", label, order, f"{max(ratios.values()):.2f}", flush=True)
        report["simultaneous"][label] = entry
    rng = np.random.default_rng(20261113)
    carriers = {"Na": 0.3, "K": 0.5, "M": 0.2}
    for label, raw in (
        ("symmetric neighbour world", fx.divided(neighbour=True)),
        (
            "asymmetric neighbour world (f 0.75, a 0.6, three carriers)",
            fx.divided(neighbour=True, f=0.75, area_fraction=0.6, carriers=carriers),
        ),
    ):
        world = Bound(raw)
        d = next(x for x in world.partition[1].divisions if x.id == "first")
        worst, drawn, rejected = {}, 0, dict(domain=0, charge=0)
        voltage, deviation = 0.0, 0.0
        for _ in range(RANDOM_STATES):
            for _ in range(MAX_DRAWS):
                state = perturbed(world, rng)
                drawn += 1
                domain, charge = admitted(world, state, fx.EVENT)
                rejected["domain"] += not domain
                rejected["charge"] += not charge
                if domain and charge:
                    break
            else:
                raise RuntimeError(f"No admitted draw in {MAX_DRAWS} on the {label}")
            voltage = max(voltage, float(np.max(np.abs(patch_voltages(world, state)))))
            q = world.view(state)
            cells = np.flatnonzero(np.asarray(q.active))
            net = np.asarray(q.initial_cell_charge_C)[cells] + CHARGE_PER_FMOL * (
                np.ravel(world.p.valence) @ np.asarray(state.amount_increment)[:, cells]
            )
            declared = np.asarray(world.p.initial_cell_charge_C)[cells]
            deviation = max(deviation, float(np.max(np.abs(net / declared - 1.0))))
            result = rops.apply(world.snapshot(state), world.division(d, state))
            after, ok = world.event(state, (1.0,))
            assert ok
            for key, value in compare(world, d, state, after, result).items():
                worst[key] = max(worst.get(key, 0.0), value)
        report["random"][label] = dict(
            states=RANDOM_STATES,
            draws=drawn,
            rejected=rejected,
            max_abs_patch_voltage_V=voltage,
            max_net_charge_deviation=deviation,
            worst=max(worst.values()),
            ratios=worst,
        )
        print("random", label, f"{max(worst.values()):.2f}", flush=True)
    (output / "q2_rops.json").write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
