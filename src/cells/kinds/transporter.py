"""cells.transporter@1: the inner model's transporter kind (B5), seam A's membrane-cycle kind.

**Two layouts in one kind** (docs/CORE_SEAMS_DESIGN.md §3.5 and §14 ruling 1, A3; the kinds owner's
design statement 1, confirmed 18 November 2026). A declaration whose every entry is in version 1's
form (today's keys and restrictions, below) keeps version 1's layout: its fields per patch, its
hook code, its refusals and its programs, unchanged. Any other declaration takes the population
axis (section "the population axis" below): populations on their own axis, any number per host,
each running its law's general form (laws/cycles/forms.py) in one generic program, with every free
energy the kind's from the species registry. An entry in the general form (keys id, host, law,
orientation, capacity_fmol_s, roles, parameters, held_rows) is never in version 1's form; entries
in today's keys on the population axis are read through a one-to-one map, and each entry writes
back in the form it was declared in. This pass's limits on the axis: hosts are membrane patches; a
mode that converts a species at P is refused (complexes III and IV will need it); held rows are
neutral (charged held rows, seam C's ATP4- with forms included, are out of scope).

**Availability schedules on the population axis** (D228 item 5; the core's gap-6 schedules, §7.4
(l)): the experiment key `transporter_controls`, optional, each population at most once, an
omitted one at 1 throughout:

    [{"transporter_id": "pump_0", "schedule": [{"time": 0.0, "availability": 1.0},
                                               {"time": 60.0, "availability": 0.25}]}]

parsed into one kind_registry.Schedule, the series "ID.availability" per population in declared
order, each right-continuous and piecewise constant from time 0 with values in [0, 1]. Its
breakpoints join the change times, so each is a step boundary and every step holds the value at its
start; the held value multiplies each population's J+ (k a S) and its carriers. Without the key the
kind declares no schedule (parse_schedule returns None, the lead's ruling (A) of 19 November 2026),
so a definition keeps its change records, by value and type, and its availability is 1 as before.
Version 1's layout holds each patch's availability at 1 and refuses the key.

Version 1's layout:

docs/INNER_MODEL_V4_DESIGN.md §7.4 (g) 2 and (k); docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §5–6
(FR-4's pump). The kind's hooks are the core's seams (`cells.registry.kind_registry.Kind`); its laws
are the kernels of processes/: per cycle a population hydrolyses one ATP to ADP + Pi at its
patch's inside cell and moves n of its role from the patch's inside to its outside.
- `atp_driven_transporter_mass_action_positive@1` (laws/pumps/atp_transporter.py): a neutral role;
- `proton_atp_mass_action_positive@1` (laws/pumps/proton_pump.py): FR-4's proton pump, a charged
  role (valence +1) on held fuel, read through the stage's read (free h at buffered nodes).

The declaration (model key `transporters`, absent unless declared), one entry per population:

    {"id": "pump_0", "patch": "bounding_0", "law": "cells.proton_atp_mass_action_positive@1",
     "capacity_fmol_s": 8.3027e-3, "stoichiometry": 2, "km_role_mM": 1e-4, "km_atp_mM": 0.1,
     "role": "H", "fuel": {"kind": "maintained_held_rows@1", "node": "cell_0",
                           "rows": ["ATP", "ADP", "Pi"], "ph_ref": 7.2, "ph_band": 0.05}}

- **law:** a namespaced law ID (a bare ID resolves to `cells.`); stored namespaced. The kind finds
  its laws in the active law registry: the cycle laws it hosts (registry/laws.py; §8.3 of
  docs/CORE_SEAMS_DESIGN.md), never a module tuple. Its two laws are declared here, on the law
  template, until each moves to its own module (§8.2). Version 1's layout runs each of the two by
  name (VERSION_1_LAWS), so it refuses any other cycle law it hosts, until the cycle kind's
  general layout (§3.5).
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
  - `finite_fuel_rows@1`: the pump moves its fuel rows, and the kind books their standard term
    Σ μ°' Δn as stored_pJ. Refused in this round: the stage energy-rate observation's
    standard-potential term waits for the landing (gap 2).
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
- **The law's domain at the stage's own inputs** (KindRates.valid): a slot outside its law's
  domain (|ΔG_cyc/RT| > 80 with the patch voltage, a non-positive input, the proton law's pH
  band at the read's free h) refuses the row or the step.
- **readouts:** the instantaneous cycle rate, ΔG_cyc and Δ_rG'_ATP per patch at the observed
  row's read and potentials (free h at buffered nodes); zero where no population.
- **membrane_flux** (gap 9): the role's outward flux across each patch joins the patches' total
  flux and, for a charged role, the membrane current.
- **stage_term** (gap 5, B7 for kinds): each charged population's electrogenic slope, n e M e^a
  nF/RT with a = ΔG_cyc/RT, at the stage's read and patch voltage, at both of its patch's ends
  (cells, then outside nodes: surface_pump_v3.patch_node_conductance): the true slope in every
  regime, so a pump driven past its static head (the voltage where ΔG_cyc = 0) into reverse
  (a > 0) counts its e^a, at a face-free compartment's node as at the cell. Called without
  potentials it takes the static head, the forward regime's maximum (a <= 0 while the pump runs
  forward or stalls). **bound_rate:** B7's definition-time term, the slope bounded with the role's
  saturation and e^a at 1, over each free node's capacitance.
- **held_rows** (gap 8): held fuel's rows at its node, which binding refuses any other writer of.
- **ledger_terms:** the role's cumulative transfers (n x cycles at its two nodes), the heat and
  the held fuel's work, folded into @3's ledgers by role (rule (a)).
- **moved_rows:** the role at both nodes (and finite fuel's rows, when admitted).
- **check_definition:** the registry's potentials for every fuel row, and finite fuel's refusal
  (gap 2).

The stage helpers `gather` (the role's and fuel's concentrations per patch), `proton_law` (the
proton kernel's inputs per patch), `patch_voltage`, `static_head_V`, `role_rows` and
`supply_record` are public, so a variant of this kind (a control's planted law, outside
src/cells) composes from them, never from private names.
"""

import math
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType, SimpleNamespace
from typing import NamedTuple

import numpy as np

from cells.laws.cycles import forms
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.laws.pumps import atp_transporter as neutral
from cells.laws.pumps import proton_pump as proton
from cells.modules import (
    CYCLE_LAW,
    AxisHost,
    ConfigError,
    Kind,
    KindFields,
    KindView,
    PartitionRole,
    Schedule,
    bounded_integer,
    declared_schedule,
    entity_sum,
    finite_number,
    parse_series,
    qualified,
    require_fields,
    scatter,
    series_to_dict,
)
from cells.registry import species_registry
from cells.registry.kind_registry import BUILTIN

KIND_ID = "cells.transporter@1"
MODEL_KEY = "transporters"
NEUTRAL_LAW = qualified(neutral.LAW_ID)
PROTON_LAW = qualified(proton.LAW_ID)
# The laws version 1's layout runs, each by name through its own slots' mask (the static dispatch).
VERSION_1_LAWS = (NEUTRAL_LAW, PROTON_LAW)
HELD = "maintained_held_rows@1"
FINITE = "finite_fuel_rows@1"
FUEL_KINDS = (HELD, FINITE)
# The kind's two laws, each declared in its own module (CORE_SEAMS §8.2; the model table's law
# homes), where the law registry's loader registers them for the kind to find by interface and host.
NEUTRAL = neutral.LAW
PROTON = proton.LAW
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
READOUT_COLUMNS = (
    "transporter_cycle_rate_fmol_s",
    "transporter_cycle_free_energy_J_mol",
    "transporter_chemical_drive_J_mol",
)
GAP_FINITE_FUEL = (
    "finite fuel (finite_fuel_rows@1) is refused in this round: the stage energy-rate "
    "observation's standard-potential term waits for the landing (gap 2)"
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


def hosted_laws():
    """{namespaced law ID: declaration} of the cycle laws this kind hosts, in canonical order:
    found in the active law registry by interface and host (CORE_SEAMS §8.3)."""
    from cells.modules import hosted_laws as lookup

    return {qualified(law.law_id): law for law in lookup(CYCLE_LAW, KIND_ID)}


def _taken_ids(m):
    pumps = [p.pump for p in m.membranes if getattr(p, "pump", None) is not None]
    pumps += [p.calcium_pump for p in m.membranes if getattr(p, "calcium_pump", None) is not None]
    nodes = (*m.cells, *m.extracellular, *m.membranes, *m.junctions, *m.faces, *pumps)
    return {node.id for node in nodes}


def _fuel(raw, where, law, patch, role, valence):
    fuel = require_fields(raw, set(FUEL_FIELDS), f"{where}'s fuel")
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
        ph_ref = finite_number(ph_ref, f"{where}: ph_ref", positive=True)
        ph_band = finite_number(ph_band, f"{where}: ph_band")
    elif ph_ref is not None or ph_band is not None:
        raise ConfigError(
            f"{where}: the neutral law names no proton row in version 1, so its fuel declares no "
            "pH band (ph_ref and ph_band null)"
        )
    return fuel["kind"], fuel["node"], tuple(rows), ph_ref, ph_band


def parse(entries, base):
    """The declaration (design statement 1, §1): today's tuple of Populations where every entry is
    in version 1's form, else the population axis (PopulationAxis)."""
    if isinstance(entries, list) and entries:
        if not all(map(_today_keys, entries)) or _diverts(entries):
            return _parse_population_axis(entries, base)
    return _parse_version_1(entries, base)


def _parse_version_1(entries, base):
    """Version 1's layout's declaration: a tuple of Populations, in declared order."""
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
        require_fields(raw, set(ENTRY_FIELDS), "a transporter population")
        name = raw["id"]
        if not isinstance(name, str) or not name or name in ids or name in taken:
            raise ConfigError(f"transporter ID {name!r} must be unique among the model's IDs")
        ids.add(name)
        where = f"transporter {name!r}"
        law = qualified(raw["law"]) if isinstance(raw["law"], str) and raw["law"] else None
        hosted = hosted_laws()
        if law not in hosted:
            raise ConfigError(f"{where}: law is one of {', '.join(hosted)}")
        if law not in VERSION_1_LAWS:
            raise ConfigError(
                f"{where}: version 1's layout runs {', '.join(VERSION_1_LAWS)}, not {law}; the "
                "cycle kind's general layout will run any cycle law it hosts (CORE_SEAMS §3.5)"
            )
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
        n = bounded_integer(
            raw["stoichiometry"],
            f"{where}: stoichiometry",
            minimum=STOICHIOMETRY_RANGE[0],
            maximum=STOICHIOMETRY_RANGE[1],
        )
        out.append(
            Population(
                name,
                patch.id,
                law,
                finite_number(raw["capacity_fmol_s"], f"{where}: capacity_fmol_s"),
                n,
                finite_number(raw["km_role_mM"], f"{where}: km_role_mM", positive=True),
                finite_number(raw["km_atp_mM"], f"{where}: km_atp_mM", positive=True),
                role,
                *_fuel(raw["fuel"], where, law, patch, role, valence),
                patch.inside,
                patch.outside,
            )
        )
    return tuple(out)


def to_dict(declaration):
    if isinstance(declaration, PopulationAxis):
        return [_population_dict(t) for t in declaration]
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
    """Value-free: the declared laws and fuel kinds, sorted; on the population axis, CycleAxis."""
    if isinstance(declaration, PopulationAxis):
        return CycleAxis(tuple(sorted({t.law for t in declaration})))
    return (
        tuple(sorted({t.law for t in declaration})),
        tuple(sorted({t.fuel_kind for t in declaration})),
    )


def check_definition(spec):
    """Δ_rG'° from the registry only (each fuel row's standard_mu_RT), and version 1's refusals."""
    declaration = dict(spec.model.kinds)[KIND_ID]
    if isinstance(declaration, PopulationAxis):
        return _check_population_axis(spec, declaration)
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


def drive0_J_mol(spec, population):
    """Δ_rG'° (J/mol) at the registry's standard concentration: RT (μ°'(ADP) + μ°'(Pi) − μ°'(ATP))
    from the registry's μ°/RT, and that c0 (mM)."""
    (atp, c0), (adp, _), (pi, _) = (
        species_registry.standard_potential(spec, row) for row in population.fuel_rows
    )
    return R * spec.model.temperature_K * (adp + pi - atp), c0


def initial(spec, declaration, layout):
    """The kind's state (zeros) and layout, per membrane slot (or per population)."""
    if isinstance(declaration, PopulationAxis):
        return _population_initial(spec, declaration)
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


SCHEDULE_KEY = "transporter_controls"  # The population axis's availability schedules (gap 6).
SCHEDULE_FIELDS = ("transporter_id", "schedule")
DEFAULT_SERIES = ((0.0, 1.0),)  # A population without an entry: available throughout.


def series_name(population_id):
    return f"{population_id}.availability"


def parse_schedule(raw, base, declaration):
    """The population axis's availability schedules from `transporter_controls` (module
    docstring), or None without the key: the kind declares no schedule, so the definition keeps
    today's change records and every availability is 1 (the lead's ruling (A))."""
    if SCHEDULE_KEY not in raw:
        return None
    if not isinstance(declaration, PopulationAxis):
        raise ConfigError(
            f"{SCHEDULE_KEY} schedules the population axis's availabilities; version 1's layout "
            "holds each patch's availability at 1"
        )
    entries = raw[SCHEDULE_KEY]
    if not isinstance(entries, list) or not entries:
        raise ConfigError(
            f"{SCHEDULE_KEY} is a non-empty list of availability schedules (omit it for none)"
        )
    ids = [t.id for t in declaration]
    given = {}
    for entry in entries:
        require_fields(entry, set(SCHEDULE_FIELDS), f"an entry of {SCHEDULE_KEY}")
        name = entry["transporter_id"]
        if name not in ids:
            raise ConfigError(f"{SCHEDULE_KEY}: unknown transporter population {name!r}")
        if name in given:
            raise ConfigError(f"{SCHEDULE_KEY}: transporter population {name!r} is scheduled twice")
        given[name] = parse_series(
            entry["schedule"], f"{SCHEDULE_KEY} {name}", value="availability"
        )
    return Schedule(tuple((series_name(i), given.get(i, DEFAULT_SERIES)) for i in ids))


def schedule_to_dict(schedule, declaration):
    """parse_schedule's inverse: every population's series under the key (a schedule exists only
    where the definition gave the key)."""
    series = dict(schedule.series)
    return {
        SCHEDULE_KEY: [
            dict(
                transporter_id=t.id,
                schedule=series_to_dict(series[series_name(t.id)], value="availability"),
            )
            for t in declaration
        ]
    }


def control_values(spec, declaration, times):
    """Each population's availability at `times` (the change times) from its schedule, or 1
    where the definition declares none; version 1's availability is 1 on every declared
    population's patch, constant over the run."""
    if isinstance(declaration, PopulationAxis):
        schedule = declared_schedule(spec, KIND_ID)
        if schedule is None:
            return dict(cycle_availability=np.ones((len(times), len(declaration))))
        columns = [schedule.values(series_name(t.id), times) for t in declaration]
        return dict(cycle_availability=np.stack(columns, axis=-1))
    patches = [p.id for p in spec.model.membranes]
    present = np.zeros(spec.execution.membrane_capacity)
    for t in declaration:
        present[patches.index(t.patch)] = 1.0
    return dict(transporter_availability=np.tile(present, (len(times), 1)))


def moved_rows(declaration):
    """The role at the patch's two nodes, each under its law (held fuel's rows are read, never
    moved; finite fuel, when admitted, adds its rows at the fuel node)."""
    if isinstance(declaration, PopulationAxis):
        return tuple(
            (species, node, t.law) for t in declaration for species, node in _rows(t, held=False)
        )
    out = []
    for t in declaration:
        out += [(t.role, t.inside, t.law), (t.role, t.outside, t.law)]
        if t.fuel_kind == FINITE:
            out += [(row, t.fuel_node, t.law) for row in t.fuel_rows]
    return tuple(out)


def role_species(declaration):
    """Each population as §5.2's admission reads it (F's EntityBinding; D142), in declared order and
    in either layout: the law it runs; the species each role its law's change rows name binds (the
    roles of registry/laws.cycle_changes' "role@end"); the node at each end those rows name, N at
    the population's N end (its host's end a, the cell, or b, the outside node; version 1's are
    always a) and P at the other; and its values for the law's parameter-named counts (the
    stoichiometry, for both built-in laws)."""
    from cells.modules import EntityBinding, cycle_changes

    hosted = hosted_laws()
    out = []
    for t in declaration:
        if isinstance(declaration, PopulationAxis):
            roles, values = dict(t.roles), dict(t.parameters)
            n_node, p_node = (t.inside, t.outside) if t.n_end == "a" else (t.outside, t.inside)
        else:  # Version 1's: N is the cell, as the general form's one-to-one map reads it.
            roles = {VERSION_1_ROLE[t.law]: t.role, **dict(zip(FUEL_ROLES, t.fuel_rows, strict=True))}
            values, n_node, p_node = {"stoichiometry": t.stoichiometry}, t.inside, t.outside
        rows = cycle_changes(hosted[t.law])
        named = [row["role"].split("@") for row in rows]
        counts = {c.lstrip("-") for c in (row["per_cycle"] for row in rows) if isinstance(c, str)}
        node = {"N": n_node, "P": p_node}
        out.append(
            EntityBinding(
                t.law,
                MappingProxyType({role: roles[role] for role in dict.fromkeys(r for r, _ in named)}),
                MappingProxyType({end: node[end] for end in dict.fromkeys(e for _, e in named)}),
                MappingProxyType({name: values[name] for name in sorted(counts)}),
            )
        )
    return tuple(out)


def held_rows(declaration):
    """Held fuel's rows at its node: read at every stage, moved by nothing (gap 8, one writer)."""
    if isinstance(declaration, PopulationAxis):
        return tuple(dict.fromkeys(row for t in declaration for row in _rows(t, held=True)))
    return tuple(
        (row, t.fuel_node) for t in declaration if t.fuel_kind == HELD for row in t.fuel_rows
    )


def bound_rate(spec, declaration):
    """B7's definition-time term (1/s, gap 5): at each free node a charged population charges, the
    populations' slopes over the node's capacitance, the largest. A pump's slope is bounded by
    k S_ATP n² e F/(RT): the role's saturation and e^a at most 1 (forward or stalled), S_ATP at
    the held fuel's declared amount. A node's capacitance sums its patches'. Held baths and nodes
    that faces join are not free nodes (as in B7's own term)."""
    if isinstance(declaration, PopulationAxis):
        return _population_bound_rate(spec, declaration)
    m = spec.model
    charged = [t for t in declaration if t.law == PROTON_LAW]
    if not charged:
        return 0.0
    ids = list(m.species_ids)
    nodes = {node.id: node for node in (*m.cells, *m.extracellular)}
    held_bath = {o.id for o in m.extracellular if o.reservoir}
    faced = {f.sender for f in m.faces} | {f.receiver for f in m.faces}
    capacitance, conductance = {}, {}
    for patch in m.membranes:
        for node in (patch.inside, patch.outside):
            capacitance[node] = capacitance.get(node, 0.0) + patch.capacitance_F
    for t in charged:
        fuel = nodes[t.fuel_node]
        atp = fuel.initial_amount_fmol[ids.index(t.fuel_rows[0])] / fuel.volume_pL
        cycles = t.capacity_fmol_s * atp / (atp + t.km_atp_mM)
        slope = t.stoichiometry**2 * F / (R * m.temperature_K) * CHARGE_PER_FMOL * cycles
        for node in (t.inside, t.outside):
            if node not in held_bath and node not in faced:
                conductance[node] = conductance.get(node, 0.0) + slope
    return max((g / capacitance[node] for node, g in conductance.items()), default=0.0)


# ---------------------------------------------------------------------------- the stage


def _concentrations(state, p, *, xp):
    """Every node's concentrations (mM) at `state`; padded nodes read 1."""
    from cells.modules import physical_amounts

    ci, co = physical_amounts(state, p)
    return (
        xp.where(p.active, ci / p.volume, 1.0),
        xp.where(p.outside_active, co / p.extracellular_volume, 1.0),
    )


def gather(state, p, *, xp):
    """(role inside, role outside, fuel [3, membrane]) concentrations per membrane slot."""
    ci, co = _concentrations(state, p, xp=xp)
    inside, outside = ci[:, p.membrane_cell], co[:, p.membrane_outside]  # [S, membrane]
    slots = xp.arange(p.transporter_role.shape[-1])
    fuel = inside[p.transporter_fuel_rows, slots[None, :]]
    return inside[p.transporter_role, slots], outside[p.transporter_role, slots], fuel


def proton_law(c_in, c_out, voltage, fuel, p, *, xp):
    """The proton kernel's (Inputs, Parameters) per membrane slot. Its c° is 1000 mM, so its
    Δ_rG'° is the registry's at c0 plus RT ln(1000 mM / c0)."""
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
    return i, q


def patch_voltage(potentials, p, *, xp):
    """[membrane] each patch's voltage, phi(inside cell) - phi(outside node) (V), from the stage's
    node potentials (cells, then outside nodes); 0 on padded patches."""
    n = p.active.size
    return xp.where(
        p.membrane_active, potentials[p.membrane_cell] - potentials[n + p.membrane_outside], 0.0
    )


def static_head_V(inputs, parameters, *, xp):
    """[membrane] the proton law's static head (V): the patch voltage where dG_cyc = 0,
    (d_rG'_ATP / n + RT ln(h_out / h_in)) / F, at the inputs' concentrations."""
    return (
        proton.chemical_drive(inputs, parameters, xp=xp) / parameters.protons_per_cycle
        + R * inputs.temperature_K * (xp.log(inputs.h_out_mM) - xp.log(inputs.h_in_mM))
    ) / F


def kinetics(state, potentials, availability, p, *, xp):
    """(cycles, ΔG_cyc, Δ_rG'_ATP, domain) per membrane slot, each declared law on its slots."""
    c_in, c_out, fuel = gather(state, p, xp=xp)
    voltage = patch_voltage(potentials, p, xp=xp)
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
        i, q = proton_law(c_in, c_out, voltage, fuel, p, xp=xp)
        r = proton.kinetics(i, q, availability, xp=xp)
        cycles = xp.where(mask, r.cycles_fmol_s, cycles)
        energy = xp.where(mask, r.cycle_free_energy_J_mol, energy)
        drive = xp.where(mask, r.chemical_drive_J_mol, drive)
        valid = valid & xp.where(mask, proton.domain_valid(i, q, availability, xp=xp), True)
    return cycles, energy, drive, valid


def role_rows(p, species, *, xp):
    """[S, membrane]: the role's row on every patch that carries a population."""
    return (xp.arange(species)[:, None] == p.transporter_role[None, :]) & p.transporter_present


def supply_record(cycles, p, species, *, xp):
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
    if MARK in type(p)._fields:  # Static: the population axis's layout.
        return _population_rates(state, potentials, control, p, xp=xp)
    from cells.modules import KindRates

    cycles, energy, drive, valid = kinetics(
        state, potentials, control.transporter_availability, p, xp=xp
    )
    moved = xp.where(valid, cycles, 0.0)
    species = state.amount_increment.shape[0]
    outward = xp.where(
        role_rows(p, species, xp=xp), (p.transporter_stoichiometry * moved)[None, :], 0.0
    )
    heat = -1e-3 * moved * energy
    work = xp.where(p.transporter_held, -1e-3 * moved * drive, 0.0)
    return KindRates(
        cell=-scatter(outward, state.amount_increment, (p.membrane_cell,), xp=xp),
        outside=scatter(
            outward, state.extracellular_amount_increment, (p.membrane_outside,), xp=xp
        ),
        derivatives=dict(
            transporter_cycles=moved,
            transporter_dissipated_energy_pJ=heat,
            transporter_metabolic_work_pJ=work,
            transporter_fuel_supplied_fmol=supply_record(moved, p, species, xp=xp),
        ),
        heat_pJ_s=heat,
        work_pJ_s=work,
        membrane_flux=outward,  # Gap 9: joins the patches' flux and current.
        valid=xp.all(valid),  # The laws' domains at the stage's read and potentials.
    )


def readouts(state, read, potentials, control, p, *, xp):
    """READOUT_COLUMNS per patch at the observed row's read and potentials; zero where no
    population."""
    if MARK in type(p)._fields:  # Static: the population axis's layout.
        return _population_readouts(read, potentials, control, p, xp=xp)
    del state
    values = kinetics(read, potentials, control.transporter_availability, p, xp=xp)[:3]
    return tuple(xp.where(p.transporter_present, value, 0.0) for value in values)


def stage_term(read, potentials, control, p, *, xp):
    """[cells, then outside nodes] conductance (S) of the charged populations at the stage (gap
    5): each proton pump's electrogenic slope n F |d cycles/dV|, the kernel's own conductance, at
    the stage's read and patch voltage, at both of its patch's ends, so a pump driven past its
    static head into reverse counts its e^a at the cell and at a face-free compartment's node
    (module docstring). Without potentials (membrane_rate called bare) the slope is taken at the
    static head, the forward regime's maximum."""
    if MARK in type(p)._fields:  # Static: the population axis's layout.
        return _population_stage_term(read, potentials, control, p, xp=xp)
    from cells.models.surface_pump_v3 import patch_node_conductance

    n = p.active.size
    if not p.transporter_proton.shape[-1]:  # Static: no charged law is declared.
        return xp.zeros(n + p.outside_active.size)
    c_in, c_out, fuel = gather(read, p, xp=xp)
    i, q = proton_law(c_in, c_out, xp.zeros_like(c_in), fuel, p, xp=xp)
    if potentials is None:  # Structure, not a value: the caller passes no potentials.
        voltage = static_head_V(i, q, xp=xp)
    else:
        voltage = patch_voltage(potentials, p, xp=xp)
    slope = proton.electrogenic_conductance_S(
        i._replace(voltage_V=voltage), q, control.transporter_availability, xp=xp
    )
    slope = xp.where(p.transporter_proton & p.membrane_active, slope, 0.0)
    return patch_node_conductance(slope, p, xp=xp)


# ---------------------------------------------------------------------------- the checks


def ledger_terms(state, p, *, xp):
    """The role's cumulative inward transfers at both nodes (n x cycles), heat and work."""
    if MARK in type(p)._fields:  # Static: the population axis's layout.
        return _population_ledger_terms(state, p, xp=xp)
    species = state.amount_increment.shape[0]
    moved = p.transporter_stoichiometry * state.transporter_cycles
    outward = xp.where(role_rows(p, species, xp=xp), moved[None, :], 0.0)
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
    if MARK in type(p)._fields:  # Static: the population axis's layout.
        return _population_domain(state, p, xp=xp)
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


# ============================================================================ the population axis
# Seam A's general layout (docs/CORE_SEAMS_DESIGN.md §3, §14 ruling 1 (A3), §16 and §19; the kinds
# owner's design statement 1, confirmed 18 November 2026): populations on their own axis, any
# number per host, each running its law's general form (laws/cycles/forms.py: data only) in
# one generic program over layout arrays. A form no population declares has zero-size arrays and is
# not traced. Every free energy is the kind's, from the species registry:
#     x_m = g°_m + sum_k nu_mk ln c_k - q_m psi,   psi = F (phi_N - phi_P) / RT,
#     J+ = k a S,   J = J+ (1 - e^x) (sign-exact),   J- = J+ e^x.
# This pass's limits (the lead's conditions on statement 1): hosts are membrane patches; a mode
# that changes a species at P without changing it at N (chemistry at P) is refused, though
# complexes III and IV will need it (cytochrome c is on the P side); held rows are neutral, so a
# charged held row (seam C's ATP4- with forms included) is out of scope.
# The monomial form (K6, the lead's rulings of 20 November 2026; forms.py) runs on the same axis:
# - its fields (MONOMIAL_FIELDS) exist only where a declared law runs it, so every other world keeps
#   its fields and programs;
# - its references resolve at the parse into free slots (a species at an end): read roles are
#   bound like roles and never moved, and a registry form or a total is read only where a declared
#   closure holds the row, with beta from the species registry alone (the binding owner's three
#   conditions); its log k's CitedConstant is converted once, at the world's T (cited_log_k);
# - its slopes land on rows by species and end, its domain is one-sided (x <= 80), and its bare
#   stage and material terms (no potentials) fail closed, since its S reads psi.

MARK = "cycle_host"  # The population axis's first layout field: the traced hooks' static switch.
GENERAL_FIELDS = (
    "id",
    "host",
    "law",
    "orientation",
    "capacity_fmol_s",
    "roles",
    "parameters",
    "held_rows",
)
ENDS = ("a", "b")  # A host's ends: a patch's cell (a) and its outside node (b).
FORM_CODES = MappingProxyType({"factored": 0, "diagram": 1, "net_flow": 2, "monomial": 3})
# Seam D's non-negative heat booking (CORE_SEAMS §6.1), which the kind admits beyond the tableau
# (K2): the core books a picked kind's heat fields as dt (q_start + q_end) / 2.
TRAPEZOID_BOOKING = "trapezoid_nonnegative@1"
MAX_ABS_AFFINITY_OVER_RT = 80.0  # Per mode, as version 1's laws (§3.2).
# Version 1's keys read on the population axis (statement 1, §1): the role's name in each law's form.
VERSION_1_ROLE = MappingProxyType({PROTON_LAW: "proton", NEUTRAL_LAW: "role"})
GENERAL_STATE_AXES = (
    ("cycle_count", ("cycle_mode", "cycle_population")),
    ("cycle_dissipated_energy_pJ", ("cycle_population",)),
    ("cycle_metabolic_work_pJ", ("cycle_population",)),
    ("cycle_supplied_fmol", ("species", "cycle_population")),
)
DIAGRAM_FIELDS = (
    "log_k0",  # [D, P]: each edge direction's ln k0; slots e, E + e and the zero slot 2E
    "orders",  # [D, K, P]
    "zeta",  # [D, P]
    "term_slots",  # [T, J, P]: the directional diagrams
    "term_root",  # [T, P]
    "term_present",  # [T, P]
    "term_orders",  # [T, K, P]
    "term_zeta",  # [T, P]
    "plus_slots",  # [M, L, P]
    "minus_slots",  # [M, L, P]
    "plus_orders",  # [M, K, P]
    "plus_zeta",  # [M, P]
    "cut_slots",  # [M, C, I, P]: each cycle's contraction's diagrams
    "cut_present",  # [M, C, P]
    "cut_orders",  # [M, C, K, P]
    "cut_zeta",  # [M, C, P]
    "edge_states",  # [E, 2, P]
    "edge_present",  # [E, P]
    "state_present",  # [S, P]
    "log_scale",  # [P]: ln omega
    "ln_standard",  # [P]: ln c° of the diagram's activities
)
NET_FLOW_FIELDS = ("weight", "counts", "standard_RT", "charge", "shift", "present")
GENERAL_LAYOUT_FIELDS = (
    MARK,  # [P]: the host-table row of each population's host
    "cycle_present",  # [P]: each population present (Q2's presence: a closer's gate ands it)
    "cycle_n_at_b",  # [P]: N is the host's end b
    "cycle_capacity_fmol_s",  # [P]
    "cycle_form",  # [P]: FORM_CODES
    "cycle_row_species",  # [K, P]
    "cycle_row_at_n",  # [K, P]
    "cycle_row_present",  # [K, P]
    "cycle_row_held",  # [K, P]
    "cycle_row_charged",  # [K, P]
    "cycle_nu",  # [M, K, P]
    "cycle_mode_present",  # [M, P]
    "cycle_standard_RT",  # [M, P]: g°_m
    "cycle_charge_moved",  # [M, P]: q_m, N to P
    "cycle_moved_standard_RT",  # [M, P]: the moved rows' standard part, sigma_m
    "cycle_held_standard_RT",  # [M, P]: the held rows'
    "cycle_sat_row",  # [M, F, P]
    "cycle_sat_log_k",  # [M, F, P]
    "cycle_sat_hill",  # [M, F, P]
    "cycle_sat_present",  # [M, F, P]
    "cycle_band_row",  # [B, P]
    "cycle_band_center",  # [B, P]
    "cycle_band_width",  # [B, P]
    "cycle_band_present",  # [B, P]
    *(f"cycle_dg_{name}" for name in DIAGRAM_FIELDS),
    *(f"cycle_nf_{name}" for name in NET_FLOW_FIELDS),  # [M, U, P], counts [M, U, K, P]
)
# The monomial form's fields (K6), only where a declared law runs it (declared_fields), so a
# definition without one keeps today's fields and programs: its free slots (each a species at an
# end, R), and each mode's tables over them (forms.monomial_tables; Q factors, G terms each).
MONOMIAL_FIELDS = (
    "cycle_mono_slot_species",  # [R, P]
    "cycle_mono_slot_at_n",  # [R, P]
    "cycle_mono_slot_present",  # [R, P]
    "cycle_mono_slot_row",  # [R, P]: the row a slot is (its species at its end), else 0
    "cycle_mono_slot_is_row",  # [R, P]
    "cycle_mono_log_k",  # [M, P]
    "cycle_mono_orders",  # [M, R, P]
    "cycle_mono_zeta",  # [M, P]
    "cycle_mono_power",  # [M, Q, P]
    "cycle_mono_term_log_k",  # [M, Q, G, P]
    "cycle_mono_term_q",  # [M, Q, G, R, P]
    "cycle_mono_term_eta",  # [M, Q, G, P]
    "cycle_mono_term_present",  # [M, Q, G, P]
    "cycle_mono_share",  # [M, P]
    "cycle_mono_ln_standard",  # [P]: ln c° of the form's activities
)
GENERAL_CONTROL_FIELDS = ("cycle_availability",)
GENERAL_READOUT_COLUMNS = (
    "cycle_rate_fmol_s",
    "cycle_free_energy_J_mol",
    "cycle_held_drive_J_mol",
)
# The hooks only the population axis has: absent for version 1's entry, so its programs stay
# today's (KindFields.without; @3's material_rate adds a check when any kind declares one).
POPULATION_HOOKS = ("material_term", "view_sets", "standard_free_energies")
INV_LN10 = 1.0 / math.log(10.0)
LN_PH_STANDARD = math.log(1000.0)  # pH = -log10(c / 1000 mM)


class CycleAxis(NamedTuple):
    """The population axis's structure entry: its declared laws, sorted (value-free)."""

    laws: tuple


class CyclePopulation(NamedTuple):
    """One population on the axis, its host's ends resolved at the parse."""

    id: str
    host: str
    law: str  # namespaced
    n_end: str  # "a" or "b": the host end that is N
    capacity_fmol_s: float
    roles: tuple  # ((role, species), ...), in the form's role order
    parameters: tuple  # ((name, value), ...), in the form's parameter order
    held_rows: tuple  # ((role, end), ...), as declared
    inside: str  # the host patch's cell (end a)
    outside: str  # its outside node (end b)
    source: object = None  # the version-1 Population an entry in today's keys was read from


class PopulationAxis(tuple):
    """The population axis's declaration: CyclePopulations in declared order."""

    __slots__ = ()


def _today_keys(raw):
    """Whether an entry is in today's keys (the general form names a host)."""
    return not (isinstance(raw, dict) and "host" in raw)


def _diverts(entries):
    """Whether a declaration of entries in today's keys needs the population axis: two populations
    on one patch, or finite fuel under the neutral law (version 1 refuses both)."""
    patches, finite = [], False
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        if isinstance(raw.get("patch"), str):
            patches.append(raw["patch"])
        fuel, law = raw.get("fuel"), raw.get("law")
        if (
            isinstance(fuel, dict)
            and fuel.get("kind") == FINITE
            and isinstance(law, str)
            and law
            and qualified(law) == NEUTRAL_LAW
        ):
            finite = True
    return finite or len(set(patches)) != len(patches)


def cycle_form(law_id):
    """The general form (a CycleForm) of a hosted law, or None."""
    law = hosted_laws().get(qualified(law_id))
    return None if law is None else getattr(law, "cycle", None)


def _mapped(t):
    """A version-1 Population read on the population axis (statement 1, §1's one-to-one map)."""
    params = dict(
        stoichiometry=float(t.stoichiometry), km_role_mM=t.km_role_mM, km_atp_mM=t.km_atp_mM
    )
    if t.law == PROTON_LAW:
        params |= dict(ph_ref=t.ph_ref, ph_band=t.ph_band)
    form = cycle_form(t.law)
    roles = dict(zip(FUEL_ROLES, t.fuel_rows, strict=True)) | {VERSION_1_ROLE[t.law]: t.role}
    held = tuple((role, "N") for role in FUEL_ROLES) if t.fuel_kind == HELD else ()
    return CyclePopulation(
        t.id,
        t.patch,
        t.law,
        "a",
        t.capacity_fmol_s,
        tuple((role, roles[role]) for role in form.role_names),
        tuple((name, params[name]) for name in form.parameter_names),
        held,
        t.inside,
        t.outside,
        t,
    )


def _counts(form, values):
    """Each mode's integer count per row, for a population's parameter values."""
    return forms.resolve(form, values)[0]


def _parse_general(raw, base, patches, valence, taken):
    """One entry in the general form (statement 1, §1)."""
    require_fields(raw, set(GENERAL_FIELDS), "a transporter population")
    name = raw["id"]
    if not isinstance(name, str) or not name or name in taken:
        raise ConfigError(f"transporter ID {name!r} must be unique among the model's IDs")
    where = f"transporter {name!r}"
    law = qualified(raw["law"]) if isinstance(raw["law"], str) and raw["law"] else None
    hosted = hosted_laws()
    if law not in hosted:
        raise ConfigError(f"{where}: law is one of {', '.join(hosted)}")
    form = getattr(hosted[law], "cycle", None)
    if form is None:
        raise ConfigError(f"{where}: {law} has no general form, so it runs on version 1's layout only")
    patch = patches.get(raw["host"])
    if patch is None:
        raise ConfigError(
            f"{where}: unknown host {raw['host']!r}: a host is a membrane patch in this pass"
        )
    orientation = raw["orientation"]
    if not (isinstance(orientation, dict) and set(orientation) == {"N"} and orientation["N"] in ENDS):
        raise ConfigError(f'{where}: orientation is {{"N": "a"}} or {{"N": "b"}} (the host end that is N)')
    capacity = finite_number(raw["capacity_fmol_s"], f"{where}: capacity_fmol_s")
    roles = raw["roles"]
    reads = form.monomial.read_roles if form.monomial is not None else ()  # Never moved (K6).
    named = (*form.role_names, *(role for role, _ in reads))
    if not (isinstance(roles, dict) and set(roles) == set(named)):
        raise ConfigError(f"{where}: roles binds each of {', '.join(named)} to a species row")
    species = [roles[role] for role in named]
    if any(s not in valence for s in species) or len(set(species)) != len(species):
        raise ConfigError(f"{where}: each role binds a distinct species row of the model")
    for role, z in (*form.roles, *reads):
        if z is not None and valence[roles[role]] != z:
            raise ConfigError(f"{where}: {law}'s role {role} has valence {z:+d}, not {roles[role]}'s")
    values = raw["parameters"]
    if not (isinstance(values, dict) and set(values) == set(form.parameter_names)):
        raise ConfigError(
            f"{where}: parameters gives {', '.join(form.parameter_names) or 'none'} (the law's)"
        )
    reasons = forms.parameter_errors(form, values)
    if reasons:
        raise ConfigError(f"{where}: " + "; ".join(reasons))
    held = raw["held_rows"]
    if not (
        isinstance(held, list)
        and all(isinstance(r, list) and len(r) == 2 and tuple(r) in form.rows for r in held)
        and len({tuple(r) for r in held}) == len(held)
    ):
        raise ConfigError(f"{where}: held_rows lists distinct rows of the law, each [role, N or P]")
    held = tuple(tuple(r) for r in held)
    population = CyclePopulation(
        name,
        patch.id,
        law,
        orientation["N"],
        capacity,
        tuple((role, roles[role]) for role in named),
        tuple((p.name, values[p.name]) for p in form.parameters),  # As declared.
        held,
        patch.inside,
        patch.outside,
    )
    _check_population(population, form, hosted[law], valence, where)
    return population


def _check_population(t, form, law, valence, where):
    """A population's rows and modes against the pass's rules (statement 1, §2; Q3, Q4)."""
    roles, held = dict(t.roles), set(t.held_rows)
    for role, end in held:
        if valence[roles[role]] != 0:
            raise ConfigError(
                f"{where}: held row {role}@{end} binds {roles[role]}, a charged row; a held row is "
                "neutral in this pass (a charged held row would create charge)"
            )
    fuel = [row for row in form.rows if row[0] in form.fuel_roles]
    held_fuel = [row for row in fuel if row in held]
    if held_fuel and len(held_fuel) != len(fuel):
        raise ConfigError(f"{where}: the fuel rows are held together or moved together")
    if fuel and held_fuel and HELD not in law.fuel_kinds:
        raise ConfigError(f"{where}: {t.law} runs on moved fuel only")
    if fuel and not held_fuel and FINITE not in law.fuel_kinds:
        raise ConfigError(
            f"{where}: {t.law} runs on held fuel (finite fuel at a node with a dynamic proton row is "
            "refused, §5.2)"
        )
    counts = _counts(form, dict(t.parameters))
    for (mode, _), row_counts in zip(form.modes, counts, strict=True):
        charge = sum(int(valence[roles[r]]) * int(n) for (r, _), n in zip(form.rows, row_counts))
        if charge != 0:
            raise ConfigError(f"{where}: mode {mode} moves charge {charge:+d}: every mode conserves charge")
        at_n = {r for (r, e), n in zip(form.rows, row_counts) if e == "N" and n}
        for (role, end), n in zip(form.rows, row_counts):
            if end == "P" and n and role not in at_n:
                raise ConfigError(
                    f"{where}: mode {mode} changes {role} at P without changing it at N (chemistry at "
                    "P is refused in this pass)"
                )


def _parse_population_axis(entries, base):
    """The population axis's declaration (statement 1, §1): entries in the general form, and
    entries in today's keys read through the map, each checked by today's code for its own keys."""
    m = base.model
    patches = {p.id: p for p in m.membranes}
    valence = dict(zip(m.species_ids, m.valence, strict=True))
    taken, ids, out = _taken_ids(m), set(), []
    for raw in entries:
        if _today_keys(raw):
            (version_1,) = _parse_version_1([raw], base)
            population = _mapped(version_1)
            _check_population(
                population,
                cycle_form(population.law),
                hosted_laws()[population.law],
                valence,
                f"transporter {population.id!r}",
            )
        else:
            population = _parse_general(raw, base, patches, valence, taken)
        if population.id in ids:
            raise ConfigError(f"transporter ID {population.id!r} must be unique among the model's IDs")
        ids.add(population.id)
        out.append(population)
    moved = {row for t in out for row in _rows(t, held=False)}
    for t in out:
        for row in _rows(t, held=True):
            if row in moved:
                raise ConfigError(
                    f"transporter {t.id!r} holds {row[0]} at {row[1]}, which another population "
                    "moves: a held row is moved by nothing (one writer)"
                )
    return PopulationAxis(out)


def _end_node(t, end):
    """The node of a population's law end (N or P)."""
    n_node, p_node = (t.inside, t.outside) if t.n_end == "a" else (t.outside, t.inside)
    return n_node if end == "N" else p_node


def _rows(t, *, held):
    """(species, node ID) of a population's held rows (held=True) or moved rows (held=False)."""
    form, roles = cycle_form(t.law), dict(t.roles)
    counts = _counts(form, dict(t.parameters))
    out = []
    for k, (role, end) in enumerate(form.rows):
        if ((role, end) in t.held_rows) != held:
            continue
        if not held and not counts[:, k].any():
            continue  # A row the law reads but never changes is not moved.
        out.append((roles[role], _end_node(t, end)))
    return out


def _population_dict(t):
    if t.source is not None:  # Declared in today's keys: written back in them.
        return to_dict((t.source,))[0]
    return dict(
        id=t.id,
        host=t.host,
        law=t.law,
        orientation={"N": t.n_end},
        capacity_fmol_s=t.capacity_fmol_s,
        roles=dict(t.roles),
        parameters=dict(t.parameters),
        held_rows=[list(row) for row in t.held_rows],
    )


def declared_fields(entry):
    """The kind's fields for its structure entry (§7.4 (n) 5): version 1's for today's entry, with
    the population axis's own hooks absent; the population axis's for CycleAxis."""
    if isinstance(entry, CycleAxis):
        layout = GENERAL_LAYOUT_FIELDS + (MONOMIAL_FIELDS if _declares_monomial(entry) else ())
        return KindFields(
            GENERAL_STATE_AXES, layout, GENERAL_CONTROL_FIELDS, GENERAL_READOUT_COLUMNS
        )
    return KindFields(STATE_AXES, LAYOUT_FIELDS, CONTROL_FIELDS, READOUT_COLUMNS, POPULATION_HOOKS)


def _declares_monomial(entry):
    """Whether a declared law of the population axis runs the monomial form (K6)."""
    hosted = hosted_laws()
    found = (getattr(hosted.get(qualified(law)), "cycle", None) for law in entry.laws)
    return any(form is not None and form.kinetics == "monomial" for form in found)


def _mono(p):
    """Static: whether the layout holds the monomial form's fields (a declared monomial law)."""
    return "cycle_mono_log_k" in type(p)._fields


# ---------------------------------------------------------------------------- its layout


def _potential(spec, species):
    found = species_registry.standard_potential(spec, species)
    return None if found is None else found[0]


def _c0(spec):
    registry = species_registry.declared(spec)
    return None if registry is None else registry.standard_concentration_mM


def _standard_part(spec, roles, rows, counts, mask):
    """sum_s Delta_s (mu°_s/RT - ln c0) over the species whose net change over the masked rows is
    nonzero (math.fsum of the terms); 0 where none is."""
    net = {}
    for (role, _), n, keep in zip(rows, counts, mask, strict=True):
        if keep and n:
            net[roles[role]] = net.get(roles[role], 0) + int(n)
    terms = [n * (_potential(spec, s) - math.log(_c0(spec))) for s, n in net.items() if n]
    return math.fsum(terms)


def _population_initial(spec, declaration):
    """The population axis's state (zeros) and layout arrays (module section's fields)."""
    m = spec.model
    ids = list(m.species_ids)
    valence = dict(zip(m.species_ids, m.valence, strict=True))
    hosted = hosted_laws()
    laws = [hosted[t.law] for t in declaration]
    # Each population's form, its named rates resolved with its own values (forms.resolved).
    all_forms = [
        forms.resolved(law.cycle, dict(t.parameters))
        for law, t in zip(laws, declaration, strict=True)
    ]
    P = len(declaration)
    K = max(len(f.rows) for f in all_forms)
    M = max(len(f.modes) for f in all_forms)
    v = dict(
        cycle_host=np.zeros(P, dtype=np.int64),
        cycle_present=np.ones(P, dtype=bool),
        cycle_n_at_b=np.zeros(P, dtype=bool),
        cycle_capacity_fmol_s=np.zeros(P),
        cycle_form=np.zeros(P, dtype=np.int64),
        cycle_row_species=np.zeros((K, P), dtype=np.int64),
        cycle_row_at_n=np.zeros((K, P), dtype=bool),
        cycle_row_present=np.zeros((K, P), dtype=bool),
        cycle_row_held=np.zeros((K, P), dtype=bool),
        cycle_row_charged=np.zeros((K, P), dtype=bool),
        cycle_nu=np.zeros((M, K, P)),
        cycle_mode_present=np.zeros((M, P), dtype=bool),
        cycle_standard_RT=np.zeros((M, P)),
        cycle_charge_moved=np.zeros((M, P)),
        cycle_moved_standard_RT=np.zeros((M, P)),
        cycle_held_standard_RT=np.zeros((M, P)),
    )
    patches = [p.id for p in m.membranes]
    resolved = []
    for j, (t, form) in enumerate(zip(declaration, all_forms, strict=True)):
        values, roles = dict(t.parameters), dict(t.roles)
        counts, saturation, bands = forms.resolve(form, values)
        resolved.append((counts, saturation, bands))
        v["cycle_host"][j] = patches.index(t.host)  # A patch's host-table row is its slot.
        v["cycle_n_at_b"][j] = t.n_end == "b"
        v["cycle_capacity_fmol_s"][j] = t.capacity_fmol_s
        v["cycle_form"][j] = FORM_CODES[form.kinetics]
        held = [row in t.held_rows for row in form.rows]
        for k, (role, end) in enumerate(form.rows):
            v["cycle_row_species"][k, j] = ids.index(roles[role])
            v["cycle_row_at_n"][k, j] = end == "N"
            v["cycle_row_present"][k, j] = True
            v["cycle_row_held"][k, j] = held[k]
            v["cycle_row_charged"][k, j] = valence[roles[role]] != 0
        for mm, row_counts in enumerate(counts):
            v["cycle_nu"][mm, : len(form.rows), j] = row_counts
            v["cycle_mode_present"][mm, j] = True
            v["cycle_charge_moved"][mm, j] = sum(
                valence[roles[r]] * int(n) for (r, e), n in zip(form.rows, row_counts) if e == "P"
            )
            everything = [True] * len(form.rows)
            v["cycle_standard_RT"][mm, j] = _standard_part(spec, roles, form.rows, row_counts, everything)
            v["cycle_moved_standard_RT"][mm, j] = _standard_part(
                spec, roles, form.rows, row_counts, [not h for h in held]
            )
            v["cycle_held_standard_RT"][mm, j] = _standard_part(spec, roles, form.rows, row_counts, held)
    # Factored forms: their Hill factors, padded to the most factors of any mode.
    width = max((len(f) for _, sat, _ in resolved for f in sat), default=0)
    width = width if any(f.kinetics == "factored" for f in all_forms) else 0
    for name, dtype in (("row", np.int64), ("log_k", float), ("hill", float), ("present", bool)):
        v[f"cycle_sat_{name}"] = np.zeros((M, width, P), dtype=dtype)
    for j, (form, (_, sat, _)) in enumerate(zip(all_forms, resolved, strict=True)):
        if form.kinetics != "factored":
            continue
        for mm, factors in enumerate(sat):
            for f, (row, k_mM, hill) in enumerate(factors):
                v["cycle_sat_row"][mm, f, j] = row
                v["cycle_sat_log_k"][mm, f, j] = math.log(k_mM)
                v["cycle_sat_hill"][mm, f, j] = hill
                v["cycle_sat_present"][mm, f, j] = True
    bands = max((len(b) for *_, b in resolved), default=0)
    for name, dtype in (("row", np.int64), ("center", float), ("width", float), ("present", bool)):
        v[f"cycle_band_{name}"] = np.zeros((bands, P), dtype=dtype)
    for j, (*_, band_list) in enumerate(resolved):
        for b, (row, center, band) in enumerate(band_list):
            v["cycle_band_row"][b, j] = row
            v["cycle_band_center"][b, j] = center
            v["cycle_band_width"][b, j] = band
            v["cycle_band_present"][b, j] = True
    v |= _diagram_layout(declaration, all_forms, K, M)
    v |= _net_flow_layout(spec, declaration, all_forms, K, M)
    if any(f.kinetics == "monomial" for f in all_forms):  # declared_fields' test (K6).
        v |= _monomial_layout(spec, declaration, all_forms, v, M)
    state = dict(
        cycle_count=np.zeros((M, P)),
        cycle_dissipated_energy_pJ=np.zeros(P),
        cycle_metabolic_work_pJ=np.zeros(P),
        cycle_supplied_fmol=np.zeros((len(ids), P)),
    )
    return state, v


def _diagram_layout(declaration, all_forms, K, M):
    """The diagram forms' tables (forms.diagram_tables), padded across populations; zero-size
    where no population runs a diagram, so the diagram's code is not traced."""
    P = len(declaration)
    tables = [forms.diagram_tables(f) if f.kinetics == "diagram" else None for f in all_forms]
    used = [x for x in tables if x is not None]
    names = {f"cycle_dg_{name}" for name in DIAGRAM_FIELDS}
    if not used:
        shapes = dict(
            log_k0=(0, P), orders=(0, K, P), zeta=(0, P), term_slots=(0, 0, P), term_root=(0, P),
            term_present=(0, P), term_orders=(0, K, P), term_zeta=(0, P), plus_slots=(M, 0, P),
            minus_slots=(M, 0, P), plus_orders=(M, K, P), plus_zeta=(M, P), cut_slots=(M, 0, 0, P),
            cut_present=(M, 0, P), cut_orders=(M, 0, K, P), cut_zeta=(M, 0, P),
            edge_states=(0, 2, P), edge_present=(0, P), state_present=(0, P), log_scale=(P,),
            ln_standard=(P,),
        )  # fmt: skip
        ints = {"term_slots", "term_root", "plus_slots", "minus_slots", "cut_slots", "edge_states"}
        bools = {"term_present", "cut_present", "edge_present", "state_present"}
        out = {}
        for name, shape in shapes.items():
            dtype = np.int64 if name in ints else bool if name in bools else float
            out[f"cycle_dg_{name}"] = np.zeros(shape, dtype=dtype)
        assert set(out) == names
        return out
    E = max(len(x.edge_states) for x in used)
    D = 2 * E + 1
    T = max(len(x.term_root) for x in used)
    J = max(x.term_slots.shape[1] for x in used)
    L = max(x.plus_slots.shape[1] for x in used)
    C = max(x.cut_slots.shape[1] for x in used)
    I = max(x.cut_slots.shape[2] for x in used)
    S = max(len(f.diagram.states) for f in all_forms if f.kinetics == "diagram")
    zero = D - 1
    o = dict(
        log_k0=np.zeros((D, P)), orders=np.zeros((D, K, P)), zeta=np.zeros((D, P)),
        term_slots=np.full((T, J, P), zero, dtype=np.int64), term_root=np.zeros((T, P), dtype=np.int64),
        term_present=np.zeros((T, P), dtype=bool), term_orders=np.zeros((T, K, P)),
        term_zeta=np.zeros((T, P)), plus_slots=np.full((M, L, P), zero, dtype=np.int64),
        minus_slots=np.full((M, L, P), zero, dtype=np.int64), plus_orders=np.zeros((M, K, P)),
        plus_zeta=np.zeros((M, P)), cut_slots=np.full((M, C, I, P), zero, dtype=np.int64),
        cut_present=np.zeros((M, C, P), dtype=bool), cut_orders=np.zeros((M, C, K, P)),
        cut_zeta=np.zeros((M, C, P)), edge_states=np.zeros((E, 2, P), dtype=np.int64),
        edge_present=np.zeros((E, P), dtype=bool), state_present=np.zeros((S, P), dtype=bool),
        log_scale=np.zeros(P), ln_standard=np.zeros(P),
    )  # fmt: skip
    for j, (form, x) in enumerate(zip(all_forms, tables, strict=True)):
        if x is None:
            continue
        e = len(x.edge_states)
        remap = np.concatenate([np.arange(e), E + np.arange(e), [zero]])  # This law's slots.
        k = len(form.rows)
        o["log_k0"][remap, j] = x.log_k0
        o["orders"][remap, :k, j] = x.orders
        o["zeta"][remap, j] = x.zeta
        t_n, j_n = x.term_slots.shape
        o["term_slots"][:t_n, :j_n, j] = remap[x.term_slots]
        o["term_root"][:t_n, j] = x.term_root
        o["term_present"][:t_n, j] = True
        m_n, l_n = x.plus_slots.shape
        o["plus_slots"][:m_n, :l_n, j] = remap[x.plus_slots]
        o["minus_slots"][:m_n, :l_n, j] = remap[x.minus_slots]
        c_n, i_n = x.cut_slots.shape[1:]
        o["cut_slots"][:m_n, :c_n, :i_n, j] = remap[x.cut_slots]
        o["cut_present"][:m_n, :c_n, j] = x.cut_present
        o["edge_states"][:e, :, j] = x.edge_states
        o["edge_present"][:e, j] = True
        o["state_present"][: len(form.diagram.states), j] = True
        o["log_scale"][j] = math.log(form.diagram.rate_scale_per_s)
        o["ln_standard"][j] = math.log(form.diagram.standard_state_mM)
        # Each directional-diagram term's exponents: the sum of its edge directions' (static).
        o["term_orders"][:, :, j] = entity_sum(
            o["orders"][o["term_slots"][:, :, j], :, j], axis=1, xp=np
        )
        o["term_zeta"][:, j] = entity_sum(o["zeta"][o["term_slots"][:, :, j], j], axis=1, xp=np)
        o["plus_orders"][:, :, j] = entity_sum(
            o["orders"][o["plus_slots"][:, :, j], :, j], axis=1, xp=np
        )
        o["plus_zeta"][:, j] = entity_sum(o["zeta"][o["plus_slots"][:, :, j], j], axis=1, xp=np)
        o["cut_orders"][:, :, :, j] = entity_sum(
            o["orders"][o["cut_slots"][:, :, :, j], :, j], axis=2, xp=np
        )
        o["cut_zeta"][:, :, j] = entity_sum(o["zeta"][o["cut_slots"][:, :, :, j], j], axis=2, xp=np)
    out = {f"cycle_dg_{name}": value for name, value in o.items()}
    assert set(out) == names
    return out


def cited_offset(constant):
    """A CitedConstant's temperature-free part in RT units, its scalar protons' nu_H ln 10^7: the
    seam-E entry's dG_RT_offset."""
    return constant.protons * math.log(1e7)


def cited_dg_RT(spec, constant):
    """A CitedConstant's dG°/RT at the world's temperature, computed as the species registry
    converts the law's seam-E entry (1000 dG / (R T) + dG_RT_offset, in Decimal, rounded once), so
    k and the entry carry one value (the lead's ruling 7)."""
    rt = Decimal(R) * Decimal(spec.model.temperature_K)
    return float(Decimal(constant.dg_kj_mol) * 1000 / rt + Decimal(cited_offset(constant)))


def cited_log_k(spec, constant):
    """A CitedConstant's log k at the world's temperature: offset - scale dG°/RT, its dG°/RT the
    seam-E entry's (cited_dg_RT). A number is its own log k."""
    if not isinstance(constant, forms.CitedConstant):
        return float(constant)
    return constant.offset - constant.scale * cited_dg_RT(spec, constant)


def _closure_rows(model):
    """{(species, node ID)} of the rows a declared general closure holds (its declaration's
    closure_rows): where a named form or a total may be read (the binding owner's condition 2)."""
    return {
        (row[0], row[1])
        for _, declaration in getattr(model, "kinds", ())
        for row in getattr(declaration, "closure_rows", ())
    }


def monomial_reader(spec, t, form, slots):
    """read(reference) for population t (forms.expand_rate's reader): each reference as monomials
    of free slots, a species at an end, registered in `slots` {(species index, "N"|"P"): index}.
    "free" (or the species' own ID) is its free slot; a registry form or "total" resolves through
    the species registry's form_log_constants only (the binding owner's conditions: a declared
    form, where a closure holds the row, beta from the registry alone), each form f as
    a_base beta_f prod a_L^n_L (c°/c0)^(sum n_L), its ligands' free slots at the same end."""
    m = spec.model
    ids, roles = list(m.species_ids), dict(t.roles)
    node = {"N": t.inside if t.n_end == "a" else t.outside}
    node["P"] = t.outside if t.n_end == "a" else t.inside
    held = _closure_rows(m)
    ln_std = math.log(form.monomial.standard_state_mM)
    where = f"transporter {t.id!r}"

    def slot(species, end):
        return slots.setdefault((ids.index(species), end), len(slots))

    def read(reference):
        species, end = roles[reference.role], reference.end
        if reference.form in ("free", species):
            return (forms.Monomial(0.0, ((slot(species, end), 1.0),)),)
        if (species, node[end]) not in held:
            raise ConfigError(
                f"{where}: {reference.form} of {species} at {node[end]} is read only where a "
                "closure holds the row; elsewhere the stored row is the total, with no speciation"
            )
        found = species_registry.forms_of(spec, species)  # Refuses a row with no declared forms.
        logs, c0 = species_registry.form_log_constants(spec, species)
        shift = ln_std - math.log(c0)

        def monomial(i):
            counts = found[i][1]
            terms = ((slot(species, end), 1.0), *((slot(lig, end), float(n)) for lig, n in counts))
            return forms.Monomial(logs[i] + sum(n for _, n in counts) * shift, terms)

        if reference.form == "total":
            return tuple(monomial(i) for i in range(len(found)))
        named = [f[0] for f in found]
        if reference.form not in named[1:]:
            raise ConfigError(f"{where}: {species} declares no form {reference.form!r}")
        return (monomial(named.index(reference.form)),)

    return read


def monomial_expanded(spec, t, form):
    """Population t's monomial rates over its free slots: ([ExpandedRate per mode], slots), each
    refusal a ConfigError naming the population (the parse's check and the layout share it)."""
    slots = {}
    read = monomial_reader(spec, t, form, slots)
    expanded = []
    for rate in form.monomial.rates:
        try:
            expanded.append(forms.expand_rate(rate, read, cited_log_k(spec, rate.log_k)))
        except ValueError as error:
            raise ConfigError(f"transporter {t.id!r}: {error}") from None
    return expanded, slots


def _monomial_layout(spec, declaration, all_forms, v, M):
    """The monomial form's fields (MONOMIAL_FIELDS), padded across populations; zeros where a
    population runs another form."""
    P = len(declaration)
    built = []
    for t, form in zip(declaration, all_forms, strict=True):
        if form.kinetics != "monomial":
            built.append(None)
            continue
        expanded, slots = monomial_expanded(spec, t, form)
        built.append((forms.monomial_tables(expanded, len(slots)), slots, form))
    used = [b for b in built if b is not None]
    R = max(len(b[1]) for b in used)
    Q = max(b[0].power.shape[1] for b in used)
    G = max(b[0].term_log_k.shape[2] for b in used)
    o = dict(
        cycle_mono_slot_species=np.zeros((R, P), dtype=np.int64),
        cycle_mono_slot_at_n=np.zeros((R, P), dtype=bool),
        cycle_mono_slot_present=np.zeros((R, P), dtype=bool),
        cycle_mono_slot_row=np.zeros((R, P), dtype=np.int64),
        cycle_mono_slot_is_row=np.zeros((R, P), dtype=bool),
        cycle_mono_log_k=np.zeros((M, P)), cycle_mono_orders=np.zeros((M, R, P)),
        cycle_mono_zeta=np.zeros((M, P)), cycle_mono_power=np.zeros((M, Q, P)),
        cycle_mono_term_log_k=np.zeros((M, Q, G, P)), cycle_mono_term_q=np.zeros((M, Q, G, R, P)),
        cycle_mono_term_eta=np.zeros((M, Q, G, P)),
        cycle_mono_term_present=np.zeros((M, Q, G, P), dtype=bool),
        cycle_mono_share=np.ones((M, P), dtype=np.int64), cycle_mono_ln_standard=np.zeros(P),
    )  # fmt: skip
    for j, b in enumerate(built):
        if b is None:
            continue
        tables, slots, form = b
        rows = {
            (int(v["cycle_row_species"][k, j]), "N" if v["cycle_row_at_n"][k, j] else "P"): k
            for k in range(len(form.rows))
        }
        for (species, end), r in slots.items():
            o["cycle_mono_slot_species"][r, j] = species
            o["cycle_mono_slot_at_n"][r, j] = end == "N"
            o["cycle_mono_slot_present"][r, j] = True
            if (species, end) in rows:
                o["cycle_mono_slot_row"][r, j] = rows[(species, end)]
                o["cycle_mono_slot_is_row"][r, j] = True
        m_n, r_n = tables.orders.shape
        q_n, g_n = tables.term_log_k.shape[1:]
        o["cycle_mono_log_k"][:m_n, j] = tables.log_k
        o["cycle_mono_orders"][:m_n, :r_n, j] = tables.orders
        o["cycle_mono_zeta"][:m_n, j] = tables.zeta
        o["cycle_mono_power"][:m_n, :q_n, j] = tables.power
        o["cycle_mono_term_log_k"][:m_n, :q_n, :g_n, j] = tables.term_log_k
        o["cycle_mono_term_q"][:m_n, :q_n, :g_n, :r_n, j] = tables.term_q
        o["cycle_mono_term_eta"][:m_n, :q_n, :g_n, j] = tables.term_eta
        o["cycle_mono_term_present"][:m_n, :q_n, :g_n, j] = tables.term_present
        o["cycle_mono_share"][:m_n, j] = tables.share
        o["cycle_mono_ln_standard"][j] = math.log(form.monomial.standard_state_mM)
    return o


def _net_flow_layout(spec, declaration, all_forms, K, M):
    """The net-flow forms' terms, padded across populations; zero-size where none runs one."""
    P = len(declaration)
    U = max((len(terms) for f in all_forms if f.kinetics == "net_flow" for terms in f.flux_terms), default=0)
    o = dict(
        weight=np.zeros((M, U, P)), counts=np.zeros((M, U, K, P)), standard_RT=np.zeros((M, U, P)),
        charge=np.zeros((M, U, P)), shift=np.zeros((M, U, P)), present=np.zeros((M, U, P), dtype=bool),
    )  # fmt: skip
    valence = dict(zip(spec.model.species_ids, spec.model.valence, strict=True))
    for j, (t, form) in enumerate(zip(declaration, all_forms, strict=True)):
        if form.kinetics != "net_flow":
            continue
        roles = dict(t.roles)
        for mm, terms in enumerate(form.flux_terms):
            for u, term in enumerate(terms):
                o["weight"][mm, u, j] = term.weight
                o["counts"][mm, u, : len(form.rows), j] = term.counts
                o["standard_RT"][mm, u, j] = _standard_part(
                    spec, roles, form.rows, term.counts, [True] * len(form.rows)
                )
                o["charge"][mm, u, j] = sum(
                    valence[roles[r]] * n for (r, e), n in zip(form.rows, term.counts) if e == "P"
                )
                o["shift"][mm, u, j] = term.shift
                o["present"][mm, u, j] = True
    return {f"cycle_nf_{name}": value for name, value in o.items()}


def _diagram_view(p):
    return SimpleNamespace(**{name: getattr(p, f"cycle_dg_{name}") for name in DIAGRAM_FIELDS})


# ---------------------------------------------------------------------------- its stage


class Evaluation(NamedTuple):
    """The population axis at one stage (statement 1, §4): every quantity its hooks project."""

    ln_c: object  # [K, P] (mM)
    c: object  # [K, P] (mM)
    row_node: object  # [K, P]
    psi: object  # [P]
    x: object  # [M, P]: Delta G / RT
    x_terms: object  # [M, P]: X, the absolute sum of x's terms
    held_x: object  # [M, P]: the held rows' part of x
    log_s: object  # [M, P]
    j_plus: object  # [M, P]
    j_minus: object  # [M, P]
    j: object  # [M, P]
    scale: object  # [M, P]: Phi, the one-way scale (a net-flow mode's sum_t k a |w_t| (1 + e^y_t))
    y_terms: object  # [M, P]: Y, the net-flow arguments' largest absolute sum (0 elsewhere)
    d_j_d_psi: object  # [M, P]
    d_j_d_ln_c: object  # [M, K, P]
    diagram: object  # forms.DiagramLogs, or None
    active: object  # [P]
    # [P]: the solver's switch, k > 0, a > 0 and active (its host active, itself present); J is
    # zero elsewhere.
    enabled: object
    valid: object  # [P]: the domain at the stage
    guard: object  # [P]: G = sum_m J x (RT fmol/s)
    allowance: object  # [P]: A (statement 1, §5.2, amendment 2)


def _evaluate(read, potentials, control, p, *, xp):
    """The population axis's one evaluation (statement 1, §4): rates, stage_term, material_term,
    readouts and probe are projections of it."""
    from cells.modules import host_table, node_concentrations

    table = host_table(p, xp=xp)
    host = p.cycle_host
    active = table.active[host] & p.cycle_present  # Its host active, and itself present (Q2).
    a_node, b_node = table.end_a[host], table.end_b[host]
    n_node = xp.where(p.cycle_n_at_b, b_node, a_node)
    p_node = xp.where(p.cycle_n_at_b, a_node, b_node)
    row_node = xp.where(p.cycle_row_at_n, n_node[None, :], p_node[None, :])
    conc = node_concentrations(read, p, xp=xp)
    c = conc[p.cycle_row_species, row_node]
    present = p.cycle_row_present
    positive = xp.isfinite(c) & (c > 0)
    ln_c = xp.where(present, xp.log(xp.where(present & positive, c, 1.0)), 0.0)
    rt = R * p.temperature
    if potentials is None:
        v_np = xp.zeros(host.shape)
    else:
        v_np = potentials[n_node] - potentials[p_node]
    psi = (F / rt) * v_np
    modes = p.cycle_mode_present
    nu = p.cycle_nu
    q = p.cycle_charge_moved
    x = p.cycle_standard_RT + entity_sum(nu * ln_c[None], axis=1, xp=xp) - q * psi[None, :]
    x = xp.where(modes, x, 0.0)
    x_terms = (
        xp.abs(p.cycle_standard_RT)
        + entity_sum(xp.abs(nu) * (xp.abs(ln_c[None]) + 1.0), axis=1, xp=xp)
        + xp.abs(q * psi[None, :])
    )
    held_rows = p.cycle_row_held[None]
    held_x = p.cycle_held_standard_RT + entity_sum(
        xp.where(held_rows, nu * ln_c[None], 0.0), axis=1, xp=xp
    )
    k, a = p.cycle_capacity_fmol_s, control.cycle_availability
    enabled = (k > 0) & (a > 0) & active
    log_ka = xp.log(xp.where(enabled, k, 1.0)) + xp.log(xp.where(enabled, a, 1.0))
    form = p.cycle_form[None, :]
    log_s = xp.zeros(x.shape)
    d_log_s = xp.zeros(nu.shape)
    d_log_s_psi = xp.zeros(x.shape)
    valid = xp.ones(host.shape, dtype=bool)
    if p.cycle_sat_row.shape[1]:  # Static: a factored form is declared.
        ls, grad = forms.hill_log_saturation(
            p.cycle_sat_row, p.cycle_sat_log_k, p.cycle_sat_hill, p.cycle_sat_present, ln_c, xp=xp
        )
        factored = form == FORM_CODES["factored"]
        log_s = xp.where(factored, ls, log_s)
        d_log_s = xp.where(factored[:, None, :], grad, d_log_s)
    diagram = None
    if p.cycle_dg_log_k0.shape[0]:  # Static: a diagram form is declared.
        diagram = forms.diagram_logs(_diagram_view(p), ln_c, psi, xp=xp)
        is_diagram = form == FORM_CODES["diagram"]
        log_s = xp.where(is_diagram, diagram.log_s, log_s)
        d_log_s = xp.where(is_diagram[:, None, :], diagram.d_log_s_d_ln_c, d_log_s)
        d_log_s_psi = xp.where(is_diagram, diagram.d_log_s_d_psi, d_log_s_psi)
    slots_ok = True
    if _mono(p):  # Static: a monomial form is declared (K6).
        slot_node = xp.where(p.cycle_mono_slot_at_n, n_node[None, :], p_node[None, :])
        c_slot = conc[p.cycle_mono_slot_species, slot_node]  # [R, P], free (the stage's read)
        live = p.cycle_mono_slot_present
        slot_positive = xp.isfinite(c_slot) & (c_slot > 0)
        ln_c_slot = xp.log(xp.where(live & slot_positive, c_slot, 1.0))
        ln_a = xp.where(live, ln_c_slot - p.cycle_mono_ln_standard[None, :], 0.0)
        table = SimpleNamespace(
            **{n: getattr(p, f"cycle_mono_{n}") for n in forms.MonomialTables._fields}
        )
        mono = forms.monomial_logs(table, ln_a, psi, x, xp=xp)
        is_mono = form == FORM_CODES["monomial"]
        on_rows = forms.slots_on_rows(
            mono.d_ln_a, p.cycle_mono_slot_row, p.cycle_mono_slot_is_row, nu.shape[1], xp=xp
        )  # Slopes on rows by (species, node); the share's d/dx carries dx/d ln c = nu.
        log_s = xp.where(is_mono, mono.log_s, log_s)
        d_log_s = xp.where(is_mono[:, None, :], on_rows + mono.d_x[:, None, :] * nu, d_log_s)
        d_log_s_psi = xp.where(is_mono, mono.d_psi - q * mono.d_x, d_log_s_psi)  # dx/dpsi = -q
        slots_ok = xp.all(xp.where(live, slot_positive, True), axis=0)
    on = modes & enabled[None, :]
    log_plus = log_ka[None, :] + log_s
    j_fd = xp.where(on, forms.sign_exact_flux(log_plus, x, xp=xp), 0.0)
    j_plus = xp.where(on, xp.exp(log_plus), 0.0)
    j_minus = xp.where(on, xp.exp(log_plus + x), 0.0)
    j = j_fd
    scale = j_plus + j_minus
    d_j_d_psi = j * d_log_s_psi + q * j_minus
    d_j_d_ln_c = j[:, None, :] * d_log_s - j_minus[:, None, :] * nu
    y_terms = xp.zeros(x.shape)
    terms_count = xp.ones(x.shape)
    if p.cycle_nf_weight.shape[1]:  # Static: a net-flow form is declared.
        nf = SimpleNamespace(**{n: getattr(p, f"cycle_nf_{n}") for n in NET_FLOW_FIELDS})
        y = (
            nf.standard_RT
            + entity_sum(nf.counts * ln_c[None, None], axis=2, xp=xp)
            - nf.charge * psi[None, None, :]
            + nf.shift * psi[None, None, :]
        )  # [M, U, P]
        y_abs = (
            xp.abs(nf.standard_RT)
            + entity_sum(xp.abs(nf.counts) * (xp.abs(ln_c[None, None]) + 1.0), axis=2, xp=xp)
            + xp.abs(nf.charge * psi[None, None, :])
            + xp.abs(nf.shift * psi[None, None, :])
        )
        ka = xp.exp(log_ka)[None, None, :]
        weight = xp.where(nf.present & on[:, None, :], nf.weight * ka, 0.0)
        e_y = xp.exp(xp.where(nf.present, y, 0.0))
        j_nf = entity_sum(weight * -xp.expm1(xp.where(nf.present, y, 0.0)), axis=1, xp=xp)
        phi_nf = entity_sum(xp.abs(weight) * (1.0 + e_y), axis=1, xp=xp)  # Each term's own scale.
        flow = form == FORM_CODES["net_flow"]
        j = xp.where(flow, j_nf, j)
        scale = xp.where(flow, phi_nf, scale)
        d_j_d_psi = xp.where(
            flow, entity_sum(weight * e_y * (nf.charge - nf.shift), axis=1, xp=xp), d_j_d_psi
        )
        d_j_d_ln_c = xp.where(
            flow[:, None, :],
            -entity_sum(weight[:, :, None, :] * e_y[:, :, None, :] * nf.counts, axis=1, xp=xp),
            d_j_d_ln_c,
        )  # fmt: skip
        y_terms = xp.where(flow, xp.max(xp.where(nf.present, y_abs, 0.0), axis=1), y_terms)
        counted = xp.maximum(entity_sum(nf.present, axis=1, xp=xp), 1)
        terms_count = xp.where(flow, counted, terms_count)
        j_plus = xp.where(flow, xp.nan, j_plus)
        j_minus = xp.where(flow, xp.nan, j_minus)
    # The domain at the stage: positive finite reads, |x| <= 80, the declared pH bands, finite
    # kinetics; only where the population's host is active (an inactive host moves nothing).
    rows_ok = xp.all(xp.where(present, positive, True), axis=0)
    within = xp.abs(x) <= MAX_ABS_AFFINITY_OVER_RT
    if _mono(p):  # Static (K6): the monomial form's domain is one-sided, x <= 80.
        within = xp.where(form == FORM_CODES["monomial"], x <= MAX_ABS_AFFINITY_OVER_RT, within)
    x_ok = xp.all(xp.where(modes, within, True), axis=0)
    finite = xp.all(xp.where(on, xp.isfinite(j) & xp.isfinite(scale), True), axis=0)
    if p.cycle_band_row.shape[0]:  # Static: a pH band is declared.
        cols = xp.arange(host.shape[0])
        ph = (LN_PH_STANDARD - ln_c[p.cycle_band_row, cols[None, :]]) * INV_LN10
        inside = xp.abs(ph - p.cycle_band_center) <= p.cycle_band_width
        bands_ok = xp.all(xp.where(p.cycle_band_present, inside, True), axis=0)
    else:
        bands_ok = True
    ok = rows_ok & x_ok & finite & bands_ok
    if _mono(p):  # Static: a world without the monomial form keeps today's program.
        ok = ok & slots_ok
    valid = xp.where(active, ok, True)
    # The guard (statement 1, §5.2; amendment 2): G = sum_m J x <= A.
    guard = entity_sum(j * x, axis=0, xp=xp)
    rows_count = entity_sum(present, axis=0, xp=xp)[None, :]
    mode_count = entity_sum(modes, axis=0, xp=xp)[None, :]
    coefficient = (rows_count + 10.0) * x_terms + (
        terms_count + mode_count + 12.0 + (rows_count + 11.0) * y_terms
    ) * xp.abs(x)
    allowance = forms.UNIT_ROUNDOFF * entity_sum(
        xp.where(on, scale * coefficient, 0.0), axis=0, xp=xp
    )
    valid = valid & xp.where(active, guard <= allowance, True)
    return Evaluation(
        ln_c, c, row_node, psi, x, x_terms, held_x, log_s, j_plus, j_minus, j, scale, y_terms,
        d_j_d_psi, d_j_d_ln_c, diagram, active, enabled, valid, guard, allowance,
    )  # fmt: skip


def _flat_scatter(values, species, nodes, shape, *, xp):
    """values [K, P] summed into [species, node] at (species [K, P], node [K, P])."""
    return scatter(values, xp.zeros(shape), (species, nodes), xp=xp)


def _population_rates(state, potentials, control, p, *, xp):
    from cells.modules import KindRates

    e = _evaluate(state, potentials, control, p, xp=xp)
    n, o = p.active.size, p.outside_active.size
    species = state.amount_increment.shape[0]
    moved = p.cycle_row_present & ~p.cycle_row_held
    row_rate = xp.where(moved, entity_sum(p.cycle_nu * e.j[:, None, :], axis=0, xp=xp), 0.0)
    nodes = _flat_scatter(row_rate, p.cycle_row_species, e.row_node, (species, n + o), xp=xp)
    rt = R * p.temperature
    heat = -1e-3 * rt * entity_sum(e.j * e.x, axis=0, xp=xp)
    work = -1e-3 * rt * entity_sum(e.j * e.held_x, axis=0, xp=xp)
    stored = 1e-3 * rt * entity_sum(e.j * p.cycle_moved_standard_RT, axis=0, xp=xp)
    held = p.cycle_row_present & p.cycle_row_held
    supply_rows = xp.where(held, -entity_sum(p.cycle_nu * e.j[:, None, :], axis=0, xp=xp), 0.0)
    cols = xp.broadcast_to(xp.arange(supply_rows.shape[-1])[None, :], supply_rows.shape)
    supply = scatter(supply_rows, xp.zeros((species, supply_rows.shape[-1])), (p.cycle_row_species, cols), xp=xp)
    at_p = moved & ~p.cycle_row_at_n
    outward = xp.where(p.cycle_n_at_b, -1.0, 1.0)[None, :]
    crossing = xp.where(at_p, row_rate * outward, 0.0)
    hosts = xp.broadcast_to(p.cycle_host[None, :], crossing.shape)
    flux = scatter(
        crossing, xp.zeros((species, p.membrane_active.size)), (p.cycle_row_species, hosts), xp=xp
    )
    return KindRates(
        cell=nodes[:, :n],
        outside=nodes[:, n:],
        derivatives=dict(
            cycle_count=e.j,
            cycle_dissipated_energy_pJ=heat,
            cycle_metabolic_work_pJ=work,
            cycle_supplied_fmol=supply,
        ),
        heat_pJ_s=heat,
        work_pJ_s=work,
        membrane_flux=flux,
        valid=xp.all(e.valid),
        stored_pJ_s=stored,
    )


def _population_readouts(read, potentials, control, p, *, xp):
    e = _evaluate(read, potentials, control, p, xp=xp)
    rt = R * p.temperature
    modes = p.cycle_mode_present & e.active[None, :]  # An absent population reads zero (Q2).
    return (
        xp.where(modes, e.j, 0.0),
        xp.where(modes, rt * e.x, 0.0),
        xp.where(modes, rt * e.held_x, 0.0),
    )


def _conductance(e, p, *, xp):
    """[P] each population's |dI/dV| (S), I its current a to b and V = phi_a - phi_b."""
    rt = R * p.temperature
    total = entity_sum(p.cycle_charge_moved * e.d_j_d_psi, axis=0, xp=xp)
    return CHARGE_PER_FMOL * (F / rt) * xp.abs(total)


def _population_stage_term(read, potentials, control, p, *, xp):
    """[cells, then outside nodes] each population's conductance at both ends of its host. Called
    bare (no potentials), at zero voltage and at each mode's static head, x = 0: dJ/dpsi = q J+.
    A charged monomial population (K6) has no voltage-free bound there, since its S reads psi, so
    the bare term fails closed for it: +inf (FR-15 P2's ruling for a potential-free path)."""
    from cells.modules import host_node_conductance

    e = _evaluate(read, potentials, control, p, xp=xp)
    if potentials is None:  # Each factored or diagram mode at its static head, x = 0.
        flow = p.cycle_form[None, :] == FORM_CODES["net_flow"]
        at_head = p.cycle_charge_moved * xp.where(flow, 0.0, e.j_plus)
        e = e._replace(d_j_d_psi=xp.where(flow, e.d_j_d_psi, at_head))
    slope = xp.where(e.active, _conductance(e, p, xp=xp), 0.0)
    if potentials is None and _mono(p):  # Static (K6).
        charged = xp.any(p.cycle_mode_present & (p.cycle_charge_moved != 0), axis=0)
        bare = (p.cycle_form == FORM_CODES["monomial"]) & charged & e.active
        slope = xp.where(bare, xp.inf, slope)
    return host_node_conductance(slope, p.cycle_host, p, xp=xp)


def material_term(read, potentials, control, p, *, xp):
    """[cells, then outside nodes] the kind's material slope (1/s; D4): per node, the largest over
    the neutral moved rows there of sum over populations and modes of |nu dJ/dn| (statement 1, §2:
    an upper bound of the row's own slope even where modes add). Version 1's entry has none."""
    e = _evaluate(read, potentials, control, p, xp=xp)
    n, o = p.active.size, p.outside_active.size
    volume = xp.concatenate((xp.where(p.active, p.volume, 1.0), xp.where(p.outside_active, p.extracellular_volume, 1.0)))
    amount = e.c * volume[e.row_node]  # [K, P] fmol
    neutral = p.cycle_row_present & ~p.cycle_row_held & ~p.cycle_row_charged
    per_row = entity_sum(xp.abs(p.cycle_nu * e.d_j_d_ln_c), axis=0, xp=xp)  # [K, P] fmol/s per ln c
    slope = xp.where(neutral & (amount > 0), per_row / xp.where(amount > 0, amount, 1.0), 0.0)
    if potentials is None and _mono(p):  # Static (K6): S reads psi, so no bound without it.
        bare = (p.cycle_form == FORM_CODES["monomial"])[None, :] & neutral & e.active[None, :]
        slope = xp.where(bare, xp.inf, slope)
    species = read.amount_increment.shape[0]
    nodes = _flat_scatter(slope, p.cycle_row_species, e.row_node, (species, n + o), xp=xp)
    return xp.max(nodes, axis=0)


def _population_ledger_terms(state, p, *, xp):
    n, o = p.active.size, p.outside_active.size
    species = state.amount_increment.shape[0]
    from cells.modules import host_table

    table = host_table(p, xp=xp)
    host = p.cycle_host
    n_node = xp.where(p.cycle_n_at_b, table.end_b[host], table.end_a[host])
    p_node = xp.where(p.cycle_n_at_b, table.end_a[host], table.end_b[host])
    row_node = xp.where(p.cycle_row_at_n, n_node[None, :], p_node[None, :])
    moved = p.cycle_row_present & ~p.cycle_row_held
    counted = entity_sum(p.cycle_nu * state.cycle_count[:, None, :], axis=0, xp=xp)
    rows = xp.where(moved, counted, 0.0)
    nodes = _flat_scatter(rows, p.cycle_row_species, row_node, (species, n + o), xp=xp)
    produced = entity_sum(nodes, axis=1, xp=xp)
    rt = R * p.temperature
    stored = 1e-3 * rt * entity_sum(state.cycle_count * p.cycle_moved_standard_RT, axis=0, xp=xp)
    return dict(
        cell=nodes[:, :n],
        outside=nodes[:, n:],
        produced=produced,
        heat_pJ=state.cycle_dissipated_energy_pJ,
        work_pJ=state.cycle_metabolic_work_pJ,
        stored_pJ=stored,
    )


def _population_domain(state, p, *, xp):
    """The population axis's own fields: finite, and exact zeros where they do not apply (an
    absent mode's cycles, a population that holds no row's work, a species it does not hold)."""
    valid = xp.all(xp.isfinite(state.cycle_count)) & xp.all(xp.where(p.cycle_mode_present, True, state.cycle_count == 0))
    for name in ("cycle_dissipated_energy_pJ", "cycle_metabolic_work_pJ"):
        valid = valid & xp.all(xp.isfinite(getattr(state, name)))
    holds = xp.any(p.cycle_row_present & p.cycle_row_held, axis=0)
    valid = valid & xp.all(xp.where(holds, True, state.cycle_metabolic_work_pJ == 0))
    record = state.cycle_supplied_fmol
    rows = xp.arange(record.shape[0])[:, None, None]
    held = (rows == p.cycle_row_species[None]) & (p.cycle_row_present & p.cycle_row_held)[None]
    held = xp.any(held, axis=1)  # [S, P]
    return valid & xp.all(xp.isfinite(record)) & xp.all(xp.where(held, True, record == 0))


def _population_bound_rate(spec, declaration):
    """B7's definition-time term on the population axis: as version 1's, for each factored
    population with a charged mode, (F/RT) CHARGE sum_m q_m^2 k S_max_m at the free nodes among its
    host's ends, over each node's capacitance; S_max takes a held row's saturation at its declared
    amount and every other factor at 1, availability and e^x at most 1. Each saturation is taken
    in log space, -log(1 + e^(h ln(K/c))), so a steep factor's (K/c)^h never overflows: where it
    would, the population's term is e^(-huge) = 0."""
    m = spec.model
    ids = list(m.species_ids)
    valence = dict(zip(m.species_ids, m.valence, strict=True))
    nodes = {node.id: node for node in (*m.cells, *m.extracellular)}
    held_bath = {o.id for o in m.extracellular if o.reservoir}
    faced = {f.sender for f in m.faces} | {f.receiver for f in m.faces}
    capacitance, conductance = {}, {}
    for patch in m.membranes:
        for node in (patch.inside, patch.outside):
            capacitance[node] = capacitance.get(node, 0.0) + patch.capacitance_F
    for t in declaration:
        form = cycle_form(t.law)
        if form.kinetics != "factored":
            continue
        roles = dict(t.roles)
        counts, saturation, _ = forms.resolve(form, dict(t.parameters))
        slope = 0.0
        for mm, row_counts in enumerate(counts):
            q = sum(valence[roles[r]] * int(n) for (r, e), n in zip(form.rows, row_counts) if e == "P")
            if not q:
                continue
            log_s = 0.0
            for row, k_mM, hill in saturation[mm]:
                if form.rows[row] in t.held_rows:
                    role, end = form.rows[row]
                    node = nodes[_end_node(t, end)]
                    c = node.initial_amount_fmol[ids.index(roles[role])] / node.volume_pL
                    # In log space, as the rate path (probe) is: (K/c)^h can overflow a float.
                    log_s -= float(np.logaddexp(0.0, hill * (math.log(k_mM) - math.log(c))))
            slope += q * q * F / (R * m.temperature_K) * CHARGE_PER_FMOL * t.capacity_fmol_s * math.exp(log_s)
        for node in (t.inside, t.outside):
            if slope and node not in held_bath and node not in faced:
                conductance[node] = conductance.get(node, 0.0) + slope
    return max((g / capacitance[node] for node, g in conductance.items()), default=0.0)


# ---------------------------------------------------------------------------- its checks


class CycleCheck(NamedTuple):
    """One population's mode at parse (statement 1, §4): its charge sum, the charge it moves N to P,
    and, for a diagram's cycle, Wegscheider's record (forms.Wegscheider)."""

    population: str
    mode: str
    charge_sum: int
    charge_moved: int
    wegscheider: object  # forms.Wegscheider, or None
    admitted: bool


def cycle_checks(spec):
    """Every population's modes checked at the engine's potentials (statement 1, §4, §5.1)."""
    declaration = dict(spec.model.kinds)[KIND_ID]
    valence = dict(zip(spec.model.species_ids, spec.model.valence, strict=True))
    out = []
    for t in declaration:
        form = forms.resolved(cycle_form(t.law), dict(t.parameters))  # Its declared rates.
        roles = dict(t.roles)
        counts = _counts(form, dict(t.parameters))
        for mm, ((mode, _), row_counts) in enumerate(zip(form.modes, counts, strict=True)):
            charge = sum(valence[roles[r]] * int(n) for (r, _), n in zip(form.rows, row_counts))
            moved = sum(valence[roles[r]] * int(n) for (r, e), n in zip(form.rows, row_counts) if e == "P")
            record = None
            if form.kinetics == "diagram":
                z = {role: valence[roles[role]] for role in form.role_names}
                mu = {role: _potential(spec, roles[role]) for role in form.role_names}
                record = forms.wegscheider(form, mm, z, mu, _c0(spec) or 1.0)
            ok = charge == 0 and (record is None or record.admitted)
            out.append(CycleCheck(t.id, mode, charge, moved, record, ok))
    return tuple(out)


def _check_population_axis(spec, declaration):
    """The population axis's refusals at the definition: a registry potential for every species a
    mode converts, the form's temperature domain, §5.2's boundary for moved fuel, Wegscheider's
    condition on every diagram cycle (statement 1, §5.1), and every monomial reference resolving
    under the binding owner's three conditions (K6), each naming the population."""
    m = spec.model
    from cells.modules import moved_nodes

    movers = moved_nodes(m)
    kinds = dict(m.kinds)
    closure = kinds.get("cells.rapid_proton_buffer@1")
    proton = getattr(closure, "proton", None)  # The closure's declared proton row, if any; else
    if proton is None:  # the row named H, as in a world with no closure (never skipped).
        proton = "H" if "H" in m.species_ids else None
    picked = dict(getattr(m, "heat_bookings", ())).get(KIND_ID)
    if picked == TRAPEZOID_BOOKING:  # K2: the booking's contract, a non-negative power per state.
        for t in declaration:
            if cycle_form(t.law).kinetics == "net_flow":
                raise ConfigError(
                    f"transporter {t.id!r}: {TRAPEZOID_BOOKING} books a non-negative power at each "
                    "state, which a net-flow population keeps only within its guard's allowance: "
                    "refused (its heat stays on the tableau's booking)"
                )
    for t in declaration:
        where = f"transporter {t.id!r}"
        form, roles = cycle_form(t.law), dict(t.roles)
        if form.kinetics == "monomial":  # K6: each reference resolves, or the parse refuses.
            monomial_expanded(spec, t, forms.resolved(form, dict(t.parameters)))
        counts = _counts(form, dict(t.parameters))
        stoichiometries = [*counts, *(term.counts for terms in form.flux_terms for term in terms)]
        for row_counts in stoichiometries:
            net = {}
            for (role, _), n in zip(form.rows, row_counts):
                net[roles[role]] = net.get(roles[role], 0) + int(n)
            for species, n in net.items():
                if n and _potential(spec, species) is None:
                    raise ConfigError(
                        f"{where}: {species} declares no standard potential (standard_mu_RT) in the "
                        "species registry; a mode's free energy comes from the registry only"
                    )
        if form.temperature_K is not None:
            low, high = form.temperature_K
            if not low <= m.temperature_K <= high:
                raise ConfigError(f"{where}: {t.law} runs between {low} and {high} K")
        fuel = [row for row in form.rows if row[0] in form.fuel_roles and row not in t.held_rows]
        for role, end in fuel:
            node = _end_node(t, end)
            if proton is not None and movers.get((proton, node)) and node not in _general_closure_nodes(m):
                raise ConfigError(
                    f"{where}: its fuel row {roles[role]} moves at {node}, whose proton row {proton} "
                    "is moved in the step: finite fuel at a node with a dynamic proton row is refused "
                    "(§5.2's boundary)"
                )
    laws = {t.id: t.law for t in declaration}
    for check in cycle_checks(spec):
        if not check.admitted:
            w, law = check.wegscheider, laws[check.population]
            form = cycle_form(law)
            _, signed = form.diagram.cycles[[m for m, _ in form.modes].index(check.mode)]
            edges = ", ".join(e for e, _ in signed)
            raise ConfigError(
                f"transporter {check.population!r} ({law}): mode {check.mode}, its cycle through "
                f"{edges}, fails Wegscheider's condition at the registry's potentials and its "
                f"declared rates (coefficients {w.coefficients}, psi {float(w.psi):.3e} against "
                f"{float(w.psi_band):.3e}, constant {float(w.constant):.3e} against "
                f"{float(w.band):.3e}): refused, never repaired (§16)"
            )


def _general_closure_nodes(model):
    """The nodes a general binding closure holds (seam C, none yet): §5.2's one exception."""
    del model
    return ()


# ---------------------------------------------------------------------------- the probe (§19 item 1)


class CycleProbe(NamedTuple):
    """The population axis's contents at one state (statement 1, §4), each [.., population]."""

    modes: object  # SimpleNamespace of [M, P] arrays
    edges: object  # SimpleNamespace of [E, P] arrays, or None
    occupancy: object  # [S, P], or None
    rows: object  # SimpleNamespace of [K, P] arrays
    populations: object  # SimpleNamespace of [P] arrays


def probe(read, potentials, control, p, *, xp=np):
    """Every quantity of §19 item 1 at a state, from the run's own evaluation (statement 1, §4),
    in either layout: version 1's gives one mode per patch (its membrane slots) and no diagram."""
    if MARK not in type(p)._fields:
        return _version_1_probe(read, potentials, control, p, xp=xp)
    e = _evaluate(read, potentials, control, p, xp=xp)
    rt = R * p.temperature
    nan = xp.nan
    flow = p.cycle_form[None, :] == FORM_CODES["net_flow"]
    sign = xp.where(p.cycle_n_at_b, -1.0, 1.0)  # dpsi/dV, V = phi_a - phi_b
    d_j_d_v = e.d_j_d_psi * (F / rt) * sign[None, :]
    modes = SimpleNamespace(
        present=p.cycle_mode_present, x=e.x, x_terms=e.x_terms, log_s=xp.where(flow, nan, e.log_s),
        s=xp.where(flow, nan, xp.exp(e.log_s)), j_plus=e.j_plus, j_minus=e.j_minus, j=e.j,
        scale=e.scale, d_j_d_v=d_j_d_v, pi_plus=None, pi_minus=None, share=None, j_minus_diagram=None,
    )  # fmt: skip
    edges = occupancy = None
    if e.diagram is not None:
        d = e.diagram
        is_diagram = p.cycle_form[None, :] == FORM_CODES["diagram"]
        modes.pi_plus = xp.where(is_diagram, xp.exp(d.log_plus), nan)
        modes.pi_minus = xp.where(is_diagram, xp.exp(d.log_minus), nan)
        modes.share = xp.where(is_diagram, xp.exp(d.log_share), nan)
        carriers = xp.exp(xp.log(xp.maximum(p.cycle_capacity_fmol_s * control.cycle_availability, 1e-300)) - p.cycle_dg_log_scale)
        carriers = xp.where(e.enabled, carriers, 0.0)  # The solver's switch: off carries nothing.
        modes.j_minus_diagram = xp.where(is_diagram, carriers[None] * xp.exp(d.log_minus + d.log_share), nan)
        n_edges = p.cycle_dg_edge_present.shape[0]
        cols = xp.arange(p.cycle_host.shape[0])
        forward = xp.exp(d.log_rates[:n_edges])
        backward = xp.exp(d.log_rates[n_edges : 2 * n_edges])
        source, target = p.cycle_dg_edge_states[:, 0], p.cycle_dg_edge_states[:, 1]
        p_from = d.occupancy[source, cols[None, :]]
        p_to = d.occupancy[target, cols[None, :]]
        edges = SimpleNamespace(
            present=p.cycle_dg_edge_present, alpha_fwd=forward, alpha_bwd=backward,
            oneway_fwd=p_from * forward, oneway_bwd=p_to * backward,
            net_fmol_s=carriers[None] * (p_from * forward - p_to * backward),
        )  # fmt: skip
        occupancy = d.occupancy
    moved = p.cycle_row_present & ~p.cycle_row_held
    held = p.cycle_row_present & p.cycle_row_held
    change = entity_sum(p.cycle_nu * e.j[:, None, :], axis=0, xp=xp)
    volume = xp.concatenate((xp.where(p.active, p.volume, 1.0), xp.where(p.outside_active, p.extracellular_volume, 1.0)))
    amount = e.c * volume[e.row_node]
    per_mode = p.cycle_nu * e.d_j_d_ln_c / xp.where(amount > 0, amount, 1.0)[None]
    rows = SimpleNamespace(
        species=p.cycle_row_species, at_n=p.cycle_row_at_n, held=p.cycle_row_held,
        present=p.cycle_row_present, rate=xp.where(moved, change, 0.0),
        held_supply=xp.where(held, -change, 0.0),
        self_slope=xp.where(moved, entity_sum(per_mode, axis=0, xp=xp), 0.0),
        max_mode_slope=xp.where(moved, xp.max(xp.abs(per_mode), axis=0), 0.0),
    )  # fmt: skip
    charge = entity_sum(p.cycle_charge_moved * e.j, axis=0, xp=xp) * sign
    populations = SimpleNamespace(
        heat_pJ_s=-1e-3 * rt * entity_sum(e.j * e.x, axis=0, xp=xp),
        work_pJ_s=-1e-3 * rt * entity_sum(e.j * e.held_x, axis=0, xp=xp),
        stored_pJ_s=1e-3 * rt * entity_sum(e.j * p.cycle_moved_standard_RT, axis=0, xp=xp),
        charge_a_to_b_fmol_s=charge, current_a_to_b_pA=1e12 * CHARGE_PER_FMOL * charge,
        conductance_pS=1e12 * _conductance(e, p, xp=xp), guard=e.guard, allowance=e.allowance,
        valid=e.valid,
    )  # fmt: skip
    return CycleProbe(modes, edges, occupancy, rows, populations)


def _version_1_probe(read, potentials, control, p, *, xp):
    """The probe on version 1's layout (one mode per patch, rows role@N, role@P and the fuel at N):
    J, x, heat and work from version 1's own kinetics, J+ = k a S from the law's saturation (both of
    version 1's laws share its form), J- = J+ e^x, and the proton law's conductance from its kernel.
    It reports; it books nothing."""
    rt = R * p.temperature
    if potentials is None:
        potentials = xp.zeros(p.active.size + p.outside_active.size)
    a = control.transporter_availability
    cycles, energy, drive, valid = kinetics(read, potentials, a, p, xp=xp)
    c_in, c_out, fuel = gather(read, p, xp=xp)
    n = p.transporter_stoichiometry
    present = p.transporter_present
    log_s = -xp.logaddexp(0.0, n * (xp.log(p.transporter_km_role_mM) - xp.log(xp.where(present, c_in, 1.0))))
    log_s = log_s - xp.logaddexp(0.0, xp.log(p.transporter_km_atp_mM) - xp.log(xp.where(present, fuel[0], 1.0)))
    k = p.transporter_capacity_fmol_s
    on = present & (k > 0) & (a > 0)
    log_plus = xp.log(xp.where(on, k, 1.0)) + xp.log(xp.where(on, a, 1.0)) + log_s
    x = xp.where(present, energy / rt, 0.0)
    j_plus = xp.where(on, xp.exp(log_plus), 0.0)
    j_minus = xp.where(on, xp.exp(log_plus + x), 0.0)
    if p.transporter_proton.shape[-1]:  # Static: the proton law moves one charge per proton.
        q = xp.where(p.transporter_proton, n, 0.0)
    else:
        q = xp.zeros_like(n)
    voltage = patch_voltage(potentials, p, xp=xp)
    ln_c = (xp.log(xp.where(present, c_in, 1.0)), xp.log(xp.where(present, c_out, 1.0)), *(xp.log(xp.where(present, f, 1.0)) for f in fuel))
    x_terms = xp.abs(p.transporter_drive0_J_mol / rt) + n * (xp.abs(ln_c[0]) + xp.abs(ln_c[1]) + 2.0)
    x_terms = x_terms + sum(xp.abs(v) + 1.0 for v in ln_c[2:]) + xp.abs(q * (F / rt) * voltage)
    modes = SimpleNamespace(
        present=present[None], x=x[None], x_terms=x_terms[None], log_s=log_s[None],
        s=xp.exp(log_s)[None], j_plus=j_plus[None], j_minus=j_minus[None], j=cycles[None],
        scale=(j_plus + j_minus)[None], d_j_d_v=(j_minus * q * F / rt)[None], pi_plus=None,
        pi_minus=None, share=None, j_minus_diagram=None,
    )  # fmt: skip
    zero = xp.zeros_like(cycles)
    rows = SimpleNamespace(
        present=xp.broadcast_to(present, (5, present.size)),
        held=xp.stack([xp.zeros_like(present), xp.zeros_like(present), *(p.transporter_held,) * 3]),
        rate=xp.stack([-n * cycles, n * cycles, zero, zero, zero]),
        held_supply=xp.stack([zero, zero, xp.where(p.transporter_held, cycles, 0.0),
                              xp.where(p.transporter_held, -cycles, 0.0),
                              xp.where(p.transporter_held, -cycles, 0.0)]),
    )  # fmt: skip
    if p.transporter_proton.shape[-1]:
        i, qp = proton_law(c_in, c_out, voltage, fuel, p, xp=xp)
        conductance = xp.where(p.transporter_proton, proton.electrogenic_conductance_S(i, qp, a, xp=xp), 0.0)
    else:
        conductance = zero
    guard = cycles * x
    coefficient = 15.0 * x_terms + 14.0 * xp.abs(x)  # K = 5 rows, M = T = 1 (statement 1, §5.2)
    populations = SimpleNamespace(
        heat_pJ_s=-1e-3 * cycles * energy, work_pJ_s=xp.where(p.transporter_held, -1e-3 * cycles * drive, 0.0),
        stored_pJ_s=zero, charge_a_to_b_fmol_s=q * cycles,
        current_a_to_b_pA=1e12 * CHARGE_PER_FMOL * q * cycles, conductance_pS=1e12 * conductance,
        guard=guard, allowance=forms.UNIT_ROUNDOFF * (j_plus + j_minus) * coefficient, valid=valid,
    )  # fmt: skip
    return CycleProbe(modes, None, None, rows, populations)


def view_sets(spec, declaration):
    """The population axis's own sets (D154): one entry per population, with its law, its host, its
    orientation and each mode's per-cycle changes per species and end; none for version 1."""
    if not isinstance(declaration, PopulationAxis):
        return {}
    populations, per_cycle = [], []
    for t in declaration:
        form, roles = cycle_form(t.law), dict(t.roles)
        counts = _counts(form, dict(t.parameters))
        per_cycle.append(
            [
                {
                    "mode": mode,
                    "changes": [
                        {"species": roles[r], "end": e, "per_cycle": int(n)}
                        for (r, e), n in zip(form.rows, row_counts)
                        if n
                    ],
                }
                for (mode, _), row_counts in zip(form.modes, counts, strict=True)
            ]
        )
        populations.append(t)
    modes = max(len(cycle_form(t.law).modes) for t in declaration)
    return {
        "cycle_population": {
            "id": "cycle_population",
            "ids": [t.id for t in populations],
            "roles": {
                "N": "the population's N end, at its host's end a or b (orientation)",
                "P": "its P end, the host's other end",
            },
            "kinds": ["cycle" for _ in populations],
            "laws": [{"law_id": t.law} for t in populations],
            "at": [{"membrane": t.host} for t in populations],
            "orientation": [{"N": t.n_end} for t in populations],
            "per_cycle": per_cycle,
        },
        "cycle_mode": {
            "id": "cycle_mode",
            "ids": [f"mode_{k}" for k in range(modes)],
            "roles": {},
        },
    }


# The run view's declarations (D154; kind_registry.KindView, the core's 74a75241). A positive cycle
# moves n of the role from the patch's cell to its outside node (ledger_terms: the role's rows
# lose n x cycles at the cell and gain them at the outside node). The fuel record is left
# unoriented on purpose: its rows change at the fuel node, not across the patch.
_CYCLES = MappingProxyType(
    {
        "from": "inside",
        "to": "outside",
        "says": "a positive cycle moves n (the stoichiometry) of the role from the patch's cell to "
        "its outside node; held fuel's maintenance restores its ATP "
        "(transporter_fuel_supplied_fmol)",
    }
)
_MODES = MappingProxyType(
    {
        "from": "N",
        "to": "P",
        "says": "a positive count is a mode's forward cycles, each changing the population's rows by "
        "its per-cycle counts (the population set's per_cycle), from its N end towards its P end; "
        "held rows' maintenance restores them (cycle_supplied_fmol)",
    }
)
VIEW = KindView(
    units=MappingProxyType(
        {
            "transporter_cycles": "fmol",
            "transporter_dissipated_energy_pJ": "pJ",
            "transporter_metabolic_work_pJ": "pJ",
            "transporter_fuel_supplied_fmol": "fmol",
            "transporter_cycle_rate_fmol_s": "fmol/s",
            "transporter_cycle_free_energy_J_mol": "J/mol",
            "transporter_chemical_drive_J_mol": "J/mol",
            # The population axis's (each present only where a structure holds it).
            "cycle_count": "fmol",
            "cycle_dissipated_energy_pJ": "pJ",
            "cycle_metabolic_work_pJ": "pJ",
            "cycle_supplied_fmol": "fmol",
            "cycle_rate_fmol_s": "fmol/s",
            "cycle_free_energy_J_mol": "J/mol",
            "cycle_held_drive_J_mol": "J/mol",
        }
    ),
    observation_axes=MappingProxyType(
        {c: ("membrane_slot",) for c in READOUT_COLUMNS}
        | {c: ("cycle_mode", "cycle_population") for c in GENERAL_READOUT_COLUMNS}
    ),
    record_kinds=MappingProxyType(
        {
            "transporter_cycles": "cumulative",
            "transporter_dissipated_energy_pJ": "cumulative",
            "transporter_metabolic_work_pJ": "cumulative",
            "transporter_fuel_supplied_fmol": "cumulative",
            "transporter_cycle_rate_fmol_s": "rate",
            "transporter_cycle_free_energy_J_mol": "level",
            "transporter_chemical_drive_J_mol": "level",
            "cycle_count": "cumulative",
            "cycle_dissipated_energy_pJ": "cumulative",
            "cycle_metabolic_work_pJ": "cumulative",
            "cycle_supplied_fmol": "cumulative",
            "cycle_rate_fmol_s": "rate",
            "cycle_free_energy_J_mol": "level",
            "cycle_held_drive_J_mol": "level",
        }
    ),
    orientation=MappingProxyType(
        {
            "transporter_cycles": _CYCLES,
            "transporter_cycle_rate_fmol_s": _CYCLES,
            "cycle_count": _MODES,
            "cycle_rate_fmol_s": _MODES,
        }
    ),
    record_layers=MappingProxyType(
        dict.fromkeys(
            (
                *(f for f, _ in STATE_AXES),
                *READOUT_COLUMNS,
                *(f for f, _ in GENERAL_STATE_AXES),
                *GENERAL_READOUT_COLUMNS,
            ),
            "pumps",
        )
    ),
)


# ---------------------------------------------------------------------------- the lifecycle's declarations
# Item 3, B1's kind-side roles (CORE_SEAMS §4.2 and §18's B1 lift; the lead's rulings of 18 and 19
# November 2026): every field of both layouts declares its partition role (F's PartitionRole) and
# its axes, and the population axis names its host. They are read on the host only, so no program
# changes; a kind beside a closer stays refused until the core gates its rates by its host's
# activity (B1's third step). Structural fields fill with the layout's own padding (version 1's
# saturation constants and stoichiometry pad with 1, the population axis's slots and indices with
# 0, which its presence masks keep out of every sum). The law-internal axes (modes, rows, Hill
# factors, bands, a diagram's edge directions, edges and terms, a net-flow law's terms) are
# declared as they are, pending F's internal_axes (the lead's answer of 19 November), which B2's
# own-axis maps honour: they are copied whole at a split and never hosted. Version 1's per-law
# masks have the slot axis, or size 0 where their law is undeclared (the static dispatch).
_STRUCTURAL = {
    "transporter_present": False,
    "transporter_neutral": False,
    "transporter_proton": False,
    "transporter_role": 0,
    "transporter_fuel_rows": 0,
    "transporter_held": False,
    "transporter_stoichiometry": 1.0,
    "transporter_km_role_mM": 1.0,
    "transporter_km_atp_mM": 1.0,
    MARK: 0,
    "cycle_present": False,
    "cycle_n_at_b": False,
    "cycle_form": 0,
    "cycle_row_species": 0,
    "cycle_row_at_n": False,
    "cycle_row_present": False,
    "cycle_row_held": False,
    "cycle_row_charged": False,
    "cycle_nu": 0,
    "cycle_mode_present": False,
    "cycle_sat_row": 0,
    "cycle_sat_present": False,
    "cycle_band_row": 0,
    "cycle_band_present": False,
    **{f"cycle_dg_{n}": 0 for n in ("term_slots", "term_root", "plus_slots", "minus_slots")},
    **{f"cycle_dg_{n}": 0 for n in ("cut_slots", "edge_states")},
    **{f"cycle_dg_{n}": False for n in ("term_present", "cut_present", "edge_present")},
    "cycle_dg_state_present": False,
    "cycle_nf_counts": 0,
    "cycle_nf_present": False,
    "cycle_mono_slot_species": 0,
    "cycle_mono_slot_at_n": False,
    "cycle_mono_slot_present": False,
    "cycle_mono_slot_row": 0,
    "cycle_mono_slot_is_row": False,
    "cycle_mono_term_present": False,
    "cycle_mono_share": 1,
}
_EXTENSIVE = ("transporter_capacity_fmol_s", "cycle_capacity_fmol_s")
_PER_ENTITY = (
    *LAYOUT_FIELDS, *CONTROL_FIELDS, *GENERAL_LAYOUT_FIELDS, *MONOMIAL_FIELDS,
    *GENERAL_CONTROL_FIELDS,
)  # fmt: skip
PARTITION_ROLES = MappingProxyType(
    {
        **{name: PartitionRole("history") for name, _ in (*STATE_AXES, *GENERAL_STATE_AXES)},
        **{name: PartitionRole("structural", fill) for name, fill in _STRUCTURAL.items()},
        **{name: PartitionRole("extensive") for name in _EXTENSIVE},
        **{
            name: PartitionRole("intensive")
            for name in _PER_ENTITY
            if name not in _STRUCTURAL and name not in _EXTENSIVE
        },
    }
)
POPULATION_AXIS = "cycle_population"
_AXIS = MappingProxyType(  # The population axis's shapes' letters (GENERAL_LAYOUT_FIELDS' notes).
    {
        "P": POPULATION_AXIS,
        "M": "cycle_mode",
        "K": "cycle_row",
        "F": "cycle_saturation",
        "B": "cycle_band",
        "D": "cycle_direction",
        "T": "cycle_term",
        "J": "cycle_term_edge",
        "L": "cycle_mode_edge",
        "C": "cycle_cut",
        "I": "cycle_cut_edge",
        "E": "cycle_edge",
        "X": "cycle_edge_end",
        "S": "cycle_state",
        "U": "cycle_flux_term",
        "R": "cycle_read",  # The monomial form's free slots (K6).
        "Q": "cycle_mono_factor",
        "G": "cycle_mono_term",
    }
)
_SHAPES = {
    MARK: "P", "cycle_present": "P", "cycle_n_at_b": "P", "cycle_capacity_fmol_s": "P", "cycle_form": "P",
    "cycle_row_species": "KP", "cycle_row_at_n": "KP", "cycle_row_present": "KP",
    "cycle_row_held": "KP", "cycle_row_charged": "KP", "cycle_nu": "MKP",
    "cycle_mode_present": "MP", "cycle_standard_RT": "MP", "cycle_charge_moved": "MP",
    "cycle_moved_standard_RT": "MP", "cycle_held_standard_RT": "MP",
    **{f"cycle_sat_{n}": "MFP" for n in ("row", "log_k", "hill", "present")},
    **{f"cycle_band_{n}": "BP" for n in ("row", "center", "width", "present")},
    "cycle_dg_log_k0": "DP", "cycle_dg_orders": "DKP", "cycle_dg_zeta": "DP",
    "cycle_dg_term_slots": "TJP", "cycle_dg_term_root": "TP", "cycle_dg_term_present": "TP",
    "cycle_dg_term_orders": "TKP", "cycle_dg_term_zeta": "TP", "cycle_dg_plus_slots": "MLP",
    "cycle_dg_minus_slots": "MLP", "cycle_dg_plus_orders": "MKP", "cycle_dg_plus_zeta": "MP",
    "cycle_dg_cut_slots": "MCIP", "cycle_dg_cut_present": "MCP", "cycle_dg_cut_orders": "MCKP",
    "cycle_dg_cut_zeta": "MCP", "cycle_dg_edge_states": "EXP", "cycle_dg_edge_present": "EP",
    "cycle_dg_state_present": "SP", "cycle_dg_log_scale": "P", "cycle_dg_ln_standard": "P",
    "cycle_nf_counts": "MUKP",
    **{f"cycle_nf_{n}": "MUP" for n in ("weight", "standard_RT", "charge", "shift", "present")},
    "cycle_availability": "P",
    **{f"cycle_mono_{n}": "RP" for n in ("slot_species", "slot_at_n", "slot_present", "slot_row")},
    "cycle_mono_slot_is_row": "RP", "cycle_mono_log_k": "MP", "cycle_mono_orders": "MRP",
    "cycle_mono_zeta": "MP", "cycle_mono_power": "MQP", "cycle_mono_term_log_k": "MQGP",
    "cycle_mono_term_q": "MQGRP", "cycle_mono_term_eta": "MQGP", "cycle_mono_term_present": "MQGP",
    "cycle_mono_share": "MP", "cycle_mono_ln_standard": "P",
}  # fmt: skip
FIELD_AXES = MappingProxyType(
    {
        **{name: ("membrane_slot",) for name in (*LAYOUT_FIELDS, *CONTROL_FIELDS)},
        "transporter_fuel_rows": ("transporter_fuel_role", "membrane_slot"),
        "transporter_c0_mM": (),  # One value: the registry's standard concentration.
        **{name: tuple(_AXIS[c] for c in letters) for name, letters in _SHAPES.items()},
    }
)
AXIS_HOSTS = MappingProxyType({POPULATION_AXIS: AxisHost("patch", MARK)})
# The laws' internal axes (F's internal_axes; the lead's Q5 answer): version 1's fuel roles and the
# population axis's own (every _AXIS letter but P), copied whole at a split and never hosted.
INTERNAL_AXES = ("transporter_fuel_role", *(axis for letter, axis in _AXIS.items() if letter != "P"))
# Q2's presence (F's presence; CORE_SEAMS §18): each entity axis's masks, every one its rates,
# readouts and stage terms read. Version 1's slots: its population's mask and its two law masks
# (each of size 0 where its law is undeclared). The population axis: each population's presence,
# anded into its host's activity in the one evaluation.
PRESENCE = MappingProxyType(
    {
        "membrane_slot": ("transporter_present", "transporter_neutral", "transporter_proton"),
        POPULATION_AXIS: ("cycle_present",),
    }
)


def standard_free_energies(declaration):
    """Seam E's kind hook (the lead's answer of 19 November): each diagram-form population's cycles'
    standard free energies implied by their own constants, as F's FreeEnergyEntry, in declared
    order, for each cycle that converts a species (forms.implied_free_energy): its stoichiometry
    over the species its roles bind, dG°/RT and c0 in mM, and the law and the mode of its form that
    produced it, so the binding owner's check computes its band from that form. The species
    registry's check compares each with its own sum of nu mu°/RT, as Wegscheider's condition did at
    parse. A monomial mode whose k is a CitedConstant (K6) and that converts a species gives its
    cited dG° the same way, in kJ/mol with its pH-7 offset (dG_kJ_mol, dG_basis and dG_RT_offset,
    F's form), at its form's standard state: the value k is built from (cited_dg_RT). Factored and
    net-flow laws have no constants of their own, and version 1's laws are factored: ()."""
    from cells.modules import TEMPERATURE_INDEPENDENT, FreeEnergyEntry

    if not isinstance(declaration, PopulationAxis):
        return ()
    hosted, out = hosted_laws(), []
    for t in declaration:
        form = forms.resolved(hosted[t.law].cycle, dict(t.parameters))  # Its declared rates.
        if form.kinetics == "monomial":
            roles = dict(t.roles)
            counts = _counts(form, dict(t.parameters))
            for (mode, _), rate, row_counts in zip(
                form.modes, form.monomial.rates, counts, strict=True
            ):
                if not isinstance(rate.log_k, forms.CitedConstant):
                    continue
                net = {}
                for (role, _), n in zip(form.rows, row_counts, strict=True):
                    net[roles[role]] = net.get(roles[role], 0) + int(n)
                stoichiometry = tuple((s, n) for s, n in net.items() if n)
                if stoichiometry:  # A pure transport mode converts nothing: no entry.
                    out.append(
                        FreeEnergyEntry(
                            stoichiometry,
                            c0=form.monomial.standard_state_mM,
                            law_id=t.law,
                            mode=mode,
                            dG_kJ_mol=rate.log_k.dg_kj_mol,
                            dG_basis=TEMPERATURE_INDEPENDENT,
                            dG_RT_offset=cited_offset(rate.log_k),
                        )
                    )
            continue
        if form.kinetics != "diagram":
            continue
        roles = dict(t.roles)
        for m, (mode, _) in enumerate(form.modes):
            net, value, c0 = forms.implied_free_energy(form, m)
            if net:
                stoichiometry = tuple((roles[r], n) for r, n in net.items())
                out.append(FreeEnergyEntry(stoichiometry, value, c0, law_id=t.law, mode=mode))
    return tuple(out)


TRANSPORTER = BUILTIN.register(
    Kind(
        kind_id=KIND_ID,
        model_key=MODEL_KEY,
        state_axes=STATE_AXES,
        layout_fields=LAYOUT_FIELDS,
        control_fields=CONTROL_FIELDS,
        readout_columns=READOUT_COLUMNS,
        parse=parse,
        to_dict=to_dict,
        structure_entry=structure_entry,
        initial=initial,
        control_values=control_values,
        experiment_keys=(SCHEDULE_KEY,),
        parse_schedule=parse_schedule,
        schedule_to_dict=schedule_to_dict,
        rates=rates,
        stage_term=stage_term,
        bound_rate=bound_rate,
        held_rows=held_rows,
        ledger_terms=ledger_terms,
        domain=domain,
        readouts=readouts,
        moved_rows=moved_rows,
        check_definition=check_definition,
        declared_fields=declared_fields,
        material_term=material_term,
        view=VIEW,
        view_sets=view_sets,
        partition_roles=PARTITION_ROLES,
        field_axes=FIELD_AXES,
        axis_hosts=AXIS_HOSTS,
        internal_axes=INTERNAL_AXES,
        presence=PRESENCE,
        standard_free_energies=standard_free_energies,
        role_species=role_species,
        # Version 1's per-law masks: full on the patches, or empty where their law is undeclared
        # (the static dispatch), which F's array-axes check admits for these alone.
        dispatch_masks=("transporter_neutral", "transporter_proton"),
        # Seam D (K2): the core's trapezoid books this kind's heat fields where a definition picks
        # it ({"cells.transporter@1": "trapezoid_nonnegative@1"} under heat_bookings).
        heat_bookings=(TRAPEZOID_BOOKING,),
    )
)
