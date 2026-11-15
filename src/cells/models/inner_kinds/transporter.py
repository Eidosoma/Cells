"""cells.transporter@1: the inner model's transporter kind (B5).

docs/INNER_MODEL_V4_DESIGN.md §7.4 (g) 2 and (k); docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §5–6
(FR-4's pump). The kind's hooks are the core's seams (`cells.core.kind_registry.Kind`); its laws
are the kernels of processes/: per cycle a population hydrolyses one ATP to ADP + Pi at its
patch's inside cell and moves n of its role from the patch's inside to its outside.
- `atp_driven_transporter_mass_action_positive@1` (processes/atp_transporter.py): a neutral role;
- `proton_atp_mass_action_positive@1` (processes/proton_pump.py): FR-4's proton pump, a charged
  role (valence +1) on held fuel, read through the stage's read (free h at buffered nodes).

The declaration (model key `transporters`, absent unless declared), one entry per population:

    {"id": "pump_0", "patch": "bounding_0", "law": "cells.proton_atp_mass_action_positive@1",
     "capacity_fmol_s": 8.3027e-3, "stoichiometry": 2, "km_role_mM": 1e-4, "km_atp_mM": 0.1,
     "role": "H", "fuel": {"kind": "maintained_held_rows@1", "node": "cell_0",
                           "rows": ["ATP", "ADP", "Pi"], "ph_ref": 7.2, "ph_band": 0.05}}

- **law:** a namespaced law ID (a bare ID resolves to `cells.`); stored namespaced.
- **capacity_fmol_s** k (fmol cycles/s: N x the per-member value for a lumped node), the
  **stoichiometry** n (an integer 1..4), the role's and ATP's half-saturations K and K_ATP (mM).
- **role:** the moved species row: valence 0 under the neutral law, +1 under the proton law.
- **fuel:** `rows` are the hydrolysed substrate and its two products, (ATP, ADP, Pi), neutral rows
  at `node`, which version 1 fixes to the patch's inside cell. Δ_rG'° comes from the species
  registry's potentials only, μ°'(ADP) + μ°'(Pi) − μ°'(ATP) at its standard concentration c0;
  never from the declaration. `kind`:
  - `maintained_held_rows@1`: the rows are read at every stage and never moved. The maintenance
    supplies the work −Δ_rG'_ATP per cycle, booked as the kind's work, and its material, +1 ATP,
    −1 ADP and −1 Pi per cycle, recorded in `transporter_fuel_supplied_fmol` (an observation:
    the held rows do not change, so no material ledger moves);
  - `finite_fuel_rows@1`: the pump moves its fuel rows. Refused in version 1 until its stored
    part is wired (gap 2: the stage energy rate's standard-potential term).
  `ph_ref` and `ph_band` are the fuel node's transformed-potential band (§5.2): required under the
  proton law, whose domain refuses |pH_in − ph_ref| > ph_band at the read's free h; null under
  the neutral law, which names no proton row in version 1.
- **one population per patch** in version 1: the kind's fields are per patch (`membrane_slot`),
  as today's pumps' are.

What the hooks do:
- **rates:** each declared law's kernel on its own slots (layout masks whose shape is the static
  dispatch: an undeclared law's mask has no element and its kernel is not traced), at the stage's
  read amounts and node potentials. The role moves n per cycle from the patch's inside to its
  outside into the shared inventory (rule (c)), so a charged role charges the field. Heat is
  −cycles x ΔG_cyc and the held fuel's work −cycles x Δ_rG'_ATP; the kind's own fields integrate
  with the tableau like any state.
- **The law's domain at the stage's own inputs** (development stopgap, named in the lane's
  report): a slot outside its law's domain (|ΔG_cyc/RT| > 80, a non-positive input, the proton
  law's pH band) makes the cycles derivative NaN, which the core's finiteness check of the
  stage's rates turns into a refused stage (@3's rhs pattern). stage_check has no potentials and
  domain sees the stored state, so neither can test the charged law's domain; the seam asked of
  the core (a (state, valid) pattern, such as KindRates.valid) replaces this.
- **ledger_terms:** the role's cumulative transfers (n x cycles at its two nodes), the heat and
  the held fuel's work, folded into @3's ledgers by role (rule (a)).
- **moved_rows:** the role at both nodes (and finite fuel's rows, when admitted).
- **check_definition:** the registry's potentials for every fuel row, and the refusals of version
  1's gaps, each named.
"""

import math
from dataclasses import dataclass

import numpy as np

from cells.core import species_registry
from cells.core.kind_registry import BUILTIN, Kind, qualified
from cells.core.specs import ConfigError, _fields, _number
from cells.numerics.extracellular_field import scatter
from cells.processes import atp_transporter as neutral
from cells.processes import proton_pump as proton
from cells.processes.electrochemistry import R

KIND_ID = "cells.transporter@1"
MODEL_KEY = "transporters"
NEUTRAL_LAW = qualified(neutral.LAW_ID)
PROTON_LAW = qualified(proton.LAW_ID)
LAWS = (NEUTRAL_LAW, PROTON_LAW)
HELD = "maintained_held_rows@1"
FINITE = "finite_fuel_rows@1"
FUEL_KINDS = (HELD, FINITE)
ENTRY_FIELDS = (
    "id",
    "patch",
    "law",
    "capacity_fmol_s",
    "stoichiometry",
    "km_role_mM",
    "km_atp_mM",
    "role",
    "fuel",
)
FUEL_FIELDS = ("kind", "node", "rows", "ph_ref", "ph_band")
FUEL_ROLES = ("ATP", "ADP", "Pi")  # `rows` order: the substrate, then its two products.
SUPPLY_PER_CYCLE = (1.0, -1.0, -1.0)  # Held fuel's maintenance restores ATP, removes ADP, Pi.
STOICHIOMETRY_RANGE = (1, 4)
STATE_AXES = (
    ("transporter_cycles", ("membrane_slot",)),
    ("transporter_dissipated_energy_pJ", ("membrane_slot",)),
    ("transporter_metabolic_work_pJ", ("membrane_slot",)),
    ("transporter_fuel_supplied_fmol", ("species", "membrane_slot")),
)
LAYOUT_FIELDS = (
    "transporter_present",  # [membrane] a population on the patch
    "transporter_neutral",  # [membrane] the neutral law's slots, or [0] when it is undeclared
    "transporter_proton",  # [membrane] the proton law's slots, or [0] when it is undeclared
    "transporter_role",  # [membrane] the role's species row
    "transporter_fuel_rows",  # [3, membrane] the ATP, ADP and Pi rows
    "transporter_held",  # [membrane] held fuel
    "transporter_capacity_fmol_s",
    "transporter_stoichiometry",
    "transporter_km_role_mM",
    "transporter_km_atp_mM",
    "transporter_drive0_J_mol",  # [membrane] Δ_rG'° at the registry's c0
    "transporter_c0_mM",  # [] the registry's standard concentration
    "transporter_ph_ref",
    "transporter_ph_band",
)
CONTROL_FIELDS = ("transporter_availability",)
GAP_FINITE_FUEL = (
    "finite fuel (finite_fuel_rows@1) is refused in version 1 until its stored part is wired: "
    "the stage energy rate's standard-potential term (gap 2, after the landing)"
)
GAP_CHARGED = (
    "the charged role waits for the core's seams: B7's stage term (gap 5), held rows with one "
    "writer (gap 8) and the per-patch membrane_flux readout (gap 9)"
)


@dataclass(frozen=True)
class Population:
    """One declared population, its patch's ends resolved at the parse."""

    id: str
    patch: str
    law: str  # namespaced
    capacity_fmol_s: float
    stoichiometry: int
    km_role_mM: float
    km_atp_mM: float
    role: str
    fuel_kind: str
    fuel_node: str
    fuel_rows: tuple  # (ATP, ADP, Pi)
    ph_ref: float | None
    ph_band: float | None
    inside: str  # the patch's inside cell
    outside: str  # the patch's outside node


# ---------------------------------------------------------------------------- definition


def _taken_ids(m):
    pumps = [p.pump for p in m.membranes if getattr(p, "pump", None) is not None]
    pumps += [p.calcium_pump for p in m.membranes if getattr(p, "calcium_pump", None) is not None]
    nodes = (*m.cells, *m.extracellular, *m.membranes, *m.junctions, *m.faces, *pumps)
    return {node.id for node in nodes}


def _fuel(raw, where, law, patch, role, valence):
    fuel = _fields(raw, set(FUEL_FIELDS), f"{where}'s fuel")
    if fuel["kind"] not in FUEL_KINDS:
        raise ConfigError(f"{where}: fuel kind is one of {', '.join(FUEL_KINDS)}")
    if fuel["node"] != patch.inside:
        raise ConfigError(
            f"{where}: the fuel node is the patch's inside cell {patch.inside!r} in version 1 "
            "(the pump hydrolyses ATP where its role starts)"
        )
    rows = fuel["rows"]
    if (
        not isinstance(rows, list)
        or len(rows) != len(FUEL_ROLES)
        or len(set(rows)) != len(rows)
        or any(not isinstance(row, str) or valence.get(row) != 0 or row == role for row in rows)
    ):
        raise ConfigError(
            f"{where}: fuel rows are three distinct neutral species rows (ATP, ADP, Pi), none "
            "of them the role"
        )
    ph_ref, ph_band = fuel["ph_ref"], fuel["ph_band"]
    if law == PROTON_LAW:
        if fuel["kind"] != HELD:
            raise ConfigError(
                f"{where}: the proton pump runs on held fuel in version 1 (finite fuel at a node "
                "with a dynamic proton row is refused, §5.2)"
            )
        ph_ref = _number(ph_ref, f"{where}: ph_ref", positive=True)
        ph_band = _number(ph_band, f"{where}: ph_band")
    elif ph_ref is not None or ph_band is not None:
        raise ConfigError(
            f"{where}: the neutral law names no proton row in version 1, so its fuel declares no "
            "pH band (ph_ref and ph_band null)"
        )
    return fuel["kind"], fuel["node"], tuple(rows), ph_ref, ph_band


def parse(entries, base):
    """The declaration: a tuple of Populations, in declared order."""
    m = base.model
    if not isinstance(entries, list) or not entries:
        raise ConfigError(
            f"{MODEL_KEY} is a non-empty list of transporter populations (omit it for none)"
        )
    patches = {p.id: p for p in m.membranes}
    valence = dict(zip(m.species_ids, m.valence, strict=True))
    taken, ids, used = _taken_ids(m), set(), set()
    out = []
    for raw in entries:
        _fields(raw, set(ENTRY_FIELDS), "a transporter population")
        name = raw["id"]
        if not isinstance(name, str) or not name or name in ids or name in taken:
            raise ConfigError(f"transporter ID {name!r} must be unique among the model's IDs")
        ids.add(name)
        where = f"transporter {name!r}"
        law = qualified(raw["law"]) if isinstance(raw["law"], str) and raw["law"] else None
        if law not in LAWS:
            raise ConfigError(f"{where}: law is one of {', '.join(LAWS)}")
        patch = patches.get(raw["patch"])
        if patch is None:
            raise ConfigError(f"{where}: unknown membrane patch {raw['patch']!r}")
        if patch.id in used:
            raise ConfigError(
                f"{where}: patch {patch.id} already carries a transporter (one per patch in "
                "version 1: the kind's fields are per patch)"
            )
        used.add(patch.id)
        role = raw["role"]
        if role not in valence:
            raise ConfigError(f"{where}: role {role!r} is not a species row")
        if law == PROTON_LAW and valence[role] != 1:
            raise ConfigError(f"{where}: the proton pump's role has valence +1")
        if law == NEUTRAL_LAW and valence[role] != 0:
            raise ConfigError(f"{where}: the neutral law's role has valence 0")
        n = raw["stoichiometry"]
        if type(n) is not int or not STOICHIOMETRY_RANGE[0] <= n <= STOICHIOMETRY_RANGE[1]:
            raise ConfigError(f"{where}: stoichiometry is an integer from 1 to 4")
        out.append(
            Population(
                name,
                patch.id,
                law,
                _number(raw["capacity_fmol_s"], f"{where}: capacity_fmol_s"),
                n,
                _number(raw["km_role_mM"], f"{where}: km_role_mM", positive=True),
                _number(raw["km_atp_mM"], f"{where}: km_atp_mM", positive=True),
                role,
                *_fuel(raw["fuel"], where, law, patch, role, valence),
                patch.inside,
                patch.outside,
            )
        )
    return tuple(out)


def to_dict(declaration):
    return [
        dict(
            id=t.id,
            patch=t.patch,
            law=t.law,
            capacity_fmol_s=t.capacity_fmol_s,
            stoichiometry=t.stoichiometry,
            km_role_mM=t.km_role_mM,
            km_atp_mM=t.km_atp_mM,
            role=t.role,
            fuel=dict(
                kind=t.fuel_kind,
                node=t.fuel_node,
                rows=list(t.fuel_rows),
                ph_ref=t.ph_ref,
                ph_band=t.ph_band,
            ),
        )
        for t in declaration
    ]


def structure_entry(declaration):
    """Value-free: the declared laws and fuel kinds, sorted."""
    return (
        tuple(sorted({t.law for t in declaration})),
        tuple(sorted({t.fuel_kind for t in declaration})),
    )


def check_definition(spec):
    """Δ_rG'° from the registry only (each fuel row's standard_mu_RT), and version 1's refusals."""
    declaration = dict(spec.model.kinds)[KIND_ID]
    for t in declaration:
        where = f"transporter {t.id!r}"
        for row in t.fuel_rows:
            if species_registry.standard_potential(spec, row) is None:
                raise ConfigError(
                    f"{where}: fuel row {row} declares no standard potential (standard_mu_RT) "
                    "in the species registry; Δ_rG'° comes from the registry only"
                )
        if t.fuel_kind == FINITE:
            raise ConfigError(f"{where}: {GAP_FINITE_FUEL}")
        if t.law == PROTON_LAW:
            raise ConfigError(f"{where}: {GAP_CHARGED}")


def drive0_J_mol(spec, population):
    """Δ_rG'° (J/mol) at the registry's standard concentration: RT (μ°'(ADP) + μ°'(Pi) − μ°'(ATP))
    from the registry's μ°/RT, and that c0 (mM)."""
    (atp, c0), (adp, _), (pi, _) = (
        species_registry.standard_potential(spec, row) for row in population.fuel_rows
    )
    return R * spec.model.temperature_K * (adp + pi - atp), c0


def initial(spec, declaration, layout):
    """The kind's state (zeros) and layout, per membrane slot."""
    m, k = spec.model, spec.execution.membrane_capacity
    s, ids, patches = len(m.species_ids), list(m.species_ids), [p.id for p in m.membranes]
    v = dict(
        transporter_present=np.zeros(k, dtype=bool),
        transporter_neutral=np.zeros(k, dtype=bool),
        transporter_proton=np.zeros(k, dtype=bool),
        transporter_role=np.zeros(k, dtype=np.int64),
        transporter_fuel_rows=np.zeros((len(FUEL_ROLES), k), dtype=np.int64),
        transporter_held=np.zeros(k, dtype=bool),
        transporter_capacity_fmol_s=np.zeros(k),
        transporter_stoichiometry=np.ones(k),
        transporter_km_role_mM=np.ones(k),
        transporter_km_atp_mM=np.ones(k),
        transporter_drive0_J_mol=np.zeros(k),
        transporter_ph_ref=np.zeros(k),
        transporter_ph_band=np.zeros(k),
    )
    c0 = None
    for t in declaration:
        j = patches.index(t.patch)
        v["transporter_present"][j] = True
        v["transporter_neutral" if t.law == NEUTRAL_LAW else "transporter_proton"][j] = True
        v["transporter_role"][j] = ids.index(t.role)
        v["transporter_fuel_rows"][:, j] = [ids.index(row) for row in t.fuel_rows]
        v["transporter_held"][j] = t.fuel_kind == HELD
        v["transporter_capacity_fmol_s"][j] = t.capacity_fmol_s
        v["transporter_stoichiometry"][j] = t.stoichiometry
        v["transporter_km_role_mM"][j] = t.km_role_mM
        v["transporter_km_atp_mM"][j] = t.km_atp_mM
        v["transporter_drive0_J_mol"][j], c0 = drive0_J_mol(spec, t)
        if t.law == PROTON_LAW:
            v["transporter_ph_ref"][j], v["transporter_ph_band"][j] = t.ph_ref, t.ph_band
    laws = {t.law for t in declaration}
    for law, name in ((NEUTRAL_LAW, "transporter_neutral"), (PROTON_LAW, "transporter_proton")):
        if law not in laws:  # The static dispatch: an undeclared law's kernel is not traced.
            v[name] = np.zeros(0, dtype=bool)
    v["transporter_c0_mM"] = np.asarray(c0, dtype=float)
    state = dict(
        transporter_cycles=np.zeros(k),
        transporter_dissipated_energy_pJ=np.zeros(k),
        transporter_metabolic_work_pJ=np.zeros(k),
        transporter_fuel_supplied_fmol=np.zeros((s, k)),
    )
    return state, v


def control_values(spec, declaration, times):
    """Availability 1 on every declared population's patch, constant over the run (version 1;
    time-varying schedules are gap 6, after the landing)."""
    patches = [p.id for p in spec.model.membranes]
    present = np.zeros(spec.execution.membrane_capacity)
    for t in declaration:
        present[patches.index(t.patch)] = 1.0
    return dict(transporter_availability=np.tile(present, (len(times), 1)))


def moved_rows(declaration):
    """The role at the patch's two nodes, each under its law (held fuel's rows are read, never
    moved; finite fuel, when admitted, adds its rows at the fuel node)."""
    out = []
    for t in declaration:
        out += [(t.role, t.inside, t.law), (t.role, t.outside, t.law)]
        if t.fuel_kind == FINITE:
            out += [(row, t.fuel_node, t.law) for row in t.fuel_rows]
    return tuple(out)


# ---------------------------------------------------------------------------- the stage


def _concentrations(state, p, *, xp):
    """Every node's concentrations (mM) at `state`; padded nodes read 1."""
    from cells.models.surface_pump_v3 import physical_amounts

    ci, co = physical_amounts(state, p)
    return (
        xp.where(p.active, ci / p.volume, 1.0),
        xp.where(p.outside_active, co / p.extracellular_volume, 1.0),
    )


def _inputs(state, potentials, p, *, xp):
    """(role inside, role outside, patch voltage, fuel [3, membrane]) per membrane slot."""
    ci, co = _concentrations(state, p, xp=xp)
    inside, outside = ci[:, p.membrane_cell], co[:, p.membrane_outside]  # [S, membrane]
    slots = xp.arange(p.transporter_role.shape[-1])
    n = p.active.size
    voltage = xp.where(
        p.membrane_active, potentials[p.membrane_cell] - potentials[n + p.membrane_outside], 0.0
    )
    fuel = inside[p.transporter_fuel_rows, slots[None, :]]
    return inside[p.transporter_role, slots], outside[p.transporter_role, slots], voltage, fuel


def kinetics(state, potentials, availability, p, *, xp):
    """(cycles, ΔG_cyc, Δ_rG'_ATP, domain) per membrane slot, each declared law on its slots."""
    c_in, c_out, voltage, fuel = _inputs(state, potentials, p, xp=xp)
    cycles = energy = drive = xp.zeros_like(c_in)
    valid = xp.ones(c_in.shape, dtype=bool)
    if p.transporter_neutral.shape[-1]:  # Static: the neutral law is declared.
        mask = p.transporter_neutral
        i = neutral.Inputs(
            c_in, c_out, fuel[0], fuel[1], fuel[2],
            p.transporter_drive0_J_mol, p.transporter_c0_mM, p.temperature,
        )  # fmt: skip
        q = neutral.Parameters(
            p.transporter_capacity_fmol_s,
            p.transporter_stoichiometry,
            p.transporter_km_role_mM,
            p.transporter_km_atp_mM,
        )
        r = neutral.kinetics(i, q, availability, xp=xp)
        cycles = xp.where(mask, r.cycles_fmol_s, cycles)
        energy = xp.where(mask, r.cycle_free_energy_J_mol, energy)
        drive = xp.where(mask, r.chemical_drive_J_mol, drive)
        valid = valid & xp.where(mask, neutral.domain_valid(i, q, availability, xp=xp), True)
    if p.transporter_proton.shape[-1]:  # Static: the proton law is declared.
        mask = p.transporter_proton
        # The proton kernel's c° is 1000 mM: Δ_rG'° there is Δ_rG'°(c0) + RT ln(1000 mM / c0).
        delta_g0 = p.transporter_drive0_J_mol + R * p.temperature * (
            math.log(proton.STANDARD_STATE_mM) - xp.log(p.transporter_c0_mM)
        )
        i = proton.Inputs(c_in, c_out, voltage, fuel[0], fuel[1], fuel[2], p.temperature)
        q = proton.Parameters(
            p.transporter_capacity_fmol_s,
            p.transporter_stoichiometry,
            p.transporter_km_role_mM,
            p.transporter_km_atp_mM,
            delta_g0,
            p.transporter_ph_ref,
            p.transporter_ph_band,
        )
        r = proton.kinetics(i, q, availability, xp=xp)
        cycles = xp.where(mask, r.cycles_fmol_s, cycles)
        energy = xp.where(mask, r.cycle_free_energy_J_mol, energy)
        drive = xp.where(mask, r.chemical_drive_J_mol, drive)
        valid = valid & xp.where(mask, proton.domain_valid(i, q, availability, xp=xp), True)
    return cycles, energy, drive, valid


def _role_rows(p, species, *, xp):
    """[S, membrane]: the role's row on every patch that carries a population."""
    return (xp.arange(species)[:, None] == p.transporter_role[None, :]) & p.transporter_present


def _supply_record(cycles, p, species, *, xp):
    """Held fuel's maintenance per cycle, [S, membrane]: +1 ATP, −1 ADP, −1 Pi."""
    rows = xp.arange(species)[:, None]
    held = p.transporter_held & p.transporter_present
    record = xp.zeros((species, cycles.shape[-1]), dtype=cycles.dtype)
    for k, coefficient in enumerate(SUPPLY_PER_CYCLE):
        at = (rows == p.transporter_fuel_rows[k][None, :]) & held
        record = record + xp.where(at, coefficient * cycles, 0.0)
    return record


def rates(state, potentials, control, p, *, xp):
    """The stage's moves, the kind's derivatives, heat and work (§7.4 (k), the rates hook)."""
    from cells.models.surface_pump_v3 import KindRates

    cycles, energy, drive, valid = kinetics(
        state, potentials, control.transporter_availability, p, xp=xp
    )
    moved = xp.where(valid, cycles, 0.0)
    species = state.amount_increment.shape[0]
    outward = xp.where(
        _role_rows(p, species, xp=xp), (p.transporter_stoichiometry * moved)[None, :], 0.0
    )
    heat = -1e-3 * moved * energy
    work = xp.where(p.transporter_held, -1e-3 * moved * drive, 0.0)
    return KindRates(
        cell=-scatter(outward, state.amount_increment, (p.membrane_cell,), xp=xp),
        outside=scatter(
            outward, state.extracellular_amount_increment, (p.membrane_outside,), xp=xp
        ),
        derivatives=dict(
            # The law's domain at the stage's own inputs refuses the stage (module docstring).
            transporter_cycles=xp.where(valid, cycles, xp.nan),
            transporter_dissipated_energy_pJ=heat,
            transporter_metabolic_work_pJ=work,
            transporter_fuel_supplied_fmol=_supply_record(moved, p, species, xp=xp),
        ),
        heat_pJ_s=heat,
        work_pJ_s=work,
    )


# ---------------------------------------------------------------------------- the checks


def ledger_terms(state, p, *, xp):
    """The role's cumulative inward transfers at both nodes (n x cycles), heat and work."""
    species = state.amount_increment.shape[0]
    moved = p.transporter_stoichiometry * state.transporter_cycles
    outward = xp.where(_role_rows(p, species, xp=xp), moved[None, :], 0.0)
    return dict(
        cell=-scatter(outward, state.amount_increment, (p.membrane_cell,), xp=xp),
        outside=scatter(
            outward, state.extracellular_amount_increment, (p.membrane_outside,), xp=xp
        ),
        heat_pJ=state.transporter_dissipated_energy_pJ,
        work_pJ=state.transporter_metabolic_work_pJ,
    )


def domain(state, p, *, xp):
    """The kind's own fields: finite, and exact zeros where they do not apply (no population, no
    held fuel, a row that is not held fuel)."""
    present = p.transporter_present
    valid = xp.asarray(True)
    for name in (
        "transporter_cycles",
        "transporter_dissipated_energy_pJ",
        "transporter_metabolic_work_pJ",
    ):
        value = getattr(state, name)
        valid = valid & xp.all(xp.isfinite(value)) & xp.all(xp.where(present, True, value == 0))
    held = p.transporter_held & present
    valid = valid & xp.all(xp.where(held, True, state.transporter_metabolic_work_pJ == 0))
    record = state.transporter_fuel_supplied_fmol
    rows = xp.arange(record.shape[0])[:, None]
    fuel = xp.zeros(record.shape, dtype=bool)
    for k in range(len(FUEL_ROLES)):
        fuel = fuel | (rows == p.transporter_fuel_rows[k][None, :])
    return valid & xp.all(xp.isfinite(record)) & xp.all(xp.where(fuel & held, True, record == 0))


TRANSPORTER = BUILTIN.register(
    Kind(
        kind_id=KIND_ID,
        model_key=MODEL_KEY,
        state_axes=STATE_AXES,
        layout_fields=LAYOUT_FIELDS,
        control_fields=CONTROL_FIELDS,
        parse=parse,
        to_dict=to_dict,
        structure_entry=structure_entry,
        initial=initial,
        control_values=control_values,
        rates=rates,
        ledger_terms=ledger_terms,
        domain=domain,
        moved_rows=moved_rows,
        check_definition=check_definition,
    )
)
