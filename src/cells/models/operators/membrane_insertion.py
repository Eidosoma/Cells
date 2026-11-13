"""Operator scheduled_membrane_insertion@1: membrane insertion at scheduled rates (stage S2).

docs/PUMP_COMPOSITE_V2_DESIGN.md §3; the law is docs/CELL_DIVISION_DESIGN.md §5.1. The name is
general: the cleavage furrow is one use (D144).

Law, per half-step h of the split part, on each inserted patch k with the rate r_k >= 0 of its
schedule: dA = r h, dC = c_d r h and dN_j = rho_j r h for each population j at the patch, with
c_d the inserted membrane's specific capacitance and rho_j its density of population j
(units/m^2). They are written to membrane_entity_state@1's increments (that operator must
precede this one) and booked in this operator's accumulators. The change is applied at fixed
free-node charges with the potentials re-solved (adapter.fixed_charge_change): the inserted
membrane arrives uncharged.
* Each held bath supplies its plate-charge change dq_b. It is booked in @3's electrode transfer,
  with the work W = phi_b dq_b in @3's electrode work and |dq_b| in insertion_image_charge_C.
* The capacitor free energy falls by H >= 0, booked as insertion heat
  (insertion_dissipated_energy_pJ, a declared heat field), so the capacitor energy obeys
  dU = W - H.
* The composite's capacitor energy is the physical 1/2 sum C V^2 - 1/2 sum C0 V0^2 through
  this operator's ledger terms (adapter.view_capacitor_terms), with the matching plate charges
  in @3's electrode ledger; @3's balances stay as they are, on the declared layout. This
  operator books the term as the only writer of capacitances and masks; a second writer
  (partition, S4) moves it to the composite.
A half-step with no rate selects its start state, so a zero schedule is bitwise idle.

Onset (event part). A patch declared with an onset time is inactive until then, together with
its outside node and that node's faces. The view masks them (membrane_active, outside_active,
face_active; the node's reference amounts read 0 while it is inactive), so the field arrays
follow the masks (R3). Activation needs the slot's anchors declared (division design §3.8):
the patch and the node are declared in @3's model at their onset values (area, capacitance,
volume, amounts), and the node is finite with a zero charge anchor, and every patch facing it
opens at the same time. The patch then opens at zero voltage, with the node following its cell,
so the onset moves no charge and changes no energy, and nothing is booked. The node's declared
content is its anchor (D057), already counted on the declared layout.

Refusals:
* a negative rate (retrieval: its heat would be negative, and the work would need a declared
  source); a rate on a patch outside its schedule (not inserted, or before its onset); a
  schedule that disagrees with the onset state (restart);
* an onset patch with channel populations or a pump, facing a held bath or a node with a
  nonzero charge anchor or with patches that open at another time, or whose node's volume an
  operator provides;
* another operator that books image charge on the declared layout (injection, replacement):
  those bookings would miss the changed capacitances;
* floating capacitor components, and more than 64 field nodes (the composite refuses both for
  any field-input provider).

Step checks (R5): @3's bounds on the definition with every inserted patch at its largest area
over the schedule and its declared (smallest) capacitance, and with onsets also on the
definition before any onset (onset patches, nodes and faces removed). Together these bound the
largest conductance over the smallest capacitance at every point of the schedule.
"""

from bisect import bisect_right
from dataclasses import dataclass, replace
from functools import cached_property

import jax.numpy as jnp
import numpy as np

from cells.core import pump_composite_spec as composite_spec
from cells.core import surface_pump_v3_spec as ionic_spec
from cells.core.bioelectric_spec import signed_number
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields, _number
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump as first
from cells.models.operators import membrane_state
from cells.models.operators.contract import Operator
from cells.numerics.extracellular_field import scatter

LAW_ID = "scheduled_membrane_insertion@1"
STEP_ID = "fixed_charge_exact_half_steps@1"

STATE_AXES = {
    "insertion_opened": ["membrane_slot"],  # int64: 1 once an onset patch has opened.
    "inserted_area_m2": ["membrane_slot"],
    "inserted_capacitance_F": ["membrane_slot"],
    "inserted_units": ["channel_slot"],
    "insertion_image_charge_C": ["extracellular_slot"],  # Sum of |dq_b| booked.
    "insertion_dissipated_energy_pJ": ["membrane_slot"],  # H.
    "insertion_energy_magnitude_pJ": ["membrane_slot"],  # Magnitudes of the bookings.
}
LAYOUT_FIELDS = (
    "insertion_patch",  # [membrane] bool: inserted patches.
    "insertion_specific_capacitance",  # [membrane] F/m^2.
    "insertion_density",  # [channel] units/m^2 of inserted membrane.
    "insertion_onset_patch",  # [membrane] bool.
    "insertion_onset_node",  # [outside] bool.
    "insertion_onset_face",  # [face] bool.
    "insertion_has_onset",  # shape (0,) or (1,): a static choice.
)


@dataclass(frozen=True)
class InsertedPatch:
    membrane_id: str
    specific_capacitance_F_per_m2: float
    densities: tuple  # ((channel id, units/m^2), ...)


@dataclass(frozen=True)
class Insertion:
    law: str
    patches: tuple


@dataclass(frozen=True)
class RateChange:
    time: float
    rate_m2_per_s: float


@dataclass(frozen=True)
class PatchSchedule:
    membrane_id: str
    onset_time: float | None
    changes: tuple


# ------------------------------------------------------------------ definition


def parse_insertion(raw, base):
    _fields(raw, {"law", "patches"}, "insertion")
    if raw["law"] != LAW_ID:
        raise ConfigError("Insertion requires law " + LAW_ID)
    if type(raw["patches"]) is not list or not raw["patches"]:
        raise ConfigError("Insertion declares its patches in a non-empty list")
    membranes = [p.id for p in base.model.membranes]
    at = {c.id: c.membrane_id for c in base.model.channels}
    patches = []
    for entry in raw["patches"]:
        _fields(
            entry,
            {"membrane_id", "specific_capacitance_F_per_m2", "population_densities_per_m2"},
            "inserted patch",
        )
        patch = identifier(entry["membrane_id"])
        if patch not in membranes:
            raise ConfigError(f"Insertion into an unknown membrane {patch!r}")
        cd = _number(entry["specific_capacitance_F_per_m2"], "specific capacitance", positive=True)
        densities = entry["population_densities_per_m2"]
        if type(densities) is not dict:
            raise ConfigError("Inserted population densities are an explicit object")
        rows = []
        for channel, value in densities.items():
            if at.get(channel) != patch:
                raise ConfigError(f"Inserted population {channel!r} is not at {patch!r}")
            rows.append((channel, _number(value, "inserted population density")))
        patches.append(InsertedPatch(patch, cd, tuple(rows)))
    if len({p.membrane_id for p in patches}) != len(patches):
        raise ConfigError("One insertion entry per patch")
    return Insertion(LAW_ID, tuple(patches))


def insertion_to_dict(declaration):
    if type(declaration) is not Insertion or any(
        type(p) is not InsertedPatch for p in declaration.patches
    ):
        raise ConfigError("Require explicit immutable insertion declaration types")
    return dict(
        law=declaration.law,
        patches=[
            dict(
                membrane_id=p.membrane_id,
                specific_capacitance_F_per_m2=p.specific_capacitance_F_per_m2,
                population_densities_per_m2=dict(p.densities),
            )
            for p in declaration.patches
        ],
    )


def parse_controls(raw, base, declaration):
    """One rate schedule per inserted patch, in declaration order (retrieval is refused)."""
    by_patch = {}
    end = base.experiment.end_time
    for entry in raw["insertion_controls"]:
        _fields(entry, {"membrane_id", "onset_time", "schedule"}, "insertion control")
        patch = entry["membrane_id"]
        if patch in by_patch:
            raise ConfigError("One insertion schedule per patch")
        onset = entry["onset_time"]
        if onset is not None:
            onset = _number(onset, "onset time")
        changes = []
        if type(entry["schedule"]) is not list:
            raise ConfigError("An insertion schedule is an explicit list")
        for c in entry["schedule"]:
            _fields(c, {"time", "rate_m2_per_s"}, "insertion rate change")
            rate = signed_number(c["rate_m2_per_s"], "insertion rate")
            if rate < 0:
                raise ConfigError("Membrane retrieval (a negative insertion rate) is refused")
            changes.append(RateChange(_number(c["time"], "time"), rate))
        times = [c.time for c in changes]
        if (
            not times
            or times[0] != 0.0
            or any(b <= a for a, b in zip(times, times[1:], strict=False))
        ):
            raise ConfigError("An insertion schedule starts at time 0 with increasing times")
        if times[-1] >= end:
            raise ConfigError("An insertion rate change lies at or beyond the end time")
        if onset is not None:
            if not 0 < onset < end:
                raise ConfigError("An onset lies inside the horizon")
            if any(c.rate_m2_per_s > 0 and c.time < onset for c in changes):
                raise ConfigError("An insertion rate lies outside its schedule (before its onset)")
        by_patch[patch] = PatchSchedule(patch, onset, tuple(changes))
    declared = [p.membrane_id for p in declaration.patches]
    if set(by_patch) != set(declared):
        raise ConfigError("Every inserted patch, and only those, has an insertion schedule")
    schedule = tuple(by_patch[k] for k in declared)
    check_onsets(base, schedule)
    return schedule


def check_onsets(base, schedule):
    """The onset rules on the inner definition (module docstring), before any domain check."""
    m = base.model
    patches, nodes, _ = onset_entities(base, schedule)
    onset = {s.membrane_id: s.onset_time for s in schedule}
    for c in m.channels:
        if c.membrane_id in patches:
            raise ConfigError("Channel populations on an onset patch are later work")
    for p in m.membranes:
        if p.id in patches and (p.pump is not None or p.calcium_pump is not None):
            raise ConfigError("Pumps on an onset patch are later work")
    for node in m.extracellular:
        if node.id not in nodes:
            continue
        if node.reservoir:
            raise ConfigError("An onset patch faces a finite node, not a held bath")
        if node.initial_charge_C != 0.0:
            raise ConfigError("An onset node's charge anchor must be 0")
        facing = [p.id for p in m.membranes if p.outside == node.id]
        if any(k not in patches for k in facing) or len({onset[k] for k in facing}) != 1:
            raise ConfigError("Every patch facing an onset node opens with it, at one time")


def controls_to_dict(schedule):
    if any(type(s) is not PatchSchedule for s in schedule):
        raise ConfigError("Require explicit immutable insertion schedule types")
    return dict(
        insertion_controls=[
            dict(
                membrane_id=s.membrane_id,
                onset_time=s.onset_time,
                schedule=[dict(time=c.time, rate_m2_per_s=c.rate_m2_per_s) for c in s.changes],
            )
            for s in schedule
        ]
    )


def rate_at(s, time):
    return s.changes[bisect_right([c.time for c in s.changes], time) - 1].rate_m2_per_s


def inserted_area(s, end):
    """The area a schedule inserts over [0, end] (m^2): its largest, since rates are >= 0."""
    times = [c.time for c in s.changes] + [end]
    return sum(
        c.rate_m2_per_s * (b - a) for c, a, b in zip(s.changes, times, times[1:], strict=False)
    )


def onset_entities(spec, schedule):
    """(onset patch ids, onset node ids, onset face ids) of a definition."""
    m = spec.model
    patches = {s.membrane_id for s in schedule if s.onset_time is not None}
    nodes = {p.outside for p in m.membranes if p.id in patches}
    faces = {f.id for f in m.faces if f.sender in nodes or f.receiver in nodes}
    return patches, nodes, faces


def bind(spec, declaration, schedule):
    m, x = spec.model, spec.execution
    nm, o, nf, nc = (
        x.membrane_capacity,
        x.extracellular_capacity,
        x.face_capacity,
        x.channel_capacity,
    )
    membranes = [p.id for p in m.membranes]
    channels = [c.id for c in m.channels]
    outside = [c.id for c in m.extracellular]
    faces = [f.id for f in m.faces]
    layout = dict(
        insertion_patch=np.zeros(nm, dtype=bool),
        insertion_specific_capacitance=np.zeros(nm),
        insertion_density=np.zeros(nc),
        insertion_onset_patch=np.zeros(nm, dtype=bool),
        insertion_onset_node=np.zeros(o, dtype=bool),
        insertion_onset_face=np.zeros(nf, dtype=bool),
    )
    for p in declaration.patches:
        k = membranes.index(p.membrane_id)
        layout["insertion_patch"][k] = True
        layout["insertion_specific_capacitance"][k] = p.specific_capacitance_F_per_m2
        for channel, rho in p.densities:
            layout["insertion_density"][channels.index(channel)] = rho
    patches, nodes, onset_faces = onset_entities(spec, schedule)
    for k in patches:
        layout["insertion_onset_patch"][membranes.index(k)] = True
    for k in nodes:
        layout["insertion_onset_node"][outside.index(k)] = True
    for k in onset_faces:
        layout["insertion_onset_face"][faces.index(k)] = True
    layout["insertion_has_onset"] = np.zeros(1 if patches else 0)
    sizes = dict(membrane_slot=nm, channel_slot=nc, extracellular_slot=o)
    state = {k: np.zeros([sizes[a] for a in axes]) for k, axes in STATE_AXES.items()}
    state["insertion_opened"] = np.zeros(nm, dtype=np.int64)
    return state, layout


def check_definition(spec, declaration, schedule, model):
    """The composition rules (the onset rules are checked when the schedule is parsed)."""
    for op in model.operators:
        if op.LAW_ID != LAW_ID and "electrode_charge_transferred_C" in op.ENTITY_WRITES:
            raise ConfigError(
                f"Insertion cannot run with {op.LAW_ID}, which books image charge on the "
                "declared layout (bookings at the view are later work)"
            )
    if onset_entities(spec, schedule)[0] and any(
        "extracellular_volume" in op.VIEW_FIELDS for op in model.operators
    ):
        raise ConfigError("An onset node's volume must be its declared anchor")


def pre_onset_spec(spec, schedule):
    """The channel-free inner definition before any onset (onset entities removed)."""
    base = ionic_spec.projection(composite_spec.projection(spec))
    patches, nodes, faces = onset_entities(spec, schedule)
    m = base.model
    model = replace(
        m,
        membranes=tuple(p for p in m.membranes if p.id not in patches),
        extracellular=tuple(c for c in m.extracellular if c.id not in nodes),
        faces=tuple(f for f in m.faces if f.id not in faces),
    )
    return replace(base, model=model)


class InsertionStepChecks:
    """The insertion's own bound: @3's explicit-rate bound before any onset (R5), evaluated
    at its first use and kept for every chunk of the clock."""

    def __init__(self, spec, schedule):
        self.spec, self.schedule = spec, schedule

    @cached_property
    def explicit_rate(self):
        return first.explicit_rate_bound(pre_onset_spec(self.spec, self.schedule))

    def __call__(self, steps):
        if self.spec.execution.solver == "rk4" or not onset_entities(self.spec, self.schedule)[0]:
            return
        if np.max(steps, initial=0) * self.explicit_rate > first.EXPLICIT_STEP_BOUND:
            raise ConfigError(
                "IMEX step exceeds the explicit-rate bound before the insertion onset"
            )


# ------------------------------------------------------------------ the law


def opened(state, p, *, xp):
    """[membrane] whether each patch is open: declared without onset, or opened at it."""
    return ~p.insertion_onset_patch | (state.insertion_opened > 0)


def masks(state, p, *, xp):
    """@3's activity masks with the onset entities closed until their onset (static: only for
    definitions with onsets)."""
    membrane = p.membrane_active & opened(state, p, xp=xp)
    facing = scatter(
        xp.where(membrane, 1.0, 0.0), xp.zeros(p.outside_active.size), (p.membrane_outside,), xp=xp
    )
    node = p.outside_active & (~p.insertion_onset_node | (facing > 0))
    face = p.face_active & (~p.insertion_onset_face | (node[p.face_sender] & node[p.face_receiver]))
    return dict(
        membrane_active=membrane,
        outside_active=node,
        face_active=face,
        extracellular_amount_reference=xp.where(node, p.extracellular_amount_reference, 0.0),
    )


def capacitor_view(state, p, *, xp):
    """(@3's layout with the current capacitances and masks, field arrays refreshed; the
    declared layout)."""
    bound = adapter.inner_layout(p)
    values = dict(membrane_capacitance=membrane_state.capacitance(state, p, xp=xp))
    if p.insertion_has_onset.shape[0]:
        values |= masks(state, p, xp=xp)
    return adapter.refresh_field(bound._replace(**values), bound, xp=xp), bound


def inserted(state, h, control, p, *, xp=jnp):
    """(state after h of insertion, valid) (module docstring)."""
    rate = control.insertion_rate_m2_s
    open_now = opened(state, p, xp=xp)
    valid = xp.all(xp.isfinite(rate)) & xp.all(rate >= 0)
    valid &= xp.all(xp.where(rate > 0, p.insertion_patch & open_now & p.membrane_active, True))
    area = xp.where(p.insertion_patch & open_now, rate * h, 0.0)
    dc = p.insertion_specific_capacitance * area
    units = xp.where(p.channel_active, p.insertion_density * area[p.channel_membranes], 0.0)
    q, bound = capacitor_view(state, p, xp=xp)
    _, image, heat, first_order, second, _, _ = adapter.fixed_charge_change(
        state, q, dc, bound, xp=xp
    )
    work = 1e12 * p.boundary_V * image
    moving = area > 0
    count = xp.maximum(xp.sum(moving), 1)
    spread = (xp.abs(second) + xp.sum(xp.abs(work))) / count
    valid &= xp.all(xp.isfinite(image)) & xp.all(xp.isfinite(heat)) & xp.all(heat >= 0)
    new = state._replace(
        membrane_area_increment_m2=state.membrane_area_increment_m2 + area,
        membrane_capacitance_increment_F=state.membrane_capacitance_increment_F + dc,
        population_abundance_increment=state.population_abundance_increment + units,
        inserted_area_m2=state.inserted_area_m2 + area,
        inserted_capacitance_F=state.inserted_capacitance_F + dc,
        inserted_units=state.inserted_units + units,
        electrode_charge_transferred_C=state.electrode_charge_transferred_C + image,
        electrode_work_pJ=state.electrode_work_pJ + work,
        insertion_image_charge_C=state.insertion_image_charge_C + xp.abs(image),
        insertion_dissipated_energy_pJ=state.insertion_dissipated_energy_pJ + heat,
        insertion_energy_magnitude_pJ=state.insertion_energy_magnitude_pJ
        + xp.where(moving, first_order + spread, 0.0),
    )
    flowing = xp.any(moving)  # No rate: select the start state (bitwise idle).
    return type(state)(*(xp.where(flowing, a, b) for a, b in zip(new, state, strict=True))), valid


def apply_onsets(state, control, p, *, xp=jnp):
    """(state after the onsets due at the step start, schedule consistency)."""
    due = p.insertion_onset_patch & (control.insertion_open > 0) & (state.insertion_opened == 0)
    stale = p.insertion_onset_patch & (control.insertion_open == 0) & (state.insertion_opened != 0)
    new = state._replace(insertion_opened=xp.where(due, 1, state.insertion_opened))
    return new, ~xp.any(stale)


def own_valid(state, p, *, xp):
    valid = xp.all((state.insertion_opened == 0) | (state.insertion_opened == 1))
    valid &= xp.all(xp.where(p.insertion_onset_patch, True, state.insertion_opened == 0))
    for name, mask in (
        ("inserted_area_m2", p.insertion_patch),
        ("inserted_capacitance_F", p.insertion_patch),
        ("inserted_units", p.channel_active),
        ("insertion_image_charge_C", p.reservoir),
        ("insertion_dissipated_energy_pJ", p.insertion_patch),
        ("insertion_energy_magnitude_pJ", p.insertion_patch),
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(value >= 0)
        valid &= xp.all(xp.where(mask, True, value == 0))
    return valid


class ScheduledMembraneInsertion(Operator):
    LAW_ID = LAW_ID
    STEP_ID = STEP_ID
    EVENT = True
    SPLIT = True
    RK4 = "split"
    STATE_AXES = STATE_AXES
    STATE_DTYPES = {"insertion_opened": np.int64}
    HEAT_FIELDS = ("insertion_dissipated_energy_pJ",)
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = ("insertion_rate_m2_s", "insertion_open")
    EXPERIMENT_KEYS = ("insertion_controls",)
    VIEW_FIELDS = (
        "membrane_active",
        "outside_active",
        "face_active",
        "extracellular_amount_reference",
    )
    VIEW_READS = ("membrane_capacitance",)
    ENTITY_WRITES = {
        "membrane_area_increment_m2": ("inserted_area_m2",),
        "membrane_capacitance_increment_F": ("inserted_capacitance_F",),
        "population_abundance_increment": ("inserted_units",),
        "electrode_charge_transferred_C": ("insertion_image_charge_C",),
        "electrode_work_pJ": ("insertion_dissipated_energy_pJ", "insertion_energy_magnitude_pJ"),
    }
    REQUIRES = (membrane_state.LAW_ID,)

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_insertion(raw, base)

    def to_dict(self, declaration, base):
        return insertion_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_controls(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return controls_to_dict(schedule)

    def schedule_times(self, schedule):
        """Rate changes after time 0 and onsets (the composite checks them as event times)."""
        times = {c.time for s in schedule for c in s.changes if c.time > 0}
        times |= {s.onset_time for s in schedule if s.onset_time is not None}
        return tuple(sorted(times))

    def value_at(self, schedule, time):
        return (
            tuple(rate_at(s, time) for s in schedule),
            tuple(float(s.onset_time is None or time >= s.onset_time) for s in schedule),
        )

    def control_values(self, spec, declaration, schedule, records, indices, times):
        membranes = [p.id for p in spec.model.membranes]
        slots = [membranes.index(s.membrane_id) for s in schedule]
        rates = np.zeros((len(records), spec.execution.membrane_capacity))
        opens = np.ones((len(records), spec.execution.membrane_capacity))
        for i, (r, o) in enumerate(records):
            rates[i, slots] = r
            opens[i, slots] = o
        return rates[indices], opens[indices]

    def check_definition(self, spec, declaration, schedule, model):
        check_definition(spec, declaration, schedule, model)

    def inner_check_spec(self, check_spec, spec, declaration, schedule):
        """The definition with every inserted patch at its largest area over the schedule and
        its declared capacitance, the smallest (R5)."""
        end = spec.experiment.end_time
        added = {s.membrane_id: inserted_area(s, end) for s in schedule}
        m = check_spec.model
        membranes = tuple(
            replace(p, area_m2=p.area_m2 + added[p.id]) if added.get(p.id) else p
            for p in m.membranes
        )
        return replace(check_spec, model=replace(m, membranes=membranes))

    def bind_check_steps(self, spec, declaration, schedule, model):
        return InsertionStepChecks(spec, schedule)

    def check_steps(self, spec, declaration, schedule, steps, controls, model):
        InsertionStepChecks(spec, schedule)(steps)

    def batch_signature(self, declaration):
        return (LAW_ID, tuple(p.membrane_id for p in declaration.patches))

    def working_size(self, spec):
        x = spec.execution
        return 8 * (x.capacity + x.extracellular_capacity) ** 2 + 16 * x.membrane_capacity

    def summary(self, spec, declaration, schedule, history):
        return {
            "insertion_law": LAW_ID,
            "insertion_step": STEP_ID,
            "insertion_patches": {
                p.membrane_id: dict(
                    specific_capacitance_F_per_m2=p.specific_capacitance_F_per_m2,
                    population_densities_per_m2=dict(p.densities),
                    onset_time=s.onset_time,
                )
                for p, s in zip(declaration.patches, schedule, strict=True)
            },
            "insertion_rk4": "exact half-steps around the inner RK4 step",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration, schedule)

    # ------------------------------------------------------------ step parts

    def view(self, state, p, q, *, xp):
        return masks(state, p, xp=xp) if p.insertion_has_onset.shape[0] else {}

    def event(self, state, control, p, *, xp):
        if not p.insertion_has_onset.shape[0]:
            return state, None
        return apply_onsets(state, control, p, xp=xp)

    def half_step(self, state, h, control, p, *, xp):
        return inserted(state, h, control, p, xp=xp)

    def control_valid(self, control, p, *, xp):
        rate, open_ = control.insertion_rate_m2_s, control.insertion_open
        return xp.all(xp.isfinite(rate)) & xp.all(rate >= 0) & xp.all((open_ == 0) | (open_ == 1))

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & own_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = own_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        view, bound = capacitor_view(row, p, xp=xp)
        energy, electrode, _, _ = adapter.view_capacitor_terms(row, view, bound, xp=xp)
        result["energy"] = result["energy"] + energy + xp.sum(row.insertion_dissipated_energy_pJ)
        result["electrode"] = result["electrode"] - electrode
        return result, {}

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """The booked image charge and the view's plate charges in the electrode bound, the
        image charge in the global-charge bound, and the booked and view energy terms in the
        energy bound; every term is zero without insertion, so the bounds are then @3's."""
        view, bound = capacitor_view(row, p, xp=xp)
        _, _, energy, electrode = adapter.view_capacitor_terms(row, view, bound, xp=xp)
        image = row.insertion_image_charge_C + electrode
        magnitudes[4] = image if magnitudes[4] is None else magnitudes[4] + image
        charge = xp.sum(row.insertion_image_charge_C)
        magnitudes[5] = charge if magnitudes[5] is None else magnitudes[5] + charge
        energy = energy + xp.sum(row.insertion_energy_magnitude_pJ)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    def external_ledger_terms(self, ledgers, row, p, *, xp):
        booked = dict(
            membrane_area_entity=row.inserted_area_m2,
            membrane_capacitance_entity=row.inserted_capacitance_F,
            population_abundance_entity=row.inserted_units,
        )
        return {k: v - booked[k] for k, v in ledgers.items()}

    def external_magnitude_terms(self, magnitudes, row, p, *, xp):
        booked = dict(
            membrane_area_entity=row.inserted_area_m2,
            membrane_capacitance_entity=row.inserted_capacitance_F,
            population_abundance_entity=row.inserted_units,
        )
        return {k: v + xp.abs(booked[k]) for k, v in magnitudes.items()}
