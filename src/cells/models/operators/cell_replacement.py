"""Operator scheduled_cell_replacement@1: scheduled carrier replacement with junction formation.

The operation, the junction formation law delayed_first_order_junction_formation@1
and their ledgers are those of resolved_pump_replacement@1
(models/cell_replacement.py, docs/CELL_REPLACEMENT.md, D139), called, never
copied.

Contract (models/operators/contract.py):
* owned state: generation and occupant template per slot (int64), the formation
  law's lag and deficit per junction, the removal, supply, charge, free-energy and
  image-charge ledgers;
* entity writes: the replaced slots' amounts (booked as removal and supply, and
  their net charge), the held baths' plate charge and its work (booked in @3's
  electrode accumulators, with the image-charge magnitude); resets of the slots'
  channel gates and of the incident junction gates, which are intensive kinetic
  state without a ledger;
* view: each slot's occupant route values as @3's channel permeability and
  abundance, leak permeability and pump capacities; a factor on @3's junction
  availability, the junction abundance A (a product with any other factor);
* parts: an event map (the replacements due at the start of the step leaving an
  event time; two events on one slot at one time are refused at the definition)
  and a split process (the exact formation update over dt/2), kept split under an
  RK4 inner step;
* refusal: a schedule disagreement refuses the step; templates are checked
  against the declared slot volume, so no other operator may provide a volume;
  replaced slots need a held bath in their capacitor component.
"""

from dataclasses import replace

import numpy as np

from cells.core import cell_replacement_spec as replacement_spec
from cells.core import surface_pump_v3_spec as ionic_spec
from cells.core.specs import ConfigError, _fields, _integer
from cells.models import cell_replacement as rep
from cells.models.operators.contract import Operator
from cells.processes import junction_formation as formation
from cells.processes.electrochemistry import CHARGE_PER_FMOL

LAW_ID = replacement_spec.OPERATION_LAW_ID


def frozen_spec(spec, declaration, events):
    """The resolved_pump_replacement@1 definition of this operator on the inner model."""
    m, e = spec.model, spec.experiment
    model = replacement_spec.CellReplacementModel(
        **{k: getattr(m, k) for k in ionic_spec.SurfacePumpChannelModel.__dataclass_fields__},
        replacement=declaration,
    )
    experiment = replacement_spec.Experiment(
        **{k: getattr(e, k) for k in ionic_spec.Experiment.__dataclass_fields__},
        replacement_events=events,
    )
    return replace(spec, model=model, experiment=experiment)


class ScheduledReplacement(Operator):
    LAW_ID = LAW_ID
    STEP_ID = formation.LAW_ID
    EVENT = True
    SPLIT = True
    RK4 = "split"
    STATE_AXES = rep.REPLACEMENT_STATE_AXES
    STATE_DTYPES = {k: np.int64 for k in rep.INTEGER_FIELDS}
    LAYOUT_FIELDS = rep.REPLACEMENT_LAYOUT_FIELDS
    CONTROL_FIELDS = ("generation", "template", "donor")
    EXPERIMENT_KEYS = ("replacement_events",)
    VIEW_FIELDS = (
        "channel_permeability",
        "channel_abundance",
        "membrane_permeability",
        "pump_capacity",
        "calcium_pump_capacity",
    )
    CONTROL_FACTORS = ("junction",)
    CONFLICTS_VIEW = ("volume", "extracellular_volume")
    ENTITY_WRITES = {
        "amount_increment": (
            "replacement_removed_fmol",
            "replacement_supplied_fmol",
            "replacement_charge_C",
        ),
        "electrode_charge_transferred_C": ("replacement_image_charge_C",),
        "electrode_work_pJ": ("replacement_free_energy_pJ", "replacement_energy_magnitude_pJ"),
    }
    STATE_RESETS = ("channel_gate", "junction_gate")
    READOUT_COLUMNS = rep.REPLACEMENT_READOUTS

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        _fields(raw, {"law", "junction_formation", "templates", "template_capacity"}, "replacement")
        if raw["law"] != LAW_ID:
            raise ConfigError("Replacement requires law " + LAW_ID)
        if type(raw["templates"]) is not list:
            raise ConfigError("Replacement templates require an explicit list")
        templates = tuple(replacement_spec.parse_template(t, base) for t in raw["templates"])
        if len({t.id for t in templates}) != len(templates):
            raise ConfigError("Template IDs must be unique")
        capacity = _integer(
            raw["template_capacity"], "template_capacity", minimum=max(1, len(templates))
        )
        return replacement_spec.Replacement(
            LAW_ID,
            inner_model,
            replacement_spec.parse_formation(raw["junction_formation"]),
            templates,
            capacity,
        )

    def to_dict(self, declaration, base):
        r = declaration
        if (
            type(r) is not replacement_spec.Replacement
            or type(r.junction_formation) is not replacement_spec.JunctionFormation
            or any(type(t) is not replacement_spec.Template for t in r.templates)
        ):
            raise ConfigError("Require explicit immutable replacement declaration types")
        f = r.junction_formation
        return dict(
            law=r.law,
            junction_formation=dict(
                law=f.law,
                initial_abundance=f.initial_abundance,
                lag_s=f.lag_s,
                time_constant_s=f.time_constant_s,
                gate_at_arrival=f.gate_at_arrival,
            ),
            templates=[
                replacement_spec.template_to_dict(t, base.model.species_ids) for t in r.templates
            ],
            template_capacity=r.template_capacity,
        )

    def parse_schedule(self, raw, base, declaration):
        return replacement_spec.parse_events(raw["replacement_events"], base, declaration.templates)

    def schedule_to_dict(self, schedule, base, declaration):
        if any(type(v) is not replacement_spec.ReplacementEvent for v in schedule):
            raise ConfigError("Require explicit immutable replacement event types")
        return dict(
            replacement_events=[
                dict(
                    time=v.time,
                    slot=v.slot,
                    newcomer=v.newcomer,
                    template=v.template,
                    donor=v.donor,
                    carrier_id=v.carrier_id,
                )
                for v in schedule
            ]
        )

    def schedule_times(self, schedule):
        return tuple(v.time for v in schedule)

    def value_at(self, schedule, time):
        return tuple(v for v in schedule if v.time == time)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        controls = replacement_spec.control_values(frozen_spec(spec, declaration, schedule), times)
        return controls.generation, controls.template, controls.donor

    def check_definition(self, spec, declaration, schedule, model):
        """resolved_pump_replacement@1's checks: held-bath slots, each template in the domain."""
        rep.check_definition(frozen_spec(spec, declaration, schedule))

    def inner_check_spec(self, check_spec, spec, declaration, schedule):
        """@3's step checks on the worst-case inner definition, every occupant included."""
        return rep.worst_case(frozen_spec(spec, declaration, schedule))

    def batch_signature(self, declaration):
        f = declaration.junction_formation
        return (declaration.law, f.law, f.gate_at_arrival, declaration.template_capacity)

    def working_size(self, spec):
        x, s = spec.execution, len(spec.model.species_ids)
        return 2 * ((2 * s + 5) * x.capacity + 2 * x.edge_capacity)

    def summary(self, spec, declaration, schedule, history):
        f = declaration.junction_formation
        generation = None
        if hasattr(history, "generation") and len(np.asarray(history.generation)):
            generation = np.asarray(history.generation)[-1]
        return {
            "replacement_law": LAW_ID,
            "junction_formation": dict(
                law=f.law,
                initial_abundance=f.initial_abundance,
                lag_s=f.lag_s,
                time_constant_s=f.time_constant_s,
                gate_at_arrival=f.gate_at_arrival,
            ),
            "replacement_events_declared": len(schedule),
            "lineage": replacement_spec.lineage(
                frozen_spec(spec, declaration, schedule), generation
            ),
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        state, p = rep.initial_values(frozen_spec(spec, declaration, schedule))
        return (
            {k: getattr(state, k) for k in self.STATE_AXES},
            {k: getattr(p, k) for k in self.LAYOUT_FIELDS},
        )

    # ------------------------------------------------------------ step parts

    def view(self, state, p, q, *, xp):
        occupant = rep.ionic_layout(p, state, xp=xp)
        return {k: getattr(occupant, k) for k in self.VIEW_FIELDS}

    def control_factors(self, state, p, *, xp):
        return dict(junction=rep.abundance(state))

    def event(self, state, control, p, *, xp):
        return rep.apply_events(state, control, p, xp=xp)

    def half_step(self, state, h, control, p, *, xp):
        lag, deficit = formation.advance(
            state.junction_lag_remaining_s,
            state.junction_abundance_deficit,
            h,
            rep.formation_parameters(p),
            xp=xp,
        )
        return state._replace(
            junction_lag_remaining_s=lag, junction_abundance_deficit=deficit
        ), None

    def rates(self, state, control, p, view, *, xp):
        lag, deficit = rep.formation_rates(state, p, xp=xp)
        rates = {k: xp.zeros_like(getattr(state, k)) for k in self.STATE_AXES}
        rates.update(junction_lag_remaining_s=lag, junction_abundance_deficit=deficit)
        return rates, rep.replacement_domain_valid(state, p, xp=xp), None, None

    def domain_valid(self, state, p, *, xp):
        return rep.replacement_domain_valid(state, p, xp=xp)

    # ------------------------------------------------------------ ledgers

    def balance_terms(self, result, row, p, *, xp):
        return rep._terms(result, row, xp=xp)

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """resolved_pump_replacement@1's rounding terms (models/cell_replacement.magnitudes)."""
        moved = row.replacement_removed_fmol + row.replacement_supplied_fmol
        magnitudes[0] = magnitudes[0] + moved
        magnitudes[2] = magnitudes[2] + xp.sum(moved, axis=1)
        charge = CHARGE_PER_FMOL * xp.sum(xp.abs(p.valence) * moved)
        magnitudes[5] = charge if magnitudes[5] is None else magnitudes[5] + charge
        held = xp.where(p.reservoir, rep.replaced_charge_magnitude(row, p, xp=xp), 0.0)
        image = row.replacement_image_charge_C + held
        magnitudes[4] = image if magnitudes[4] is None else magnitudes[4] + image
        energy = xp.sum(row.replacement_energy_magnitude_pJ)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        columns = {k: getattr(state, k) for k in self.STATE_AXES}
        columns["junction_abundance"] = np.asarray(rep.abundance(state))
        return columns
