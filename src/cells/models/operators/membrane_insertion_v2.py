"""Operator scheduled_membrane_insertion@2: insertion@1's law, its onset a closer (stage S5).

docs/CELL_DIVISION_S5_DESIGN.md §5.1. The law is insertion@1's (membrane_insertion.py; division
design §5.1), whose functions are reused unmodified. Per half-step h on each inserted patch k
with rate r_k >= 0: dA = r h, dC = c_d r h and dN_j = rho_j r h, written to
membrane_entity_state@1's increments at fixed free-node charges. The clamps supply the image
charge, booked with its work, and the capacitor free energy falls by the heat H >= 0.

Changed from @1:
* The onset is a closer (§2), not a provider. Until its onset an onset patch is closed
  (membrane_active), and so is its node (outside_active) until any of its onset patches has
  opened. The adapter propagates the closure to the node's faces and pads the node (reference
  amounts 0). These closures combine with the partition's by conjunction.
* The fixed-charge change is computed at the composite's view, with every closer's masks
  (BOOKS_AT_VIEW). A pending daughter's patch is closed there.
* Rates only on live patches. They are refused at run time against the view's mask, and at the
  definition against the partition's schedule: while a patch's rate is positive, its cell must
  be live (born, not retired).
* The onset rule, generalised. Every onset patch facing a node opens with it, at one time, on
  a cell live then. Every other patch facing the node must be closed at that time: a partition
  daughter born later, or a cell already retired. So the zero-charge onset of @1 holds
  unchanged: the node opens with its one cell's patches, at zero voltage.
* Version 1 refuses an onset at a division's time.
* The energy rule at the view is the composite's (§5.3). This operator books its heat in the
  energy ledger and its image charge in the rounding bounds, not the view's capacitor terms.
* It precedes isopotential_partition@1: the partition's step-check share (R5) reads the area
  inserted on the parent.

Kept from @1:
* populations and pumps on onset patches are refused (decision 9: S5b);
* an onset node is finite, with a zero charge anchor;
* another operator that books image charge on the declared layout is refused;
* an onset node's volume is its declared anchor, unless its provider anchors it until the
  onset (ONSET_ANCHORED_VIEWS: restricted_cleft_lumen@2);
* the step checks (R5): every inserted patch at its largest area, and the definition before
  any onset (as built: with every patch facing an onset node removed, pending daughters'
  among them).
"""

from dataclasses import replace
from functools import cached_property

import numpy as np

from cells.core import pump_composite_spec as composite_spec
from cells.core import surface_pump_v3_spec as ionic_spec
from cells.core.specs import ConfigError
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump as first
from cells.models.operators import membrane_insertion as v1
from cells.models.operators import membrane_state, partition
from cells.models.operators.contract import Operator
from cells.numerics.extracellular_field import scatter

LAW_ID = "scheduled_membrane_insertion@2"
STEP_ID = v1.STEP_ID


# ------------------------------------------------------------------ definition


def check_onsets(base, schedule):
    """@1's onset rules on the inner definition, except that the patches facing an onset node
    are checked against the partition's schedule (check_definition)."""
    m = base.model
    patches, nodes, _ = v1.onset_entities(base, schedule)
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


def partition_schedule(spec):
    """(the partition's declaration, its events), or (None, ()) without a partition."""
    for op, declaration, schedule in composite_spec.entries(spec):
        if op.LAW_ID == partition.LAW_ID:
            return declaration, schedule
    return None, ()


def check_definition(spec, declaration, schedule, model):
    """@1's composition rules, then the onsets and the rates against the partition's schedule
    (module docstring)."""
    v1.check_definition(spec, declaration, schedule, model)
    divisions, events = partition_schedule(spec)
    laws = [d.law for d in spec.model.operators]
    if divisions is not None and laws.index(partition.LAW_ID) < laws.index(LAW_ID):
        raise ConfigError(
            f"{LAW_ID} precedes {partition.LAW_ID}: the partition's step-check share reads the "
            "inserted area"
        )

    def interval(cell):
        if divisions is None:
            return None, None
        return partition.living_interval(divisions, events, cell)

    m = spec.model
    membranes = {p.id: p for p in m.membranes}
    onset = {s.membrane_id: s.onset_time for s in schedule}
    patches, nodes, _ = v1.onset_entities(spec, schedule)
    division_times = {e.time for e in events}
    for k in sorted(patches):
        t = onset[k]
        if t in division_times:
            raise ConfigError("An onset at a division's time is later work")
        birth, retirement = interval(membranes[k].inside)
        if (birth is not None and birth >= t) or (retirement is not None and retirement <= t):
            raise ConfigError(f"Onset patch {k}: its cell is live at its onset")
    for node in sorted(nodes):
        facing = [p for p in m.membranes if p.outside == node]
        times = {onset[p.id] for p in facing if p.id in patches}
        if len(times) != 1:
            raise ConfigError("Every onset patch facing an onset node opens with it, at one time")
        (t,) = times
        for p in facing:
            if p.id in patches:
                continue
            birth, retirement = interval(p.inside)
            if not (
                (birth is not None and birth > t) or (retirement is not None and retirement <= t)
            ):
                raise ConfigError(
                    f"Patch {p.id} faces onset node {node}: it opens with the node at its onset, "
                    "or is closed then (a partition daughter born later)"
                )
    for s in schedule:
        birth, retirement = interval(membranes[s.membrane_id].inside)
        for i, c in enumerate(s.changes):
            stop = s.changes[i + 1].time if i + 1 < len(s.changes) else float("inf")
            dead = (birth is not None and c.time < birth) or (
                retirement is not None and stop > retirement
            )
            if c.rate_m2_per_s > 0 and dead:
                raise ConfigError(
                    f"An insertion rate on {s.membrane_id} outside its cell's living interval"
                )


def pre_onset_spec(spec, schedule):
    """The channel-free inner definition before any onset: @1's, with every patch facing an
    onset node removed (pending daughters' patches facing it among them, which @1 never had)."""
    base = ionic_spec.projection(composite_spec.projection(spec))
    _, nodes, faces = v1.onset_entities(spec, schedule)
    m = base.model
    model = replace(
        m,
        membranes=tuple(p for p in m.membranes if p.outside not in nodes),
        extracellular=tuple(c for c in m.extracellular if c.id not in nodes),
        faces=tuple(f for f in m.faces if f.id not in faces),
    )
    return replace(base, model=model)


class StepChecks(v1.InsertionStepChecks):
    """@1's bound before any onset (R5), on this law's pre-onset definition."""

    @cached_property
    def explicit_rate(self):
        return first.explicit_rate_bound(pre_onset_spec(self.spec, self.schedule))


# ------------------------------------------------------------------ the law


def closures(state, p, *, xp):
    """{membrane_active, outside_active}: an onset patch is open from its onset, and an onset
    node once any onset patch facing it has opened; everything else is open."""
    opened = p.insertion_onset_patch & (state.insertion_opened > 0)
    facing = scatter(
        xp.where(opened, 1.0, 0.0), xp.zeros(p.outside_active.size), (p.membrane_outside,), xp=xp
    )
    return dict(
        membrane_active=v1.opened(state, p, xp=xp),
        outside_active=~p.insertion_onset_node | (facing > 0),
    )


def inserted(state, h, control, p, view, *, xp):
    """(state after h of insertion at the composite's view, valid): @1's half-step (its
    operations, in its order) with the view in place of @1's own and its mask for liveness."""
    rate = control.insertion_rate_m2_s
    live = view.membrane_active
    valid = xp.all(xp.isfinite(rate)) & xp.all(rate >= 0)
    valid &= xp.all(xp.where(rate > 0, p.insertion_patch & live, True))
    area = xp.where(p.insertion_patch & live, rate * h, 0.0)
    dc = p.insertion_specific_capacitance * area
    units = xp.where(p.channel_active, p.insertion_density * area[p.channel_membranes], 0.0)
    bound = adapter.inner_layout(p)
    _, image, heat, first_order, second, _, _ = adapter.fixed_charge_change(
        state, view, dc, bound, xp=xp
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


class ScheduledMembraneInsertionV2(Operator):
    LAW_ID = LAW_ID
    STEP_ID = STEP_ID
    EVENT = True
    SPLIT = True
    RK4 = "split"
    BOOKS_AT_VIEW = True
    STATE_AXES = v1.STATE_AXES
    STATE_DTYPES = {"insertion_opened": np.int64}
    HEAT_FIELDS = ("insertion_dissipated_energy_pJ",)
    LAYOUT_FIELDS = v1.LAYOUT_FIELDS
    CONTROL_FIELDS = ("insertion_rate_m2_s", "insertion_open")
    EXPERIMENT_KEYS = ("insertion_controls",)
    CLOSES = ("membrane_active", "outside_active")
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
        return v1.parse_insertion(raw, base, law=LAW_ID)

    def to_dict(self, declaration, base):
        return v1.insertion_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return v1.parse_controls(raw, base, declaration, onsets=check_onsets)

    def schedule_to_dict(self, schedule, base, declaration):
        return v1.controls_to_dict(schedule)

    def schedule_times(self, schedule):
        return v1.ScheduledMembraneInsertion.schedule_times(self, schedule)

    def value_at(self, schedule, time):
        return v1.ScheduledMembraneInsertion.value_at(self, schedule, time)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        return v1.ScheduledMembraneInsertion.control_values(
            self, spec, declaration, schedule, records, indices, times
        )

    def check_definition(self, spec, declaration, schedule, model):
        check_definition(spec, declaration, schedule, model)

    def inner_check_spec(self, check_spec, spec, declaration, schedule):
        return v1.ScheduledMembraneInsertion.inner_check_spec(
            self, check_spec, spec, declaration, schedule
        )

    def bind_check_steps(self, spec, declaration, schedule, model):
        return StepChecks(spec, schedule)

    def check_steps(self, spec, declaration, schedule, steps, controls, model):
        StepChecks(spec, schedule)(steps)

    def batch_signature(self, declaration):
        return (LAW_ID, tuple(p.membrane_id for p in declaration.patches))

    def working_size(self, spec):
        return v1.ScheduledMembraneInsertion.working_size(self, spec)

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
            "insertion_onset": "a closer of its onset patches and nodes (S5 design §2)",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return v1.bind(spec, declaration, schedule)

    # ------------------------------------------------------------ step parts

    def closures(self, state, p, q, *, xp):
        return closures(state, p, xp=xp)

    def event(self, state, control, p, *, xp, view=None):
        return v1.apply_onsets(state, control, p, xp=xp)

    def half_step(self, state, h, control, p, *, xp, view=None):
        if view is None:
            raise ConfigError("Insertion@2 books at the composite's view")
        return inserted(state, h, control, p, view, xp=xp)

    def control_valid(self, control, p, *, xp):
        rate, open_ = control.insertion_rate_m2_s, control.insertion_open
        return xp.all(xp.isfinite(rate)) & xp.all(rate >= 0) & xp.all((open_ == 0) | (open_ == 1))

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & v1.own_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = v1.own_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        """The heat in the energy ledger; the view's capacitor terms are the composite's."""
        result["energy"] = result["energy"] + xp.sum(row.insertion_dissipated_energy_pJ)
        return result, {}

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """The booked image charge in the electrode and global-charge bounds and the booked
        energy terms in the energy bound (the view's terms are the composite's): every term is
        zero without insertion."""
        image = row.insertion_image_charge_C
        magnitudes[4] = image if magnitudes[4] is None else magnitudes[4] + image
        charge = xp.sum(image)
        magnitudes[5] = charge if magnitudes[5] is None else magnitudes[5] + charge
        energy = xp.sum(row.insertion_energy_magnitude_pJ)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    def external_ledger_terms(self, ledgers, row, p, *, xp):
        return v1.ScheduledMembraneInsertion.external_ledger_terms(self, ledgers, row, p, xp=xp)

    def external_magnitude_terms(self, magnitudes, row, p, *, xp):
        return v1.ScheduledMembraneInsertion.external_magnitude_terms(
            self, magnitudes, row, p, xp=xp
        )
