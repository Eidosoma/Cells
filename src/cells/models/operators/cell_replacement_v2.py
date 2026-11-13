"""Operator scheduled_cell_replacement@2: scheduled carrier replacement over water.

docs/PUMP_COMPOSITE_V2_DESIGN.md §2. This is scheduled_cell_replacement@1
(models/operators/cell_replacement.py, unchanged) over a volume owner,
ideal_osmosis_linear_compliance_water@1, which must precede it: the same event map,
formation law, templates, donor rule, route values and bookings, plus the slot's volume and
water's free energy. It writes none of @1's fields.

Event map, per due slot c at the start of the step leaving t_e, with V0 the slot's declared
volume and dv its volume increment:
1. @1's event map, called unchanged: amounts, gates, junction restarts, generation, the
   image charge and its work, and @3's free-energy change. Nothing in it depends on the
   current volume (capacitor_change reads no volume, and @3's chemical term is on V0).
2. The volume. V_old = V0 + dv is water's view. The newcomer's increment dv' is V_t - V0 for
   a template (its declared volume is its arrival volume) or the donor's increment for a
   donor copy, read before any event at t_e as @1 reads the donor's amounts. Then
   volume_increment_pL[c] <- dv', replacement_volume_removed_pL[c] += V_old and
   replacement_volume_supplied_pL[c] += V0 + dv'. Water accepts the write (ACCEPTS_WRITES),
   and these terms close its local and total ledgers.
3. Water's free energy. replacement_water_free_energy_pJ[c] += W_c(after) - W_c(before),
   with W water's endpoint term per node (osmotic_water.node_free_energy_pJ: the dilution
   -RT N_tot log(V/V0) and the elastic energy), and |W_c(before)| + |W_c(after)| in
   replacement_water_energy_magnitude_pJ.
4. The impermeant content. For a donor copy, the copied amount of each declared impermeant
   species must equal the slot's declared amount exactly; otherwise the step is refused.
The ideal chemical free energy splits exactly into @3's term on V0 and water's dilution, with
no cross term, so the event books the change of the slot's free energy, elastic energy
included, less the clamps' work: @3's part in @1's field, water's in @2's.

Contract (models/operators/contract.py), beyond @1's:
* requires water before it, and reads the volume view through water's function;
* owned state: removed and supplied volumes, water's free-energy change and its magnitudes;
* entity writes: water's cell volume increments, replaced at events (EVENT_REPLACES);
* refused: providers of the area (template pump densities are scaled by the declared area,
  as in @1) and of the capacitances and masks that @1's event map reads from the declared
  layout (CONFLICTS_VIEW); law_steady arrival gates, whose field solve would read the
  declared volumes (decision 11); RK4, since water's coupled part refuses event maps;
* definition checks: a template's volume strictly inside the slot's water bounds; a donor
  copy's water compartment equal to the slot's; the declared impermeant species without a
  route at the replaced slots and donors, and with equal declared amounts across slots,
  donors and templates (so every copy brings the slot's declared content);
* step checks (v2 design R5): @3's explicit-rate and calcium bounds on @1's worst-case
  template routes at water's minimum volumes, and water's relaxation rate at each template's
  post-event state.
"""

from dataclasses import dataclass, replace
from functools import cached_property

import jax.numpy as jnp
import numpy as np

from cells.core import cell_replacement_spec as replacement_spec
from cells.core import pump_composite_spec as composite_spec
from cells.core import surface_pump_v3_spec as ionic_spec
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields
from cells.models import surface_pump as first
from cells.models import surface_pump_v2 as second
from cells.models.operators import cell_replacement as replacement
from cells.models.operators import osmotic_water as water

LAW_ID = "scheduled_cell_replacement@2"

VOLUME_STATE_AXES = {
    "replacement_volume_removed_pL": ["cell_slot"],  # Occupants' volumes at their removal.
    "replacement_volume_supplied_pL": ["cell_slot"],  # Newcomers' volumes on arrival.
    "replacement_water_free_energy_pJ": ["cell_slot"],  # Change of water's free-energy term.
    "replacement_water_energy_magnitude_pJ": ["cell_slot"],  # Its magnitudes (rounding).
}
STATE_AXES = {**replacement.REPLACEMENT_STATE_AXES, **VOLUME_STATE_AXES}
LAYOUT_FIELDS = (
    *replacement.REPLACEMENT_LAYOUT_FIELDS,
    "template_volume_pL",  # [rows]: each template's declared (arrival) volume; padding 1.0.
    "replacement_impermeant",  # [species] bool: the declared impermeant species.
)
# Every view field @1's event map reads from the declared layout, besides the area: its image
# charge and capacitor energy are booked on the declared capacitances and masks.
DECLARED_LAYOUT_VIEWS = (
    "membrane_area",
    "membrane_capacitance",
    "active",
    "outside_active",
    "membrane_active",
    "channel_active",
    "junction_active",
)


@dataclass(frozen=True)
class ReplacementOverWater(replacement_spec.Replacement):
    impermeant_species: tuple = ()  # Species IDs whose content newcomers keep from the slot.


# ------------------------------------------------------------------ the event map


def event_map(state, due, control, p, *, xp=jnp):
    """@1's event map, then the slot's volume and water's free energy (module docstring)."""
    n = p.active.size
    new = replacement.event_map(state, due, control, p, xp=xp)
    copy = control.donor > 0
    donor = xp.maximum(control.donor - 1, 0)
    row = xp.maximum(control.template - 1, 0)
    dv = state.volume_increment_pL
    arrival = xp.where(copy, dv[donor], p.template_volume_pL[row] - p.volume)
    before = water.volumes(state, p, xp=xp)[:n]  # Water's view, read through its function.
    removed, supplied = state.replacement_volume_removed_pL, state.replacement_volume_supplied_pL
    new = new._replace(
        volume_increment_pL=xp.where(due, arrival, dv),
        replacement_volume_removed_pL=xp.where(due, removed + before, removed),
        replacement_volume_supplied_pL=xp.where(due, supplied + (p.volume + arrival), supplied),
    )
    w0 = water.node_free_energy_pJ(state, p, xp=xp)[:n]
    w1 = water.node_free_energy_pJ(new, p, xp=xp)[:n]
    energy = state.replacement_water_free_energy_pJ
    magnitude = state.replacement_water_energy_magnitude_pJ
    return new._replace(
        replacement_water_free_energy_pJ=xp.where(due, energy + (w1 - w0), energy),
        replacement_water_energy_magnitude_pJ=xp.where(
            due, magnitude + (xp.abs(w0) + xp.abs(w1)), magnitude
        ),
    )


def impermeant_valid(state, due, control, p, *, xp=jnp):
    """Each donor copy's amount of every declared impermeant species is the slot's declared
    amount, exactly (step 4 of the module docstring)."""
    copy = due & (control.donor > 0)
    donor = xp.maximum(control.donor - 1, 0)
    copied = p.amount_reference[:, donor] + state.amount_increment[:, donor]
    checked = p.replacement_impermeant[:, None] & copy[None, :]
    return xp.all(xp.where(checked, copied == p.amount_reference, True))


def apply_events(state, control, p, *, xp=jnp):
    """(state after the due replacements, schedule consistency and impermeant content)."""
    new, ok = replacement.apply_events(state, control, p, xp=xp, event=event_map)
    due = p.active & (control.generation == state.generation + 1)
    return new, ok & impermeant_valid(state, due, control, p, xp=xp)


def own_valid(state, p, *, xp=jnp):
    """@1's replacement fields, then the volume and water free-energy fields (zero for
    founders; volumes and magnitudes nonnegative)."""
    valid = replacement.replacement_domain_valid(state, p, xp=xp)
    fresh = state.generation == 0
    for name in (
        "replacement_volume_removed_pL",
        "replacement_volume_supplied_pL",
        "replacement_water_energy_magnitude_pJ",
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(value >= 0)
        valid &= xp.all(xp.where(fresh, value == 0, True))
    value = state.replacement_water_free_energy_pJ
    return valid & xp.all(xp.isfinite(value)) & xp.all(xp.where(fresh, value == 0, True))


# ------------------------------------------------------------------ binding and checks


def bind(spec, declaration, events):
    """@1's state and layout, the volume fields (zero) and the template volumes."""
    state, layout = replacement.bind(spec, declaration, events)
    n = spec.execution.capacity
    state |= {k: np.zeros(n) for k in VOLUME_STATE_AXES}
    volumes = np.ones(declaration.template_capacity)  # Route-only rows and padding keep 1.0.
    for k, t in enumerate(declaration.templates):
        if t.volume_pL is not None:
            volumes[k] = t.volume_pL
    species = list(spec.model.species_ids)
    impermeant = np.array([s in declaration.impermeant_species for s in species], dtype=bool)
    return state, layout | dict(template_volume_pL=volumes, replacement_impermeant=impermeant)


def water_of(spec):
    """The volume owner's declaration (REQUIRES puts water before this operator)."""
    for op, declaration, _ in composite_spec.entries(spec):
        if op.LAW_ID == water.LAW_ID:
            return declaration
    raise ConfigError(f"{LAW_ID} requires {water.LAW_ID} before it")


def check_volumes(declaration, events, volumes):
    """Templates arrive inside the slot's water bounds; a donor's compartment is the slot's."""
    rows = {c.compartment_id: c for c in volumes.compartments}
    names = {t.id: t for t in declaration.templates}
    for v in events:
        if v.slot not in rows:
            raise ConfigError(f"Replacement slot {v.slot} has no water compartment")
        slot = rows[v.slot]
        if v.donor is None:
            t = names[v.template]
            if not slot.minimum_volume_pL < t.volume_pL < slot.maximum_volume_pL:
                raise ConfigError(
                    f"Template {t.id} volume {t.volume_pL!r} pL lies outside water's bounds at "
                    f"{v.slot} ({slot.minimum_volume_pL!r}, {slot.maximum_volume_pL!r})"
                )
        elif v.donor not in rows or replace(rows[v.donor], compartment_id=v.slot) != slot:
            raise ConfigError(
                f"Donor {v.donor} water compartment differs from {v.slot}'s: a donor copy takes "
                "the donor's volume, so their compartments must be equal"
            )


def check_impermeants(spec, declaration, events, model):
    """The declared impermeant species: no route at the replaced slots and donors, and equal
    declared amounts across slots, donors and templates (v2 design §2.2)."""
    if not declaration.impermeant_species:
        return
    from cells.models.pump_composite import compact

    small = compact(spec)
    _, p = model.initial_values(small)
    order = {c.id: i for i, c in enumerate(small.model.cells)}
    names = {t.id: t for t in declaration.templates}
    touched = np.zeros(p.active.size, dtype=bool)
    for v in events:
        touched[order[v.slot]] = True
        if v.donor is not None:
            touched[order[v.donor]] = True
    cell = np.asarray(p.membrane_cell)
    patch = cell[np.asarray(p.channel_membranes)]
    junction = touched[np.asarray(p.junction_sender)] | touched[np.asarray(p.junction_receiver)]
    species = list(small.model.species_ids)
    membrane = np.asarray(p.membrane_active) & touched[cell]
    channel = np.asarray(p.channel_active) & touched[patch]
    junction &= np.asarray(p.junction_active)
    pump = np.asarray(p.pump_present) & touched[cell]
    calcium = np.asarray(p.calcium_pump_present) & touched[cell]
    for s in declaration.impermeant_species:
        i = species.index(s)
        routes = (
            membrane & (p.membrane_permeability[i] > 0),
            junction & (p.junction_permeability[i] > 0),
            channel & (p.channel_relative_permeability[i] > 0),
            pump & (p.stoichiometry[i] != 0),
            calcium & (p.calcium_stoichiometry[i] != 0),
        )
        if any(np.any(r) for r in routes):
            raise ConfigError(
                f"Impermeant species {s} has a route at a replaced slot or donor, so its amount "
                "is not the declared one at an event"
            )
        reference = np.asarray(p.amount_reference)[i]
        for v in events:
            c = order[v.slot]
            if v.donor is not None and reference[order[v.donor]] != reference[c]:
                raise ConfigError(
                    f"Donor {v.donor} declares another {s} content than {v.slot}: a newcomer "
                    "keeps the slot's declared impermeant content"
                )
            t = names.get(v.template)
            if t is not None and t.amounts_fmol is not None and t.amounts_fmol[i] != reference[c]:
                raise ConfigError(
                    f"Template {t.id} declares another {s} content than {v.slot}: a newcomer "
                    "keeps the slot's declared impermeant content"
                )


def newcomer_states(spec, declaration, events, model):
    """(event, state after it, layout) for each template's first event, applied to the compact
    initial state on the host (as @1's definition check applies it)."""
    from cells.models.pump_composite import compact

    small = compact(spec)
    state, p = model.initial_values(small)
    order = {c.id: i for i, c in enumerate(small.model.cells)}
    rows = {t.id: k + 1 for k, t in enumerate(declaration.templates)}
    controls = composite_spec.control_values(small, [0.0])
    base = model.CONTROL_TYPE(*(np.asarray(v[0]) for v in controls))
    seen = set()
    for v in events:
        if v.donor is not None or v.template in seen:
            continue
        seen.add(v.template)
        generation, template, donor = (np.zeros_like(base.generation) for _ in range(3))
        generation[order[v.slot]] = 1
        template[order[v.slot]] = rows[v.template]
        control = base._replace(generation=generation, template=template, donor=donor)
        with np.errstate(all="ignore"):
            after, _ = apply_events(state, control, p, xp=np)
        yield v, after, p


class ReplacementWaterStepChecks:
    """@2's bounds of one definition (v2 design R5), evaluated at first use and kept for every
    chunk of its clock: @3's explicit-rate and calcium bounds on @1's worst-case template
    routes at water's minimum volumes, and water's relaxation rate at each template's
    post-event state. Water's own checks read the declared routes, and @1's worst case the
    declared volumes, so neither covers their product."""

    def __init__(self, spec, declaration, events, model):
        self.spec, self.declaration, self.events, self.model = spec, declaration, events, model

    @cached_property
    def low(self):
        volumes = water.minimum_volume_spec(self.spec, water_of(self.spec))
        worst = replacement.worst_case(self.spec, self.declaration, self.events, base=volumes)
        return ionic_spec.projection(worst)

    @cached_property
    def explicit_rate(self):
        return first.explicit_rate_bound(self.low)

    @cached_property
    def calcium_rate(self):
        return second.calcium_rate_bound(self.low)

    @cached_property
    def water_rate(self):
        rates = [
            water.water_rate(after, p.membrane_active.astype(float), p, xp=np)
            for _, after, p in newcomer_states(self.spec, self.declaration, self.events, self.model)
        ]
        return float(np.max(rates, initial=0.0))

    def __call__(self, steps):
        step = np.max(steps, initial=0)
        if self.spec.execution.solver != "rk4":
            if step * self.explicit_rate > first.EXPLICIT_STEP_BOUND:
                raise ConfigError(
                    "IMEX step exceeds the explicit-rate bound of the newcomers' routes at "
                    "water's minimum volumes"
                )
            if step * self.calcium_rate > first.EXPLICIT_STEP_BOUND:
                raise ConfigError(
                    "IMEX step exceeds the calcium pump bound of the newcomers' routes at "
                    "water's minimum volumes"
                )
        rate = self.water_rate
        if not np.isfinite(rate) or step * rate > water.MAX_WATER_RELAXATION_PER_STEP * (
            1 + 16 * np.finfo(float).eps
        ):
            raise ConfigError(
                "Water relaxation at a newcomer's state requires a smaller step "
                "(dt x rate exceeds 0.05)"
            )


# ------------------------------------------------------------------ the operator


class ScheduledReplacementOverWater(replacement.ScheduledReplacement):
    LAW_ID = LAW_ID
    STATE_AXES = STATE_AXES
    STATE_DTYPES = {k: np.int64 for k in replacement.INTEGER_FIELDS}
    LAYOUT_FIELDS = LAYOUT_FIELDS
    VIEW_READS = ("volume",)
    CONFLICTS_VIEW = DECLARED_LAYOUT_VIEWS
    ENTITY_WRITES = {
        **replacement.ScheduledReplacement.ENTITY_WRITES,
        "volume_increment_pL": ("replacement_volume_removed_pL", "replacement_volume_supplied_pL"),
    }
    EVENT_REPLACES = {
        **replacement.ScheduledReplacement.EVENT_REPLACES,
        "volume_increment_pL": ("replacement_volume_removed_pL", "replacement_volume_supplied_pL"),
    }
    REQUIRES = (water.LAW_ID,)

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        """@1's declaration (its parser, on the shared keys) with the impermeant species."""
        keys = {"law", "junction_formation", "templates", "template_capacity"}
        _fields(raw, keys | {"impermeant_species"}, "replacement")
        if raw["law"] != LAW_ID:
            raise ConfigError("Replacement over water requires law " + LAW_ID)
        listed = raw["impermeant_species"]
        if type(listed) is not list:
            raise ConfigError("Replacement impermeant_species requires an explicit list")
        listed = tuple(identifier(s) for s in listed)
        if len(set(listed)) != len(listed) or not set(listed) <= set(base.model.species_ids):
            raise ConfigError("Impermeant species are distinct declared species")
        shared = {k: raw[k] for k in keys} | {"law": replacement.LAW_ID}
        r = super().parse(shared, base, inner_model)
        return ReplacementOverWater(
            LAW_ID, r.inner_model, r.junction_formation, r.templates, r.template_capacity, listed
        )

    def to_dict(self, declaration, base):
        r = declaration
        if type(r) is not ReplacementOverWater:
            raise ConfigError("Require explicit immutable replacement declaration types")
        shared = replacement_spec.Replacement(
            r.law, r.inner_model, r.junction_formation, r.templates, r.template_capacity
        )
        return super().to_dict(shared, base) | dict(impermeant_species=list(r.impermeant_species))

    def parse_schedule(self, raw, base, declaration):
        """@1's events; a template's volume is its arrival volume (checked against water)."""
        return replacement_spec.parse_events(
            raw["replacement_events"], base, declaration.templates, template_volume="arrival"
        )

    def check_definition(self, spec, declaration, schedule, model):
        if declaration.junction_formation.gate_at_arrival == "law_steady":
            raise ConfigError(
                "law_steady arrival gates are refused over water: their field solve reads the "
                "declared volumes (docs/PUMP_COMPOSITE_V2_DESIGN.md §2.6)"
            )
        check_volumes(declaration, schedule, water_of(spec))
        check_impermeants(spec, declaration, schedule, model)
        replacement.check_definition(spec, declaration, schedule, model, apply=apply_events)

    def inner_check_spec(self, check_spec, spec, declaration, schedule):
        """@1's route maxima applied to the incoming check spec (not discarded)."""
        base = check_spec
        if isinstance(check_spec.model, composite_spec.CompositeModel):
            base = composite_spec.projection(check_spec)
        return replacement.worst_case(spec, declaration, schedule, base=base)

    def check_steps(self, spec, declaration, schedule, steps, controls, model):
        self.bind_check_steps(spec, declaration, schedule, model)(steps)

    def bind_check_steps(self, spec, declaration, schedule, model):
        return ReplacementWaterStepChecks(spec, declaration, schedule, model)

    def working_size(self, spec):
        return super().working_size(spec) + 2 * len(VOLUME_STATE_AXES) * spec.execution.capacity

    def summary(self, spec, declaration, schedule, history):
        return super().summary(spec, declaration, schedule, history) | {
            "replacement_law": LAW_ID,
            "replacement_volume_owner": water.LAW_ID,
            "replacement_volume_rule": (
                "templates arrive at their declared volume; donor copies at the donor's"
            ),
            "impermeant_species": list(declaration.impermeant_species),
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration, schedule)

    # ------------------------------------------------------------ step parts

    def event(self, state, control, p, *, xp):
        return apply_events(state, control, p, xp=xp)

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & own_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = own_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        """@1's terms, then water's free-energy change booked at events."""
        result, own = super().ledger_terms(result, row, p, xp=xp)
        result["energy"] = result["energy"] - xp.sum(row.replacement_water_free_energy_pJ)
        return result, own

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """@1's magnitudes, then water's energy magnitudes in the energy bound (zero for
        founders, so without events the bounds are @1's)."""
        magnitudes = super().magnitude_terms(magnitudes, row, p, xp=xp)
        magnitudes[6] = magnitudes[6] + xp.sum(row.replacement_water_energy_magnitude_pJ)
        return magnitudes

    def external_ledger_terms(self, ledgers, row, p, *, xp):
        """Water's local and total ledgers with the volumes supplied less removed at events."""
        net = row.replacement_volume_supplied_pL - row.replacement_volume_removed_pL
        terms = dict(water_local=net, water_total=xp.sum(net))
        return {k: v - terms[k] for k, v in ledgers.items()}

    def external_magnitude_terms(self, magnitudes, row, p, *, xp):
        moved = row.replacement_volume_removed_pL + row.replacement_volume_supplied_pL
        terms = dict(water_local=moved, water_total=xp.sum(moved))
        return {k: v + terms[k] for k, v in magnitudes.items()}
