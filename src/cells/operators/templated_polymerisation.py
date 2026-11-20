"""Operator templated_polymerisation@1: templated polymerisation, its products' degradation and its
monomers' recharging, on the shared species inventory (gene regulation's option A, D235; FR-25).

The declared equations are docs/TEMPLATED_POLYMERISATION_LAWS.md (tag gr1-sheet-2026-11-20b); the
design is docs/GENE_REGULATION_DESIGN.md §7. Development, not judged: A's protocol (G6) judges it
against the code-blind references of validation/gene_regulation/references/.

Declaration
-----------
- `standard_concentration_mM`: c0 > 0, the standard concentration of every declared potential.
- `species`: each a neutral, impermeant species of the inner model (D150's identity form, `id`,
  `catalogue`, `evidence`) with its `standard_mu_RT`, mu°/RT at c0 (species_registry's
  check_potentials compares it with the registry's).
- `pools`: each {id, cell, machines}, a pool of machines (polymerases or ribosomes) in a cell,
  machines in copies.
- `chains`: each {id, pool, template, product, residues, stages, speed_per_s, draws, releases,
  saturation_mM}, a templated route of the pool's cell:
  - template {"copies": T} (a gene's copies, declared data) or {"species": row};
  - product, the row a finished chain joins, one molecule of `residues` L residues;
  - stages m, which divide L, so r = L/m residues per stage, and speed_per_s v;
  - draws and releases, {row: count per residue}, the rows each residue added consumes and gives
    back (transcription draws N and releases 2 Pi; translation draws A and 4 ATP and releases 4 ADP
    and 4 Pi);
  - saturation_mM, {drawn row: K}, for every drawn row.
- `degradations`: each {id, cell, polymer, residues, monomers, standard_free_energy}, one polymer
  molecule of L residues hydrolysed to L times `monomers` ({row: count per residue}).
- `transfers`: each {id, cell, stoichiometry, saturation_mM, share, standard_free_energy}: the
  monomers' recharging, NMP + 2 ATP -> NTP + 2 ADP as a signed integer {row: nu}, with K for each
  consumed row and its share n, the number of elementary steps it lumps (2).
- `standard_free_energy`: null, or the route's cited dG° per unit of its net move at c0, in one of
  FreeEnergyEntry's two forms: {"dG_RT"}, or {"dG_kJ_mol", "basis", "dG_RT_offset"} with a basis of
  kind_registry.DG_BASES. Each is declared to the species registry through standard_free_energies,
  whose check_free_energies holds it to the registry's potentials (seam E; the sheet's §3.3).

Every key is explicit, every route ID is distinct, and every row a route names is a listed species.

Schedule `polymerisation_controls`
----------------------------------
Per route, by ID, a piecewise-constant value from time 0, changing at exact multiples of dt inside
the horizon:
- a chain's initiation rate constant k_I, in mM^-1 s^-1;
- a degradation's first-order rate, in s^-1;
- a transfer's capacity, in mM/s.

The initiation rate is routable (B1′): a rate route's factor u in [b, 1] multiplies it at the start
of each half-step, so the scheduled k_I is the maximum.

Laws (the sheet's §4), per route at its cell
--------------------------------------------
With c = n/V in mM and mu/RT = mu°/RT + ln(c/c0):
- **Initiation:** J_I = k_I c_T F, with F the pool's free machines (fmol). c_T = T 1e15/(N_A V)
  for a gene's copies, or the template row's c. It moves no row and books nothing (declared).
- **Stage exits:** J_j = kappa C_j phi, with kappa = v/r, C_j the complexes of stage j (fmol) and
  phi = prod over drawn rows c/(K + c) times (1 - e^x).
  - x is the per-residue affinity: mu°_res/RT + sum_k net_k mu_k/RT, with net = releases - draws.
  - mu°_res is the residue's potential: the product row's mu° at 1 M, over L.
  - Each exit makes r residue moves. The last stage's exit also releases one product molecule and
    returns its machine to the pool.
- **Degradation:** J_D = k n (1 - e^y), with y = (L sum_k monomers_k mu_k - mu_polymer)/(L RT).
- **Transfer:** J_T = V cap prod over consumed rows c/(K + c) (1 - e^(x/n)), with x its affinity.

The stage and degradation laws are one-sided. A per-residue affinity above X_DOM = -1, or a product
above c° = 1 M at a chain in use, refuses the step (the sheet's §3.5). Transfers are two-sided.

The half-step
-------------
SSPRK(3,3) in Butcher form, as D152's, on this operator's own variables: its listed rows at every
cell, its pools' free machines, and its chains' complexes.
- Y1 = y, Y2 = y + h A J(Y1), Y3 = y + h A (J(Y1) + J(Y2))/4.
- d xi = h (J(Y1) + J(Y2) + 4 J(Y3))/6, and every move is applied as A d xi. So the material,
  machine and residue identities hold by construction.
- The stage condition h max L <= 1/2 holds on the unidirectional rates at every stage, which keeps
  every amount positive. A failure refuses the step; it is never repaired.

Energy
------
Per cell and half-step, the exact free-energy change of the move is booked as heat, H = -dG. It is
the sum of:
- @3's chemical term of the moved rows (adapter.species_chemical_free_energy_pJ);
- their standard term RT (mu°/RT - ln c0) dn;
- the residues in transit's mu°_res dW.

The standard part is held in poly_standard_energy_pJ, an owned free-energy term like D152's. The
energy ledger gains standard + heat, which closes against @3's chemical term by construction.
Machines and templates carry no free energy (declared).

Each route's heat (the sheet's heat classes, per route: poly_chain_heat_pJ,
poly_degradation_heat_pJ and poly_transfer_heat_pJ) is its extent times minus the
divided-difference potentials of the rows it moves. This is D152's average-vector-field share
(McLachlan, Quispel & Robidoux 1999), with mu-bar each row's exact dG over the half-step divided by
its dn (divided_potential).
- G is a sum over rows, so the routes' heats sum to the booked heat exactly, up to rounding on the
  routes' gross moves.
- A chain's is -[r S (mu°_res + sum net mu-bar) + Q (mu-bar_product - L mu°_res)].
- Within the one-sided domain each chain's and degradation's increment is non-negative.
- A known limit: a two-sided transfer's increment may take either sign in a half-step that crosses
  its equilibrium. There is no work field to absorb a quadrature's difference, and the sum is kept
  exact.
- They are diagnostics, outside HEAT_FIELDS: the composite's dissipation check holds the total.

Refused at the definition
-------------------------
- a charged, permeable or unlisted row;
- an unknown cell, pool or row;
- m not dividing L, and a draw without its K;
- a transfer that is not a reaction (a sign missing), and a degradation whose polymer a chain makes
  at another length;
- another writer of a listed row: an author, D152's reactions or an in-step mover;
- dt kappa > 1, dt k_D > 1, and dt k_I c_T F/F > 1 for a gene's template;
- more than the species cap.

At run time: a non-finite or non-positive amount, a negative pool or complex, a broken stage
condition, and the one-sided domains.

Idle: with no route it is statically idle. With no flux in a half-step the start state is selected,
so zero rates are bitwise idle.
"""

import math
from dataclasses import dataclass
from types import MappingProxyType

import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields, _number
from cells.laws.electrochemistry import R
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump as first
from cells.numerics.species_sums import entity_sum, species_sum
from cells.operators import species_common as common
from cells.operators import species_reactions
from cells.operators.contract import Operator
from cells.registry import kind_registry, species_registry

LAW_ID = "templated_polymerisation@1"
STEP_ID = "ssprk33_stage_condition_exact_bookings@1"
EXPERIMENT_KEY = "polymerisation_controls"
AVOGADRO = 6.02214076e23  # 1/mol, exact (SI 2019).
COPY_FMOL = 1e15 / AVOGADRO  # One molecule, in fmol.
STANDARD_MM = 1000.0  # c° = 1 M: the residue's potential and the release's domain.
X_DOM = -1.0  # The one-sided laws' per-residue affinity bound (the sheet's §3.5).
THETA = 0.5  # The stage condition h max L <= THETA at every stage.
RATE_BOUND = 1.0  # dt times a route's largest static rate.
FLOOR_FMOL = 1e-22  # The own ledgers' floor.
SERIES_BELOW = 1e-6  # |x| below which mu-bar's ratio (1 + x) log1p(x) / x is a series (D152's).
POOL_AXIS, CHAIN_AXIS, STAGE_AXIS = "poly_pool", "poly_chain", "poly_stage"
DEGRADATION_AXIS, TRANSFER_AXIS = "poly_degradation", "poly_transfer"
INITIATION = "polymerisation_initiation_rate"
DEGRADATION = "polymerisation_degradation_rate"
TRANSFER = "polymerisation_transfer_capacity"

STATE_AXES = {
    "poly_free_machines_fmol": [POOL_AXIS],
    "poly_complexes_fmol": [CHAIN_AXIS, STAGE_AXIS],
    "poly_initiated_fmol": [CHAIN_AXIS],  # Cumulative initiations.
    "poly_stage_exits_fmol": [CHAIN_AXIS],  # Cumulative stage exits, every stage (∫S).
    "poly_released_fmol": [CHAIN_AXIS],  # Cumulative releases (∫Q).
    "poly_degraded_fmol": [DEGRADATION_AXIS],  # Cumulative molecules degraded (∫D).
    "poly_transferred_fmol": [TRANSFER_AXIS],  # Cumulative transfer extent, signed.
    "poly_produced_fmol": ["species", "cell_slot"],
    "poly_consumed_fmol": ["species", "cell_slot"],
    "poly_dissipated_energy_pJ": ["cell_slot"],  # Heat: -dG of every move, exact.
    "poly_chain_heat_pJ": [CHAIN_AXIS],  # Each route's share of it (the sheet's classes).
    "poly_degradation_heat_pJ": [DEGRADATION_AXIS],
    "poly_transfer_heat_pJ": [TRANSFER_AXIS],
    "poly_standard_energy_pJ": ["cell_slot"],  # The owned standard term, transit included.
    "poly_energy_magnitude_pJ": ["cell_slot"],  # The bookings' absolute terms (rounding).
}
LAYOUT_FIELDS = (
    "poly_rows",  # [k] int64: the listed species' rows, in declared order.
    "poly_mu_RT",  # [k] mu°/RT at c0.
    "poly_c0_mM",  # [] c0.
    "poly_pool_total_fmol",  # [pool] M.
    "poly_chain_cell",  # [chain, cell] one-hot.
    "poly_chain_pool",  # [chain, pool] one-hot.
    "poly_chain_kappa",  # [chain] v/r, 1/s.
    "poly_chain_r",  # [chain] residues per stage.
    "poly_chain_length",  # [chain] L.
    "poly_chain_present",  # [chain, stage] bool.
    "poly_chain_last",  # [chain, stage] bool: stage m - 1.
    "poly_chain_held",  # [chain, stage] residues held per complex, j r.
    "poly_chain_net",  # [chain, k] releases - draws, per residue.
    "poly_chain_draws",  # [chain, k] draws per residue.
    "poly_chain_releases",  # [chain, k] releases per residue.
    "poly_chain_saturates",  # [chain, k] bool: a drawn row.
    "poly_chain_K_mM",  # [chain, k] (1 where not drawn).
    "poly_chain_product",  # [chain, k] one-hot.
    "poly_chain_template",  # [chain, k] one-hot of a species template (0 for a gene).
    "poly_chain_copies",  # [chain] a gene's copies (0 for a species template).
    "poly_chain_residue_mu_RT",  # [chain] mu°_res/RT at 1 M.
    "poly_deg_cell",  # [degradation, cell] one-hot.
    "poly_deg_polymer",  # [degradation, k] one-hot.
    "poly_deg_monomers",  # [degradation, k] per residue.
    "poly_deg_length",  # [degradation] L.
    "poly_tr_cell",  # [transfer, cell] one-hot.
    "poly_tr_nu",  # [transfer, k] signed.
    "poly_tr_saturates",  # [transfer, k] bool: a consumed row.
    "poly_tr_K_mM",  # [transfer, k] (1 where not consumed).
    "poly_tr_share",  # [transfer] n.
)
LEDGERS = ("poly_machines", "poly_residues")
LEDGER_DIAGNOSTICS = ("poly_machines_balance_error", "poly_residues_balance_error")
LEDGER_MESSAGE = "Templated polymerisation accounting failed: "


# ------------------------------------------------------------------ declaration


@dataclass(frozen=True)
class Pool:
    id: str
    cell: str
    machines: float  # Copies.


@dataclass(frozen=True)
class Chain:
    id: str
    pool: str
    cell: str  # The pool's (derived).
    template_copies: int | None
    template_species: str | None
    product: str
    residues: int
    stages: int
    speed_per_s: float
    draws: tuple  # ((row, count), ...)
    releases: tuple
    saturation_mM: tuple  # ((row, K), ...)


@dataclass(frozen=True)
class CitedFreeEnergy:
    """A route's cited standard free energy per unit of its net move, at the declaration's c0:
    dG°/RT, or dG° in kJ/mol with its basis and temperature-free offset (FreeEnergyEntry's two
    forms)."""

    dG_RT: float | None
    dG_kJ_mol: float | None
    basis: str | None
    offset_RT: float


@dataclass(frozen=True)
class Degradation:
    id: str
    cell: str
    polymer: str
    residues: int
    monomers: tuple  # ((row, count), ...)
    standard_free_energy: CitedFreeEnergy | None


@dataclass(frozen=True)
class Transfer:
    id: str
    cell: str
    stoichiometry: tuple  # ((row, nu), ...)
    saturation_mM: tuple  # ((row, K), ...)
    share: int
    standard_free_energy: CitedFreeEnergy | None


@dataclass(frozen=True)
class Polymerisation:
    law: str
    c0_mM: float
    species: tuple  # Identities.
    mu_RT: tuple  # mu°/RT at c0, per listed species.
    pools: tuple
    chains: tuple
    degradations: tuple
    transfers: tuple

    def route_ids(self):
        return tuple(r.id for r in (*self.chains, *self.degradations, *self.transfers))


@dataclass(frozen=True)
class RouteSchedule:
    route_id: str
    changes: tuple  # ((time, value), ...), increasing in time.


def _integer(value, what, low=1):
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise ConfigError(f"{LAW_ID}: {what} is an integer >= {low}")
    return value


def _positive(value, what):
    v = _number(value, f"{LAW_ID}: {what}")
    if not math.isfinite(v) or v <= 0:
        raise ConfigError(f"{LAW_ID}: {what} is finite and positive")
    return float(v)


def _counts(raw, listed, what, *, signed=False):
    """{row: integer} as ((row, count), ...): rows listed, counts nonzero (positive unless
    signed)."""
    if type(raw) is not dict or not raw:
        raise ConfigError(f"{LAW_ID}: {what} is a non-empty object {{row: count}}")
    out = []
    for row, count in raw.items():
        if row not in listed:
            raise ConfigError(f"{LAW_ID}: {what} names {row!r}, which is not a listed species")
        if isinstance(count, bool) or not isinstance(count, int) or count == 0:
            raise ConfigError(f"{LAW_ID}: {what}'s count for {row!r} is a nonzero integer")
        if not signed and count < 0:
            raise ConfigError(f"{LAW_ID}: {what}'s count for {row!r} is positive")
        out.append((row, count))
    return tuple(out)


def _saturations(raw, rows, what):
    if type(raw) is not dict or set(raw) != set(rows):
        raise ConfigError(f"{LAW_ID}: {what} gives K (mM) for exactly the rows {sorted(rows)}")
    return tuple((row, _positive(raw[row], f"{what} for {row!r}")) for row in rows)


def _cited(raw, what):
    """A route's standard_free_energy: None, or one of FreeEnergyEntry's two forms."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"{LAW_ID}: {what} is null or an object")
    if set(raw) == {"dG_RT"}:
        if not _finite(raw["dG_RT"]):
            raise ConfigError(f"{LAW_ID}: {what}'s dG_RT is a finite number")
        return CitedFreeEnergy(float(raw["dG_RT"]), None, None, 0.0)
    if set(raw) != {"dG_kJ_mol", "basis", "dG_RT_offset"}:
        raise ConfigError(f"{LAW_ID}: {what} gives {{dG_RT}} or {{dG_kJ_mol, basis, dG_RT_offset}}")
    if not (_finite(raw["dG_kJ_mol"]) and _finite(raw["dG_RT_offset"])):
        raise ConfigError(f"{LAW_ID}: {what}'s dG_kJ_mol and dG_RT_offset are finite numbers")
    if raw["basis"] not in kind_registry.DG_BASES:
        raise ConfigError(f"{LAW_ID}: {what}'s basis is one of {', '.join(kind_registry.DG_BASES)}")
    return CitedFreeEnergy(None, float(raw["dG_kJ_mol"]), raw["basis"], float(raw["dG_RT_offset"]))


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _cited_to_dict(cited):
    if cited is None:
        return None
    if cited.dG_RT is not None:
        return dict(dG_RT=cited.dG_RT)
    return dict(dG_kJ_mol=cited.dG_kJ_mol, basis=cited.basis, dG_RT_offset=cited.offset_RT)


def parse_declaration(raw, base):
    keys = {"law", "standard_concentration_mM", "species", "pools", "chains", "degradations",
            "transfers"}  # fmt: skip
    _fields(raw, keys, "templated polymerisation")
    if raw["law"] != LAW_ID:
        raise ConfigError("Templated polymerisation requires law " + LAW_ID)
    c0 = _positive(raw["standard_concentration_mM"], "standard_concentration_mM")
    entries = raw["species"]
    if type(entries) is not list or not entries:
        raise ConfigError(f"{LAW_ID} declares its species in a non-empty list")
    for entry in entries:
        _fields(entry, {"id", "catalogue", "evidence", "standard_mu_RT"}, f"{LAW_ID} species")
    identities = common.parse_species(
        [dict(id=e["id"], catalogue=e["catalogue"], evidence=e["evidence"]) for e in entries],
        base,
        LAW_ID,
        limit=": version 1 is the sheet's neutral reduction (the charged form is a later arm)",
    )
    mu = []
    for e in entries:
        value = _number(e["standard_mu_RT"], f"{LAW_ID}: {e['id']}'s standard_mu_RT")
        if not math.isfinite(value):
            raise ConfigError(f"{LAW_ID}: {e['id']}'s standard_mu_RT is finite")
        mu.append(float(value))
    listed = [s.id for s in identities]
    cells = [c.id for c in base.model.cells]
    lists = {}
    for key in ("pools", "chains", "degradations", "transfers"):
        if type(raw[key]) is not list:
            raise ConfigError(f"{LAW_ID}: {key} is an explicit list")
        lists[key] = raw[key]
    pools = []
    for item in lists["pools"]:
        _fields(item, {"id", "cell", "machines"}, f"{LAW_ID} pool")
        if item["cell"] not in cells:
            raise ConfigError(f"{LAW_ID}: pool {item['id']!r} is in an unknown cell")
        machines = _number(item["machines"], f"{LAW_ID}: pool {item['id']}'s machines")
        if not math.isfinite(machines) or machines < 0:
            raise ConfigError(f"{LAW_ID}: a pool's machines are finite and >= 0")
        pools.append(Pool(identifier(item["id"]), item["cell"], float(machines)))
    pool_cells = {p.id: p.cell for p in pools}
    chains = []
    chain_keys = {"id", "pool", "template", "product", "residues", "stages", "speed_per_s",
                  "draws", "releases", "saturation_mM"}  # fmt: skip
    for item in lists["chains"]:
        _fields(item, chain_keys, f"{LAW_ID} chain")
        name = identifier(item["id"])
        if item["pool"] not in pool_cells:
            raise ConfigError(f"{LAW_ID}: chain {name} names an unknown pool")
        template = item["template"]
        if (
            type(template) is not dict
            or len(template) != 1
            or set(template) - {"copies", "species"}
        ):
            raise ConfigError(f"{LAW_ID}: chain {name}'s template is {{copies: T}} or {{species}}")
        copies = species = None
        if "copies" in template:
            copies = _integer(template["copies"], f"chain {name}'s template copies")
        else:
            species = template["species"]
            if species not in listed:
                raise ConfigError(f"{LAW_ID}: chain {name}'s template is not a listed species")
        if item["product"] not in listed:
            raise ConfigError(f"{LAW_ID}: chain {name}'s product is not a listed species")
        residues = _integer(item["residues"], f"chain {name}'s residues")
        stages = _integer(item["stages"], f"chain {name}'s stages")
        if residues % stages:
            raise ConfigError(f"{LAW_ID}: chain {name}'s stages divide its residues (r = L/m)")
        draws = _counts(item["draws"], listed, f"chain {name}'s draws")
        releases = _counts(item["releases"], listed, f"chain {name}'s releases")
        drawn = [row for row, _ in draws]
        if set(drawn) & {row for row, _ in releases} or item["product"] in {
            *drawn,
            *dict(releases),
        }:
            raise ConfigError(f"{LAW_ID}: chain {name} draws, releases and makes distinct rows")
        chains.append(
            Chain(
                name,
                item["pool"],
                pool_cells[item["pool"]],
                copies,
                species,
                item["product"],
                residues,
                stages,
                _positive(item["speed_per_s"], f"chain {name}'s speed"),
                draws,
                releases,
                _saturations(item["saturation_mM"], drawn, f"chain {name}'s saturation_mM"),
            )
        )
    made = {c.product: c.residues for c in chains}
    degradations = []
    for item in lists["degradations"]:
        _fields(item, {"id", "cell", "polymer", "residues", "monomers", "standard_free_energy"},
                f"{LAW_ID} degradation")  # fmt: skip
        name = identifier(item["id"])
        if item["cell"] not in cells or item["polymer"] not in listed:
            raise ConfigError(f"{LAW_ID}: degradation {name} names an unknown cell or polymer")
        residues = _integer(item["residues"], f"degradation {name}'s residues")
        if item["polymer"] in made and made[item["polymer"]] != residues:
            raise ConfigError(
                f"{LAW_ID}: degradation {name}'s polymer has {made[item['polymer']]} residues "
                "where its chain makes it"
            )
        monomers = _counts(item["monomers"], listed, f"degradation {name}'s monomers")
        if item["polymer"] in dict(monomers):
            raise ConfigError(f"{LAW_ID}: degradation {name}'s polymer is not its monomer")
        cited = _cited(item["standard_free_energy"], f"degradation {name}'s standard_free_energy")
        degradations.append(
            Degradation(name, item["cell"], item["polymer"], residues, monomers, cited)
        )
    transfers = []
    for item in lists["transfers"]:
        _fields(item, {"id", "cell", "stoichiometry", "saturation_mM", "share",
                       "standard_free_energy"}, f"{LAW_ID} transfer")  # fmt: skip
        name = identifier(item["id"])
        if item["cell"] not in cells:
            raise ConfigError(f"{LAW_ID}: transfer {name} is in an unknown cell")
        nu = _counts(item["stoichiometry"], listed, f"transfer {name}'s stoichiometry", signed=True)
        consumed = [row for row, v in nu if v < 0]
        if not consumed or len(consumed) == len(nu):
            raise ConfigError(f"{LAW_ID}: transfer {name} consumes some rows and makes others")
        transfers.append(
            Transfer(
                name,
                item["cell"],
                nu,
                _saturations(item["saturation_mM"], consumed, f"transfer {name}'s saturation_mM"),
                _integer(item["share"], f"transfer {name}'s share"),
                _cited(item["standard_free_energy"], f"transfer {name}'s standard_free_energy"),
            )
        )
    declaration = Polymerisation(
        LAW_ID, c0, identities, tuple(mu), tuple(pools), tuple(chains), tuple(degradations),
        tuple(transfers),
    )  # fmt: skip
    ids = [p.id for p in pools] + list(declaration.route_ids())
    if len(set(ids)) != len(ids):
        raise ConfigError(f"{LAW_ID}: every pool and route ID is distinct")
    used = {p for p in (c.pool for c in chains)}
    if used != set(pool_cells):
        raise ConfigError(f"{LAW_ID}: every pool serves a chain")
    named = set()
    for c in chains:
        named |= {c.product, *dict(c.draws), *dict(c.releases)}
        named |= {c.template_species} - {None}
    for d in degradations:
        named |= {d.polymer, *dict(d.monomers)}
    for t in transfers:
        named |= set(dict(t.stoichiometry))
    if set(listed) - named:
        raise ConfigError(f"{LAW_ID}: listed species {sorted(set(listed) - named)} are unused")
    return declaration


def declaration_to_dict(d):
    return dict(
        law=d.law,
        standard_concentration_mM=d.c0_mM,
        species=[
            dict(**common.species_to_dict((s,))[0], standard_mu_RT=mu)
            for s, mu in zip(d.species, d.mu_RT, strict=True)
        ],
        pools=[dict(id=p.id, cell=p.cell, machines=p.machines) for p in d.pools],
        chains=[
            dict(
                id=c.id,
                pool=c.pool,
                template=(
                    dict(copies=c.template_copies)
                    if c.template_copies is not None
                    else dict(species=c.template_species)
                ),
                product=c.product,
                residues=c.residues,
                stages=c.stages,
                speed_per_s=c.speed_per_s,
                draws=dict(c.draws),
                releases=dict(c.releases),
                saturation_mM=dict(c.saturation_mM),
            )
            for c in d.chains
        ],
        degradations=[
            dict(
                id=x.id,
                cell=x.cell,
                polymer=x.polymer,
                residues=x.residues,
                monomers=dict(x.monomers),
                standard_free_energy=_cited_to_dict(x.standard_free_energy),
            )
            for x in d.degradations
        ],  # fmt: skip
        transfers=[
            dict(
                id=t.id,
                cell=t.cell,
                stoichiometry=dict(t.stoichiometry),
                saturation_mM=dict(t.saturation_mM),
                share=t.share,
                standard_free_energy=_cited_to_dict(t.standard_free_energy),
            )
            for t in d.transfers
        ],  # fmt: skip
    )


def parse_schedule(raw, base, declaration):
    rows = raw[EXPERIMENT_KEY]
    if type(rows) is not list:
        raise ConfigError(f"{LAW_ID}: {EXPERIMENT_KEY} is an explicit list")
    dt, end = base.execution.dt, base.experiment.end_time
    known = list(declaration.route_ids())
    schedules = {}
    for row in rows:
        _fields(row, {"route_id", "schedule"}, f"{LAW_ID} control")
        name = row["route_id"]
        if name not in known or name in schedules:
            raise ConfigError(f"{LAW_ID}: one schedule per declared route ({name!r})")
        changes = row["schedule"]
        if type(changes) is not list or not changes:
            raise ConfigError(f"{LAW_ID}: route {name}'s schedule is a non-empty list")
        parsed = []
        for index, change in enumerate(changes):
            _fields(change, {"time", "value"}, f"{LAW_ID} change")
            time = _number(change["time"], f"{LAW_ID}: a schedule time")
            if index == 0 and time != 0.0:
                raise ConfigError(f"{LAW_ID}: route {name}'s schedule starts at 0")
            if time != round(time / dt) * dt:
                raise ConfigError(f"{LAW_ID}: a schedule change is an exact multiple of dt")
            if index > 0 and not 0.0 < time < end:
                raise ConfigError(f"{LAW_ID}: a schedule change lies inside 0 < t < end")
            value = _number(change["value"], f"{LAW_ID}: route {name}'s value")
            if not math.isfinite(value) or value < 0:
                raise ConfigError(f"{LAW_ID}: route {name}'s value is finite and >= 0")
            parsed.append((time, float(value)))
        times = [t for t, _ in parsed]
        if any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ConfigError(f"{LAW_ID}: route {name}'s schedule times increase strictly")
        schedules[name] = tuple(parsed)
    missing = [k for k in known if k not in schedules]
    if missing:
        raise ConfigError(f"{LAW_ID}: route {missing[0]} needs its schedule in {EXPERIMENT_KEY}")
    return tuple(RouteSchedule(k, schedules[k]) for k in known)


def schedule_to_dict(schedule):
    return {
        EXPERIMENT_KEY: [
            dict(route_id=s.route_id, schedule=[dict(time=t, value=v) for t, v in s.changes])
            for s in schedule
        ]
    }


def value_at(changes, time):
    """The value in force at `time` (a change at t applies from t)."""
    value = changes[0][1]
    for t, v in changes:
        if t <= time:
            value = v
    return value


# ------------------------------------------------------------------ definition checks


def check_writers(spec, declaration):
    """Refuse another writer of a listed row (one writer: the sheet's §4.5 and the design's §7.5):
    another author's declaration of it, a D152 reaction writing it, and an in-step mover."""
    listed = {s.id for s in declaration.species}
    for op, other, _ in composite_spec.entries(spec):
        if op.LAW_ID == LAW_ID:
            continue
        if op.LAW_ID == species_reactions.LAW_ID:
            hit = sorted(name for name, _ in species_reactions.written(other) if name in listed)
            if hit:
                raise ConfigError(
                    f"{LAW_ID}: a {op.LAW_ID} reaction writes {hit[0]!r}; this operator is the "
                    "one writer of its listed rows (its transfers recharge them)"
                )
        elif op.IDENTITY_ROLE == "author":
            shared = sorted(listed & {s.id for s in op.species_identities(other)})
            if shared:
                raise ConfigError(
                    f"{LAW_ID}: {op.LAW_ID} also declares {shared[0]!r}; this operator is the one "
                    "writer of its listed rows"
                )
    moved = species_registry.moved_in_step(spec)
    for name in sorted(listed):
        movers = moved.get(name, {}).get("cell", ())
        if movers:
            raise ConfigError(
                f"{LAW_ID}: {name!r} is moved inside the inner step by {movers[0]}; its writer is "
                "this split part's half-steps only"
            )


def check_rate_bound(spec, declaration, schedule):
    """Refuse dt times a route's largest static rate above RATE_BOUND: a chain's kappa, a
    degradation's k, and a gene-templated chain's initiation k_I c_T (the run-time stage
    condition covers the rest)."""
    dt = spec.execution.dt
    top = {s.route_id: max(v for _, v in s.changes) for s in schedule}
    volumes = {c.id: c.volume_pL for c in spec.model.cells}
    for c in declaration.chains:
        kappa = c.speed_per_s * c.stages / c.residues
        rate = kappa
        if c.template_copies is not None:
            rate = max(rate, top[c.id] * c.template_copies * COPY_FMOL / volumes[c.cell])
        if dt * rate > RATE_BOUND:
            raise ConfigError(
                f"{LAW_ID}: chain {c.id} has dt times its largest rate = {dt * rate:.3g} > "
                f"{RATE_BOUND}"
            )
    for d in declaration.degradations:
        if dt * top[d.id] > RATE_BOUND:
            raise ConfigError(f"{LAW_ID}: degradation {d.id} has dt k = {dt * top[d.id]:.3g} > 1")


# ------------------------------------------------------------------ binding


def _one_hot(index, size):
    out = np.zeros((len(index), size))
    for i, j in enumerate(index):
        if j is not None:
            out[i, j] = 1.0
    return out


def bind(spec, declaration):
    m, x = spec.model, spec.execution
    species = list(m.species_ids)
    listed = [s.id for s in declaration.species]
    k = len(listed)
    cells = [c.id for c in m.cells]
    n_cells = x.capacity
    pools, chains = declaration.pools, declaration.chains
    degradations, transfers = declaration.degradations, declaration.transfers
    pool_index = {p.id: i for i, p in enumerate(pools)}
    depth = max((c.stages for c in chains), default=0)
    mu = dict(zip(listed, declaration.mu_RT, strict=True))

    def per_row(pairs):
        out = np.zeros(k)
        for row, value in pairs:
            out[listed.index(row)] = value
        return out

    present = np.zeros((len(chains), depth), dtype=bool)
    last = np.zeros((len(chains), depth), dtype=bool)
    held = np.zeros((len(chains), depth))
    for i, c in enumerate(chains):
        present[i, : c.stages] = True
        last[i, c.stages - 1] = True
        held[i, : c.stages] = np.arange(c.stages) * (c.residues // c.stages)
    draws = np.array([per_row(c.draws) for c in chains]).reshape(len(chains), k)
    releases = np.array([per_row(c.releases) for c in chains]).reshape(len(chains), k)
    saturates = draws > 0
    chain_K = np.array([per_row(c.saturation_mM) for c in chains]).reshape(len(chains), k)
    chain_K = np.where(saturates, chain_K, 1.0)
    tr_nu = np.array([per_row(t.stoichiometry) for t in transfers]).reshape(len(transfers), k)
    tr_K = np.array([per_row(t.saturation_mM) for t in transfers]).reshape(len(transfers), k)
    tr_saturates = tr_nu < 0
    layout = dict(
        poly_rows=np.asarray([species.index(s) for s in listed], dtype=np.int64),
        poly_mu_RT=np.asarray(declaration.mu_RT, dtype=float),
        poly_c0_mM=np.asarray(declaration.c0_mM, dtype=float),
        poly_pool_total_fmol=np.asarray([p.machines * COPY_FMOL for p in pools], dtype=float),
        poly_chain_cell=_one_hot([cells.index(c.cell) for c in chains], n_cells),
        poly_chain_pool=_one_hot([pool_index[c.pool] for c in chains], len(pools)),
        poly_chain_kappa=np.asarray(
            [c.speed_per_s * c.stages / c.residues for c in chains], dtype=float
        ),
        poly_chain_r=np.asarray([c.residues / c.stages for c in chains], dtype=float),
        poly_chain_length=np.asarray([float(c.residues) for c in chains], dtype=float),
        poly_chain_present=present,
        poly_chain_last=last,
        poly_chain_held=held,
        poly_chain_net=releases - draws,
        poly_chain_draws=draws,
        poly_chain_releases=releases,
        poly_chain_saturates=saturates,
        poly_chain_K_mM=chain_K,
        poly_chain_product=_one_hot([listed.index(c.product) for c in chains], k),
        poly_chain_template=_one_hot(
            [
                None if c.template_species is None else listed.index(c.template_species)
                for c in chains
            ],
            k,
        ),  # fmt: skip
        poly_chain_copies=np.asarray([float(c.template_copies or 0) for c in chains]),
        # The residue's potential at 1 M: the product's mu° at c0 moved to 1 M, over L.
        poly_chain_residue_mu_RT=np.asarray(
            [
                (mu[c.product] - math.log(declaration.c0_mM / STANDARD_MM)) / c.residues
                for c in chains
            ],
            dtype=float,
        ),  # fmt: skip
        poly_deg_cell=_one_hot([cells.index(d.cell) for d in degradations], n_cells),
        poly_deg_polymer=_one_hot([listed.index(d.polymer) for d in degradations], k),
        poly_deg_monomers=np.array([per_row(d.monomers) for d in degradations]).reshape(
            len(degradations), k
        ),
        poly_deg_length=np.asarray([float(d.residues) for d in degradations], dtype=float),
        poly_tr_cell=_one_hot([cells.index(t.cell) for t in transfers], n_cells),
        poly_tr_nu=tr_nu,
        poly_tr_saturates=tr_saturates,
        poly_tr_K_mM=np.where(tr_saturates, tr_K, 1.0),
        poly_tr_share=np.asarray([float(t.share) for t in transfers], dtype=float),
    )
    s, c = len(species), n_cells
    state = dict(
        poly_free_machines_fmol=layout["poly_pool_total_fmol"].copy(),
        poly_complexes_fmol=np.zeros((len(chains), depth)),
        poly_initiated_fmol=np.zeros(len(chains)),
        poly_stage_exits_fmol=np.zeros(len(chains)),
        poly_released_fmol=np.zeros(len(chains)),
        poly_degraded_fmol=np.zeros(len(degradations)),
        poly_transferred_fmol=np.zeros(len(transfers)),
        poly_produced_fmol=np.zeros((s, c)),
        poly_consumed_fmol=np.zeros((s, c)),
        poly_dissipated_energy_pJ=np.zeros(c),
        poly_chain_heat_pJ=np.zeros(len(chains)),
        poly_degradation_heat_pJ=np.zeros(len(degradations)),
        poly_transfer_heat_pJ=np.zeros(len(transfers)),
        poly_standard_energy_pJ=np.zeros(c),
        poly_energy_magnitude_pJ=np.zeros(c),
    )
    return state, layout


# ------------------------------------------------------------------ the law


def _product(values, mask, *, xp):
    """prod over the last axis of `values` where `mask`, 1 elsewhere."""
    return xp.prod(xp.where(mask, values, 1.0), axis=-1)


def fluxes(n, free, complexes, controls, p, volume, *, xp):
    """Every route's flux at amounts n [k, cell] (fmol), free machines [pool] and complexes
    [chain, stage]; with the affinities its domain reads and the unidirectional rates its stage
    condition reads."""
    init_rate, deg_rate, tr_cap = controls
    c = n / volume[None, :]  # mM.
    ln_rel = xp.log(c / p.poly_c0_mM)  # ln(c/c0)
    mu = p.poly_mu_RT[:, None] + ln_rel  # [k, cell] mu/RT.
    # Chains, at their cells.
    c_chain = p.poly_chain_cell @ c.T  # [chain, k]
    mu_chain = p.poly_chain_cell @ mu.T
    sat = _product(c_chain / (p.poly_chain_K_mM + c_chain), p.poly_chain_saturates, xp=xp)
    x_chain = p.poly_chain_residue_mu_RT + xp.sum(p.poly_chain_net * mu_chain, axis=1)
    phi = sat * -xp.expm1(x_chain)
    stage = p.poly_chain_kappa * phi  # [chain] the stage rate.
    j_stage = xp.where(p.poly_chain_present, stage[:, None] * complexes, 0.0)
    v_chain = p.poly_chain_cell @ volume
    gene = p.poly_chain_copies * COPY_FMOL / xp.where(v_chain > 0, v_chain, 1.0)
    template = xp.sum(p.poly_chain_template * c_chain, axis=1) + gene  # mM
    lam = init_rate * template  # [chain] 1/s per free machine.
    pool_free = p.poly_chain_pool @ free  # [chain] its pool's free machines.
    j_init = lam * pool_free
    product = xp.sum(p.poly_chain_product * c_chain, axis=1)
    # Degradations.
    n_deg = p.poly_deg_cell @ n.T  # [deg, k]
    mu_deg = p.poly_deg_cell @ mu.T
    polymer = xp.sum(p.poly_deg_polymer * n_deg, axis=1)
    y = (
        p.poly_deg_length * xp.sum(p.poly_deg_monomers * mu_deg, axis=1)
        - xp.sum(p.poly_deg_polymer * mu_deg, axis=1)
    ) / p.poly_deg_length
    j_deg = deg_rate * polymer * -xp.expm1(y)
    # Transfers.
    c_tr = p.poly_tr_cell @ c.T
    mu_tr = p.poly_tr_cell @ mu.T
    v_tr = p.poly_tr_cell @ volume
    forward = v_tr * tr_cap * _product(c_tr / (p.poly_tr_K_mM + c_tr), p.poly_tr_saturates, xp=xp)
    x_tr = xp.sum(p.poly_tr_nu * mu_tr, axis=1)
    j_tr = forward * -xp.expm1(x_tr / p.poly_tr_share)
    backward = forward * xp.exp(x_tr / p.poly_tr_share)
    # The one-sided domains, at the routes in use.
    in_use = (xp.sum(complexes, axis=1) > 0) | (j_init > 0)
    ok = xp.all(xp.where(in_use, (x_chain <= X_DOM) & (product <= STANDARD_MM), True))
    ok &= xp.all(xp.where((deg_rate > 0) & (polymer > 0), y <= X_DOM, True))
    # Unidirectional consumption per (row, cell), the stage condition's rates.
    s_total = xp.sum(j_stage, axis=1)  # [chain] every stage's exits.
    draw = (p.poly_chain_r * s_total)[:, None] * p.poly_chain_draws  # [chain, k]
    used = draw.T @ p.poly_chain_cell + (p.poly_deg_polymer * j_deg[:, None]).T @ p.poly_deg_cell
    used += (
        xp.where(p.poly_tr_nu < 0, -p.poly_tr_nu, 0.0) * forward[:, None]
        + xp.where(p.poly_tr_nu > 0, p.poly_tr_nu, 0.0) * backward[:, None]
    ).T @ p.poly_tr_cell
    return (j_init, j_stage, j_deg, j_tr), dict(
        ok=ok,
        stage=stage,
        lam_pool=p.poly_chain_pool.T @ lam,
        used=used,
    )


def changes(j_init, j_stage, j_deg, j_tr, p, *, xp):
    """(dn [k, cell], d free [pool], d complexes [chain, stage], produced, consumed) of fluxes or
    their extents: A J, every move's stoichiometry (the sheet's §4.7)."""
    s_total = xp.sum(j_stage, axis=1)
    released = xp.sum(xp.where(p.poly_chain_last, j_stage, 0.0), axis=1)
    r = p.poly_chain_r[:, None]
    chain_made = r * s_total[:, None] * p.poly_chain_releases + released[:, None] * (
        p.poly_chain_product
    )
    chain_used = r * s_total[:, None] * p.poly_chain_draws
    deg_made = (p.poly_deg_length * j_deg)[:, None] * p.poly_deg_monomers
    deg_used = j_deg[:, None] * p.poly_deg_polymer
    tr = p.poly_tr_nu * j_tr[:, None]
    produced = (
        chain_made.T @ p.poly_chain_cell
        + deg_made.T @ p.poly_deg_cell
        + xp.where(tr > 0, tr, 0.0).T @ p.poly_tr_cell
    )
    consumed = (
        chain_used.T @ p.poly_chain_cell
        + deg_used.T @ p.poly_deg_cell
        + xp.where(tr < 0, -tr, 0.0).T @ p.poly_tr_cell
    )
    d_free = (released - j_init) @ p.poly_chain_pool
    upstream = xp.concatenate([j_init[:, None], j_stage[:, :-1]], axis=1)
    d_complexes = xp.where(p.poly_chain_present, upstream - j_stage, 0.0)
    return produced - consumed, d_free, d_complexes, produced, consumed


def divided_potential(n, dn, volume, p, rt, *, xp):
    """mu-bar [k, cell], pJ/fmol: each row's divided difference over the half-step of
    g(n) = RT n (ln(n/V) - 1) + RT (mu°/RT - ln c0) n, in D152's stable form (the series
    1 + x/2 - x^2/6 for |x| < SERIES_BELOW), so that mu-bar dn is the row's booked dG."""
    x = dn / n
    small = xp.abs(x) < SERIES_BELOW
    ratio = xp.where(
        small, 1.0 + x / 2 - x * x / 6, (1.0 + x) * xp.log1p(x) / xp.where(small, 1.0, x)
    )
    standard = (p.poly_mu_RT - xp.log(p.poly_c0_mM))[:, None]
    return rt * (xp.log(n / volume[None, :]) + ratio - 1.0 + standard)


def route_heats(n0, dn, d_transit, extents, volume, active, p, rt, *, xp):
    """Each route's heat over the half-step (module docstring, Energy), pJ: (chain [chain],
    degradation [deg], transfer [transfer]), zero at an inactive cell."""
    j_init, j_stage, j_deg, j_tr = extents
    mu_bar = divided_potential(n0, dn, volume, p, rt, xp=xp)  # [k, cell]
    on = xp.where(active, 1.0, 0.0)
    s_total = xp.sum(j_stage, axis=1)
    released = xp.sum(xp.where(p.poly_chain_last, j_stage, 0.0), axis=1)
    mu_chain = p.poly_chain_cell @ mu_bar.T  # [chain, k]
    chain = -(
        p.poly_chain_r * s_total * xp.sum(p.poly_chain_net * mu_chain, axis=1)
        + released * xp.sum(p.poly_chain_product * mu_chain, axis=1)
        + rt * p.poly_chain_residue_mu_RT * d_transit
    )
    mu_deg = p.poly_deg_cell @ mu_bar.T
    degradation = -j_deg * (
        p.poly_deg_length * xp.sum(p.poly_deg_monomers * mu_deg, axis=1)
        - xp.sum(p.poly_deg_polymer * mu_deg, axis=1)
    )
    transfer = -j_tr * xp.sum(p.poly_tr_nu * (p.poly_tr_cell @ mu_bar.T), axis=1)
    return (
        xp.where(p.poly_chain_cell @ on > 0, chain, 0.0),
        xp.where(p.poly_deg_cell @ on > 0, degradation, 0.0),
        xp.where(p.poly_tr_cell @ on > 0, transfer, 0.0),
    )


def poly_half_step(state, controls, h, p, *, xp=jnp):
    """(state after h, valid): SSPRK(3,3) on the operator's variables, every move booked."""
    rows, active = p.poly_rows, p.active
    volume = xp.where(active, p.volume, 1.0)
    n0 = xp.where(active[None, :], p.amount_reference[rows] + state.amount_increment[rows], 1.0)
    f0, c0 = state.poly_free_machines_fmol, state.poly_complexes_fmol

    def stage_valid(n, free, complexes, info):
        valid = info["ok"]
        valid &= xp.all(xp.where(active[None, :], xp.isfinite(n) & (n > 0), True))
        valid &= xp.all(xp.isfinite(free) & (free >= 0))
        valid &= xp.all(xp.isfinite(complexes) & (complexes >= 0))
        valid &= xp.all(h * info["stage"] <= THETA)
        valid &= xp.all(h * info["lam_pool"] <= THETA)
        valid &= xp.all(xp.where(active[None, :], h * info["used"] <= THETA * n, True))
        return valid

    j1, i1 = fluxes(n0, f0, c0, controls, p, volume, xp=xp)
    d1 = changes(*j1, p, xp=xp)
    y2 = (n0 + h * d1[0], f0 + h * d1[1], c0 + h * d1[2])
    j2, i2 = fluxes(*y2, controls, p, volume, xp=xp)
    d2 = changes(*j2, p, xp=xp)
    y3 = (
        n0 + h * (d1[0] + d2[0]) / 4,
        f0 + h * (d1[1] + d2[1]) / 4,
        c0 + h * (d1[2] + d2[2]) / 4,
    )
    j3, i3 = fluxes(*y3, controls, p, volume, xp=xp)
    extents = tuple(h * (a + b + 4 * c) / 6 for a, b, c in zip(j1, j2, j3, strict=True))
    dn, d_free, d_complexes, produced, consumed = changes(*extents, p, xp=xp)
    dn = xp.where(active[None, :], dn, 0.0)
    produced = xp.where(active[None, :], produced, 0.0)
    consumed = xp.where(active[None, :], consumed, 0.0)
    n1, free1, complexes1 = n0 + dn, f0 + d_free, c0 + d_complexes
    # Energy (module docstring): the exact dG of the move, per cell, booked as heat.
    rt = 1e-3 * R * p.temperature  # pJ per fmol per unit of mu/RT.
    chem = species_sum(
        adapter.species_chemical_free_energy_pJ(n0, dn, volume[None, :], p.temperature, xp=xp),
        xp=xp,
    )
    std_terms = rt * (p.poly_mu_RT - xp.log(p.poly_c0_mM))[:, None] * dn
    d_transit = xp.sum(p.poly_chain_held * d_complexes, axis=1)  # dW: j r residues per complex.
    transit = (rt * p.poly_chain_residue_mu_RT * d_transit) @ p.poly_chain_cell
    standard = species_sum(std_terms, xp=xp) + transit
    heat = -(chem + standard)
    magnitude = (
        species_sum(
            adapter.species_chemical_magnitude_pJ(n0, dn, volume[None, :], p.temperature, xp=xp),
            xp=xp,
        )
        + species_sum(xp.abs(std_terms), xp=xp)
        + xp.abs(rt * p.poly_chain_residue_mu_RT * d_transit) @ p.poly_chain_cell
    )
    chain_heat, deg_heat, tr_heat = route_heats(
        n0, dn, d_transit, extents, volume, active, p, rt, xp=xp
    )
    full = state.amount_increment.shape[0]
    j_init, j_stage, j_deg, j_tr = extents
    new = state._replace(
        amount_increment=_set_rows(state.amount_increment, rows,
                                   state.amount_increment[rows] + dn, xp=xp),
        poly_free_machines_fmol=free1,
        poly_complexes_fmol=complexes1,
        poly_initiated_fmol=state.poly_initiated_fmol + j_init,
        poly_stage_exits_fmol=state.poly_stage_exits_fmol + xp.sum(j_stage, axis=1),
        poly_released_fmol=state.poly_released_fmol
        + xp.sum(xp.where(p.poly_chain_last, j_stage, 0.0), axis=1),
        poly_degraded_fmol=state.poly_degraded_fmol + j_deg,
        poly_transferred_fmol=state.poly_transferred_fmol + j_tr,
        poly_produced_fmol=state.poly_produced_fmol + _on_species(full, rows, produced, xp=xp),
        poly_consumed_fmol=state.poly_consumed_fmol + _on_species(full, rows, consumed, xp=xp),
        poly_dissipated_energy_pJ=state.poly_dissipated_energy_pJ + xp.where(active, heat, 0.0),
        poly_chain_heat_pJ=state.poly_chain_heat_pJ + chain_heat,
        poly_degradation_heat_pJ=state.poly_degradation_heat_pJ + deg_heat,
        poly_transfer_heat_pJ=state.poly_transfer_heat_pJ + tr_heat,
        poly_standard_energy_pJ=state.poly_standard_energy_pJ + xp.where(active, standard, 0.0),
        poly_energy_magnitude_pJ=state.poly_energy_magnitude_pJ
        + xp.where(active, magnitude, 0.0),
    )  # fmt: skip
    flowing = xp.any(j_init > 0) | xp.any(j_stage > 0) | xp.any(j_deg > 0) | xp.any(j_tr != 0)
    selected = type(state)(*(xp.where(flowing, a, b) for a, b in zip(new, state, strict=True)))
    valid = stage_valid(n0, f0, c0, i1) & stage_valid(*y2, i2) & stage_valid(*y3, i3)
    valid &= xp.all(xp.where(active[None, :], xp.isfinite(n1) & (n1 > 0), True))
    valid &= xp.all(xp.isfinite(free1) & (free1 >= 0))
    valid &= xp.all(xp.isfinite(complexes1) & (complexes1 >= 0))
    valid &= own_valid(selected, xp=xp)
    return selected, valid


def _on_species(full, rows, values, *, xp):
    """values [k, cell] on the full species axis at the listed rows, zero elsewhere."""
    if xp is jnp:
        return jnp.zeros((full, values.shape[1])).at[rows].add(values)
    out = np.zeros((full, values.shape[1]))
    np.add.at(out, rows, values)
    return out


def _set_rows(full, rows, values, *, xp):
    """full with its listed rows replaced (the other rows untouched, bit for bit)."""
    if xp is jnp:
        return full.at[rows].set(values)
    out = np.array(full, copy=True)
    out[rows] = values
    return out


def own_valid(state, *, xp):
    valid = xp.asarray(True)
    for name in (
        "poly_free_machines_fmol",
        "poly_complexes_fmol",
        "poly_initiated_fmol",
        "poly_stage_exits_fmol",
        "poly_released_fmol",
        "poly_degraded_fmol",
        "poly_produced_fmol",
        "poly_consumed_fmol",
        "poly_energy_magnitude_pJ",
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(value >= 0)
    for name in (
        "poly_transferred_fmol",
        "poly_dissipated_energy_pJ",
        "poly_chain_heat_pJ",
        "poly_degradation_heat_pJ",
        "poly_transfer_heat_pJ",
        "poly_standard_energy_pJ",
    ):
        valid &= xp.all(xp.isfinite(getattr(state, name)))
    return valid


def poly_domain_valid(state, p, *, xp):
    """Its own fields and its listed rows' amounts (finite and positive at active cells)."""
    valid = own_valid(state, xp=xp)
    if p.poly_chain_present.shape[1]:
        valid &= xp.all(xp.where(p.poly_chain_present, True, state.poly_complexes_fmol == 0))
    rows = p.poly_rows
    amounts = p.amount_reference[rows] + state.amount_increment[rows]
    valid &= xp.all(xp.where(p.active[None, :], xp.isfinite(amounts) & (amounts > 0), True))
    return valid


# ------------------------------------------------------------------ the operator


class TemplatedPolymerisation(Operator):
    LAW_ID = LAW_ID
    IDENTITY_ROLE = "author"  # Species registry (D176): it declares the rows it writes.
    STEP_ID = STEP_ID
    SPLIT = True
    RK4 = "split"
    STATE_AXES = STATE_AXES
    HEAT_FIELDS = ("poly_dissipated_energy_pJ",)
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = (INITIATION, DEGRADATION, TRANSFER)
    # B1′: a chain's initiation rate constant, which a rate route may multiply in the half-steps
    # (the scheduled rate is the maximum).
    ROUTABLE_CONTROLS = MappingProxyType({INITIATION: "rate"})
    EXPERIMENT_KEYS = (EXPERIMENT_KEY,)
    CONFLICTS_VIEW = common.CONFLICTS_VIEW
    ENTITY_WRITES = {"amount_increment": ("poly_produced_fmol", "poly_consumed_fmol")}
    LEDGERS = LEDGERS
    LEDGER_DIAGNOSTICS = LEDGER_DIAGNOSTICS
    LEDGER_MESSAGE = LEDGER_MESSAGE
    VIEW_LAYERS = (
        {
            "id": "polymerisation",
            "label": "Templated polymerisation",
            "representation": "simulated",
        },
    )
    RECORD_KINDS = {
        "poly_free_machines_fmol": "amount",
        "poly_complexes_fmol": "amount",
        "poly_initiated_fmol": "cumulative",
        "poly_stage_exits_fmol": "cumulative",
        "poly_released_fmol": "cumulative",
        "poly_degraded_fmol": "cumulative",
        "poly_transferred_fmol": "cumulative",
        "poly_produced_fmol": "cumulative",
        "poly_consumed_fmol": "cumulative",
        "poly_chain_heat_pJ": "cumulative",
        "poly_degradation_heat_pJ": "cumulative",
        "poly_transfer_heat_pJ": "cumulative",
        "poly_standard_energy_pJ": "cumulative",
        "poly_energy_magnitude_pJ": "cumulative",
    }

    def view_sets(self, spec, declaration):
        """The run view's sets of its axes: pools, chains, stages, degradations and transfers."""
        depth = max((c.stages for c in declaration.chains), default=0)
        return {
            POOL_AXIS: {
                "id": POOL_AXIS,
                "ids": tuple(p.id for p in declaration.pools),
                "holds": "machine pool",
                "at": tuple({"cell": p.cell} for p in declaration.pools),
            },
            CHAIN_AXIS: {
                "id": CHAIN_AXIS,
                "ids": tuple(c.id for c in declaration.chains),
                "holds": "templated chain",
                "carries": tuple(c.product for c in declaration.chains),
                "at": tuple({"cell": c.cell} for c in declaration.chains),
            },
            STAGE_AXIS: {
                "id": STAGE_AXIS,
                "ids": tuple(f"stage_{j + 1}" for j in range(depth)),
                "holds": "chain stage",
            },
            DEGRADATION_AXIS: {
                "id": DEGRADATION_AXIS,
                "ids": tuple(d.id for d in declaration.degradations),
                "holds": "degradation",
                "carries": tuple(d.polymer for d in declaration.degradations),
                "at": tuple({"cell": d.cell} for d in declaration.degradations),
            },
            TRANSFER_AXIS: {
                "id": TRANSFER_AXIS,
                "ids": tuple(t.id for t in declaration.transfers),
                "holds": "transfer",
                "at": tuple({"cell": t.cell} for t in declaration.transfers),
            },
        }

    def view_events(self, spec, declaration, schedule):
        """Every scheduled value change of each route, at its cell (the entry at time 0 sets the
        start). It decides no cell's life, so there are no births or retirements."""
        layer = self.VIEW_LAYERS[0]["id"]
        cell = {r.id: r.cell for r in (*declaration.chains, *declaration.degradations,
                                       *declaration.transfers)}  # fmt: skip
        events = [
            dict(
                time=float(t),
                kind="polymerisation rate",
                layer=layer,
                at={"cell": cell[s.route_id]},
                label=f"{s.route_id}: {v!r}",
            )
            for s in schedule
            for t, v in s.changes
        ]
        return tuple(sorted(events, key=lambda e: (e["time"], e["label"])))

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_declaration(raw, base)

    def to_dict(self, declaration, base):
        return declaration_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_schedule(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return schedule_to_dict(schedule)

    def schedule_times(self, schedule):
        return tuple(sorted({t for s in schedule for t, _ in s.changes if t > 0}))

    def value_at(self, schedule, time):
        return tuple(value_at(s.changes, time) for s in schedule)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        values = np.array(records, dtype=float).reshape(len(records), -1)[indices]
        nc, nd = len(declaration.chains), len(declaration.degradations)
        return values[:, :nc], values[:, nc : nc + nd], values[:, nc + nd :]

    def routable_elements(self, declaration, field):
        """B1′: the initiation rate's elements are the chains, by chain ID, each at its pool's
        cell, in control order."""
        return tuple((c.id, c.cell) for c in declaration.chains)

    def species_identities(self, declaration):
        return declaration.species

    def species_potentials(self, declaration):
        """Its declared mu°/RT of each listed species at its c0 (check_potentials: the registry's,
        where it gives one, must agree; F2)."""
        return tuple(
            (s.id, mu, declaration.c0_mM)
            for s, mu in zip(declaration.species, declaration.mu_RT, strict=True)
        )

    def standard_free_energies(self, declaration):
        """The cited standard free energies of its degradations and transfers (seam E; the sheet's
        §3.3 entries), each a FreeEnergyEntry on the route's net move per unit at its c0: a
        polymer molecule degraded, a transfer turnover. Chains declare none: their dG° follows
        from the rows' potentials. check_free_energies holds each to the registry's."""
        out = []
        for route, cited in (
            *((d, d.standard_free_energy) for d in declaration.degradations),
            *((t, t.standard_free_energy) for t in declaration.transfers),
        ):
            if cited is None:
                continue
            if isinstance(route, Degradation):
                nu = ((route.polymer, -1),) + tuple(
                    (row, count * route.residues) for row, count in route.monomers
                )
            else:
                nu = tuple(route.stoichiometry)
            if cited.dG_RT is not None:
                entry = kind_registry.FreeEnergyEntry(nu, dG_RT=cited.dG_RT, c0=declaration.c0_mM)
            else:
                entry = kind_registry.FreeEnergyEntry(
                    nu,
                    c0=declaration.c0_mM,
                    dG_kJ_mol=cited.dG_kJ_mol,
                    dG_basis=cited.basis,
                    dG_RT_offset=cited.offset_RT,
                )
            out.append(entry)
        return tuple(out)

    def species_moieties(self, declaration):
        """Each route's net row change per unit (G3's hook; the sheet's §1.4): a finished product
        of a chain (L draws and releases per residue, one product), a polymer molecule degraded,
        a transfer turnover."""
        moves = []
        for c in declaration.chains:
            nu = {}
            for row, count in c.draws:
                nu[row] = nu.get(row, 0) - count * c.residues
            for row, count in c.releases:
                nu[row] = nu.get(row, 0) + count * c.residues
            nu[c.product] = nu.get(c.product, 0) + 1
            moves.append((f"chain {c.id}", tuple((s, v) for s, v in nu.items() if v)))
        for d in declaration.degradations:
            nu = {d.polymer: -1}
            for row, count in d.monomers:
                nu[row] = nu.get(row, 0) + count * d.residues
            moves.append((f"degradation {d.id}", tuple(nu.items())))
        for t in declaration.transfers:
            moves.append((f"transfer {t.id}", tuple(t.stoichiometry)))
        return tuple(moves)

    def check_definition(self, spec, declaration, schedule, model):
        common.check_species_cap(spec, LAW_ID)
        common.check_identities(spec, LAW_ID, declaration.species)
        check_writers(spec, declaration)
        check_rate_bound(spec, declaration, schedule)

    def batch_signature(self, declaration):
        """The static structure; identities, potentials and every rate are not part of it."""
        return (
            LAW_ID,
            tuple(s.id for s in declaration.species),
            tuple(p.cell for p in declaration.pools),
            tuple(
                (c.pool, c.template_copies is None, c.product, c.stages, c.draws, c.releases)
                for c in declaration.chains
            ),
            tuple((d.cell, d.polymer, d.monomers) for d in declaration.degradations),
            tuple((t.cell, t.stoichiometry) for t in declaration.transfers),
        )

    def working_size(self, spec):
        """Values per step (execution/resources.trace_bytes multiplies by 8 bytes): its rows at
        every cell, and each route's arrays over its listed species (a chain's over its stages
        too)."""
        x, s = spec.execution, len(spec.model.species_ids)
        (d,) = (d for op, d, _ in composite_spec.entries(spec) if op.LAW_ID == LAW_ID)
        k, depth = len(d.species), max((c.stages for c in d.chains), default=0)
        routes = len(d.chains) * (depth + 5) + len(d.pools) + 2 * len(d.degradations)
        routes += 2 * len(d.transfers)
        return (6 * s + 8) * x.capacity + routes * (6 * k + 16)

    def summary(self, spec, declaration, schedule, history):
        return {
            "polymerisation_law": LAW_ID,
            "polymerisation_step": STEP_ID,
            "polymerisation_species": common.summary_identities(declaration.species),
            "polymerisation_routes": declaration_to_dict(declaration),
            "polymerisation_limits": (
                "the sheet's neutral reduction: one NTP, NMP and amino-acid lump; GTP as ATP; AMP "
                "folded by adenylate kinase; PPi hydrolysed at once; no machine physics beyond "
                "capacity; machines and templates carry no free energy; development, not judged"
            ),
            "polymerisation_rk4": "half-steps kept around the inner RK4 step",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def statically_idle(self, p):
        return (
            p.poly_chain_kappa.shape[0] + p.poly_deg_length.shape[0] + p.poly_tr_share.shape[0]
        ) == 0

    def half_step(self, state, h, control, p, *, xp):
        controls = (getattr(control, INITIATION), getattr(control, DEGRADATION),
                    getattr(control, TRANSFER))  # fmt: skip
        return poly_half_step(state, controls, h, p, xp=xp)

    def control_valid(self, control, p, *, xp):
        valid = xp.asarray(True)
        for name in (INITIATION, DEGRADATION, TRANSFER):
            value = getattr(control, name)
            valid &= xp.all(xp.isfinite(value) & (value >= 0))
        return valid

    def rates(self, state, control, p, view, *, xp):
        return {k: xp.zeros_like(getattr(state, k)) for k in self.STATE_AXES}, None, None

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & poly_domain_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = poly_domain_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        """@3's local ledger gains consumed - produced, the total its node sums; the energy ledger
        gains the standard term + heat (module docstring)."""
        cell = row.poly_consumed_fmol - row.poly_produced_fmol
        result["local"] = result["local"] + cell
        result["total"] = result["total"] + entity_sum(cell, axis=1, xp=xp)
        result["energy"] = (
            result["energy"]
            + entity_sum(row.poly_standard_energy_pJ, axis=None, xp=xp)
            + entity_sum(row.poly_dissipated_energy_pJ, axis=None, xp=xp)
        )
        return result, self.own_ledgers(row, p, xp=xp)

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        cell = row.poly_produced_fmol + row.poly_consumed_fmol
        magnitudes[0] = magnitudes[0] + cell
        magnitudes[2] = magnitudes[2] + entity_sum(cell, axis=1, xp=xp)
        energy = entity_sum(row.poly_energy_magnitude_pJ, axis=None, xp=xp)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    def own_ledgers(self, row, p, *, xp):
        """The machines per pool (F + engaged - M) and the residues per chain (r ∫S - W - L ∫Q)."""
        engaged = xp.sum(row.poly_complexes_fmol, axis=1) @ p.poly_chain_pool
        transit = xp.sum(p.poly_chain_held * row.poly_complexes_fmol, axis=1)
        return dict(
            poly_machines=row.poly_free_machines_fmol + engaged - p.poly_pool_total_fmol,
            poly_residues=p.poly_chain_r * row.poly_stage_exits_fmol
            - transit
            - p.poly_chain_length * row.poly_released_fmol,
        )

    def own_magnitudes(self, row, p, *, xp):
        engaged = xp.sum(xp.abs(row.poly_complexes_fmol), axis=1) @ p.poly_chain_pool
        transit = xp.sum(p.poly_chain_held * xp.abs(row.poly_complexes_fmol), axis=1)
        return (
            xp.abs(row.poly_free_machines_fmol) + engaged + p.poly_pool_total_fmol,
            p.poly_chain_r * xp.abs(row.poly_stage_exits_fmol)
            + transit
            + p.poly_chain_length * xp.abs(row.poly_released_fmol),
        )

    def own_bounds(self, magnitudes, steps):
        rounding = first.LEDGER_STEP_ROUNDING * np.finfo(float).eps * steps
        return tuple(FLOOR_FMOL + rounding * m for m in magnitudes)
