"""cells.kind.passive_routes@1: the passive routes' insertion point, laws by contract (A5).

docs/INNER_MODEL_V4_DESIGN.md §7.4 (i), §7.5 (version 1, ruled), §11; the lead's scope ruling (15
November): one kind for passive routes, its laws by contract. The kernels are the FR-4/FR-5
owner's, called here and never edited:
- `cells.route.passive_neutral_permeation@1` (laws/routes/passive_permeation.py): a neutral species, Fick's law
  at valence 0, with §7.5's exact booking;
- `cells.route.proton_constant_field_leak@1` (laws/transport/proton_leak.py): an H+ constant-field route at
  valence +1 on a membrane patch, reading free h through the stage read (B4) at buffered nodes;
  tableau-booked (charged), with its slope conductance in the stage rule (B7) and its flux in the
  membrane current;
- `cells.route.proton_constant_field_leak@2` (laws/transport/proton_leak_v2.py; MT-1b's face plan, item 3):
  @1's kernel declared as a law that reads the general closure (cells.binding.rapid_binding@1), whose stage read
  writes free h into the held H row. It runs through @1's mask and fields (`passive_leak`), so it
  adds no field and gives @1's arithmetic on the same read. Its own refusal: an end at a node of
  B4's version-1 closure, whose free h @1 reads. At the general closure's rows the species
  registry's admission reads its declared read;
- `cells.route.inward_rectifier_linear_driving_force@1` (laws/routes/inward_rectifier_linear_driving_force.py,
  the kinds owner's; D228 item 2): an instantaneous inward rectifier at valence +1 on a membrane
  patch, I = m A g_ref (c_o/K_ref)^(1/2) q(V - E) (V - E); tableau-booked as the leak is, with
  its slope conductance's magnitude in the stage rule (it turns negative) and its flux in the
  membrane current. Its fields exist only in a definition that declares it (declared_fields), so
  a definition without it keeps today's fields and programs;
- `cells.route.passive_constant_field_permeation@1` (laws/routes/constant_field_permeation.py; FR-15 F2's
  P2, the lead's rulings of 19 November 2026, and its junction hosting, D310): a charged
  species' constant-field route at its own valence on a membrane patch or a junction, reading the
  row's amounts at both ends (the leak's flux at any z != 0); tableau-booked as the leak is. Its
  max-side slope conductance G joins the stage rule (2G at each cell on a junction, @3's own
  junction form), its material slopes the material rule (material_term: a charged trace row's
  bound, which @3's static bound cannot hold) and, on a patch, its flux the membrane current. A
  row whose free/total split a closure owns is refused on it (it reads amounts, not free forms),
  and so is a junction that joins two capacitor components where one floats (version 1, D310:
  the field solve's current balance there holds @3's own currents only). Its field, and its
  material_term, exist only in a definition that declares it (declared_fields), so a definition
  without it keeps today's fields and programs.

The declaration (model key `passive_routes`, FR-4's form in validation/compartment_ph_engine/
definitions.py), each route on one host (`patch`, or `junction` for the neutral and charged
laws):

    [{"id": "proton_leak_0", "patch": "bounding_0", "law": "cells.route.proton_constant_field_leak@1",
      "permeability_m_per_s": 6e-7},
     {"id": "cargo_0", "patch": "bounding_0", "law": "cells.route.passive_neutral_permeation@1",
      "species": "X", "permeability_m_per_s": 1e-9}]

`species` is the neutral law's carried row; the leak's is the proton row (`species`, default "H",
which must be B4's proton_row when B4 is declared). `factors` is a list of factor-source IDs
(§7.4 (n): FR-5's damage d and pH condition f), in declared order; omitted or empty, none.

The rectifier's route declares its coefficients in place of a permeability, and its carried row:

    {"id": "rectifier_0", "patch": "rectifier_patch_0",
     "law": "cells.route.inward_rectifier_linear_driving_force@1", "species": "K", "g_ref_S_per_m2": 1.0,
     "k_ref_mM": 5.0, "v_half_V": 0.01, "slope_V": 0.01}

each finite: g_ref >= 0 (0, a closed route), K_ref > 0, s > 0 and V_h any value. Its patch's own
permeability for the carried row is zero.

The kind finds its laws in the active law registry: the route laws it hosts, named as declared
(registry/laws.py; docs/CORE_SEAMS_DESIGN.md §8.3), never a module tuple. Each of its laws is
declared in its own module (§8.2). Version 1 runs each of its four by name (VERSION_1_LAWS), so it
refuses any other route law it hosts.

- **The routing door's sink (§7.4 (n) 6):** where any route declares factors, the kind's entry
  records it and its fields gain the control `passive_multiplier` [route], held at 1; each
  factored route's slot is routed (`routed_controls`), so at every stage it is the left fold of
  its sources' factors. Each route's opening is multiplied by it in rates and stage_term.
  Booking, its scope, bound_rate (m <= 1) and moved_rows are unchanged. A factored route that moves
  a row its own source reads closes a loop: the sink's feedback hooks (routed_rows and routed_flux;
  kind_registry.Kind) give the core its row and its routed flux, and the core bounds the loop. A
  definition whose routes declare no factors keeps today's entry, fields and programs.

- **The flux,** inward from the host's outside end (a patch's outside node, a junction's receiver)
  to its inside end (a patch's cell, a junction's sender), at every explicit stage, on the read
  amounts; the leak, the rectifier and the charged law at the host's voltage phi_in - phi_out (on
  a junction, phi_sender - phi_receiver). Its opening is the host's: a patch's availability, or a
  junction's gate times its availability.
- **One law per species and route:** the host route's own constant-field permeability for a
  carried species must be zero. The neutral law carries valence-0 species only; the leak and the
  rectifier a valence +1 row; the charged law a charged row (z != 0) that no closure holds. The
  rectifier's E reads both ends: the host's parse admits only positive initial amounts, and its
  domain hook keeps both positive and finite at every checked state.
- **Its own fields:** `passive_transferred` [species, route] (cumulative, inward) and
  `passive_dissipated_energy_pJ` [route]; both join @3's material and energy ledgers by role.
- **The booking (§7.5, version 1):** a neutral route whose every carried row (species, end node)
  is moved by passive routes alone (binding, from moved_nodes; a held bath's row is never one)
  books, per step, its exact divided-difference shares of each row's exact free-energy decrease:
  Q = -1e-3 RT moved (mu-bar_in - mu-bar_out) (the kernel's divided_potential_RT and
  route_heat_pJ). No clamp, no scaling: each share is booked as computed. A share below its
  floor, -RAW_SUM_FACTOR eps (|mu-bar_in| + |mu-bar_out| + 2) |moved| RT (negative beyond its own
  rounding, its potentials' evaluation rounding included: §7.5's sign rule, amended 17 November
  2026), or a row whose shares miss its exact decrease by more than RAW_SUM_FACTOR eps times its
  terms and its inputs' rounding (the stored amounts, increments and cumulative transfers times
  |mu-bar|: §7.5's raw-sum bound, amended 16 November 2026), refuses the step ("negative exact
  share: step-bound breach"). A share within
  its floor is booked too, so a route's heat may fall in a step by at most that rounding. Every
  other route, the leak and the rectifier always, keeps the tableau's booking of its dissipation
  rate (each kernel's heat_pJ_s, >= 0).
- **Its step (ruled):** the neutral law's dt L <= 1, L = 1e15 P A (1/V_a + 1/V_b) summed over
  the routes at each node, as its bound term (bound_rate); the leak's slope conductance (the
  kernel's conductance_S, max side) joins membrane_rate's per-stage refusal (stage_term), and so
  does the rectifier's |dI/dV| at the stage's potentials (slope_conductance_S), or, where
  membrane_rate has no potentials, its voltage-free bound at the stage's concentrations
  (slope_bound_S), and the charged law's max-side slope (its conductance_S), twice that at each
  cell on a junction (D310: a junction's charge mode relaxes at G (1/C_a + 1/C_b) <= 2G / min C,
  @3's own junction term). The charged law's material slopes (its material_slope_per_s, at the
  stage's amounts and potentials) are the kind's material_term, which membrane_rate's material
  counterpart holds to the same bound: at each end, both ends' slopes summed where the other end
  relaxes too (a cell, or a finite outside node: the Gershgorin row sum, the neutral law's form
  at zero voltage), its own where the other end is a held bath (D310).
- **FR-42's labels (D303 item 6; docs/NEUTRAL_LABELS_DESIGN.md §11):** the neutral, leak and
  charged kernels are linear in their two ends at a fixed voltage, so a route's one-way fluxes
  are its kernel with c_in = 0 (inward) and minus its kernel with c_out = 0 (outward)
  (one_way_fluxes). label_transfers reports them over the step, the trapezoid of its two ends
  plus the gap to passive_transferred; label_refusals refuses a labelled row a rectifier moves.
  Neither is traced without labels.
- **FR-50's one-way records** (D327; the registered protocol fr50-one-way-records-v1): a route asks
  with its optional key `"one_way": true`. Then the kind holds `passive_inward_fmol` and
  `passive_outward_fmol` [route], cumulative in fmol, and `passive_one_way_gap_relative` [route],
  the running maximum of each step's relative gap. Inward less outward is passive_transferred's
  change at the route's carried row, at rounding. @3's IMEX step books them by the shared rule
  (numerics/one_way_split.py) from the same kernels as the labels (record_fluxes; record_nets reads
  the net record), and a route that does not ask keeps zeros. The fields, the mask
  `passive_one_way` and both hooks exist only where a route asks (declared_fields), so a
  definition without the key keeps today's structure entry, fields and programs. A rectifier route
  that asks is refused: its flux reads both ends through E, so it has no one-way form.
"""

from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.laws.electrochemistry import CHARGE_PER_FMOL, R
from cells.laws.routes import constant_field_permeation as charged_law
from cells.laws.routes import inward_rectifier_linear_driving_force as rectifier
from cells.laws.routes import passive_permeation as passive
from cells.laws.transport import proton_leak as leak
from cells.laws.transport import proton_leak_v2 as leak_v2
from cells.modules import OneWayRecord, close_one_way, step_one_way_amounts
from cells.numerics.extracellular_field import scatter
from cells.numerics.species_sums import entity_sum, species_sum
from cells.registry import laws as law_registry
from cells.registry.kind_registry import BUILTIN, ConfigError, Kind, KindFields, KindView

KIND_ID = "cells.kind.passive_routes@1"
MODEL_KEY = "passive_routes"
LAW_ID = passive.LAW_ID  # The neutral law.
LEAK_LAW_ID = leak.LAW_ID  # The charged proton leak.
LEAK_V2_LAW_ID = leak_v2.LAW_ID  # Its version reading the general closure (MT-1b, item 3).
LEAK_LAWS = (LEAK_LAW_ID, LEAK_V2_LAW_ID)  # One kernel, one mask (passive_leak).
RECTIFIER_LAW_ID = rectifier.LAW_ID  # The inward rectifier (D228 item 2).
CHARGED_LAW_ID = charged_law.LAW_ID  # A charged species' constant-field route (FR-15 P2).
# Version 1 runs each by name (Route.law's dispatch).
VERSION_1_LAWS = (LAW_ID, LEAK_LAW_ID, RECTIFIER_LAW_ID, CHARGED_LAW_ID, LEAK_V2_LAW_ID)
# The kind's laws, each declared in its own module (CORE_SEAMS §8.2), where the law registry's
# loader registers them for the kind to find by interface and host.
NEUTRAL = passive.LAW
LEAK = leak.LAW
LEAK_V2 = leak_v2.LAW
RECTIFIER = rectifier.LAW
CHARGED = charged_law.LAW
DEFAULT_PROTON = "H"
RAW_SUM_FACTOR = 16.0  # §7.5: |sum of shares - exact decrease| <= 16 eps (own + inputs), per row.
NEGATIVE_SHARE = "negative exact share: step-bound breach"
HOSTS = ("patch", "junction")
MULTIPLIER = "passive_multiplier"  # The sink's control field (§7.4 (n) 6).
STATE_AXES = (
    ("passive_transferred", ("species", "passive_route")),
    ("passive_dissipated_energy_pJ", ("passive_route",)),
)
LAYOUT_FIELDS = (
    "passive_permeability",
    "passive_area",
    "passive_inside",
    "passive_outside",
    "passive_membrane",
    "passive_junction",
    "passive_on_junction",
    "passive_leak",
    "passive_exact",
)
# The rectifier's own fields, only where a definition declares it (declared_fields).
RECTIFIER_FIELDS = (
    "passive_rectifier",  # [route]: the law's routes.
    "passive_rectifier_g",  # [species, route]: g_ref (S/m^2) at the carried row.
    "passive_rectifier_k_ref",  # [route]: K_ref (mM).
    "passive_rectifier_v_half",  # [route]: V_h (V).
    "passive_rectifier_slope",  # [route]: s (V).
)
RECTIFIER_KEYS = ("id", "law", "patch", "species", *rectifier.COEFFICIENTS)
# The charged law's own field, only where a definition declares it (declared_fields), and its
# material_term, which a definition without it does not have (KindFields.without).
CHARGED_FIELDS = ("passive_charged",)  # [route]: the charged law's routes.
# FR-34's readouts (D251, D252): a route asks with its optional key `readout: true`, and the field,
# the columns and the readouts hook exist only where one does (declared_fields; KindFields.without
# drops the hook elsewhere), so a definition without the key keeps today's structure entry,
# fields, observations and programs.
READOUT_KEY = "readout"
READOUT_FIELDS = ("passive_readout",)  # [route]: the route asks.
READOUT_COLUMNS = (
    "passive_flux_fmol_s",  # [species, route]: inward, as passive_transferred moves.
    "passive_current_A",  # [route]: outward, its share of @3's membrane_current_A.
)
# FR-50's one-way records: a route asks with its optional key `one_way: true`, and the fields, the
# mask and the two hooks exist only where one does (declared_fields; bound() drops the hooks
# elsewhere), so a definition without the key keeps today's structure entry, fields and programs.
ONE_WAY_KEY = "one_way"
ONE_WAY_STATE_AXES = (
    ("passive_inward_fmol", ("passive_route",)),  # Cumulative, from the outside end in.
    ("passive_outward_fmol", ("passive_route",)),  # Cumulative, from the inside end out.
    ("passive_one_way_gap_relative", ("passive_route",)),  # The running maximum of r.
)
ONE_WAY_FIELDS = ("passive_one_way",)  # [route]: the route records.
ONE_WAY_RECORD = OneWayRecord(
    "passive_transferred", "passive_inward_fmol", "passive_outward_fmol",
    "passive_one_way_gap_relative",
)  # fmt: skip


def hosted_laws():
    """{law ID as declared: declaration} of the route laws this kind hosts, in canonical order:
    found in the active law registry by interface and host (CORE_SEAMS §8.3)."""
    laws = law_registry.active().laws(law_registry.ROUTE_LAW, KIND_ID)
    return {law.law_id: law for law in laws}


class Route(NamedTuple):
    id: str
    law: str
    host_kind: str  # "patch" or "junction"
    host: str
    inside: str  # A patch's cell, a junction's sender.
    outside: str  # A patch's outside node, a junction's receiver.
    species: str
    permeability: float  # m/s
    factors: tuple = ()  # Factor-source IDs, in declared order (§7.4 (n)).
    readout: bool = False  # FR-34: its flux and current read out at each observed row.
    one_way: bool = False  # FR-50: its one-way records.


class RectifierRoute(NamedTuple):
    """A route of the inward rectifier (RECTIFIER_LAW_ID), always on a membrane patch: its
    coefficients in place of a permeability. Version 1's Route is unchanged."""

    id: str
    law: str
    host_kind: str  # "patch"
    host: str
    inside: str  # The patch's cell.
    outside: str  # The patch's outside node.
    species: str
    g_ref: float  # S/m^2, >= 0
    k_ref: float  # mM, > 0
    v_half: float  # V
    slope: float  # V, > 0
    factors: tuple = ()  # Factor-source IDs, in declared order (§7.4 (n)).
    readout: bool = False  # FR-34: its flux and current read out at each observed row.
    one_way: bool = False  # Always false: a rectifier route has no one-way form (FR-50).


def _moves(route):
    """Whether a route moves its row: a positive permeability, or a rectifier's positive g_ref."""
    return route.g_ref > 0 if isinstance(route, RectifierRoute) else route.permeability > 0


def _readout(raw, rid):
    """A route's optional readout key (FR-34): true or false, false where it is not given."""
    readout = raw.get(READOUT_KEY, False)
    if not isinstance(readout, bool):
        raise ConfigError(
            f"{MODEL_KEY} {rid}: {READOUT_KEY} is true or false (true reads the route's flux and "
            "current out at each observed row)"
        )
    return readout


def _one_way(raw, rid):
    """A route's optional one_way key (FR-50): true or false, false where it is not given."""
    one_way = raw.get(ONE_WAY_KEY, False)
    if not isinstance(one_way, bool):
        raise ConfigError(
            f"{MODEL_KEY} {rid}: {ONE_WAY_KEY} is true or false (true keeps the route's one-way "
            "records, inward and outward)"
        )
    return one_way


def _parse_rectifier(raw, rid, patches, m):
    """One rectifier route (the module docstring's form): a patch, its carried row and its four
    coefficients, each finite, g_ref >= 0, K_ref > 0 and s > 0."""
    keys = set(raw)
    if "junction" in keys:
        raise ConfigError(f"{MODEL_KEY} {rid}: {RECTIFIER_LAW_ID} sits on a membrane patch")
    if not set(RECTIFIER_KEYS) <= keys <= {*RECTIFIER_KEYS, "factors", READOUT_KEY, ONE_WAY_KEY}:
        raise ConfigError(
            f"{MODEL_KEY} {rid}: a {RECTIFIER_LAW_ID} route declares {', '.join(RECTIFIER_KEYS)} "
            f"and optionally factors and {READOUT_KEY}"
        )
    if _one_way(raw, rid):
        raise ConfigError(
            f"{MODEL_KEY} {rid}: {ONE_WAY_KEY} records are refused on {RECTIFIER_LAW_ID}, an "
            "inward rectifier: its flux q(V - E)(V - E) reads both ends through E, so it has no "
            "one-way form (FR-50, version 1)"
        )
    hosted = hosted_laws()
    if RECTIFIER_LAW_ID not in hosted:
        raise ConfigError(f"{MODEL_KEY} {rid}: law must be one of {', '.join(hosted)}")
    factors = raw.get("factors", [])
    if (
        not isinstance(factors, list)
        or any(not isinstance(f, str) or not f for f in factors)
        or len(set(factors)) != len(factors)
    ):
        raise ConfigError(f"{MODEL_KEY} {rid}: factors is a list of distinct factor-source IDs")
    host = raw["patch"]
    if host not in patches:
        raise ConfigError(f"{MODEL_KEY} {rid}: unknown membrane patch {host!r}")
    species = raw["species"]
    if species not in m.species_ids:
        raise ConfigError(f"{MODEL_KEY} {rid}: unknown species {species!r}")
    values = []
    for key in rectifier.COEFFICIENTS:
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{MODEL_KEY} {rid}: {key} is one number")
        value = float(value)
        if not np.isfinite(value):
            raise ConfigError(f"{MODEL_KEY} {rid}: {key} is finite")
        values.append(value)
    g_ref, k_ref, v_half, slope = values
    if g_ref < 0:
        raise ConfigError(f"{MODEL_KEY} {rid}: g_ref_S_per_m2 is >= 0 (0: a closed route)")
    if not k_ref > 0:
        raise ConfigError(f"{MODEL_KEY} {rid}: k_ref_mM is positive")
    if k_ref < np.finfo(np.float64).tiny:
        raise ConfigError(
            f"{MODEL_KEY} {rid}: k_ref_mM is a normal float, at least 2.2250738585072014e-308 mM "
            "(compiled CPU code reads a subnormal K_ref as 0, and sqrt(c_o / K_ref) as inf)"
        )
    if not slope > 0:
        raise ConfigError(
            f"{MODEL_KEY} {rid}: slope_V is positive (q falls as V - E rises: inward rectification)"
        )
    patch = patches[host]
    return RectifierRoute(
        rid, RECTIFIER_LAW_ID, "patch", host, patch.inside, patch.outside, species, g_ref, k_ref,
        v_half, slope, tuple(factors), _readout(raw, rid),
    )  # fmt: skip


def parse(entries, base):
    m = base.model
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{MODEL_KEY} is a nonempty list of routes")
    patches = {p.id: p for p in m.membranes}
    junctions = {j.id: j for j in m.junctions}
    routes = []
    for raw in entries:
        if not isinstance(raw, dict):
            raise ConfigError(f"{MODEL_KEY}: each route is a mapping")
        rid = str(raw.get("id"))
        if raw.get("law") == RECTIFIER_LAW_ID:  # Its own keys; version 1's entries as today.
            routes.append(_parse_rectifier(raw, rid, patches, m))
            continue
        hosts = [h for h in HOSTS if h in raw]
        allowed = {"id", "law", "permeability_m_per_s", "species", "factors", READOUT_KEY, *hosts}
        allowed.add(ONE_WAY_KEY)
        if not {"id", "law", "permeability_m_per_s"} <= set(raw) <= allowed or len(hosts) != 1:
            raise ConfigError(
                f"{MODEL_KEY}: a route declares id, law, permeability_m_per_s, one host (patch or "
                f"junction), and species for the neutral law; optionally factors, {READOUT_KEY} "
                f"and {ONE_WAY_KEY}"
            )
        law, hosted = raw["law"], hosted_laws()
        if not isinstance(law, str) or law not in hosted:
            raise ConfigError(f"{MODEL_KEY} {rid}: law must be one of {', '.join(hosted)}")
        if law not in VERSION_1_LAWS:
            raise ConfigError(
                f"{MODEL_KEY} {rid}: version 1 runs {', '.join(VERSION_1_LAWS)}, not {law}"
            )
        factors = raw.get("factors", [])
        if (
            not isinstance(factors, list)
            or any(not isinstance(f, str) or not f for f in factors)
            or len(set(factors)) != len(factors)
        ):
            raise ConfigError(f"{MODEL_KEY} {rid}: factors is a list of distinct factor-source IDs")
        kind, host = hosts[0], raw[hosts[0]]
        if kind == "patch":
            if host not in patches:
                raise ConfigError(f"{MODEL_KEY} {rid}: unknown membrane patch {host!r}")
            inside, outside = patches[host].inside, patches[host].outside
        else:
            if law in LEAK_LAWS:
                raise ConfigError(f"{MODEL_KEY} {rid}: the proton leak sits on a membrane patch")
            if host not in junctions:
                raise ConfigError(f"{MODEL_KEY} {rid}: unknown junction {host!r}")
            inside, outside = junctions[host].sender, junctions[host].receiver
        species = raw.get("species", DEFAULT_PROTON if law in LEAK_LAWS else None)
        if species not in m.species_ids:
            raise ConfigError(f"{MODEL_KEY} {rid}: unknown species {species!r}")
        value = raw["permeability_m_per_s"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{MODEL_KEY} {rid}: permeability_m_per_s is one number (m/s)")
        value = float(value)
        if not (np.isfinite(value) and value >= 0):
            raise ConfigError(f"{MODEL_KEY} {rid}: permeability_m_per_s is finite and >= 0")
        readout, one_way = _readout(raw, rid), _one_way(raw, rid)
        routes.append(
            Route(
                rid, law, kind, host, inside, outside, species, value, tuple(factors), readout,
                one_way,
            )
        )  # fmt: skip
    ids = [r.id for r in routes]
    if len(set(ids)) != len(ids):
        raise ConfigError(f"{MODEL_KEY}: route IDs must be unique")
    return tuple(sorted(routes))


def to_dict(declaration):
    out = []
    for r in declaration:
        if isinstance(r, RectifierRoute):
            entry = {"id": r.id, "patch": r.host, "law": r.law, "species": r.species}
            values = (r.g_ref, r.k_ref, r.v_half, r.slope)
            entry |= dict(zip(rectifier.COEFFICIENTS, values, strict=True))
            if r.factors:
                entry["factors"] = list(r.factors)
            if r.readout:  # FR-34: written only where asked, so a definition keeps its form.
                entry[READOUT_KEY] = True
            out.append(entry)
            continue
        entry = {
            "id": r.id,
            r.host_kind: r.host,
            "law": r.law,
            "permeability_m_per_s": r.permeability,
        }
        if r.law in (LAW_ID, CHARGED_LAW_ID) or r.species != DEFAULT_PROTON:  # The leak's default.
            entry["species"] = r.species
        if r.factors:
            entry["factors"] = list(r.factors)
        if r.readout:  # FR-34: written only where asked, so a definition keeps its form.
            entry[READOUT_KEY] = True
        if r.one_way:  # FR-50: likewise.
            entry[ONE_WAY_KEY] = True
        out.append(entry)
    return out


class Factored(NamedTuple):
    """The structure entry of a declaration whose routes declare factors (§7.4 (n) 6)."""

    laws: tuple


class ReadOut(NamedTuple):
    """The structure entry of a declaration where a route asks for its readouts (FR-34)."""

    laws: tuple
    factored: bool  # Whether a route declares factors (the multiplier, as Factored has it).


class OneWay(NamedTuple):
    """The structure entry of a declaration where a route keeps one-way records (FR-50)."""

    laws: tuple
    factored: bool  # As ReadOut's.
    readout: bool  # Whether a route asks for its readouts (FR-34).


def structure_entry(declaration):
    """Value-free: the declared laws (the leak traces its own kernel); Factored(laws) where any
    route declares factors; ReadOut(laws, factored) where any route asks for its readouts (FR-34);
    OneWay(laws, factored, readout) where any route keeps one-way records (FR-50). So today's
    declarations keep today's entry."""
    laws = tuple(sorted({route.law for route in declaration}))
    factored = any(route.factors for route in declaration)
    readout = any(route.readout for route in declaration)
    if any(route.one_way for route in declaration):
        return OneWay(laws, factored, readout)
    if readout:
        return ReadOut(laws, factored)
    return Factored(laws) if factored else laws


def declared_fields(entry):
    """The kind's fields for its entry (§7.4 (n) 5): the multiplier and the sink's feedback hooks
    exist only where factored, the rectifier's fields only where a route runs it, the charged law's
    field and its material_term only where a route runs that law, the readouts' field, columns and
    hook only where a route asks (FR-34), and the one-way records' fields, mask and hooks only where
    a route keeps them (FR-50), so no other entry's program or observation changes."""
    one_way = isinstance(entry, OneWay)
    readout = isinstance(entry, ReadOut) or (one_way and entry.readout)
    laws = entry.laws if isinstance(entry, (Factored, ReadOut, OneWay)) else entry
    factored = (
        entry.factored if isinstance(entry, (ReadOut, OneWay)) else isinstance(entry, Factored)
    )
    layout = LAYOUT_FIELDS + (RECTIFIER_FIELDS if RECTIFIER_LAW_ID in laws else ())
    charged = CHARGED_LAW_ID in laws
    layout += CHARGED_FIELDS if charged else ()
    layout += READOUT_FIELDS if readout else ()
    layout += ONE_WAY_FIELDS if one_way else ()
    return KindFields(
        STATE_AXES + (ONE_WAY_STATE_AXES if one_way else ()),
        layout,
        (MULTIPLIER,) if factored else (),
        READOUT_COLUMNS if readout else (),
        (() if charged else ("material_term",))
        + (() if readout else ("readouts",))
        + (() if factored else ("routed_rows", "routed_flux")),
        (ONE_WAY_RECORD,) if one_way else (),
    )


def _rectified(p):
    """Static: whether the layout holds the rectifier's fields (a definition that declares it)."""
    return "passive_rectifier" in type(p)._fields


def _charged(p):
    """Static: whether the layout holds the charged law's field (a definition that declares it)."""
    return "passive_charged" in type(p)._fields


def control_values(spec, declaration, times):
    """The multiplier's held value, 1 on every route; the door routes the factored ones."""
    return {MULTIPLIER: np.ones((len(times), len(declaration)))}


def routed_controls(declaration):
    """Each factored route's multiplier slot and its sources, in declared order (§7.4 (n))."""
    return tuple(
        (MULTIPLIER, k, route.factors) for k, route in enumerate(declaration) if route.factors
    )


def routed_rows(declaration):
    """The row each factored route moves, between its two ends, in routed_controls' order (a
    factor's feedback, kind_registry.Kind; names only)."""
    return tuple(
        ((route.species, route.inside, route.outside),) for route in declaration if route.factors
    )


def routed_flux(read, potentials, control, p, *, xp):
    """{the multiplier: [species, route] the inward flux (fmol/s)} at the routed control, the
    rates' own (_flux): a factor's feedback (kind_registry.Kind)."""
    return {MULTIPLIER: _flux(read, potentials, control, p, xp=xp).flux}


def _node_ids(spec):
    m, x = spec.model, spec.execution
    nodes = [c.id for c in m.cells] + [None] * (x.capacity - len(m.cells))
    return (
        nodes
        + [o.id for o in m.extracellular]
        + [None] * (x.extracellular_capacity - len(m.extracellular))
    )


def _exact(spec, declaration):
    """Version 1's scope, per route: a neutral route whose every carried row (species, end node) is
    moved by exact-booked passive routes alone, neither end a held bath; the leak never.

    A fixpoint over shared rows: a route starts as a candidate unless it is the leak, touches a
    held bath or shares a row with a non-passive mover (moved_nodes); then any candidate sharing a
    row with a passive route that is not one drops out, until nothing changes. So a route beside
    a tableau-booked passive route on one row is tableau-booked too. Operators' writers (the
    registry's moved_in_step) are the composite's admission."""
    from cells.models.surface_pump_v3 import moved_nodes

    m = spec.model
    held = {o.id for o in m.extracellular if o.reservoir}
    movers = moved_nodes(m)
    rows, candidate = {}, []
    for k, route in enumerate(declaration):
        ends = [(route.species, route.inside), (route.species, route.outside)]
        if _moves(route):
            for row in ends:
                rows.setdefault(row, []).append(k)
        others = any(w != KIND_ID for row in ends for w in movers.get(row, ()))
        candidate.append(
            route.law == LAW_ID
            and route.outside not in held
            and not (_moves(route) and others)
        )
    changed = True
    while changed:
        changed = False
        for k, route in enumerate(declaration):
            ends = [(route.species, route.inside), (route.species, route.outside)]
            if candidate[k] and any(not candidate[j] for row in ends for j in rows.get(row, ())):
                candidate[k], changed = False, True
    return np.asarray(candidate, dtype=bool)


def initial(spec, declaration, layout):
    m = spec.model
    ids, nodes = list(m.species_ids), _node_ids(spec)
    s, r = len(ids), len(declaration)
    membranes = [p.id for p in m.membranes]
    junctions = [j.id for j in m.junctions]
    areas = {p.id: p.area_m2 for p in m.membranes} | {j.id: j.area_m2 for j in m.junctions}
    permeability = np.zeros((s, r))
    for k, route in enumerate(declaration):
        if not isinstance(route, RectifierRoute):  # The rectifier has no permeability.
            permeability[ids.index(route.species), k] = route.permeability
    own = dict(
        passive_permeability=permeability,
        passive_area=np.asarray([areas[route.host] for route in declaration]),
        passive_inside=np.asarray([nodes.index(route.inside) for route in declaration]),
        passive_outside=np.asarray([nodes.index(route.outside) for route in declaration]),
        passive_membrane=np.asarray(
            [membranes.index(r.host) if r.host_kind == "patch" else 0 for r in declaration]
        ),
        passive_junction=np.asarray(
            [junctions.index(r.host) if r.host_kind == "junction" else 0 for r in declaration]
        ),
        passive_on_junction=np.asarray([r.host_kind == "junction" for r in declaration]),
        passive_leak=np.asarray([r.law in LEAK_LAWS for r in declaration]),
        passive_exact=_exact(spec, declaration),
    )
    if any(isinstance(route, RectifierRoute) for route in declaration):  # declared_fields' test.
        own |= _rectifier_layout(ids, declaration)
    if any(route.law == CHARGED_LAW_ID for route in declaration):  # declared_fields' test.
        own["passive_charged"] = np.asarray([route.law == CHARGED_LAW_ID for route in declaration])
    if any(route.readout for route in declaration):  # declared_fields' test (FR-34).
        own["passive_readout"] = np.asarray([route.readout for route in declaration])
    state = dict(passive_transferred=np.zeros((s, r)), passive_dissipated_energy_pJ=np.zeros(r))
    if any(route.one_way for route in declaration):  # declared_fields' test (FR-50).
        own["passive_one_way"] = np.asarray([route.one_way for route in declaration])
        state |= {name: np.zeros(r) for name, _ in ONE_WAY_STATE_AXES}
    return state, own


def _rectifier_layout(ids, declaration):
    """The rectifier's fields: its mask, g_ref at each route's carried row, and K_ref, V_h and s
    per route (1, 0 and 1 on the other routes, where g is zero and the mask false)."""
    r = len(declaration)
    g, k_ref, v_half, slope = np.zeros((len(ids), r)), np.ones(r), np.zeros(r), np.ones(r)
    for k, route in enumerate(declaration):
        if isinstance(route, RectifierRoute):
            g[ids.index(route.species), k] = route.g_ref
            k_ref[k], v_half[k], slope[k] = route.k_ref, route.v_half, route.slope
    return dict(
        passive_rectifier=np.asarray([isinstance(r, RectifierRoute) for r in declaration]),
        passive_rectifier_g=g,
        passive_rectifier_k_ref=k_ref,
        passive_rectifier_v_half=v_half,
        passive_rectifier_slope=slope,
    )


def _amounts(state, p, xp):
    return xp.concatenate(
        (
            p.amount_reference + state.amount_increment,
            p.extracellular_amount_reference + state.extracellular_amount_increment,
        ),
        axis=1,
    )


def _volumes(p, xp):
    volume = xp.concatenate((p.volume, p.extracellular_volume))
    active = xp.concatenate((p.active, p.outside_active))
    return xp.where(active, volume, 1.0), active


def _net(moved, p, nodes, xp):
    """[species, node] net inward change of each node from route values [species, route]."""
    zero = xp.zeros((moved.shape[0], nodes))
    into = scatter(moved, zero, (p.passive_inside,), xp=xp)
    return into - scatter(moved, zero, (p.passive_outside,), xp=xp)


def _opening(state, control, p, xp):
    """Each route's opening: its patch's availability, or its junction's gate x availability,
    times its routed multiplier where the declaration has one (§7.4 (n) 6)."""
    opening = xp.ones(p.passive_area.shape)
    if control.membrane.shape[-1]:  # Static: membrane routes need a patch to exist.
        opening = control.membrane[p.passive_membrane]
    if control.junction.shape[-1]:  # Static: junction routes need a junction to exist.
        gated = control.junction * state.junction_gate
        opening = xp.where(p.passive_on_junction, gated[p.passive_junction], opening)
    if MULTIPLIER in type(control)._fields:  # Static: a factored declaration's field.
        opening = opening * getattr(control, MULTIPLIER)
    return opening


def _ends(state, p, xp):
    """(c_in, c_out) [species, route] in mM, from the read's amounts (free h at buffered nodes)."""
    volume, active = _volumes(p, xp)
    c = xp.where(active, _amounts(state, p, xp) / volume, 1.0)
    return c[:, p.passive_inside], c[:, p.passive_outside]


def _rectifier_terms(c_in, c_out, voltage, opening, p):
    """The rectifier kernels' arguments [species, route], in their order (laws/routes/
    inward_rectifier_linear_driving_force.py)."""
    return (
        c_in, c_out, voltage, p.temperature, p.passive_area, p.passive_rectifier_g,
        p.passive_rectifier_k_ref, p.passive_rectifier_v_half, p.passive_rectifier_slope, opening,
    )  # fmt: skip


class Flux(NamedTuple):
    """Every route's flux at one stage, with the inputs its heat reads."""

    c_in: object  # [species, route], mM
    c_out: object
    voltage: object  # [route], phi_in - phi_out (V)
    terms: object  # The rectifier kernels' arguments, or None where no route runs it.
    flux: object  # [species, route], fmol/s, inward.


def _flux(state, potentials, control, p, *, xp, voltage=None):
    """Every route's flux, inward, at the stage's read amounts and its availability. Its voltage
    is the patch voltage phi_in - phi_out from the potentials, or the one given (clamped_flux), at
    the same step of the arithmetic, so rates' program is the step's as before (FR-34)."""
    c_in, c_out = _ends(state, p, xp)
    opening = _opening(state, control, p, xp)
    neutral = passive.flux_fmol_s(
        c_in, c_out, p.passive_area, p.passive_permeability, opening, xp=xp
    )  # [species, route], inward.
    if voltage is None:
        voltage = potentials[p.passive_inside] - potentials[p.passive_outside]  # phi_in - phi_out.
    charged = leak.flux_fmol_s(
        c_in, c_out, voltage, p.temperature, p.passive_area, p.passive_permeability, opening, xp=xp
    )
    flux = xp.where(p.passive_leak, charged, neutral)
    terms = None
    if _rectified(p):  # Static: only a definition that declares the rectifier traces it.
        terms = _rectifier_terms(c_in, c_out, voltage, opening, p)
        flux = xp.where(p.passive_rectifier, rectifier.flux_fmol_s(*terms, xp=xp), flux)
    if _charged(p):  # Static: only a definition that declares the charged law traces it.
        moved = charged_law.flux_fmol_s(
            c_in, c_out, voltage, p.valence, p.temperature, p.passive_area, p.passive_permeability,
            opening, xp=xp,
        )  # fmt: skip
        flux = xp.where(p.passive_charged, moved, flux)
    return Flux(c_in, c_out, voltage, terms, flux)


def _current(flux, p, *, xp):
    """[route] each route's electric current (A), outward-positive: positive charge from its
    inside end to its outside end, its share of @3's membrane_current_A (e species_sum(z x the
    patches' outward flux)); 0 on a junction, which crosses no membrane patch (a charged junction
    route's current between its cells is e z times its flux, outside membrane_current_A, as @3's
    own junction routes' is)."""
    outward = xp.where(p.passive_on_junction, 0.0, -flux)
    return CHARGE_PER_FMOL * species_sum(p.valence * outward, xp=xp)


def rates(state, potentials, control, p, *, xp):
    from cells.models.surface_pump_v3 import KindRates

    c_in, c_out, voltage, terms, flux = _flux(state, potentials, control, p, xp=xp)
    volume, _ = _volumes(p, xp)
    n = p.active.size
    net = _net(flux, p, volume.shape[0], xp)
    log_ratio = xp.log(c_out) - xp.log(c_in)
    fick = 1e-3 * R * p.temperature * species_sum(flux * log_ratio, xp=xp)
    ghk = species_sum(leak.heat_pJ_s(flux, c_in, c_out, voltage, p.temperature, xp=xp), xp=xp)
    heat = xp.where(p.passive_leak, ghk, fick)  # >= 0, pJ/s per route.
    if _rectified(p):  # Its I u, >= 0, per route.
        dissipated = species_sum(rectifier.heat_pJ_s(*terms, xp=xp), xp=xp)
        heat = xp.where(p.passive_rectifier, dissipated, heat)
    if _charged(p):  # J (mu-tilde_out - mu-tilde_in), >= 0, per route (FR-15 P2).
        ohmic = charged_law.heat_pJ_s(flux, c_in, c_out, voltage, p.valence, p.temperature, xp=xp)
        heat = xp.where(p.passive_charged, species_sum(ohmic, xp=xp), heat)
    outward = xp.where(p.passive_on_junction, 0.0, -flux)
    patch_flux = scatter(outward, p.membrane_permeability, (p.passive_membrane,), xp=xp)
    return KindRates(
        cell=net[:, :n],
        outside=net[:, n:],
        derivatives=dict(passive_transferred=flux, passive_dissipated_energy_pJ=heat),
        heat_pJ_s=entity_sum(heat, axis=None, xp=xp),  # Over routes.
        work_pJ_s=xp.zeros(()),
        membrane_flux=patch_flux,
    )


def _one_way_kernel(view, p, *, xp):
    """(kernel, c_in, c_out) at one end of a step (a LabelView: its read's amounts, its node
    potentials and its routed control): kernel(at_in, at_out) is each route's own law,
    inward-positive [species, route], at the end's opening and voltage, and c_in and c_out [species,
    route] are the end's concentrations. The neutral, proton-leak and charged constant-field
    kernels are linear in their two end concentrations at a fixed voltage, so the inward flux is
    the kernel's with c_in = 0 and the outward one minus the kernel's with c_out = 0: inward less
    outward is the kernel's own flux, at rounding, from the same kernels (no new law). A rectifier
    route's kernel is 0: its flux is not linear in its ends. FR-42's labels and FR-50's records
    read it alike."""
    c_in, c_out = _ends(view.read, p, xp)
    opening = _opening(view.read, view.control, p, xp)
    voltage = view.potentials[p.passive_inside] - view.potentials[p.passive_outside]

    def kernel(at_in, at_out):  # Each route's own law, inward-positive [species, route].
        flux = xp.where(
            p.passive_leak,
            leak.flux_fmol_s(
                at_in, at_out, voltage, p.temperature, p.passive_area, p.passive_permeability,
                opening, xp=xp,
            ),
            passive.flux_fmol_s(
                at_in, at_out, p.passive_area, p.passive_permeability, opening, xp=xp
            ),
        )  # fmt: skip
        if _charged(p):  # Static, as in _flux.
            moved = charged_law.flux_fmol_s(
                at_in, at_out, voltage, p.valence, p.temperature, p.passive_area,
                p.passive_permeability, opening, xp=xp,
            )  # fmt: skip
            flux = xp.where(p.passive_charged, moved, flux)
        if _rectified(p):  # Static: never the rectifier's kernel (it reads both ends' logs).
            flux = xp.where(p.passive_rectifier, 0.0, flux)
        return flux

    return kernel, c_in, c_out


def one_way_fluxes(view, p, rows, *, xp):
    """FR-42 (D303 item 6): each route's one-way fluxes of the labelled rows at one end of a step,
    as (inward, outward) [m, route] in fmol/s, each >= 0, from _one_way_kernel. A rectifier route
    reports 0, and label_refusals refuses a labelled row it moves."""
    kernel, c_in, c_out = _one_way_kernel(view, p, xp=xp)
    zero = xp.zeros_like(c_in)
    idx = xp.asarray(rows)
    return kernel(zero, c_out)[idx], -kernel(c_in, zero)[idx]


def label_transfers(start, end, p, dt, rows, *, weight=None, xp):
    """FR-42's kinds hook (D303 item 6; the contract in kind_registry.Kind): the routes' one-way
    amounts of the labelled rows over one step, (inward [m, route], outside end, inside end) and
    (outward, inside end, outside end), fmol, each >= 0, ends on the combined node axis. Each is
    the trapezoid of the start's and end's one-way fluxes, or under the Euler IMEX `weight` times
    the start's, plus the gap to the booked net passive_transferred (end less start, inward) on the
    side its sign gives: the shared rule (numerics/one_way_split.py)."""
    at_start = one_way_fluxes(start, p, rows, xp=xp)
    at_end = one_way_fluxes(end, p, rows, xp=xp) if weight is None else None
    inward, outward = step_one_way_amounts(at_start, at_end, dt, weight=weight)
    moved = end.state.passive_transferred - start.state.passive_transferred
    split = close_one_way(inward, outward, moved[xp.asarray(rows)], xp=xp)
    return (
        (split.forward, p.passive_outside, p.passive_inside),
        (split.backward, p.passive_inside, p.passive_outside),
    )


def record_fluxes(view, p, *, xp):
    """FR-50's hook (the contract in kind_registry.Kind): each route's one-way fluxes at one end of
    a step, {passive_transferred: (inward [route], outward [route])}, fmol/s, each >= 0, its
    carried row's (the kernel's other rows are 0: a route's permeability is its carried row's),
    and 0 on a route that keeps no records."""
    kernel, c_in, c_out = _one_way_kernel(view, p, xp=xp)
    zero = xp.zeros_like(c_in)
    inward = species_sum(kernel(zero, c_out), xp=xp)
    outward = species_sum(-kernel(c_in, zero), xp=xp)
    on = p.passive_one_way
    return {"passive_transferred": (xp.where(on, inward, 0.0), xp.where(on, outward, 0.0))}


def record_nets(state, p, *, xp):
    """FR-50's hook: each recording route's net record [route], passive_transferred at its carried
    row (its other rows stay 0), and 0 on a route that keeps no records."""
    net = species_sum(state.passive_transferred, xp=xp)
    return {"passive_transferred": xp.where(p.passive_one_way, net, 0.0)}


def label_refusals(declaration, species):
    """FR-42 (D303 item 6): the labelled species (IDs) these routes cannot carry. Of its moved
    rows (moved_rows: a route that moves its row), only an inward rectifier's: its flux
    q(V - E)(V - E) reads both ends through E, so it has no one-way form. Every other route's law
    is linear in its ends."""
    return [
        f"{route.id} runs {RECTIFIER_LAW_ID}, whose flux has no one-way form (its driving force "
        f"reads both ends), and moves the labelled {route.species}"
        for route in declaration
        if isinstance(route, RectifierRoute) and _moves(route) and route.species in species
    ]


def readouts(state, read, potentials, control, p, *, xp):
    """FR-34: each asking route's flux [species, route] (fmol/s, inward-positive, as
    passive_transferred moves) and current [route] (A, outward-positive, its share of @3's
    membrane_current_A), at the observed row's read amounts and potentials: the rates' own flux, so
    the step and its record are one computation. 0 on every route that does not ask."""
    del state
    flux = xp.where(
        p.passive_readout[None, :], _flux(read, potentials, control, p, xp=xp).flux, 0.0
    )
    return flux, _current(flux, p, xp=xp)


def clamped_flux(read, control, p, voltages_V, *, xp=np):
    """FR-34, current at a declared voltage: every route's flux [species, route] (fmol/s, inward)
    and current [route] (A, outward-positive) at the patch voltages phi_in - phi_out given [route]
    (V; a scalar applies to every route), at a state's read amounts and controls: the step's own
    kernels, the potentials' voltage replaced by the one given. A junction's neutral route is
    voltage-free; a charged one takes its entry as phi_sender - phi_receiver. A junction's route
    carries no share of the membrane current (_current). Pure: it records nothing, so no program or
    record changes."""
    voltage = xp.broadcast_to(xp.asarray(voltages_V, dtype=float), p.passive_inside.shape)
    flux = _flux(read, None, control, p, xp=xp, voltage=voltage).flux
    return flux, _current(flux, p, xp=xp)


def _row_energy(n, volume, xp):
    """G = n (ln(n/V) - 1) per row (RT units, fmol), n ln n -> 0 at n = 0."""
    safe = xp.where(n > 0, n, 1.0)
    return xp.where(n > 0, n * (xp.log(safe / volume) - 1.0), 0.0)


def exact_booking(start, end, p, *, xp):
    """§7.5 version 1's booking over one step: (heat per route [route] in pJ, no negative share,
    every exact row's raw sum within its rounding bound). Exact routes only; the caller keeps the
    tableau's heat on the others."""
    heat, positive, residual, bound, rows = _booking(start, end, p, xp=xp)
    return heat, positive, xp.all(xp.where(rows, residual <= bound, True))


def raw_sum_check(start, end, p, *, xp=np):
    """(|sum of shares - exact decrease| per row, its bound, the exact rows) over one step: the
    raw-sum check's terms, for its factor's test (§7.5: confirmed at implementation)."""
    _, _, residual, bound, rows = _booking(start, end, p, xp=xp)
    return residual, bound, rows


def raw_sum_terms(start, end, p, *, xp=np):
    """(residual, own, inputs, rows) over one step: the bound's two magnitudes apart, the row's own
    terms and its inputs' rounding (§7.5, the raw-sum bound); bound = RAW_SUM_FACTOR eps (own +
    inputs). For the bound's tests and probes."""
    _, _, residual, own, inputs, rows = _raw_sums(start, end, p, xp=xp)
    return residual, own, inputs, rows


def _increments(state, xp):
    """[species, node] stored increments, cells then outside nodes (_amounts less its reference)."""
    return xp.concatenate((state.amount_increment, state.extracellular_amount_increment), axis=1)


def share_check(start, end, p, *, xp=np):
    """(each route's share [species, route], its floor, the exact routes' mask) over one step,
    share and floor in pJ: the sign rule's terms (§7.5, amended 17 November 2026), for its tests
    and probes. The step is refused where an exact route's share lies below its floor."""
    _, _, _, _, _, _, _, shares, floor, exact = _shares(start, end, p, xp=xp)
    return shares, floor, exact


def _booking(start, end, p, *, xp):
    heat, positive, residual, own, inputs, rows = _raw_sums(start, end, p, xp=xp)
    bound = RAW_SUM_FACTOR * np.finfo(float).eps * (own + inputs)
    return heat, positive, residual, bound, rows


def _shares(start, end, p, *, xp):
    """One step's exact shares and their floors (§7.5): (volume, n0, n1, moved, mu-bar, mu-bar_in,
    mu-bar_out, shares, floor, exact), moved and both pJ terms [species, route].

    The sign rule (amended 17 November 2026, its band near 1 mM closed the same day): a share is
    refused only below its floor. The floor is minus the raw-sum check's factor times eps times
    the share's scale, (|mu-bar_in| + |mu-bar_out| + 2) |m|, in the share's unit (route_heat_pJ's
    1e-3 RT).
    - |mu-bar| |m| is the route's product in its rows' own terms.
    - 2 |m| is its potentials' evaluation rounding. The kernel forms each end's mu-bar as
      ln(n0/V) + p(x) - 1 with p near 1, so a mu-bar carries the ulp of |mu-bar| + 1 even where it
      is 0 (c = 1 mM).
    Between rows whose divided potentials differ by a few ulp, a transfer below the amounts'
    resolution gives a share of either sign at that scale; a relative tolerance on the share
    itself would be zero there."""
    volume, _ = _volumes(p, xp)
    n0, n1 = _amounts(start, p, xp), _amounts(end, p, xp)
    moved = end.passive_transferred - start.passive_transferred  # [species, route], inward.
    mu = passive.divided_potential_RT(n0, n1, volume[None, :], xp=xp)  # [species, node]
    mu_in, mu_out = mu[:, p.passive_inside], mu[:, p.passive_outside]
    shares = passive.route_heat_pJ(moved, mu_in, mu_out, p.temperature, xp=xp)
    exact = p.passive_exact[None, :] & (p.passive_permeability > 0)
    terms = (xp.abs(mu_in) + xp.abs(mu_out) + 2.0) * xp.abs(moved)  # RT fmol.
    floor = -(RAW_SUM_FACTOR * np.finfo(float).eps * 1e-3 * R) * p.temperature * terms
    return volume, n0, n1, moved, mu, mu_in, mu_out, shares, floor, exact


def _raw_sums(start, end, p, *, xp):
    volume, n0, n1, moved, mu, mu_in, mu_out, shares, floor, exact = _shares(start, end, p, xp=xp)
    negative = xp.any(xp.where(exact, shares < floor, False))  # Below its floor (_shares).
    # Raw sums: each exact row's shares (mu-bar times every route's transfer at it) against its
    # exact change of G, within RAW_SUM_FACTOR eps of the terms' magnitudes (§7.5's bound).
    carried = xp.where(exact, moved, 0.0)
    zero = xp.zeros_like(n0)

    def at_ends(values):  # [species, route] -> [species, node], at both of each route's ends.
        inside = scatter(values, zero, (p.passive_inside,), xp=xp)
        return inside + scatter(values, zero, (p.passive_outside,), xp=xp)

    rows = at_ends(xp.where(exact, 1.0, 0.0)) > 0  # Every row an exact route touches.
    g0, g1 = _row_energy(n0, volume[None, :], xp), _row_energy(n1, volume[None, :], xp)
    summed = mu * _net(carried, p, volume.shape[0], xp)
    own = (  # The row's own terms: its G at both ends and its shares' products.
        xp.abs(g0)
        + xp.abs(g1)
        + scatter(xp.abs(mu_in * carried), zero, (p.passive_inside,), xp=xp)
        + scatter(xp.abs(mu_out * carried), zero, (p.passive_outside,), xp=xp)
    )
    # Its inputs' rounding (§7.5, the raw-sum bound): the stored amounts are reference +
    # increment, rounded to the result, and each tableau term adds onto the increments and onto
    # the exact routes' cumulative transfers (_combine), rounded to the running sum. The recorded
    # net transfer and n1 - n0 therefore differ by about eps times these magnitudes, and the
    # shares carry |mu-bar| times that difference.
    cumulative = xp.abs(start.passive_transferred) + xp.abs(end.passive_transferred)
    inputs = xp.abs(mu) * (
        xp.abs(n0)
        + xp.abs(n1)
        + xp.abs(_increments(start, xp))
        + xp.abs(_increments(end, xp))
        + at_ends(xp.where(exact, cumulative, 0.0))
    )
    heat = species_sum(xp.where(exact, shares, 0.0), xp=xp)  # A7: the species fold.
    return heat, ~negative, xp.abs(summed - (g1 - g0)), own, inputs, rows


def book(applied, start, end, control, p, dt, *, xp):
    """§7.5: exact routes book their exact shares; the others keep the tableau's heat."""
    heat, positive, within = exact_booking(start, end, p, xp=xp)
    booked = xp.where(
        p.passive_exact,
        start.passive_dissipated_energy_pJ + heat,
        end.passive_dissipated_energy_pJ,
    )
    return dict(passive_dissipated_energy_pJ=booked), positive & within


def ledger_terms(state, p, *, xp):
    n = p.active.size
    volume, _ = _volumes(p, xp)
    net = _net(state.passive_transferred, p, volume.shape[0], xp)
    return dict(cell=net[:, :n], outside=net[:, n:], heat_pJ=state.passive_dissipated_energy_pJ)


def domain(state, p, *, xp):
    """Every route's transfers and heat finite; and, where the rectifier is declared, its carried
    row's concentration positive and finite at both ends of each route that conducts (its E reads
    both)."""
    moved, heat = state.passive_transferred, state.passive_dissipated_energy_pJ
    valid = xp.all(xp.isfinite(moved)) & xp.all(xp.isfinite(heat))
    if _rectified(p):  # Static.
        c_in, c_out = _ends(state, p, xp)
        positive = (c_in > 0) & (c_out > 0) & xp.isfinite(c_in) & xp.isfinite(c_out)
        valid = valid & xp.all(xp.where(p.passive_rectifier_g > 0, positive, True))
    return valid


def moved_rows(declaration):
    rows = []
    for route in declaration:
        if _moves(route):
            rows += [
                (route.species, route.inside, route.law),
                (route.species, route.outside, route.law),
            ]
    return tuple(rows)


def stage_term(read, potentials, control, p, *, xp):
    """B7 for the leak (gap 5): each leak route's max-side slope conductance (the kernel's
    conductance_S, S) at both of its patch's ends (cells, then outside nodes), for membrane_rate's
    per-stage refusal at every node; at the stage's patch voltage when the potentials are given
    (the max-side slope does not depend on it). Each rectifier route's |dI/dV| joins it the same
    way: at the stage's patch voltage when the potentials are given, and its voltage-free bound at
    the stage's concentrations when they are not (the rectifier's slope turns negative, so its
    magnitude is the term). Each charged route's max-side slope G joins it at both of its host's
    ends, as 2G at each cell on a junction (D310; @3's own junction form)."""
    c_in, c_out = _ends(read, p, xp)
    opening = _opening(read, control, p, xp)
    voltage = 0.0
    if potentials is not None:
        voltage = potentials[p.passive_inside] - potentials[p.passive_outside]
    slope = leak.conductance_S(
        c_in, c_out, voltage, p.temperature, p.passive_area, p.passive_permeability, opening, xp=xp
    )  # [species, route]; nonzero at each route's own row.
    per_route = xp.where(p.passive_leak, species_sum(slope, xp=xp), 0.0)
    if _rectified(p):  # Static.
        if potentials is None:
            magnitude = rectifier.slope_bound_S(
                c_in, c_out, p.temperature, p.passive_area, p.passive_rectifier_g,
                p.passive_rectifier_k_ref, p.passive_rectifier_v_half, p.passive_rectifier_slope,
                opening, xp=xp,
            )  # fmt: skip
        else:
            terms = _rectifier_terms(c_in, c_out, voltage, opening, p)
            magnitude = rectifier.slope_conductance_S(*terms, xp=xp)
        per_route = xp.where(p.passive_rectifier, species_sum(magnitude, xp=xp), per_route)
    if _charged(p):  # Static: the charged law's max-side slope (FR-15 P2), 2G on a junction.
        slope = charged_law.conductance_S(
            c_in, c_out, voltage, p.valence, p.temperature, p.passive_area, p.passive_permeability,
            opening, xp=xp,
        )  # fmt: skip
        # D310: a junction's charge mode relaxes at G (1/C_a + 1/C_b) <= 2G / min C, so each of
        # its cells takes 2G, @3's own junction term (surface_pump.explicit_rate_bound).
        hosted = xp.where(p.passive_on_junction, 2.0, 1.0)
        per_route = xp.where(p.passive_charged, hosted * species_sum(slope, xp=xp), per_route)
    nodes = xp.zeros(p.active.size + p.outside_active.size)  # Cells, then outside nodes.
    inside = scatter(per_route, nodes, (p.passive_inside,), xp=xp)
    return inside + scatter(per_route, nodes, (p.passive_outside,), xp=xp)


def material_term(read, potentials, control, p, *, xp):
    """D4 for the charged law (FR-15 P2): [cells, then outside nodes] the kind's material slope
    (1/s), per node the largest over the rows its charged routes move there of the sum over those
    routes of the route's material rate at that end, at the stage's read amounts and host voltage.
    A route's two slopes are the law's material_slope_per_s, |dJ/dn_in| = A P m B(-x)/V_in and
    |dJ/dn_out| = A P m B(x)/V_out. Where both ends relax (a junction's two cells, or a patch's
    cell and a finite outside node), each end takes their sum, the Gershgorin row sum of the
    route's two-row block, which is its mode's rate and at x = 0 the neutral law's L (D310); a
    patch facing a held bath, whose row does not relax, keeps the cell's own slope (and the bath's
    value is one material_rate drops). It follows the voltage with no assumed range: a charged
    trace row's bound, which @3's static bound cannot hold. Only a definition that declares the
    charged law has this hook (declared_fields).

    Without potentials it fails closed: +inf at every node a charged route touches, because
    |dJ/dn| = A P m B(-+x)/V grows without limit in |x|, so no voltage-free value bounds it (the
    lead's ruling, 19 November 2026). Every engine caller passes the stage's potentials today; a
    future caller without them refuses rather than reads a silent non-bound."""
    if not _charged(p):  # Static: a layout without the charged law's field moves no charged row
        return xp.zeros(p.active.size + p.outside_active.size)  # (a kind derived from this one).
    opening = _opening(read, control, p, xp)
    volume, _ = _volumes(p, xp)
    if potentials is None:
        permeable = xp.any(p.passive_permeability > 0, axis=0)  # [route]: no species sum (A7).
        moving = xp.where(p.passive_charged & permeable, 1.0, 0.0)
        nodes = xp.zeros(volume.shape[0])
        count = scatter(moving, nodes, (p.passive_inside,), xp=xp)
        count = count + scatter(moving, nodes, (p.passive_outside,), xp=xp)
        return xp.where(count > 0, xp.inf, 0.0)
    voltage = potentials[p.passive_inside] - potentials[p.passive_outside]
    to_in, to_out = charged_law.material_slope_per_s(
        voltage, p.valence, p.temperature, p.passive_area, p.passive_permeability, opening,
        volume[p.passive_inside], volume[p.passive_outside], xp=xp,
    )  # fmt: skip
    held = xp.concatenate((xp.zeros(p.active.size, dtype=bool), p.reservoir))  # Node axis.
    free = ~held[p.passive_outside]  # [route]: the outside end relaxes (a cell or a finite node).
    pair = to_in + to_out  # [species, route]: the two-row block's row sum (D310).
    at_in, at_out = xp.where(free, pair, to_in), xp.where(free, pair, to_out)
    zero = xp.zeros((to_in.shape[0], volume.shape[0]))
    inside = scatter(xp.where(p.passive_charged, at_in, 0.0), zero, (p.passive_inside,), xp=xp)
    outside = scatter(xp.where(p.passive_charged, at_out, 0.0), zero, (p.passive_outside,), xp=xp)
    return xp.max(inside + outside, axis=0)


def bound_rate(spec, declaration):
    """The neutral law's dt L <= 1 (§7.4 (i)): L = 1e15 P A (1/V_a + 1/V_b) summed over the routes
    at each node, the largest over species and nodes (availability and gate at most 1)."""
    m = spec.model
    volume = {c.id: c.volume_pL for c in m.cells} | {o.id: o.volume_pL for o in m.extracellular}
    area = {p.id: p.area_m2 for p in m.membranes} | {j.id: j.area_m2 for j in m.junctions}
    totals = {}
    for route in declaration:
        if route.law != LAW_ID:
            continue
        both = 1.0 / volume[route.inside] + 1.0 / volume[route.outside]
        rate = 1e15 * route.permeability * area[route.host] * both  # P A (m^3/s) over V (pL).
        for node in (route.inside, route.outside):
            totals[(route.species, node)] = totals.get((route.species, node), 0.0) + rate
    return max(totals.values(), default=0.0)


def check_definition(spec):
    """Admission: the neutral law carries a valence-0 row, the leak (either version) a valence +1
    row (the closure's proton row where a closure is declared), and @2 no end at a buffered node of
    B4's version-1 closure (it reads the general closure's free h), the rectifier a valence +1 row
    (its E reads both ends, whose initial amounts the host's parse admits only positive), the
    charged law a charged row, and on a junction only one that joins no floating capacitor
    component (version 1, D310: such a component's offset is set by the field solve's current
    balance, which holds @3's own face and junction currents, not a kind's; the scope is
    surface_pump_v3.crossing_junctions', fix (A)'s); the host route's own permeability for the
    carried row is zero; route IDs are unique among the definition's entity IDs. A row a declared
    closure holds is refused on the charged law by the species registry
    (check_amount_reading_routes, beside its other closure rules: FR-15 P2, fail-closed), so this
    kind does no registry lookup."""
    m = spec.model
    kinds = dict(m.kinds)
    declaration = kinds[KIND_ID]
    patches = {p.id: p for p in m.membranes}
    junctions = {j.id: j for j in m.junctions}
    taken = {x.id for x in (*m.cells, *m.extracellular, *m.membranes, *m.junctions, *m.faces)}
    closure = kinds.get("cells.kind.rapid_proton_buffer@1")
    crossing = None  # The junctions that cross a floating component, read once where needed.
    for route in declaration:
        if route.id in taken:
            raise ConfigError(f"{MODEL_KEY} {route.id}: the ID is already an entity's")
        host = patches[route.host] if route.host_kind == "patch" else junctions[route.host]
        row = m.species_ids.index(route.species)
        if route.law == LAW_ID and m.valence[row] != 0:
            raise ConfigError(
                f"{MODEL_KEY} {route.id}: {LAW_ID} carries neutral species only, not "
                f"{route.species}"
            )
        if route.law in LEAK_LAWS:
            if m.valence[row] != leak.VALENCE:
                raise ConfigError(
                    f"{MODEL_KEY} {route.id}: {route.law} carries a valence +1 proton row"
                )
            if closure is not None and closure.proton != route.species:
                raise ConfigError(
                    f"{MODEL_KEY} {route.id}: the leak's row {route.species} is not the closure's "
                    f"proton row {closure.proton or '(none: the closure declares no proton_row)'}"
                )
        if route.law == LEAK_V2_LAW_ID and closure is not None:
            buffered = () if hasattr(closure, "closure_rows") else dict(closure.buffers)
            at = [end for end in (route.inside, route.outside) if end in buffered]
            if at:  # B4's version 1: its free h is @1's read, not cells.binding.rapid_binding@1's.
                raise ConfigError(
                    f"{MODEL_KEY} {route.id}: {LEAK_V2_LAW_ID} reads {leak_v2.CLOSURE_READ_ID}'s "
                    f"free h, and {at[0]} is a buffered node of B4's version-1 closure; "
                    f"{LEAK_LAW_ID} reads that closure"
                )
        if isinstance(route, RectifierRoute) and m.valence[row] != rectifier.VALENCE:
            raise ConfigError(
                f"{MODEL_KEY} {route.id}: {RECTIFIER_LAW_ID} carries a valence +1 row, not "
                f"{route.species}"
            )
        if route.law == CHARGED_LAW_ID and m.valence[row] == 0:
            raise ConfigError(
                f"{MODEL_KEY} {route.id}: {CHARGED_LAW_ID} carries a charged row, not the "
                f"neutral {route.species} ({LAW_ID} carries neutral rows)"
            )
        if route.law == CHARGED_LAW_ID and route.host_kind == "junction":
            if crossing is None:
                from cells.modules import crossing_junctions  # @3's, through the surface.

                crossing = set(crossing_junctions(m))
            if route.host in crossing:
                raise ConfigError(
                    f"{MODEL_KEY} {route.id}: {CHARGED_LAW_ID} on junction {route.host}, which "
                    "joins two capacitor components where one floats, is refused in version 1 "
                    "(D310): the field solve sets a floating component's offset by current "
                    "balance over @3's own face and junction currents, which would miss this "
                    "route's current"
                )
        if _moves(route) and host.permeability_m_per_s[row]:
            raise ConfigError(
                f"{MODEL_KEY} {route.id}: its {route.host_kind} {route.host} has its own "
                f"permeability for {route.species}; one law moves a species on a route"
            )


# The run view's declarations (D154): the routes' own set (axis passive_route), with each route's
# ends as roles, its carried species, law and host; transfers are inward-positive (rates: `flux`).
# FR-34's readout columns exist only where a route asks (READOUT_KEY); each is the instantaneous
# value at the observed row, not a step's mean (that is passive_transferred's difference over dt).
_INWARD = MappingProxyType(
    {
        "from": "outside",
        "to": "inside",
        "says": "inward-positive: a positive amount moves from the route's outside end (its "
        "patch's outside node, or its junction's receiver) into its inside end (its patch's cell, "
        "or its junction's sender)",
        "confirmed": "the core's owner, from the code (core-next, 16 November 2026)",
    }
)
_OUTWARD_CURRENT = MappingProxyType(
    {
        "from": "inside",
        "to": "outside",
        "says": "outward-positive, in A: positive charge moving from the route's inside end (its "
        "patch's cell) to its outside end, the route's share of the patch's membrane_current_A; "
        "0 on a junction's route, which crosses no patch",
        "confirmed": "the kinds owner, from the code (FR-34, 20 November 2026)",
    }
)
_OUTWARD = MappingProxyType(
    {
        "from": "inside",
        "to": "outside",
        "says": "outward-positive: a positive amount moves from the route's inside end (its "
        "patch's cell, or its junction's sender) into its outside end (its patch's outside node, "
        "or its junction's receiver)",
        "confirmed": "the kinds owner, from the code (FR-50, 24 November 2026)",
    }
)
VIEW = KindView(
    units=MappingProxyType(
        {
            "passive_transferred": "fmol",
            "passive_dissipated_energy_pJ": "pJ",
            "passive_flux_fmol_s": "fmol/s",
            "passive_current_A": "A",
            "passive_inward_fmol": "fmol",
            "passive_outward_fmol": "fmol",
            "passive_one_way_gap_relative": "1",
        }
    ),
    observation_axes=MappingProxyType(
        {
            "passive_flux_fmol_s": ("species", "passive_route"),
            "passive_current_A": ("passive_route",),
        }
    ),
    record_kinds=MappingProxyType(
        {
            "passive_transferred": "cumulative",
            "passive_dissipated_energy_pJ": "cumulative",
            "passive_flux_fmol_s": "rate",
            "passive_current_A": "rate",
            "passive_inward_fmol": "cumulative",
            "passive_outward_fmol": "cumulative",
            "passive_one_way_gap_relative": "level",
        }
    ),
    orientation=MappingProxyType(
        {
            "passive_transferred": _INWARD,
            "passive_inward_fmol": MappingProxyType(
                {
                    **_INWARD,
                    "says": f"{_INWARD['says']}; the inward one-way record, 0 on a route that does "
                    f"not ask ({ONE_WAY_KEY} false)",
                    "confirmed": "the kinds owner, from the code (FR-50, 24 November 2026)",
                }
            ),
            "passive_outward_fmol": MappingProxyType(
                {
                    **_OUTWARD,
                    "says": f"{_OUTWARD['says']}; the outward one-way record, 0 on a route that "
                    f"does not ask ({ONE_WAY_KEY} false)",
                }
            ),
            "passive_flux_fmol_s": MappingProxyType(
                {
                    **_INWARD,
                    "says": f"{_INWARD['says']}; the rate at the observed row, 0 on a route that "
                    f"does not ask ({READOUT_KEY} false)",
                    "confirmed": "the kinds owner, from the code (FR-34, 20 November 2026)",
                }
            ),
            "passive_current_A": MappingProxyType(
                {
                    **_OUTWARD_CURRENT,
                    "says": f"{_OUTWARD_CURRENT['says']}; 0 on a route that does not ask "
                    f"({READOUT_KEY} false)",
                }
            ),
        }
    ),
    record_layers=MappingProxyType(
        dict.fromkeys(
            (
                "passive_transferred", "passive_dissipated_energy_pJ", *READOUT_COLUMNS,
                *(name for name, _ in ONE_WAY_STATE_AXES),
            ),
            "membrane",
        )
    ),
)


# The run view's word for each law's routes (per-entity kinds are words, docs/RUN_VIEW_DESIGN.md;
# each route's law ID is under "laws", in the form of the view's own sets).
KIND_WORDS = MappingProxyType(
    {
        LAW_ID: "permeation",
        LEAK_LAW_ID: "leak",
        LEAK_V2_LAW_ID: "leak",
        RECTIFIER_LAW_ID: "rectifier",
        CHARGED_LAW_ID: "charged permeation",
    }
)


def view_sets(spec, declaration):
    """The view's set of the routes' axis: one entry per route, in the declaration's order, each
    with its kind as a word (KIND_WORDS) and its law ID under "laws"."""
    return {
        "passive_route": {
            "id": "passive_route",
            "ids": [route.id for route in declaration],
            "roles": {
                "inside": "the route's inside end: its patch's cell, or its junction's sender",
                "outside": "its outside end: its patch's outside node, or its junction's receiver",
            },
            "carries": [[route.species] for route in declaration],
            "kinds": [KIND_WORDS[route.law] for route in declaration],
            "laws": [{"law_id": route.law} for route in declaration],
            "at": [
                {"membrane" if route.host_kind == "patch" else "junction": route.host}
                for route in declaration
            ],
        }
    }


PASSIVE_ROUTES = BUILTIN.register(
    Kind(
        kind_id=KIND_ID,
        model_key=MODEL_KEY,
        state_axes=STATE_AXES,
        layout_fields=LAYOUT_FIELDS,
        parse=parse,
        to_dict=to_dict,
        structure_entry=structure_entry,
        initial=initial,
        rates=rates,
        readouts=readouts,  # FR-34: bound only where a route asks (declared_fields).
        stage_term=stage_term,
        material_term=material_term,
        book=book,
        ledger_terms=ledger_terms,
        domain=domain,
        moved_rows=moved_rows,
        bound_rate=bound_rate,
        check_definition=check_definition,
        declared_fields=declared_fields,
        control_values=control_values,
        routed_controls=routed_controls,
        routed_rows=routed_rows,
        routed_flux=routed_flux,
        view=VIEW,
        view_sets=view_sets,
        label_refusals=label_refusals,  # FR-42's hook (D303 item 6): traced only with labels.
        label_transfers=label_transfers,
        one_way_fluxes=record_fluxes,  # FR-50: bound only where a route keeps records.
        one_way_nets=record_nets,
    )
)
