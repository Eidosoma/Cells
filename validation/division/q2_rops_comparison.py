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
* 200 random pre-event states: random increments, histories, patch growth, abundances and
  gates on the compact neighbour world.

Usage: python -m validation.division.q2_rops_comparison OUTPUT_DIR. It is NumPy only, about a
minute.
"""

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
                abundance_reference=float(p.channel_abundance[j]),
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


def compare(world, d, before, after, result):
    """{key: worst ratio} of one division (module docstring)."""
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
        ratio(
            moved[:, index[c]],
            v["moved_fmol"][c],
            np.abs(moved[:, index[c]]) + np.abs(v["moved_fmol"][c]),
        )
        for c in v["moved_fmol"]
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
    work = np.asarray(after.partition_work_pJ) - np.asarray(before.partition_work_pJ)
    out["work_pJ"] = ratio(work[index[d.parent]], v["work_pJ"], mag["work_pJ"])
    return out


def perturbed(world, rng):
    """A random pre-event state of the neighbour world: increments, histories, growth, gates."""
    s = world.state
    fields = {k: np.array(getattr(s, k), copy=True) for k in type(s)._fields}
    cells = [world.cells.index(c) for c in ("cell_0", "cell_1")]
    amounts = np.asarray(world.p.amount_reference)[:, cells]
    fields["amount_increment"][:, cells] = amounts * rng.uniform(-1e-3, 1e-3, amounts.shape)
    live = [world.patches.index(k) for k in ("membrane_0", "membrane_1")]
    fields["membrane_transferred"][:, live] = rng.normal(0, 1e-4, (amounts.shape[0], len(live)))
    fields["membrane_dissipated_energy_pJ"][live] = rng.uniform(0, 1e-5, len(live))
    growth = rng.uniform(0, 1e-12, len(live))
    fields["membrane_area_increment_m2"][live] = growth
    fields["membrane_capacitance_increment_F"][live] = 0.05 * growth
    channels = [
        k for k, c in enumerate(world.spec.model.channels)
        if world.patches.index(c.membrane_id) in live
    ]  # fmt: skip
    fields["population_abundance_increment"][channels] = rng.uniform(0, 1e8, len(channels))
    fields["channel_gate"][:, channels] = rng.uniform(
        0, 1, (fields["channel_gate"].shape[0], len(channels))
    )
    contact = world.junctions.index("contact")
    fields["junction_gate"][contact] = rng.uniform(0.1, 1.0)
    fields["junction_transferred"][:, contact] = rng.normal(0, 1e-5, amounts.shape[0])
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


def opened(world):
    """The furrow worlds' state after the first onset and one insertion half-step: the furrow
    and its cleft are live, and the furrow has grown, as at the division."""
    ops = {op.LAW_ID: op for op in world.model.operators}
    values = fx.cs.control_values(world.spec, [fx.ONSET])
    control = world.model.CONTROL_TYPE(*(np.asarray(x[0]) for x in values))
    state, ok = ops[fx.INSERTION2].event(world.state, control, world.p, xp=np, view=world.view)
    assert ok
    state, ok = ops[fx.INSERTION2].half_step(
        state, 0.5 * fx.DT, control, world.p, xp=np, view=world.view(state)
    )
    assert ok
    return state


def main(output):
    jax.config.update("jax_enable_x64", True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status=STATUS, tolerance_eps=64, cases={}, random={})
    for label, world, state, due, division_id in cases():
        d = next(x for x in world.partition[1].divisions if x.id == division_id)
        result = rops.apply(world.snapshot(state), world.division(d, state))
        after, ok = world.event(state, due)
        ratios = compare(world, d, state, after, result)
        report["cases"][label] = dict(engine_ok=ok, worst=max(ratios.values()), ratios=ratios)
        print(label, ok, f"{max(ratios.values()):.2f}", flush=True)
    world = Bound(fx.divided(neighbour=True))
    d = next(x for x in world.partition[1].divisions if x.id == "first")
    rng = np.random.default_rng(20261113)
    worst = {}
    for _ in range(RANDOM_STATES):
        state = perturbed(world, rng)
        result = rops.apply(world.snapshot(state), world.division(d, state))
        after, ok = world.event(state, (1.0,))
        assert ok
        for key, value in compare(world, d, state, after, result).items():
            worst[key] = max(worst.get(key, 0.0), value)
    report["random"] = dict(states=RANDOM_STATES, worst=max(worst.values()), ratios=worst)
    print("random", f"{max(worst.values()):.2f}", flush=True)
    (output / "q2_rops.json").write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
