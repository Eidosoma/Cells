"""Electrode current injection, an operator of the composite (docs/PUMP_COMPOSITE_V2_DESIGN.md §4).

An electrode delivers a scheduled current I(t) into a cell compartment; the return flows
through the clamped bath. Declared per electrode: its cell and its carrier fractions f_s
(each carrier a charged species, fractions summing to 1). The default for a 3 M KCl filling
is {K: 0.4912, Cl: 0.5088}, the free-solution proportion (dLB74 p530; the rule registered
for J1, validation/division/j1_declared_inputs.json, rm_definition).

Law, per half-step h of the split part (both polarities): each carrier s moves
dN_s = f_s I h / (z_s F), so a positive current is K+ entering and Cl- leaving the cytosol,
and the charge f_s I h of each carrier sums to I h. Bookings, exact for each half-step:
* supplied and removed amounts (injection_supplied_fmol, injection_removed_fmol), the
  electrode's reservoir being source and sink, and the charge I h (injection_charge_C);
* the clamps' image charge and its work, from the capacitor state before and after (as a
  replacement event books them), added to @3's electrode fields and mirrored in
  injection_image_charge_C;
* the source's work, the free-energy change of the state less the clamps' work, in the
  declared work field injection_work_pJ. The membrane's response dissipates through @3's
  own heat. The free-energy terms are @3's (the replacement law's _chemical and
  _electric, imported, until §1.1 gives them a declared owner).
Refusal: a half-step in which a cell could not supply a removed carrier (its amount would
not stay positive). No electrode: statically idle. No current in a step: the half-step
selects the start state. Current changes are exact multiples of dt.
Departures from the v2 note, accepted by the lead (12 November):
* RK4 keeps the half-steps around the inner step ("split", not "coupled"): the
  composite's coupled right-hand side takes operator rates on owned fields only, and the
  injection writes @3's amounts. The step term of a dt study captures the splitting
  error, and the stationary right-hand side leaves this forcing out, as it should.
* The free-energy terms are the replacement law's _chemical and _electric, imported (not
  copied) until the v2 note's §1.1 gives @3's free energy a declared owner.
"""

from bisect import bisect_right
from dataclasses import asdict, dataclass

import jax.numpy as jnp
import numpy as np

from cells.core.specs import ConfigError, _fields
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_tissue as tissue
from cells.models.operators.cell_replacement import _chemical, _electric
from cells.models.operators.contract import Operator
from cells.processes.electrochemistry import CHARGE_PER_FMOL

LAW_ID = "electrode_current_injection@1"
DEFAULT_CARRIERS = {"K": 0.4912, "Cl": 0.5088}  # 3 M KCl filling (dLB74 p530).
FRACTION_TOLERANCE = 1e-9

STATE_AXES = {
    "injection_supplied_fmol": ["species", "cell_slot"],
    "injection_removed_fmol": ["species", "cell_slot"],
    "injection_charge_C": ["cell_slot"],
    "injection_image_charge_C": ["extracellular_slot"],  # Sum of |image charge| booked.
    "injection_work_pJ": ["cell_slot"],
    "injection_energy_magnitude_pJ": ["cell_slot"],
}


@dataclass(frozen=True)
class Electrode:
    cell_id: str
    carriers: tuple  # ((species id, fraction), ...)


@dataclass(frozen=True)
class Injection:
    law: str
    electrodes: tuple


@dataclass(frozen=True)
class CurrentChange:
    time: float
    current_A: float


def _number(value, what):
    if type(value) not in (int, float) or not np.isfinite(value):
        raise ConfigError(f"Injection requires a finite {what}")
    return float(value)


def parse_injection(raw, base):
    _fields(raw, {"law", "electrodes"}, "injection")
    if raw["law"] != LAW_ID:
        raise ConfigError("Injection requires law " + LAW_ID)
    if type(raw["electrodes"]) is not list:
        raise ConfigError("Injection electrodes require an explicit list")
    cells = [c.id for c in base.model.cells]
    electrodes = []
    for entry in raw["electrodes"]:
        _fields(entry, {"cell_id", "carriers"}, "injection electrode")
        if entry["cell_id"] not in cells:
            raise ConfigError(f"Injection electrode in unknown cell {entry['cell_id']!r}")
        carriers = entry["carriers"]
        if type(carriers) is not dict or not carriers:
            raise ConfigError("An electrode declares its carrier fractions")
        fractions = tuple((s, _number(f, "carrier fraction")) for s, f in carriers.items())
        if any(f <= 0 for _, f in fractions):
            raise ConfigError("Carrier fractions are positive")
        if abs(sum(f for _, f in fractions) - 1.0) > FRACTION_TOLERANCE:
            raise ConfigError("Carrier fractions sum to 1")
        electrodes.append(Electrode(entry["cell_id"], fractions))
    if len({e.cell_id for e in electrodes}) != len(electrodes):
        raise ConfigError("One electrode per cell")
    return Injection(LAW_ID, tuple(electrodes))


def parse_controls(raw, base, declaration):
    """One current schedule per electrode: ((time, current), ...) from time 0, increasing."""
    by_cell = {}
    for entry in raw["injection_controls"]:
        _fields(entry, {"cell_id", "schedule"}, "injection control")
        if entry["cell_id"] in by_cell:
            raise ConfigError("One current schedule per electrode")
        changes = []
        for c in entry["schedule"]:
            _fields(c, {"time", "current_A"}, "injection current change")
            changes.append(
                CurrentChange(_number(c["time"], "time"), _number(c["current_A"], "current"))
            )
        times = [c.time for c in changes]
        if (
            not times
            or times[0] != 0.0
            or any(b <= a for a, b in zip(times, times[1:], strict=False))
        ):
            raise ConfigError("A current schedule starts at time 0 with increasing times")
        if times[-1] > base.experiment.end_time:
            raise ConfigError("A current change lies beyond the end time")
        by_cell[entry["cell_id"]] = tuple(changes)
    declared = [e.cell_id for e in declaration.electrodes]
    if set(by_cell) != set(declared):
        raise ConfigError("Every electrode, and only those, has a current schedule")
    return tuple(by_cell[c] for c in declared)


def bind(spec, declaration, inner_layout):
    cells = [c.id for c in spec.model.cells]
    species = list(spec.model.species_ids)
    valence = np.asarray(inner_layout.valence).reshape(-1)  # @3 holds a [species, 1] column.
    fraction = np.zeros((len(declaration.electrodes), len(species)))
    for i, e in enumerate(declaration.electrodes):
        for s, f in e.carriers:
            if s not in species or valence[species.index(s)] == 0:
                raise ConfigError(f"Carrier {s!r} must be a charged species of the model")
            fraction[i, species.index(s)] = f
    n, outside = inner_layout.active.size, inner_layout.reservoir.size
    shapes = dict(species=len(species), cell_slot=n, extracellular_slot=outside)
    state = {k: np.zeros([shapes[a] for a in axes]) for k, axes in STATE_AXES.items()}
    layout = dict(
        injection_cell=np.asarray(
            [cells.index(e.cell_id) for e in declaration.electrodes], dtype=np.int64
        ),
        injection_carrier_fraction=fraction,
    )
    return state, layout


def injected(state, current, h, p, *, xp=jnp):
    """(state after h of injection, every removed carrier available) (module docstring)."""
    n = p.active.size
    z = xp.reshape(p.valence, (-1,))  # @3 holds a [species, 1] column.
    valence = xp.where(z == 0, 1, z)  # Uncharged species carry nothing.
    # dN_s = f_s I h / (z_s F), in fmol: [species, electrode].
    moved = (
        h * p.injection_carrier_fraction.T * current[None, :] / (valence[:, None] * CHARGE_PER_FMOL)
    )
    delta = xp.zeros_like(state.amount_increment)
    delta = (
        delta.at[:, p.injection_cell].add(moved)
        if xp is jnp
        else _add(delta, p.injection_cell, moved)
    )
    increment = state.amount_increment + delta
    available = xp.all(xp.where(delta < 0, p.amount_reference + increment > 0, True))
    dq = CHARGE_PER_FMOL * xp.sum(p.valence * delta, axis=0)
    new = state._replace(
        amount_increment=increment,
        injection_supplied_fmol=state.injection_supplied_fmol + xp.maximum(delta, 0.0),
        injection_removed_fmol=state.injection_removed_fmol + xp.maximum(-delta, 0.0),
        injection_charge_C=state.injection_charge_C + dq,
    )
    # The clamps' image charge and work, and the source's work (as replacement books them).
    q = adapter.inner_layout(p)
    _, start, dv0 = tissue.capacitor_change(adapter.inner_state(state), q, xp=xp)
    _, end, dv1 = tissue.capacitor_change(adapter.inner_state(new), q, xp=xp)
    electrode = xp.where(p.reservoir, end[n:] - start[n:], 0.0)
    work = 1e12 * p.boundary_V * electrode
    g0 = _chemical(state.amount_increment, p, xp=xp)
    g1 = _chemical(increment, p, xp=xp)
    e0, e1 = _electric(dv0, p, xp=xp), _electric(dv1, p, xp=xp)
    cells = xp.any(delta != 0, axis=0)
    count = xp.maximum(xp.sum(cells), 1)
    shared = (e1 - e0 - xp.sum(work)) / count
    magnitude = xp.abs(g0) + xp.abs(g1) + (xp.abs(e0) + xp.abs(e1) + xp.sum(xp.abs(work))) / count
    new = new._replace(
        electrode_charge_transferred_C=state.electrode_charge_transferred_C + electrode,
        electrode_work_pJ=state.electrode_work_pJ + work,
        injection_image_charge_C=state.injection_image_charge_C + xp.abs(electrode),
        injection_work_pJ=xp.where(
            cells, state.injection_work_pJ + (g1 - g0) + shared, state.injection_work_pJ
        ),
        injection_energy_magnitude_pJ=xp.where(
            cells,
            state.injection_energy_magnitude_pJ + magnitude,
            state.injection_energy_magnitude_pJ,
        ),
    )
    flowing = xp.any(current != 0)  # No current: select the start state (bitwise idle).
    return type(state)(
        *(xp.where(flowing, a, b) for a, b in zip(new, state, strict=True))
    ), available


def _add(delta, cells, moved):
    delta = delta.copy()
    np.add.at(delta, (slice(None), cells), moved)
    return delta


class ElectrodeCurrentInjection(Operator):
    LAW_ID = LAW_ID
    SPLIT = True
    RK4 = "split"
    STATE_AXES = STATE_AXES
    WORK_FIELDS = ("injection_work_pJ",)
    LAYOUT_FIELDS = ("injection_cell", "injection_carrier_fraction")
    CONTROL_FIELDS = ("injection_current_A",)
    EXPERIMENT_KEYS = ("injection_controls",)
    ENTITY_WRITES = {
        "amount_increment": (
            "injection_supplied_fmol",
            "injection_removed_fmol",
            "injection_charge_C",
        ),
        "electrode_charge_transferred_C": ("injection_image_charge_C",),
        "electrode_work_pJ": ("injection_work_pJ", "injection_energy_magnitude_pJ"),
    }

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_injection(raw, base)

    def to_dict(self, declaration, base):
        return dict(
            law=declaration.law,
            electrodes=[
                dict(cell_id=e.cell_id, carriers=dict(e.carriers)) for e in declaration.electrodes
            ],
        )

    def parse_schedule(self, raw, base, declaration):
        return parse_controls(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return dict(
            injection_controls=[
                dict(cell_id=e.cell_id, schedule=[asdict(c) for c in g])
                for e, g in zip(declaration.electrodes, schedule, strict=True)
            ]
        )

    def schedule_times(self, schedule):
        return tuple(c.time for g in schedule for c in g)

    def value_at(self, schedule, time):
        return tuple(g[bisect_right([c.time for c in g], time) - 1].current_A for g in schedule)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        values = np.asarray(records, dtype=np.float64).reshape(len(records), -1)
        return (values[indices],)

    def check_definition(self, spec, declaration, schedule, model):
        dt = spec.execution.dt
        for g in schedule:
            for c in g:
                if c.time != round(c.time / dt) * dt:
                    raise ConfigError("A current change must be an exact multiple of dt (k * dt)")

    def batch_signature(self, declaration):
        return (LAW_ID, tuple((e.cell_id, e.carriers) for e in declaration.electrodes))

    def working_size(self, spec):
        x = spec.execution
        return 4 * x.capacity + x.extracellular_capacity

    def summary(self, spec, declaration, schedule, history):
        return {
            "injection_law": LAW_ID,
            "injection_electrodes": {e.cell_id: dict(e.carriers) for e in declaration.electrodes},
            "injection_rk4": "exact half-steps around the inner RK4 step",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration, inner_layout)

    # ------------------------------------------------------------ step parts

    def statically_idle(self, p):
        return p.injection_cell.shape[0] == 0

    def half_step(self, state, h, control, p, *, xp):
        return injected(state, control.injection_current_A, h, p, xp=xp)

    def control_valid(self, control, p, *, xp):
        return xp.all(xp.isfinite(control.injection_current_A))

    def rates(self, state, control, p, view, *, xp):
        return {k: xp.zeros_like(getattr(state, k)) for k in self.STATE_AXES}, None, None

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & _own_valid(state, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = _own_valid(state, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        net = row.injection_removed_fmol - row.injection_supplied_fmol
        result["local"] = result["local"] + net
        result["total"] = result["total"] + xp.sum(net, axis=1)
        result["global_charge"] = result["global_charge"] + xp.sum(row.injection_charge_C)
        result["energy"] = result["energy"] - xp.sum(row.injection_work_pJ)
        return result, {}

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """Moved amounts in the material ledgers, their charge, the booked image charge and
        energy terms; every term is zero without current, so the bounds are then @3's."""
        moved = row.injection_removed_fmol + row.injection_supplied_fmol
        magnitudes[0] = magnitudes[0] + moved
        magnitudes[2] = magnitudes[2] + xp.sum(moved, axis=1)
        charge = CHARGE_PER_FMOL * xp.sum(xp.abs(p.valence) * moved)
        magnitudes[5] = charge if magnitudes[5] is None else magnitudes[5] + charge
        image = row.injection_image_charge_C
        magnitudes[4] = image if magnitudes[4] is None else magnitudes[4] + image
        energy = xp.sum(row.injection_energy_magnitude_pJ)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes


def _own_valid(state, *, xp):
    valid = xp.asarray(True)
    for name in ("injection_supplied_fmol", "injection_removed_fmol", "injection_image_charge_C"):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(value >= 0)
    for name in ("injection_charge_C", "injection_work_pJ", "injection_energy_magnitude_pJ"):
        valid &= xp.all(xp.isfinite(getattr(state, name)))
    return valid & xp.all(state.injection_energy_magnitude_pJ >= 0)
