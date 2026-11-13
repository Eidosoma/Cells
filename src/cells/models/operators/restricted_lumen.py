"""Operator restricted_cleft_lumen@1: a restricted compartment filled with bath fluid as it grows.

docs/CELL_DIVISION_S3_PLAN.md §1; the law is docs/CELL_DIVISION_DESIGN.md §4.2 and §7. The
compartment is general: a finite outside node opened at an insertion onset, lying between the
two apposed sheets of the one patch that faces it (a cleavage cleft is one use; D144).

Law, per half-step of the split part, on each declared lumen node c with its source bath b and
gap width w: the lumen's volume follows its patch's area A (membrane_entity_state@1's view),
V = V_on + w (A - A_on) / 2 with V_on and A_on the declared (onset) values, and the added volume
dV fills with fluid of the bath's declared composition, dn_s = c_b,s dV. There is no water flow.
The volume is state, and each fill books its amounts with the same dV, so the lumen's amounts and
its volume always agree (the lumen_fill ledger). Bookings, exact for each half-step:
* the supply, as @3 books its own: the amounts enter the lumen's extracellular increment, the
  bath's reservoir_supplied and, with the work mu_b dn (mu_b = RT ln c_b + z F phi_b, @3's
  bath potential), its reservoir_work_pJ; lumen_supplied_fmol mirrors them at the lumen;
* the fluid's volume work at the bath, -Pi_b dV with Pi_b = RT sum c_b (the water law's bath
  water work at the bath's water potential psi_b = -Pi_b), in the declared work field
  lumen_fluid_work_pJ;
* the mixing heat of bath fluid entering a lumen of another composition,
  H = RT sum_s c'_s [V phi(c_s / c'_s) + dV phi(c_b,s / c'_s)] >= 0 with phi(y) = y ln y - y + 1
  and c' the mixed concentrations: the exact W - dG of the fill (a Jensen gap, zero at bath
  composition), in the declared heat field lumen_fill_dissipated_energy_pJ;
* the energy ledger's dilution term at the view volume, water's expression
  -RT N ln(V / V_on) (N the lumen's amounts), which brings @3's chemical term on the declared
  volume to the physical one; with it dG = W_supply + W_fluid - H closes exactly;
* the clamps' image charge and its work at the view (BOOKS_AT_VIEW, as injection books it),
  for the rounding-level charge of a fill: the source is declared electroneutral. The electric
  energy of that charge (about 1e-18 pJ per fill in the egg) is left to the energy ledger's
  rounding.
Fluid added between the last insertion half-step and the end of a step waits for the next
step's first half (the operator follows insertion), a splitting error covered by a step study.
A half-step with no fill selects its start state, so a lumen whose patch does not grow is
bitwise idle; the second half-step of a step always selects (the area has not moved since the
first).

Refusals:
* a lumen node that is not a finite onset node of the insertion; a node faced by more than one
  patch (later work) or by none; an onset volume that differs from w A_on / 2 (relative 1e-12);
  another provider of the node's volume (the composite refuses a second provider);
* a source that is not a held bath, or whose declared composition is not electroneutral: the
  lumen has no background state, so a bath's background charge could not enter with its fluid;
* a fill that would shrink the lumen (the area fell), and a volume above its area's.
Insertion's onset rule ("an onset node's volume must be its declared anchor") admits this
operator (ONSET_ANCHORED_VIEWS): its volume is the declared anchor until the area grows.
"""

from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np

from cells.core import pump_composite_spec as composite_spec
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields, _number
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump as first
from cells.models import surface_tissue as tissue
from cells.models.operators import membrane_insertion as insertion
from cells.models.operators import membrane_state
from cells.models.operators.contract import Operator
from cells.numerics.extracellular_field import scatter
from cells.processes.electrochemistry import F, R

LAW_ID = "restricted_cleft_lumen@1"
STEP_ID = "bath_fill_exact_half_steps@1"
ONSET_VOLUME_RTOL = 1e-12  # The declared onset volume against w A_on / 2.
NEUTRALITY_RTOL = 1e-12  # |sum z c| against sum |z| c of a source's declared composition.
FILL_FLOOR_FMOL = 1e-12  # Floor of the fill ledger (plus the per-step rounding).
SERIES_BELOW = 1e-4  # phi(1 + e) by its series for |e| below this (it never rounds negative).

STATE_AXES = {
    "lumen_volume_increment_pL": ["extracellular_slot"],  # V - V_on at lumen nodes.
    "lumen_supplied_fmol": ["species", "extracellular_slot"],  # Bath fluid's amounts received.
    "lumen_image_charge_C": ["extracellular_slot"],  # Sum of |image charge| booked at clamps.
    "lumen_fluid_work_pJ": ["extracellular_slot"],  # -Pi_b dV, per lumen node.
    "lumen_fill_dissipated_energy_pJ": ["extracellular_slot"],  # Mixing heat H >= 0.
    "lumen_energy_magnitude_pJ": ["extracellular_slot"],  # Magnitudes of the energy bookings.
}
LAYOUT_FIELDS = (
    "lumen_node",  # [outside] bool: lumen nodes.
    "lumen_source",  # [outside] int64: each lumen's source bath (0 elsewhere).
    "lumen_patch",  # [outside] int64: the patch each lumen faces (0 elsewhere).
    "lumen_volume_per_area",  # [outside] pL per m^2 of patch area: 1e15 w / 2 (0 elsewhere).
)
LEDGERS = ("lumen_fill",)
LEDGER_DIAGNOSTICS = ("lumen_fill_balance_error_fmol",)
LEDGER_MESSAGE = "Restricted lumen accounting failed: "
READOUT_COLUMNS = ("lumen_volume_pL", "lumen_concentration_mM")


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
    """The declaration on the inner definition (the onset rule is checked with the schedule)."""
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
        facing = [p for p in m.membranes if p.outside == node]
        if len(facing) > 1:
            raise ConfigError("A lumen facing more than one patch is later work")
        if not facing:
            raise ConfigError("A lumen faces one membrane patch, whose area it follows")
        volume = outside[node].volume_pL
        expected = 0.5e15 * width * facing[0].area_m2
        if not abs(volume - expected) <= ONSET_VOLUME_RTOL * expected:
            raise ConfigError(
                f"A lumen's onset volume must be w A_on / 2 = {expected!r} pL, not {volume!r}"
            )
        c = np.asarray(outside[source].initial_amount_fmol) / outside[source].volume_pL
        if not abs(np.sum(z * c)) <= NEUTRALITY_RTOL * np.sum(np.abs(z) * c):
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


def check_definition(spec, declaration):
    """Every lumen node is an onset node of the insertion (REQUIRES puts it before this one)."""
    nodes = set()
    for op, _, schedule in composite_spec.entries(spec):
        if op.LAW_ID == insertion.LAW_ID:
            nodes = insertion.onset_entities(spec, schedule)[1]
    for lumen in declaration.lumens:
        if lumen.node_id not in nodes:
            raise ConfigError(
                f"A lumen node is a finite onset node of the insertion, not {lumen.node_id!r}"
            )


def bind(spec, declaration):
    m, x = spec.model, spec.execution
    o, s = x.extracellular_capacity, len(m.species_ids)
    outside = [c.id for c in m.extracellular]
    layout = dict(
        lumen_node=np.zeros(o, dtype=bool),
        lumen_source=np.zeros(o, dtype=np.int64),
        lumen_patch=np.zeros(o, dtype=np.int64),
        lumen_volume_per_area=np.zeros(o),
    )
    for lumen in declaration.lumens:
        i = outside.index(lumen.node_id)
        layout["lumen_node"][i] = True
        layout["lumen_source"][i] = outside.index(lumen.source_id)
        layout["lumen_patch"][i] = next(
            k for k, p in enumerate(m.membranes) if p.outside == lumen.node_id
        )
        layout["lumen_volume_per_area"][i] = 0.5e15 * lumen.gap_width_m
    sizes = dict(species=s, extracellular_slot=o)
    state = {k: np.zeros([sizes[a] for a in axes]) for k, axes in STATE_AXES.items()}
    return state, layout


# ------------------------------------------------------------------ the law


def source_composition(p, *, xp):
    """[species, outside] each lumen's source concentration, fmol/pL = mM (0 elsewhere)."""
    src = p.lumen_source
    c = p.extracellular_amount_reference[:, src] / p.extracellular_volume[src]
    return xp.where(p.lumen_node, c, 0.0)


def lumen_volume(state, p, *, xp):
    """[outside] every node's volume as this operator provides it (pL)."""
    return p.extracellular_volume + state.lumen_volume_increment_pL


def target_increment(state, p, *, xp):
    """[outside] w (A - A_on) / 2 in pL at lumen nodes, A from the membrane state (0 elsewhere)."""
    grown = membrane_state.area(state, p, xp=xp) - p.membrane_area
    return xp.where(p.lumen_node, p.lumen_volume_per_area * grown[p.lumen_patch], 0.0)


def potentials(p, *, xp):
    """[species, outside] @3's chemical potentials at the declared layout, RT ln c + z F phi_b
    (balances' own expression; the held baths' are their supply potentials mu_b)."""
    co = xp.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1.0)
    return R * p.temperature * xp.log(co) + p.valence * F * p.boundary_V


def mixing(e, *, xp):
    """phi(1 + e) = (1 + e) ln(1 + e) - e >= 0 for e > -1, by its series near e = 0."""
    small = xp.abs(e) < SERIES_BELOW
    safe = xp.where(small, 1.0, e)
    direct = (1.0 + safe) * xp.log1p(safe) - safe
    series = e * e * (0.5 - e * (1.0 / 6.0 - e * (1.0 / 12.0 - e / 20.0)))
    return xp.where(small, series, direct)


def fill_energy(amounts, volume, bath, dv, p, *, xp):
    """(heat H, fluid work) per node of a fill dv, pJ (module docstring).

    amounts [species, outside] fmol and volume [outside] pL before the fill, bath the fluid's
    composition (fmol/pL). With c = n / V, V' = V + dV and c' = (n + c_b dV) / V', the exact
    W - dG of the fill (W = sum mu_b dn - Pi_b dV, its chemical parts) is
    H = RT sum_s c'_s [V phi(c_s / c'_s) + dV phi(c_b,s / c'_s)] >= 0; the arguments are
    1 + e with e = dV (c - c_b) / (V' c') and 1 + e_b with e_b = V (c_b - c) / (V' c'),
    formed without cancellation.
    """
    rt = 1e-3 * R * p.temperature
    lumen = p.lumen_node & (dv > 0)
    v = xp.where(lumen, volume, 1.0)
    v1 = v + dv
    n = xp.where(lumen, amounts, 1.0)
    cb = xp.where(lumen, bath, 1.0)
    c = n / v
    c1 = (n + cb * dv) / v1
    e = dv * (c - cb) / (v1 * c1)
    eb = v * (cb - c) / (v1 * c1)
    heat = rt * xp.sum(c1 * (v * mixing(e, xp=xp) + dv * mixing(eb, xp=xp)), axis=0)
    fluid = -rt * xp.sum(cb, axis=0) * dv
    return xp.where(lumen, heat, 0.0), xp.where(lumen, fluid, 0.0)


def filled(state, p, *, xp=jnp, view=None):
    """(state after one fill half-step, valid) (module docstring). The step length does not
    enter: the fill follows the area that the insertion has reached.

    view: @3's layout at the current state when a field input is provided (BOOKS_AT_VIEW);
    the clamps' plate charges are then the view's, else the declared layout's.

    The fill is decided by comparing the target with the held volume, never by the sign of
    their difference: XLA may contract w dA / 2 - V into one fused multiply-subtract, whose
    rounding residue would make the second half-step of a step (target equal to the held
    volume) a spurious fill or a refusal. The target and the filled amounts are materialised
    behind optimization barriers (adapter.barrier), so the new amounts are one rounded addition
    that no later kernel can recompute fused: every evaluation of the filled state gives the
    same bits, which the electrode ledger's telescoping needs (v2 design §3, prerequisite (c)).
    """
    n = p.active.size
    old = state.lumen_volume_increment_pL
    target = adapter.barrier(target_increment(state, p, xp=xp), xp=xp)
    valid = xp.all(xp.isfinite(target)) & xp.all(target >= old)  # No shrinking lumen.
    lumen = p.lumen_node & (target > old)
    dv = xp.where(lumen, target - old, 0.0)
    bath = source_composition(p, xp=xp)
    dn = adapter.barrier(bath * dv, xp=xp)
    mu = potentials(p, xp=xp)
    supplied = scatter(dn, dn, (p.lumen_source,), xp=xp)  # At the source baths.
    work = 1e-3 * xp.sum(mu * supplied, axis=0)  # As @3 books its own supply.
    amounts = p.extracellular_amount_reference + state.extracellular_amount_increment
    heat, fluid = fill_energy(amounts, lumen_volume(state, p, xp=xp), bath, dv, p, xp=xp)
    new = state._replace(
        extracellular_amount_increment=state.extracellular_amount_increment + dn,
        reservoir_supplied=state.reservoir_supplied + supplied,
        reservoir_work_pJ=state.reservoir_work_pJ + work,
        lumen_volume_increment_pL=xp.where(lumen, target, state.lumen_volume_increment_pL),
        lumen_supplied_fmol=state.lumen_supplied_fmol + dn,
        lumen_fluid_work_pJ=state.lumen_fluid_work_pJ + fluid,
        lumen_fill_dissipated_energy_pJ=state.lumen_fill_dissipated_energy_pJ + heat,
    )
    # The clamps' image charge of the fill's (rounding-level) charge, as injection books it.
    q = adapter.inner_layout(p) if view is None else view
    _, start, _ = tissue.capacitor_change(adapter.inner_state(state), q, xp=xp)
    _, end, _ = tissue.capacitor_change(adapter.inner_state(new), q, xp=xp)
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


def dilution(row, p, *, xp):
    """Water's dilution term at the lumens' volumes, -RT N ln(V / V_on), pJ: @3's chemical term
    on the declared volume plus this is the physical free energy (osmotic_water.water_ledgers)."""
    total = xp.sum(p.extracellular_amount_reference + row.extracellular_amount_increment, axis=0)
    ratio = xp.where(p.lumen_node, row.lumen_volume_increment_pL / p.extracellular_volume, 0.0)
    return -1e-3 * R * p.temperature * xp.sum(xp.where(p.lumen_node, total * xp.log1p(ratio), 0.0))


def energy_magnitude(row, p, *, xp):
    """Magnitudes of the energy terms that cancel once a lumen has grown: @3's chemical term on
    the declared volume at the lumen nodes and the dilution (0 while no lumen has grown)."""
    grown = p.lumen_node & (row.lumen_volume_increment_pL > 0)
    a = xp.where(grown, p.extracellular_amount_reference, 1.0)
    d = xp.where(grown, row.extracellular_amount_increment, 0.0)
    v0 = xp.where(grown, p.extracellular_volume, 1.0)
    rt = 1e-3 * R * p.temperature
    chemical = rt * xp.sum(xp.abs(d * (xp.log(a / v0) - 1)) + xp.abs((a + d) * xp.log1p(d / a)))
    return chemical + xp.abs(dilution(row, p, xp=xp))


def own_valid(state, p, *, xp):
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
    # Never more fluid than the patch's area admits (no fill before the onset).
    return valid & xp.all(state.lumen_volume_increment_pL <= target_increment(state, p, xp=xp))


class RestrictedCleftLumen(Operator):
    LAW_ID = LAW_ID
    STEP_ID = STEP_ID
    SPLIT = True
    RK4 = "split"
    BOOKS_AT_VIEW = True
    STATE_AXES = STATE_AXES
    HEAT_FIELDS = ("lumen_fill_dissipated_energy_pJ",)
    WORK_FIELDS = ("lumen_fluid_work_pJ",)
    LAYOUT_FIELDS = LAYOUT_FIELDS
    VIEW_FIELDS = ("extracellular_volume",)
    ONSET_ANCHORED_VIEWS = ("extracellular_volume",)
    VIEW_READS = ("membrane_area",)
    ENTITY_WRITES = {
        "extracellular_amount_increment": ("lumen_supplied_fmol",),
        "reservoir_supplied": ("lumen_supplied_fmol",),
        "reservoir_work_pJ": ("lumen_supplied_fmol", "lumen_energy_magnitude_pJ"),
        "electrode_charge_transferred_C": ("lumen_image_charge_C",),
        "electrode_work_pJ": ("lumen_image_charge_C", "lumen_energy_magnitude_pJ"),
    }
    LEDGERS = LEDGERS
    LEDGER_DIAGNOSTICS = LEDGER_DIAGNOSTICS
    LEDGER_MESSAGE = LEDGER_MESSAGE
    READOUT_COLUMNS = READOUT_COLUMNS
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
            "lumen_volume_rule": "V = V_on + w (A - A_on) / 2, filled at the source's composition",
            "lumen_rk4": "exact half-steps around the inner RK4 step",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def view(self, state, p, q, *, xp):
        return dict(extracellular_volume=lumen_volume(state, p, xp=xp))

    def half_step(self, state, h, control, p, *, xp, view=None):
        return filled(state, p, xp=xp, view=view)

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & own_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = own_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        """The fill in @3's outside ledger (received at the lumen, supplied at its source)
        and the dilution, fill heat and fluid work in the energy ledger."""
        supplied = row.lumen_supplied_fmol
        source = scatter(supplied, supplied, (p.lumen_source,), xp=xp)
        result["outside"] = result["outside"] - supplied + source
        result["energy"] = (
            result["energy"]
            + dilution(row, p, xp=xp)
            + xp.sum(row.lumen_fill_dissipated_energy_pJ)
            - xp.sum(row.lumen_fluid_work_pJ)
        )
        return result, self.own_ledgers(row, p, xp=xp)

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """The fill's amounts in the outside ledger, the booked image charge in the electrode
        and global-charge bounds, and the energy terms; every term is zero while no lumen has
        grown, so the bounds are then those without this operator."""
        supplied = xp.abs(row.lumen_supplied_fmol)
        magnitudes[1] = (
            magnitudes[1] + supplied + scatter(supplied, supplied, (p.lumen_source,), xp=xp)
        )
        image = row.lumen_image_charge_C
        magnitudes[4] = image if magnitudes[4] is None else magnitudes[4] + image
        charge = xp.sum(image)
        magnitudes[5] = charge if magnitudes[5] is None else magnitudes[5] + charge
        energy = xp.sum(row.lumen_energy_magnitude_pJ) + energy_magnitude(row, p, xp=xp)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    def own_ledgers(self, row, p, *, xp):
        """The fill: the amounts received equal the source's composition times the volume."""
        bath = source_composition(p, xp=xp)
        received = row.lumen_supplied_fmol - bath * row.lumen_volume_increment_pL
        return dict(lumen_fill=xp.where(p.lumen_node, received, 0.0))

    def own_magnitudes(self, row, p, *, xp):
        bath = source_composition(p, xp=xp)
        return (xp.abs(row.lumen_supplied_fmol) + bath * xp.abs(row.lumen_volume_increment_pL),)

    def own_bounds(self, magnitudes, steps):
        rounding = first.LEDGER_STEP_ROUNDING * np.finfo(float).eps * steps
        return (FILL_FLOOR_FMOL + rounding * magnitudes[0],)

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        columns = {k: getattr(state, k) for k in self.STATE_AXES}
        lumen = np.asarray(p.lumen_node) & np.asarray(view.outside_active)
        volume = np.asarray(lumen_volume(state, p, xp=np))
        amounts = np.asarray(view.extracellular_amount_reference) + np.asarray(
            state.extracellular_amount_increment
        )
        columns.update(
            lumen_volume_pL=np.where(lumen, volume, 0.0),
            lumen_concentration_mM=np.where(lumen, amounts / volume, 0.0),
        )
        return columns
