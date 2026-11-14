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
* the frozen random draws on each of two compact neighbour worlds, the symmetric one and an
  asymmetric one (f 0.75, a 0.6, three carriers): random increments, histories, patch growth,
  abundances and gates. The daughters' population abundances and gates are compared too, from
  R-ops' post-event snapshot;
* the negative controls (negative_controls).

The random sets (the lead, 14 November; frozen before R-ops' amended magnitudes land). For each
world and each net-charge spread of SPREADS (0.1, 1 and 3 declared charges): RANDOM_STATES (200)
draws of perturbed from a fresh numpy generator. The seen sets, seeded SEEN_SEED (20261113, the
draws q2_domain_probe makes), are development evidence: main() runs them, at each scale R-ops
offers. The judged sets take fresh seeds, the protocol's alone, which only judge() reads, behind
its guard; nobody runs them before the judged run. Every draw the composite's control domain
check admits, with the
control at the event (@3's domain at the view, each operator's domain and control checks, and
the readouts' validity, where the gating laws' voltage domains sit), is compared, and no other
bound applies: no draw is redrawn. Each draw changes each live cell's content by uniform
fractions within 1e-3 of each amount, made neutral by M (the permeant anion), plus a net
charge, carried by K, uniform within the spread times the cell's declared charge; the patches,
populations and contact get random histories (on admitted routes only), growth, abundances and
gates. The report counts the admitted draws, and how many lie outside the earlier 10%
net-charge band (CHARGE_BAND), which the lead dropped: it kept |V| away from zero and so
bounded the ratio by construction.

Q2 is open (the lead, 14 November). Within the control domain check alone the asymmetric world
exceeds 64 eps x R-ops' present magnitudes (q2_domain_probe), and the difference scales with
the increments' ionic content (q2_rounding_cause). R-ops' magnitudes for a cell's node charge,
input and daughters alike, add |Q| + 1e-15 F sum |z dn| and carry it through R-ops' own solve
(Appendix A.8). Once R-ops takes charge_term, every case runs under both scales (apply: the old
without the term, the new with it); until then the old alone.

The negative controls (the lead, 14 November: every family A.8 loosens, under both scales; frozen
with the judged seeds). Cases: the asymmetric neighbour world's bound state; its near-zero seen
draws NEAR_ZERO (admitted, the parent patch within NEAR_ZERO_V of 0 V before the event; the
860.6 draw, WORST_SEEN, among them); the asymmetric furrow world. In each, R-ops is applied with
a defect against the engine's own event (to first order, an engine defect of -delta), for each
delta of DEFECTS (1e-16 to 1e-2 in quarter decades):
* a_k: membrane_0's share a_k + delta. Its charge and capacitance split together, so each
  daughter patch keeps its parent's voltage: it reaches the charges, never the potentials;
* the parent charge: Q_P + delta |Q_declared| (the snapshot's charge anchor, so the defect does
  not vanish as Q_P nears 0): the charges and the potentials;
* f: the volume fraction f + delta: the amounts, increments, moved amounts and W;
* transference: the first carrier's t + delta and the second's t - delta (their sum stays 1):
  delta and the mismatch, which the engine exposes only through the increments and moved
  amounts that carry them;
* W (the amendment, the lead, 14 November): R-ops' daughters' free energy evaluated at
  V_D (1 + delta), a booking defect in the free-energy volume: W moves by -1e-3 RT N_D
  ln(1 + delta), first order. f no longer targets W: dG is stationary at the correct split (at
  delta = 0 the daughters' concentrations equal the parent's, d dG / d delta = ln c_D1 - ln c_D2
  = 0), so a map defect reaches W only at second order (W equals dG here, the bath at 0 V);
  f's effect on W is reported;
* mismatch scale (the amendment; formerly "image"): the engine moves (1 + delta) times the
  mismatch, its carrier fractions scaled, which breaks isopotentiality at first order: the
  potentials and the charges (an engine-side defect; R-ops' interface keeps the transference
  numbers summing to 1). It cannot reach the image charge: a held node's plate charge is minus
  the total charge of the patches facing it, which a charge-conserving split leaves unchanged
  (the second amendment, the lead, 14 November);
* non-conservation (the second amendment): D2 takes slightly more than the rest, Delta_D2 ->
  (Delta_P - Delta_D1)(1 + delta), applied to the engine's state after its event (its D2
  increment and moved amount, and the image it books, plates1 - plates0, recomputed with the
  partition's capacitor_state). At first order it moves the amounts by delta Delta_D2, and the
  charges and the image charge by delta F sum_s z_s Delta_D2,s, which is zero where D2's
  increment is electroneutral: a miss there is read as such, as for W. The work bookings keep
  the engine's undefected values, so the control's work entries are uninformative.
For the two engine-side controls the delta at which the engine's own event checks refuse is
reported, with the checks that refuse it: the event map's verdict for the mismatch scale, and
for non-conservation the partition's event checks (isopotential, outside potentials, plate
charges, positivity, finiteness, with its constants) re-applied to the defective state
(event_checks), since the event map conserves by construction. Each case records the
construction against the engine (construction_checks): at delta = 0 the non-conservation
construction reproduces the engine's event in every field; event_checks passes the engine's
event; and along the mismatch-scale ladder it agrees with the event map's verdict and booked
image at every delta. The verdict requires all three.
The near-zero rule applies unchanged to the judged sets: the judged run's near-zero cases are
the judged sets' admitted draws within NEAR_ZERO_V of 0 V.
The statistic is the smallest delta whose ratio passes 64, per family (CONTROL_GROUPS); the
threshold: each control's target families (CONTROL_TARGETS) caught at or below THRESHOLD
(1e-9) wherever the undefected case passes. Where the undefected ratio already exceeds 64 no
defect is measurable at that scale, and the report says so; at the new scale each near-zero
case must pass undefected and fail with the parent-charge defect. A control that misses the
threshold is a finding, never a moved threshold.

Disclosed out-of-domain run: comparisons-s5a9 (snapshot-s5a9, 6c2b118) drew uncompensated
increments within 1e-3 of each amount. The asymmetric states reached 94.7 on the post-event
potentials (and 73.6 on the moved amounts, 33.0 on a daughter's charge). Those draws (as
q2_domain_probe redraws them) pass @3's bare domain check but fail the composite's control
domain check in 197 of 200, and the charge band in all 200 (|V| up to 1.3 V, net charge up to
61 times the declared). The control domain check rejects them through the gating laws'
voltage domains among the readouts' validity: each rejected draw has a live patch voltage
outside the channel gates' (-0.120, 0.060) V, and most also a contact voltage above the
junction gate's 0.120 V. The cause of the ratio:
the engine forms node charges in increment form (anchor + F sum z dn), and its rounding there
scales with the increments' ionic content, which R-ops' charge-form magnitudes do not count.
(That run also passed population abundances per area; 5234ba8 passes units. q2-s5a10's draws
held histories on routes @3 does not admit, which its domain check refuses; 987fa28 draws them
on admitted routes only, and the ratios are unchanged.)

Usage: python -m validation.division.q2_rops_comparison OUTPUT_DIR. It is NumPy only, about a
minute.
"""

import dataclasses
import inspect
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
from cells.processes.electrochemistry import CHARGE_PER_FMOL, R
from tests import partition_fixtures as fx
from validation.division import partition_reference as rops

STATUS = "Development comparison for Q2 (S5a); not judged"
RANDOM_STATES = 200  # Draws per world and spread, seen and judged sets alike.
SPREADS = (0.1, 1.0, 3.0)  # Net-charge half-widths, in declared charges.
# The seen sets (the lead, 14 November): development evidence, drawn from a fresh generator per
# world and spread seeded SEEN_SEED (q2_domain_probe's draws). The judged sets' seeds are the
# protocol's alone (validation/division/s5_protocol.json), read by judge() behind its guard.
SEEN_SEED = 20261113
SEED = SEEN_SEED  # q2_domain_probe and q2_rounding_cause draw the seen sets.
CHARGE_BAND = 0.1  # The dropped net-charge band, |Q - Q_declared| <= 0.1 |Q_declared|: reported.
SPREAD = 0.1  # perturbed's default half-width (q2_domain_probe and q2_rounding_cause).
# The negative controls (frozen with the judged seeds, the lead, 14 November): defects 1e-16 to
# 1e-2 in a quarter-decade ladder; the statistic, the smallest defect whose ratio passes 64; the
# threshold, a target family caught at or below 1e-9.
DEFECTS = tuple(10.0 ** (k / 4) for k in range(-64, -7))
THRESHOLD = 1e-9
CONTROL_GROUPS = dict(
    charges=("charge_D1_C", "charge_D2_C"),
    potentials=("potentials_after_V",),
    image=("image_charge_C",),
    amounts=(
        "amounts_D1_fmol",
        "amounts_D2_fmol",
        "increment_D1_fmol",
        "increment_D2_fmol",
        "moved_fmol",
    ),
    work=("work_pJ",),
)
# {control: the families it must reach}. The engine exposes delta and the mismatch only through
# the increments and moved amounts that carry them, so the transference control reaches them
# there; an a_k defect moves charge but keeps each patch's voltage, so it cannot reach the
# potentials. The amendment (the lead, 14 November): W left f's targets. Delta G is stationary
# at the correct split (at delta = 0 the daughters' concentrations equal the parent's, so
# d dG / d delta = ln c_D1 - ln c_D2 = 0), so any map defect reaches W only at second order (W
# equals dG here, the bath held at 0 V); f's effect on W is reported. W takes its own
# first-order control (a booking defect in the free-energy volume), and the image charge its
# own (the mismatch charge scaled).
CONTROL_TARGETS = {
    "a_k": ("charges",),
    "parent charge": ("charges", "potentials"),
    "f": ("amounts",),
    "transference": ("amounts",),
    "W": ("work",),
    # The second amendment (the lead, 14 November): the delta-scaling control (formerly "image")
    # cannot reach the image charge, since a held node's plate charge is minus the total charge
    # facing it and the split conserves charge; the non-conservation control does.
    "mismatch scale": ("charges", "potentials"),
    "non-conservation": ("image", "charges", "amounts"),
}
CONTROL_PATCH = "membrane_0"
# The near-zero cases: the asymmetric world's admitted seen draws whose parent patch sits within
# NEAR_ZERO_V of 0 V before the event (a state-only rule, chosen after the seen states had been
# seen: a 1 mV rule kept two draws, 5 mV adds the spread-3 worst). (spread, draw index).
NEAR_ZERO_V = 5e-3
NEAR_ZERO = (
    (1.0, 35),
    (1.0, 45),
    (1.0, 77),
    (1.0, 111),
    (1.0, 143),
    (1.0, 149),
    (1.0, 171),
    (1.0, 180),
    (1.0, 191),
    (3.0, 32),
)
WORST_SEEN = (1.0, 35)  # The 860.6 draw (old scale), a member of NEAR_ZERO.
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

    def event(self, state, due, p=None):
        """The partition's event; with p, under that layout (an engine-side defect)."""
        op = self.partition[0]
        p = self.p if p is None else p
        new, ok = op.event(
            state, SimpleNamespace(partition_due=np.asarray(due, float)), p, xp=np,
            view=lambda s: self.model.view(p, s, xp=np),
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


def charge_term():
    """Whether R-ops carries A.8's increment-form term (its apply takes charge_term)."""
    return "charge_term" in inspect.signature(rops.apply).parameters


def scales():
    """The scales R-ops offers: the old (charge form) always; the new (A.8's increment-form
    term) once R-ops' amended magnitudes have landed."""
    return ("old", "new") if charge_term() else ("old",)


def apply(snapshot, division, scale):
    """R-ops' apply at one scale ("old": without A.8's term; "new": with it)."""
    if charge_term():
        return rops.apply(snapshot, division, charge_term=scale == "new")
    if scale != "old":
        raise SystemExit("R-ops' amended magnitudes (A.8's increment-form term) have not landed")
    return rops.apply(snapshot, division)


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


def perturbed(world, rng, *, spread=SPREAD):
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
    """(control domain, within CHARGE_BAND) of a random draw: the composite's control domain check
    with the control at time, which alone admits it (module docstring), and whether every live
    cell's net charge lies within the dropped band."""
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


def simultaneous(world, state, time, order, scale="old"):
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
        result = apply(snapshot, world.division(divisions[name], state), scale)
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


def random_worlds():
    carriers = {"Na": 0.3, "K": 0.5, "M": 0.2}
    return {
        "symmetric neighbour world": fx.divided(neighbour=True),
        "asymmetric neighbour world (f 0.75, a 0.6, three carriers)": fx.divided(
            neighbour=True, f=0.75, area_fraction=0.6, carriers=carriers
        ),
    }


def frozen_draws(world, spread, seed=SEEN_SEED):
    """RANDOM_STATES draws of perturbed at spread from a fresh generator seeded seed, and the
    draws the composite's control domain check admits (every one compared, none redrawn)."""
    rng = np.random.default_rng(seed)
    draws = [perturbed(world, rng, spread=spread) for _ in range(RANDOM_STATES)]
    return draws, [s for s in draws if admitted(world, s, fx.EVENT)[0]]


def random_case(world, d, spread, seed=SEEN_SEED, scale="old"):
    """Every admitted draw of one set against R-ops (module docstring)."""
    draws, kept = frozen_draws(world, spread, seed)
    worst, voltage, deviation, outside = {}, 0.0, 0.0, 0
    for state in kept:
        outside += not admitted(world, state, fx.EVENT)[1]
        voltage = max(voltage, float(np.max(np.abs(patch_voltages(world, state)))))
        q = world.view(state)
        cells = np.flatnonzero(np.asarray(q.active))
        net = np.asarray(q.initial_cell_charge_C)[cells] + CHARGE_PER_FMOL * (
            np.ravel(world.p.valence) @ np.asarray(state.amount_increment)[:, cells]
        )
        declared = np.asarray(world.p.initial_cell_charge_C)[cells]
        deviation = max(deviation, float(np.max(np.abs(net / declared - 1.0))))
        result = apply(world.snapshot(state), world.division(d, state), scale)
        after, ok = world.event(state, (1.0,))
        assert ok
        for key, value in compare(world, d, state, after, result).items():
            worst[key] = max(worst.get(key, 0.0), value)
    return dict(
        seed=seed,
        spread=spread,
        draws=len(draws),
        admitted=len(kept),
        outside_dropped_band=outside,
        max_abs_patch_voltage_V=voltage,
        max_net_charge_deviation=deviation,
        worst=max(worst.values()),
        worst_key=max(worst, key=worst.get),
        ratios=worst,
    )


ASYMMETRIC = "asymmetric neighbour world (f 0.75, a 0.6, three carriers)"


def near_zero_draws(world, seeds=None):
    """[(spread, index, state)]: the near-zero rule's members (module docstring). From the seen
    sets (seeds None) they are asserted equal to NEAR_ZERO and to hold WORST_SEEN; the rule
    applies unchanged to the judged sets (seeds {"spread s": seed})."""
    found = []
    k = world.patches.index(CONTROL_PATCH)
    for spread in SPREADS:
        seed = SEEN_SEED if seeds is None else seeds[f"spread {spread:g}"]
        draws, _ = frozen_draws(world, spread, seed)
        for index, state in enumerate(draws):
            if not admitted(world, state, fx.EVENT)[0]:
                continue
            q = world.view(state)
            phi = adapter.node_potentials(state, q, xp=np)
            node = len(world.cells) + int(world.p.membrane_outside[k])
            if abs(float(phi[world.cells.index("cell_0")] - phi[node])) <= NEAR_ZERO_V:
                found.append((spread, index, state))
    if seeds is None:
        assert tuple((s, i) for s, i, _ in found) == NEAR_ZERO, [(s, i) for s, i, _ in found]
        assert WORST_SEEN in NEAR_ZERO
    return found


def control_cases(seeds=None):
    """(label, world, pre-event state, due) of the negative controls (module docstring); the
    near-zero cases from the seen sets, or from the judged sets' seeds {world: {spread: seed}}."""
    world = Bound(random_worlds()[ASYMMETRIC])
    out = [("asymmetric neighbour world, bound state", world, world.state, (1.0,))]
    sets = "seen" if seeds is None else "judged"
    for spread, index, state in near_zero_draws(
        world, None if seeds is None else seeds[ASYMMETRIC]
    ):
        label = f"asymmetric neighbour world, {sets} spread {spread:g} draw {index}"
        out.append((label, world, state, (1.0,)))
    carriers = {"Na": 0.5, "K": 0.5}
    raw = fx.cleft_divided(f=0.75, area_fraction=0.6, carriers=carriers, bridge=("linear", 0.001))
    world = Bound(raw)
    out.append(("asymmetric furrow world (two patches a cell)", world, opened(world), (1.0,)))
    return out


def defects(division, snapshot, parent):
    """{control: delta -> (snapshot, division)}: each defect given to R-ops against the engine's
    own event (to first order, an engine defect of -delta)."""
    one, two, share = division.patches[CONTROL_PATCH]
    cell = snapshot.cells[parent]
    declared = abs(cell.charge_reference_C)  # The declared charge: no zero as Q_P nears 0.
    species = list(division.carriers)

    def a_k(x):
        changed = {**division.patches, CONTROL_PATCH: (one, two, share + x)}
        return snapshot, dataclasses.replace(division, patches=changed)

    def parent_charge(x):
        moved = dataclasses.replace(cell, charge_C=cell.charge_C + x * declared)
        return dataclasses.replace(snapshot, cells={**snapshot.cells, parent: moved}), division

    def f(x):
        return snapshot, dataclasses.replace(division, f=division.f + x)

    def transference(x):  # t_1 + x, t_2 - x: the sum stays 1.
        carriers = dict(division.carriers)
        carriers[species[0]] += x
        carriers[species[1]] -= x
        return snapshot, dataclasses.replace(division, carriers=carriers)

    return {
        "a_k": a_k,
        "parent charge": parent_charge,
        "f": f,
        "transference": transference,
    }


def booked_volume_defect(result, temperature_K, x):
    """R-ops' result with its daughters' free energy evaluated at V_D (1 + x): A.6's
    G(n, V) = 1e-3 RT sum n (ln(n / V) - 1) moves by -1e-3 RT N_D ln(1 + x) for each daughter,
    so W does (the usage note's formula; R-ops itself is not changed)."""
    v = result.values
    total = float(np.sum(v["amounts_D1_fmol"]) + np.sum(v["amounts_D2_fmol"]))
    moved = -1e-3 * R * temperature_K * np.log1p(x) * total
    values = {**v, "work_pJ": v["work_pJ"] + moved}
    return SimpleNamespace(values=values, magnitudes=result.magnitudes, snapshot=result.snapshot)


def event_checks(world, d, before, new):
    """(the held nodes' image charge, {check: passed}): the partition's event checks re-applied
    to a state after the event, as event_map applies them (its isopotential, outside-potential,
    plate-charge, positivity and finiteness checks, its constants and capacitor_state)."""
    p, n = world.p, len(world.cells)
    phi0, _, _, plates0, _ = partition.capacitor_state(before, world.view(before), xp=np)
    q1 = world.view(new)
    phi1, _, _, plates1, _ = partition.capacitor_state(new, q1, xp=np)
    scale = partition.POTENTIAL_RTOL * np.max(np.abs(phi0)) + partition.POTENTIAL_ATOL_V
    parent = world.cells.index(d.parent)
    kids = [world.cells.index(c) for c in d.daughters]
    outside = np.asarray(q1.outside_active) & ~np.asarray(p.reservoir)
    image = np.where(np.asarray(p.reservoir), plates1 - plates0, 0.0)
    bound = partition.PLATE_RTOL * np.abs(plates0) + partition.PLATE_ATOL_C
    amounts = np.asarray(p.amount_reference) + np.asarray(new.amount_increment)
    checks = dict(
        isopotential=all(bool(abs(phi1[k] - phi0[parent]) <= scale) for k in kids),
        outside_potentials=bool(
            np.all(np.where(outside, np.abs(phi1[n:] - phi0[n:]) <= scale, True))
        ),
        plate_charges=bool(np.all(np.abs(image) <= bound)),
        positive_amounts=bool(np.all(amounts[:, kids] > 0)),
        finite=all(bool(np.all(np.isfinite(np.asarray(v)))) for v in new),
    )
    return image, checks


def failed_checks(checks):
    return [name for name, passed in checks.items() if not passed]


def nonconserving_event(world, d, before, after, x):
    """(the engine's state after the event with D2 taking (1 + x) times the rest, event_checks
    on it): D2's increment and moved amount become (Delta_P - Delta_D1)(1 + x), and the image
    the held nodes book follows; the work bookings keep the engine's (module docstring)."""
    one, two = (world.cells.index(c) for c in d.daughters)
    parent = world.cells.index(d.parent)
    rest = (
        np.asarray(before.amount_increment)[:, parent] - np.asarray(after.amount_increment)[:, one]
    )
    increment = np.array(after.amount_increment, copy=True)
    increment[:, two] = rest * (1 + x)
    moved = np.array(after.partition_moved_fmol, copy=True)
    moved[:, two] = np.asarray(before.partition_moved_fmol)[:, two] + rest * (1 + x)
    new = after._replace(amount_increment=increment, partition_moved_fmol=moved)
    image, checks = event_checks(world, d, before, new)
    new = new._replace(
        electrode_charge_transferred_C=np.asarray(before.electrode_charge_transferred_C) + image,
        partition_image_charge_C=np.asarray(before.partition_image_charge_C) + np.abs(image),
    )
    return new, checks


def construction_checks(world, d, state, after):
    """The engine-side controls' construction against the engine's own event (module
    docstring): whether the non-conservation construction at delta = 0 reproduces the event in
    every field (and the fields that differ), event_checks on the event, and D2's net charge
    increment (C), the non-conservation defect's charge and image coefficient per unit delta."""
    zero, _ = nonconserving_event(world, d, state, after, 0.0)
    differing = [
        name
        for name in type(after)._fields
        if not np.array_equal(np.asarray(getattr(zero, name)), np.asarray(getattr(after, name)))
    ]
    _, checks = event_checks(world, d, state, after)
    two = world.cells.index(d.daughters[1])
    z = np.ravel(world.p.valence)
    second = np.asarray(after.amount_increment)[:, two]
    return dict(
        nonconservation_at_zero_reproduces_the_event=not differing,
        fields_differing_at_zero=differing,
        event_checks_on_the_event=checks,
        d2_net_charge_increment_C=float(CHARGE_PER_FMOL * np.sum(z * second)),
    )


def control_runs(world, d, state, due, after, base, division, snapshot, scale, log):
    """{control: delta -> (the engine's state after the event, R-ops' result)}. The four map
    defects and W's are given to R-ops against the engine's own event; the mismatch scale and
    non-conservation are the engine's (module docstring). Each engine-side run appends to log
    its delta, its validity, the event checks it fails and, for the mismatch scale, whether
    event_checks agrees with the event map (its verdict and its booked image)."""
    reference = defects(division, snapshot, d.parent)
    runs = {c: (lambda x, c=c: (after, apply(*reference[c](x), scale))) for c in reference}
    runs["W"] = lambda x: (after, booked_volume_defect(base, snapshot.temperature_K, x))

    def mismatch_scale(x):
        fraction = world.p.partition_carrier_fraction * (1 + x)
        new, valid = world.event(state, due, world.p._replace(partition_carrier_fraction=fraction))
        image, checks = event_checks(world, d, state, new)
        booked = np.asarray(state.electrode_charge_transferred_C) + image
        agrees = all(checks.values()) == valid and np.array_equal(
            booked, np.asarray(new.electrode_charge_transferred_C)
        )
        log.append(dict(delta=x, valid=valid, failing=failed_checks(checks), agrees=bool(agrees)))
        return new, base

    def nonconserving(x):
        new, checks = nonconserving_event(world, d, state, after, x)
        log.append(dict(delta=x, valid=all(checks.values()), failing=failed_checks(checks)))
        return new, base

    runs["mismatch scale"] = mismatch_scale
    runs["non-conservation"] = nonconserving
    return runs


def negative_controls(scale="old", seeds=None):
    """The negative controls at one scale (module docstring). Per case: the undefected ratios
    per family and the construction checks; per control, the smallest defect caught per family
    (None if none is, "baseline above 64" where the undefected case already fails) and whether
    every target family is caught at or below THRESHOLD; for the engine-side controls, the
    smallest delta the engine's own event checks refuse and the checks that refuse it."""
    out = {}
    for label, world, state, due in control_cases(seeds):
        d = next(x for x in world.partition[1].divisions if x.id == "first")
        division, snapshot = world.division(d, state), world.snapshot(state)
        after, ok = world.event(state, due)
        assert ok
        base = apply(snapshot, division, scale)
        baseline = compare(world, d, state, after, base)
        groups = {**CONTROL_GROUPS, "any key": tuple(baseline)}
        entry = dict(
            baseline={group: max(baseline[k] for k in keys) for group, keys in groups.items()},
            construction=construction_checks(world, d, state, after),
        )
        log = []
        runs = control_runs(world, d, state, due, after, base, division, snapshot, scale, log)
        for control, run in runs.items():
            log.clear()
            ladder = [(x, compare(world, d, state, *run(x))) for x in DEFECTS]
            caught = {
                group: "baseline above 64"
                if entry["baseline"][group] > 64
                else min((x for x, r in ladder if max(r[k] for k in keys) > 64), default=None)
                for group, keys in groups.items()
            }
            targets = {
                group: isinstance(caught[group], float) and caught[group] <= THRESHOLD
                for group in CONTROL_TARGETS[control]
            }
            refused = min(
                (e for e in log if not e["valid"]), key=lambda e: e["delta"], default=None
            )
            entry[control] = dict(
                smallest_defect_caught=caught,
                targets_caught_at_threshold=targets,
                engine_refuses_from=refused["delta"] if refused else None,
                ladder=[
                    dict(delta=x, worst=max(r.values()), worst_key=max(r, key=r.get))
                    | {group: max(r[k] for k in keys) for group, keys in CONTROL_GROUPS.items()}
                    for x, r in ladder
                ],
            )
            if log:
                entry[control]["refused_by"] = refused["failing"] if refused else []
            if any("agrees" in e for e in log):
                agree = all(e["agrees"] for e in log)
                entry[control]["event_checks_agree_with_the_event_map"] = agree
            print("control", scale, label, control, caught, flush=True)
        construction = entry["construction"]
        construction["faithful"] = (
            construction["nonconservation_at_zero_reproduces_the_event"]
            and all(construction["event_checks_on_the_event"].values())
            and entry["mismatch scale"]["event_checks_agree_with_the_event_map"]
        )
        out[label] = entry
    return out


def run_all(scale, seeds):
    """Every Q2 case at one scale, the random sets drawn from seeds {world: {spread: seed}}."""
    report = dict(cases={}, simultaneous={}, random={})
    for label, world, state, due, division_id in cases():
        d = next(x for x in world.partition[1].divisions if x.id == division_id)
        result = apply(world.snapshot(state), world.division(d, state), scale)
        after, ok = world.event(state, due)
        ratios = compare(world, d, state, after, result)
        report["cases"][label] = dict(engine_ok=ok, worst=max(ratios.values()), ratios=ratios)
        print(scale, label, ok, f"{max(ratios.values()):.2f}", flush=True)
    for label, world, state, time in simultaneous_cases():
        entry = {}
        for order in (("second_d1", "second_d2"), ("second_d2", "second_d1")):
            ratios = simultaneous(world, state, time, order, scale)
            entry[" then ".join(order)] = dict(worst=max(ratios.values()), ratios=ratios)
        report["simultaneous"][label] = entry
    for label, raw in random_worlds().items():
        world = Bound(raw)
        d = next(x for x in world.partition[1].divisions if x.id == "first")
        report["random"][label] = {
            f"spread {s:g}": random_case(world, d, s, seeds[label][f"spread {s:g}"], scale)
            for s in SPREADS
        }
    judged = seeds != seen_seeds()
    report["negative_controls"] = negative_controls(scale, seeds if judged else None)
    return report


def seen_seeds():
    return {w: {f"spread {s:g}": SEEN_SEED for s in SPREADS} for w in random_worlds()}


def main(output):
    """The development run: the seen sets, every case and control, at each scale R-ops offers."""
    jax.config.update("jax_enable_x64", True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status=STATUS, tolerance_eps=64, sets="seen", scales={})
    for scale in scales():
        report["scales"][scale] = run_all(scale, seen_seeds())
        (output / "q2_rops.json").write_text(json.dumps(report, indent=1) + "\n")
    return report


def verdict(report, item):
    """Q2's verdict at the new scale: every compared ratio of the cases, the simultaneous
    divisions and the judged sets within 64; every control's target families caught at or
    below THRESHOLD wherever the undefected case passes; each near-zero case passing
    undefected and failing with the parent-charge defect; and each case's engine-side
    construction faithful to the engine (construction_checks)."""
    new = report["scales"]["new"]
    worst = [v["worst"] for v in new["cases"].values()]
    worst += [e["worst"] for v in new["simultaneous"].values() for e in v.values()]
    worst += [e["worst"] for v in new["random"].values() for e in v.values()]
    comparisons = max(worst) <= 64
    controls = {}
    for label, entry in new["negative_controls"].items():
        near = " spread " in label  # A near-zero case, from the seen or the judged sets.
        for control in CONTROL_TARGETS:
            targets = entry[control]["targets_caught_at_threshold"]
            passed = all(targets.values()) and (not near or entry["baseline"]["any key"] <= 64)
            controls[f"{label}: {control}"] = passed
        controls[f"{label}: construction"] = entry["construction"]["faithful"]
    ok = comparisons and all(controls.values())
    return dict(
        largest_ratio=max(worst),
        comparisons_within_64=comparisons,
        controls=controls,
        threshold=item["negative_controls"]["threshold"],
        verdict="pass" if ok else "fail",
    )


def judge(output, protocol_path=None, root=None):
    """The judged run: refused first unless the S5 protocol is registered, the source a clean
    snapshot (s5_protocol.registered) and R-ops' amended magnitudes landed; then the judged sets
    (the protocol's seeds) and every case and control under both scales, with the verdict."""
    from validation.division import s5_protocol

    _, item = s5_protocol.registered(
        "Q2", protocol_path or s5_protocol.PROTOCOL, root or s5_protocol.ROOT
    )
    if "new" not in scales():
        raise SystemExit("Refused: R-ops' amended magnitudes (A.8) have not landed")
    seeds = item["frozen_draws"]["judged"]["seeds"]
    jax.config.update("jax_enable_x64", True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status="Judged run of Q2", sets="judged", scales={})
    for scale in ("old", "new"):
        report["scales"][scale] = run_all(scale, seeds)
    # The run first, then its verdict, computed on what was written (the JSON round trip).
    path = output / "q2_judged.json"
    path.write_text(json.dumps(report, indent=1) + "\n")
    report = json.loads(path.read_text())
    report["verdict"] = verdict(report, item)
    path.write_text(json.dumps(report, indent=1) + "\n")
    return report


if __name__ == "__main__":
    if sys.argv[1:2] == ["judge"]:
        judge(sys.argv[2])
    else:
        main(sys.argv[1])
