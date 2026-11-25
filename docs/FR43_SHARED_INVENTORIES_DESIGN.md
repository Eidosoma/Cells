# FR-43: shared inventories: sparse networks above 16 species, one pool with two writers, and a low-count population on continuous chemistry (design)

**Status: decided by the user, 23 November 2026 (D315).** Part 3's host is B (the composite). The cap
rises to 1,024 species, with today's sum through 16 terms and the scan fold above; the trace budget
is fixed now and the per-entry layout staged after. The accuracy-limited step is reported and a
stiff integrator deferred. One row may have two writers under one registry potential, each with its
own accounts, and both writers read the current volume within FR-43, with a test of both while the
volume changes. §5 records the user's answers in full. Parts 1 and 2 are built on `fr43-part1` and
`fr43-part2`, part 3 by a separate builder. Branch `fr43-design` from main 92e18df4. **S** marks this note's own derivation or
probe. "From memory" marks standard theory cited without being read for this note; it is read and
cited properly when the piece is built. Evidence: `/mnt/workspaces/Cells/fr43-20261123/` (`probe/`
holds the scripts; `out/`, `out/v2/`, `out/v3/`, `out/v4/`, `out/w4rest/` and `out/ops1024/` the
records; `out/NOTES.log` lists every edit to the scripts between runs).

## In short, for the user's review

FR-43 asks for three general features of the composite's shared inventory. This note proposes each,
measures the first, and lists the choices. The user selected B for part 3 so the integer population
and existing operators share finite pools. Section 5 records the answers for the lead.

**Part 1: networks larger than 16 species.** Today a world with a species operator stops at 16
species, ions included. The cap was a precaution about the order of sums, not a physical limit. We
ran FR-43's chain (a reversible chain of neutral species in one cell, with fast and slow steps) at
16, 32, 256 and 1,024 species against its exact matrix-exponential solution:
- every size reached the same accuracy (2 × 10⁻⁵ of the largest amount at a 5 ms step), with
  material, charge and energy books closed to rounding, and the booked heat matched the exact
  free-energy drop;
- the order of sums does not bind: the sums the books rest on agree bit for bit between the host
  and the compiled CPU program at every size, and the others add exact zeros or meet a ledger only
  within its tolerance;
- idleness, restart and batches stay bit for bit above 16 (checked at 32 and 256); every operator
  that shares the cap ran beside idle padding rows at 32 species, and at 1,024 in eight of nine
  worlds (the ninth's long horizon met the runner's storage budget), with every check passing. Only
  the reactions acted on every row; the others' own rows stayed at 1 to 8;
- cost on one CPU core at 1,024 species: 3.5 min to compile (42 s with a looped sum), 0.44 s per
  step, about 87 s per simulated second, 3.9 GiB of memory;
- on the L4 card the answers are the same at every size, to rounding. With the looped sum, 1,024
  species step 4.1 times faster than on one CPU core (0.10 s), but the unrolled sum's run at 1,024
  species was killed at the block's 16 GiB memory cap, most likely while compiling. Compiling
  takes 2.4 to 9 times longer on the card (§1.8);
- fast steps are limited by accuracy, not stability: the step is about 0.1/k_fast. Much faster,
  stiff chemistry would need a new integrator, which is not proposed now.

**Proposal:** raise the cap to 1,024; compile long sums as a loop, so compile time and memory stay
modest (worlds of 16 or fewer species keep their programs exactly); later, store reaction networks
sparsely, which cuts the rate step 4.5 times at 256 species and 45 times at 1,024 in our benchmark.

**Part 2: one pool spent and refilled by two processes.** Today the gene-expression unit refuses any
other writer of its pools. A rule already admits two writers elsewhere: split steps in a declared
order, each booking its own moves and energy. **Proposal:** extend it to the gene unit beside a
reaction network; keep labelled and exported rows single-writer; and take the shared row's standard
potential from the species registry only. We found that today two processes could book one row at
two different potentials when the registry gives none. At changing volume, reactions read the
current volume. Water already counts every row as an osmolyte, so the energy books close if the
reactions book at that volume. A tracer halving its concentration as the volume doubles was checked
with today's water operator. The checks are FR-43's: per-process books, an independent coupled
calculation, and each process alone.

**Part 3. The user chose B for integer units driving continuous chemistry.**
- **A (original recommendation):** a declared hybrid representation in the assembly family. The units run as
  exact events and the pools as continuous equations. It reuses the family's exact events, random
  streams, integrator and pore clock, so event times are located to a declared tolerance. Est.
  5–8 agent-days, after OL6's slice S7. It lifts two of OL6's version-1 refusals for this
  representation only (mixed representations, and checkpoints), and a third (a single lineage's
  checkpoint) unless FR-43's world is a population. A membrane holding both kinds of place would be
  refused. Today's laws express the unit driving the transfer, or the pool driving the assembly,
  but not both in one world, so a small new factor is part of the price.
- **B (selected):** a new integer-population operator in the cell composite, where part 2's pools live. Event
  times are only as accurate as the step, and the composite needs its first random streams and owned
  state through division. Est. 5–8 agent-days.
- In either, a declared rule gives a single unit to one of two daughters with equal probability.

**The request.** FR-43, logged by the user on 23 November 2026 at very high priority, asks for three
general features of the composite's shared inventory. Each is motivated by physics with public
consumers:
1. **Larger sparse reaction networks.** Metabolic networks have hundreds of species, each reaction
   touching a few (Syn3A's metabolism is the roadmap's largest, INNER_MODEL_V4_DESIGN §10.6). Today a
   species operator refuses a world above 16 species, ions included.
2. **One pool spent and replenished by separate processes,** at fixed and at changing volume. Gene
   expression draws on shared nucleotide and amino-acid pools that other chemistry also writes
   (GENE_REGULATION_DESIGN §2.4 named this case and left it for a world with a regenerator).
3. **A low-count integer population coupled to continuous chemistry.** A few channels, transporters
   or machines whose individual on and off states drive a continuous flux, and whose assembly reads
   the flux's pools (FR-13's machines "individually and in aggregate"; FR-40's single ribosome).

**FR-43's acceptance cases** are REQUEST.md's checks, numbered here in its order:

| Case | The check |
| --- | --- |
| C1.1 | A reversible chain of neutral species in one compartment, unequal initial amounts, fast and slow transfers, at 16 rows (the control), 32 and 256, and 1,024 profiled; background ions counted in each size |
| C1.2 | The amount histories against the independent matrix-exponential solution |
| C1.3 | Material, charge and energy accounting |
| C1.4 | At one declared accuracy: compilation time, time per simulated second after compilation, and peak memory, with the device and precision |
| C2.1 | At fixed volume, one operator replenishes a pool from a finite reserve while another spends it; the amount and its standard chemical potential have one authority |
| C2.2 | The shared amount against initial stock plus receipts minus spending, at each saved time |
| C2.3 | Both rates and the amount against an independent coupled calculation |
| C2.4 | Disabling either process recovers the other's standalone result |
| C2.5 | At changing volume: an impermeant tracer with its reactions disabled keeps its amount and halves its concentration when the volume doubles |
| C2.6 | A concentration-dependent reaction against a reference evaluated at the evolving volume |
| C2.7 | The work of changing volume in the energy balance |
| C2.8 (requested in §5) | Both writers act on a shared pool while the volume changes |
| C3.1 | Two free subunits form one active unit that transfers material between two finite pools; disassembly returns both subunits |
| C3.2 | Free subunits plus twice the active count stay constant, and the two pools conserve their total |
| C3.3 | Feedback off, constant rates: the probability of no active unit against the exact two-state solution |
| C3.4 | Feedback on: event times against independently integrated rates, using the same random draws |
| C3.5 | An equal-probability split of one active unit: exactly one recipient per draw, the recipients' inventories summing to the original, and the split frequencies across seeds |
| C3.6 | A same-seed checkpoint and restart reproduces the event trace and the balances |

**Engine models (AGENTS.md).** This note runs none. Its desk probe (§1.2) ran
`resolved_pump_composite@1` over `resolved_pump_tissue@3` with `local_species_reactions@1` (the
chain), with `scheduled_species_turnover@1` (the charged world) and with
`ideal_osmosis_linear_compliance_water@1` (the doubling check, §2.3).

## 0. Summary: the recommendations, and the rulings asked

| # | Question | Recommendation | Who | § |
| --- | --- | --- | --- | --- |
| 1 | How far the cap rises | **To 1,024,** the largest size the request asks for: every size matched the closed form at one accuracy with ledgers at rounding; W4's idleness, restart and batch parts held bitwise at 32 and 256; every cap-sharing operator ran at 32, and at 1,024 in eight of nine worlds; and the cost is measured (1,024 rows: 42 s to compile with the gated fold, 0.43 s per step, 1.7 GiB). The cap is in no traced program, so every world keeps its programs | Lead | 1.7 |
| 2 | Sum order above 16 (limit (a)) | No new order rule. Every sum whose order a ledger, guard or promise rests on is already the explicit fold, bitwise between the host and the compiled CPU program to 1,024. The shared modules' own sums either add exact zeros on the added rows or meet a ledger only at its tolerance. One stated limit: many charged rows (§1.3) | Lead | 1.3 |
| 3 | Compile time (limit (b)) | The unrolled fold costs compile and memory above 256 (1,024 rows: 214 s and 3.9 GiB, against 42 s and 1.7 GiB for a `lax.scan` fold, saves bitwise equal; on the L4 card the unrolled fold's 1,024-row run was killed at 16 GiB of host memory, most likely compiling, and the scan's ran, §1.8). **A static gate:** the unrolled fold up to 16 terms, the scan above, so every world at 16 or fewer keeps its program text and crossrev is the proof. One fold everywhere waits for the next D148 round of reaction programs | Lead | 1.4 |
| 4 | The step (limit (c)) | A reported dt limit, no new integrator in FR-43: the declared accuracy sets dt ≈ 0.1/k_fast in the probe's chain, below the stage condition's refusal at dt·L > 1. A stiff integrator stays D152's door, a separate law | Lead | 1.5 |
| 5 | Dense against per-entry arrays | The dense [rows, route] arrays set the step's cost above 256 (0.43 s per step at 1,024; the rate kernel alone 45 times the per-entry form's). **A per-entry [R, K] layout,** entries in row order so physical fields stay bitwise, as a D148 case-2 change after the raise; not needed for correctness. Meanwhile the trace estimate, which counts the dense layout per step, is corrected (host-side admission only) | Lead | 1.6 |
| 6 | Two writers at fixed volume | Extend the 19 November two-writer rule (exact half-steps, own books, own ΔG, declared order) to the gene unit beside a D152 reaction: SSP half-steps of order three admitted beside exact ones; a registry potential required on the shared row (today's check compares none where the registry gives none); labelled and exported rows keep one writer | Lead | 2.2 |
| 7 | Changing volume | D152's volume door, as composition M3 for reactions: `volume` and `extracellular_volume` read current at the split, C1's fallback keeping every other world's programs; the bookings at the half-step's volume, which water's dilution term already completes, since every row is an osmolyte | Lead | 2.3 |
| 8 | Part 3's host | **B selected.** The integer-population operator shares the composite's finite pools with the existing operators. | **User decision, 23 November** | 3, 5 |
| 9 | Part 3's split of one unit | A new declared token, independent segregation (each unit to the first recipient with probability f), beside S7's `exact_fraction`, whose contract stays untouched | Lead | 3.5 |

## 1. Part 1: networks above 16 species

### 1.1 What the cap is, in code

- `species_common.MAX_SPECIES = 16` (`src/cells/operators/species_common.py`:53) is read only by
  `check_species_cap` (:280), which counts every species of the world, ions included.
- **Eight operators call it at their definition check:** turnover, exchange, reactions, site
  occupancy, the bath schedule, the unit producer, the coupling operator (@1 and @2) and the gene
  unit. @3 alone has no cap. P6's measurements ran @3 at 64–320 species (INNER_MODEL_V4_DESIGN
  §10.6).
- **The refusal's reason** is the W4 probe's: up to 16 species no ledger, guard or promised
  idleness depends on NumPy's pairwise sum order, "a larger world needs another probe" (D165).
- **D165, amended,** makes each raise a D148 change with a guard world at the new size and a cost
  measurement, and says D172's explicit fold removes the need for a new order probe. That holds for
  the sums the fold covers. The shared modules keep their own sums (`numerics/species_sums.py`'s
  docstring), so this note reran W4's parts above 16: its order and host-ledger parts (P3, P5;
  §1.3), its idleness, restart and batch parts (P4, P6, P7; §1.2), and every operator that
  reads the cap at 32 rows (§1.7).

### 1.2 The probe: the chain world at 16, 32, 256 and 1,024 rows (S)

**The world** (`probe/chain_world.py`; synthetic). D150's quiescent species-only world with one 1 pL
cell on its held bath, no finite node, contact or face, so the cell is the one compartment.
- Na, K and Cl are the 3 background rows in every size. The chain is X₁ … X_k, k = rows − 3, one
  moiety. Each link Xᵢ ⇌ Xᵢ₊₁ is a passive `ideal_detailed_balance_mass_action@1` reaction in the
  cell.
- **Fast and slow transfers:** k_f = 20 s⁻¹ on odd links and 0.2 s⁻¹ on even ones, with
  μ°ᵢ/RT a fixed pattern in [−0.5, 0.5], so the reverse constants differ too.
- **Unequal initial amounts:** cᵢ = 1 µM × (1 + (3i mod 7))/4.
- **The reference is closed form:** every link is first order in amounts, so dn/dt = K n with K the
  tridiagonal rate matrix, and n(t) = expm(K t) n(0) (scipy). The probe propagates expm(K dt) over
  every step and checks it against expm(K t) at the observation times (agreement to 3 × 10⁻¹⁴ of
  the largest species).
- **The planted error:** the same reference with one middle link's k_f 0.1% high. The comparison
  must see it.
- **How it ran.** Each size is one process through the runner (`jit`, every host check on every
  row), from a frozen snapshot of this branch at 92e18df4 (clean), with `MAX_SPECIES` raised in that
  process only, as W4 did. Every size ran in one detached benchmark (`cells-fr43-probe-v2`, 16G cap,
  no memory event), each process on CPU 4 under the timed lock in turn, float64 on the CPU (an Intel
  Xeon at 2.20 GHz, recorded in each record). dt = 5 ms, horizon 2 s (400 steps), every step saved.

**The declared accuracy:** the largest error over every saved step and species, over the largest
initial species amount, at most **2 × 10⁻⁵**. It was declared after the 16-row dt study (below):
dt = 5 ms gives 1.63 × 10⁻⁵ there, so the declaration sits 25% above the control's measured error.
The planted error is 9–14 times the declared accuracy at every size.

**Results** (`out/v2/run-*.json`, the unrolled fold, today's; every record status complete; the peak
RSS is the process's, set by the run). Each is a single run: the 16-row world compiled in 16.2 s in
the first queue and 20.4 s in this one, so compile times carry about 25% of run-to-run spread:

| Rows (ions + chain) | Routes | Parse s | Compile s | Execute ms/step | s per simulated s | Host checks s | Peak RSS MiB | Error / largest | Planted / largest | Energy residual (relative) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16 (3 + 13) | 12 | 1.1 | 20.4 | 0.26 | 0.052 | 0.87 | 835 | 1.63e-5 | 2.16e-4 | 4.2e-15 |
| 32 (3 + 29) | 28 | 0.9 | 20.3 | 0.45 | 0.090 | 0.96 | 852 | 1.63e-5 | 2.52e-4 | 4.9e-15 |
| 256 (3 + 253) | 252 | 1.0 | 39.1 | 17.3 | 3.47 | 1.47 | 1,129 | 1.63e-5 | 1.86e-4 | 3.8e-15 |
| 1,024 (3 + 1,021) | 1,020 | 1.8 | 213.9 | 436 | 87.3 | 3.27 | 4,015 | 1.63e-5 | 2.73e-4 | 2.9e-15 |

- **C1.2:** the error is the same at every size, 1.63 × 10⁻⁵, at t = 0.02 s in the fast links'
  transient, and falls to rounding by 0.6 s. The planted link is seen at every size.
- **C1.3:** the material ledgers close to 2.1 × 10⁻¹⁸ fmol at most, and the chain's total drifts by
  at most 1.1 × 10⁻¹⁴ of itself (at 1,024 rows; 4 × 10⁻¹⁶ at 16). Charge is exactly zero, since no
  charged row moves. Energy closes to 3–5 × 10⁻¹⁵ relative, but that is by construction for a
  passive-only network (H = −ΔG, D152 §3.3), so the probe also compares the booked heat with the
  closed form's free-energy drop, F(n₀) − F(n_ref(t)) with F = Σ RT n (ln(n/V) − 1) + μ°′n, at every
  saved step (`probe/heat_check.py`, `out/v2/heat_check.json`). They agree to 2.0 × 10⁻⁵ of the
  drop's scale at every size, worst at 0.01 s in the fast transient, as the amounts do, and to
  1–4 × 10⁻¹² at 2 s; against the engine's own states the heat is the drop to 2 × 10⁻¹³.
- **C1.4:** compile, execute and memory columns above. The 16-row control's error and cost are
  today's engine's; above 16 nothing but the cap changed.

**The dt study at 16 rows** (`out/v2/dt-16-*.json`): the error over the largest species is
1.45 × 10⁻⁴, 1.63 × 10⁻⁵ and 1.93 × 10⁻⁶ at dt = 10, 5 and 2.5 ms, ratios 8.9 and 8.4: third order,
SSPRK(3,3)'s, since @3's step is the identity on these rows and the split adds nothing here.

**W4's idleness, restart and batches above 16** (S, `probe.py w4rest`, `out/w4rest/`; untimed, on gate
lane A; the chain for 40 steps of 5 ms):

| Rows, fold | D136 claim 2: the network at multiplier 0 against none | Restart in process / through a written snapshot | Two worlds batched (k_f × 1 and × 1.5): reversed batch / against the scalar runs |
| --- | --- | --- | --- |
| 32, unrolled | 22 of 22 fields bitwise | bitwise / bitwise | bitwise / 0 (bitwise) |
| 32, scan | 22 of 22 fields bitwise | bitwise / bitwise | bitwise / 0 (bitwise) |
| 256, unrolled | 22 of 22 fields bitwise | bitwise / bitwise | bitwise / 0 (bitwise) |
| 256, scan | 22 of 22 fields bitwise | bitwise / bitwise | bitwise / 0 (bitwise) |

The batches' device diagnostics are at rounding in all four (material 3 × 10⁻¹⁹ fmol, energy
1–4 × 10⁻¹⁵ relative). So W4's P4, P6 and P7 hold above 16 in both folds.

### 1.3 Limit (a): the sum order (S)

D148's promises rest on explicit species order wherever a quantity and its ledger meet (D182). The
question is which sums over the species axis a composite world runs that the fold does not cover,
and whether any promise rests on their order above 16.

**The fold itself** (`out/orders.json`, light CPU, not a timing): `species_sum` on the host equals the
compiled one bitwise at every size from 2 to 1,024 rows, in one column and in 64, with inexact
products formed inside the compiled program and the barrier on. So D182's host-equals-device
property holds at every size probed.

**The other sums,** from an AST scan of the shared modules (`numerics/species_sums.py`'s list and
the law kernel the reactions call), in three classes:

| Class | Sums (module: function) | Order-sensitive above 16? | What they feed |
| --- | --- | --- | --- |
| **Exact zeros on neutral rows** | z- or z²-weighted: `surface_tissue.charge_increment` and its magnitude; `surface_imex.face_laplacian` and `forms_face_laplacian`; `surface_field.solve`'s Σz²W, ΣzW ln and Σz·rates; `surface_pump.explicit_rate_bound` and `moved_charge`. Membrane and junction routes: `surface_transport.transport`'s Σz·flux and Σflux·μ, since a neutral row has no membrane or junction route (`species_common.check_impermeant`) | Only among the charged or permeant rows: a neutral row adds an exact zero, which no order changes. Above 16 the nonzero terms are those rows, not the species count | Field solves, bounds and route readouts; W4's P1 found no ledger among them. @3 calls `charge_increment` and `face_laplacian` directly (`surface_pump_v3.py`:1021, 2450) |
| **Exact zeros off a route's own species** | `laws/reactions/mass_action.reversible_flux`'s Σα ln a and Σβ ln a over the network's rows (axis −2) | Only among a route's reactants or products: at most 3 nonzero terms per side (D152's molecularity cap) | A passive route's net rate, inside the half-step on the device, and the host's readout `observe` |
| **Totals over every row, or over the rows a face or a bath moves** | `numerics/osmotic_water.evaluate` and `edge_exchange`'s osmolyte total; `pump_composite_adapter.chemical_free_energy_pJ`; `surface_field.solve`'s chemical-rate and reservoir-power readouts; `surface_pump.ledger_magnitudes`' and `ledger_limits`' magnitudes; `surface_tissue.balances` (the older families' host ledger; @3 has its own) | Yes: XLA's reduce departs from the fold from 64 rows on the CPU (up to 1,216 ulps of a cancelling random sum), NumPy's single-column sum from 16 in these draws (W4: from 8) | Water's drive and energy rate, beside its ledger's dilution term, which takes the fold; replacement's and injection's bookings, beside @3's ledger, which takes the fold; readout columns; bound magnitudes. Each meets a ledger only at the ledger's tolerance, never bitwise |

**Measured** (`out/orders.json`; `out/v2/charged.json`):
- **Sparse sums** with three nonzero rows give the fold's value exactly under NumPy, XLA and NumPy's
  single column, at every size to 1,024. So the first two classes cannot move at a neutral raise.
- **W4's P3 and P5 above 16, with charged rows past slots 8 and 64:** W4's `cell_charged_9`
  widened, with four more mobile charged rows in the world's last slots (§1.2's script,
  `charged_world`), 20 steps of 1 ms with every host check on every row:

  | Rows | Moving charged rows (slots) | NumPy ≠ fold (rows of 21, ulps) | XLA reduce ≠ fold (rows, ulps) | Fold host = jit | Material, capacitor, global charge ratio, energy (relative) |
  | --- | --- | --- | --- | --- | --- |
  | 16 | 11 (0–2, 4–7, 12–15) | 16, 6 | 0 | Every row | 5.9e-20 fmol, 9.9e-32 C, 2.6e-6, 4.4e-8 |
  | 32 | 11 (… 28–31) | 16, 6 | 0 | Every row | the same |
  | 80 | 11 (… 76–79) | 16, 6 | 11, 2 | Every row | the same |
  | 256 | 11 (… 252–255) | 15, 9 | 11, 2 | Every row | 5.9e-20, 9.9e-32, 1.6e-6, 4.4e-8 |

  So both of the shared sum orders depart from the fold above 64 rows, on the host and the device,
  while every ledger, which takes the fold, passes on every row with residuals that do not grow with
  the species count: W4's finding holds to 256.

**Conclusion.** No ledger, guard or promised idleness rests on a shared module's sum order above 16:
the first two classes are exact at any order for neutral rows and at most a route's molecularity of
terms, and the third meets its ledgers at their tolerances, never bitwise. So the raise needs no new
order rule. **One stated limit:** a world with many *charged* rows puts many nonzero terms into the
z-weighted sums. W4's argument (they feed bounds and field solves only) is independent of the
count, and the charged probe above checks it with 11 moving charged rows; a world with tens of charged
rows reruns that check at its own size.

### 1.4 Limit (b): compile time (S)

`species_sum` is a Python loop, unrolled over S at every call site. The reactions' half-step traced
alone (`out/jaxpr-unrolled.json`) has 1,261 equations at 16 rows, 1,933 at 32, 11,341 at 256 and
43,597 at 1,024; with the fold as a `lax.scan` (`folds.total`'s form, unroll 8) it has 785 at every
size (`out/jaxpr-scan.json`; the scan arm rebinds `species_sum` in 16 loaded modules, and its jaxpr
holds 14 scans, so the arm was live).

**The whole run's compile, both arms** (`out/v2/run-*`):

| Rows | Unrolled: compile s / ms per step / peak RSS MiB | Scan: compile s / ms per step / peak RSS MiB | Saves bitwise equal |
| --- | --- | --- | --- |
| 16 | 20.4 / 0.26 / 835 | 19.7 / 0.25 / 837 | Yes, all 37 fields |
| 32 | 20.3 / 0.45 / 852 | 20.2 / 0.47 / 867 | Yes |
| 256 | 39.1 / 17.3 / 1,129 | 23.1 / 16.4 / 937 | Yes |
| 1,024 | 213.9 / 436 / 4,015 | 42.2 / 431 / 1,738 | Yes |

**What the bitwise result covers, and what it does not.** The two arms' saves are equal in every
field of this one neutral world's forward run, at each size. That is not a D148 proof. D148's first
case failed on the stationary judges' Jacobians, not on forward runs, and a swap changes every
program text. A swap everywhere would need D148 case 2's obligations: G1's 113 worlds, crossrev's
renewal, and the derivative programs the judges take.

**What it buys.** At 1,024 rows the scan fold compiles 5.1 times faster and peaks at 43% of the
memory, with the step's cost unchanged (the dense layout sets it, §1.6). Below 256 the two are within
noise.

**Recommendation: a static gate in the helper.** `species_sum` unrolls up to 16 terms, today's
cap, and folds by `lax.scan` (unroll 8) above. Every world at 16 or fewer species keeps its program
text, so crossrev is the proof (D148 by construction), and the larger worlds get the scan. The order
is one serial left fold either way, and §1.3's host-equals-device and scan-equals-fold checks hold
at every size probed; `tests/unit/test_species_sums.py` gains rows at 17, 256 and 1,024 (no world;
seconds in all).

**The gate's claim, checked** (S, `probe/gate_check.py`, `out/gate_check.json`). It holds only if no
call site folds more than 16 terms in a world at 16 or fewer species, whatever axis it folds. Tracing
crossrev's eleven world sets (tracing only) with `species_sum` wrapped to record each call's
leading-axis length reached 54 call sites; the longest fold had 10 terms, and none had more than 16.
So the gate leaves those worlds' programs as they are, and crossrev at landing is the proof. G1's 113
worlds hold at most 7 species (their saved definitions, counted). The gene unit's folds are over its
own listed rows, at most the world's species, by reading; its worlds are not in crossrev's sets.
**One gap:** @3 alone and the kinds carry no cap, so a recorded world above 16 species can exist
today outside both sets (the mitochondria worlds were not counted here). Under a gate at 16 its
programs would change. At landing, the registered and recorded worlds' species are counted: the
threshold is set above the largest, or each larger world is named as changed under D148. Two code paths in one helper is the price; folding them into one belongs to the
next D148 round that re-proves every reaction program anyway, the per-entry layout's (§1.6), with
G1, crossrev's renewal and the derivative programs.

### 1.5 Limit (c): the step (S)

`local_species_reactions@1`'s half-step is explicit SSPRK(3,3) at one sub-step, refused at
run time where dt·L > 1 at any stage (D152 §4.2, §4.3), L being a species' consumption rate per
amount on unidirectional fluxes. Fast and slow transfers are therefore a stiffness question, and in
this world two limits act:
- **The stage condition** refuses dt·L > 1. For the chain L = max over species of the adjacent
  links' k_f and k_r, 33.2 s⁻¹ at k_fast = 20 s⁻¹ (about 1.66 k_fast), so dt ≤ 30 ms.
- **The declared accuracy** binds first: dt = 5 ms (dt·L = 0.17). With third order, the error at a
  fixed k_fast·dt is the same, so the accuracy-limited step is dt ≈ 0.1/k_fast for this world and
  tolerance, six times below the refusal.
- **Confirmed at a 20-fold faster link** (k_fast = 400 s⁻¹, `out/v2/fast-16-*.json`): dt = 5 ms
  (dt·L = 3.3) is refused at the first step, "no invalid step accepted"; dt = 1 ms (dt·L = 0.66) is
  admitted, with error 1.4 × 10⁻³ of the largest species at the first step, where the planted link
  is invisible. Meeting 2 × 10⁻⁵ there needs dt ≈ 0.25 ms.
- **The cost of a network** is then (steps per simulated second) × (cost per step):
  about 10 k_fast steps per simulated second at this accuracy, times §1.2's per-step cost at its size.
  At k_fast = 20 s⁻¹ that is 200 steps per simulated second.

**The answer for FR-43: a reported dt limit, no new integrator.** A transfer fast against the step
the rest of the world needs (binding, at 10³–10⁴ s⁻¹ beside a 1 ms step) is the stiff door D152 §7.3
names: sub-steps with a splitting that holds its order where C3 found reduction (second order held
to dt·L ≈ 2, then fell towards first), or a positive implicit or linearly implicit half-step. Either
is a separate law, with its own order and positivity probes, and the lead's ruling. At 1,021 species
a dense per-node solve costs O(k³) per stage (about 10⁹ flops), so a stiff integrator at this size
also needs the network's sparsity, which is the next section's question.

### 1.6 Dense arrays against a per-entry form (S)

`species_reactions.Network` holds α, β, ν, the catalysis and the consumption as dense
[rows, route] arrays, and the rate kernel forms [rows, route] products at every stage. A chain of k
species has about k routes, so every stage is O(k²) in work and memory, against O(R·K) for a per-entry
form like the assembly kernel's [R, K] View (K = 6 entries per step).

**The rate evaluation alone** (`out/v4/rates.json`, CPU 4 under the timed lock): the chain's forward
and reverse log terms at one node, as `route_rates` forms them, every array an argument as the engine
binds its layout, placed on the device once before timing. (An earlier record, `out/v2/rates.json`,
passed host arrays on every call and so timed their copies too: 88 times at 1,024. It is kept and
superseded.)

| Rows | Dense: µs per call / temporaries | Per entry: µs per call / temporaries | Ratio | Values bitwise equal |
| --- | --- | --- | --- | --- |
| 16 | 16 / 2.6 kB | 17 / 1.7 kB | 0.9 | Yes |
| 32 | 29 / 13 kB | 30 / 4.0 kB | 1.0 | Yes |
| 256 | 237 / 1.0 MB | 53 / 36 kB | 4.5 | Yes |
| 1,024 | 5,898 / 16.7 MB | 131 / 147 kB | 45 | Yes |

**In the runs** (§1.2) the step's cost grows about quadratically above 32 rows: 0.45 ms at 32,
17.3 ms at 256 (38 times for 8 times the rows) and 436 ms at 1,024 (25 times for 4 times), in
both folds alike. At 1,024 rows that is 87 s per simulated second at the declared accuracy.

**Beyond 1,024, a profile** (`out/v3/`, the scan fold, 40 steps of 5 ms, the two sizes run at once on
CPUs 4 and 5, so not comparable with §1.2's single runs):

| Rows | Compile s | s per step | s per simulated s | Peak RSS GiB | Error / largest | Planted / largest |
| --- | --- | --- | --- | --- | --- | --- |
| 2,048 | 100.7 | 1.77 | 354 | 4.3 | 1.63e-5 | 1.58e-4 |
| 4,096 | 276.6 | 10.2 | 2,038 | 14.5 | 1.63e-5 | 3.30e-4 |

The answers stay at the declared accuracy, and the dense layout's cost (time and memory, about k²)
is what grows.

**The trace budget.** The runner's definition-time estimate (`execution/resources.trace_bytes`)
counts the reactions' `working_size` per saved step, and that includes count × (6k + 16) words, the
dense layout. At 256 rows it estimates 9.5 GiB for 400 steps, refused under the fixtures' 2 GiB
budget, against a measured peak of 1.1 GiB; at 1,024 rows it estimates 153 GiB, against a measured
3.9 GiB. The probe raised the definition's `max_trace_bytes` and recorded the estimate. The estimate
is host-side admission, not a program, so correcting it (the layout counted once, not per step)
changes no program. The vector-window batches read the same per-world estimate when they plan their
memory (`execution/vector_windows.py`), so the correction also changes which batches are admitted
under a `max_working_bytes`.

**Recommendation: a per-entry layout, after the raise.** The network's arrays become [R, K] entries
(K = 6, the molecularity cap on each side), each route's entries in row order, the rates folded over
K and scattered to [rows, node] in route order. The aim is that the nonzero terms and their order
stay the dense form's, so physical fields stay bitwise. That is shown here only for the chain's rate
kernel (the table above); for every reaction world it is the change's D148 case-2 obligation (G1's
reaction worlds, crossrev's renewal, the derivative programs), not a new ID.
It also makes the trace estimate per-entry and is the sparsity a stiff per-node solve would need
(§1.5). Est. 2–3 agent-days plus the G1 run. It is speed, not correctness: the raise does not wait
for it.

### 1.7 What lands for part 1, and its acceptance

**The proposal** (est. 0.5–1 agent-day; `species_common` is in FR-15's charged-junction build's
reach, so it lands after that build or with its owner's leave):
1. `MAX_SPECIES` 16 → 1,024, as a D148 change, with the refusal's reason rewritten to this probe. The
   cap is read only at definition (`check_species_cap`), so no program changes: crossrev identical.
2. `species_sum`'s static gate above 16 (§1.4): worlds at 16 or fewer keep their programs.
3. The trace estimate: `species_reactions.working_size` counts the dense layout once, not per saved
   step (host-side admission, no program; today it refuses 256 rows at 400 steps under a 2 GiB
   budget that 1.1 GiB fits).
4. **Tests** (D224's costs stated at landing): the 32-row chain against its closed form, amounts
   and booked heat, with the planted link, as one row of the existing `test_species_cap_runs.py`
   (about 20 s, nearly all compile; tier 2); the refusal test at 1,025 rows (parse only, about
   2 s); the 1,024-row world for 20 steps as a tier-3 guard (about 1 min with the gate). The 256 and
   1,024 records above stay a detached benchmark, rerun at each later raise, never tier tests.
5. **Docs:** D150 §2.6 and §11.5, D152 §7.2 and its refusal lists, the operators' docstrings and
   FR-9's entry.

**Every operator that reads the cap ran at 32 rows** (S, `probe/ops32.py`, `out/ops32.json`): one
existing world of each, crossrev's acceptance worlds or the operator's fixture, padded with idle
neutral rows to 32 species, through the runner with every host check on every row. All nine ran to
their horizons:

| World (operators) | Species before | Rows run | Material residual (fmol) | Energy residual (relative) |
| --- | --- | --- | --- | --- |
| FR-1 load and degrade (owned compartment, exchange, turnover) | 4 | 6 | 0 | 5.3e-16 |
| FR-1 load and react (owned compartment, exchange, reactions) | 5 | 6 | 0 | 9.2e-16 |
| FR-3 q5 inward (site occupancy) | 4 | 6 | 3.2e-27 | 6.4e-16 |
| FR-3 q5 class switch (site occupancy, scheduled) | 4 | 20,001 | 4.2e-22 | 9.6e-14 |
| FR-10 ion world (bath schedule) | 4 | 2,001 | 0 | 1.7e-5 |
| FR-10 ledger world (bath schedule, RK4) | 4 | 61 | 0 | 5.9e-16 |
| FR-6 A5″ (coupling, turnover) | 4 | 2,001 | 5.5e-15 | 1.5e-5 |
| FR-7 Kir world (unit producer) | 5 | 31 | 2.2e-19 | 9.8e-6 |
| Gene unit, polymerase-limited at 10 copies, 20 steps | 8 | 21 | 5.2e-26 | 8.8e-15 |

The 10⁻⁵ energy residuals are the moving-ion worlds' own IMEX accuracy, inside their bounds as every
row passed. **At 1,024 rows** (`probe/ops_rows.py`, `out/ops1024/`; the scan fold, on gate lane A),
eight of the nine ran to their horizons with every host check on every row and the same residuals as
at 32 (the added rows are idle). The ninth, FR-3's class switch (20,001 steps), was refused at its
definition by the runner's trace budget, whose estimate grows with species times saved steps: long
horizons at this size need the windowed runners or a raised budget, a definition's choice. Site
occupancy itself ran at 1,024 in q5 inward.

**What the raise does not claim.** The operator runs padded each world with idle rows: each operator
acted on its own 1 to 8 rows only. Only the reactions acted on every row (the chain), and the charged
world ran in the unrolled fold only. Worlds above 16 stay outside D150's and MG0c's judged scope until a
protocol covers them, and integration grants no acceptance. The cost at 1,024 is one chain in one
cell; a world with many nodes adds @3's per-species work (INNER_MODEL_V4_DESIGN §10.6's P6: about
1 s per step for 160 species on the 825-node world).

### 1.8 The L4 column (S)

**How it ran.** One detached block (`probe/gpu_block.sh`, unit `cells-fr43-gpu`, 16 GiB of host
memory, 90 min, the first 30 of them a wait before the block began; the lead launched it at
13:36:47).
It set the `gpu.reserved` flag at 14:06:47, held `gpu.lock` exclusively, and removed the flag at
14:48:22. It ran the same frozen snapshot (92e18df4, `MAX_SPECIES` raised in process) in float64 on
the NVIDIA L4 (`cuda:0`, JAX 0.11.1), one process per run as on the CPU: 400 steps of 5 ms, every
host check on every row (`out/gpu/`, `out/gpu/l4_column.json`). The host thread ran on CPU 6, which
other agents' jobs shared (45 processes on CPUs 6 and 22 at the start, `out/gpu/cpu6_at_start.txt`),
so compile and host times are contended. The CPU's values (in parentheses) are §1.2's and §1.4's,
uncontended.

| Rows, fold | Outcome | Compile s | ms per step | s per simulated s | Host peak RSS MiB | Card peak MiB | Error / largest | Saves against the CPU's |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16, unrolled | complete | 49.7 (20.4) | 1.29 (0.26) | 0.26 | 1,091 | 80 | 1.63e-5 | 29 of 37 fields bitwise, the other 8 within 4 × 10⁻¹⁶ relative |
| 256, unrolled | complete | 352 (39.1) | 5.6 (17.3) | 1.12 | 2,865 | 100 | 1.63e-5 | 29 of 37 bitwise, the other 8 within 1.3 × 10⁻¹⁵ |
| 256, scan | complete | 98.2 (23.1) | 24.0 (16.4) | 4.81 | 1,408 | 100 | 1.63e-5 | the same; and the scan's saves equal the unrolled's on the card bitwise (37 of 37) |
| 1,024, unrolled | **killed by the out-of-memory killer at the unit's 16 GiB cap**, 14 min 19 s into the run (exit 137; the unit's cgroup: one OOM kill, peak 16.00 GiB); no record | – | – | – | – | – | – | – |
| 1,024, scan | complete | 377 (42.2) | 105 (431) | 20.9 | 2,848 | 125 | 1.63e-5 | 29 of 37 bitwise, the other 8 within 1.3 × 10⁻¹⁵ |
| 4,096, scan | not run: the block ran it only if 1,024 rows' scan stepped in under 50 ms on the card | – | – | – | – | – | – | – |

- **The answers are the card's too.** The error is 1.63 × 10⁻⁵ of the largest species at every size,
  agreeing with the CPU's to 11 digits, and the planted link is seen at every size. The material
  ledgers close to 2.1 × 10⁻¹⁸ fmol and energy to 3.4–4.6 × 10⁻¹⁵ relative.
- **The card's saves are not the CPU's bit for bit.** The 8 fields that differ are the chain's
  amounts and their increments, and the reactions' accumulators and energies, all within
  1.3 × 10⁻¹⁵ relative. Their terms come through the rate kernel's exponentials and logarithms,
  whose device implementations are not the host's. The fold's host-equals-device property (D182) is
  for bitwise-equal terms, and every ledger closes on the card.
- **The unrolled fold's 1,024-row run did not fit in 16 GiB of host memory on the card,** against
  a 3.9 GiB peak on the CPU. Its record was never written, so the phase is not recorded. A run holds
  little else on the host (the scan's 1,024-row run peaked at 2.8 GiB there and 125 MiB on the
  card), so the compile is the likely cause. The scan's compile took 377 s. So the gate above 16
  terms is also what lets the large worlds run on the card.
- **The scan is slower per step on the card at 256 rows:** 24.0 ms against the unrolled form's 5.6
  (on the CPU, 16.4 against 17.3). It compiles 3.6 times faster (98 s against 352). Above 256 the
  unrolled form's compile is the limit. The scan's `unroll` (8) changes the compiled loop but never
  the additions, so a larger unroll on the card is a measured option, not this build's.
- **Per step, 1,024 rows on the card cost 105 ms,** 4.1 times faster than one CPU core, or 21 s per
  simulated second at the declared accuracy.

**The rate kernel on the card** (`out/gpu/rates.json`; as §1.6's, every array placed on the device
once, values bitwise equal between the forms at every size):

| Rows | Dense: µs per call / temporaries | Per entry: µs per call / temporaries | Ratio | Dense compile s |
| --- | --- | --- | --- | --- |
| 16 | 181 / 2.8 kB | 271 / 1.6 kB | 0.67 | 0.4 |
| 32 | 197 / 13 kB | 183 / 3.1 kB | 1.08 | 0.4 |
| 256 | 462 / 1.0 MB | 405 / 25 kB | 1.14 | 3.8 |
| 1,024 | 227 / 16.7 MB | 233 / 98 kB | 0.97 | 28.9 |
| 4,096 | 3,560 / 268 MB | 333 / 0.39 MB | 10.7 | 527 |

Up to 1,024 rows a call costs 0.2–0.5 ms on the card whatever the layout: the launch, not the
arithmetic. The dense layout's square shows only above that. The per-entry form's compile stays
under 0.7 s at every size. So §1.6's recommendation stands, and on the card it matters above
1,024 rows.

## 2. Part 2: one pool, two processes

### 2.1 Where the engine stands

- **The gene unit refuses any other writer of its listed rows** (`templated_polymerisation.check_writers`,
  `src/cells/operators/templated_polymerisation.py`:1344): a D152 reaction that writes one, another
  author's declaration of one, and an in-step mover. Its reasons (GENE_REGULATION_DESIGN §7.5): one
  account for the nucleotide loop, and no new two-writer ruling for A's worlds, which declare no
  regenerator.
- **D152 keeps one local-kinetics writer per (species, node)** (its §1.1): it refuses turnover on a
  row it writes, because splitting one network's reactions between operators splits their coupling at
  an unmeasured O(dt²). Its §7.3 door: "a measured splitting between turnover and the network, if a
  consumer needs it".
- **A two-writer rule exists** (the lead, 19 November 2026; `population_unit_turnover.py`:18–22):
  two writers of one row are admitted when each is a split part with exact half-steps in declared
  order, books its own moved amounts and the exact ΔG of its own move from the state its half-step
  receives, and refuses a non-positive amount. Strang splitting, second order. GENE_REGULATION_DESIGN
  §2.4 says it "would need extending" to a D152 network beside the gene unit, "with a measured
  splitting check".
- **The contract to extend** is `tests/unit/test_species_reactions_same_material.py`: exchange and
  reactions write one row S, and the run equals the composed map E(dt/2) R(dt/2) I(dt) R(dt/2)
  E(dt/2) at rounding (1e-13), the other order is far off, and the composition converges at second
  order (ratio 3.6–4.4) to the coupled system's exact solution.

### 2.2 At fixed volume

**The rule (the 19 November rule, extended).** A row may have two writers among the gene unit
(`templated_polymerisation@1`) and a D152 network (`local_species_reactions@1`) when:
1. each writer is a split part whose half-steps are in the declared order, book their own moved
   amounts in their own accumulators (`ENTITY_WRITES`) and the exact ΔG of their own move from the
   state the half-step receives, and refuse a non-positive amount. Both already do: D152's SSPRK(3,3)
   with its stage condition, and the gene unit's, which is D152's. Neither is exact, so the rule's
   "exact half-steps" becomes "exact or SSP half-steps of order three or more"; the composition stays
   second order;
2. the row is neither labelled (FR-42's shares) nor exported (FR-38's amendment T). Those keep one
   writer: a second writer would have to report one-way moves to the label owner and to the
   per-producer counters, which no stage plans. Extending label accounting is out of FR-43's scope;
3. **the row's standard potential has one authority: the species registry.** Both operators declare
   `standard_mu_RT` for their species, and `check_potentials` compares each with the registry's. But
   it compares none where the registry gives no potential (`species_registry.py`:657–659), so two
   writers could book one row at two values. A row two operators write is therefore refused unless
   the registry declares its potential. The amount's authority is @3, which owns the row; each writer
   books its own moves;
4. the declared operator order is the split's palindrome, as today.

**What refuses next, lifted in process** (S, `probe/part2_parse.py`, `out/part2_parse.json`; host-only
parses of `polymerase_limited(10)` with a D152 first-order sink of N, the source untouched):
- as is, `check_writers`' D152 branch refuses ("a local_species_reactions@1 reaction writes 'N'");
- with that branch skipped, its author branch refuses ("local_species_reactions@1 also declares
  'N'"): the network is an identity author of the rows it lists, so the rule must admit it in both
  branches;
- with both skipped, the pair parses, and a 10-step run (0.5 s steps) passes every host check
  (material 4 × 10⁻¹⁹ fmol, energy 2 × 10⁻¹⁶ relative, the gene unit's machine and residue ledgers
  at 5 × 10⁻²³ and 5 × 10⁻²²);
- **the potential gap is real:** with the registry's potential of N in place, the network's N
  declared 0.1 RT off is refused by `check_potentials`; with the registry's potential removed, the
  same 0.1 RT disagreement between the two writers is admitted.

**What changes in code** (est. 1–1.5 agent-days, the gene-regulation lane's files and one registry
function):
- the gene unit's `check_writers` admits a D152 network that writes or declares a listed row (both
  of its branches) under items 2–3, and keeps refusing other authors (turnover, exchange) and
  in-step movers;
- the registry gains the shared-row rule of item 3, one function that every operator with writers
  calls, so no pairwise check is added (D176);
- D152's `check_turnover_rows` is untouched (turnover beside a reaction stays refused unless a
  consumer asks).
- **D148:** worlds without a second writer keep their programs; every newly admitted composition is
  a new definition (D143), refused today. Crossrev stays identical.

**The checks, as tests** (one compiled world family; the costs stated at landing, D224):

| Case | Test | Tolerance's origin |
| --- | --- | --- |
| C2.1 | A gene unit (polymerase-limited, the A1-M world) whose recharging replenishes N from the finite M and ATP reserves, beside a D152 mass-action sink of N (the second spender); and the mirror, a D152 source X → N spending a finite X while transcription spends N. The registry declares N's potential; without it the parse refuses | – |
| C2.2 | n_N(t) = n_N(0) + Σ_writers (produced − consumed) at every saved row, per writer | Rounding: each writer's accumulators against @3's ledger, the ledger's own bound |
| C2.3 | Both writers' rates and n_N against the independent coupled calculation (§4), at dt and dt/2 | The split's second order: ratio 3.6–4.4, and the finer error under a bound fixed from the coarse one before the run |
| C2.4 | Either writer at zero rate against the other alone: bitwise. D152's claim 2 and the gene unit's "zero rates are bitwise idle" both select the start state | Bitwise |
| Plants | One writer's booked consumption 10⁻³ high in a copy of the run's records: C2.2 must fail. The reference with the D152 rate constant 1% high: C2.3 must fail at the finer dt | – |

The same-material test's composed-map check is extended by one row: the gene unit's half-step map
beside the reactions', which pins the order the split uses.

### 2.3 At changing volume

**This is composition M3 (D301) with reactions in place of turnover,** and D152's door "Volume (water,
the lumen): `VIEW_READS` with D150's fallback; bookings at the view through water's endpoint free
energy". D301's inventory (`/mnt/workspaces/Cells/arch-inventories-20261122/INVENTORIES.md`, part A,
row 2) prices M3 for turnover at 2–2.5 agent-days of declared reads only, class (i), with no new state;
reactions differ in reading the volume for their rates as well as their bookings.

**Today** `local_species_reactions@1` lists `volume` and `extracellular_volume` in `CONFLICTS_VIEW`
(`species_reactions.py`:1433), so water (`VIEW_FIELDS`) is refused at parse
(`test_species_reactions_refusals.py`'s water fixture).

**The change** (composition option A's general rule, D191; M1's rules C1–C4 are on main):
- the two fields move from `CONFLICTS_VIEW` to `VIEW_READS`, with
  `SCOPED_READS = Read("current", "split")` for each, as exchange reads `membrane_area`;
- the half-step takes the view's volumes for its concentrations, its rates, its stage condition and
  its bookings (`network`, `route_rates`, `divided_potential`, `adapter.species_chemical_free_energy_pJ`),
  and `observe` and `stage_report` take the row's;
- **C1's fallback:** where no operator changes a volume, the part receives no view and its program is
  today's, bit for bit. So every existing world keeps its program (D148 by construction; crossrev
  identical), and the law ID stays, as composition option A ruled;
- `active`, `outside_active` and the outside anchors stay in `CONFLICTS_VIEW`: closers stay refused.
- **Lifted in process** (`out/part2_parse.json`): with the two fields moved to current reads, the
  water fixture's pair (a heredity cell, water, and a D152 source of S) parses with no further
  refusal. What remains is the program: the half-step taking the view, which no probe exercised.

**Which volume each half-step reads.** The current one at its own stage (the composition note's §6):
a first-half reader sees earlier split changers after their first half; the second halves see the
inner step's result and the later operators' second halves. Within its half-step the reactions hold
that volume fixed, and water holds the amounts fixed in its Heun half-step. Each is then an exact or
second-order flow of its own variables, and the palindrome is **second order for the coupled system**
(S). So C2.6's tolerance comes from that order: the error against the reference at dt and dt/2 with
ratio 3.6–4.4, and the finer error under a bound fixed from the coarse one before the run. A lagged
(step-start) read would be first order; today's fixed read is an O(1) modelling error.

**Does a reacting row count in water's osmotic term? Yes, every row does.** Water's `amounts` is
`physical_amounts` over every species row (`operators/osmotic_water.py`:108). The osmotic pressure
sums them all (`numerics/osmotic_water.py`:131, 204), and so does the dilution term of water's ledger
and its node free energy (`operators/osmotic_water.py`:275, 315). So a reacting row's dilution has its
booked counterpart, and the ledger closes, **provided the reactions book at the half-step's volume:**
- with F(N, V) = Σ RT nₛ(ln(nₛ/V) − 1) + μ°′nₛ, the composite's endpoint free energy is @3's chemical
  term at V₀ plus water's dilution term −RT N_tot ln(V/V₀), which is F(N, V) (S);
- a reaction half-step at fixed V changes it by F(N′, V) − F(N, V), exactly what it books at the
  view's V; water's half-step at fixed N changes it by −RT N_tot ln(V′/V), which water books;
- booked at V₀ instead, each reaction half-step would miss −RT ΔN_tot ln(V/V₀) wherever Σν ≠ 0, the
  turnover probe's 4.8 × 10⁻⁷ pJ per 0.01 fmol (OPERATOR_COMPOSITION_DESIGN §3).

**A doubling is reachable with water alone** (S, `probe/doubling.py`, `out/doubling.json`): one
quiescent 1 pL cell with an impermeant neutral tracer at 1 µM, its held bath at 0.4 of the cell's
osmolarity, no modulus, maximum volume 3 V₀ (above the water fixture's cited 2 V₀ validity bound: a
synthetic world). V crosses 2 V₀ at t = 16.11 s. The tracer's amount is bitwise constant on all 4,001
rows, c·V equals n₀ to 2 × 10⁻¹⁶, and its concentration at the crossing is 0.49999 of the initial.
Every host check passed (energy residual 1.1 × 10⁻⁷ relative, water's Heun step).

**The checks:**

| Case | Test | Tolerance's origin |
| --- | --- | --- |
| C2.5 | The doubling world with the network declared and every multiplier zero: the tracer's amount bitwise constant, and its concentration n₀/V(t) at every row, halved where V crosses 2 V₀ | Bitwise and rounding |
| C2.6 | A second-order reaction A + B → C (Σν ≠ 0, so the reaction also changes the osmolarity and with it the volume) in the swelling cell, against the reference integrating n and V together at the evolving volume, at dt and dt/2 | Second order, as above |
| C2.7 | The energy ledger closes on every row with water's dilution, elastic, heat and bath-work terms and the reactions' bookings; plus an endpoint check: F(N_t, V_t) + U(V_t) − F(N₀, V₀) − U(V₀) equals the booked work (the reactions' and the bath's water work) less the booked heat (the reactions' and water's), to the ledger's bound | The ledger's own bound |
| C2.8 (requested in §5) | Both writers use the evolving volume. Compare the shared amount, both rates and energy with a coupled reference. Using initial volume for one active writer must fail. | Step-halving against the reference and the ledger's own bound |
| Plant | The reactions booking at V₀ (the declared volume) in the same world: C2.7's endpoint check must fail by the missed −RT ΔN ln(V/V₀) | – |

**Two writers at changing volume.** "Repeat with changing volume" for part 2's two processes needs
both writers to read the current volume. The gene unit reads concentrations too (c_T, its
saturations, its affinities) and lists the same view conflicts (`common.CONFLICTS_VIEW`), so it needs
the same current read and bookings at the view, in its own files: est. 1–1.5 agent-days beside the
reactions' 1.5–2. The lead may stage it: reactions beside water first (C2.5–C2.7), then the pair.

### 2.4 Owners and order

- The gene unit's files are the gene-regulation lane's; FR-38's amendment T and FR-42's label work are
  in flight there, so part 2's fixed-volume change follows their landing, or is merged into that lane.
- `species_reactions.py` and the registry function are the operators owner's.
- The references (§4) are written by a code-blind agent from §4's list.

### 2.5 The gene unit beside the unit producer (a user's review, 23 November 2026)

**The question.** `templated_polymerisation@1` (the gene unit) and `population_unit_turnover@1` (the
unit producer) each refused the other as a writer of one row. Is there a supported contract for one
of them adding a neutral stock and the other consuming it, with final = initial + input −
consumption, also after a restart?

**Supported (part 2A, D315).** Yes, under the two-writer rule of 19 November 2026 as part 2 extends
it (§2.2):
- Each writer is a split part in declared order: the gene unit's SSP half-steps of order three, the
  producer's exact chain. Each books its own moves (the gene unit's `poly_produced_fmol` and
  `poly_consumed_fmol`, the producer's `unit_consumed_fmol`) and their exact ΔG. So the stock's
  amount is its start plus the gene unit's net books less the producer's consumption, at every
  saved row, and a restart resumes every account with the state.
- The shared row's standard potential comes from the species registry.
  `species_registry.check_shared_rows` refuses a shared row without one.
- Labelled rows (FR-42) and exported rows (amendment T) keep the gene unit as their one writer.
  D152 beside the producer on a precursor stays refused (D152's one local writer).
- **The producer's R5 bound** (the largest units its population can reach, which @3's checks read)
  now counts every producer of the precursor. `supply_bound` sums turnover's routes and each
  operator's `production_bound`: a rate in fmol/s. `check_spec_for` multiplies it by the horizon
  once, and the step-size check (`check_rate_bound`) never reads it, so nothing is scaled twice.
- A precursor the gene unit makes without a static bound (a degradation's monomers, a release's
  fates, an export's coupling) is refused, with that reason.

**The general feature it needed:** `production_bound(spec, declaration) → {(species, cell): fmol/s}`,
an operator's largest rate of making a row, read with `getattr` (no contract change). The gene
unit's comes from its laws (TEMPLATED_POLYMERISATION_LAWS.md §4):
- a chain's release, κ_ρ C_ρ,m φ_ρ with φ ≤ 1 and C at most its pool's machines, is at most
  κ_ρ M_pool;
- a transfer's (recharging), V V_C times saturations and an affinity factor each at most 1, is at
  most ν V_C V, at the cell's largest volume.

**Fixture and tests.**
- The fixture: `validation/tissue/shared_inventory_fixtures.unit_pair`, the ribosome-limited world.
  Translation makes the neutral protein P. The producer assembles P into the units of a gate-free K
  population, whose units carry no current.
- The tests: `tests/unit/test_shared_inventory_unit_writers.py`:
  - the definition both ways: admitted; refused without P's registry potential, on a precursor
    made only by degradation, and with a D152 route on the precursor;
  - R5 including the gene unit's supply, exactly once;
  - the per-writer books at every saved row;
  - a mid-run restart, in process and through a written snapshot, bit for bit the unbroken run;
  - a restart cut exactly at both sources' switch-off, and one step to each side of it (D349): bit for bit the unbroken
    run, with a switch that is skipped or undone after the resume caught. The switch acts in the step that leaves its row,
    so the checkpoint at that row holds the state before it.

## 3. Part 3. An integer population on continuous chemistry (B selected)

### 3.1 The physics, in either host

A population of integer units, here free subunits S and active units A with S + 2A fixed, jumps by
events whose rates depend on continuous amounts; between events the continuous amounts follow ODEs
in which the integer counts are constants. This is a piecewise-deterministic Markov process (Davis
1984, from memory), and its exact simulation is the hybrid next-reaction rule (Haseltine and Rawlings
2002; Alfonsi et al. 2005; from memory):
- **The clock.** H(t) = ∫ a₀(x(s), N) ds from the last event, a₀ the sum of the population's
  channel rates at the continuous state x and the counts N. The next event fires at H = E,
  E = −ln u₁.
- **The channel** at the crossing state, by u₂ against the channels' partial totals in declared
  order: the exact kernel's rule (the first j with c_j > min(u₂ a₀, nextafter(a₀, 0)), its prefix a
  serial left fold).
- **The jump** changes N; the continuous right-hand side changes with it, so the integrator restarts
  there, as at the lumen's kink.
- **The draws:** two uniforms per event, (u₁, u₂), from the population's own stream at counter k for
  its k-th event. So with feedback off and constant rates a₀ is constant between events, the crossing
  falls at t_k − ln(u₁)/a₀, and the event trace equals the exact kernel's for the same stream: a
  pathwise check to rounding, in the manner of Protocol G's tier 1.
- **The propensities** keep the family's convention, which the references must use:
  `cells.stochastic_mass_action@1`'s ff(n, a) = n!/(n − a)!, so 2S → A at n_S = 2 has
  ff(2, 2) = 2 (ordered pairs) times k_f's other factors, and the reverse from the declared
  potentials.

S3's pore clock (OL6, `rosenbrock_dense.quadrature`) is this clock already: H is carried by the
Rodas4 stages without entering step selection, with its own embedded estimate and dense output, and
D309 accepts a step when |U^H| ≤ 10⁻¹⁰ + 2 × 10⁻³ |dH|. That gives **the event-time tolerance's
form:** summed over the steps to a crossing, H's error is at most n_steps × 10⁻¹⁰ + 2 × 10⁻³ E by the
estimate, so the event time's error is at most that over a₀(t*), plus the crossing solver's tolerance;
a run declares its own constants (D309's are the pore clock's). The estimate overstated H's error
about 200-fold in OL6's probe, so the registered tolerance comes from the bound, not from a measured
error.

### 3.2 Option A: a declared per-scope hybrid representation in the assembly family

- **What it is.** A new representation, for example `cells.hybrid_events@1`, chosen in
  `execution.representation` over the same declared world, in which each place and each step is
  declared to one scope: **exact** (the population's places and steps, fired by the clock) or
  **continuous** (the pools, integrated by Rodas4). D301's contract holds per scope: one
  representation per scope, chosen at definition, refused when a place is declared in both.
- **The couplings are reads.** The transfer is a continuous step (S's entry from the pool to the
  lumen) whose rate the active unit sets as a catalyst through the transition-state factor, which
  parses today; the assembly 2S → A is an exact step whose rate reads the pool (the feedback), which
  needs a new factor (below). A step that changes places of both scopes is refused in version 1. In a
  vesicle world the two finite pools are its lumen and its pool, and the active unit a channel in
  the membrane.
- **What it reuses.** `cells.rate_equations@1`'s host loop, stops and crossings (Illinois, re-stepped
  to the root), Rodas4 with its dense output, S3's carried clock and D309's bound, the exact kernel's
  draw and channel conventions, the family's streams, keys and domains, and FR-22's checkpoint format
  for exact events.
- **What it lifts, for this representation only:** OL6's refusal 11 (mixed representations), and
  refusal 9 (checkpoints): the checkpoint saves t, y, the next h, the controller's memory, H, the
  counts and every stream counter at an accepted step, and restarts bit for bit (OL6 §6.10's later
  option, about 0.5 agent-day). Refusal 3 opens for the exact scope's events: their trace and
  uniforms are recorded.
- **What the representation must state per scope** (none of it exists today):
  - **count arithmetic and F:** exact places keep the exact kernel's falling factorials and ln k!,
    continuous places Kurtz's limit and Stirling's form (OL6 §1.3). That is separable only where a
    phase's free energy is: per place in a dilute phase, but not in the membrane, whose mixing term
    normalises by every membrane place's count (x = n/(N − c)). Version 1 would admit exact places in
    dilute phases, or a membrane whose places are all exact, and refuse a mixed membrane;
  - **the envelope and the zero-fed refusal** (OL6 §1.5, refusal 2) apply to the continuous scope
    only: the active count reads 0 or 1 by design;
  - **the ledger:** event heats as the exact kernel books them (ln a⁺ − ln a⁻), continuous heats as
    the rate equations' quadratures, both into one F;
  - **checkpoints:** FR-22's rung P serves population worlds; a single lineage's checkpoint (rung S)
    is refused today (`checkpoints.py`), so C3.6 runs in a population world (`cells.shared_pool@1`)
    or a third refusal lifts.
- **C3.1's world in @2 today** (S, `probe/part3_parse.py`, `out/part3_parse.json`; host-only parses
  of `validation/assembly_lineages_v2/worlds.world` with a subunit moiety, U and P = 2U):
  - with the units in the membrane and S's entry catalysed by P through the transition-state
    factor, the world parses: the activity drives the transfer;
  - the feedback as a pool place on both sides of the membrane's assembly step is refused: a
    cross-phase step takes a geometric encounter law, and the one other admitted shape is a pool
    molecule binding a declared site (§0.2c rule 3, §0.2f);
  - with the units in the pool, the assembly reading S as a place on both sides parses, but then P
    cannot catalyse the entry, since the factor's catalysts are membrane places.

  So today's laws express either coupling, not both in one world. Option A also needs a factor by
  which a membrane step's rate reads a pool place (or a pool unit catalyses a crossing): est. 0.5–1
  agent-day more, in the family's files. The membrane's both-sides factor, (N − c − r* + 1)/
  ff(N − c, r), is singular at N = r under c = 1 (`stochastic_mass_action@1`'s docstring), which a
  world with c = 1 must avoid.
- **Owners and timing:** the assembly family's files are the OL6 builder's until S7 lands; the build
  starts after it.
- **Price (est.):** the hybrid loop and its scope declaration 2–3 agent-days, the per-scope
  arithmetic, F and ledger 1–1.5, the pool-reading factor 0.5–1, the checkpoint 0.5–1, the split
  token 0.5–1 (§3.5, beside S7), the records 0.5; about 5–8 in all, plus the references.

### 3.3 Option B: an integer-population operator in the composite

- **What it is.** A new operator, for example `integer_unit_population@1`, owning per-site integer
  counts, a clock H and threshold E per site, and a stream counter. Its channels read @3's rows
  (the feedback), and its active count drives a declared transfer between two finite pools, for
  example a cell and its closed compartment (FR-1), written to @3's rows as a further writer with its
  own books and ΔG (part 2's rule).
- **Events inside a fixed step.** The operator's half-step integrates its transfer and H by
  SSPRK(3,3), locates a crossing on the stage polynomial, and splits its half-step there, the
  remainder at the new counts. The pools also move in other split parts and in @3's step, so the
  event time carries the split's O(dt²) error against the coupled system: the tolerance comes from a
  dt-halving study, not an integrator tolerance. Events only at grid times would be first order.
- **What it needs that the composite lacks:** a random stream (keys, domains and counters in the
  state, threefry in a split part, per-world streams under vmap), integer owned state, event location
  inside a split part, and the division of owned state for C3.5: today the partition refuses an
  operator with owned state on a dividing cell (D301's inventory, row 7; composition M4's C5 and C6).
- **What it gets free:** the composite's checkpoints carry owned state, so a same-seed restart is
  bitwise through D153's loaders; every world without the operator keeps its programs (crossrev
  identical); part 2's pools, water and reactions are in the same world.
- **Price (est.):** the stream infrastructure 1–1.5 agent-days, the operator with event location 2–3,
  owned state through division 1.5–2 after M4, the records 0.5; about 5–8 in all, plus the references.

### 3.4 What discriminates the hosts

| | A: hybrid representation (assembly) | B: population operator (composite) |
| --- | --- | --- |
| Event times | A located crossing on the dense output; error bounded by the declared clock constants (D309's form) | The split's O(dt²); shown by halving dt |
| Restart (C3.6) | Needs refusal 9 lifted: the loop's state saved | D153's loaders, bitwise as built |
| Split (C3.5) | A token beside S7's, in the division the family has | Needs owned state through division (M4) first |
| Streams | The family's, with domains and keys | New in the composite |
| Refusals lifted | OL6's 9 and 11, for this representation only (the OL6 builder's files) | None of OL6's; new infrastructure in the composite (the core owner's files) |
| The pools' chemistry | The family's laws: dilute and membrane mass action, permeation, the osmotic lumen | Every composite process: reactions, water, transport, the gene unit, part 2's two writers |
| Consumers | Protocells with low-count channels; FR-39's pores beside them | Cells with few channels or machines (FR-13, FR-40) beside shared pools |
| Count arithmetic | Per scope: discrete for the exact places, Stirling's for the continuous ones; a mixed membrane refused | The units carry no free energy (declared, as the gene unit's machines); the pools keep @3's terms |
| Price (est.) | 5–8 agent-days | 5–8 agent-days |

### 3.5 The split of one unit: a declared token

Protocol G §3's S7 contract gives the first daughter floor(f N) of the ranked places, so at N = 1 and
f = ½ the first daughter gets none, deterministically. C3.5 asks for an equal-probability split of a
single unit, which needs its own rule. The proposal, in either host:
- **`independent_segregation`:** each unit goes to the first recipient with probability f, drawn from
  the partition domain keyed by the parent's key, one uniform per unit in declared unit order (u < f:
  the first recipient); the second recipient takes the rest. It is binomial partitioning, the
  standard model of random segregation of low-copy components at division (Huh and Paulsson 2011,
  from memory). At N = 1 exactly one recipient receives the unit on every draw, with probability f
  each way, and the recipients' counts sum to the parent's exactly, in integers.
- **The alternative,** `rounded_fraction`: floor(f N) plus one more with probability f N − floor(f N).
  It also gives ½ at N = 1, with the least variance, but it is not a physical segregation model.
- **What it governs:** the exact scope's integer places, unit by unit. The continuous places split by
  the division's rule for them, the mean split f·n (the rate equations' shear fission), so the
  recipients' inventories sum to the parent's: exactly for the units, to rounding for the pools.
- **S7's `exact_fraction` and Protocol G's contract stay untouched:** the new rule is another token of
  the same declaration, and a world that declares none keeps S7's.

### 3.6 The checks

| Case | Test | Tolerance's origin |
| --- | --- | --- |
| C3.1, C3.2 | S + 2A = 2 at every event and row, exactly (integers); the two pools' total constant to the integrator's rounding (A) or the ledger's (B) | Exact; rounding |
| C3.3 | Feedback off, constant rates: the fraction of n seeds with A = 0 at each of m times against P₀(t) = k_d/(k_a + k_d) + (P₀(0) − k_d/(k_a + k_d)) e^{−(k_a + k_d) t}, with k_a and k_d the two states' total rates under §3.1's convention | Binomial: |p̂ − P₀| ≤ z √(P₀(1 − P₀)/n), z set for m comparisons before the run; a plant with k_a 10% high must fail at that n. Plus the pathwise check: the trace equals the exact kernel's, to rounding |
| C3.4 | Feedback on: each event time against the same-draws integration (§4) | §3.1's bound (A) or the dt-halving order (B), fixed before the run |
| C3.5 | Splits at N = 1 over n seeds: one recipient per draw, counts summing to the parent's; the first recipient's frequency against f | Exact; binomial as C3.3, with a plant at f = 0.45 that must fail |
| C3.6 | A same-seed run cut at an accepted step after an event, restarted: its trace, counts, pools and ledger equal the uninterrupted run's | Bitwise |

### 3.7 Recommendation: A

This was the design's initial recommendation on event timing. The user's decision for B is recorded in §5.

- FR-43's part-3 checks are statements about exact events and their timing. A gives a located
  crossing under a declared bound and reuses the family's streams, keys, division and exact-event
  conventions; B gives event times only to the split's order and makes the composite stochastic for
  the first time.
- A's lifted refusals are confined to one new representation, so `cells.rate_equations@1` and
  exact events keep their programs and their protocols (D and G) stand. Its open points are stated
  (§3.2: per-scope arithmetic, a mixed membrane, rung S, the pool-reading factor), and its price
  carries them. With both at 5–8 agent-days, the choice rests on the event-time guarantee, the
  restart and the split, where A has the machinery and B needs new infrastructure.
- B is the door when a cell-scale world needs a low-count population beside part 2's shared pools.
  Its stream and event-location pieces would then be designed against A's clock, which is the same
  algorithm.

## 4. The independent references: what each needs

Each is written by a code-blind references agent from equations and declared values, never from the
engine's code or outputs.

**Part 1 (no agent).** The closed form expm(K t) n(0) sits in the test with the planted link (§1.2):
the lead's brief allows it.

**Part 2, the coupled calculation (C2.3):**
- the world's declared values: volumes, initial amounts, the gene unit's declaration (copies, pools,
  chain lengths, stages, speeds, saturations, the transfer's capacity and share), the D152 reaction's
  law and constants, the registry's potentials and c₀, temperature;
- the laws, from TEMPLATED_POLYMERISATION_LAWS.md §4 (initiation, stage exits with the per-residue
  affinity, degradation, recharging) and D152 §2.2 (mass action, Michaelis–Menten, the passive law),
  with their units;
- the unsplit coupled ODE, integrated to a stated tolerance (for example Radau at rtol 10⁻¹¹ checked
  against DOP853), giving n_N(t), each writer's rate and its cumulative produced and consumed amounts
  at the sample times;
- not the split order: that is the engine's discretisation, which the dt-halving ratio measures.

**Part 2, the evolving volume (C2.6, C2.7):** the above, plus water's law (docs/PUMP_WATER_MODEL.md:
the flow across a patch Q = 10¹⁵ A L_p a (ψ_cell − ψ_outside) pL/s, ψ = P − RT (Σₛ nₛ + n_imp)/V,
P = K (V/V_ref − 1) + P₀, the bath held), every row counted as an osmolyte, and the energy terms to
report: F(N, V), U(V), the water heat, the bath work and the reactions' heat and work.

**Part 3, the same-draws integration (C3.4):**
- the per-event uniforms (u₁, u₂), read from the engine's recorded uniforms, plus a premise check that
  regenerates them from the documented stream (threefry2x32 keyed by seed, domain, key and counter; the
  family's `streams.UNIFORM` map from a word to the open interval), as Protocol G §4 checks its shared
  uniforms;
- the map E = −ln u₁ per event, H restarting at 0 after each event, two uniforms per event at counter
  k, and the channel rule of §3.1;
- the propensities under §3.1's convention, the feedback's form, and the continuous ODE with the
  counts constant between events;
- its own integration (for example the ODE with H appended, Radau at rtol 10⁻¹², events located by a
  root finder), giving each event's time, channel and the pools at it.

**Part 3, the closed forms (C3.3, C3.5):** the two-state P₀(t) and the binomial frequencies need no
agent; they sit in the tests with their plants.

## 5. Rulings and decisions asked

**User decision, 23 November 2026. Choose B for part 3.** The integer population and the existing
composite operators must be able to act on the same finite pools in one world. Verify event times
against the same-draw reference under step halving, and include a case where an existing writer
changes the pool read by the integer clock and the integer state changes the subsequent pool flux.

**The user's answers for the lead.** The lead owns the five implementation rulings below.

1. **Cap, sum order and layout (§§1.3–1.7).** Raise the cap to 1,024 total species including ions.
   Keep the existing fold through 16 terms and use an ordered scan above 16. Record the species
   counts and cross-revision checks at landing. Correct scalar and batch trace budgeting now,
   counting fixed storage per resident copy and saved rows per time point. Stage the per-entry
   sparse layout after the cap change and include a cancellation case before claiming equivalence.
2. **Timestep (§1.5).** Report the step needed for the declared accuracy and the stage limit.
   Document the measured range for the chain fixture. Leave a stiff integrator to a separate law.
3. **Fixed-volume writers (§2.2).** Accept the declared split order, one standard potential in
   the registry and separate material and energy accounts for each writer. Retain the single-writer
   restriction on labelled and exported-product rows in this release.
4. **Changing volume (§2.3).** Use composition option A for the reaction volume read and keep the
   reaction law ID. Deliver current-volume reads for both the reaction and the gene unit in FR-43.
   Add C2.8 with both writers active while volume changes. Check amounts, both rates and energy
   against the independent reference, including a case that fails if one writer uses initial volume.
5. **Integer partition (§§3.3–3.6).** Use `independent_segregation` and preserve the existing
   `exact_fraction` contract. B requires no change to OL6 refusals 9 or 11. Schedule owned state
   through division, verify exact integer conservation, and check a same-seed restart between events.

## 6. Evidence and disclosures

- **Scripts:** `probe/chain_world.py` (the chain world, the charged world), `probe/probe.py` (the run,
  orders, jaxpr, rates, charged and w4rest subcommands), `probe/doubling.py`, `probe/heat_check.py`,
  `probe/gate_check.py`, `probe/part2_parse.py`, `probe/ops32.py` and `probe/ops_rows.py`; the
  queues `timed_small.sh`, `timed_large.sh`, `timed_v2.sh` and `timed_v3.sh` (CPUs 4 and 5 under the
  timed lock), `w4rest.sh` (stopped on the light CPUs, under 5% of a core each), `lane_batch.sh` and
  `lane_ops1024.sh` (gate lane A under its lock) and `gpu_block.sh`; each queue copied the scripts it
  ran beside its records. The first smoke, the order checks, the doubling, the guard set, the
  library check, the heat check and part 2's parses ran on the light CPUs (6, 7 and 22) at nice 10,
  both gate lanes being held then.
  `probe_v1.py` and `chain_world_v1.py` are the versions the first queues ran: their run records in
  `out/` are superseded by `out/v2/` and kept; `out/orders.json` and `out/jaxpr-*.json` are theirs,
  from code v2 kept unchanged.
- **The first large queue failed** at the definition: the trace budget refused 256 and 1,024 rows
  (§1.6). Its records are kept in `out/`.
- **Source:** every run used the frozen snapshot `snapshot-92e18df4` (guards scope, clean patch).
- **Blindness:** this note's author read nothing under `validation/ool/references/`, no held-out value
  and nothing of the OL6 checker's. Three recursive content searches traversed those folders while
  looking for other text: two over the checkout's root (a function's name, `def polymerase_limited`,
  and the GPU flag's name, `gpu.reserved`), which pass through `validation/ool/references/`, and one
  over `/mnt/workspaces/Cells/*/` (the timed lock's name), which passes through the OL6 checker's
  folder; and one recursive file-name search over the checkout (`SITES.md`). None displayed any
  content from those folders. One process listing, taken to see which jobs loaded the light CPUs,
  displayed the command lines of two running OL6 checker processes (their driver scripts' paths
  under the checker's folder); no output of theirs was read. On 23 November at about 14:31,
  after the user's review, two more searches: a recursive content search for `probes2` over
  `scripts/`, `validation/` and `tools/` (file names listed, paths containing `references` filtered
  from the display), which traversed `validation/ool/references/`; and a file-name search over `/` for
  `proofs.sh`, stopped after about 2 min before it displayed anything. Neither displayed any name or
  content from those folders. Searches since then use `git grep` with a pathspec that excludes the
  blind folder.
- **The L4 block** (§1.8): `probe/gpu_block.sh`, launched by the lead as the unit `cells-fr43-gpu`
  after the visualizer's notice; its scripts are copied beside its records in `out/gpu/`.
