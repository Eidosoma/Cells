"""Operator restricted_cleft_lumen@2: lumen@1's fill, with a lumen faced by several patches (S5).

docs/CELL_DIVISION_S5_DESIGN.md §5.2 and Appendix A.5. The law, bookings and observer are
lumen@1's (restricted_lumen.py), whose helpers are reused unmodified. Bath fluid fills the
lumen at the source's declared composition as its volume grows. There is no water flow. The
supply, the fluid's volume work, the mixing heat, the dilution term and the clamps' image charge
at the view are booked as in @1.

Changed from @1:
* Target. V = V_on + w (sum_live A_k - A_on) / 2. The sum runs over the facing patches live in
  the composite's view: their own membrane_active, the onset's and the partition's closures.
  A_on is the onset patches' declared area. In the engine it is computed as
  w/2 sum_live (A_k - A_k,declared): the declared areas of the live facing patches sum to A_on
  exactly by the anchor rule, and each term then reduces to @1's for one patch.
* Admission. A lumen node is an onset node of scheduled_membrane_insertion@2. Its facing
  patches are its onset patches, or partition-born descendants of them through the partition's
  patch maps. The declared onset volume is w A_on / 2 (relative 1e-12).
* Continuity. A birth keeps the live facing area: exactly for a = 1/2, within rounding
  otherwise. A target below the held volume by no more than that rounding is no fill; shrinkage
  beyond rounding is refused, as in @1.
* The domain check has no view. Its bound sums over every facing patch, which equals the live
  sum while closed patches hold no growth: pending daughters have none, and the partition moves
  a retired parent's to its daughters. tests/unit/test_restricted_lumen_v2.py asserts this.
* The observer fills each lumen to its live facing area at the saved time, as @1 does for its
  one patch.
"""

from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np

from cells.core import pump_composite_spec as composite_spec
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields, _number
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_tissue as tissue
from cells.models.operators import membrane_insertion as insertion_v1
from cells.models.operators import membrane_insertion_v2 as insertion
from cells.models.operators import membrane_state
from cells.models.operators import restricted_lumen as v1
from cells.models.operators.contract import Operator
from cells.numerics.extracellular_field import scatter

LAW_ID = "restricted_cleft_lumen@2"
STEP_ID = v1.STEP_ID
SHRINK_ROUNDING = 8.0  # eps x w/2 x the live facing area: a birth's rounding, at most.

LAYOUT_FIELDS = (
    "lumen_node",  # [outside] bool: lumen nodes.
    "lumen_source",  # [outside] int64: each lumen's source bath (0 elsewhere).
    "lumen_facing",  # [membrane] bool: patches facing a lumen node.
    "lumen_volume_per_area",  # [outside] pL per m^2 of patch area: 1e15 w / 2 (0 elsewhere).
)


@dataclass(frozen=True)
class Lumen:
    node_id: str
    source_id: str
    gap_width_m: float


@dataclass(frozen=True)
class RestrictedLumens:
    law: str
    lumens: tuple


# ------------------------------------------------------------------ definition


def parse_lumens(raw, base):
    """The declaration on the inner definition. Admission and the onset volume need the
    insertion's schedule and the partition's maps: check_definition."""
    _fields(raw, {"law", "lumens"}, "restricted lumen")
    if raw["law"] != LAW_ID:
        raise ConfigError("A restricted lumen requires law " + LAW_ID)
    if type(raw["lumens"]) is not list or not raw["lumens"]:
        raise ConfigError("A restricted lumen declares its lumens in a non-empty list")
    m = base.model
    outside = {c.id: c for c in m.extracellular}
    z = np.asarray(m.valence, dtype=float)
    lumens = []
    for entry in raw["lumens"]:
        _fields(entry, {"node_id", "source_id", "gap_width_m"}, "lumen")
        node, source = identifier(entry["node_id"]), identifier(entry["source_id"])
        width = _number(entry["gap_width_m"], "lumen gap width", positive=True)
        if node not in outside or outside[node].reservoir:
            raise ConfigError(f"A lumen node is a finite outside node, not {node!r}")
        if source not in outside or not outside[source].reservoir:
            raise ConfigError(f"A lumen's source is a held bath, not {source!r}")
        if not any(p.outside == node for p in m.membranes):
            raise ConfigError("A lumen is faced by a membrane patch, whose area it follows")
        c = np.asarray(outside[source].initial_amount_fmol) / outside[source].volume_pL
        if not abs(np.sum(z * c)) <= v1.NEUTRALITY_RTOL * np.sum(np.abs(z) * c):
            raise ConfigError(
                "A lumen's source must be electroneutral: its background charge cannot enter "
                "the lumen with its fluid"
            )
        lumens.append(Lumen(node, source, width))
    if len({x.node_id for x in lumens}) != len(lumens):
        raise ConfigError("One lumen entry per node")
    return RestrictedLumens(LAW_ID, tuple(lumens))


def lumens_to_dict(declaration):
    if type(declaration) is not RestrictedLumens or any(
        type(x) is not Lumen for x in declaration.lumens
    ):
        raise ConfigError("Require explicit immutable restricted lumen declaration types")
    return dict(
        law=declaration.law,
        lumens=[
            dict(node_id=x.node_id, source_id=x.source_id, gap_width_m=x.gap_width_m)
            for x in declaration.lumens
        ],
    )


def descendants(spec):
    """{patch id: the patch ids the composition's patch maps make of it, transitively} (through
    the contract's patch_maps; this module never imports the operator that maps them)."""
    children = {}
    for op, declaration, _ in composite_spec.entries(spec):
        for parent, daughters in op.patch_maps(declaration).items():
            children.setdefault(parent, []).extend(daughters)
    found = {}
    for patch in [p.id for p in spec.model.membranes]:
        seen, stack = set(), list(children.get(patch, ()))
        while stack:
            k = stack.pop()
            if k not in seen:
                seen.add(k)
                stack.extend(children.get(k, ()))
        found[patch] = seen
    return found


def check_definition(spec, declaration):
    """Admission and the onset volume (module docstring); insertion@2 precedes this law."""
    schedule = next(
        (s for op, _, s in composite_spec.entries(spec) if op.LAW_ID == insertion.LAW_ID), None
    )
    if schedule is None:
        raise ConfigError("A restricted lumen@2 requires " + insertion.LAW_ID)
    patches, nodes, _ = insertion_v1.onset_entities(spec, schedule)
    outside = {c.id: c for c in spec.model.extracellular}
    family = descendants(spec)
    for lumen in declaration.lumens:
        if lumen.node_id not in nodes:
            raise ConfigError(
                f"A lumen node is a finite onset node of the insertion, not {lumen.node_id!r}"
            )
        facing = [p for p in spec.model.membranes if p.outside == lumen.node_id]
        onset = [p for p in facing if p.id in patches]
        admitted = {p.id for p in onset} | {k for p in onset for k in family[p.id]}
        for p in facing:
            if p.id not in admitted:
                raise ConfigError(
                    f"Lumen {lumen.node_id}: patch {p.id} is neither an onset patch nor a "
                    "partition-born descendant of one"
                )
        expected = 0.5e15 * lumen.gap_width_m * sum(p.area_m2 for p in onset)
        volume = outside[lumen.node_id].volume_pL
        if not abs(volume - expected) <= v1.ONSET_VOLUME_RTOL * expected:
            raise ConfigError(
                f"A lumen's onset volume must be w A_on / 2 = {expected!r} pL, not {volume!r}"
            )


def bind(spec, declaration):
    m, x = spec.model, spec.execution
    o, s = x.extracellular_capacity, len(m.species_ids)
    outside = [c.id for c in m.extracellular]
    layout = dict(
        lumen_node=np.zeros(o, dtype=bool),
        lumen_source=np.zeros(o, dtype=np.int64),
        lumen_facing=np.zeros(x.membrane_capacity, dtype=bool),
        lumen_volume_per_area=np.zeros(o),
    )
    for lumen in declaration.lumens:
        i = outside.index(lumen.node_id)
        layout["lumen_node"][i] = True
        layout["lumen_source"][i] = outside.index(lumen.source_id)
        layout["lumen_volume_per_area"][i] = 0.5e15 * lumen.gap_width_m
        for k, p in enumerate(m.membranes):
            if p.outside == lumen.node_id:
                layout["lumen_facing"][k] = True
    sizes = dict(species=s, extracellular_slot=o)
    state = {k: np.zeros([sizes[a] for a in axes]) for k, axes in v1.STATE_AXES.items()}
    return state, layout


# ------------------------------------------------------------------ the law


def target_increment(state, p, live, *, xp):
    """[outside] w/2 sum_live (A_k - A_k,declared) in pL at lumen nodes (0 elsewhere): live is
    a [membrane] mask (the view's, or every patch for the domain's bound)."""
    grown = membrane_state.area(state, p, xp=xp) - p.membrane_area
    facing = xp.where(p.lumen_facing & live, grown, 0.0)
    total = scatter(facing, xp.zeros(p.outside_active.size), (p.membrane_outside,), xp=xp)
    return xp.where(p.lumen_node, p.lumen_volume_per_area * total, 0.0)


def rounding(state, p, live, *, xp):
    """[outside] the continuity allowance at lumen nodes: SHRINK_ROUNDING eps w/2 sum_live A_k."""
    area = xp.where(p.lumen_facing & live, membrane_state.area(state, p, xp=xp), 0.0)
    total = scatter(area, xp.zeros(p.outside_active.size), (p.membrane_outside,), xp=xp)
    eps = SHRINK_ROUNDING * np.finfo(float).eps
    return xp.where(p.lumen_node, eps * p.lumen_volume_per_area * total, 0.0)


def filled(state, p, view, *, xp=jnp):
    """(state after one fill half-step at the composite's view, valid): @1's fill (its
    operations, barriers and order) with the target over the live facing patches, and a
    shrinkage within the birth's rounding taken as no fill."""
    n = p.active.size
    live = view.membrane_active
    old = state.lumen_volume_increment_pL
    target = adapter.barrier(target_increment(state, p, live, xp=xp), xp=xp)
    allowance = rounding(state, p, live, xp=xp)
    valid = xp.all(xp.isfinite(target)) & xp.all(target >= old - allowance)  # No shrinking lumen.
    lumen = p.lumen_node & (target > old)
    dv = xp.where(lumen, target - old, 0.0)
    bath = v1.source_composition(p, xp=xp)
    dn = adapter.barrier(bath * dv, xp=xp)
    mu = v1.potentials(p, xp=xp)
    supplied = scatter(dn, dn, (p.lumen_source,), xp=xp)  # At the source baths.
    work = 1e-3 * xp.sum(mu * supplied, axis=0)  # As @3 books its own supply.
    amounts = p.extracellular_amount_reference + state.extracellular_amount_increment
    heat, fluid = v1.fill_energy(amounts, v1.lumen_volume(state, p, xp=xp), bath, dv, p, xp=xp)
    new = state._replace(
        extracellular_amount_increment=state.extracellular_amount_increment + dn,
        reservoir_supplied=state.reservoir_supplied + supplied,
        reservoir_work_pJ=state.reservoir_work_pJ + work,
        lumen_volume_increment_pL=xp.where(lumen, target, state.lumen_volume_increment_pL),
        lumen_supplied_fmol=state.lumen_supplied_fmol + dn,
        lumen_fluid_work_pJ=state.lumen_fluid_work_pJ + fluid,
        lumen_fill_dissipated_energy_pJ=state.lumen_fill_dissipated_energy_pJ + heat,
    )
    # The clamps' image charge of the fill's (rounding-level) charge, at the view.
    _, start, _ = tissue.capacitor_change(adapter.inner_state(state), view, xp=xp)
    _, end, _ = tissue.capacitor_change(adapter.inner_state(new), view, xp=xp)
    electrode = xp.where(p.reservoir, end[n:] - start[n:], 0.0)
    clamp = 1e12 * p.boundary_V * electrode
    count = xp.maximum(xp.sum(lumen), 1)
    booked = 1e-3 * xp.sum(xp.abs(mu[:, p.lumen_source]) * dn, axis=0)  # Each lumen's supply work.
    magnitude = booked + xp.abs(fluid) + heat + xp.sum(xp.abs(clamp)) / count
    new = new._replace(
        electrode_charge_transferred_C=new.electrode_charge_transferred_C + electrode,
        electrode_work_pJ=new.electrode_work_pJ + clamp,
        lumen_image_charge_C=state.lumen_image_charge_C + xp.abs(electrode),
        lumen_energy_magnitude_pJ=state.lumen_energy_magnitude_pJ + xp.where(lumen, magnitude, 0.0),
    )
    valid &= xp.all(xp.isfinite(heat)) & xp.all(heat >= 0) & xp.all(xp.isfinite(electrode))
    flowing = xp.any(lumen)  # No fill: select the start state (bitwise idle).
    return type(state)(*(xp.where(flowing, a, b) for a, b in zip(new, state, strict=True))), valid


def filled_to_area(state, p, reference, live, *, xp):
    """@1's observer lumen (restricted_lumen.filled_to_area) over the live facing patches."""
    target = target_increment(state, p, live, xp=xp)
    old = state.lumen_volume_increment_pL
    lumen = p.lumen_node & (target > old)
    dv = xp.where(lumen, target - old, 0.0)
    increment = state.extracellular_amount_increment + v1.source_composition(p, xp=xp) * dv
    volume = p.extracellular_volume + xp.where(lumen, target, old)
    return volume, reference + increment


def own_valid(state, p, *, xp):
    """@1's state checks, with the volume bounded by every facing patch's growth (no view: it
    equals the live growth while closed patches hold none) within the birth's rounding."""
    lumen = p.lumen_node
    valid = xp.asarray(True)
    for name, mask, sign in (
        ("lumen_volume_increment_pL", lumen, 1),
        ("lumen_supplied_fmol", lumen, 1),
        ("lumen_image_charge_C", p.reservoir, 1),
        ("lumen_fluid_work_pJ", lumen, -1),
        ("lumen_fill_dissipated_energy_pJ", lumen, 1),
        ("lumen_energy_magnitude_pJ", lumen, 1),
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(sign * value >= 0)
        valid &= xp.all(xp.where(mask, True, value == 0))
    every = xp.ones_like(p.lumen_facing)
    bound = target_increment(state, p, every, xp=xp) + rounding(state, p, every, xp=xp)
    return valid & xp.all(state.lumen_volume_increment_pL <= bound)


class RestrictedCleftLumenV2(Operator):
    LAW_ID = LAW_ID
    STEP_ID = STEP_ID
    SPLIT = True
    RK4 = "split"
    BOOKS_AT_VIEW = True
    STATE_AXES = v1.STATE_AXES
    HEAT_FIELDS = ("lumen_fill_dissipated_energy_pJ",)
    WORK_FIELDS = ("lumen_fluid_work_pJ",)
    LAYOUT_FIELDS = LAYOUT_FIELDS
    VIEW_FIELDS = ("extracellular_volume",)
    ONSET_ANCHORED_VIEWS = ("extracellular_volume",)
    VIEW_READS = ("membrane_area", "membrane_active")
    ENTITY_WRITES = {
        "extracellular_amount_increment": ("lumen_supplied_fmol",),
        "reservoir_supplied": ("lumen_supplied_fmol",),
        "reservoir_work_pJ": ("lumen_supplied_fmol", "lumen_energy_magnitude_pJ"),
        "electrode_charge_transferred_C": ("lumen_image_charge_C",),
        "electrode_work_pJ": ("lumen_image_charge_C", "lumen_energy_magnitude_pJ"),
    }
    LEDGERS = v1.LEDGERS
    LEDGER_DIAGNOSTICS = v1.LEDGER_DIAGNOSTICS
    LEDGER_MESSAGE = v1.LEDGER_MESSAGE
    READOUT_COLUMNS = v1.READOUT_COLUMNS
    REQUIRES = (membrane_state.LAW_ID, insertion.LAW_ID)

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_lumens(raw, base)

    def to_dict(self, declaration, base):
        return lumens_to_dict(declaration)

    def check_definition(self, spec, declaration, schedule, model):
        check_definition(spec, declaration)

    def batch_signature(self, declaration):
        return (LAW_ID, tuple((x.node_id, x.source_id) for x in declaration.lumens))

    def working_size(self, spec):
        x = spec.execution
        return 8 * (len(spec.model.species_ids) + 6) * x.extracellular_capacity

    def summary(self, spec, declaration, schedule, history):
        return {
            "lumen_law": LAW_ID,
            "lumen_step": STEP_ID,
            "lumens": {
                x.node_id: dict(source_id=x.source_id, gap_width_m=x.gap_width_m)
                for x in declaration.lumens
            },
            "lumen_volume_rule": (
                "V = V_on + w (sum_live A - A_on) / 2 over the live facing patches, filled at "
                "the source's composition"
            ),
            "lumen_rk4": "exact half-steps around the inner RK4 step",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def view(self, state, p, q, *, xp):
        return dict(extracellular_volume=v1.lumen_volume(state, p, xp=xp))

    def half_step(self, state, h, control, p, *, xp, view=None):
        if view is None:
            raise ConfigError("Lumen@2 follows the live facing patches at the composite's view")
        return filled(state, p, view, xp=xp)

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & own_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = own_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        return v1.RestrictedCleftLumen.ledger_terms(self, result, row, p, xp=xp)

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        return v1.RestrictedCleftLumen.magnitude_terms(self, magnitudes, row, p, xp=xp)

    def own_ledgers(self, row, p, *, xp):
        return v1.RestrictedCleftLumen.own_ledgers(self, row, p, xp=xp)

    def own_magnitudes(self, row, p, *, xp):
        return v1.RestrictedCleftLumen.own_magnitudes(self, row, p, xp=xp)

    def own_bounds(self, magnitudes, steps):
        return v1.RestrictedCleftLumen.own_bounds(self, magnitudes, steps)

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        """The state fields, and each lumen filled to its live facing area at this time."""
        columns = {k: getattr(state, k) for k in self.STATE_AXES}
        lumen = np.asarray(p.lumen_node) & np.asarray(view.outside_active)
        volume, amounts = (
            np.asarray(x)
            for x in filled_to_area(
                state,
                p,
                np.asarray(view.extracellular_amount_reference),
                np.asarray(view.membrane_active),
                xp=np,
            )
        )
        columns.update(
            lumen_volume_pL=np.where(lumen, volume, 0.0),
            lumen_concentration_mM=np.where(lumen, amounts / volume, 0.0),
        )
        return columns
