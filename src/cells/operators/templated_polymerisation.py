"""Operator cells.operator.templated_polymerisation@1: templated polymerisation, its products' degradation and its
monomers' recharging, on the shared species inventory (gene regulation's option A, D235; FR-25).

The declared equations are docs/TEMPLATED_POLYMERISATION_LAWS.md (tag gr1-sheet-2026-11-20b; its
§9, the release, to tag gr1-sheet-fr38-erratum-a2-2026-11-22; §9.16, replacement, tag
gr1-sheet-fr38-amendment-s-2026-11-22; §9.17, the export, tag gr1-sheet-fr38-amendment-t-2026-11-22,
with erratum H, §9.21, tag gr1-sheet-fr38-erratum-h-2026-11-23); the design is
docs/GENE_REGULATION_DESIGN.md §7. Development, not judged: A's protocol (G6) judges it
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
- Optional: `templates`, the newcomers' values (Replacement, below), and `exports` with
  `outside_degradations`, a row carried out of its cell into a finite node and its loss there
  (The export, below).

Every key is explicit, every route ID is distinct, and every row a route names is a listed species.

A chain may add `release` (the sheet's §9, FR-38, D284), a hold between its completion and its fate
rows: {id, dwell_s, machine, durable_fraction, fates, label, initial_copies}.
- dwell_s: tau > 0, the hold's mean dwell.
- machine: "returned" (the machine leaves at completion, §4.3's physics) or "held" (it stays engaged
  through the hold and returns at release).
- durable_fraction: p in [0, 1], or "scheduled": p from the schedule under the release's ID.
- fates: a list of one {durable, short_lived} pair of listed rows, each of the product's
  chemistry: its declared mu° equal to the product's. The chain's own product may be one of them;
  a row that another chain writes (its product, draws, releases or fates), or that this chain
  draws, releases or templates from, may not. FR-38's class rows (several pairs) were replaced by
  FR-42's shares (D288, D296; the sheet's errata B and C): they were not neutral labels.
- label: where FR-42's labels mark the molecules: null or {"at": "release"} at the release (a fate
  row's arrival; the requester's cohort), or {"at": "completion"}, the hold then carrying its
  labels into the fate rows (Labels, below). It changes no physics.
- initial_copies: [H(0)], the hold's start in copies, unlabelled (at the base). With "held",
  every pool's free machines start at M - sum H(0) of its held chains, which must be >= 0.
A chain without the key is today's Chain, so its definition, signature and fingerprint are today's.

Schedule `polymerisation_controls`
----------------------------------
Per schedule, by ID, a piecewise-constant value from time 0, changing at the clock's instants inside
the horizon (grid_time):
- a chain's initiation rate constant k_I, in mM^-1 s^-1;
- a degradation's first-order rate, in s^-1;
- a transfer's capacity, in mM/s;
- a scheduled release's durable fraction p, in [0, 1], by the release's ID;
- an export's rate constant k_E and an outside degradation's first-order rate k_o, in s^-1.

The initiation rate and a release's durable fraction are routable (B1′): a rate route's factor u in
[b, 1] multiplies each at the start of each half-step, or at its midpoint where the half-step moves
the route's source (half_step_rows), so the scheduled k_I and p are the maxima and a routed p stays
in [0, 1] (the sheet's §9.4, source 3).

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
cell, its pools' free machines, and its chains' complexes; with an export, also its listed rows
at the exported nodes, under the same stage condition.
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
Machines and templates carry no free energy (declared). With an export, each exported node books
its own in the same way: HEAT_FIELDS' second field, poly_outside_dissipated_energy_pJ, and
poly_outside_standard_energy_pJ (The export, below).

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

The release (the sheet's §9)
----------------------------
- **The hold.** H [release, class] (fmol) holds a chain's completed molecules, L residues each, with
  no concentration term. The class axis has one class: the control polymerisation_release_class
  (always 1) and the axis stay so that every program keeps its inputs (D296).
- **The law:** Q^d = p H/tau and Q^s = (1 - p) H/tau into the durable and short-lived rows, with no
  affinity factor. At p = 0 or 1 one of them is zero and books nothing.
- **The machine:** "returned" frees it at completion; "held" counts the hold among the engaged and
  frees it at release.
- **Energy:** G gains the hold's standard term L mu°_res H, booked with the transit term. A
  completion books the chain's moves with L mu°_res per molecule into the hold, and a release into
  fate row F books mu-bar_F - L mu°_res, its heat class poly_release_heat_pJ [release, class, fate]
  (H_rel). No work, no new energy field.
- **Domain:** c_F <= c° at every fate row a positive release feeds, never repaired; the product's
  bound does not apply to a chain with a release, which puts no product in use at completion.
- **Counters and identities:** ∫Q (poly_released_fmol) counts arrivals, poly_hold_released_fmol
  [release, class, fate] each fate row's releases. The residue ledger adds, per release, L (H(0) +
  ∫Q - H - sum ∫Q^f); the machine ledger counts a held hold among the engaged.
- **Static:** without a release block the release arrays are empty and no release computation is
  traced, so every such definition's physical fields are bitwise today's (D148; the lead's ruling of
  22 November 2026: the programs differ by the empty fields only).

Labels (FR-42, D289, D296)
--------------------------
The physics stays on each row's physical total; the operator reports amounts and never reads a
share. It is a label source and a label pool reporter (LABEL_SOURCES, LABEL_POOLS; static, so
without a label owner every call is today's):
- **Sources** (label_sources): one per chain, the row its new material is labelled as (its
  product, or its durable fate row, whose labels its short-lived row shares: check_labels). The
  owner's schedule may name a chain (a producer's label: its cell, generation and chain crossed
  with the window); a chain without its own takes its row's window label.
- **Pools** (label_pools): one per release, its hold, carrying the durable fate row's labels.
- **The moves** (one_way_moves), from the same SSPRK(3,3) combination as the booked move: out
  (draws, forward degradation's polymer, re-synthesis's monomers, each transfer direction's
  consumed side); into at the row's window label (monomer releases, forward degradation's
  monomers, re-synthesis's polymer, each transfer direction's produced side) or at the chain's
  source label (its products, and fate releases marked at release); and each hold's part: its
  amounts, its completions (at the source label where marked at completion, else the base), its
  releases it does not carry, and carried, each release marked at completion into a labelled fate
  row, keeping the hold's labels. With an export, the node columns follow the cells' (The export,
  below).
- **Marked at release** (FR-38's cohort, the requester's answer to (e)): labels on the fate rows
  give §9.8's route 1 on shares (erratum C) with no blank.
- **A limit:** a labelled species carries at most cells.operator.neutral_arrival_labels@1's MAX_LABELS labels, so
  producer identity crossed with the window labels must fit within it.

Replacement (the sheet's §9.16, amendment S; FR-38's step 4)
--------------------------------------------------------------
Beside cells.operator.scheduled_cell_replacement@1, an event part acts at the start of the step leaving each event
time on every replaced slot (a cell that an event replaces and where this operator has a pool,
chain, degradation or transfer), reading only its own state and its control, the replacements due
per replaced slot (replacement@1's own count), so its place among the events does not matter:
- its chains in progress leave (complexes to 0), counted in poly_rep_chains_removed_fmol and their
  residues in poly_rep_residues_removed_fmol (W^rem); its holds leave (H to 0), counted in
  poly_rep_hold_removed_fmol (H^rem); the standard free energy leaving with them, mu°_res (W + L H),
  in poly_rep_removed_energy_pJ, never as heat; its pools' machines are all free (F to M);
- every cumulative counter stays cumulative; its value at the event becomes the newcomer's birth
  value (poly_rep_*_birth_fmol), and the departed generation's own totals are recorded
  (poly_rep_*_departed_fmol), so the newcomer's counters start at zero;
- the residue ledger counts W^rem and the hold's counts H^rem; the rows are replacement@1's.
The occupant rule: an optional `templates` key, [{template_id, rates: {schedule ID: value}}], gives
each newcomer's k_I, k, capacity, scheduled p and export k_E, constant through its life
(control_values). Without an event on a slot of this operator every such field is zero-size and the
event returns its state with no validity term, so the programs are today's (D148 case 2).

The export (the sheet's §9.17, amendment T; erratum H, §9.21)
------------------------------------------------------------
A fate row or product leaves its cell into a finite extracellular node and is retained there with
its labels (FR-38, the requester's retention of the producer's ID). Two optional keys:
- `exports`: each {id, row, patch, coupling, saturation_mM}. The patch's inside is the export's
  cell c and its outside the node o. The row F is a fate row or the product of a chain at c. The
  coupling, {row: nu} signed per molecule exported, gives the rows of c the move consumes and
  releases; it is non-empty, since only a driven export is admitted in version 1. K is given for
  each consumed row.
- `outside_degradations`: each {id, node, polymer, residues, monomers, standard_free_energy},
  §4.4's law at o on a row an export carries there, at its chain's length. Its monomers stay at o.

The laws, with o's volume and rows:
- **Export:** a forward part k_E n_F,c phi_E and a backward part forward e^(x_E), where
  x_E = mu_F,o/RT - mu_F,c/RT + sum nu mu_c/RT and phi_E is the product over the consumed coupling
  rows of c/(K + c). The net J_E = forward - backward = k_E n_F,c phi_E (1 - e^(x_E)) moves F from c
  to o and runs the coupling at c.
- **Outside degradation:** J_o = k_o n_F,o (1 - e^(y_o)), as at a cell.
- Both are one-sided: x_E or y_o above X_DOM at a route in use refuses the step. The listed rows
  at the exported nodes (the poly_outside_node axis) are among the half-step's variables.

**Energy.** G extends over the nodes the operator writes. An export's heat, poly_export_heat_pJ, is
-J_E (mu-bar_F,o - mu-bar_F,c + sum nu mu-bar_c) by the divided-difference potentials of both sides,
and is booked whole at its cell: its node part J_E mu-bar_F,o moves from the node's exact dG to the
cell's. So each node books only its outside degradations' heat (poly_outside_degradation_heat_pJ)
in poly_outside_dissipated_energy_pJ, with its standard term in poly_outside_standard_energy_pJ.
The totals are each side's exact dG, and no work is booked.

**Counters and ledgers.**
- poly_export_forward_fmol and poly_export_backward_fmol count the one-way parts (erratum H, item
  3), and poly_outside_degraded_fmol counts ∫D_o.
- The node amounts are this operator's own writes: extracellular_amount_increment among its
  ENTITY_WRITES, booked by poly_outside_produced_fmol and poly_outside_consumed_fmol.
- @3's ledgers gain them, and the energy ledger gains the nodes' standard term and heat.

**Labels.** Each export reports two one-way transfers of its labelled row: forward from c to o with
c's shares, and backward with o's (erratum H, item 3 (a)). Its coupling's rows move at c at the
window label. An outside degradation moves its rows at o as a degradation does at its cell.

**Replacement.** A replaced slot's export takes its newcomer's k_E from `templates`. Its two
counters' birth and departed values (poly_rep_export_birth_fmol, poly_rep_export_departed_fmol)
split them by generation. A node is never replaced, so the RNA exported from a departed generation
stays at the node with its label.

**Static.** Without the keys every export field is zero-size and no export computation is traced
(exporting). The physical fields of every such definition are therefore bitwise today's (D148
case 2).

Refused at the definition
-------------------------
- a charged, permeable or unlisted row;
- an unknown cell, pool or row;
- m not dividing L, and a draw without its K;
- a transfer that is not a reaction (a sign missing), and a degradation whose polymer a chain makes
  at another length;
- another writer of a listed row: a conversion other than those admitted, or an in-step mover.
  FR-43 / D315 admits a D152 network writing one and the unit producer
  (cells.operator.population_unit_turnover@1) consuming one, the two-writer rule of 19 November
  2026 extended (check_writers): the row's potential from the species registry, each writer's own
  books, and a labelled or exported row keeping this operator alone (sole_rows). FR-43 part 3
  admits a transfer of a listed row (exchange, the integer population; the species registry's
  check_row_writers), except across a compartment's patch, and refuses an undeclared split writer;
- a volume changer other than water (the lumens, replacement@2 by its water): the volumes are
  current reads at the split, the view's where water changes them, the declared ones otherwise
  (C1's fallback; FR-43 / D315);
- beside a replacement (check_occupants): a version other than replacement@1; a donor copy into or
  from a slot of this operator (version 1.1); a template that is not a replacement template; a
  newcomer whose template gives no value for a schedule of its slot; a template value for no such
  schedule; a schedule change of a replaced slot at or after its founder's death;
- dt kappa > 1, dt k_D > 1, dt k_I c_T F/F > 1 for a gene's template, dt/tau > 1, dt k_E > 1 and
  dt k_o > 1, newcomers' values included;
- a release's fate rows that break the rules above, more than one pair of them, fate rows
  labelled unalike by FR-42's owner, and a held hold that the pool cannot staff;
- the export's (§9.17.6):
  - an exported row that is no fate row or product of a chain at its patch's inside cell;
  - an unknown patch, a patch onto a held bath, or one onto no finite extracellular node;
  - an empty coupling (the passive form, follow-on (ii));
  - a coupling row that is not listed, the exported row among them, or a consumed one without
    its K;
  - an outside degradation of a row that no export carries into its node, or at another length,
    or among its own monomers;
  - an ID that another pool, route or release holds;
  - another in-step mover, at its node, of an exported row or of an outside degradation's
    monomer (check_writers; the monomers' is beyond §9.17.6's wording, and fails closed);
  - beside cells.operator.cell_owned_compartments@1 (FR-49, D327; check_compartments), an outside degradation
    at a declared compartment's node, then an export into one: a compartment lies behind its
    owner's membrane, and secretion into it is a later step with its own books at the
    compartment's node. Routes in the owner's cytosol never touch the compartment;
- more than the species cap.

At run time: a non-finite or non-positive amount (at the cells, and at the exported nodes), a
negative pool or complex, a broken stage condition, and the one-sided domains (x_E's and y_o's
among them).

Idle: with no route it is statically idle. With no flux in a half-step the start state is selected,
so zero rates are bitwise idle.
"""

import math
from dataclasses import dataclass, replace
from types import MappingProxyType

import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields, _number
from cells.laws.electrochemistry import R
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump as first
from cells.numerics.clock_instants import ON_THE_GRID, on_grid  # D283's one predicate.
from cells.numerics.species_sums import entity_sum, species_sum
from cells.operators import species_common as common
from cells.operators import species_reactions
from cells.operators.contract import Operator, Read
from cells.registry import kind_registry, species_registry

LAW_ID = "cells.operator.templated_polymerisation@1"
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
RELEASE_AXIS, CLASS_AXIS, FATE_AXIS = "poly_release", "poly_class", "poly_fate"
FATES = ("durable", "short_lived")  # The fate axis, in order (the sheet's d and s).
# Amendment S (§9.16): the replaced slots and their entities, zero-size without a replacement.
REPLACED_SLOT_AXIS, REPLACED_CHAIN_AXIS = "poly_replaced_slot", "poly_replaced_chain"
REPLACED_RELEASE_AXIS = "poly_replaced_release"
REPLACED_DEGRADATION_AXIS, REPLACED_TRANSFER_AXIS = (
    "poly_replaced_degradation",
    "poly_replaced_transfer",
)
COUNTER_AXIS = "poly_chain_counter"
# Amendment T (§9.17; erratum H, §9.21): the exports, the outside degradations, the exported nodes
# and an export's two one-way parts, all zero-size without an export.
EXPORT_AXIS, OUTSIDE_DEGRADATION_AXIS = "poly_export", "poly_outside_degradation"
OUTSIDE_NODE_AXIS, EXPORT_PART_AXIS = "poly_outside_node", "poly_export_part"
REPLACED_EXPORT_AXIS = "poly_replaced_export"
EXPORT_PARTS = ("forward", "backward")  # c to o with c's shares, o to c with o's (erratum H).
CHAIN_COUNTERS = ("poly_initiated_fmol", "poly_stage_exits_fmol", "poly_released_fmol")
REPLACEMENT_LAW = (
    common.REPLACEMENT_LAW
)  # cells.operator.scheduled_cell_replacement@1, the one admitted.
REPLACEMENT_FAMILY = REPLACEMENT_LAW.partition("@")[0]  # Its other versions are refused.
MACHINE_OPTIONS = ("returned", "held")
LABEL_TRANSITIONS = ("completion", "release")
SCHEDULED = "scheduled"  # A release's durable fraction read from its schedule.
INITIATION = "polymerisation_initiation_rate"
DEGRADATION = "polymerisation_degradation_rate"
TRANSFER = "polymerisation_transfer_capacity"
RELEASE_FRACTION = "polymerisation_release_fraction"  # [release] p.
RELEASE_CLASS = "polymerisation_release_class"  # [release] psi, 1 without a label.
REPLACEMENTS_DUE = "polymerisation_replacements_due"  # [replaced slot] events due by now (§9.16).
EXPORT_RATE = "polymerisation_export_rate"  # [export] k_E (§9.17.2).
OUTSIDE_DEGRADATION = "polymerisation_outside_degradation_rate"  # [outside degradation] k_o.
# The half-step's controls, in its order; the event reads REPLACEMENTS_DUE alone.
HALF_STEP_CONTROLS = (
    INITIATION,
    DEGRADATION,
    TRANSFER,
    RELEASE_FRACTION,
    RELEASE_CLASS,
    EXPORT_RATE,
    OUTSIDE_DEGRADATION,
)

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
    # The release (the sheet's §9), sized by the declaration: empty without a release block.
    "poly_hold_fmol": [RELEASE_AXIS, CLASS_AXIS],  # The hold H.
    "poly_hold_released_fmol": [RELEASE_AXIS, CLASS_AXIS, FATE_AXIS],  # Cumulative ∫Q^f.
    "poly_release_heat_pJ": [RELEASE_AXIS, CLASS_AXIS, FATE_AXIS],  # H_rel per fate row.
    # Amendment S (§9.16), sized by the replaced slots and their entities: empty without one.
    "poly_rep_applied": [REPLACED_SLOT_AXIS],  # int64: the replacements applied per slot.
    "poly_rep_chains_removed_fmol": [REPLACED_CHAIN_AXIS],  # Chains in progress removed.
    "poly_rep_residues_removed_fmol": [REPLACED_CHAIN_AXIS],  # W^rem.
    "poly_rep_removed_energy_pJ": [REPLACED_CHAIN_AXIS],  # mu°_res (W + L H) leaving.
    "poly_rep_hold_removed_fmol": [REPLACED_RELEASE_AXIS, CLASS_AXIS],  # H^rem.
    "poly_rep_chain_birth_fmol": [REPLACED_CHAIN_AXIS, COUNTER_AXIS],  # At the occupant's birth.
    "poly_rep_chain_departed_fmol": [REPLACED_CHAIN_AXIS, COUNTER_AXIS],  # The last departed's.
    "poly_rep_release_birth_fmol": [REPLACED_RELEASE_AXIS, CLASS_AXIS, FATE_AXIS],
    "poly_rep_release_departed_fmol": [REPLACED_RELEASE_AXIS, CLASS_AXIS, FATE_AXIS],
    "poly_rep_degradation_birth_fmol": [REPLACED_DEGRADATION_AXIS],
    "poly_rep_degradation_departed_fmol": [REPLACED_DEGRADATION_AXIS],
    "poly_rep_transfer_birth_fmol": [REPLACED_TRANSFER_AXIS],  # Signed, as the extent is.
    "poly_rep_transfer_departed_fmol": [REPLACED_TRANSFER_AXIS],
    # Amendment T (§9.17, erratum H), sized by the declaration: empty without an export.
    "poly_export_forward_fmol": [EXPORT_AXIS],  # Cumulative forward one-way part, c to o.
    "poly_export_backward_fmol": [EXPORT_AXIS],  # Cumulative backward one-way part, o to c.
    "poly_export_heat_pJ": [EXPORT_AXIS],  # Its whole heat, its node part included (H_E).
    "poly_outside_degraded_fmol": [OUTSIDE_DEGRADATION_AXIS],  # Cumulative molecules (∫D_o).
    "poly_outside_degradation_heat_pJ": [OUTSIDE_DEGRADATION_AXIS],
    "poly_outside_produced_fmol": ["species", OUTSIDE_NODE_AXIS],
    "poly_outside_consumed_fmol": ["species", OUTSIDE_NODE_AXIS],
    "poly_outside_dissipated_energy_pJ": [OUTSIDE_NODE_AXIS],  # Heat booked at each node.
    "poly_outside_standard_energy_pJ": [OUTSIDE_NODE_AXIS],  # The node's owned standard term.
    "poly_outside_energy_magnitude_pJ": [OUTSIDE_NODE_AXIS],
    "poly_rep_export_birth_fmol": [REPLACED_EXPORT_AXIS, EXPORT_PART_AXIS],  # §9.17.3.
    "poly_rep_export_departed_fmol": [REPLACED_EXPORT_AXIS, EXPORT_PART_AXIS],
}
EXPORT_STATE = (  # Amendment T's own fields (§9.17); its replacement counters are poly_rep_.
    "poly_export_forward_fmol",
    "poly_export_backward_fmol",
    "poly_export_heat_pJ",
    "poly_outside_degraded_fmol",
    "poly_outside_degradation_heat_pJ",
    "poly_outside_produced_fmol",
    "poly_outside_consumed_fmol",
    "poly_outside_dissipated_energy_pJ",
    "poly_outside_standard_energy_pJ",
    "poly_outside_energy_magnitude_pJ",
)
REPLACEMENT_STATE = tuple(k for k in STATE_AXES if k.startswith("poly_rep_"))
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
    "poly_rel_chain",  # [release, chain] one-hot: its chain.
    "poly_rel_rate",  # [release] 1/tau, 1/s.
    "poly_rel_held",  # [release] 1 where the machine is held through the hold.
    "poly_rel_at_release",  # [release] 1 where FR-42's labels mark the release, 0 at completion.
    "poly_rel_classes",  # [release, class] bool: one class (D296; the axis keeps the programs).
    "poly_rel_fate",  # [release, class, fate, k] one-hot: each fate row.
    "poly_rel_hold0_fmol",  # [release, class] H(0).
    # Amendment S (§9.16): one-hot maps of the replaced entities, zero-size without a replacement.
    "poly_rep_slot_cell",  # [replaced slot] int64: its cell.
    "poly_rep_chain_hot",  # [replaced chain, chain].
    "poly_rep_chain_slot_hot",  # [replaced chain, replaced slot].
    "poly_rep_release_hot",  # [replaced release, release].
    "poly_rep_release_slot_hot",  # [replaced release, replaced slot].
    "poly_rep_release_chain_hot",  # [replaced release, replaced chain].
    "poly_rep_degradation_hot",  # [replaced degradation, degradation].
    "poly_rep_degradation_slot_hot",  # [replaced degradation, replaced slot].
    "poly_rep_transfer_hot",  # [replaced transfer, transfer].
    "poly_rep_transfer_slot_hot",  # [replaced transfer, replaced slot].
    # Amendment T (§9.17): the exports and the outside degradations, zero-size without an export.
    "poly_out_slot_hot",  # [exported node, extracellular slot] one-hot.
    "poly_exp_cell",  # [export, cell] one-hot: its patch's inside.
    "poly_exp_node",  # [export, exported node] one-hot: its patch's outside.
    "poly_exp_row",  # [export, k] one-hot: the exported row.
    "poly_exp_nu",  # [export, k] its coupling at the cell per molecule exported, signed.
    "poly_exp_saturates",  # [export, k] bool: a consumed coupling row.
    "poly_exp_K_mM",  # [export, k] (1 where not consumed).
    "poly_odeg_node",  # [outside degradation, exported node] one-hot.
    "poly_odeg_polymer",  # [outside degradation, k] one-hot.
    "poly_odeg_monomers",  # [outside degradation, k] per residue.
    "poly_odeg_length",  # [outside degradation] L.
    "poly_rep_export_hot",  # [replaced export, export] (§9.16 beside §9.17).
    "poly_rep_export_slot_hot",  # [replaced export, replaced slot].
)
EXPORT_LAYOUT = tuple(
    f for f in LAYOUT_FIELDS if f.startswith(("poly_out_", "poly_exp_", "poly_odeg_"))
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
class Label:
    """The transition at which FR-42's labels mark a release's molecules (the sheet's §9.1, as
    erratum C reads it; D296): "release" (FR-42's arrival into a fate row, the default) or
    "completion" (the hold carries its labels into the fate rows)."""

    at: str


@dataclass(frozen=True)
class Release:
    """A chain's release step (the sheet's §9): the hold's mean dwell tau (s), its machine option,
    its durable fraction p (None: scheduled under the release's ID), its fate rows ((durable,
    short-lived),), its label (None: FR-42's labels mark the release) and the hold's initial
    copies ((H0,)). One class: FR-42's shares replaced the class rows (D288, D296)."""

    id: str
    dwell_s: float
    machine: str
    durable_fraction: float | None
    fates: tuple
    label: Label | None
    initial_copies: tuple

    def rows(self):
        return tuple(row for pair in self.fates for row in pair)


@dataclass(frozen=True)
class ReleasingChain(Chain):
    """A chain that declares the sheet's §9 (its `release` block). Every other chain stays a
    Chain, so its form, its signature and its definition's fingerprint are today's."""

    release: Release


def releases_of_chains(chains):
    """((chain, release), ...) of the chains that declare a release, in chain order."""
    return tuple((c, c.release) for c in chains if isinstance(c, ReleasingChain))


def releases_of(declaration):
    return releases_of_chains(declaration.chains)


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
class Export:
    """Amendment T's export (§9.17.2): row F from its patch's inside cell into its outside node,
    a finite extracellular node, driven by its coupling at the cell ((row, nu), ...; non-empty in
    version 1), with K for each consumed coupling row."""

    id: str
    patch: str
    cell: str  # The patch's inside (derived).
    node: str  # The patch's outside (derived).
    row: str
    coupling: tuple  # ((row, nu), ...), signed, per molecule exported.
    saturation_mM: tuple  # ((consumed row, K), ...)


@dataclass(frozen=True)
class OutsideDegradation:
    """Amendment T's outside degradation (§9.17.2): §4.4's law at an exported node, on a row an
    export carries there; its monomers stay at the node."""

    id: str
    node: str
    polymer: str
    residues: int
    monomers: tuple  # ((row, count), ...)
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
    # Amendment S (§9.16, item 6), the occupant rule: ((template ID, ((schedule ID, value), ...)),
    # ...), a replaced slot's newcomers' values; empty without the key.
    templates: tuple = ()
    # Amendment T (§9.17): its exports and outside degradations; empty without the keys.
    exports: tuple = ()
    outside_degradations: tuple = ()

    def route_ids(self):
        return tuple(
            r.id
            for r in (
                *self.chains,
                *self.degradations,
                *self.transfers,
                *self.exports,
                *self.outside_degradations,
            )
        )

    def schedule_ids(self):
        """Every schedule's ID in polymerisation_controls, in control order: the routes', then
        each scheduled durable fraction's (its release's ID)."""
        releases = [r for _, r in releases_of(self)]
        return (*self.route_ids(), *(r.id for r in releases if r.durable_fraction is None))


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


RELEASE_KEYS = {"id", "dwell_s", "machine", "durable_fraction", "fates", "label", "initial_copies"}


def _release(raw, chain, listed):
    """A chain's release block (the sheet's §9), on its own: parse_declaration checks its rows
    against the other routes' (_check_fates, _check_release_routes)."""
    what = f"chain {chain}'s release"
    _fields(raw, RELEASE_KEYS, f"{LAW_ID} {what}")
    name = identifier(raw["id"])
    dwell = _positive(raw["dwell_s"], f"{what}'s dwell_s")
    if raw["machine"] not in MACHINE_OPTIONS:
        raise ConfigError(f"{LAW_ID}: {what}'s machine is one of {', '.join(MACHINE_OPTIONS)}")
    fraction = raw["durable_fraction"]
    if fraction == SCHEDULED:
        fraction = None
    elif _finite(fraction) and 0.0 <= fraction <= 1.0:
        fraction = float(fraction)
    else:
        raise ConfigError(
            f"{LAW_ID}: {what}'s durable_fraction is a number in [0, 1] or {SCHEDULED!r}"
        )
    if type(raw["fates"]) is not list or not raw["fates"]:
        raise ConfigError(f"{LAW_ID}: {what}'s fates are a list of one {{durable, short_lived}}")
    if len(raw["fates"]) > 1:
        raise ConfigError(
            f"{LAW_ID}: {what} has one {{durable, short_lived}} pair: FR-38's class rows are "
            "replaced by FR-42's shares (D288, D296); label the fate rows with "
            "cells.operator.neutral_arrival_labels@1"
        )
    pairs = []
    for entry in raw["fates"]:
        _fields(entry, set(FATES), f"{LAW_ID} {what}'s fate rows")
        for fate in FATES:
            if entry[fate] not in listed:
                raise ConfigError(
                    f"{LAW_ID}: {what}'s {fate} row {entry[fate]!r} is not a listed species"
                )
        pairs.append(tuple(entry[fate] for fate in FATES))
    rows = [row for pair in pairs for row in pair]
    if len(set(rows)) != len(rows):
        raise ConfigError(f"{LAW_ID}: {what}'s fate rows are distinct")
    label = raw["label"]
    if label is not None:  # FR-42's labels: which transition marks the molecules (D296).
        _fields(label, {"at"}, f"{LAW_ID} {what}'s label")
        if label["at"] not in LABEL_TRANSITIONS:
            raise ConfigError(
                f"{LAW_ID}: {what}'s label is at one of {', '.join(LABEL_TRANSITIONS)}"
            )
        label = Label(label["at"])
    copies = raw["initial_copies"]
    if type(copies) is not list or len(copies) != 1:
        raise ConfigError(f"{LAW_ID}: {what}'s initial_copies list its hold's one entry")
    if not all(_finite(v) and v >= 0 for v in copies):
        raise ConfigError(f"{LAW_ID}: {what}'s initial copies are finite and >= 0")
    return Release(
        name, dwell, raw["machine"], fraction, tuple(pairs), label, tuple(float(v) for v in copies)
    )


def _release_to_dict(r):
    return dict(
        id=r.id,
        dwell_s=r.dwell_s,
        machine=r.machine,
        durable_fraction=SCHEDULED if r.durable_fraction is None else r.durable_fraction,
        fates=[dict(zip(FATES, pair, strict=True)) for pair in r.fates],
        label=None if r.label is None else dict(at=r.label.at),
        initial_copies=list(r.initial_copies),
    )


def _written(chain):
    """The rows a chain writes: its draws and releases, and its product or, with a release, its
    fate rows."""
    rows = {*dict(chain.draws), *dict(chain.releases)}
    if isinstance(chain, ReleasingChain):
        return rows | set(chain.release.rows())
    return rows | {chain.product}


def _check_fates(chains, mu):
    """Refuse a fate row this chain draws, releases or templates from, one another chain writes
    (one producer per fate row, version 1; the sheet's §9.1, question d), and one whose declared
    mu° is not its product's (one chemistry, so the release's dG is RT ln(c_F/c°))."""
    for c, release in releases_of_chains(chains):
        fates = set(release.rows())
        own = {*dict(c.draws), *dict(c.releases)} | ({c.template_species} - {None})
        if fates & own:
            raise ConfigError(
                f"{LAW_ID}: chain {c.id}'s fate rows are none of its draws, releases or template"
            )
        for other in chains:  # One producer per fate row at its cell (amendment T, §9.17.3).
            hit = sorted(fates & _written(other)) if other is not c and other.cell == c.cell else []
            if hit:
                raise ConfigError(
                    f"{LAW_ID}: chain {other.id} writes {hit[0]!r}, a fate row of chain {c.id} "
                    "(one producer per fate row)"
                )
        for row in sorted(fates):
            if mu[row] != mu[c.product]:
                raise ConfigError(
                    f"{LAW_ID}: chain {c.id}'s fate row {row!r} has another standard_mu_RT than "
                    f"its product {c.product!r} (one chemistry)"
                )


def _check_release_routes(declaration):
    """Refuse a fate row that a degradation makes or a transfer moves (one producer), and a pool
    whose machines cannot staff its held holds at t = 0: F(0) = M - sum H(0) >= 0 (§9.3)."""
    fates = {}  # {cell: fate rows there}: one producer per fate row at its cell (§9.17.3).
    for c, r in releases_of(declaration):
        fates.setdefault(c.cell, set()).update(r.rows())
    for d in declaration.degradations:
        hit = sorted(set(dict(d.monomers)) & fates.get(d.cell, set()))
        if hit:
            raise ConfigError(f"{LAW_ID}: degradation {d.id} makes {hit[0]!r}, a fate row")
    for t in declaration.transfers:
        hit = sorted(set(dict(t.stoichiometry)) & fates.get(t.cell, set()))
        if hit:
            raise ConfigError(f"{LAW_ID}: transfer {t.id} moves {hit[0]!r}, a fate row")
    held = {}
    for c, r in releases_of(declaration):
        if r.machine == "held":
            held[c.pool] = held.get(c.pool, 0.0) + math.fsum(r.initial_copies)
    for pool in declaration.pools:
        if held.get(pool.id, 0.0) > pool.machines:
            raise ConfigError(
                f"{LAW_ID}: pool {pool.id}'s {pool.machines:g} machines cannot hold its held "
                f"chains' {held[pool.id]:g} initial copies (F(0) = M - sum H(0) >= 0)"
            )


def parse_declaration(raw, base):
    keys = {"law", "standard_concentration_mM", "species", "pools", "chains", "degradations",
            "transfers"}  # fmt: skip
    optional = {"templates", "exports", "outside_degradations"}  # §9.16 and §9.17.
    _fields(raw, keys | (optional & set(raw)), "templated polymerisation")
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
        value = e["standard_mu_RT"]  # Any finite mu°/RT at c0: a negative one is physical.
        if not _finite(value):
            raise ConfigError(f"{LAW_ID}: {e['id']}'s standard_mu_RT is a finite number")
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
        releasing = isinstance(item, dict) and "release" in item
        _fields(item, chain_keys | ({"release"} if releasing else set()), f"{LAW_ID} chain")
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
        fields = (
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
        if releasing:
            chains.append(ReleasingChain(*fields, _release(item["release"], name, listed)))
        else:
            chains.append(Chain(*fields))
    _check_fates(chains, dict(zip(listed, mu, strict=True)))
    made = {c.product: c.residues for c in chains}
    made |= {row: c.residues for c, r in releases_of_chains(chains) for row in r.rows()}
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
    ids += [r.id for _, r in releases_of(declaration)]
    if len(set(ids)) != len(ids):
        raise ConfigError(f"{LAW_ID}: every pool, route and release ID is distinct")
    used = {p for p in (c.pool for c in chains)}
    if used != set(pool_cells):
        raise ConfigError(f"{LAW_ID}: every pool serves a chain")
    _check_release_routes(declaration)
    named = set()
    for c in chains:
        named |= {c.product, *dict(c.draws), *dict(c.releases)}
        named |= {c.template_species} - {None}
        if isinstance(c, ReleasingChain):
            named |= set(c.release.rows())
    for d in degradations:
        named |= {d.polymer, *dict(d.monomers)}
    for t in transfers:
        named |= set(dict(t.stoichiometry))
    if set(listed) - named:
        raise ConfigError(f"{LAW_ID}: listed species {sorted(set(listed) - named)} are unused")
    if {"exports", "outside_degradations"} & set(raw):  # Before templates, which name k_E.
        exports, outside = _exports(raw, base, declaration)
        declaration = replace(declaration, exports=exports, outside_degradations=outside)
    if "templates" in raw:
        declaration = replace(declaration, templates=_templates(raw["templates"], declaration))
    return declaration


def _exports(raw, base, declaration):
    """Amendment T's exports and outside degradations (§9.17.2, §9.17.6), each refused at the
    definition: an export of a row that is no fate row or product of a chain at its patch's inside
    cell; a patch whose outside is a held bath or no finite extracellular node; an empty coupling
    (the passive form, follow-on (ii)); a coupling row that is not listed, the exported row among
    them, or a consumed one without its K; an outside degradation of a row that no export carries
    into its node, at another length; and an ID another route or release holds."""
    listed = {s.id for s in declaration.species}
    patches = {m.id: m for m in base.model.membranes}
    outside = {c.id: c for c in base.model.extracellular}
    made = {}  # (row, cell): a chain's product, or with a release its fate rows, at its cell.
    for c in declaration.chains:
        for row in c.release.rows() if isinstance(c, ReleasingChain) else (c.product,):
            made[(row, c.cell)] = c.residues
    taken = {p.id for p in declaration.pools} | set(declaration.route_ids())
    taken |= {r.id for _, r in releases_of(declaration)}
    exports = []
    for item in _listed(raw, "exports"):
        _fields(item, {"id", "row", "patch", "coupling", "saturation_mM"}, f"{LAW_ID} export")
        name = identifier(item["id"])
        patch = patches.get(item["patch"])
        if patch is None:
            raise ConfigError(f"{LAW_ID}: export {name} names an unknown patch {item['patch']!r}")
        cell, node = patch.inside, patch.outside
        if node not in outside:
            raise ConfigError(
                f"{LAW_ID}: export {name}'s patch {patch.id} opens onto {node!r}, not a finite "
                "extracellular node"
            )
        if outside[node].reservoir:
            raise ConfigError(
                f"{LAW_ID}: export {name}'s patch {patch.id} opens onto a held bath, {node!r}: "
                "secretion into it is clearance, which retains nothing (§9.17.6)"
            )
        row = item["row"]
        if (row, cell) not in made:
            raise ConfigError(
                f"{LAW_ID}: export {name}'s row {row!r} is no fate row or product of a chain at "
                f"its patch's inside cell {cell!r}"
            )
        if item["coupling"] == {}:
            raise ConfigError(
                f"{LAW_ID}: export {name} has an empty coupling: the passive form is refused in "
                "version 1, since its domain refuses a node filled past the cell's concentration "
                "over e (§9.17.2; follow-on (ii))"
            )
        coupling = _counts(item["coupling"], listed, f"export {name}'s coupling", signed=True)
        if row in dict(coupling):
            raise ConfigError(f"{LAW_ID}: export {name}'s row is not one of its coupling's rows")
        consumed = [r for r, v in coupling if v < 0]
        saturation = _saturations(item["saturation_mM"], consumed, f"export {name}'s saturation_mM")
        exports.append(Export(name, patch.id, cell, node, row, coupling, saturation))
    carried = {(e.row, e.node): made[(e.row, e.cell)] for e in exports}
    degradations = []
    for item in _listed(raw, "outside_degradations"):
        _fields(item, {"id", "node", "polymer", "residues", "monomers", "standard_free_energy"},
                f"{LAW_ID} outside degradation")  # fmt: skip
        name = identifier(item["id"])
        key = (item["polymer"], item["node"])
        if key not in carried:
            raise ConfigError(
                f"{LAW_ID}: outside degradation {name}'s polymer {key[0]!r} is carried into "
                f"{key[1]!r} by no export"
            )
        residues = _integer(item["residues"], f"outside degradation {name}'s residues")
        if residues != carried[key]:
            raise ConfigError(
                f"{LAW_ID}: outside degradation {name}'s polymer has {carried[key]} residues "
                "where its chain makes it"
            )
        monomers = _counts(item["monomers"], listed, f"outside degradation {name}'s monomers")
        if key[0] in dict(monomers):
            raise ConfigError(f"{LAW_ID}: outside degradation {name}'s polymer is not its monomer")
        cited = _cited(
            item["standard_free_energy"], f"outside degradation {name}'s standard_free_energy"
        )
        degradations.append(
            OutsideDegradation(name, item["node"], key[0], residues, monomers, cited)
        )
    ids = [e.id for e in (*exports, *degradations)]
    if len(set(ids)) != len(ids) or set(ids) & taken:
        raise ConfigError(f"{LAW_ID}: every pool, route, release and export ID is distinct")
    return tuple(exports), tuple(degradations)


def _listed(raw, key):
    """raw[key], a non-empty list where the key is given, else []."""
    if key not in raw:
        return []
    if type(raw[key]) is not list or not raw[key]:
        raise ConfigError(f"{LAW_ID}: {key} is a non-empty list where it is given")
    return raw[key]


def _templates(raw, declaration):
    """Amendment S's templates (§9.16, item 6): [{template_id, rates: {schedule ID: value}}], each
    a schedule of this declaration's (a route's, or a scheduled release's p) with its newcomers'
    value; check_occupants holds them to the replacement's events."""
    if type(raw) is not list or not raw:
        raise ConfigError(f"{LAW_ID}: templates is a non-empty list")
    known, releases = declaration.schedule_ids(), {r.id for _, r in releases_of(declaration)}
    out = []
    for entry in raw:
        _fields(entry, {"template_id", "rates"}, f"{LAW_ID} template")
        tid = identifier(entry["template_id"])
        rates = entry["rates"]
        if type(rates) is not dict or not rates:
            raise ConfigError(f"{LAW_ID}: template {tid}'s rates are a non-empty object")
        values = []
        for name, value in rates.items():
            if name not in known:
                raise ConfigError(f"{LAW_ID}: template {tid} names {name!r}, not a schedule here")
            v = _number(value, f"{LAW_ID}: template {tid}'s value for {name}")
            if not (math.isfinite(v) and v >= 0 and (name not in releases or v <= 1)):
                raise ConfigError(
                    f"{LAW_ID}: template {tid}'s value for {name} is finite and >= 0 (a durable "
                    "fraction in [0, 1])"
                )
            values.append((name, float(v)))
        out.append((tid, tuple(values)))
    if len({t for t, _ in out}) != len(out):
        raise ConfigError(f"{LAW_ID}: each template is declared once")
    return tuple(out)


def declaration_to_dict(d):
    return (
        dict(
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
                    # The sheet's §9, written only where declared (a chain without one is today's).
                    **(
                        {"release": _release_to_dict(c.release)}
                        if isinstance(c, ReleasingChain)
                        else {}
                    ),
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
        | (
            {"templates": [dict(template_id=t, rates=dict(rates)) for t, rates in d.templates]}
            if d.templates
            else {}
        )
        | (
            {
                "exports": [
                    dict(
                        id=e.id,
                        row=e.row,
                        patch=e.patch,
                        coupling=dict(e.coupling),
                        saturation_mM=dict(e.saturation_mM),
                    )
                    for e in d.exports
                ]
            }
            if d.exports
            else {}
        )
        | (
            {
                "outside_degradations": [
                    dict(
                        id=x.id,
                        node=x.node,
                        polymer=x.polymer,
                        residues=x.residues,
                        monomers=dict(x.monomers),
                        standard_free_energy=_cited_to_dict(x.standard_free_energy),
                    )
                    for x in d.outside_degradations
                ]
            }
            if d.outside_degradations
            else {}
        )
    )


def grid_time(time, dt):
    """The clock's instant that `time` names on steps of dt, or None where it names none: the
    predicate this operator's schedules read for their change times, a release's durable fraction
    and class switches among them: D283's clock predicate (cells.numerics.clock_instants.on_grid),
    as the host-side cohort's window edges read its same_instant."""
    return on_grid(time, dt)  # D283: the clock's one predicate, the same-instant tolerance.


def _schedule_kinds(declaration):
    """{schedule ID: what its values are}: "rate" for a route's, "fraction" for a scheduled
    durable fraction's."""
    kinds = dict.fromkeys(declaration.route_ids(), "rate")
    for _, r in releases_of(declaration):
        if r.durable_fraction is None:
            kinds[r.id] = "fraction"
    return kinds


def _scheduled_value(value, kind, name):
    if kind == "rate":
        if not math.isfinite(value) or value < 0:
            raise ConfigError(f"{LAW_ID}: route {name}'s value is finite and >= 0")
    elif not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ConfigError(f"{LAW_ID}: release {name}'s durable fraction is in [0, 1]")
    return float(value)


def parse_schedule(raw, base, declaration):
    rows = raw[EXPERIMENT_KEY]
    if type(rows) is not list:
        raise ConfigError(f"{LAW_ID}: {EXPERIMENT_KEY} is an explicit list")
    dt, end = base.execution.dt, base.experiment.end_time
    known = list(declaration.schedule_ids())
    kinds = _schedule_kinds(declaration)
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
            if grid_time(time, dt) is None:
                raise ConfigError(f"{LAW_ID}: a schedule change must be {ON_THE_GRID}")
            if index > 0 and not 0.0 < time < end:
                raise ConfigError(f"{LAW_ID}: a schedule change lies inside 0 < t < end")
            value = _number(change["value"], f"{LAW_ID}: route {name}'s value")
            parsed.append((time, _scheduled_value(value, kinds[name], name)))
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


UNIT_PRODUCER = (
    "cells.operator.population_unit_turnover@1"  # FR-43: the unit producer, a precursor's consumer.
)


def production_bound(spec, declaration, schedule):
    """{(species, cell): the largest rate (fmol/s) at which this operator can make the row}, from
    its laws (docs/TEMPLATED_POLYMERISATION_LAWS.md §4; FR-43 / D315), for a consumer's bounds
    (the unit producer's R5, population_unit_turnover.supply_bound):
    - a chain's release, J = kappa C phi with phi <= 1 and C at most its pool's machines, is at
      most kappa M_pool, kappa = v stages / residues;
    - a transfer's, V V_C times its saturations and its affinity factor (each at most 1), at most
      nu V_C V for each row it makes, V the cell's largest volume (species_common
      .largest_volumes);
    - a row it makes in a cell otherwise (a degradation's monomers, a release's fates, an
      export's coupling) has no such static bound: math.inf, so a consumer refuses it."""
    top = {s.route_id: max(v for _, v in s.changes) for s in schedule}
    for _, values in declaration.templates:  # A newcomer's values (§9.16, item 6).
        for name, value in values:
            top[name] = max(top.get(name, 0.0), value)
    machines = {pool.id: pool.machines * COPY_FMOL for pool in declaration.pools}
    volumes = common.largest_volumes(spec)
    out = {}

    def add(row, cell, rate):
        out[(row, cell)] = out.get((row, cell), 0.0) + rate

    for c in declaration.chains:
        if isinstance(c, ReleasingChain):
            for durable, short in c.release.fates:
                add(durable, c.cell, math.inf)
                add(short, c.cell, math.inf)
        else:
            add(c.product, c.cell, c.speed_per_s * c.stages / c.residues * machines[c.pool])
    for t in declaration.transfers:
        for row, nu in t.stoichiometry:
            if nu > 0:
                add(row, t.cell, nu * top.get(t.id, 0.0) * volumes[t.cell])
    for d in declaration.degradations:
        for row, _ in d.monomers:
            add(row, d.cell, math.inf)
    for e in declaration.exports:
        for row, nu in e.coupling:
            if nu > 0:
                add(row, e.cell, math.inf)
    return out


def single_writer_rows(spec, declaration):
    """The listed rows that keep this operator as their one writer beside a D152 network (FR-43 /
    D315): its exported rows and its outside degradations' monomers (amendment T, §9.17), whose
    moves the per-producer counters report, and the rows FR-42's label owner labels, whose moves
    advance its shares. No stage plans a second writer's reports to either."""
    out = {e.row for e in declaration.exports}
    out |= {row for x in declaration.outside_degradations for row, _ in x.monomers}
    owner = next((d for op, d, _ in composite_spec.entries(spec) if op.LABEL_OWNER), None)
    if owner is not None:
        from cells.operators import species_labels  # The label owner's derivation (amendment G).

        out |= {s.id for s in species_labels.derived(spec, owner)[0].species if s.labels}
    return out


COMPARTMENTS_LAW = "cells.operator.cell_owned_compartments@1"


def check_compartments(spec, declaration):
    """FR-49 (D327; validation/fr49/REGISTRATION.md, Part H): beside cells.operator.cell_owned_compartments@1,
    refuse an outside degradation at a declared compartment's node, then an export into one, then a
    transfer of a listed row there (FR-43 part 3), each with its reason. Degradations are checked
    first, so that each refusal has a world that reaches it (a degradation needs an export carrying
    its polymer into its node). A world declaring no compartment is unchanged."""
    owners = {}
    for op, other, _ in composite_spec.entries(spec):
        if op.LAW_ID == COMPARTMENTS_LAW:
            owners |= {c.node: (c.id, c.owner) for c in other.compartments}
    if not owners:
        return
    for d in declaration.outside_degradations:
        if d.node in owners:
            cid, owner = owners[d.node]
            raise ConfigError(
                f"{LAW_ID}: outside degradation {d.id} is at {d.node!r}, compartment {cid!r} of "
                f"{owner!r} ({COMPARTMENTS_LAW}); a compartment's content is cleared by turnover "
                "or D152's reactions, and an export into a compartment is a later step (FR-49)"
            )
    for e in declaration.exports:
        if e.node in owners:
            cid, owner = owners[e.node]
            raise ConfigError(
                f"{LAW_ID}: export {e.id} opens onto {e.node!r}, compartment {cid!r} of {owner!r} "
                f"({COMPARTMENTS_LAW}); secretion into a compartment is a later step, with its "
                "own books at the compartment's node (FR-49)"
            )
    # FR-43 part 3: a transfer may move a listed row (check_row_writers), but not across a
    # compartment's bounding patch until FR-49's combination checks cover it.
    listed = {s.id for s in declaration.species}
    for op, other, _ in composite_spec.entries(spec):
        if op.ROW_MOVES != "transfer":
            continue
        for name, node in op.written_rows(spec, other):
            if name in listed and node in owners:
                cid, owner = owners[node]
                raise ConfigError(
                    f"{LAW_ID}: {op.LAW_ID} moves the listed row {name!r} at {node!r}, compartment "
                    f"{cid!r} of {owner!r} ({COMPARTMENTS_LAW}); a transfer of a listed row across "
                    "a compartment's patch waits for FR-49's combination checks (FR-43 part 3)"
                )


def check_writers(spec, declaration):
    """Refuse another writer of a listed row (one writer: the sheet's §4.5 and the design's §7.5)
    other than those admitted, and an in-step mover. A D152 network may write a listed row, and
    the unit producer (cells.operator.population_unit_turnover@1) may consume one as its precursor
    (FR-43 / D315: the two-writer rule of 19 November 2026, extended); any other conversion of a
    listed row (D150's turnover, cells.operator.site_occupancy@1's binding) is refused. A transfer
    may move a listed row (FR-43 part 3: the species registry's rule, check_row_writers). Each
    writer is a split part whose half-steps (SSP of order three here and in D152, exact in the
    producer and a transfer) run in declared order and book their own moved amounts and the exact
    dG of their own moves from the state they receive, so the composition is Strang's, second
    order; the row's standard potential has the species registry as its one authority
    (species_registry.check_shared_rows). A labelled or exported row keeps this operator as its one
    writer (sole_rows, refused by check_row_writers)."""
    listed = {s.id for s in declaration.species}
    admitted = (species_reactions.LAW_ID, UNIT_PRODUCER)
    for op, other, _ in composite_spec.entries(spec):
        if op.LAW_ID == LAW_ID or op.ROW_MOVES != "conversion" or op.LAW_ID in admitted:
            continue
        shared = sorted(listed & {name for name, _ in op.written_rows(spec, other)})
        if shared:
            raise ConfigError(
                f"{LAW_ID}: {op.LAW_ID} converts {shared[0]!r}, a listed row; beside this operator "
                f"a listed row's conversions are its own, {species_reactions.LAW_ID}'s and "
                f"{UNIT_PRODUCER}'s (FR-43 / D315, part 3)"
            )
    species_registry.check_row_writers(spec, LAW_ID)
    moved = species_registry.moved_in_step(spec)
    for name in sorted(listed):
        movers = moved.get(name, {}).get("cell", ())
        if movers:
            raise ConfigError(
                f"{LAW_ID}: {name!r} is moved inside the inner step by {movers[0]}; its writer is "
                "this split part's half-steps only"
            )
    species_registry.check_shared_rows(spec, LAW_ID)
    # Amendment T (§9.17.6): retention is the one-writer rule extended to the exported nodes.
    for name in sorted(
        {e.row for e in declaration.exports}
        | {row for x in declaration.outside_degradations for row, _ in x.monomers}
    ):
        movers = moved.get(name, {}).get("outside", ())
        if movers:
            raise ConfigError(
                f"{LAW_ID}: {name!r} is moved at an outside node inside the inner step by "
                f"{movers[0]}; an exported row's writer at its node is this operator's export alone"
            )


def check_occupants(spec, declaration, schedule):
    """Amendment S's refusals at the definition (§9.16, items 1 and 6): a replacement law other
    than replacement@1; a donor copy into or from a slot of this operator (version 1.1, as D152's);
    templates that are not replacement templates; a newcomer whose template gives no value for a
    schedule of its slot; a template value that applies to no schedule of a slot its newcomers
    fill; and a schedule change of a replaced slot at or after its founder's death (a newcomer's
    values are its template's, constant through its life)."""
    for op, _, _ in composite_spec.entries(spec):
        if op.LAW_ID.startswith(REPLACEMENT_FAMILY) and op.LAW_ID != REPLACEMENT_LAW:
            raise ConfigError(
                f"{LAW_ID} composes with {REPLACEMENT_LAW} only, not {op.LAW_ID} (the sheet's "
                "§9.16)"
            )
    replacement, events = common.replacement_of(spec)
    known = set() if replacement is None else {t.id for t in replacement.templates}
    rates = {t: dict(r) for t, r in declaration.templates}
    for tid in rates:
        if tid not in known:
            raise ConfigError(f"{LAW_ID} declares values for {tid}, not a replacement template")
    ours = {e.cell for e in (*declaration.pools, *declaration.chains, *declaration.degradations,
                             *declaration.transfers)}  # fmt: skip
    routes = slot_routes(declaration)
    used, death = set(), {}
    for v in sorted(events, key=lambda v: v.time):
        if v.newcomer != "isolated_template" and (v.slot in ours or v.donor in ours):
            raise ConfigError(
                f"{LAW_ID}: a donor copy into or from {v.slot if v.slot in ours else v.donor}, a "
                "slot of this operator, is version 1.1 (the sheet's §9.16)"
            )
        if v.slot not in ours:
            continue
        death.setdefault(v.slot, v.time)
        for name in routes.get(v.slot, ()):
            if name not in rates.get(v.template, {}):
                raise ConfigError(
                    f"{LAW_ID}: a newcomer from template {v.template} at {v.slot} takes its "
                    f"values from the template: declare {v.template} in templates with a value "
                    f"for {name} (its occupant rule, §9.16)"
                )
            used.add((v.template, name))
    changes = {s.route_id: s.changes for s in schedule}
    for slot, t_death in death.items():
        for name in routes.get(slot, ()):
            late = [t for t, _ in changes[name] if t >= t_death]
            if late:
                raise ConfigError(
                    f"{LAW_ID}: schedule {name} changes at {late[0]} s, at or after its founder's "
                    f"death at {t_death} s; a newcomer's values are its template's (§9.16)"
                )
    for tid, values in rates.items():
        unused = sorted(set(values) - {n for t, n in used if t == tid})
        if unused:
            raise ConfigError(
                f"{LAW_ID}: template {tid}'s value for {unused[0]} applies to no schedule of a "
                "slot its newcomers fill"
            )


def smallest_volumes(spec):
    """{cell id: the smallest volume it can take}: its declared volume, or where water changes the
    volumes (FR-43 / D315) its water compartment's declared minimum."""
    out = {c.id: c.volume_pL for c in spec.model.cells}
    for op, water, _ in composite_spec.entries(spec):
        if op.LAW_ID == species_reactions.WATER:
            for c in water.compartments:
                if c.compartment_id in out:
                    out[c.compartment_id] = min(out[c.compartment_id], c.minimum_volume_pL)
    return out


def check_rate_bound(spec, declaration, schedule):
    """Refuse dt times a route's largest static rate above RATE_BOUND: a chain's kappa, a
    degradation's k, and a gene-templated chain's initiation k_I c_T (the run-time stage
    condition covers the rest)."""
    dt = spec.execution.dt
    top = {s.route_id: max(v for _, v in s.changes) for s in schedule}
    for _, values in declaration.templates:  # A newcomer's values (§9.16, item 6).
        for name, value in values:
            top[name] = max(top[name], value)
    volumes = smallest_volumes(spec)  # c_T is largest at the smallest volume (FR-43 / D315).
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
    for _, r in releases_of(declaration):
        if dt / r.dwell_s > RATE_BOUND:
            raise ConfigError(f"{LAW_ID}: release {r.id} has dt/tau = {dt / r.dwell_s:.3g} > 1")
    for e in (*declaration.exports, *declaration.outside_degradations):  # §9.17.6.
        if dt * top[e.id] > RATE_BOUND:
            raise ConfigError(f"{LAW_ID}: {e.id} has dt k = {dt * top[e.id]:.3g} > 1")


def check_labels(spec, declaration):
    """FR-42's labels on a release's fate rows (D296): the two fates are one chemistry, its chain's
    one source labels both (label_sources), and a hold marked at completion carries its labels into
    either. So where the label owner labels one fate row it labels the other, with the same labels
    in the same order, its producers' derived labels included (amendment G)."""
    owner = next((d for op, d, _ in composite_spec.entries(spec) if op.LABEL_OWNER), None)
    if owner is None:
        return
    from cells.operators import species_labels  # The label owner's derivation (amendment G).

    # Amendment G (§9.20): a species' labels include its producers' derived labels, so the two fate
    # rows' derived lists must agree, which holds where both declare the same producers.
    labels = {s.id: s.labels for s in species_labels.derived(spec, owner)[0].species}
    for _, r in releases_of(declaration):
        durable, short = r.fates[0]
        if labels.get(durable) != labels.get(short):
            raise ConfigError(
                f"{LAW_ID}: release {r.id}'s fate rows {durable!r} and {short!r} carry FR-42's "
                "labels alike or not at all (its chain's one source labels both)"
            )


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
    layout_r, state_r = _bind_releases(declaration, layout, listed, chains)
    layout |= layout_r
    state |= state_r
    layout_s, state_s = _bind_replacement(spec, declaration, layout_r)
    layout |= layout_s
    state |= state_s
    layout_e, state_e = _bind_exports(spec, declaration, listed)
    layout |= layout_e
    state |= state_e
    return state, layout


def exported_nodes(declaration):
    """The exported nodes, in their exports' order (amendment T's poly_outside_node axis)."""
    return tuple(dict.fromkeys(e.node for e in declaration.exports))


def _bind_exports(spec, declaration, listed):
    """Amendment T's layout and state (§9.17), all zero-size without an export: each export's cell,
    node, row and coupling, each outside degradation's node, polymer and monomers, and the exported
    nodes' accumulators and energy terms."""
    m, x = spec.model, spec.execution
    k, cells, slots = len(listed), [c.id for c in m.cells], [c.id for c in m.extracellular]
    exports, outside = declaration.exports, declaration.outside_degradations
    nodes = list(exported_nodes(declaration))

    def per_row(pairs):
        out = np.zeros(k)
        for row, value in pairs:
            out[listed.index(row)] = value
        return out

    nu = np.array([per_row(e.coupling) for e in exports]).reshape(len(exports), k)
    K = np.array([per_row(e.saturation_mM) for e in exports]).reshape(len(exports), k)
    monomers = np.array([per_row(d.monomers) for d in outside]).reshape(len(outside), k)
    layout = dict(
        poly_out_slot_hot=_one_hot([slots.index(n) for n in nodes], x.extracellular_capacity),
        poly_exp_cell=_one_hot([cells.index(e.cell) for e in exports], x.capacity),
        poly_exp_node=_one_hot([nodes.index(e.node) for e in exports], len(nodes)),
        poly_exp_row=_one_hot([listed.index(e.row) for e in exports], k),
        poly_exp_nu=nu,
        poly_exp_saturates=nu < 0,
        poly_exp_K_mM=np.where(nu < 0, K, 1.0),
        poly_odeg_node=_one_hot([nodes.index(d.node) for d in outside], len(nodes)),
        poly_odeg_polymer=_one_hot([listed.index(d.polymer) for d in outside], k),
        poly_odeg_monomers=monomers,
        poly_odeg_length=np.asarray([float(d.residues) for d in outside], dtype=float),
    )
    s, n, e, d = len(m.species_ids), len(nodes), len(exports), len(outside)
    state = dict(
        poly_export_forward_fmol=np.zeros(e),
        poly_export_backward_fmol=np.zeros(e),
        poly_export_heat_pJ=np.zeros(e),
        poly_outside_degraded_fmol=np.zeros(d),
        poly_outside_degradation_heat_pJ=np.zeros(d),
        poly_outside_produced_fmol=np.zeros((s, n)),
        poly_outside_consumed_fmol=np.zeros((s, n)),
        poly_outside_dissipated_energy_pJ=np.zeros(n),
        poly_outside_standard_energy_pJ=np.zeros(n),
        poly_outside_energy_magnitude_pJ=np.zeros(n),
    )
    return layout, state


def replaced_slots(spec, declaration):
    """The cells, in the model's order, that a replacement@1 event replaces and where this
    operator has a pool, chain, degradation or transfer (§9.16, item 1); () without one."""
    _, events = common.replacement_of(spec)
    ours = {e.cell for e in (*declaration.pools, *declaration.chains, *declaration.degradations,
                             *declaration.transfers)}  # fmt: skip
    hit = {v.slot for v in events} & ours
    return tuple(c.id for c in spec.model.cells if c.id in hit)


def _bind_replacement(spec, declaration, release_layout):
    """Amendment S's layout and state (§9.16): one-hot maps of the replaced slots' chains,
    releases, degradations and transfers, and their counters, all zero-size without a
    replacement."""
    slots = replaced_slots(spec, declaration)
    cells = [c.id for c in spec.model.cells]
    at = {cell: i for i, cell in enumerate(slots)}
    chains, releases = declaration.chains, releases_of(declaration)

    def pick(entities, cell_of):
        index = [i for i, e in enumerate(entities) if cell_of(e) in at]
        return index, [at[cell_of(entities[i])] for i in index]

    rc, rc_slot = pick(chains, lambda c: c.cell)
    rr, rr_slot = pick(releases, lambda pair: pair[0].cell)
    rd, rd_slot = pick(declaration.degradations, lambda d: d.cell)
    rt, rt_slot = pick(declaration.transfers, lambda t: t.cell)
    re, re_slot = pick(declaration.exports, lambda e: e.cell)  # §9.17.3.
    chain_of = {c.id: k for k, c in enumerate(chains)}
    rr_chain = [rc.index(chain_of[releases[i][0].id]) for i in rr]
    classes = release_layout["poly_rel_classes"].shape[1]
    n = len(slots)
    layout = dict(
        poly_rep_slot_cell=np.asarray([cells.index(c) for c in slots], dtype=np.int64),
        poly_rep_chain_hot=_one_hot(rc, len(chains)),
        poly_rep_chain_slot_hot=_one_hot(rc_slot, n),
        poly_rep_release_hot=_one_hot(rr, len(releases)),
        poly_rep_release_slot_hot=_one_hot(rr_slot, n),
        poly_rep_release_chain_hot=_one_hot(rr_chain, len(rc)),
        poly_rep_degradation_hot=_one_hot(rd, len(declaration.degradations)),
        poly_rep_degradation_slot_hot=_one_hot(rd_slot, n),
        poly_rep_transfer_hot=_one_hot(rt, len(declaration.transfers)),
        poly_rep_transfer_slot_hot=_one_hot(rt_slot, n),
        poly_rep_export_hot=_one_hot(re, len(declaration.exports)),
        poly_rep_export_slot_hot=_one_hot(re_slot, n),
    )
    counters = (len(rc), len(CHAIN_COUNTERS))
    state = dict(
        poly_rep_applied=np.zeros(n, dtype=np.int64),
        poly_rep_chains_removed_fmol=np.zeros(len(rc)),
        poly_rep_residues_removed_fmol=np.zeros(len(rc)),
        poly_rep_removed_energy_pJ=np.zeros(len(rc)),
        poly_rep_hold_removed_fmol=np.zeros((len(rr), classes)),
        poly_rep_chain_birth_fmol=np.zeros(counters),
        poly_rep_chain_departed_fmol=np.zeros(counters),
        poly_rep_release_birth_fmol=np.zeros((len(rr), classes, len(FATES))),
        poly_rep_release_departed_fmol=np.zeros((len(rr), classes, len(FATES))),
        poly_rep_degradation_birth_fmol=np.zeros(len(rd)),
        poly_rep_degradation_departed_fmol=np.zeros(len(rd)),
        poly_rep_transfer_birth_fmol=np.zeros(len(rt)),
        poly_rep_transfer_departed_fmol=np.zeros(len(rt)),
        poly_rep_export_birth_fmol=np.zeros((len(re), len(EXPORT_PARTS))),
        poly_rep_export_departed_fmol=np.zeros((len(re), len(EXPORT_PARTS))),
    )
    return layout, state


def _replaced_sets(spec, declaration):
    """The run view's sets of the replaced entities' axes (§9.16), empty without a replacement."""
    slots = replaced_slots(spec, declaration)
    on = set(slots)

    def axis(name, holds, entities, cell_of):
        picked = [e for e in entities if cell_of(e) in on]
        return {
            "id": name,
            "ids": tuple((e[1] if isinstance(e, tuple) else e).id for e in picked),
            "holds": holds,
            "at": tuple({"cell": cell_of(e)} for e in picked),
        }

    return {
        REPLACED_SLOT_AXIS: {
            "id": REPLACED_SLOT_AXIS,
            "ids": slots,
            "holds": "replaced slot",
            "at": tuple({"cell": c} for c in slots),
        },
        REPLACED_CHAIN_AXIS: axis(
            REPLACED_CHAIN_AXIS, "replaced chain", declaration.chains, lambda c: c.cell
        ),
        REPLACED_RELEASE_AXIS: axis(
            REPLACED_RELEASE_AXIS, "replaced release", releases_of(declaration), lambda e: e[0].cell
        ),
        REPLACED_DEGRADATION_AXIS: axis(
            REPLACED_DEGRADATION_AXIS,
            "replaced degradation",
            declaration.degradations,
            lambda d: d.cell,
        ),  # fmt: skip
        REPLACED_TRANSFER_AXIS: axis(
            REPLACED_TRANSFER_AXIS, "replaced transfer", declaration.transfers, lambda t: t.cell
        ),
        REPLACED_EXPORT_AXIS: axis(
            REPLACED_EXPORT_AXIS, "replaced export", declaration.exports, lambda e: e.cell
        ),
        COUNTER_AXIS: {
            "id": COUNTER_AXIS,
            "ids": ("initiated", "stage_exits", "released"),
            "holds": "chain counter",
        },
    }


def slot_routes(declaration):
    """{cell: (schedule ID, ...)}: each cell's routes' and scheduled releases' schedules."""
    out = {}
    for r in (*declaration.chains, *declaration.degradations, *declaration.transfers,
              *declaration.exports):  # fmt: skip
        out.setdefault(r.cell, []).append(r.id)
    for c, r in releases_of(declaration):
        if r.durable_fraction is None:
            out.setdefault(c.cell, []).append(r.id)
    return {cell: tuple(ids) for cell, ids in out.items()}


def occupant_controls(spec, declaration, values, column, times):
    """[time, replaced slot] the replacements due by each time (replacement@1's own count, its
    events at or before the time), and, in place in `values` [time, schedule], the occupant rule
    (§9.16, item 6): from each newcomer's birth its template's value for every schedule of its
    slot, constant through its life. Empty without a replacement."""
    slots = replaced_slots(spec, declaration)
    times = np.asarray(times, dtype=np.float64)
    due = np.zeros((times.size, len(slots)))
    if not slots:
        return due
    _, events = common.replacement_of(spec)
    rates = {t: dict(r) for t, r in declaration.templates}
    routes = slot_routes(declaration)
    for j, slot in enumerate(slots):
        lives = sorted((v for v in events if v.slot == slot), key=lambda v: v.time)
        at = np.asarray([v.time for v in lives])
        due[:, j] = np.searchsorted(at, times, side="right")
        for k, v in enumerate(lives):
            end = lives[k + 1].time if k + 1 < len(lives) else math.inf
            live = (times >= v.time) & (times < end)
            for name in routes.get(slot, ()):  # A missing value: check_occupants refuses it.
                if name in rates.get(v.template, {}):
                    values[live, column[name]] = rates[v.template][name]
    return due


def exporting(p):
    """Whether the definition declares an export (static, by its layout's shape): without one no
    export or outside computation is traced (amendment T, §9.17.7)."""
    return p.poly_exp_cell.shape[0] > 0


def replacing(p):
    """Whether a replacement@1 event replaces a slot of this operator (static, by its layout's
    shape): without one no replacement computation is traced (§9.16, item 9)."""
    return p.poly_rep_slot_cell.shape[0] > 0


def _gather(hot, values, *, xp):
    """values' rows that the one-hot map `hot` picks, [picked, ...]: exact (one product by 1)."""
    width = math.prod(values.shape[1:])
    flat = values.reshape(values.shape[0], width)
    return (hot @ flat).reshape((hot.shape[0], *values.shape[1:]))


def _spread(hot, mask, *, xp):
    """[entity] bool: the entities that `hot` picks where mask (over the picked) holds."""
    return (xp.where(mask, 1.0, 0.0) @ hot) > 0


def hold_report(state, release_due, p, *, xp):
    """[release] the holds the event empties, H summed over the class axis from the state before
    it where the release's slot is due, 0 elsewhere: its label_pools' entries, in order (FR-42's
    pool reporter's report; erratum E, §9.18)."""
    return xp.where(release_due, entity_sum(state.poly_hold_fmol, axis=1, xp=xp), 0.0)


def poly_event(state, control, p, *, xp=jnp):
    """Amendment S's event (§9.16, item 2), at the start of the step leaving an event time: on each
    replaced slot whose next replacement is due, its chains in progress and its holds leave
    (counted, with the standard free energy leaving with them, never as heat), its pools' machines
    are all free, and each counter's value becomes the newcomer's birth value, the departed
    generation's totals recorded. It reads only its own state and its control, so its place among
    the events does not matter. Returns (state, valid, removed): removed the holds it emptied
    (hold_report). (state, None, None) statically without a replacement; nothing due: the
    start state, bitwise."""
    if not replacing(p):
        return state, None, None
    applied = state.poly_rep_applied
    count = getattr(control, REPLACEMENTS_DUE)
    due = count == applied + 1  # [replaced slot]
    valid = xp.all(due | (count == applied))  # A stale count refuses the step.
    due_f = xp.where(due, 1.0, 0.0)
    rc = (p.poly_rep_chain_slot_hot @ due_f) > 0  # [replaced chain]
    rr = (p.poly_rep_release_slot_hot @ due_f) > 0
    rd = (p.poly_rep_degradation_slot_hot @ due_f) > 0
    rt = (p.poly_rep_transfer_slot_hot @ due_f) > 0
    chain_due = _spread(p.poly_rep_chain_hot, rc, xp=xp)  # [chain]
    complexes = _gather(p.poly_rep_chain_hot, state.poly_complexes_fmol, xp=xp)  # [rc, stage]
    held = _gather(p.poly_rep_chain_hot, p.poly_chain_held, xp=xp)
    chains_out = entity_sum(complexes, axis=1, xp=xp)
    residues_out = entity_sum(held * complexes, axis=1, xp=xp)
    hold = _gather(p.poly_rep_release_hot, state.poly_hold_fmol, xp=xp)  # [rr, class]
    length = p.poly_rep_chain_hot @ p.poly_chain_length  # [rc]
    hold_residues = p.poly_rep_release_chain_hot.T @ entity_sum(hold, axis=1, xp=xp)  # [rc]
    rt_pJ = 1e-3 * R * p.temperature
    mu_res = p.poly_rep_chain_hot @ p.poly_chain_residue_mu_RT
    energy_out = rt_pJ * mu_res * (residues_out + length * hold_residues)
    counters = xp.stack(
        [p.poly_rep_chain_hot @ getattr(state, name) for name in CHAIN_COUNTERS], axis=1
    )  # [rc, counter]
    releases = _gather(p.poly_rep_release_hot, state.poly_hold_released_fmol, xp=xp)
    degraded = p.poly_rep_degradation_hot @ state.poly_degraded_fmol
    transferred = p.poly_rep_transfer_hot @ state.poly_transferred_fmol
    exported = {}
    if exporting(p):  # §9.17.3: each export's two one-way counters split by generation.
        re = (p.poly_rep_export_slot_hot @ due_f) > 0
        now = xp.stack(
            [
                p.poly_rep_export_hot @ state.poly_export_forward_fmol,
                p.poly_rep_export_hot @ state.poly_export_backward_fmol,
            ],
            axis=1,
        )

    def add(name, mask, term):
        value = getattr(state, name)
        return xp.where(mask.reshape(mask.shape + (1,) * (value.ndim - 1)), value + term, value)

    def born(birth, departed, mask, now):
        b, d = getattr(state, birth), getattr(state, departed)
        m = mask.reshape(mask.shape + (1,) * (b.ndim - 1))
        return {birth: xp.where(m, now, b), departed: xp.where(m, now - b, d)}

    pool_due = _spread(p.poly_chain_pool, chain_due, xp=xp)  # [pool]
    release_due = _spread(p.poly_rep_release_hot, rr, xp=xp)  # [release]
    if exporting(p):
        exported = born("poly_rep_export_birth_fmol", "poly_rep_export_departed_fmol", re, now)
    new = state._replace(
        poly_complexes_fmol=xp.where(chain_due[:, None], 0.0, state.poly_complexes_fmol),
        poly_free_machines_fmol=xp.where(
            pool_due, p.poly_pool_total_fmol, state.poly_free_machines_fmol
        ),
        poly_hold_fmol=xp.where(release_due[:, None], 0.0, state.poly_hold_fmol),
        poly_rep_applied=xp.where(due, applied + 1, applied),
        poly_rep_chains_removed_fmol=add("poly_rep_chains_removed_fmol", rc, chains_out),
        poly_rep_residues_removed_fmol=add("poly_rep_residues_removed_fmol", rc, residues_out),
        poly_rep_removed_energy_pJ=add("poly_rep_removed_energy_pJ", rc, energy_out),
        poly_rep_hold_removed_fmol=add("poly_rep_hold_removed_fmol", rr, hold),
        **born("poly_rep_chain_birth_fmol", "poly_rep_chain_departed_fmol", rc, counters),
        **born("poly_rep_release_birth_fmol", "poly_rep_release_departed_fmol", rr, releases),
        **born(
            "poly_rep_degradation_birth_fmol", "poly_rep_degradation_departed_fmol", rd, degraded
        ),  # fmt: skip
        **born(
            "poly_rep_transfer_birth_fmol", "poly_rep_transfer_departed_fmol", rt, transferred
        ),  # fmt: skip
        **exported,
    )
    valid &= xp.all(xp.isfinite(energy_out))
    flowing = xp.any(due)  # Nothing due: the start state, bitwise.
    selected = type(state)(*(xp.where(flowing, a, b) for a, b in zip(new, state, strict=True)))
    return selected, valid, hold_report(state, release_due, p, xp=xp)


def _bind_releases(declaration, layout, listed, chains):
    """The release's layout and state (the sheet's §9), empty without a release block; with a held
    hold, its pool's free machines start at M - sum H(0)."""
    releases = releases_of(declaration)
    k, fates = len(listed), len(FATES)
    classes = max((len(r.fates) for _, r in releases), default=0)
    chain_index = {c.id: i for i, c in enumerate(chains)}
    present = np.zeros((len(releases), classes), dtype=bool)
    fate = np.zeros((len(releases), classes, fates, k))
    hold0 = np.zeros((len(releases), classes))
    for i, (_, r) in enumerate(releases):
        present[i, : len(r.fates)] = True
        for j, pair in enumerate(r.fates):
            for f, row in enumerate(pair):
                fate[i, j, f, listed.index(row)] = 1.0
        hold0[i, : len(r.initial_copies)] = np.asarray(r.initial_copies) * COPY_FMOL
    out = dict(
        poly_rel_chain=_one_hot([chain_index[c.id] for c, _ in releases], len(chains)),
        poly_rel_rate=np.asarray([1.0 / r.dwell_s for _, r in releases], dtype=float),
        poly_rel_held=np.asarray([float(r.machine == "held") for _, r in releases], dtype=float),
        # 1 where FR-42's labels mark the release (the default), 0 where the hold carries them.
        poly_rel_at_release=np.asarray(
            [float(r.label is None or r.label.at == "release") for _, r in releases],
            dtype=float,
        ),
        poly_rel_classes=present,
        poly_rel_fate=fate,
        poly_rel_hold0_fmol=hold0,
    )
    state = dict(
        poly_hold_fmol=hold0.copy(),
        poly_hold_released_fmol=np.zeros((len(releases), classes, fates)),
        poly_release_heat_pJ=np.zeros((len(releases), classes, fates)),
    )
    if releases:
        held = out["poly_rel_held"] * entity_sum(hold0, axis=1, xp=np)  # [release]
        engaged = (held @ out["poly_rel_chain"]) @ layout["poly_chain_pool"]  # [pool]
        state["poly_free_machines_fmol"] = layout["poly_pool_total_fmol"] - engaged
    return out, state


# ------------------------------------------------------------------ the law


def _product(values, mask, *, xp):
    """prod over the last axis of `values` where `mask`, 1 elsewhere."""
    return xp.prod(xp.where(mask, values, 1.0), axis=-1)


def releasing(p):
    """Whether the definition declares a release (static, by its layout's shape): without one no
    release computation is traced."""
    return p.poly_rel_rate.shape[0] > 0


def _with_release(p, *, xp):
    """[chain] 1 where the chain declares a release, else 0."""
    return entity_sum(p.poly_rel_chain, axis=0, xp=xp)


def _product_ok(product, p, *, xp):
    """A chain's product at or below c° (its domain where the chain is in use). A chain with a
    release puts no product row in use at completion (the sheet's §9.6), so it is exempt."""
    ok = product <= STANDARD_MM
    if releasing(p):
        ok = ok | (_with_release(p, xp=xp) > 0)
    return ok


def class_weights(label, p, *, xp):
    """(psi, first) [release, class]: the one-hot of each release's class psi(t), and of class 1."""
    index = xp.arange(1, p.poly_rel_classes.shape[1] + 1, dtype=float)
    psi = xp.where(p.poly_rel_classes & (index[None, :] == label[:, None]), 1.0, 0.0)
    first = xp.where(p.poly_rel_classes & (index[None, :] == 1.0), 1.0, 0.0)
    return psi, first


def release_flux(c, hold, fraction, label, p, *, xp):
    """Q^f [release, class, fate] (fmol/s) into each class's fate rows: the hold's first-order exit
    at 1/tau split p, 1 - p (the sheet's §9.2), with no affinity factor. Hold class k feeds class
    k's rows; with the label at release the hold's one class feeds class psi(t)'s. With its domain
    (§9.6): c_F <= c° at every fate row a positive flux feeds."""
    psi, _ = class_weights(label, p, xp=xp)
    whole = entity_sum(hold, axis=1, xp=xp)  # [release] the hold, every class.
    source = xp.where(p.poly_rel_at_release[:, None] > 0, psi * whole[:, None], hold)
    split = xp.stack([fraction, 1.0 - fraction], axis=-1)  # [release, fate]
    flux = (p.poly_rel_rate[:, None] * source)[:, :, None] * split[:, None, :]
    c_release = p.poly_rel_chain @ (p.poly_chain_cell @ c.T)  # [release, k] at its chain's cell
    c_fate = xp.transpose(
        species_sum(xp.transpose(p.poly_rel_fate * c_release[:, None, None, :]), xp=xp)
    )  # [release, class, fate]
    return flux, xp.all(xp.where(flux > 0, c_fate <= STANDARD_MM, True))


def export_fluxes(n, c, mu, n_o, volume_o, controls, p, *, xp):
    """Amendment T's routes (§9.17.2; erratum H, §9.21): (forward [export], backward [export],
    outside [outside degradation]), ok, the unidirectional consumption the stage condition reads at
    the cells [k, cell] and at the exported nodes [k, node], and the outside degradations' one-way
    parts.
    - An export's one-way parts: forward k_E n_F,c phi_E, from c to o, and backward forward
      e^(x_E), from o to c, with x_E = mu_F,o - mu_F,c + sum nu mu_c (RT units) and phi_E the
      product over its consumed coupling rows of c/(K + c). Its net J_E is forward - backward.
    - An outside degradation's net loss k_o n_F,o (1 - e^(y_o)), §4.4's law at the node.
    - The domains: x_E <= X_DOM at an export in use, y_o <= X_DOM at an outside degradation in
      use (one-sided; refused, never repaired)."""
    export_rate, outside_rate = controls[5], controls[6]
    mu_o = p.poly_mu_RT[:, None] + xp.log(n_o / volume_o[None, :] / p.poly_c0_mM)  # [k, node]
    c_exp, mu_exp = p.poly_exp_cell @ c.T, p.poly_exp_cell @ mu.T  # [export, k] at its cell
    phi = _product(c_exp / (p.poly_exp_K_mM + c_exp), p.poly_exp_saturates, xp=xp)
    mu_F_o = species_sum((p.poly_exp_row * (p.poly_exp_node @ mu_o.T)).T, xp=xp)
    x = mu_F_o - species_sum((p.poly_exp_row * mu_exp).T, xp=xp)
    x = x + species_sum((p.poly_exp_nu * mu_exp).T, xp=xp)
    n_F = species_sum((p.poly_exp_row * (p.poly_exp_cell @ n.T)).T, xp=xp)
    forward = export_rate * n_F * phi
    backward = forward * xp.exp(x)
    ok = xp.all(xp.where((export_rate > 0) & (n_F > 0), x <= X_DOM, True))
    n_od, mu_od = p.poly_odeg_node @ n_o.T, p.poly_odeg_node @ mu_o.T  # [outside, k]
    polymer = species_sum((p.poly_odeg_polymer * n_od).T, xp=xp)
    y = (
        p.poly_odeg_length * species_sum((p.poly_odeg_monomers * mu_od).T, xp=xp)
        - species_sum((p.poly_odeg_polymer * mu_od).T, xp=xp)
    ) / p.poly_odeg_length
    od_forward = outside_rate * polymer
    od_backward = od_forward * xp.exp(y)
    outside = od_forward * -xp.expm1(y)
    ok &= xp.all(xp.where((outside_rate > 0) & (polymer > 0), y <= X_DOM, True))
    taken = xp.where(p.poly_exp_nu < 0, -p.poly_exp_nu, 0.0)
    made = xp.where(p.poly_exp_nu > 0, p.poly_exp_nu, 0.0)
    used = (
        forward[:, None] * (p.poly_exp_row + taken) + backward[:, None] * made
    ).T @ p.poly_exp_cell  # fmt: skip
    length = p.poly_odeg_length[:, None]
    used_o = (backward[:, None] * p.poly_exp_row).T @ p.poly_exp_node + (
        od_forward[:, None] * p.poly_odeg_polymer
        + length * od_backward[:, None] * p.poly_odeg_monomers
    ).T @ p.poly_odeg_node
    parts = dict(odeg_forward=od_forward, odeg_backward=od_backward)
    return (forward, backward, outside), ok, used, used_o, parts


def fluxes(
    n, free, complexes, controls, p, volume, *, xp, hold=None, one_way=False, n_o=None,
    volume_o=None,
):  # fmt: skip
    """Every route's flux at amounts n [k, cell] (fmol), free machines [pool] and complexes
    [chain, stage], and with a release its hold [release, class]; with the affinities its domain
    reads and the unidirectional rates its stage condition reads."""
    init_rate, deg_rate, tr_cap = controls[:3]
    c = n / volume[None, :]  # mM.
    ln_rel = xp.log(c / p.poly_c0_mM)  # ln(c/c0)
    mu = p.poly_mu_RT[:, None] + ln_rel  # [k, cell] mu/RT.
    # Chains, at their cells.
    c_chain = p.poly_chain_cell @ c.T  # [chain, k]
    mu_chain = p.poly_chain_cell @ mu.T
    sat = _product(c_chain / (p.poly_chain_K_mM + c_chain), p.poly_chain_saturates, xp=xp)
    x_chain = p.poly_chain_residue_mu_RT + species_sum((p.poly_chain_net * mu_chain).T, xp=xp)
    phi = sat * -xp.expm1(x_chain)
    stage = p.poly_chain_kappa * phi  # [chain] the stage rate.
    j_stage = xp.where(p.poly_chain_present, stage[:, None] * complexes, 0.0)
    v_chain = p.poly_chain_cell @ volume
    gene = p.poly_chain_copies * COPY_FMOL / xp.where(v_chain > 0, v_chain, 1.0)
    template = species_sum((p.poly_chain_template * c_chain).T, xp=xp) + gene  # mM
    lam = init_rate * template  # [chain] 1/s per free machine.
    pool_free = p.poly_chain_pool @ free  # [chain] its pool's free machines.
    j_init = lam * pool_free
    product = species_sum((p.poly_chain_product * c_chain).T, xp=xp)
    # Degradations.
    n_deg = p.poly_deg_cell @ n.T  # [deg, k]
    mu_deg = p.poly_deg_cell @ mu.T
    polymer = species_sum((p.poly_deg_polymer * n_deg).T, xp=xp)
    y = (
        p.poly_deg_length * species_sum((p.poly_deg_monomers * mu_deg).T, xp=xp)
        - species_sum((p.poly_deg_polymer * mu_deg).T, xp=xp)
    ) / p.poly_deg_length
    j_deg = deg_rate * polymer * -xp.expm1(y)
    # Transfers.
    c_tr = p.poly_tr_cell @ c.T
    mu_tr = p.poly_tr_cell @ mu.T
    v_tr = p.poly_tr_cell @ volume
    forward = v_tr * tr_cap * _product(c_tr / (p.poly_tr_K_mM + c_tr), p.poly_tr_saturates, xp=xp)
    x_tr = species_sum((p.poly_tr_nu * mu_tr).T, xp=xp)
    j_tr = forward * -xp.expm1(x_tr / p.poly_tr_share)
    backward = forward * xp.exp(x_tr / p.poly_tr_share)
    # The one-sided domains, at the routes in use.
    in_use = (entity_sum(complexes, axis=1, xp=xp) > 0) | (j_init > 0)
    ok = xp.all(xp.where(in_use, (x_chain <= X_DOM) & _product_ok(product, p, xp=xp), True))
    ok &= xp.all(xp.where((deg_rate > 0) & (polymer > 0), y <= X_DOM, True))
    # Unidirectional consumption per (row, cell), the stage condition's rates.
    s_total = entity_sum(j_stage, axis=1, xp=xp)  # [chain] every stage's exits.
    draw = (p.poly_chain_r * s_total)[:, None] * p.poly_chain_draws  # [chain, k]
    used = draw.T @ p.poly_chain_cell + (p.poly_deg_polymer * j_deg[:, None]).T @ p.poly_deg_cell
    used += (
        xp.where(p.poly_tr_nu < 0, -p.poly_tr_nu, 0.0) * forward[:, None]
        + xp.where(p.poly_tr_nu > 0, p.poly_tr_nu, 0.0) * backward[:, None]
    ).T @ p.poly_tr_cell
    routes = (j_init, j_stage, j_deg, j_tr)
    info = dict(ok=ok, stage=stage, lam_pool=p.poly_chain_pool.T @ lam, used=used)
    if one_way:  # Static (FR-42): the two-sided routes' one-way parts, for labelled rows.
        info |= dict(deg_forward=deg_rate * polymer, tr_forward=forward, tr_backward=backward)
        info["deg_backward"] = info["deg_forward"] * xp.exp(y)
    if releasing(p):
        j_rel, release_ok = release_flux(c, hold, controls[3], controls[4], p, xp=xp)
        routes += (j_rel,)
        info["ok"] = ok & release_ok
    if exporting(p):  # Amendment T (§9.17): its routes follow the release's, if any.
        j_exp, exp_ok, used_c, used_o, parts = export_fluxes(
            n, c, mu, n_o, volume_o, controls, p, xp=xp
        )
        routes += j_exp
        info["ok"] = info["ok"] & exp_ok
        info["used"] = info["used"] + used_c
        info["used_outside"] = used_o
        if one_way:
            info |= parts
    return routes, info


def _completed_rows(p, *, xp):
    """The rows a completion joins: its product's, or none for a chain with a release, whose
    completions join its hold (the sheet's §9.7)."""
    if not releasing(p):
        return p.poly_chain_product
    return p.poly_chain_product * (1.0 - _with_release(p, xp=xp))[:, None]


def export_changes(j_exp, p, *, xp):
    """Amendment T's moves (§9.17): (at the cells: dn [k, cell], produced, consumed; at the exported
    nodes: dn [k, node], produced, consumed) of its routes' fluxes or extents (forward, backward,
    outside): an export moves its row F from c to o and runs its coupling at c by its net J_E =
    forward - backward; an outside degradation hydrolyses F at o into its monomers there."""
    forward, backward, outside = j_exp
    net = forward - backward
    row = net[:, None] * p.poly_exp_row
    coupling = net[:, None] * p.poly_exp_nu
    produced = xp.where(coupling > 0, coupling, 0.0).T @ p.poly_exp_cell
    consumed = (row + xp.where(coupling < 0, -coupling, 0.0)).T @ p.poly_exp_cell
    made_o = (p.poly_odeg_length * outside)[:, None] * p.poly_odeg_monomers
    used_o = outside[:, None] * p.poly_odeg_polymer
    produced_o = row.T @ p.poly_exp_node + made_o.T @ p.poly_odeg_node
    consumed_o = used_o.T @ p.poly_odeg_node
    return produced - consumed, produced, consumed, produced_o - consumed_o, produced_o, consumed_o


def changes(j_init, j_stage, j_deg, j_tr, p, *, xp, j_rel=None, weights=None, j_exp=None):
    """(dn [k, cell], d free [pool], d complexes [chain, stage], produced, consumed), and with a
    release d hold [release, class], of fluxes or their extents: A J, every move's stoichiometry
    (the sheet's §4.7 and §9.7). weights: (arrival, first) [release, class], the one-hots of each
    release's arrival class and of class 1 (class_weights)."""
    s_total = entity_sum(j_stage, axis=1, xp=xp)
    released = entity_sum(xp.where(p.poly_chain_last, j_stage, 0.0), axis=1, xp=xp)
    r = p.poly_chain_r[:, None]
    chain_made = r * s_total[:, None] * p.poly_chain_releases + released[:, None] * (
        _completed_rows(p, xp=xp)
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
    if j_rel is None:
        d_free = (released - j_init) @ p.poly_chain_pool
    else:  # A held machine returns at release, not at completion (the sheet's §9.3).
        held = p.poly_rel_held @ p.poly_rel_chain  # [chain]
        out = entity_sum(j_rel, axis=(1, 2), xp=xp)  # [release] every release
        freed = released * (1.0 - held) + (p.poly_rel_held * out) @ p.poly_rel_chain
        d_free = (freed - j_init) @ p.poly_chain_pool
    upstream = xp.concatenate([j_init[:, None], j_stage[:, :-1]], axis=1)
    d_complexes = xp.where(p.poly_chain_present, upstream - j_stage, 0.0)
    tail = ()
    if j_exp is not None:  # Amendment T (§9.17): the exports' cell moves, then their nodes'.
        _, produced_e, consumed_e, *tail = export_changes(j_exp, p, xp=xp)
        produced, consumed = produced + produced_e, consumed + consumed_e
    if j_rel is None:
        return (produced - consumed, d_free, d_complexes, produced, consumed, *tail)
    # The release (the sheet's §9.7): arrivals join the hold's class; releases leave it into each
    # class's fate rows, all from class 1 where the label marks the release.
    arrival, first = weights
    made = entity_sum(j_rel[..., None] * p.poly_rel_fate, axis=(1, 2), xp=xp)  # [release, k]
    produced = produced + made.T @ (p.poly_rel_chain @ p.poly_chain_cell)
    into = entity_sum(j_rel, axis=2, xp=xp)  # [release, class]
    leave = xp.where(p.poly_rel_at_release[:, None] > 0, first * out[:, None], into)
    d_hold = (p.poly_rel_chain @ released)[:, None] * arrival - leave
    return produced - consumed, d_free, d_complexes, produced, consumed, d_hold, *tail


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


def _completion_term(released, mu_chain, rt, p, *, xp):
    """A completion's move, pJ: the product joining its row at mu-bar, or with a release the hold,
    at L mu°_res per molecule (the sheet's §9.5)."""
    term = released * species_sum((p.poly_chain_product * mu_chain).T, xp=xp)
    if releasing(p):
        hold = released * rt * p.poly_chain_length * p.poly_chain_residue_mu_RT
        term = xp.where(_with_release(p, xp=xp) > 0, hold, term)
    return term


def route_heats(n0, dn, d_transit, extents, volume, active, p, rt, *, xp):
    """Each route's heat over the half-step (module docstring, Energy), pJ: (chain [chain],
    degradation [deg], transfer [transfer]), and with a release each fate row's release [release,
    class, fate] (H_rel: -(mu-bar_F - L mu°_res) per molecule), zero at an inactive cell."""
    j_init, j_stage, j_deg, j_tr = extents[:4]
    mu_bar = divided_potential(n0, dn, volume, p, rt, xp=xp)  # [k, cell]
    on = xp.where(active, 1.0, 0.0)
    s_total = entity_sum(j_stage, axis=1, xp=xp)
    released = entity_sum(xp.where(p.poly_chain_last, j_stage, 0.0), axis=1, xp=xp)
    mu_chain = p.poly_chain_cell @ mu_bar.T  # [chain, k]
    chain = -(
        p.poly_chain_r * s_total * species_sum((p.poly_chain_net * mu_chain).T, xp=xp)
        + _completion_term(released, mu_chain, rt, p, xp=xp)
        + rt * p.poly_chain_residue_mu_RT * d_transit
    )
    mu_deg = p.poly_deg_cell @ mu_bar.T
    degradation = -j_deg * (
        p.poly_deg_length * species_sum((p.poly_deg_monomers * mu_deg).T, xp=xp)
        - species_sum((p.poly_deg_polymer * mu_deg).T, xp=xp)
    )
    transfer = -j_tr * species_sum((p.poly_tr_nu * (p.poly_tr_cell @ mu_bar.T)).T, xp=xp)
    heats = (
        xp.where(p.poly_chain_cell @ on > 0, chain, 0.0),
        xp.where(p.poly_deg_cell @ on > 0, degradation, 0.0),
        xp.where(p.poly_tr_cell @ on > 0, transfer, 0.0),
    )
    if len(extents) == 4:
        return heats
    mu_release = p.poly_rel_chain @ mu_chain  # [release, k] at its chain's cell
    mu_fate = xp.transpose(
        species_sum(xp.transpose(p.poly_rel_fate * mu_release[:, None, None, :]), xp=xp)
    )  # [release, class, fate]
    held = rt * (p.poly_rel_chain @ (p.poly_chain_length * p.poly_chain_residue_mu_RT))
    release = -extents[4] * (mu_fate - held[:, None, None])
    on_release = (p.poly_rel_chain @ p.poly_chain_cell) @ on > 0
    return (*heats, xp.where(on_release[:, None, None], release, 0.0))


def poly_half_step(state, controls, h, p, *, xp=jnp, labels=None, volumes=None):
    """(state after h, valid): SSPRK(3,3) on the operator's variables, every move booked. With
    labels (FR-42, D289; static), (state, valid, moves): moves (one_way_moves) from the same
    combination of the stages' one-way fluxes as the booked move. volumes: (cell, outside) pL, the
    view's current volumes where an operator changes them (FR-43 / D315), held over the half-step;
    None reads the declared ones (C1's fallback, today's program)."""
    rows, active = p.poly_rows, p.active
    cell_volume, outside_volume = (p.volume, p.extracellular_volume) if volumes is None else volumes
    volume = xp.where(active, cell_volume, 1.0)
    n0 = xp.where(active[None, :], p.amount_reference[rows] + state.amount_increment[rows], 1.0)
    f0, c0 = state.poly_free_machines_fmol, state.poly_complexes_fmol
    rel = releasing(p)  # Static: the release's variables only where a release is declared.
    hold0 = state.poly_hold_fmol if rel else None
    if rel:
        psi, first = class_weights(controls[4], p, xp=xp)
        weights = (xp.where(p.poly_rel_at_release[:, None] > 0, first, psi), first)
    exp = exporting(p)  # Static: amendment T's variables only where an export is declared.
    n_o0 = volume_o = None
    if exp:  # The listed rows at the exported nodes, [k, node], and the nodes' volumes.
        slots = p.poly_out_slot_hot
        volume_o = slots @ outside_volume
        n_o0 = (
            p.extracellular_amount_reference[rows] + state.extracellular_amount_increment[rows]
        ) @ slots.T

    def move(routes):
        extra = dict(j_exp=routes[-3:]) if exp else {}
        if rel:
            return changes(*routes[:4], p, xp=xp, j_rel=routes[4], weights=weights, **extra)
        return changes(*routes[:4], p, xp=xp, **extra)

    def stage_valid(n, free, complexes, info, hold=None, n_o=None):
        valid = info["ok"]
        valid &= xp.all(xp.where(active[None, :], xp.isfinite(n) & (n > 0), True))
        valid &= xp.all(xp.isfinite(free) & (free >= 0))
        valid &= xp.all(xp.isfinite(complexes) & (complexes >= 0))
        valid &= xp.all(h * info["stage"] <= THETA)
        valid &= xp.all(h * info["lam_pool"] <= THETA)
        valid &= xp.all(xp.where(active[None, :], h * info["used"] <= THETA * n, True))
        if hold is not None:  # The hold, and its exit's stage condition h/tau <= THETA.
            valid &= xp.all(xp.isfinite(hold) & (hold >= 0))
            valid &= xp.all(h * p.poly_rel_rate <= THETA)
        if n_o is not None:  # The exported nodes' rows (§9.17), and their stage condition.
            valid &= xp.all(xp.isfinite(n_o) & (n_o > 0))
            valid &= xp.all(h * info["used_outside"] <= THETA * n_o)
        return valid

    one_way = labels is not None
    nodes = dict(volume_o=volume_o)
    j1, i1 = fluxes(n0, f0, c0, controls, p, volume, xp=xp, hold=hold0, one_way=one_way, n_o=n_o0,
                    **nodes)  # fmt: skip
    d1 = move(j1)
    y2 = (n0 + h * d1[0], f0 + h * d1[1], c0 + h * d1[2])
    hold2 = hold0 + h * d1[5] if rel else None
    n_o2 = n_o0 + h * d1[-3] if exp else None
    j2, i2 = fluxes(*y2, controls, p, volume, xp=xp, hold=hold2, one_way=one_way, n_o=n_o2,
                    **nodes)  # fmt: skip
    d2 = move(j2)
    y3 = (
        n0 + h * (d1[0] + d2[0]) / 4,
        f0 + h * (d1[1] + d2[1]) / 4,
        c0 + h * (d1[2] + d2[2]) / 4,
    )
    hold3 = hold0 + h * (d1[5] + d2[5]) / 4 if rel else None
    n_o3 = n_o0 + h * (d1[-3] + d2[-3]) / 4 if exp else None
    j3, i3 = fluxes(*y3, controls, p, volume, xp=xp, hold=hold3, one_way=one_way, n_o=n_o3,
                    **nodes)  # fmt: skip
    extents = tuple(h * (a + b + 4 * c) / 6 for a, b, c in zip(j1, j2, j3, strict=True))
    dn, d_free, d_complexes, produced, consumed, *d_rest = move(extents)
    d_hold = d_rest[:1] if rel else []
    if exp:
        dn_o, produced_o, consumed_o = d_rest[-3:]
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
    d_transit = entity_sum(
        p.poly_chain_held * d_complexes, axis=1, xp=xp
    )  # dW: j r residues per complex.
    transit = (rt * p.poly_chain_residue_mu_RT * d_transit) @ p.poly_chain_cell
    standard = species_sum(std_terms, xp=xp) + transit
    if rel:  # The hold's standard term, L mu°_res per molecule held (the sheet's §9.5).
        (d_hold,) = d_hold
        on_cell = p.poly_rel_chain @ p.poly_chain_cell  # [release, cell]
        per_held = rt * (p.poly_rel_chain @ (p.poly_chain_length * p.poly_chain_residue_mu_RT))
        held_terms = per_held * entity_sum(d_hold, axis=1, xp=xp)  # [release] pJ
        standard = standard + held_terms @ on_cell
    heat = -(chem + standard)
    magnitude = (
        species_sum(
            adapter.species_chemical_magnitude_pJ(n0, dn, volume[None, :], p.temperature, xp=xp),
            xp=xp,
        )
        + species_sum(xp.abs(std_terms), xp=xp)
        + xp.abs(rt * p.poly_chain_residue_mu_RT * d_transit) @ p.poly_chain_cell
    )
    if rel:
        magnitude = magnitude + xp.abs(held_terms) @ on_cell
    if exp:  # Amendment T (§9.17.2): the exported nodes' exact dG, and where it is booked.
        n_o1 = n_o0 + dn_o
        chem_o = species_sum(
            adapter.species_chemical_free_energy_pJ(
                n_o0, dn_o, volume_o[None, :], p.temperature, xp=xp
            ),
            xp=xp,
        )
        std_o_terms = rt * (p.poly_mu_RT - xp.log(p.poly_c0_mM))[:, None] * dn_o
        std_o = species_sum(std_o_terms, xp=xp)
        forward_x, backward_x, outside_x = extents[-3:]
        export_heat, outside_heat, node_part = export_heats(
            n0, dn, n_o0, dn_o, volume, volume_o, forward_x - backward_x, outside_x, p, rt, xp=xp
        )
        # An export's whole heat is its cell's (its node part by the divided potentials), so
        # each node books only its outside degradations' heat; the totals are each side's exact dG.
        heat = heat - node_part @ p.poly_exp_cell
        heat_o = -(chem_o + std_o) + node_part @ p.poly_exp_node
        magnitude = magnitude + xp.abs(node_part) @ p.poly_exp_cell
        magnitude_o = species_sum(
            adapter.species_chemical_magnitude_pJ(
                n_o0, dn_o, volume_o[None, :], p.temperature, xp=xp
            ),
            xp=xp,
        ) + species_sum(xp.abs(std_o_terms), xp=xp)
    heats = route_heats(n0, dn, d_transit, extents[: 5 if rel else 4], volume, active, p, rt, xp=xp)
    chain_heat, deg_heat, tr_heat = heats[:3]
    full = state.amount_increment.shape[0]
    j_init, j_stage, j_deg, j_tr = extents[:4]
    new = state._replace(
        amount_increment=_set_rows(state.amount_increment, rows,
                                   state.amount_increment[rows] + dn, xp=xp),
        poly_free_machines_fmol=free1,
        poly_complexes_fmol=complexes1,
        poly_initiated_fmol=state.poly_initiated_fmol + j_init,
        poly_stage_exits_fmol=state.poly_stage_exits_fmol + entity_sum(j_stage, axis=1, xp=xp),
        poly_released_fmol=state.poly_released_fmol
        + entity_sum(xp.where(p.poly_chain_last, j_stage, 0.0), axis=1, xp=xp),
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
    if rel:
        hold1 = hold0 + d_hold
        new = new._replace(
            poly_hold_fmol=hold1,
            poly_hold_released_fmol=state.poly_hold_released_fmol + extents[4],
            poly_release_heat_pJ=state.poly_release_heat_pJ + heats[3],
        )
        flowing = flowing | xp.any(extents[4] > 0)
    if exp:
        before_o = state.extracellular_amount_increment[rows]
        delta = dn_o @ p.poly_out_slot_hot  # [k, extracellular slot]
        new = new._replace(
            extracellular_amount_increment=_set_rows(
                state.extracellular_amount_increment,
                rows,
                xp.where(delta != 0, before_o + delta, before_o),
                xp=xp,
            ),
            poly_export_forward_fmol=state.poly_export_forward_fmol + forward_x,
            poly_export_backward_fmol=state.poly_export_backward_fmol + backward_x,
            poly_export_heat_pJ=state.poly_export_heat_pJ + export_heat,
            poly_outside_degraded_fmol=state.poly_outside_degraded_fmol + outside_x,
            poly_outside_degradation_heat_pJ=state.poly_outside_degradation_heat_pJ + outside_heat,
            poly_outside_produced_fmol=state.poly_outside_produced_fmol
            + _on_species(full, rows, produced_o, xp=xp),
            poly_outside_consumed_fmol=state.poly_outside_consumed_fmol
            + _on_species(full, rows, consumed_o, xp=xp),
            poly_outside_dissipated_energy_pJ=state.poly_outside_dissipated_energy_pJ + heat_o,
            poly_outside_standard_energy_pJ=state.poly_outside_standard_energy_pJ + std_o,
            poly_outside_energy_magnitude_pJ=state.poly_outside_energy_magnitude_pJ + magnitude_o,
        )  # fmt: skip
        flowing = flowing | xp.any(forward_x > 0) | xp.any(outside_x != 0)
    selected = type(state)(*(xp.where(flowing, a, b) for a, b in zip(new, state, strict=True)))
    valid = stage_valid(n0, f0, c0, i1, hold0, n_o0) & stage_valid(*y2, i2, hold2, n_o2)
    valid &= stage_valid(*y3, i3, hold3, n_o3)
    if exp:
        valid &= xp.all(xp.isfinite(n_o1) & (n_o1 > 0))
    valid &= xp.all(xp.where(active[None, :], xp.isfinite(n1) & (n1 > 0), True))
    valid &= xp.all(xp.isfinite(free1) & (free1 >= 0))
    valid &= xp.all(xp.isfinite(complexes1) & (complexes1 >= 0))
    if rel:
        valid &= xp.all(xp.isfinite(hold1) & (hold1 >= 0))
    valid &= own_valid(selected, xp=xp)
    if not one_way:
        return selected, valid
    named = (*ONE_WAY_PARTS, *(EXPORT_ONE_WAY_PARTS if exp else ()))
    parts = {k: h * (i1[k] + i2[k] + 4 * i3[k]) / 6 for k in named}
    holds = (hold0, selected.poly_hold_fmol) if rel else None
    out, into, pools = one_way_moves(extents, parts, labels, p, xp=xp, holds=holds)
    live = xp.concatenate((active, p.outside_active & ~p.reservoir)) if exp else active
    on = live[None, :] & flowing  # Nothing moves where the start state is kept.
    out, into = xp.where(on, out, 0.0), xp.where(on[:, None, :], into, 0.0)
    n0p, n1p, intop, outp, (amount, source, destination) = pools
    pools = (n0p, n1p, xp.where(flowing, intop, 0.0), xp.where(flowing, outp, 0.0),
             (xp.where(flowing, amount, 0.0), source, destination))  # fmt: skip
    return selected, valid, (out, into, (), pools)


ONE_WAY_PARTS = ("deg_forward", "deg_backward", "tr_forward", "tr_backward")
EXPORT_ONE_WAY_PARTS = ("odeg_forward", "odeg_backward")  # Amendment T's outside degradations.


def export_heats(n0, dn, n_o0, dn_o, volume, volume_o, net, outside, p, rt, *, xp):
    """Amendment T's heat classes over the half-step (§9.17.2), pJ, by the divided-difference
    potentials of both sides, as every route's (module docstring): (each export's whole heat
    -J_E (mu-bar_F,o - mu-bar_F,c + sum nu mu-bar_c), each outside degradation's
    -J_D (L sum monomers mu-bar_o - mu-bar_F,o), and each export's node part J_E mu-bar_F,o, its
    share of its node's exact dG)."""
    mu_c = p.poly_exp_cell @ divided_potential(n0, dn, volume, p, rt, xp=xp).T  # [export, k]
    mu_bar_o = divided_potential(n_o0, dn_o, volume_o, p, rt, xp=xp)
    mu_o = p.poly_exp_node @ mu_bar_o.T
    node_part = net * species_sum((p.poly_exp_row * mu_o).T, xp=xp)
    cell_part = species_sum(((p.poly_exp_nu - p.poly_exp_row) * mu_c).T, xp=xp)
    export_heat = -(node_part + net * cell_part)
    mu_od = p.poly_odeg_node @ mu_bar_o.T  # [outside, k]
    outside_heat = -outside * (
        p.poly_odeg_length * species_sum((p.poly_odeg_monomers * mu_od).T, xp=xp)
        - species_sum((p.poly_odeg_polymer * mu_od).T, xp=xp)
    )
    return export_heat, outside_heat, node_part


def _by_label(weight, label, node, *, xp):
    """[m, label, node]: over entities c, weight [m, c] at c's label [c, label] and c's node
    [c, node] (one-hot)."""
    labelled = weight[:, :, None] * label[None, :, :]  # [m, c, label]
    return xp.matmul(xp.transpose(labelled, (0, 2, 1)), node)


def one_way_moves(extents, parts, labels, p, *, xp, holds=None):
    """(out [m, cell], into [m, label, cell], pools) of the labelled rows over a half-step (FR-42's
    interface, D289, with D296's sources and pools): each row's one-way consumption, which the share
    owner splits by the row's shares, and its one-way production by label. labels is (rows [m],
    the composite's species indices; arrival [m, label], one-hot, each row's window label; source
    [S, label], one-hot, each chain's label this step, the first chains' rows mine: label_sources).
    - Out: chain draws, forward degradation's polymer (k n), re-synthesis's monomers (k n e^y),
      and each transfer direction's consumed side.
    - Into at the row's window label: chain releases of monomers, forward degradation's monomers,
      re-synthesis's polymer and each transfer direction's produced side. Into at the chain's
      source label: its products, and a release's fate releases where FR-42's labels mark the
      release.
    - Pools, one entry per release (its hold; label_pools): the hold at the half-step's start and
      end; its completions, at the chain's source label where its labels mark the completion and
      at the base otherwise; its losses, the releases it does not carry; and carried, each release
      marked at completion into a labelled fate row, from the hold's site (M N + release) to the
      row's site at the chain's cell (j N + k), keeping the hold's labels. Never also in into.
    Each row's and each hold's change is its into minus out, plus carried in minus carried out,
    at rounding."""
    rows, arrival, source = labels
    j_init, j_stage, j_deg, j_tr = extents[:4]
    s_total = entity_sum(j_stage, axis=1, xp=xp)
    completed = entity_sum(xp.where(p.poly_chain_last, j_stage, 0.0), axis=1, xp=xp)
    r = p.poly_chain_r[:, None]
    chain_in = r * s_total[:, None] * p.poly_chain_releases
    chain_out = r * s_total[:, None] * p.poly_chain_draws
    length = p.poly_deg_length[:, None]
    fwd, bwd = parts["deg_forward"][:, None], parts["deg_backward"][:, None]
    deg_out = fwd * p.poly_deg_polymer + length * bwd * p.poly_deg_monomers
    deg_in = length * fwd * p.poly_deg_monomers + bwd * p.poly_deg_polymer
    made = xp.where(p.poly_tr_nu > 0, p.poly_tr_nu, 0.0)
    taken = xp.where(p.poly_tr_nu < 0, -p.poly_tr_nu, 0.0)
    forward, backward = parts["tr_forward"][:, None], parts["tr_backward"][:, None]
    tr_out, tr_in = forward * taken + backward * made, forward * made + backward * taken
    out = chain_out.T @ p.poly_chain_cell + deg_out.T @ p.poly_deg_cell + tr_out.T @ p.poly_tr_cell
    window = chain_in.T @ p.poly_chain_cell + deg_in.T @ p.poly_deg_cell + tr_in.T @ p.poly_tr_cell
    pick = xp.where(p.poly_rows[None, :] == xp.asarray(rows)[:, None], 1.0, 0.0)  # [m, k]
    exp = exporting(p)
    if exp:  # Amendment T: its coupling's one-way moves at the cells, its node moves after them.
        out, window, carried_e = _export_moves(out, window, extents, parts, pick, p, xp=xp)
    into = arrival[:, :, None] * (pick @ window)[:, None, :]
    width = arrival.shape[1]

    def at_cells(values):  # [m, label, cell] onto the node axis: cells, then outside nodes.
        if not exp:
            return values
        pad = xp.zeros(values.shape[:-1] + (p.outside_active.shape[0],))
        return xp.concatenate((values, pad), axis=-1)

    tag = source[: p.poly_chain_kappa.shape[0]]  # [chain, label]: each chain's label this step.
    products = (pick @ _completed_rows(p, xp=xp).T) * completed[None, :]  # [m, chain]
    into = into + at_cells(_by_label(products, tag, p.poly_chain_cell, xp=xp))
    if not releasing(p):
        none = xp.zeros(0)
        empty = (none, xp.zeros(0, dtype=xp.int64), xp.zeros(0, dtype=xp.int64))
        return (
            pick @ out,
            into,
            (none, none, xp.zeros((0, width)), none, carried_e if exp else empty),
        )
    # The release (one class): each fate f's releases [release, fate] and where they go.
    hold0, hold1 = holds
    released = extents[4][:, 0, :]  # [release, fate]
    cell = p.poly_rel_chain @ p.poly_chain_cell  # [release, cell]
    label = p.poly_rel_chain @ tag  # [release, label]: its chain's label this step.
    marked = p.poly_rel_at_release  # [release]: 1 marked at release, 0 at completion.
    fate = p.poly_rel_fate[:, 0]  # [release, fate, k]
    hit = xp.stack([pick @ fate[:, f, :].T for f in range(len(FATES))], axis=-1)  # [m, r, fate]
    at_release = hit[:, :, 0] * (released[:, 0] * marked)[None, :]
    at_release = at_release + hit[:, :, 1] * (released[:, 1] * marked)[None, :]  # [m, release]
    into = into + at_cells(_by_label(at_release, label, cell, xp=xp))
    # Marked at completion: the hold carries its labels into each labelled fate row.
    labelled = entity_sum(hit, axis=0, xp=xp)  # [release, fate]: 1 where the row is labelled.
    carries = labelled * (1.0 - marked)[:, None]  # [release, fate]
    m, nodes = hit.shape[0], p.active.shape[0] + p.outside_active.shape[0]
    position = entity_sum(xp.arange(m, dtype=float)[:, None, None] * hit, axis=0, xp=xp)
    at = cell @ xp.arange(cell.shape[1], dtype=float)  # [release] its cell's index.
    count = released.shape[0]
    destination = xp.reshape(position * nodes + at[:, None], (-1,)).astype(xp.int64)
    origin = xp.repeat(m * nodes + xp.arange(count, dtype=float), len(FATES)).astype(xp.int64)
    amount = xp.reshape(released * carries, (-1,))
    lost = released[:, 0] * (1.0 - carries[:, 0]) + released[:, 1] * (1.0 - carries[:, 1])
    # Its completions: at the chain's label where they are marked, else at the base.
    base = xp.where(xp.arange(width) == 0, 1.0, 0.0)[None, :]
    known = entity_sum(label, axis=1, xp=xp)[:, None] > 0  # The chain's row is labelled.
    entering = (1.0 - marked)[:, None] * xp.where(known, label, base) + marked[:, None] * base
    arrivals = (p.poly_rel_chain @ completed)[:, None] * entering  # [release, label]
    if exp:  # The exports' transfers join the hold's carried releases (one site space).
        amount = xp.concatenate((amount, carried_e[0]))
        origin = xp.concatenate((origin, carried_e[1]))
        destination = xp.concatenate((destination, carried_e[2]))
    pools = (hold0[:, 0], hold1[:, 0], arrivals, lost, (amount, origin, destination))
    return pick @ out, into, pools


def _export_moves(out, window, extents, parts, pick, p, *, xp):
    """Amendment T's label report (§9.17.4 as erratum H, §9.21 item 3, reads it): (out, window
    [k, cell + outside node], carried). Each export is two one-way transfers of its labelled row,
    the forward part from its cell to its node with the cell's shares and the backward part back
    with the node's (sites j N + node, N the node count, as one_way_moves' carried releases); its
    coupling's rows move at its cell, consumed at its forward or backward part's taken side and
    produced at the other, at the row's window label. Each outside degradation moves its rows at
    its node as a degradation does at its cell: its polymer out by its forward part, back in by
    re-synthesis at the window label, its monomers the other way."""
    forward, backward = extents[-3], extents[-2]
    taken = xp.where(p.poly_exp_nu < 0, -p.poly_exp_nu, 0.0)
    made = xp.where(p.poly_exp_nu > 0, p.poly_exp_nu, 0.0)
    f, b = forward[:, None], backward[:, None]
    out = out + (f * taken + b * made).T @ p.poly_exp_cell
    window = window + (f * made + b * taken).T @ p.poly_exp_cell
    of, ob = parts["odeg_forward"][:, None], parts["odeg_backward"][:, None]
    length = p.poly_odeg_length[:, None]
    gone = (of * p.poly_odeg_polymer + length * ob * p.poly_odeg_monomers).T @ p.poly_odeg_node
    back = (length * of * p.poly_odeg_monomers + ob * p.poly_odeg_polymer).T @ p.poly_odeg_node
    out = xp.concatenate((out, gone @ p.poly_out_slot_hot), axis=1)
    window = xp.concatenate((window, back @ p.poly_out_slot_hot), axis=1)
    cells, slots = p.active.shape[0], p.outside_active.shape[0]
    nodes = cells + slots
    hit = pick @ p.poly_exp_row.T  # [m, export]: 1 where labelled row m is export e's row.
    labelled = entity_sum(hit, axis=0, xp=xp)
    position = entity_sum(xp.arange(hit.shape[0], dtype=float)[:, None] * hit, axis=0, xp=xp)
    at_cell = position * nodes + p.poly_exp_cell @ xp.arange(cells, dtype=float)
    at_node = (
        position * nodes
        + cells
        + (p.poly_exp_node @ p.poly_out_slot_hot) @ xp.arange(slots, dtype=float)
    )
    amount = xp.concatenate((forward * labelled, backward * labelled))
    origin = xp.concatenate((at_cell, at_node)).astype(xp.int64)
    destination = xp.concatenate((at_node, at_cell)).astype(xp.int64)
    return out, window, (amount, origin, destination)


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


def _held(hold, p, *, xp):
    """[pool] the machines a held hold engages."""
    return ((p.poly_rel_held * entity_sum(hold, axis=1, xp=xp)) @ p.poly_rel_chain) @ (
        p.poly_chain_pool
    )


def _hold_terms(row, p, *, xp, magnitude=False):
    """([release] ∫Q of its chain, the hold H, the releases sum ∫Q^f), their absolute values with
    magnitude."""
    size = xp.abs if magnitude else (lambda v: v)
    completed = p.poly_rel_chain @ size(row.poly_released_fmol)
    held = entity_sum(size(row.poly_hold_fmol), axis=1, xp=xp)
    released = entity_sum(size(row.poly_hold_released_fmol), axis=(1, 2), xp=xp)
    return completed, held, released


def _hold_removed(row, p, *, xp, magnitude=False):
    """[release] the holds removed at replacements, H^rem (§9.16), absolute with magnitude."""
    removed = row.poly_rep_hold_removed_fmol
    removed = xp.abs(removed) if magnitude else removed
    return p.poly_rep_release_hot.T @ entity_sum(removed, axis=1, xp=xp)


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
    if state.poly_hold_fmol.shape[0]:  # Static: a release is declared.
        for name in ("poly_hold_fmol", "poly_hold_released_fmol"):
            value = getattr(state, name)
            valid &= xp.all(xp.isfinite(value)) & xp.all(value >= 0)
        valid &= xp.all(xp.isfinite(state.poly_release_heat_pJ))
    if state.poly_export_forward_fmol.shape[0]:  # Static: an export is declared (§9.17).
        for name in EXPORT_STATE:
            value = getattr(state, name)
            valid &= xp.all(xp.isfinite(value))
            if name.endswith("_fmol"):
                valid &= xp.all(value >= 0)
    if state.poly_rep_applied.shape[0]:  # Static: a replacement replaces a slot (§9.16).
        valid &= xp.all(state.poly_rep_applied >= 0)
        for name in REPLACEMENT_STATE:
            value = getattr(state, name)
            valid &= xp.all(xp.isfinite(value))
            if "transfer" not in name and "energy" not in name:  # Signed: extent, mu°_res.
                valid &= xp.all(value >= 0)
    return valid


def poly_domain_valid(state, p, *, xp):
    """Its own fields and its listed rows' amounts (finite and positive at active cells)."""
    valid = own_valid(state, xp=xp)
    if p.poly_chain_present.shape[1]:
        valid &= xp.all(xp.where(p.poly_chain_present, True, state.poly_complexes_fmol == 0))
    if releasing(p):
        valid &= xp.all(xp.where(p.poly_rel_classes, True, state.poly_hold_fmol == 0))
    rows = p.poly_rows
    amounts = p.amount_reference[rows] + state.amount_increment[rows]
    valid &= xp.all(xp.where(p.active[None, :], xp.isfinite(amounts) & (amounts > 0), True))
    if exporting(p):  # §9.17: its listed rows at the exported nodes.
        outside = (
            p.extracellular_amount_reference[rows] + state.extracellular_amount_increment[rows]
        ) @ p.poly_out_slot_hot.T
        valid &= xp.all(xp.isfinite(outside) & (outside > 0))
    return valid


# ------------------------------------------------------------------ the operator


class TemplatedPolymerisation(Operator):
    LAW_ID = LAW_ID
    IDENTITY_ROLE = "author"  # Species registry (D176): it declares the rows it writes.
    # FR-43 part 3: a conversion of its listed rows, which claims its exported and labelled rows
    # alone (sole_rows) and whose shared rows need the registry's potential (FR-43 / D315).
    ROW_MOVES = "conversion"
    SHARED_ROW_POTENTIAL = True
    # FR-42 (D296): its chains are label sources, and its holds label pools (static, by class).
    LABEL_SOURCES = True
    LABEL_POOLS = True
    STEP_ID = STEP_ID
    # Amendment S (§9.16): an event map at replacement@1's events, statically absent (its state
    # unchanged, no validity term) where no event replaces a slot of this operator.
    EVENT = True
    SPLIT = True
    RK4 = "split"
    STATE_AXES = STATE_AXES
    STATE_DTYPES = MappingProxyType({"poly_rep_applied": np.int64})
    # The exported nodes' heat (amendment T; zero-size without an export) is the second.
    HEAT_FIELDS = ("poly_dissipated_energy_pJ", "poly_outside_dissipated_energy_pJ")
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = (*HALF_STEP_CONTROLS, REPLACEMENTS_DUE)
    # B1′: a chain's initiation rate constant and a release's durable fraction p (the sheet's §9.4,
    # source 3), which a rate route may multiply in the half-steps (the scheduled value is the
    # maximum, so a routed p stays in [0, 1]).
    ROUTABLE_CONTROLS = MappingProxyType({INITIATION: "rate", RELEASE_FRACTION: "rate"})
    EXPERIMENT_KEYS = (EXPERIMENT_KEY,)
    # Its own tuple, not species_common's, which turnover and exchange share (FR-43 / D315): the
    # volumes are current reads at the split, as the reactions' are, so where water changes them
    # its concentrations (c_T, its saturations and affinities) and bookings take the view's (C1's
    # fallback without a changer). Water is the one changer admitted
    # (species_reactions.check_volume_changers); the masks' providers and closers stay refused.
    CONFLICTS_VIEW = ("active", "outside_active", "membrane_active")
    VIEW_READS = ("volume", "extracellular_volume")
    SCOPED_READS = {
        "volume": Read("current", "split"),
        "extracellular_volume": Read("current", "split", scoped=True),  # Its exported nodes.
    }
    ENTITY_WRITES = {
        "amount_increment": ("poly_produced_fmol", "poly_consumed_fmol"),
        # Amendment T (§9.17): the exported nodes' rows, booked by its own outside accumulators.
        "extracellular_amount_increment": (
            "poly_outside_produced_fmol",
            "poly_outside_consumed_fmol",
        ),
    }
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
        "poly_hold_fmol": "amount",
        "poly_hold_released_fmol": "cumulative",
        "poly_release_heat_pJ": "cumulative",
        "poly_rep_applied": "cumulative",
        "poly_rep_chains_removed_fmol": "cumulative",
        "poly_rep_residues_removed_fmol": "cumulative",
        "poly_rep_removed_energy_pJ": "cumulative",
        "poly_rep_hold_removed_fmol": "cumulative",
        "poly_rep_chain_birth_fmol": "level",
        "poly_rep_chain_departed_fmol": "level",
        "poly_rep_release_birth_fmol": "level",
        "poly_rep_release_departed_fmol": "level",
        "poly_rep_degradation_birth_fmol": "level",
        "poly_rep_degradation_departed_fmol": "level",
        "poly_rep_transfer_birth_fmol": "level",
        "poly_rep_transfer_departed_fmol": "level",
        "poly_export_forward_fmol": "cumulative",
        "poly_export_backward_fmol": "cumulative",
        "poly_export_heat_pJ": "cumulative",
        "poly_outside_degraded_fmol": "cumulative",
        "poly_outside_degradation_heat_pJ": "cumulative",
        "poly_outside_produced_fmol": "cumulative",
        "poly_outside_consumed_fmol": "cumulative",
        "poly_outside_dissipated_energy_pJ": "cumulative",
        "poly_outside_standard_energy_pJ": "cumulative",
        "poly_outside_energy_magnitude_pJ": "cumulative",
        "poly_rep_export_birth_fmol": "level",
        "poly_rep_export_departed_fmol": "level",
    }
    UNITS = MappingProxyType({"poly_rep_applied": "1"})

    def view_sets(self, spec, declaration):
        """The run view's sets of its axes: pools, chains, stages, degradations and transfers, and
        the releases, their classes and the two fates."""
        depth = max((c.stages for c in declaration.chains), default=0)
        releases = releases_of(declaration)
        classes = max((len(r.fates) for _, r in releases), default=0)
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
            RELEASE_AXIS: {
                "id": RELEASE_AXIS,
                "ids": tuple(r.id for _, r in releases),
                "holds": "release hold",
                "carries": tuple(c.product for c, _ in releases),
                "at": tuple({"cell": c.cell} for c, _ in releases),
            },
            CLASS_AXIS: {
                "id": CLASS_AXIS,
                "ids": tuple(f"class_{k + 1}" for k in range(classes)),
                "holds": "release class",
            },
            FATE_AXIS: {"id": FATE_AXIS, "ids": FATES, "holds": "release fate"},
            EXPORT_AXIS: {
                "id": EXPORT_AXIS,
                "ids": tuple(e.id for e in declaration.exports),
                "holds": "export",
                "carries": tuple(e.row for e in declaration.exports),
                "at": tuple({"cell": e.cell} for e in declaration.exports),
            },
            OUTSIDE_DEGRADATION_AXIS: {
                "id": OUTSIDE_DEGRADATION_AXIS,
                "ids": tuple(d.id for d in declaration.outside_degradations),
                "holds": "outside degradation",
                "carries": tuple(d.polymer for d in declaration.outside_degradations),
                "at": tuple({"outside": d.node} for d in declaration.outside_degradations),
            },
            OUTSIDE_NODE_AXIS: {
                "id": OUTSIDE_NODE_AXIS,
                "ids": exported_nodes(declaration),
                "holds": "exported node",
                "at": tuple({"outside": n} for n in exported_nodes(declaration)),
            },
            EXPORT_PART_AXIS: {"id": EXPORT_PART_AXIS, "ids": EXPORT_PARTS, "holds": "export part"},
            **_replaced_sets(spec, declaration),
        }

    def view_events(self, spec, declaration, schedule):
        """Every scheduled value change of each route, at its cell (the entry at time 0 sets the
        start). It decides no cell's life, so there are no births or retirements."""
        layer = self.VIEW_LAYERS[0]["id"]
        cell = {r.id: r.cell for r in (*declaration.chains, *declaration.degradations,
                                       *declaration.transfers, *declaration.exports)}  # fmt: skip
        for c, r in releases_of(declaration):
            cell |= {r.id: c.cell}
        place = {r: {"cell": c} for r, c in cell.items()}
        place |= {d.id: {"outside": d.node} for d in declaration.outside_degradations}
        events = [
            dict(
                time=float(t),
                kind="polymerisation rate",
                layer=layer,
                at=place[s.route_id],
                label=f"{s.route_id}: {v!r}",
            )
            for s in schedule
            for t, v in s.changes
        ]
        slots = set(replaced_slots(spec, declaration))
        _, replacements = common.replacement_of(spec)
        events += [
            dict(
                time=float(v.time),
                kind="producer departure",
                layer=layer,
                at={"cell": v.slot},
                label=f"{v.slot}: chains in progress and holds leave; newcomer from {v.template}",
            )
            for v in replacements
            if v.slot in slots
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
        """The routes' scheduled values, then each release's durable fraction (its constant, or
        its schedule) and its class, 1: one class since FR-42's shares replaced the class rows
        (D296); the control stays, so that every program keeps its inputs."""
        values = np.array(records, dtype=float).reshape(len(records), -1)[indices]
        nc, nd = len(declaration.chains), len(declaration.degradations)
        nt = len(declaration.transfers)
        ne, no = len(declaration.exports), len(declaration.outside_degradations)
        column = {s.route_id: i for i, s in enumerate(schedule)}
        due = occupant_controls(spec, declaration, values, column, times)
        releases = releases_of(declaration)
        fraction = np.ones((len(values), len(releases)))
        label = np.ones((len(values), len(releases)))
        for i, (_, r) in enumerate(releases):
            if r.durable_fraction is None:
                fraction[:, i] = values[:, column[r.id]]
            else:
                fraction[:, i] = r.durable_fraction
        return (
            values[:, :nc],
            values[:, nc : nc + nd],
            values[:, nc + nd : nc + nd + nt],
            fraction,
            label,
            values[:, nc + nd + nt : nc + nd + nt + ne],  # Amendment T: each export's k_E,
            values[:, nc + nd + nt + ne : nc + nd + nt + ne + no],  # each outside k.
            due,
        )

    def routable_elements(self, declaration, field):
        """B1′, in control order: the initiation rate's elements are the chains, by chain ID, each
        at its pool's cell; the durable fraction's are the releases, by release ID, each at its
        chain's cell (the sheet's §9.4: p = p_max u, u in [b, 1], p_max its constant or scheduled
        value)."""
        if field == RELEASE_FRACTION:
            return tuple((r.id, c.cell) for c, r in releases_of(declaration))
        return tuple((c.id, c.cell) for c in declaration.chains)

    def half_step_rows(self, declaration):
        """((species, cell), ...): every row its own half-steps move, at the cell of the route
        that moves it (B1′, the target side; pump_composite.self_moved_targets): a chain's draws,
        releases and product, or with a release its fate rows; a degradation's polymer and
        monomers; a transfer's rows. A template is read, not moved. A rate route on k_I whose
        source is one of them is evaluated at the half-step's midpoint, second order: before this
        hook such a route was a left-endpoint rule, first order, and silently so."""
        moved = []
        for c in declaration.chains:
            moved += [(row, c.cell) for row in sorted(_written(c))]
        for d in declaration.degradations:
            moved += [(row, d.cell) for row in (d.polymer, *dict(d.monomers))]
        for t in declaration.transfers:
            moved += [(row, t.cell) for row, _ in t.stoichiometry]
        for e in declaration.exports:  # §9.17: its row and its coupling at its cell.
            moved += [(row, e.cell) for row in (e.row, *dict(e.coupling))]
        return tuple(dict.fromkeys(moved))

    def species_identities(self, declaration):
        return declaration.species

    def label_sources(self, declaration):
        """FR-42's sources (D296), one per chain in chain order: (chain ID, the row whose labels
        its new material takes, its cell). The row is its product, or with a release its durable
        fate row, whose labels its short-lived row shares (check_labels)."""
        return tuple(
            (c.id, c.release.fates[0][0] if isinstance(c, ReleasingChain) else c.product, c.cell)
            for c in declaration.chains
        )

    def label_pools(self, declaration):
        """FR-42's pools (D296), one per release in release order: (release ID, its durable fate
        row, whose labels the hold carries, its cell)."""
        return tuple((r.id, r.fates[0][0], c.cell) for c, r in releases_of(declaration))

    def written_rows(self, spec, declaration):
        """Its listed rows at its cells and at its exported rows' nodes, whose writer its half-steps
        are: the registry's row rules read them (species_registry.check_row_writers and
        check_shared_rows; FR-43 / D315, part 3)."""
        cells = dict.fromkeys(
            e.cell
            for e in (*declaration.pools, *declaration.chains, *declaration.degradations,
                      *declaration.transfers, *declaration.exports)
        )  # fmt: skip
        nodes = (*cells, *exported_nodes(declaration))
        return tuple((s.id, node) for s in declaration.species for node in nodes)

    def sole_rows(self, spec, declaration):
        """Its listed rows that keep it as their one writer at every node (single_writer_rows:
        exported rows, outside degradations' monomers and labelled rows; FR-43 / D315, amendment T),
        which the registry refuses a second writer of (check_row_writers, FR-43 part 3)."""
        listed = {s.id for s in declaration.species}
        reason = (
            f"a labelled or exported row, which keeps {LAW_ID} as its one writer (FR-43 / D315; "
            "amendment T)"
        )
        return tuple(
            (name, None, reason) for name in sorted(listed & single_writer_rows(spec, declaration))
        )

    def production_bound(self, spec, declaration):
        """{(species, cell): fmol/s}: the largest rate at which it makes each row (module function
        production_bound; FR-43 / D315), its own schedule's largest rates."""
        (schedule,) = (s for op, d, s in composite_spec.entries(spec) if d is declaration)
        return production_bound(spec, declaration, schedule)

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
        if declaration is None:  # The contract's default: no declaration, no entries.
            return ()
        out = []
        for route, cited in (
            *((d, d.standard_free_energy) for d in declaration.degradations),
            *((t, t.standard_free_energy) for t in declaration.transfers),
            *((d, d.standard_free_energy) for d in declaration.outside_degradations),
        ):
            if cited is None:
                continue
            if isinstance(route, (Degradation, OutsideDegradation)):
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
        of a chain (L draws and releases per residue, one product), or with a release one such
        move into each fate row (the hold is no row: a molecule's move ends at its fate), a
        polymer molecule degraded, a transfer turnover."""
        moves = []
        for c in declaration.chains:
            nu = {}
            for row, count in c.draws:
                nu[row] = nu.get(row, 0) - count * c.residues
            for row, count in c.releases:
                nu[row] = nu.get(row, 0) + count * c.residues
            if isinstance(c, ReleasingChain):
                for fate in c.release.rows():
                    into = nu | {fate: nu.get(fate, 0) + 1}
                    moves.append(
                        (f"chain {c.id} into {fate}", tuple((s, v) for s, v in into.items() if v))
                    )
                continue
            nu[c.product] = nu.get(c.product, 0) + 1
            moves.append((f"chain {c.id}", tuple((s, v) for s, v in nu.items() if v)))
        for d in declaration.degradations:
            nu = {d.polymer: -1}
            for row, count in d.monomers:
                nu[row] = nu.get(row, 0) + count * d.residues
            moves.append((f"degradation {d.id}", tuple(nu.items())))
        for t in declaration.transfers:
            moves.append((f"transfer {t.id}", tuple(t.stoichiometry)))
        for e in declaration.exports:  # §9.17: its row only moves between nodes; its coupling.
            moves.append((f"export {e.id}", tuple(e.coupling)))
        for d in declaration.outside_degradations:
            nu = {d.polymer: -1}
            for row, count in d.monomers:
                nu[row] = nu.get(row, 0) + count * d.residues
            moves.append((f"outside degradation {d.id}", tuple(nu.items())))
        return tuple(moves)

    def read_slots(self, spec, declaration):
        """Door S: its outside reads are at its exported nodes only (amendment T, §9.17)."""
        index = {c.id: i for i, c in enumerate(spec.model.extracellular)}
        return {"extracellular_volume": tuple(index[n] for n in exported_nodes(declaration))}

    def check_definition(self, spec, declaration, schedule, model):
        common.check_species_cap(spec, LAW_ID)
        common.check_identities(spec, LAW_ID, declaration.species)
        check_compartments(spec, declaration)
        species_reactions.check_volume_changers(spec, LAW_ID)
        check_writers(spec, declaration)
        check_occupants(spec, declaration, schedule)
        check_rate_bound(spec, declaration, schedule)
        check_labels(spec, declaration)

    def batch_signature(self, declaration):
        """The static structure; identities, potentials and every rate are not part of it."""
        return (
            LAW_ID,
            tuple(s.id for s in declaration.species),
            tuple(p.cell for p in declaration.pools),
            tuple(
                (c.pool, c.template_copies is None, c.product, c.stages, c.draws, c.releases)
                + ((("release", c.release.fates),) if isinstance(c, ReleasingChain) else ())
                for c in declaration.chains
            ),
            tuple((d.cell, d.polymer, d.monomers) for d in declaration.degradations),
            tuple((t.cell, t.stoichiometry) for t in declaration.transfers),
        ) + (
            (
                (
                    "exports",
                    tuple((e.cell, e.node, e.row, e.coupling) for e in declaration.exports),
                    tuple(
                        (d.node, d.polymer, d.monomers) for d in declaration.outside_degradations
                    ),
                ),
            )
            if declaration.exports
            else ()
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
        routes += sum([2 * len(r.fates) + 1 for _, r in releases_of(d)])  # Its fate rows and hold.
        if replaced_slots(spec, d):  # §9.16's maps and counters, at most a dozen per entity.
            routes += 12 * (len(d.chains) + len(d.degradations) + len(d.transfers)) + 4
        nodes = len(exported_nodes(d))  # §9.17: the exported nodes' rows and their routes.
        routes += 4 * (len(d.exports) + len(d.outside_degradations))
        return (6 * s + 8) * (x.capacity + nodes) + routes * (6 * k + 16)

    def summary(self, spec, declaration, schedule, history):
        releases = {
            r.id: dict(
                chain=c.id,
                machine=r.machine,
                durable_fraction=(
                    f"scheduled under {r.id}" if r.durable_fraction is None
                    else f"constant {r.durable_fraction!r}"
                ),
                label="FR-42's labels mark the "
                + ("release" if r.label is None else r.label.at),
            )
            for c, r in releases_of(declaration)
        }  # fmt: skip
        exports = {
            e.id: dict(
                row=e.row, patch=e.patch, cell=e.cell, node=e.node, coupling=dict(e.coupling)
            )
            for e in declaration.exports
        }
        return {
            **({"polymerisation_releases": releases} if releases else {}),
            **({"polymerisation_exports": exports} if exports else {}),
            **(
                {
                    "polymerisation_replacement": dict(
                        slots=replaced_slots(spec, declaration),
                        templates={t: dict(r) for t, r in declaration.templates},
                        rule="the sheet's §9.16: departing chains and holds removed, counted apart "
                        "from degradation; the newcomer's counters from zero",
                    )
                }
                if replaced_slots(spec, declaration)
                else {}
            ),
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

    def event(self, state, control, p, *, xp, labels=None, view=None):
        """Amendment S's event (poly_event). labels (FR-42's pool reporter, erratum E; static):
        the call then also returns removed [release], the holds it emptied (hold_report), zeros
        without a replacement. view: the reader view the composite passes to a current reader's
        parts where an operator changes the volumes (FR-43 / D315); the event map reads none."""
        state, valid, removed = poly_event(state, control, p, xp=xp)
        if labels is None:
            return state, valid
        if removed is None:  # Statically no replacement: it empties no hold.
            removed = xp.zeros(p.poly_rel_rate.shape[0])
        return state, valid, removed

    def half_step(self, state, h, control, p, *, xp, labels=None, view=None):
        """labels (FR-42, D289, D296; static): (rows, arrival, source); the call then returns
        (state, valid, (out, into, (), pools)), one_way_moves's. view: the reader view the
        composite passes where an operator changes the volumes (FR-43 / D315), whose current
        volumes the half-step takes. Without either, today's call."""
        controls = tuple(getattr(control, name) for name in HALF_STEP_CONTROLS)
        volumes = None if view is None else (view.volume, view.extracellular_volume)
        if labels is None:
            return poly_half_step(state, controls, h, p, xp=xp, volumes=volumes)
        return poly_half_step(state, controls, h, p, xp=xp, labels=labels, volumes=volumes)

    def control_valid(self, control, p, *, xp):
        valid = xp.asarray(True)
        for name in (INITIATION, DEGRADATION, TRANSFER):
            value = getattr(control, name)
            valid &= xp.all(xp.isfinite(value) & (value >= 0))
        if releasing(p):  # p in [0, 1]; psi an integer class of the release.
            fraction, label = getattr(control, RELEASE_FRACTION), getattr(control, RELEASE_CLASS)
            valid &= xp.all(xp.isfinite(fraction) & (fraction >= 0) & (fraction <= 1))
            count = entity_sum(xp.where(p.poly_rel_classes, 1.0, 0.0), axis=1, xp=xp)
            valid &= xp.all((label >= 1) & (label <= count) & (label == xp.floor(label)))
        if exporting(p):  # §9.17: k_E and the outside degradations' k.
            for name in (EXPORT_RATE, OUTSIDE_DEGRADATION):
                value = getattr(control, name)
                valid &= xp.all(xp.isfinite(value) & (value >= 0))
        if replacing(p):  # §9.16: a count of the replacements due.
            due = getattr(control, REPLACEMENTS_DUE)
            valid &= xp.all(xp.isfinite(due) & (due >= 0) & (due == xp.floor(due)))
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
        if exporting(p):  # §9.17: the exported nodes' rows, their standard term and their heat.
            node = (
                row.poly_outside_consumed_fmol - row.poly_outside_produced_fmol
            ) @ p.poly_out_slot_hot  # fmt: skip
            result["outside"] = result["outside"] + node
            result["total"] = result["total"] + entity_sum(node, axis=1, xp=xp)
            result["energy"] = (
                result["energy"]
                + entity_sum(row.poly_outside_standard_energy_pJ, axis=None, xp=xp)
                + entity_sum(row.poly_outside_dissipated_energy_pJ, axis=None, xp=xp)
            )
        return result, self.own_ledgers(row, p, xp=xp)

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        cell = row.poly_produced_fmol + row.poly_consumed_fmol
        magnitudes[0] = magnitudes[0] + cell
        magnitudes[2] = magnitudes[2] + entity_sum(cell, axis=1, xp=xp)
        energy = entity_sum(row.poly_energy_magnitude_pJ, axis=None, xp=xp)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        if exporting(p):  # §9.17: the exported nodes' moves and bookings.
            node = (
                row.poly_outside_produced_fmol + row.poly_outside_consumed_fmol
            ) @ p.poly_out_slot_hot  # fmt: skip
            magnitudes[1] = magnitudes[1] + node
            magnitudes[2] = magnitudes[2] + entity_sum(node, axis=1, xp=xp)
            magnitudes[6] = magnitudes[6] + entity_sum(
                row.poly_outside_energy_magnitude_pJ, axis=None, xp=xp
            )
        return magnitudes

    def own_ledgers(self, row, p, *, xp):
        """The machines per pool (F + engaged - M, a held hold among the engaged) and the
        residues: per chain r ∫S - W - L ∫Q, and after them per release L (H(0) + ∫Q - H -
        sum ∫Q^f), its completed residues held or released (the sheet's §9.7)."""
        engaged = entity_sum(row.poly_complexes_fmol, axis=1, xp=xp) @ p.poly_chain_pool
        transit = entity_sum(p.poly_chain_held * row.poly_complexes_fmol, axis=1, xp=xp)
        if releasing(p):
            engaged = engaged + _held(row.poly_hold_fmol, p, xp=xp)
        machines = row.poly_free_machines_fmol + engaged - p.poly_pool_total_fmol
        residues = (
            p.poly_chain_r * row.poly_stage_exits_fmol
            - transit
            - p.poly_chain_length * row.poly_released_fmol
        )
        if replacing(p):  # §9.16: the residues that left with departed chains, W^rem.
            residues = residues - p.poly_rep_chain_hot.T @ row.poly_rep_residues_removed_fmol
        if releasing(p):
            completed, held, released = _hold_terms(row, p, xp=xp)
            length = p.poly_rel_chain @ p.poly_chain_length
            initial = entity_sum(p.poly_rel_hold0_fmol, axis=1, xp=xp)
            if replacing(p):  # §9.16: the holds that left with departed occupants, H^rem.
                released = released + _hold_removed(row, p, xp=xp)
            hold = length * (initial + completed - held - released)
            residues = xp.concatenate([residues, hold])
        return dict(poly_machines=machines, poly_residues=residues)

    def own_magnitudes(self, row, p, *, xp):
        engaged = entity_sum(xp.abs(row.poly_complexes_fmol), axis=1, xp=xp) @ p.poly_chain_pool
        transit = entity_sum(p.poly_chain_held * xp.abs(row.poly_complexes_fmol), axis=1, xp=xp)
        if releasing(p):
            engaged = engaged + _held(xp.abs(row.poly_hold_fmol), p, xp=xp)
        machines = xp.abs(row.poly_free_machines_fmol) + engaged + p.poly_pool_total_fmol
        residues = (
            p.poly_chain_r * xp.abs(row.poly_stage_exits_fmol)
            + transit
            + p.poly_chain_length * xp.abs(row.poly_released_fmol)
        )
        if replacing(p):
            residues = residues + p.poly_rep_chain_hot.T @ xp.abs(
                row.poly_rep_residues_removed_fmol
            )
        if releasing(p):
            completed, held, released = _hold_terms(row, p, xp=xp, magnitude=True)
            if replacing(p):
                released = released + _hold_removed(row, p, xp=xp, magnitude=True)
            length = p.poly_rel_chain @ p.poly_chain_length
            initial = entity_sum(p.poly_rel_hold0_fmol, axis=1, xp=xp)
            residues = xp.concatenate([residues, length * (initial + completed + held + released)])
        return machines, residues

    def own_bounds(self, magnitudes, steps):
        rounding = first.LEDGER_STEP_ROUNDING * np.finfo(float).eps * steps
        return tuple(FLOOR_FMOL + rounding * m for m in magnitudes)
