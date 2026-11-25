# Calcium: channels that carry it, a store, and the sodium/calcium exchanger (design)

**Status: revised 25 November 2026 after its second reader, for the lead.** Desk work only: no engine code. Branch
`calcium-store-design` from 43b22d40. Main is at f839a8a0 (D386), and no ID has changed. The second reader's table
(`REVIEW.md`) and the lead's rulings on it (`LEAD-RULINGS.md`) are in the lead's working folder; rows 1 to 9, 13, 14
and 16 are this note's. D385 ruled L1 to L9 as recommended. D386 gave the user's answer to U1 and asked for two
symport laws (§7.2). The advisor timed out every time it was asked.

**What it answers.** Candidates G-1 (calcium-permeant channels) and G-4 (a calcium store) and row B2 (the 3 Na : 1
Ca exchanger) of the legacy port plan, with the corrections of its re-expression map (`legacy-port-plan` at
a1db6ab9, §14), and D211's two symport laws (plan rows I8 and I9). This is the map's stream D. Stream E owns the
factor source that opens the store's release (G-5) and G-7; its note is
`docs/IP3_RELEASE_AND_ASSEMBLY_AVAILABILITY_DESIGN.md` at 66ffa1d7.

**Engine models (AGENTS.md).** `resolved_pump_composite@1` over `resolved_pump_tissue@3` ("@3"), with the kinds
`cells.passive_routes@1` and `cells.transporter@1` and the operators `cell_owned_compartments@1` and
`local_species_reactions@1` ("D152's reactions").

**Marks.**
- **(M)** measured by this note's probes, listed with their commands and outputs in Appendix A; **(M2)** measured by
  the second reader;
- **(R)** read in the code at 43b22d40. Paths start at `src/cells/` unless they say otherwise. §15.1 gives the lines
  on `legacy-cleanup` too;
- **(S)** this note's own derivation, arithmetic or estimate. Nothing marked (S) was run;
- sources: [abs] the abstract, or the page as a reader tool showed it; [rec] the bibliographic record only; [sec: X]
  through X.

**What this revision changed.** The charge rule's correction, designed in full and measured (§8.3). One material
rule for channels, cycles and loops (§8.2), with the corrected bounds (§6.3, §6.5). Four refusals by name (§5.2,
§5.5, §10). Refusal 6's version text (§6.2). The feedback hooks' final form (§6.5). What retires and when (§6.3).
Two symport laws (§7.2). The tests' plants and a two-cell closed row (§14). The price, the order and every live edit
with its line (§15).

## 0. Summary

1. **Most of the store runs on today's engine (M).** Two planted law modules, data only, were enough for a one-cell
   world with a store: pump, leaks, a release route (ungated, since its source is E's), kinetic buffers, a plasma
   pump and the exchanger. It parses, steps under the composite, and closes its energy ledger. So does the two-cell
   closed world, with near and far, a store per cell, a channel per plasma patch and calcium on the junction and the
   faces (§14, row 14).
2. **What is missing is small** (the table below). The pieces are general. None is written for one experiment.
3. **One live rule must be corrected first (§8.3).** The stage's charge rule divides a cell's conductances by the
   capacitance of its stores' membranes too. It admits steps that the plasma membrane cannot take. No world of today
   is above the corrected limit (M, 31 worlds with such a node, the largest 0.028).
4. **Every piece keeps the ensemble's equations.** Only the integrator and the splitting change. So a derived band
   can apply to every row, and no row needs the consumer's own 3e-9 criterion (§12).
5. **The price is about 7 to 9.25 agent-days (S),** against the plan's 7.5 to 13 for the same three items, and 0.8
   to 0.9 more for the two symport laws (§15).
6. **No new family word is needed** (§13). The user's one question is answered (§16.1). Four new points go to the
   lead (§16.3).

| Piece | Today | What this note adds | Equations |
| --- | --- | --- | --- |
| The charge rule beside a store | a step four to five times too long is admitted beside a store of the ensemble's size (M, M2) | each patch that faces a floating node has its own row (§8.3) | unchanged |
| Calcium as a species row | runs | nothing | unchanged |
| Calcium through a gated channel (G-1) | refused at the parse; then the buffers refuse it (M) | the law as the one authority for its ions' valences; a per-stage material bound for channels; a door for the buffers; the module `cav1p2_m2h@1` | unchanged |
| A store with its own voltage | runs on @3; its declaration is refused in a closed world (M) | refusal 6, version 1.1 | unchanged |
| The store's pump | @3's own pump is refused there (R); a planted cycle law is admitted and matches bit for bit (M) | the cycle law `atp_driven_transporter_mass_action_positive@2`; the transporter's material bound for the charged rows it moves | unchanged |
| The store's leaks | run (M) | nothing | unchanged |
| The release | its route and its `factors` list run (M, R) | the bound on the feedback a factor brings (§6.5); the source is E's | unchanged |
| Buffers, cytosol and store | run (M) | nothing beyond G-1's door | unchanged |
| The exchanger (B2) | a planted law is admitted and matches to 1.9e-15 (M) | the module `sodium_calcium_exchange_symmetric_barrier@1`, labelled synthetic (D386) | unchanged |
| The plasma pump (B1) | @3's live law equals the legacy kernel bit for bit with a converted constant (M) | nothing needed; one law for both pumps (§6.3) | unchanged |
| NKCC and the configured symport (D211, D386) | planted laws are admitted and match to 8e-15 of the one-way rate (M) | two modules, data only; one refusal (§7.2) | unchanged |

**The choices, each with one recommendation** (C2, C4 and C5 are ruled as recommended, D385; C8 is the user's,
D386).

| | Choice | Recommended | The main alternative, and why not |
| --- | --- | --- | --- |
| C1 | Where calcium lives | one row of free calcium per node, bound forms as their own rows (the ensemble); a row of totals under `rapid_binding@1` (the cardiac plan). Both are on main; a world picks per node | a second row for the store's calcium inside the cell's node: it loses the store's volume and voltage |
| C2 | How a channel carries calcium | a channel population on @3, whose law declares each ion's valence, with constant-field flux | gates as a factor source on a charged passive route: no core change, but a second home for voltage-gated channels (§5.1) |
| C3 | Where the store lives | a compartment of FR-1 with its own capacitor, for the ensemble | pools at the cell's potential (the cardiac plan's): a changed model for the ensemble, and the right form for a dyadic subspace (§6.1) |
| C4 | A closed exterior | the compartment's node must not be its component's representative | a held bath: a changed model (the map, §14.1) |
| C5 | The pump | one cycle law on the transporter kind, any valence, any host | per-stage terms for @3's own pump: a special case in the core, and no host for the cardiac SR (§6.3) |
| C6 | The release's opening | the existing charged route, its `factors` list, and a stage bound for the feedback | a law of its own: it would hold the gate and the flux together, for one ligand |
| C7 | Buffers | D152's mass action, as today | the rapid closure: a changed model for the ensemble, and the cardiac plan's form |
| C8 | The exchanger | one module in the monomial form | the cardiac lane's four-state cycle: a changed model (§7.1) |

## 1. What is refused today, and where

| # | Refused | Where | Shown |
| --- | --- | --- | --- |
| 1 | a channel's calcium ion: "Channel ion requires its law's species and valence" | `definitions/surface_pump_v3_spec.py:169, 328-329` | (M), with a planted law |
| 2 | any calcium channel law by name: none is registered on @3 ("Channel requires a resolved_pump_tissue@3 law and permeant ions") | the same file, 321-322 | (M) |
| 3 | a reaction that writes calcium while a channel carries it: "acts on species with zero membrane, junction and channel permeability only" | `operators/species_common.py:167-192` | (M) |
| 4 | calcium as a covered counter-ion. The threshold is 100. Its margin is 4.6 on the plasma patch with a held bath (M); the map's arithmetic for the closed worlds gives 3.7 there, 10.5 on the store's patch and 1.3 on the junction. With the corrected capacitance (§8.3) they are about 16, 14 and 6, still refused (S) | `operators/species_common.py:204, 207, 255` | (M) |
| 5 | @3's calcium pump, its Na/K pump, or a channel population on a compartment's bounding patch | `operators/compartments.py:356-366` (refusal 4) | (R) |
| 6 | a cycle law's move at a compartment's node, unless the law declares a step term that its kind holds. Of the cycle laws only the proton pump declares one | `operators/compartments.py:270-342`; `laws/pumps/proton_pump.py:264` | (R); a planted law that declares both terms is admitted (M) |
| 7 | a compartment in a world without a held bath | `operators/compartments.py:512-518` (refusal 6) | (M) |
| 8 | declared kinds, reactions and routes at a compartment under RK4 | `models/surface_pump_v3.py:3412-3427` | (M) |
| 9 | the composite on a GPU in the vector windows, and device row checks on any GPU | `execution/vector_windows.py:213-230`; `execution/row_checks.py:72-76` | (R) |
| 10 | replacement beside any channel law beyond today's five: a bare `ValueError`, not a refusal by name | `operators/cell_replacement.py:206` | (M2), with `kv1p1_mh2@1` |
| 11 | the two-cell closed world's definition under field solver version 2: "Initial resolved charge/current field or transport domain invalid". With version 3 (D147's floor) it parses | `models/surface_tissue.py:515` | (M) |

**Not refused, but not bounded, or bounded wrongly.** Each is a gap that the pieces here would otherwise widen.

| # | Today | Where | Shown |
| --- | --- | --- | --- |
| 12 | a trace ion's material relaxation through a channel has no bound. Adding the calcium channel left the stage's material rate at 2.42 per second | `models/surface_pump_v3.py:3701-3727` | (M) |
| 13 | a charged row that crosses in a cycle has no material bound: the term counts neutral rows, and charged rows changed at one end only. A cycle that moves no net charge (the K/H exchange, the phosphate symport, any salt symport) has no charge slope either, so nothing bounds its charged rows | `kinds/transporter.py:2240-2250`; `laws/cycles/potassium_proton_exchange.py`, `phosphate_proton_symport.py` | (R); named by `docs/CHARGED_TRACE_SPECIES_DESIGN.md` §6 for the kinds owner |
| 14 | the feedback of a factor on the row it reads has no bound. The stage rules use the routed value, never its slope | `models/surface_pump_v3.py:3682, 3721` | (R) |
| 15 | a cell's charge row divides by its stores' capacitance too, so it reads up to 1 + C_b/C_m times too low | `models/surface_pump_v3.py:3674`; `models/surface_pump.py:487`; `kinds/transporter.py:691-718, 2330-2376` | (M, M2), §8.3 |

Row 14 is the reason the coupling operator refuses an instantaneous read of a charged species: "could close a loop
@3's bound does not see" (`operators/species_regulated_availability.py:748-753`).

## 2. The two consumers, and what they share

### 2.1 The calcium ensemble

Four worlds (`configs/{spatial,plasma,gated,ip3}_calcium_cluster.json`), two cells each, all synthetic. The map's
§14.2 and §14.3 hold their equations and file lines. In short, each adds to the one before:

| World | Needs | From |
| --- | --- | --- |
| `spatial_calcium@1` | a store per cell (pump, K and Ca leak, release), buffers in the cytosol and the store, Ca on the plasma patch, the junction and the faces | G-4; E's calcium factor |
| `@2` | the plasma calcium pump and the exchanger | B1; §7.1 |
| `@3` | one Cav1.2 population per plasma patch | G-1 |
| `@4` | IP3, its buffer, and a second factor on the release | E |

Every control in the four configurations is constant at 1 (R): no schedule of a leak, a pump or a release is used
there.

### 2.2 The cardiac lane, and what has moved since its note

`docs/HUMAN_CARDIAC_LAWS_DESIGN.md` (16 November) plans calcium as a channel ion and an L-type current with
calcium-dependent inactivation (H1), then pools at the cell's potential with uptake, leak, graded release, rapid
buffers and its own exchanger (H2). D211 folds calcium handling into that lane. Since the note was written:
- chloride is a channel ion (D228); calcium is not;
- the transporter kind has a population axis: any number of populations per patch, several roles per cycle, no fuel,
  and four general forms (its §1, §3.6 and question 9 ask for these);
- the general closure `rapid_binding@1` holds several ligands (its §3.3 and question 8 ask for this);
- the routing door reaches @3's channel availabilities (its question 10, first half);
- channels, membranes, pumps and the transporter admit a heat booking that cannot be negative (its §3.8 and question
  13);
- the species cap is 1,024, not 16 (its §3.3).

These are read in the code and the decisions. They shorten H1 and H2, and nothing here undoes them.

### 2.3 One law per mechanism (D210)

| Mechanism | The ensemble | The cardiac plan | The shared law | What differs, and stays apart |
| --- | --- | --- | --- | --- |
| ATP-driven calcium transport | plasma pump and store pump, 1 Ca per ATP, saturating, times 1 - e^x | sarcolemmal pump, and SR uptake in two populations, completed by the same factor | `atp_driven_transporter_mass_action_positive@2` (§6.3) | the host: a plasma patch, a bounding patch, later a pool route; the parameters |
| Passive calcium flux | constant field, at the host's voltage | leaks, transfer and diffusion between pools; Fick's law | `passive_constant_field_permeation@1`: at zero voltage it is Fick's law, since B(0) = 1 | the host's voltage rule |
| Calcium through a channel | Cav1.2, m²h, constant field | L-type with calcium-dependent inactivation, constant field with activity factors; a calcium leak | the channel population, its valence rule and its material bound (§5) | the gating laws. H1's reads, gate counts and activity factors stay H1's |
| Na/Ca exchange | one mode, 3:1, a symmetric barrier | a four-state cycle with a sodium leak mode | the transporter's population axis, in both | two kinetic forms: the ensemble's is registered as synthetic, and the question is taken up again when the cardiac law lands (D386) |
| Buffers | mass action, charged forms | rapid equilibrium | none: mass action is the detailed form, the closure its declared fast limit (Wagner and Keizer 1994 [rec] for rapid buffers) | the representation, declared per world (D175) |
| The store | a node with a capacitor | two pools and a subspace at the cell's potential | none: two representations (§6.1) | the representation |
| Release | instantaneous Hill factors of Ca and IP3 | a state that relaxes to a target set by the L-type current | the route; the sources differ | the source (E's; H2's) |

## 3. Conventions

- **Units:** amounts fmol, volumes pL, concentrations mM (fmol/pL), areas m², permeabilities m/s, voltages V,
  currents A, energies pJ, times s. F and R are `laws/electrochemistry.py`'s.
- **A patch** has its cell inside and its outside node outside: V = phi_in - phi_out. A store's bounding patch has
  the cytosol inside and the store outside, so V_b = phi_cytosol - phi_store. Legacy's store voltage is V_ER =
  phi_store - phi_cytosol = -V_b.
- **B(x) = x / (e^x - 1),** and x = z F V / (RT).
- **A cycle's ends:** N and P. `orientation {"N": "a"}` makes N the patch's cell. psi = F (phi_N - phi_P) / (RT).
- **The affinity x** is the cycle's free energy over RT, negative when the forward cycle runs down. J = k a S (1 -
  e^x).

## 4. Where calcium lives

| Option | What it is | What it gives | What it loses |
| --- | --- | --- | --- |
| (a) free rows | row Ca holds free calcium; each bound form (B, CaB, Ca2B) is its own row at its node | finite-rate binding; the charge of every form is a row's; the ensemble's equations | stiffness at fast on-rates (D152 bounds dt L <= 1) |
| (b) totals | row Ca holds total equivalents and each binder row its total; `rapid_binding@1` gives free calcium at every stage | the exact fast limit; no on-rate in the step | the kinetics; operators may not name a held row; routes must read the closure |
| (c) a store row in the cell's node | a second species for stored calcium | no new node | the store's volume, voltage and charge |

**Recommended: (a) for the ensemble, (b) for the cardiac plan.** Both are on main. A world chooses per node, and the
two refuse to share a row (`registry/species_registry.py:1909`). (c) is not recommended for either.

**Absent rows.** Every species row exists at every node, positive. Where a bound form is absent, its row is a
declared trace. The engine's key for it is `background`, `{trace_mM, floor_fmol}`, in the species' own entry
(`registry/species_registry.py:295`, parsed at 479-484 and checked at 1544, `check_background`). It is inert there:
no route, no reaction, zero diffusivity. (The second reader's row 16 calls `background` a validation builder's key.
It is the registry's; FR-4's builder writes it. The sentence is corrected to say so rather than dropped.)

## 5. Channels that carry calcium (G-1)

### 5.1 The options

| | A. A population on @3; the law declares its ions | B. A population on @3; a longer valence table | C. Gates as a factor source on a charged passive route |
| --- | --- | --- | --- |
| What | the parser checks each ion against the law's own (species, valence, weight); the table goes | one more entry, `"Ca": 2` | a kind holds m and h per population, its opening multiplies a `passive_constant_field_permeation@1` route through the routing door |
| Authority for an ion's valence | one, the law | two, the law and the table | the species row, as for every passive route |
| Gates | @3's exponential stage update, in [0, 1] at any step | the same | the tableau: a kind's end-of-step booking receives no potentials (`registry/kind_registry.py`, `book`), so an exponential update needs a new core seam; a domain check refuses a gate outside [0, 1] |
| Gate counts, concentration reads | H1's seams, needed by the cardiac currents in any case | the same | free: the kind sees the stage's amounts |
| Ions per population | any mixture, each at its valence | the same | one route per ion, sharing one gate |
| Availability schedules, abundance, units, trafficking, block (FR-51), regulated availability, G-7's assembly factor | all apply, since they act on channel populations | the same | none applies: the gate is a factor, the abundance a number in the permeability |
| Material bound | added here (§5.3) | the same | exists |
| Buffers | a door (§5.4) | the same | admitted as they are |
| A law's host | @3, as every voltage-gated law | @3 | the new kind: a law has one host (`registry/laws.py`), so calcium laws would leave the other channels' home |
| Core change | `material_rate` gains a static term | the same | none, or the gate-update seam |
| This build (S) | about 2 agent-days | the same, less 0.25 | about 2 to 2.5 |
| Cost to the cardiac plan (S) | none. H1 keeps its route (its §4.5 (a), recommended) and finds one of its items, calcium as a permeant ion, done: about half a day saved | as A | H1's other seams are still needed for IKs, IKr and IK1, which read concentrations on @3. The L-type current would live apart from them, as six routes and two gate sources. About 1 to 2 days more, and the currents then have two homes |
| At a closure's rows (H2) | the population declares the read (`ChannelLaw.reads`, reserved today) and the registry admits it, about half a day: the flux already reads the stage's read | as A | a new version of the route law that reads the closure, as the proton leak's @2 does, about half a day |

**Recommended: A (ruled, L1).** C is the map's other form, and it is real: it needs no core edit and it reads
concentrations for free. But it gives voltage-gated channels a second home, chosen by whether an ion is scarce. The
same law could not be hosted in both. Nothing that acts on channel populations would act on it, G-7's assembly
factor included. D211's 22 calcium and HCN laws, some of which carry Na and K as well, would leave the channel
interface. **C stays the fallback** if the lead wants no core edit in this cleanup. Its equations are the same, so
it can be replaced by A later without a changed model.

**The driving force: constant field, unchanged.** Calcium currents are strongly rectifying because the two
concentrations differ by thousands; the constant-field flux carries that and a linear form does not. The cardiac
lane's linear form, G (V - E), is H1's own declared form for other ions. Activity factors (the L-type current's
0.341 outside) are H1's, with their declared domain.

### 5.2 The law as the one authority

- **The parser's check** becomes: for each declared ion, the model's valence equals the law's own for that species
  (`ChannelLaw.permeant`, which already holds it). `SPECIES_VALENCE` is deleted. Two tests read it
  (`tests/unit/test_inner_laws.py:148`, `test_chloride_leak_law.py:109`), and they read the law instead.
- **The message** keeps its words, with the ion, its law's valence and the model's added.
- **So any ion a law declares is admitted.** The next ion needs a law, never an edit to the parser.
- **Refused by name (row 4):** a population whose law carries an ion outside Na, K and Cl and declares no
  `material_term`. "Channel {id}: {law} carries {ion}, which is not Na, K or Cl, and declares no material_term; the
  charge rule alone does not hold a scarce ion's amounts." It is checked in `parse_channel`, where the valence table
  was, so no law of D211's list can land on @3 without the term.

**The module `cav1p2_m2h@1`.** The existing kernel (`laws/channels/calcium_gates.py`), as a `ChannelLaw` on @3:

```text
u = V - 0.010 V                          (the source's shift, part of the law)
m_inf = 1/(1 + exp(-(u + 0.030)/0.006))  h_inf = 1/(1 + exp((u + 0.080)/0.0064))
tau_m = 0.005 + 0.020/(1 + exp((u + 0.025)/0.005)) s
tau_h = 0.020 + 0.050/(1 + exp((u + 0.040)/0.007)) s
open = m^2 h;  permeant (("Ca", 2, 1.0),);  V in [-0.120, 0.060] V;  no temperature term
material_term = its material slope;  rk4_step_s = None
```

Its code is the host's next free one, and its numbers are the source's. **It declares no RK4 step bound (row 5).**
The material rule runs at the IMEX stages only, and a gated law without a bound already runs on no RK4 grid
(`models/surface_pump_v3.py:4022-4028`: the bound read is 0 s, with the law's name). Its template admits None
(`registry/laws.py:418`). Its page and docstring use neutral words: the live module's text names its source in its
first line and calls the shift "native" (`laws/channels/calcium_gates.py:1-5`).

### 5.3 Equations, state and bounds

For population j on patch m, with cell c and outside node o, gates g, abundance a_j, availability v_j (routed at the
stage), block fraction u_j (1 without a block), and each permeant ion s with relative permeability r_s:

```text
J_s = 1e15 A_m P_j r_s a_j open_j(g) v_j u_j [c_s,c B(-x_s) - c_s,o B(x_s)]     fmol/s, positive out of the cell
I_j = 1e-15 F sum_s z_s J_s                                                      A, positive out of the cell
dg/dt = (g_inf(V) - g) / tau(V)
q_j,s = 1e-3 J_s [RT ln(c_s,c / c_s,o) + z_s F V]                                pJ/s, >= 0 for each ion
```

- **State:** none new. The gates, the transfers per species and the heat per species are @3's channel fields.
- **Measured:** a planted law gives the legacy flux to 2.2e-16 relative, and its targets and time constants, at the
  ensemble's start; the energy-rate balance is -1.4e-16 pJ/s of 0.85 (M).
- **The charge bound** is today's: F²/(RT) sum z² P r a open v A max(c), so z = 2 counts four times. Its denominator
  is §8.3's.
- **The material bound (new).** A channel law may declare `material_term`. Its populations then add to the stage's
  material rate, at each explicit stage, at that stage's voltage:

```text
at the cell:     T_c,s = 1e15 A P r_s a open v u B(-x_s) / V_c     1/s
at the outside:  T_o,s = 1e15 A P r_s a open v u B(+x_s) / V_o     1/s
```

  The mode's own rate, T_c + T_o, is added to the ion's row at both ends (§8.2's one rule). Where an end is a held
  bath, its part and its row are left out: D310's form. The ions add per row, so a node's rate is the largest over
  species. FR-51's part through the reversal potential (`channel_block_terms`' `inside_through_e` and
  `outside_through_e`) is added where a block uses it, and the direct part is never counted twice. At the ensemble's
  Cav1.2 it is 0.02 per second at the start and 0.7 at full opening (S).
- **Where the term is:** `models/surface_pump_v3.material_rate`, with the kernel that exists
  (`laws/routes/constant_field_permeation.material_slope_per_s`). Under N2 it stays, since N2 is implicit in
  voltage, not in amounts. It is one edit with §6.5's loops (steps 2 and 6, one owner).

### 5.4 The door for the buffers

`species_common.check_impermeant` refuses a written row with a channel route because nothing bounds that route. So:
- a channel route whose law declares `material_term` no longer counts, for `local_species_reactions@1` only (L5: the
  one operator that admits charged rows, and one that refuses RK4);
- @3's membrane and junction permeabilities still count. Calcium's leaks and its junction route are
  `passive_constant_field_permeation@1` routes, as the map has them;
- with that clause lifted in a probe, the buffers and a calcium channel parse together, and the composite steps (M).

### 5.5 Heat, integrator, refusals, restart

- **Heat and work:** passive, heat only. Default booking, or `heat_bookings: {"channels":
  "trapezoid_nonnegative@1"}`.
- **Integrator:** the flux is explicit at each ARS(2,2,2) stage; the gates take the exponential stage update; second
  order. N2 treats the slope in voltage implicitly.
- **Refused by name:** an ion whose valence differs from its law's; a law that carries a scarce ion without a
  material term (§5.2); any RK4 grid (§5.2); a gate outside [0, 1]; a voltage outside -120 to +60 mV; a channel on a
  compartment's bounding patch (refusal 4, unchanged); a population of other gate counts beside two-gate laws
  (today's `NotImplementedError`, `models/surface_pump_v3.py:619`, H1's seam); a reaction that writes a
  channel-carried row whose law declares no material term (today's words); replacement beside it (next line).
- **Replacement (row 6).** `scheduled_cell_replacement@1` and `@2` read a donor's gates from a table of today's five
  laws. `law_channels` (`operators/cell_replacement.py:194-209`) raises `ValueError: 'kv1p1_mh2@1' is not in list`
  for any other law (M2). It becomes a `ConfigError` that names the operator, the population and the law: "{law}
  carries no donor gate table in {operator}; a replacement copies gates of {the five} only". The same refusal covers
  D213's Kv1 laws and all of D211's. Widening the table is a feature for its own consumer, not this note's.
- **Restart:** the gates and ledgers are already in the checkpoint.
- **Provenance:** the flux is the constant-field form (Goldman 1943; Hodgkin and Katz 1949), a form with no number.
  The gates' numbers are BETSE v1.5.0's channel class, read as text by the port, as the Kv1 laws cite theirs.
- **Same equations:** yes.

### 5.6 Not claimed

- That calcium channels obey a constant-field flux in any tissue. D351 records two indications against carrying one
  permeability across voltage for other ions.
- Any calibration, calcium-dependent inactivation, gating charge, or temperature dependence.
- The other 21 calcium and HCN laws of D211's list. The interface then holds them; their modules are D211's, after
  this cleanup.

## 6. The store (G-4)

### 6.1 The entity

| | S1. A compartment with its own capacitor | S2. Pools at the cell's potential | S3. A row in the cell's node |
| --- | --- | --- | --- |
| Voltage | phi_store - phi_cytosol = q_store / C | zero by construction | none |
| Charge seen by the plasma patch | cytosol and store together (Gauss) | the same | the same |
| Volume, concentrations | its own | its own | the cell's |
| Counter-ions | K through its leak, with heat | left out | left out |
| Energy | 1/2 C V² and every route's heat | no capacitor term; pump and release lose 2 F V | no transport |
| Subspace (bounded by no membrane), or a route between two stores | not possible: one bounding patch, to the owner | yes | no |
| On main | yes, with refusal 6's door | no: a pool entity, a patch that faces a pool, and a zero-voltage host (the core owner's, 3 to 5 days in the cardiac note) | the rows exist, but at the cell's volume |
| The ensemble's equations | exactly these (below) | a changed model | a changed model |

**Recommended: S1 for the ensemble; S2 stays the cardiac plan's.** They are two declared representations of a store
(D175), never two laws: the pump, the routes, the buffers and the factors are the same laws on either, because each
reads its host's ends and voltage.

**Why S1 is the ensemble's model.** Legacy has V_ER = V0 + (F 1e-15/C) sum z dn_store, and a plasma voltage from the
whole cell's charge (`legacy/models/spatial_calcium.py:1-6`). @3's capacitor solve gives the store's row C_b
(phi_store - phi_cytosol) = q_store, and the owner's row C_m V_m = q_cytosol + q_store
(`docs/CLOSED_COMPARTMENT_DESIGN.md` §3.1). They are the same two equations, with the anchor q_store(0) = C_b V0.

**How far S2 is from it, here (S).** S2 is the limit of a large K leak when K is equal on both sides, as it is in
these worlds. The store voltage measured in the probe is -74 µV after 1 ms, so 2 F V/(RT) is 0.6%. Small, and still
a changed model. Modelling studies hold that the SR's own channels and K channels keep its voltage small (Gillespie
and Fill 2008; Zsolnay, Fill and Gillespie 2018 [abs]). They are models, not measurements of these stores.

**What a held bath would change.** The map's finding 4: the worlds are closed. A bath would add a supply, void the
global ion balance, and is not needed.

### 6.2 Refusal 6, version 1.1

- **Today:** a compartment's owner must lie in a capacitor component that holds a held bath.
- **The rule (L4):** the compartment's node is not its component's representative. The solver picks the gauge where
  the component holds it, else the component's lowest outside node (`numerics/surface_field.py:299-304`).
- **Closed worlds** (one gauge, no held bath): the gauge is the representative, and refusal 1 already says a
  compartment is never the gauge. The ensemble's gauge, `local`, is in its owners' component.
- **A floating component without the gauge** is admitted where its lowest outside node is not a compartment, and
  refused by name where it is.
- **Measured (M):** in a closed store world the store's node is free and the bath node is fixed; 80 steps hold the
  capacitor rows to 5e-29 C, the material to 1e-20 fmol and the energy to 2e-7 of the flows. In the two-cell closed
  world both stores are free nodes, local, near and far are fixed, and near and far give two free offsets.
- **Not extended:** FR-1's silence claims S1 to S3 stay claims of the held-bath topology until a row shows them in a
  closed one. A provider of areas, capacitances or masks (trafficking, for one) still refuses a floating component
  by its own check, and replacement still needs a held bath in the replaced cell's component.
- **D148:** host only. No program changes.

**The dated section for `docs/CLOSED_COMPARTMENT_DESIGN.md`,** written with the change, as refusal 5's version 1.2
was. Its date is the landing's:

> ### 3.5.1 Refusal 6 version 1.1: the component's representative (the calcium store; the lead's ruling, 25 November 2026)
>
> **Why.** Version 1 asked for a held bath in the owner's component, so that the compartment is a free node of the
> capacitor solve. The reason is the free node, not the bath. A closed world (one gauge, no bath) has the gauge for
> its representative, so a compartment there is a free node too.
>
> **The rule.** The compartment's node is not its component's representative: the gauge where the component holds
> it, else the component's first outside node in the definition's order, and none where it holds a held bath. One
> helper, `surface_field.representative`, gives it to `bind` and to this check, so the two cannot drift.
>
> **The message:** "{law}: compartment {node} is the representative of its capacitor component (no held bath and no
> gauge is in it, and {node} is its first outside node); the capacitor solve fixes a representative, so its row would
> carry the component's net charge. Declare another outside node of the component first (refusal 6, version 1.1)".
>
> **What stays.** Refusals 1 to 5 and 7; the parse as the place (it reads the base definition alone); the silence
> claims S1 to S3, which are claims of the held-bath topology; FR-1's judged run, which covers the build it judged.
>
> **FR-1's R6 pair.** The protocol's R6 world (a gauge in place of the held bath) is admitted by version 1.1. The
> registered protocol and its record are not edited. The driver's R6 world becomes one that still refuses, a floating
> component whose first outside node is the compartment's, under the same class key and label; `classify()` gains the
> new phrase beside the old, so old records classify as before. This section is the dated amendment that a re-judge
> would cite.
>
> **Text.** The scope string of every compartment world's summary names version 1.1. No saved result holds it.

- **The scope string** (`operators/compartments.py:698-707`) becomes "refusal 4 version 1.3, refusal 5 version 1.2,
  refusal 6 version 1.1: a node that its capacitor component does not take as its representative, at a fixed volume;
  on a bounding patch ..." and on as today.
- **Pinned places:** the unit row at `tests/unit/test_cell_owned_compartments.py:510` is replaced by one that still
  refuses (the compartment's node is its component's representative) and one that is now admitted (a closed world
  with the gauge in the component); the scope row at 1510-1516 reads the new start; the driver's phrase is at
  `validation/tissue/compartment_acceptance_qualification.py:112` and its world at 699 and 730. The class label in
  `compartment_acceptance_protocol.py:43` and the JSON (55, 440, 479) stay.

**The entity's facts.** State: none of its own; its rows are @3's outside rows. Ledgers: §6.7's row. Integrator: the
capacitor solve at every stage. Refused by name: the declaration's refusals 1 to 7, with 6 as above. Restart: the
charge anchor is imported (refusal 5). Provenance: the parallel-plate organelle capacitor (Grabe and Oster 2001, as
`docs/CLOSED_COMPARTMENT_DESIGN.md` §3.2 read it). Same equations: yes.

### 6.3 The pump

**One equation, whatever its host.** N is the side it pumps from, P the side it fills, n ions per ATP, valence z,
held ATP, ADP and Pi at N:

```text
x = [mu(ADP) + mu(Pi) - mu(ATP)]/RT + ln(ADP Pi / (ATP c0)) + n ln(c_P / c_N) - n z psi
S = [1 + (K/c_N)^n]^-1 [1 + K_ATP/ATP]^-1
J = k a S (1 - e^x)     fmol cycles/s;   current N to P = 1e-15 F n z J A
```

With z = 2, n = 1, N the cytosol and P the store, -2 psi = -2 F V_b/(RT) = 2 F V_ER/(RT): the store pump of legacy.
With P the outside, it is the plasma pump. **Measured:** the planted law equals both legacy kernels bit for bit at
the ensemble's start (M); the second reader finds it within 4.8e-15 of the one-way rate at 5,000 random states (M2).

| | P-A. Per-stage terms for @3's own pump | P-B. A cycle law on the transporter kind (recommended, L2) | P-C. @3's pump on the plasma patch, the cycle law on the store |
| --- | --- | --- | --- |
| What | refusal 4 admits @3's calcium pump; `membrane_rate` and `material_rate` gain its slopes at both ends | the new law, on any host the table knows | the map's first form |
| Law count | one | one in the world; @3's own stays for other worlds until it moves | two hosts for one equation in one world |
| Fuel | constants, no rows | three held rows | both |
| Hosts | patches | patches now, a pool route when the core adds that host kind (`models/surface_pump_v3.py:3775`) | mixed |
| Core edit | yes, static, for one law | none | none |
| Cardiac uptake and sarcolemmal pump | cannot serve the SR | serves both, as two populations for the phosphorylated form | serves the SR only |
| Price (S) | 1 to 1.25 days | 0.5 for the law, 0.75 to 1 for the kind's bound | as P-B |

**P-B, for both of the ensemble's pumps.** The store needs the fuel rows in any case, so the plasma pump adds none.
@3's `ca_atp_mass_action_positive@1` is the same equation: bit for bit on 2,000 random states when the constant is
converted, dG0(1 M) = dG0(mM) + RT ln 1000 = -19,875.97 J/mol here (M). A definition that puts both laws on one
patch for one species is refused: one representation of a pathway per patch (D175).

**The law: `atp_driven_transporter_mass_action_positive@2`.** The neutral law's factored form with the role's
valence free (`CycleForm` roles `("role", None)`), held fuel only in this build.
- **Why a new major, not a calcium name:** the mechanism is ATP-driven transport of one species. Nothing in it is
  calcium's.
- **Its potentials:** the three fuel rows' are the species registry's, at its c0. D152's standard concentration is
  checked against it (`check_potentials`), and both are 1 mM here, so the drive is the ensemble's numeric-mM
  quotient.
- **Finite fuel under a charged role** waits for a consumer (G-6).
- **Its declared step terms:** `stage_term` and `material_term`, so refusal 4 admits it at a compartment's node. The
  kind supplies both. It declares `forms="base"` and `reads=("rapid_binding@1",)`, as the exchanger does, so the
  cardiac plan's closure may hold its ion (S).

**What retires, and when (row 13; D210; pre-alpha, no backwards compatibility).** After @2 there are four laws for
ATP-driven transport of one species. From @2's landing no new definition takes another of them, and each old law's
docstring names @2. The dates are the lead's.

| Law | Who runs it | Retires |
| --- | --- | --- |
| `atp_driven_transporter_mass_action_positive@1` (a neutral role) | FR-50's judged worlds (version 1's layout) and tests | superseded at @2's landing: at z = 0, @2 is @1's equation. (i) Then, as its own commit after step 5, 0.5 day more (S): FR-50's driver and the tests move to @2 in the general form, version 1's neutral slots leave, and FR-50's records stay at their tag. This is the user's standing direction, and recommended. It changes FR-4's and FR-5's layouts and programs, so it is a D148 round. (ii) Or with version 1's layout, when those worlds are judged again |
| `proton_atp_mass_action_positive@1` (a proton role) | FR-4's and FR-5's judged worlds | the same re-judgement folds it into @2 with the form's pH band (`PhBand`), its c° of 1 M converted through the registry. Until then it stays: it has a band and a closure read that @2 does not declare |
| `ca_atp_mass_action_positive@1` (@3's own) | @3's worlds | when the Na/K and Ca pumps move onto the kind (`docs/CORE_LAWS_ROADMAP.md:255`, family 2, 2 to 4 days) |
| `nak_atp_mass_action_positive@1` (@3's own) | @3's worlds | with the same item, into its own cycle law: it moves two ions, so it is another mechanism |
| legacy's two calcium pump kernels | legacy | at the deletion (§13) |

**The kind's material bound, corrected (rows 2 and 13; kinds owner's file).** Where a population's law declares
`material_term`, all its moved rows count, charged or neutral, crossing or not, protons included:

```text
lambda_p = sum over modes m and moved rows k at both ends of |nu_mk dJ_m/dn_k|      1/s
rows[k] += lambda_p at every row k the population moves;   a node's rate is the largest row sum there
```

- **Why the sum (S).** One mode's Jacobian is nu g^T, rank one, with g_k = dJ/dn_k. Its only rate is the sum of nu_k
  g_k over all its rows, at both ends. The largest over species is up to the number of species too low: in the
  closed store world the exchanger's own rate is 1.006 per second, the sum gives 1.006 and the largest over species
  0.953 (M); at equal rows it would be half (S).
- **Why every row takes it (S).** Near a steady state a population's block is, up to a scaling of the rows by their
  amounts, u u^T with |u|² = lambda. For several populations, sum_p (u_p . x)² <= sum_p lambda_p sum over p's rows
  of x_k² <= (the largest row sum) |x|². So the rule bounds the whole block, and for a route with two ends it is
  D310's.
- **Left out:** held rows, and rows at held baths.
- **A row that a general closure holds** takes its slope through the closure's derivative. That branch
  (`_closure_slopes`) is traced today only where a mode changes a charged row at one end; it is traced for the new
  rows too. Without it the exchanger's declared closure read would use free amounts, too tight by total over free.
- **A row that version 1's proton buffer holds** has no derivative (`kinds/proton_buffer.py:804-807`). A law that
  declares `material_term` and moves such a row is refused by name, so nothing is bounded wrongly.
- **Static (D148).** A layout field `cycle_material` [population] and a flag of the axis's structure entry, present
  only where a declared law has `material_term`, as K3b's. No cycle law declares one today, so no world's fields or
  programs change. Populations whose law does not declare it keep today's rows.
- **Sizes (M).** At the store world's start: exchanger 0.95 (held bath) or 1.01 (closed), plasma pump 0.33, store
  pump 0.50; the row of free calcium in the cell sums to 1.8 per second.

**The proton rows (the neighbour of row 2).** A proton row that a cycle law moves at both ends has no material bound
in either layout. Where it moves charge, its charge slope holds it, if its node has a charge row and n_eff >= n_C /
z². Here n_C = R T C 1e15/F² in fmol, and n_eff = dn_total/d ln c_free. With the buffer, FR-4's charge rule is 67
times tighter than the proton's material rate at the lumen and 15,000 times at the cytosol. Without a closure it
would be 527 and 13 times looser (S, `proton_rows`). Where the cycle moves no charge (§1, row 13) nothing holds it.
- **The population axis: covered** by the rule above, by declaration. The mitochondria's seven laws that move a
  charged row at both ends (complexes I, III and IV, the synthase, the nucleotide exchange, the phosphate symport,
  the K/H exchange) take `material_term` with step 5, one line each: no judged run declares them (MT-1b is a draft),
  so MT-1b registers with the bound in place. Their unit worlds' programs change. Recommended, and for the lead
  (L12).
- **The proton pump** declares nothing new now: its judged worlds run on version 1's layout, next.
- **Version 1's layout: not covered.** It runs the two laws of FR-4, FR-5 and FR-50 by name, and a term there would
  change their judged programs. Its docstring states the condition above and the two numbers. It retires as the
  table says.

- **State:** `cycle_count`, `cycle_dissipated_energy_pJ`, `cycle_metabolic_work_pJ`, `cycle_supplied_fmol`
  (existing).
- **Ledgers:** role -n at N and +n at P per cycle; charge through the field; heat -J x RT, work -J times the fuel's
  drive, the held fuel's supply recorded. **Roles:** heat and work.
- **Refused:** |x| above 80; K or K_ATP not positive; n outside 1 to 4; fuel rows that are not neutral or that
  another route moves; @3's calcium pump on the same patch for the same species (a host-side check in the kind: one
  law moves a species by this mechanism on a patch); a moved row that version 1's proton buffer holds; RK4.
- **Provenance:** the form is the engine's own mass-action completion
  (`laws/pumps/nak_atp_mass_action_positive.py`), no number taken. One calcium per ATP is the ensemble's declared
  stoichiometry. A two-calcium cycle is the biological SERCA's (Tran et al. 2009 [rec]); n = 2 is a parameter.
- **Not claimed:** a SERCA or PMCA mechanism, proton counter-transport, or any kinetic constant.

### 6.4 The leaks

- **K on the bounding patch:** @3's own constant-field permeability. K is a major ion, so the charge rule holds it.
- **Calcium on the plasma patch, the bounding patch and the junction:** `passive_constant_field_permeation@1`
  routes: charge slope, material slope and heat exist, and a junction host exists (D310). In these worlds no
  junction crosses a floating component, since both cells lie in the gauge's, so D310's refusal does not arise: the
  two-cell closed world parses with its junction route (M).
- **The inward flux:** J = 1e15 A P m [c_out B(x) - c_in B(-x)], the ensemble's, with the sign of §3.
- **Measured:** the store's leak and the plasma leak equal the legacy kernel's value (M).
- **Facts.** State: `passive_transferred` and its heat. Integrator: explicit at each stage. Refused by name: a
  patch's own permeability for a carried row, a neutral row on this law, a closure-held row, RK4. Restart: existing
  fields. Provenance: the constant-field form, no number. Same equations: yes. Not claimed: one permeability across
  voltage (§5.6).

### 6.5 The release: the route, and what it asks of its source

**The route is this stream's, the source is E's.** The release is one more `passive_constant_field_permeation@1`
route for Ca on the bounding patch:

```text
m = (the patch's availability) x f_IP3(c_IP3, cytosol) x f_Ca(c_cytosol)     the product of the sources in its `factors` list, in that order
J = 1e15 A P_release m [c_store B(x) - c_cytosol B(-x)],  x = 2 F V_b / (RT)    fmol/s into the cytosol
```

Nothing changes in the route: its `factors` list, its routed control and its slopes at the routed opening are on
main (R). E's source is `species_condition@1`, one condition for calcium and one for IP3.

**What the route needs from any source of its kind:** its value at each explicit stage, on the stage's read, in [0,
1], finite; and the concentration it reads through the stage read, so a closure's free calcium is what a closure's
world sees.

**The feedback bound (L3, built). The contract is E's section 5.5, at 66ffa1d7, word for word** except the shape
noted below. Calcium released raises the calcium the factor reads, and the stage rules use the routed value but not
its slope (§1, row 14).

| Hook | Side, owner | Gives |
| --- | --- | --- |
| `factor_rows(declaration)` | source (E) | host, once: per source in `factor_sources` order, the (species, node) pairs its factor reads, names only |
| `factor_log_slopes(read, p, *, xp) -> [P]` | source (E) | at a stage: d ln f / d ln n of each pair, dimensionless, signed |
| `routed_rows(declaration)` | sink (this note) | host, once: per routed slot in `routed_controls` order, the (species, node a, node b) of each row it moves |
| `routed_flux(read, potentials, control, p, *, xp)` | sink (this note) | at a stage, at the ROUTED control: fmol/s of each row through each slot |

A kind that has one hook of its side must have both; registration refuses one alone by name, as the source side is
being built on `species-condition-build` (`kind_factor_rows` there reads and checks the names; the sink takes the
same shape, `kind_routed_rows`). @3 is the sink of its own channel slots and has the same two in the core: its rows
are the population's permeant ions, its flux `channel_rates`'.

**The static pairing.** `InnerStructure.loops = ((m, p), ...)`, positions only. m is a (slot, row) of a routed slot,
in the order of the structure's `routes` (canonical kind order, then @3's channels) and then `routed_rows`' order. p
is a pair of one of that slot's sources, in canonical kind order, then `factor_sources`', then `factor_rows`'. A
pair is taken where its (species, node) is an end of a row the same slot moves and the node is not a held bath.
Every row of the slot pairs with every such p. `loops` is empty where no routed slot reads a row it moves, and where
a source has no hooks.

**The layout fields,** present only where `loops` is not empty, on FR-51's pattern: `loop_pair_row`,
`loop_pair_node` [P]; `loop_flux_row`, `loop_flux_end_a`, `loop_flux_end_b` [M]. **The core can add them (R).**
`_kind_types` and `kind_types` gain one flag, as they have for a block (`models/surface_pump_v3.py:5354, 5442`),
`initial_values` fills them from the IDs (332), and the composite carries any extra inner layout field by name
(`models/pump_composite.py:1423-1432`), as it carries FR-51's in `tests/unit/test_fr51_blocked_run.py:121`. The slot
of each m is static, from `structure.routes`. `structure(model)` needs no capacity.

**The rule,** in `material_rate`, after its stage read and the door's `_route`, at every place the rule runs:

```text
rate(m, p) = (|J_m| x |slope_p|) / max(n_p, tiny)        1/s; J in fmol/s, n in fmol, tiny the smallest normal float64
rows[species_m, end a of m] and rows[species_m, end b of m]  +=  sum over the pairs p of m of rate(m, p)
a node's rate  +=  the largest over species of its rows
```

- **f is inside the product.** J is routed, so it holds f, and the product is formed before the division. A
  zero-amount row gives 0/tiny = 0, finite; the division first gives NaN (M2, `feedback_zero`). It is finite there
  but not a bound at exactly zero. On @3 no row reaches zero (`models/surface_tissue.py:414`): unreachable today,
  covered anyway, with a row (§14, row 11).
- **The held control is never used:** at 1e-9 fmol it would read 4e7 per second (M2).
- **Both ends, per moved row** (row 3). For one row, as the release's, this is the loop's own rate. For a slot with
  several rows it is a row sum of the block, a bound that can be looser than the mode's own rate by |J_m|/|J_p|. The
  core could take the read row's J for every row of the slot later, with the same hooks.
- **Its size in the ensemble (S):** J_r 0.0157 fmol/s, d ln f/d ln c = 0.38, 0.001 fmol free: 6 per second, 7.5e-5
  per 12.5 µs step. Nothing there binds.

**One difference from E's text, on the sink's side only (L10).** E writes `routed_flux(...) -> [M]`. A kind's stage
hooks see no declaration, so the passive routes cannot know which of their slots are routed, and a layout field for
it would change FR-5's layouts, whose sources have no hooks. So the hook returns the kind's flux array in its
control field's slot order, `{control field: [species, slot]}` (for the passive routes, the `flux` of `_flux`,
`kinds/passive_routes.py:702`, as it stands), and the core takes J_m at (`loop_flux_row`[m], the static slot of m).
One J per slot and row, at the routed control, as ruled. The source's hooks, the pairing, the fields and the rule
are E's. Binding traces both stage hooks once, as it traces `factors` (`models/surface_pump_v3.py:3589-3612`), and
refuses a wrong shape by name.

**Limits, stated (row 7), in this note and in E's:**
- loops through two routes (one moves X and gates on Y, another moves Y and gates on X) are not bounded;
- **loops through a source without the hooks are not bounded: today `ph_condition`,** which reads the proton row. It
  is used (FR-5), so it is not refused; its docstring says so, and the hooks for it are a follow-up to log.
  `patch_damage` has no hooks either and needs none: its factor is its own state d, which no route moves, so no loop
  closes through an amount. Its docstring says that;
- where a closure owns the read row, n is the free amount while the route moves the total. No captured world has
  one.

**`loop_term` (row 13): removed, with the reason E gives.** `ChannelLaw.loop_term` (`registry/laws.py:377`) is
declared by no law and read by nothing. `CycleLaw.loop_term` (446, 482) is declared by the proton pump alone
(`laws/pumps/proton_pump.py:137, 265`) and evaluated by nothing. What it reserved, a law's own loop through a
closure's read, is the transporter's material term with the closure's derivative (§6.3), which takes the slopes from
the form, not from a declared kernel. A channel's loop is bounded through `routed_flux`. `loop_rates_per_s` stays as
a tested function, documented as not evaluated by the engine.

**One source of factors.** For channels and routes the door is the one place, and `species_condition@1` the one
concentration source, where the shapes agree; E's section 5.10 says where they do not (held factors, junction and
operator targets, basal, switches, RK4) and what retires when. This note adds no second source.

**Integrator, heat, restart.** Explicit at each stage, at the stage's own calcium, as legacy's. A route books heat
only. The factor books nothing. No state of its own. **Refused by name:** an unknown source, a source outside [0,
1], a factor held through the step (a changed model), one hook of a side without the other. **Provenance:** the flux
is the constant-field form; the factor's is E's. **Same equations:** yes, with the factor at each stage.

**Not claimed:** that IP3 multiplies the release by an activation factor. One patch-clamp study fitted Po against
calcium with a biphasic Hill curve and found IP3 moving only the inhibition constant (Mak, McBride and Foskett 1998
[abs]). That is one study's indication, and it speaks against the ensemble's synthetic product. Bell-shaped calcium
dependence itself has two independent reports here (Bezprozvanny, Watras and Ehrlich 1991 [rec]; the 1998 work
[abs]). No law's form changes on one study.

### 6.6 The buffers

- **The same law as legacy's:** `ideal_detailed_balance_mass_action@1` of `local_species_reactions@1`, whose kernel
  is the same function (`laws/reactions/mass_action.reversible_flux`): Ca + B = CaB (k_f 1000 per s, dmu -6.9078)
  and Ca + CaB = Ca2B (100 per s), in the cytosol and in the store.
- **Charge:** B -2, CaB 0, Ca2B +2. Every reaction conserves charge. B, CaB and Ca2B are impermeant rows.
- **Why it is admitted:** calcium has no @3 membrane, junction or (with §5.4) unbounded channel route; its movers
  are kinds. The admission is D152's own rule, not a new one, and the probe ran it (M).
- **Energy:** exact bookings: heat -dG of the written rows, no work, and the standard-potential term the operator
  owns.
- **Stage condition at the start:** the largest unidirectional rate is 200 per s in the store and 51 in the cytosol,
  so dt L is 2.5e-3 at 12.5 µs (S).
- **Two steps between the laws:** the buffers run in Strang halves around @3's step, so calcium is buffered once
  before and once after the transport, where legacy evaluated both in one RK4 stage. Second order (§12).
- **Refused by name:** a reaction that does not conserve charge or a moiety; a row another operator writes by local
  kinetics; a step with h L above 1; RK4. **Restart:** its accumulators are saved. **Same equations:** yes.
- **Not claimed:** a calibrated buffer, or that its three forms are a real protein's.

### 6.7 One table of state, ledgers and closure

| Mover | Its own state | Material | Charge | Energy |
| --- | --- | --- | --- | --- |
| K leak, Ca leaks, release | `passive_transferred`, heat | equal and opposite at its two nodes | z F J through the field | heat >= 0 |
| Store pump, plasma pump | cycle counts, heat, work, supply | 1 Ca per cycle at each end | 2 F J | heat >= 0; work is the fuel's drive |
| Exchanger | cycle counts, heat | 3 Na in, 1 Ca out at each end | 1 F J inward | heat >= 0; no work |
| Ca channel | gates, transfers, heat | as a leak | 2 F J | heat >= 0 |
| Buffers | reaction extents, heat, standard term | none created; stoichiometry | zero per reaction | heat >= 0; standard term stored |
| Store node | none | its rows | q_store = C_b (phi_store - phi_cytosol) | 1/2 C_b V_b² in the capacitor term |
| Factor (E) | none | none | none | none |

**Heat near a reversal.** A route whose power falls by more than 59% within a step books a negative increment under
the tableau (ARS(2,2,2)'s weights), and the dissipation check refuses beyond 1e-12 pJ. Channels, @3's patches and
the transporter admit the trapezoid, which cannot be negative; the K leak can take it as a patch. The passive routes
do not (§16.2, L9). In these worlds the calcium routes stay far from reversal, and the K leak's power near its own
zero is below the tolerance (S). The second reader ran the ensemble's independent references: no change of sign of
the K leak's, the store's calcium leak's or the junction's driving force after the start (M2).

**Closure measured:** energy-rate balance -1.4e-16 of 0.85 pJ/s; the largest relative ledger over 80 host steps at
12.5 µs is 1.6e-7, and it falls by four per halving (1.6e-7, 4.1e-8, 1.0e-8); the composite's, with buffers, after 5
steps at 6.25 µs is 9.5e-9 (M). The engine's own limit is 2e-3 of the flows plus 2e-8 pJ.

### 6.8 Not claimed

- A biological ER, SR or any calibrated constant. Every value is synthetic.
- That the voltage, the counter-ion and the pump stoichiometry are right for any cell.
- S2's equivalence to S1 in any regime.
- The division, fusion or growth of a store: FR-1's later doors.

## 7. The exchanger (B2) and two symport laws: modules, no engine change

### 7.1 The exchanger

**The equations,** positive J moving 3 Na in and 1 Ca out, with a = Na_in/Kn, b = Na_out/Kn, c = Ca_in/Kc, d =
Ca_out/Kc, u = FV/(RT):

```text
D = (1 + a^3 + b^3)(1 + c + d)
J = k v [b^3 c e^(-u/2) - a^3 d e^(u/2)] / D          fmol cycles/s
x = 3 ln(Na_in/Na_out) + ln(Ca_out/Ca_in) + u;  J = k v S (1 - e^x);  S = b^3 c e^(-u/2) / D
```

**The form** (`laws/cycles/forms.py`, monomial; N the cell, P the outside; c° = 1 mM, so each K is a number in mM):

| Part | Value |
| --- | --- |
| Roles, rows | Na (+1), Ca (+2); (Na,N), (Na,P), (Ca,N), (Ca,P) |
| Mode `exchange` | counts (+3, -3, -1, +1): charge 0 over both ends, one charge inward |
| Orders, `zeta` | Na@P 3, Ca@N 1; -1/2 |
| Two factors, power 1 | 1 + Kn^-3 Na@N^3 + Kn^-3 Na@P^3, and 1 + Kc^-1 Ca@N + Kc^-1 Ca@P |
| Constants | Kn^-3, Kc^-1 |
| Parameters | `km_na_mM`, `km_ca_mM`, positive; capacity and availability are the kind's |
| Declared | `stage_term`; `forms="base"`, `reads=("rapid_binding@1",)` (a pure exchange of ions: its rows are base forms, so a closure may hold them). `material_term` joins with §6.3's bound (step 5), so that nothing declares a term its kind does not yet hold |

- **Checked (M):** the planted module parses in the store world and gives the legacy kernel's rate to 1.9e-15
  relative; the second reader finds 1.4e-14 of the one-way rate at random states (M2). Its free energy needs no
  registry potential, since nothing is converted.
- **State, ledgers, heat:** as §6.7's row. The trapezoid booking is admitted.
- **Same equations:** yes. The kind's domain is x <= 80, one-sided; legacy's is |x| <= 80 and |V| <= 0.15 V. Those
  differ only outside the worlds' range.
- **The user's answer (D386, A2):** it is registered now, **labelled synthetic: only its reversal is supported.**
  Whether it stays beside the cardiac plan's law or retires is decided when that law lands. So its provenance is
  "parity" (moved from an older family), not "cited".
- **What supports its reversal.** Measured reversals close to a 3:1 exchange (Matsuoka and Hilgemann 1992, the third
  of a series on giant patches, the one PMID 1336540 names [abs]), and a whole-cell study of guinea-pig myocytes
  finds 3:1 (Hinata et al. 2002 [abs]). **Against it:** one 2000 study of the same cells in inside-out patches
  concluded 4:1 or variable (Fujioka, Komeda and Matsuoka [abs]), and a 2004 study reports minor transport modes
  beside the 3:1 (Kang and Hilgemann [abs]). 3:1 is the form's. The evidence for it is not one study's, and neither
  is the evidence against it.
- **The denominator and the equal barrier are synthetic.** The same 1992 work reports that voltage dependence
  changes with calcium and sodium on either side, which a fixed half split does not do [abs].
- **Not claimed:** a calibrated exchanger, its inactivation, calcium activation, or any other mode.
- **The name:** `sodium_calcium_exchange_symmetric_barrier@1`. The live constant says
  `ncx_3na_1ca_symmetric_barrier@1`; names state a mechanism and its form, not a protein family.
- **The plasma pump (B1)** is re-parameterised, as the map says. Nothing else is designed for it (§6.3).
- **Order.** It depends on nothing above, and D386 puts it in the first stage, with G-7's driver.

### 7.2 Two symport laws of D211: NKCC and the configured symport

D386 ports both in the cleanup, as law modules on the transporter kind, after a check of their tanh form. This is
the check. They ship with this note's pieces. Both are **manufactured forms with no outside source**
(`legacy/processes/cotransport.py:1`); they are labelled so, with provenance "parity".

**The law.** One inward cycle moves nu_s of each species; A is its affinity, and the capacity is C:

```text
J = C a tanh(A / 2RT),   A = RT sum_s nu_s ln(c_out,s / c_in,s);   with N the cell and x = -A/RT:
tanh(-x/2) = (1 - e^x)/(1 + e^x),   so J = k a S (1 - e^x)  with  S = 1/(1 + e^x),  e^x = prod_s (c_N,s / c_P,s)^nu_s
```

So S is one factor of the monomial form: power 1, one term with K = 1 and each row's own count as its order, plus at
N and minus at P. The one-way rates are k a/(1 + e^x) and k a e^x/(1 + e^x), so they sum to k a. c° cancels, since
the orders sum to zero. No new form, no kind edit. The free energy needs no registry potential.

**Checked (M, `nkcc_probe`, 4,000 random states over five decades; in a third of them each ion's two concentrations
differ by at most 0.7%):**

| Stoichiometry | abs(J - legacy) over the one-way sum k a, worst | relative to abs(legacy), worst | heat, relative |
| --- | --- | --- | --- |
| 1 Na : 1 K : 2 Cl (NKCC) | 7.6e-15 | 8.1e-12, at abs(x) = 1e-5 | 1.6e-11 |
| 1 K : 1 Cl; 1 Na : 1 Cl; 1 Ca : 2 Cl; 2 Na : 1 SO4; 1 Na : 1 Mg : 1 Cl : 1 SO4 | 5.1e-15 to 9.9e-15 | 4.5e-12 to 2.4e-10, at abs(x) from 2e-6 | 8.9e-12 to 4.8e-10 |

The relative figure grows only near equilibrium, where both sides subtract logarithms: about 1e-16 of their terms
over abs(x). The voltage slope is exactly 0. `errors()` is empty for each, and all six parse on one patch. The sign
is right in both orientations.

**NKCC: port it as its own module,** `na_k_2anion_symport_reversible_tanh@1`, roles Na (+1), K (+1), anion (-1),
counts 1, 1, 2, no parameter beyond the kind's capacity and availability. The name follows `k_anion_symport_*` and
`na_anion_symport_*`. **0.4 agent-day (S):** the module 0.1, its page 0.1, rows 0.2 (the closed form at random
states and its reversal in `test_cycle_kind.py`, the planted stoichiometry 1:1:1 and the planted sign must fail; the
heat is never negative; and, with step 5, its material bound).

**Could it be KCC's sibling instead?** KCC is canonical as `k_anion_symport_mass_action@1`, an operator beside the
water operator: k a f(V) times the difference of the two sides' products K A, with a volume factor f. A sibling's
rate would be k a f(V) times the difference of the products Na K A². Not recommended here:
- it is another equation than D211's law, so a changed model for anything that used legacy's;
- it runs only beside water (`operators/k_anion_symport.py`, its contract), where the kind's law runs on plain @3
  too, with several populations per patch, availability schedules, one-way records and labels;
- it needs the operator's roles, counts, rate bound and energy check generalised: 2 to 2.5 days (S).

What the kind's law lacks is the volume factor: the kind reads no volume. If a cited NKCC is wanted, the mass-action
form is also one monomial module here (S = the product of P's activities, as `potassium_proton_exchange@1`), and the
volume factor is the water operator's. **D210:** the tanh law is then declared a representation of the cited one
(D175) or retires.

**The configured symport: port it as one module with two roles,** `electroneutral_symport_reversible_tanh@1`: roles
cation and anion with their valences free, counts `n_cation` and `n_anion` (integers 1 to 2, legacy's range), each
exponent an `Affine` of its count. Checked (M, `symport_forms`): `errors()` is empty; K : Cl 1:1, Ca : Cl 1:2 and Na
: SO4 2:1 match to 5.4e-15 of k.
- **It needs one refusal.** A binding that is not neutral is admitted today: K : Cl 1:2 and Ca : Cl 1:1 parse, move
  one charge per cycle, and no longer follow the tanh, since S has no voltage term (M). So `CycleLaw` gains one
  defaulted field, `electroneutral`, and the kind refuses by name a population of such a law whose modes move charge
  ("{population}: {law} is electroneutral; {species and counts} move charge {q} per cycle"). It is a general
  statement a law can make, about 15 lines, host only, with no program change.
- **What legacy's kernel had beyond it:** any number of species. No definition could declare more than KCC and NKCC
  (`legacy/core/surface_cotransport_spec.py:159-161`), and its tests use those two, so nothing tested is lost. A
  salt of three or more ions is a module like NKCC's, about 25 lines of data.
- **Not a second KCC.** Its page says that the canonical KCC is `k_anion_symport_mass_action@1`.
- **0.4 to 0.5 agent-day (S):** the form 0.1, the refusal 0.15, rows 0.1 (the closed form; the refusal; the planted
  non-neutral binding), its page 0.1.

**Both, for the engine.** State, ledgers and heat are the kind's (`cycle_count`, heat, no work). They move charged
rows with no net charge, so nothing bounds them today (§1, row 13): they declare `material_term` with step 5. At a
compartment's node refusal 4 refuses them with or without it, since a charged row there needs a charge slope and
these have none. No consumer puts one there. **Not claimed:** an isoform, a calibrated capacity, regulation by
volume, chloride or phosphorylation, or water carried with the salt.

## 8. The step, and the rules it is held to

### 8.1 One composite step of size h

1. Event maps (none in these worlds).
2. D152's first half, h/2, at every reaction site (cytosol and store).
3. @3's IMEX step, ARS(2,2,2). At each explicit stage: the stage's read; the routing door, which multiplies the
   release by its factors at that read; the field solve (C + a h L) phi = q, with faces implicit; the rates of @3's
   patches, pumps, channels and junctions and of the kinds; the stage's checks. Gates take the exponential update.
4. D152's second half, h/2.

Second order in h. `cell_owned_compartments@1` runs no part.

### 8.2 The stage rules

**Every explicit stage refuses the step where:**
- charge: h times the largest charge rate exceeds 1, the rates read as §8.3 says. At the ensemble's store it is
  5,291 per second (M), the K leak's 5,257 of it (S), so 0.066 at 12.5 µs, well below the limit. The plasma rows are
  16 to 17 per second (M). FR-4's 0.05 was a limit of the energy ledger in other worlds; here the ledger holds at
  1.6e-7 (M);
- material: h times the largest material rate exceeds 1. 2.4 per second today (M), 4.2 with the cycles' charged rows
  (M), about 11 with the channel and the feedback (S);
- domain: each law's own. D152's halves hold h L <= 1 at each stage, on unidirectional rates.

**One material rule (rows 2 and 3).** A mode's own rate goes to every row the mode moves, at both ends, held baths
left out; the modes add per row; a node's rate is its largest row. It is D310's rule for a route (T_c + T_o), §5.3's
for a channel's ion, §6.3's for a cycle, and §6.5's row sum for a loop. Each kind's and each core term stays one
array per node, and `material_rate` adds the arrays, as today. **Checked (M, `material_check`):** in the store
world, at fixed potentials, the true largest rate of the calcium and sodium rows is 3.37 per second with a held bath
and 3.38 closed (finite differences of the live `explicit_rates`), and the rule reads 4.21 and 4.30. At a thousandth
of the calcium they are 20.90 and 20.94, and 22.55 and 22.59.

**RK4 is refused** for every world with a store (§1, row 8) and for every world with a calcium channel (§5.2).

### 8.3 The charge rule, corrected: before any store world (row 1)

**The gap (M, M2).** A cell's conductances are divided by the capacitance of all its patches, its stores' bounding
patches included. But a plasma current changes the charge behind the plasma patch alone, while a store floats along
with its cell. Measured on the live engine: plain @3, no kind, NumPy steps of `imex_step` at 1 ms.

| World | True dt x rate | The live rule reads | What the live engine does |
| --- | --- | --- | --- |
| A. One cell, C_b/C_m = 3.3, a silent store | 2.2 | 0.51 | admits it; V_m 0.122, 0.149, 0.222, 0.491 mV at steps 1, 2, 4, 8 |
| A, at a smaller leak | 0.9 | 0.21 | V_m decays |
| B. Two cells joined by a junction, a silent store each | 2.2 | 0.51 | admits it; the difference grows 0.114, 0.129, 0.166, 0.276 mV |
| C. Closed; near joined to the gauge by a face; the store declared first, so it is its component's representative | 2.2 | 0.51 | admits it; V_m as in A; refused at step 2 by another check |
| D. One floating node between two cells | 3.0 at the patch (2.7 true) | 0.27 | admits it; the patch's voltage doubles at each step |

It is not silent: the domain or the energy ledger stops the run (M2). It does not bind in the ensemble. World C and
world D are not in the second reader's table; they show which patches must count.

**Why (S).** Let x be a perturbation of the node potentials, and C, G and J the Laplacians of the patches'
capacitances, the patches' conductances and the junctions' conductances. Explicit currents relax at the rates r of
(G + J) x = r C x. A node that a face, a held bath or the gauge holds has x = 0: today's assumption, since the
implicit drift holds it. A floating node is free. With d_m the perturbation of patch m's voltage, x'Gx = sum G_m
d_m² and x'Cx = sum C_m d_m².
- A cell's patches on held nodes share one d, the cell's own x. Their part of r is at most sum G / sum C over those
  patches.
- Each patch that faces a floating node has a d of its own. Its part is at most G_m / C_m.
- For a junction, x'Jx <= 2 sum_i (sum_j G_j) x_i², and x'Cx >= sum_i C_held,i x_i², since a floating node can
  follow its cell at no cost. So its part is at most 2 max_i (sum_j G_j) / C_held,i.

On 20,000 random networks of each shape the patch rows are never below the true rate and reach it (true over rule at
most 1.000); with junctions the true rate reaches 1.85 times the rule, as it reaches 1.82 times today's in worlds
with no floating node, because the rule takes the larger of two terms and not their sum, inside its margin of 2 (the
explicit stage of ARS(2,2,2) is stable to 2, the rule holds 1). Against the live rule the true rate reaches 250 to
380 times, and against a node's summed row where two cells share the node, 34 times (M, `bound_check`).

**Which patches count.**
- **Floating node:** an active outside node that is not a held bath and not the gauge, and that no active face and
  no forms face names. This is `free_outside_nodes` without its last exclusion, the field layout's fixed nodes. What
  that exclusion leaves out is a component's representative that no face names, and the stage's operator solves that
  node like any other (world C). Refusal 6 keeps it from being a compartment; plain @3 admits it.
- **Loose patch:** an active patch whose outside node is floating. **Held patch:** any other active patch.
- **A cell's row:** the slopes of its held patches (@3's patches and channels, the kinds' there, FR-51's T_V), and
  its junction-hosted kinds' 2G, over the capacitance of its held patches.
- **A loose patch's row:** its own slopes plus the kinds' at its outside node, over its own capacitance. For a node
  that one patch faces, which every compartment is, this is B7's row, unchanged. For a node that several patches
  face it is a bound where B7's sum is not (world D).
- **The junction term:** 2 (sum of G_j) over the capacitance of the cell's held patches.
- **A cell with no held patch** has an infinite row where a junction or a route charges it, and is refused by name.
  `bind` gives every capacitor component a held node, so such a cell needs a floating node it shares with another
  cell.

**Where, with one helper.** `surface_pump.floating_nodes(model)` gives the floating outside nodes' IDs from the
declared topology (host; exported through `cells.modules`). It is read by:

| Place | Edit |
| --- | --- |
| `models/surface_pump_v3.py:3615-3698` (`membrane_rate`) | the rows below, static on the structure |
| `models/surface_pump_v3.py:3730-3745` (`free_outside_nodes`) | the fixed-node exclusion leaves |
| `models/surface_pump.py:464-520` (`explicit_rate_bound`: 487, 516, 517) and 543-569 (`face_free_node_rate`) | the held capacitance in the junction and membrane terms; one row per loose patch; the set as an argument, so that `StepChecks.explicit_rate` (`surface_pump_v3.py:4003-4010`) passes the one that knows forms faces |
| `kinds/transporter.py:691-718` (`bound_rate`, version 1) and 2330-2376 (`_population_bound_rate`) | the cell's row over its held patches and only for a population on one; a loose patch's own row; the gauge left out |
| `operators/species_common.py:207-247` (`counter_ion_margin`) | the same capacitance, since it states the bound's own term. It was too strict, never unsafe |
| `models/inner_laws.py:314` and `models/surface_pump_v3.py:5041` | `floating_nodes: bool = False` on the structure, and its value |

**Settled at the build (25 November 2026):** the table's third row and D148 were inconsistent. Today's rule calls
`free_outside_nodes` in every world with a kind, floating node or not, so its fixed-node expression is in those
programs. The exclusion leaves the function's meaning, and a static argument keeps the old expression, in its order
of operations, on the branch of a world with no floating node. The trace shows those worlds' texts unchanged.

`explicit_rate_bound(spec)` and `face_free_node_rate(spec, p, gm)` keep their names and arguments, since a
validation tool and tests call them (`validation/long_duration/m1_bound_terms.py:106`,
`tests/unit/test_surface_pump_step_checks.py`). The four operators that call the bound on their own projections
(`operators/osmotic_water.py:464`, `cell_replacement_v2.py:358`, `membrane_insertion.py:370`,
`membrane_insertion_v2.py:207`) inherit the rule. In a world with forms faces the definition's bound no longer
counts a node that only a forms face names, as the stage's never did.

**The per-stage rule (compiled).** In a world whose structure says so:

```text
floating = free_outside_nodes(p);  loose = membrane_active & floating[membrane_outside];  held = membrane_active & ~loose
cells    = slope x sum over held patches of G            (@3's patches and channels, at the cell)
         + sum over kinds of stage_term(read, potentials, control with availability 0 at loose patches, p with membrane_active = held)[cells]
at_node  = sum over kinds of stage_term(read, potentials, control, p)[outside nodes]
rate     = max( cells / sum over held patches of C,   at loose patches (slope x G + at_node[their node]) / C )
```

- **No kind changes.** The core reads each kind's `stage_term` twice: as it is, for the loose rows, and on a view
  where the loose patches are closed, for the cells' rows. A closed patch moves nothing, by every kind's contract:
  the passive routes read the availability (`kinds/passive_routes.py:667`), the transporter the host's activity. A
  kind that ignored both would be counted at the cell too, on the safe side. Measured: FR-4's declared world, FR-5's
  arm T and the store world give today's rates, 25.296 and 5,290.6 per second, with cell rows of 0, 0 and 15.7 (M).
- **Kind-free worlds take the loose rows too.** Today a kind-free world has no node row at a stage (the early return
  at 3676), so without this the fix would leave a channel on a loose patch in no row at all.
- **Under N2** the patches' slopes are implicit; both readings of the kinds stay.
- **`structure=None`** (host tools, tests): NumPy callers take the rule by the layout; a compiled caller has a
  structure (`registry.get_model`).

**D148.** In a world with no floating node `floating_nodes` is False and the branch is today's, so its compiled
programs, layouts and bindings are the same. The host numbers are too: over 69 such worlds of crossrev's sets and
the fixture modules the definition's and the stage's rates are equal bit for bit (M). In a world with one, the
structure key and the programs change; layouts, states, controls and checkpoints do not. Seven of crossrev's worlds
have one (three of `kinds`, four of `acceptances`). The round compares crossrev's seven sets, G1's 113 worlds and
FR's set, and runs FR-1's and FR-4's declared worlds before and after: only the refusal predicate changed, and any
last-bit difference from the compiler's fusion is reported, not assumed away.

**The scan, a build step.** Already run in part here, host only, at the initial state (M):
- 140 definitions from crossrev's seven sets and the builder modules of FR-1 (its refusal pairs too), FR-4, FR-5,
  FR-7, FR-49, delivery, trafficking, site occupancy, water, replacement and the transfer example: 47 hold a
  floating node, each face-free and faced by one patch, except FR-1's refused R2 pair. The largest C_b/C_m is 1.0
  (FR-49), then 0.625 (FR-4, FR-5), then 0.2. None is a representative, none is joined to another by a face.
- 31 of them parse and have rates: the largest dt x corrected rate is 0.028 (0.027 before). Only three differ at
  all: FR-1's W+, 22.98 to 25.28 per second, and trafficking's two, 26.80 to 28.14. **No hit.**
- **What the build step adds:** FR-7's registered worlds, whose builder takes arguments; the worlds built inside
  tests (the gate finds a hit as a changed outcome); every stage of the judged runs' saved trajectories, where
  amounts were saved, since the start is not the largest rate. A hit goes to the lead as a recorded erratum. It is
  not fixed silently.

**The plants.** Each planted world is admitted by the old rule and refused by the new (§14, row 0): A and B with all
patches counted; B with the junction term alone over all patches; C with the representative left out; D with the
node's summed row; a channel on a loose patch in a kind-free world with the loose rows dropped; FR-4's cell row with
the kinds' term read once.

**Limits, stated in the docstring.** A faced node is taken as held, as today. Two or more nodes that faces join to
each other and to no clamp (a lumen of two nodes) are still counted as held: refusal 1 keeps them from being a
compartment, and none of the 140 worlds has one. The rule takes the larger of the junction and patch terms, as
today. Outside worlds with a floating node the cell's sum still counts a patch that a closer has closed (487 and
3674 have no activity mask, 3694 has).

**How far a face holds a node, measured at the build (25 November 2026, M).** Only where the step times the face's
charged conductance is at least about the node's capacitance. A face with no charged diffusivity holds nothing: at a
true dt x rate of 2.2 the rule reads 0.2 for a conducting patch on such a node and 0.51 for one on its cell, admits
the step, and the voltage grows 0.122, 0.149, 0.222, 0.491, 1.09 mV at steps 1, 2, 4, 8, 12, as in world A. In the
second world it still grows at ion diffusivities of 1e-14 m2/s and decays at 1e-12. In the scan no world has a
conducting patch beside a face with no charged diffusivity. Three have one where the faces hold weakly (dt g / C at
most 0.011: the pump family's fixture, the padded replacement world on it, the insertion fixture's cleft cell), and
their dt x rate is at most 0.028 with those nodes floating. A compartment is named by no face. It stays a limit, in
the docstring (the lead).

**Price: 0.75 to 1 day (S). Its own commit, first, one D148 round.**

## 9. Ledgers

| Ledger | How it closes |
| --- | --- |
| Amount, per species and node | every route writes two nodes equal and opposite; D152's extents times its stoichiometry; held rows do not move |
| Amount, whole world | the sum of all nodes (the worlds are closed, so it is constant) |
| Charge | z-weighted: each node's row and the capacitor rows. Reactions add zero by construction. A closed world has no electrode: the gauge is a potential's zero, not a supply (measured: 0 C of electrode error in the two-cell closed world) |
| Energy | the change of the chemical, capacitor (with 1/2 C_b V_b²) and reaction standard-potential terms, plus heat, less work and the held nodes' supply, is zero to @3's bound (2e-3 of the flows plus 2e-8 pJ) |
| Fuel | `cycle_supplied_fmol`: ATP, ADP and Pi the maintenance would restore. The held rows do not change |

## 10. Composition

No operator is added, so `docs/PUMP_COMPOSITE.md`'s generated matrix does not change. The store's world declares
kinds, so it inherits their rules. (R) from `operators/compartments.py:154-171` and the composite.

| With | A store (compartment) | A Ca channel, no store | The cycle laws, no store |
| --- | --- | --- | --- |
| @3 faces, junctions, channels, Na/K pump | composes | composes | composes |
| `local_species_reactions@1` | composes (measured) | composes with §5.4 | composes |
| `electrode_current_injection@1` | composes | composes | composes |
| `scheduled_species_exchange@1`, `scheduled_species_turnover@1` | composes; neutral species only | composes | composes |
| `species_regulated_availability@1`, `@2` | composes; its instantaneous sources are neutral, its channel targets now include calcium's | composes | composes |
| `species_condition@1` (E's source) | composes, as a source (E's 5.7) | composes, as a sink of it | a cycle law's availability is not routed |
| `scheduled_bath_composition@1` | composes beside a held bath; a closed world has none | composes | composes |
| `templated_polymerisation@1`, `neutral_arrival_labels@1`, `population_unit_turnover@1`, membrane state | as the compartments' list says; a provider of areas or capacitances still needs a held bath in the component | as their own rules | as their own rules |
| `scheduled_cell_replacement@1`, `@2` | refused: a declared kind is present | **refused by name** (§5.5; today a bare `ValueError`, M2) | refused: a declared kind is present |
| `scheduled_membrane_trafficking@1` | refused: a declared kind is present | composes (no kind) | refused: a declared kind is present |
| Insertion, division, lumens | refused by the compartment | as their own rules | refused or admitted by the kinds' lifecycle roles |
| Water, `k_anion_symport` | refused by the compartment (volume) | as today | as today |
| Compartment wash, site occupancy, bridge | refused by the compartment's list | as today | as today |
| RK4 | refused | **refused by name:** the law declares no RK4 bound (§5.2) | refused |
| `rapid_binding@1` | the closure refuses @3 routes and pumps on its rows; a Ca channel reads through the closure but is refused there today (§2.3, H2's) | refused on a held row | admitted for laws that declare the read |
| Near and far (free offsets) | composes with field solver version 3, declared (D147); version 2 refuses the two-cell world at the parse (M) | the same | the same |

## 11. D148, CPU, GPU, restart

- **D148 (bit for bit when not declared).** Host only: the parser's valence check and its refusal, the reactions
  door, refusal 6, the replacement's refusal, the symport's. Static, by shape or structure, as K3b, FR-51 and B1
  are: the charge rule's rows (only where a floating node is declared, §8.3), the channel material term (only where
  a declared channel law declares it), the transporter's (where a population's law does), the loops (where a routed
  source reads a row its sink moves and has the hooks). Every other world of today's keeps its programs, layouts and
  fingerprints. Proof: row 1's own D148 round first, then the cleanup's one gate, with crossrev's sets, G1's 113
  worlds and FR's set.
- **CPU:** everything here runs there. The probe's one-cell composite world took 26 s to parse, compile and step
  five steps; the two-cell closed world 1.7 s to parse and 27.4 s to compile and step five (M).
- **GPU:** nothing in these laws blocks one (no host callback, no data-dependent loop). What blocks is the
  composite's path: refused in the vector windows (D338), and a plain, unflagged run on a GPU is the user's open
  choice (D380). The buffers and the identity declaration make the world a composite; the rest of the store is @3
  and its kinds. **So two routes stay open for later:** a GPU qualification of the composite (G-8), or the store on
  @3 with `rapid_binding@1` as its buffers, which is a changed model.
- **Restart:** no new state. Gates, cycle counts, transfers and heats are checkpointed. The store's nonzero charge
  anchor is admitted on import, since the world declares kinds and IMEX (refusal 5). The charge rule's flag is in
  the structure, not in a layout or a state, so checkpoints of worlds with a floating node still load. The loops'
  layout fields are saved and compared with the layout, in worlds that have them.

## 12. For the criteria

- **All rows here are the same equations.** A held bath, a factor held through the step, or a store at the cytosol's
  potential would be changed models.
- **The order is 2.** The candidate's own h, h/2 and h/4 are its own steps. The energy residual fell by four per
  halving (§6.7).
- **The 1e-9 pJ absolute energy bound is legacy's RK4 property.** The measured residual of the closed store world is
  4.5e-11 pJ after 1 ms at 12.5 µs, without buffers, faces or the channel, and the composite's is 3.0e-12 pJ after
  31 µs (M). Nothing was run to 20 ms. So the criteria can either judge that bound with a margin it measures first,
  or judge the engine's rule and the second-order fall.
- **The 3e-9 comparison** (`tests/unit/test_spatial_calcium.py:68-76`) belongs to the RK4 world at 12.5 µs. It is
  not needed if the band applies.
- **Independent references exist.** `tests/reference_{er,spatial,plasma,gated,ip3}_calcium.py` integrate the same
  equations with SciPy's DOP853 and Radau, and import no Cells. The extrapolated candidate can be compared with them
  directly, which is stronger than a comparison with legacy. **The deletion must keep**
  `validation/betse/spatial_cluster/reference.py`, which `tests/reference_spatial_calcium.py:15` imports, or move it
  beside them.
- **Known differences with no physics in them:** traces of absent rows (1e-9 mM); V_ER = -V_b; legacy refuses |V_ER|
  above 0.15 V and steps above 50 µs, and @3 refuses neither, so a criterion may record both.
- **The controls** (release off, a leak off, the pump off) are used by legacy's qualification tests, not by the four
  configurations. A transporter has schedules; a passive route has none. If a registered row uses one, that is about
  half a day (§16.2, L7).

## 13. IDs, registry pieces and pages

**On the branch, code is written with today's bare IDs** and the scripted move follows (D383). Every ID below takes
a family that exists.

| Piece | Today's ID | After the move | Family word |
| --- | --- | --- | --- |
| Channel law | `cav1p2_m2h@1` (in the catalogue) | `cells.channel.cav1p2_m2h@1` | existing |
| Cycle law, the pump | `atp_driven_transporter_mass_action_positive@2` | `cells.cycle.atp_driven_transporter_mass_action_positive@2` | existing |
| Cycle law, the exchanger | `sodium_calcium_exchange_symmetric_barrier@1` | `cells.cycle.sodium_calcium_exchange_symmetric_barrier@1` | existing |
| Cycle laws, the symports | `na_k_2anion_symport_reversible_tanh@1`, `electroneutral_symport_reversible_tanh@1` | `cells.cycle.*`, the same names | existing |
| E's source and its law | E's note | `cells.kind.*`, `cells.transfer_factor.*` | existing; `transfer_factor` is D383's |

The five IDs need rows in `scripts/moves/id-rename-choices.json`, which is the rename's owner's.

- **No new interface** here. `ChannelLaw` gains one defaulted field, `material_term` (D191's precedent for
  `JunctionLaw`), and loses `loop_term`; `CycleLaw` gains `electroneutral` and loses `loop_term` (§6.5, §7.2). The
  declarations manifest shows them.
- **Two optional `Kind` hooks for a sink** (`routed_rows`, `routed_flux`); E's two for a source are E's (§6.5).
- **Model table:** five new homes on @3's row (`registry/model_table.py:67-114`), each an inert module.
- **Library pages:** one for each of the five laws, with their independent reference, plant and stated limits.
  `transporter@1`'s generated blocks, the index and the glossary follow `library_pages.py --write`. The glossary
  gains "store" and "floating node".
- **Notes to amend:** CLOSED_COMPARTMENT_DESIGN §1.4, §3.5 and its status block (§6.2 here), INNER_MODEL_V4_DESIGN
  §13.6 (B7's rows, §8.3 here) and 558 and 841 (`loop_term`), CHARGED_TRACE_SPECIES_DESIGN §6 (the transporter's
  bound is built), HUMAN_CARDIAC_LAWS_DESIGN §1 and §6 (§2.2 above), CORE_LAWS_ROADMAP families 1, 2, 5 and 9.
- **At the deletion,** `laws/reactions/er_calcium.py` and `plasma_calcium.py` reduce to one function, `pump_rates`,
  which the live pump law uses: it can move into that law's module. Their first lines name BETSE, and so does
  `calcium_gates.py`'s.

## 14. Tests (rows, with plants; D224)

Rows go into existing files. One new file holds the world-level rows. Times are estimates from the probes (S); each
is measured at the landing. A planted row must fail the criterion it names.

| # | Row | File | Plant (each must fail the row) | Est. |
| --- | --- | --- | --- | --- |
| 0 | the charge rule (§8.3): worlds A, B, C and D refused at 2.2 (D at 3.0) and admitted at 0.9, host bounds; a kind's slope on a loose patch and on a held one, and a channel on a loose patch without kinds, at the stage; FR-4's cell row is 0; the host rates of worlds without a floating node equal today's bit for bit | `test_surface_pump_step_checks.py`, `test_kind_rules.py` | all patches counted; the junction term over all patches; the fixed-node exclusion kept; the node's summed row; the kinds' term read once; the loose rows dropped without kinds | 4 s |
| 1 | the parser reads each ion's valence from its law; a law with a scarce ion and no material term refused; a Ca channel refused on an RK4 grid; replacement beside a law outside the five refused by name | `test_chloride_leak_law.py`, `test_inner_laws.py`, `test_cell_replacement.py` | a law that says Ca is +1; a model whose Ca is +1; a Ca law that declares the 25 µs bound (admitted on RK4) | 2 s |
| 2 | `cav1p2_m2h@1` against its independent reference at 1,801 voltages | `test_kv1_channel_laws.py`, a new row beside its laws | the 10 mV shift dropped; m² for m³ | 1 s |
| 3 | its flux, transfer and heat at a state (valence 2, both directions) | the same | z = 1 | 1 s |
| 4 | the channel material term against a NumPy finite difference of dJ/dn at each end, over voltages and openings; the mode's rate at both ends; largest over species | new `tests/unit/test_calcium_store.py` | B(x) and B(-x) exchanged; the term at one end only; the term absent at a store's node | 2 s |
| 5 | the reactions door: a Ca channel beside a written Ca row, with and without the term; RK4 | `test_species_reactions_refusals.py` (its charged-rows table) | a law that declares none; a membrane permeability | 1 s |
| 6 | refusal 6, version 1.1: the closed store world admitted, with the gauge its representative; a compartment that is its component's first outside node refused by name; the helper equal to `bind`'s fixed nodes; the scope string's start | `test_cell_owned_compartments.py` (replacing row 510) | the last outside node taken as the representative; the held-bath rule kept | 3 s |
| 7 | refusal 4: the pump @2 at a store's node, admitted by its step terms; both pump laws on one patch refused; a symport at a store's node refused | the same (its planted-moves table) | a law that declares no term; **a law that declares `material_term` alone** (a charge term alone is admitted, `PLANTED_MOVES`, so it is no plant) | 2 s |
| 8 | the pump @2 against the NumPy closed form, at z = 2, 1, -1 and 0 (at 0 its rate is @1's), n = 1 to 4; the slopes at both ends against finite differences | `test_cycle_kind.py` | the electrical sign; n applied to K twice | 2 s |
| 9 | the exchanger against the product formula at random states, and its reversal, heat sign and slopes; the two symports against the tanh form, their reversal and heat sign; a non-neutral binding of the configured one refused | the same | zeta +1/2; K^3 for K; Ca and Na roles exchanged; NKCC at 1:1:1; the symport's S without the factor | 3 s |
| 10 | the material bound of a declaring population: the sum over its rows at both ends against the block's own eigenvalue, for the exchanger at equal rows; a closure's derivative on a declared read; a row that version 1's buffer holds refused; a world without the declaration keeps its structure entry and its program (a property) | `test_cycle_kind.py` | the largest over species in place of the sum (2x low at equal rows); the far end left out; the closure branch untraced (too tight by total over free); held rows counted | 3 s |
| 11 | the loop's bound against a finite difference of the stage's derivative, at both ends; finite at a zero amount; `loops` empty without a loop, for a held bath and for a source without hooks | `test_passive_routes_kind.py` | the slope dropped; a source on another node; the held control in place of the routed one; the division before the product (NaN) | 2 s |
| 12 | a one-cell store world against a code-blind SciPy solution, NumPy steps at h, h/2, h/4: amounts, V_b, heat, the order; its material block's largest eigenvalue below the stage's rate | the new file | the release's sign; the pump's electrical term; a 1% change of each constant must exceed the band | 15 s |
| 13 | the composite store world **with V_b(0) = -5 mV**, 5 compiled steps, restart equal | the same | the store's charge anchor dropped on import (the plant needs V_b(0) nonzero) | 30 s |
| 14 | **the two-cell closed world,** compiled, 5 steps of 12.5 µs, **tier 2:** two cells on the gauge, near and far (two free offsets, the floor solver declared under D147), a store per cell at -5 mV, a Ca route on the junction, Ca on the faces, buffers, both pumps, the exchanger, a Ca channel per plasma patch, the release gated by E's two conditions per cell. Every ledger within @3's bounds; the whole-world amounts constant; V_m and V_b at each node as a dense capacitor solve of the row's own gives; restart equal | the new file | cell_0's condition reads cell_1's node; K and n exchanged in a condition (E's two); the owners of the two stores exchanged; the junction route's sign; near's row left out of the whole-world sum; a 1% change of one route's permeability must exceed the band | 30 s (27.4 s to compile and run, 1.7 s to parse, M, ungated) |

**About 100 s in all (S),** of it about 40 s in tier 1 and 60 s in tier 2 (rows 13 and 14). The reason for the two
compiled rows: the closed topology, the restart and the hooks in one program are in no row today, and no compiled
world has two cells with stores. The code-blind reference for rows 8, 9 and 12 is written by a fresh agent from this
note's equations, and never from the code.

**The field solver.** Rows that hold near and far take it from `field_solver_choice` (D147). Two facts for the
builder (M): the two-cell definition is refused at the parse under version 2, so `declare(raw, "auto")`, which
parses with the declared solver to count the free offsets, fails too; with version 3 declared first it counts two
and keeps it. So the world is built with version 3 declared, and `declare` confirms the choice.

## 15. Price, order and owners

| Step | Work | Files | Days (S) |
| --- | --- | --- | --- |
| 0 | **the charge rule** (§8.3), its own commit, first, one D148 round, with the scan | `models/surface_pump.py`, `models/surface_pump_v3.py`, `models/inner_laws.py`, `kinds/transporter.py`, `operators/species_common.py` | 0.75 to 1 |
| 1 | the parser's valence rule and its refusal; `cav1p2_m2h@1`; replacement's refusal by name | `definitions/surface_pump_v3_spec.py`, `laws/channels/cav1p2_m2h.py`, `model_table.py`, `operators/cell_replacement.py` | 0.75 |
| 2 | the channel material term and the reactions door | `models/surface_pump_v3.py`, `registry/laws.py`, `operators/species_common.py` | 1 to 1.25 |
| 3 | refusal 6, version 1.1, with its section, the R6 pair and the rows | `operators/compartments.py`, `numerics/surface_field.py`, the design note | 0.5 |
| 4 | the exchanger; the pump @2; with their references | `laws/cycles/`, `laws/pumps/` | 1 |
| 5 | the transporter's material bound (sum, closure branch, proton rows), declared on the exchanger, the pump @2, the symports and the mitochondria's seven | `kinds/transporter.py`, `laws/cycles/` | 0.75 to 1 |
| 6 | the feedback bound (with E's hooks), `loop_term`'s removal | `models/surface_pump_v3.py`, `models/inner_laws.py`, `registry/kind_registry.py`, `registry/laws.py`, `kinds/passive_routes.py` | 1 to 1.5 |
| 7 | the store worlds: references, rows 12 to 14 | `tests/unit/` | 1 to 1.5 |
| 8 | pages, notes, the roadmap | `docs/` | 0.5 to 0.75 |
| | **In all** | | **7.25 to 9.25, so about 7 to 9.25** |
| S | the two symport laws (§7.2), beside step 4; their material rows with step 5 | `laws/cycles/`, `registry/laws.py`, `kinds/transporter.py` | 0.8 to 0.9 |

- **Order.** D386's stages, with the second reader's order inside the last:
  1. the exchanger (from step 4), beside G-7's driver: it depends on nothing;
  2. E's source with the final hooks (§6.5), which `species-condition-build` is building;
  3. the calcium core edits: **step 0 first, alone;** then steps 1 and 3, the pump @2 and the symports; then steps 2
     and 6 as one edit of `material_rate`, by one owner; step 5; step 7; step 8 with each. Step 0 comes before any
     store world. The re-expression of the four worlds follows.
- **Not in this price:** the re-expression and its qualification (the plan's 8 to 12 days); H1's and H2's own work;
  D211's other channel laws (about 0.15 to 0.25 of a day each); a hook pair for `ph_condition` (about 0.25 day), a
  follow-up; @1's retirement (0.5 day, §6.3).

### 15.1 Live-engine edits

Lines at 43b22d40. On `legacy-cleanup` (e67f4660) `models/surface_pump_v3.py` is one line earlier throughout and
`models/inner_laws.py` too; every other file below has the same lines. The owner column is a proposal.

| Step | File and line | Edit | Owner |
| --- | --- | --- | --- |
| 0 | `models/surface_pump.py:464-520` (487, 516, 517), 543-569; new helper beside 543 | `explicit_rate_bound(spec, *, floating=None)`; the loose-patch rows; `floating_nodes(model)`; the refusal of a cell with no held patch | core |
| 0 | `models/surface_pump_v3.py:3615-3698`, 3730-3745, 4003-4010, 5041-5066 | the stage rows; the node set; the definition's call with the forms-aware set; the structure's flag | core |
| 0 | `models/inner_laws.py:314` | `floating_nodes: bool = False`, checked in `__post_init__` | core |
| 0 | `kinds/transporter.py:691-718`, 2330-2376; `modules/__init__.py:110-131, 200-210` | the two definition terms; the helper's export | kinds |
| 0 | `operators/species_common.py:207-247` | `counter_ion_margin`'s capacitance | operators |
| 0 | `registry/kind_registry.py:276-284` | the docstring of `stage_term`: the held view | core |
| 1 | `definitions/surface_pump_v3_spec.py:169, 317-331` | `SPECIES_VALENCE` leaves; the law's valences; the refusal | core |
| 1 | `registry/laws.py:362-432` | `ChannelLaw.material_term`, its check | core |
| 1 | `operators/cell_replacement.py:194-209` | the refusal by name | operators |
| 1 | new `laws/channels/cav1p2_m2h.py`; `registry/model_table.py:67-82` | the module and its home | laws |
| 2, 6 | `models/surface_pump_v3.py:3701-3727` (`material_rate`), 795-825 (`block_material_rates`), 189-196, 332-400, 1185-1262, 3589-3612 (`_check_routes`), 5041, 5354-5401, 5442-5458; call sites 2830 and 2941 | the channel term, the loops, their layout fields, pairing, types and the rule: **one edit, one owner** | core |
| 2 | `operators/species_common.py:167-192` | the reactions door | operators |
| 3 | `operators/compartments.py:42-45, 256-268, 445-451, 512-518, 698-707` | the docstring's item 6, the representative, the check and its message, the scope string | operators |
| 3 | `numerics/surface_field.py:299-304` | `representative(...)`, used by `bind` | core |
| 3 | `validation/tissue/compartment_acceptance_qualification.py:112, 699, 730-744`; `tests/unit/test_cell_owned_compartments.py:510, 1510-1516` | the added phrase, the R6 world, the rows | operators |
| 4 | new `laws/cycles/sodium_calcium_exchange_symmetric_barrier.py`, `laws/pumps/` (the @2 module); `registry/model_table.py:88-114` | the modules and their homes | laws |
| 5 | `kinds/transporter.py:464-478, 1085-1116, 1419-1440, 1589, 2225-2287, 2410`; docstring 22-34 and 137-144 | the static field, the sum, the closure branch, the refusal at version 1's buffer, the two layouts' limits | kinds |
| 6 | `models/inner_laws.py:314` | `loops: tuple = ()` | core |
| 6 | `registry/kind_registry.py:251-259, 457-460, 957` | `routed_rows`, `routed_flux` (the two source hooks are E's) | core, with E |
| 6 | `kinds/passive_routes.py:529` and 702 | the sink's two hooks | kinds |
| 6 | `kinds/ph_condition.py:1-31`, `kinds/patch_damage.py:1-51` | the limit's sentence (E names the first's successor too) | E |
| 6 | `registry/laws.py:377, 446, 482`; `laws/pumps/proton_pump.py:137, 265`; `docs/INNER_MODEL_V4_DESIGN.md:558, 841`; `docs/library/DECLARATIONS_FORMAT.md:210, 224`; `tests/unit/test_inner_laws.py:152`, `test_law_registry.py:222` | `loop_term` removed, with its reason | core |
| S | new `laws/cycles/na_k_2anion_symport_reversible_tanh.py`, `electroneutral_symport_reversible_tanh.py`; `registry/laws.py:434-460` (`CycleLaw.electroneutral`); `kinds/transporter.py:1308-1343` (the refusal); `registry/model_table.py:88-114` | the two modules | laws, kinds |

**Files two owners meet in:** `models/surface_pump_v3.py` (steps 0, 2, 6: the core's one owner, in that order),
`models/inner_laws.py` (two fields, 0 and 6), `kinds/transporter.py` (0, 5, S: the kinds owner),
`registry/kind_registry.py` (6 and E's source), `registry/model_table.py` (five lines, with E's none),
`registry/laws.py` (1, 6, S). The last three are short and go through one owner at a time.

### 15.2 If a ruling cannot be executed

Every ruling on rows 1 to 9, 13 and 14 can be executed as ruled. What is done differently, and why:
- **Row 1, wider than its words.** "Patches that do not face a free face-free node" leaves two shapes admitted: a
  representative that no face names (world C) and a node shared by two cells (world D). The set drops the fixed-node
  exclusion, and a loose patch takes its own row in place of the node's sum. Both are exact for one patch per node,
  which every compartment has. If the lead prefers the ruled words alone, worlds C and D become stated limits (L11).
- **Row 7, for `patch_damage`:** its factor reads no amount, so there is no loop to leave unbounded. Its docstring
  says that instead (§6.5).
- **Row 9, the flux's shape:** `{control field: [species, slot]}` and not [M] (§6.5, L10).
- **Row 13, the retirements:** @1 can leave at once (§6.3 (i)). The proton law and @3's own pumps are tied to judged
  worlds and to the roadmap's pump item, so they get a trigger and not a date.
- **Row 16, `background`:** it is the registry's key (§4).
- **Row 5's message.** The rule that refuses the RK4 grid says "Resolved gated channels ({law}) require RK4 steps <=
  0 us". It names the law, as ruled. A clearer sentence is one line in `StepChecks.__call__`
  (`models/surface_pump_v3.py:4069-4074`), taken with step 1.

## 16. Questions

### 16.1 For the user: U1, answered (D386)

**The exchanger: two kinetic forms, one mechanism.** The ensemble's form is registered now, labelled synthetic (only
its reversal is supported). Whether it stays beside the cardiac plan's law or retires is decided when that law
lands.

### 16.2 For the lead: L1 to L9, ruled as recommended (D385)

L1 the channel population (form A). L2 one ATP-driven law for both pumps. L3 the feedback bound is built. L4 "not
the representative". L5 the buffers' door for `local_species_reactions@1` alone. L6 the engine's own ledger rule. L7
no passive-route schedules now. L8 the independent reference is kept. L9 no non-negative booking for passive routes
now.

### 16.3 For the lead: new

- **L10. `routed_flux`'s shape** (§6.5): `{control field: [species, slot]}`, recommended, or E's [M] with the routed
  slots passed as a static argument. The rest of E's text and this note's agree.
- **L11. The charge rule's set** (§8.3, §15.2): with worlds C and D, recommended, or the ruled words alone with two
  stated limits.
- **L12. The mitochondria's seven laws' `material_term`** (§6.3): with step 5, recommended, since nothing judged
  runs them, or at MT-1b's registration. Two of them move no net charge (the K/H exchange, the phosphate symport),
  so they have no stage bound of any kind today (§1, row 13). Not looked for: a world where it binds.
- **L13. The configured symport's refusal** (§7.2): `CycleLaw.electroneutral` in the template, recommended, or only
  fixed-stoichiometry modules and no configured law.

## 17. What is wrong in the plan and the docstrings

Plan lines are those of `docs/LEGACY_PORT_PLAN.md` at a1db6ab9. The map there has already corrected B2 and I8 (the
population axis does not refuse electrogenic modes) and §8's "changed model" for B1 and NCX. Not corrected:

1. **B1, "Not bitwise" (line 335):** true of a trajectory, not of the kernel. It is bit for bit with the converted
   constant on 2,000 states (M).
2. **§8, "Conservation ledgers keep their own absolute bounds, for example 1e-9 pJ on energy" (line 975):** not
   established for a second-order candidate (§12).
3. **B4 (line 338)** says the reactions hold a species that @3 routes only as a covered counter-ion, and that inside
   the ER it waits for G-4. That is one admission. The other is that a species whose movers are all kinds has no @3
   route, and the probe ran it (M), in the cytosol and in the store.
4. **The price of G-4, 5 to 8 days (line 498):** the store's entity, its leaks, its buffers and its charged door
   exist. §15 replaces it.
5. `laws/reactions/er_calcium.py:1` and `laws/reactions/plasma_calcium.py:3` name BETSE in their docstrings, and
   `laws/channels/calcium_gates.py:1` too; its line 3 says "native". Live code should read neutrally (§13).
6. **The cardiac note's §1 and §6** (16 November) list as missing prerequisites that exist now (§2.2).
7. `docs/SPATIAL_CALCIUM.md:49` and `docs/ER_CALCIUM.md:68` state 1e-9 pJ as the residual limit. That is true of the
   RK4 models and is not the engine's bound for their re-expression (§12). They are the legacy models' records.
8. **`models/surface_pump.py:468-469`** says a cell's charge relaxes against "the cell's total patch capacitance".
   It does not, beside a floating node (§8.3). `surface_pump_v3.py:3731-3745` and `surface_pump.py:548-560` exclude
   "fixed nodes", which leaves a face-free representative out (world C).
9. **`kinds/transporter.py:28-29`** says "proton rows changed at both ends stay on the charge rule". That holds
   where the cycle moves charge, its node has a charge row and its row is buffered; not where the cycle is neutral
   (§6.3).
10. **`field_solver_choice.declare`** (`validation/tissue/field_solver_choice.py:60-100`) counts the free offsets by
    parsing with the solver the definition declares. A world that version 2 refuses at its initial field cannot be
    counted until version 3 is declared (§14).
11. **This note at c5006ff6** said: the material bound is the largest over a population's rows (it is the sum,
    §6.3); the loop's rate is added at the read node (at both ends, §6.5); the loop slope is in 1/fmol
    (dimensionless); the channel's RK4 bound is 25 µs (None); a declared Ca channel composes with replacement (it
    raised); a plant of one step term (admitted today); an electrode at the gauge (there is none). Corrected here.

## 18. Sources

- D. E. Goldman (1943). Potential, impedance, and rectification in membranes. J. Gen. Physiol. 27:37-60.
  doi:10.1085/jgp.27.1.37 [rec].
- A. L. Hodgkin, B. Katz (1949). J. Physiol. 108:37-77. doi:10.1113/jphysiol.1949.sp004310 [rec].
- S. Matsuoka, D. W. Hilgemann (1992). Steady-state and dynamic properties of cardiac sodium-calcium exchange. Ion
  and voltage dependencies of the transport cycle. J. Gen. Physiol. 100:963-1001. doi:10.1085/jgp.100.6.963 [abs].
  Two companions of the same series, doi:10.1085/jgp.100.6.905 and 10.1085/jgp.100.6.933 [rec].
- M. Hinata and colleagues (2002). Stoichiometry of Na+-Ca2+ exchange is 3:1 in guinea-pig ventricular myocytes. J.
  Physiol. 545:453-461. doi:10.1113/jphysiol.2002.025866 [abs].
- Y. Fujioka, M. Komeda, S. Matsuoka (2000). Stoichiometry of Na+-Ca2+ exchange in inside-out patches excised from
  guinea-pig ventricular myocytes. J. Physiol. 523:339-351. doi:10.1111/j.1469-7793.2000.t01-2-00339.x [abs].
- T. Kang, D. W. Hilgemann (2004). Multiple transport modes of the cardiac Na+/Ca2+ exchanger. Nature 427:544-548.
  doi:10.1038/nature02271 [abs].
- D. O. Mak, S. McBride, J. K. Foskett (1998). Inositol 1,4,5-tris-phosphate activation of inositol tris-phosphate
  receptor Ca2+ channel by ligand tuning of Ca2+ inhibition. PNAS 95:15821-15825. doi:10.1073/pnas.95.26.15821
  [abs].
- I. Bezprozvanny, J. Watras, B. E. Ehrlich (1991). Nature 351:751-754. doi:10.1038/351751a0 [rec].
- K. Tran, N. P. Smith, D. S. Loiselle, E. J. Crampin (2009). A thermodynamic model of the cardiac
  sarcoplasmic/endoplasmic Ca2+ (SERCA) pump. Biophys. J. 96:2029-2042. doi:10.1016/j.bpj.2008.11.045 [rec].
- J. Wagner, J. Keizer (1994). Effects of rapid buffers on Ca2+ diffusion and Ca2+ oscillations. Biophys. J.
  67:447-456. doi:10.1016/S0006-3495(94)80500-4 [rec].
- D. Gillespie, M. Fill (2008). Intracellular calcium release channels mediate their own countercurrent. Biophys. J.
  95:3706-3714. doi:10.1529/biophysj.108.131987 [abs].
- A. Zsolnay, M. Fill, D. Gillespie (2018). Biophys. J. 114:462-473. doi:10.1016/j.bpj.2017.11.3775 [abs].
- BETSE v1.5.0's channel and pump functions, as `docs/ER_CALCIUM.md` and `docs/PLASMA_CALCIUM.md` cite them [sec:
  those files].

None of these was read in full for this note. Where a form rests on more than one independent report, the text says
so; where it rests on one, it says one.

## Appendix A. Probes

### A.1 The first version's (25 November 2026)

Folder `/mnt/workspaces/Cells/calcium-store-design-20261125/probes/` (scripts and outputs; the world is `world.py`).
All ran on 25 November 2026 at 43b22d40, on CPU 6 (probe 5 on CPUs 6, 7, 22, 23 as a unit capped at 6 GB), one
thread, at nice 10, under `/mnt/workspaces/Cells/venv-cpu`, with no file written in the tree. The planted laws are
in the `tests.` namespace, in an extended registry, in the probe's process only.

| Probe | What it ran | Result |
| --- | --- | --- |
| 1 | `parse_spec` on the store world and six variants | the world is admitted (kinds, store, reactions, held bath); a closed exterior is refused by refusal 6 and admitted without the declaration; the catalogue's Ca law is refused; RK4 is refused by name |
| 2 | one host evaluation of @3's readouts | valid; energy balance -1.4e-16 pJ/s of 0.85; the exchanger to 1.9e-15, both pumps 0.0 relative to the legacy kernels; leaks equal; charge rate 5,290.6 per s; material rate 2.42 per s |
| 3 | a planted calcium channel law | refused by the valence table; admitted with Ca added in the process; its flux 2.2e-16 from legacy's; its gate values equal; the material rate unchanged at 2.42; beside the reactions refused by `check_impermeant`; counter-ion margin 4.62 |
| 4 | 80, 160 and 320 host steps of `imex_step` (NumPy, no composite) at 12.5, 6.25 and 3.125 µs | no refusal; worst relative energy ledger 1.6e-7, 4.1e-8, 1.0e-8 against 2e-3; same amounts to 12 digits |
| 5 | the composite (compile and 5 steps at 6.25 µs), with and without the planted channel, the channel clause of `check_impermeant` lifted in the process | parsed, compiled and ran (26 and 30 s); energy residual 3.0e-12 pJ, relative 9.5e-9 |
| 6 | 80 host steps of the closed world | the store's node is free, the bath node fixed; relative energy 2.0e-7; capacitor error 5e-29 C; energy error 4.5e-11 pJ |
| 7 | `ca_atp_mass_action_positive@1` against the legacy kernel at 2,000 random states | worst relative difference 0.0; dG0(1 M) = -19,875.97 J/mol |
| 8 | the planted exchanger with the declarations of §7.1 (`reads`, base forms), and a store pump whose law declares no step term | parses, same rate; refused by name without a step term; a charge term alone is admitted (refusal 4's version 1.3) |

### A.2 This revision's

Folder `.../calcium-store-design-20261125/revision/` (about 0.5 MB; scripts and `.out` files). The same environment,
on CPU 6; the units (`scan_rates`, `scan_wide`, `two_cell`) on CPUs 6, 7, 22 and 23, capped at 4 to 6 GB. The
corrected rules are candidate NumPy functions beside the live ones (`rates.py`, `rates2.py`). Nothing is patched
into `src/`; refusal 6, the valence table and `check_impermeant`'s channel clause are lifted in `two_cell`'s process
only.

| Script | What it ran | Result |
| --- | --- | --- |
| `bound_check` | 20,000 random capacitor networks of each of seven shapes: true largest relaxation rate against the live and the corrected rows | §8.3 |
| `row1_check` | worlds A to D on live @3: definition and stage rates, live and corrected; 12 NumPy steps each | §8.3's table |
| `row1_kinds` | the corrected stage rate with kinds, on FR-4's declared world, FR-5's arm T with its factors, the store world open and closed | today's rates to every printed digit; cell rows 0, 0, 15.7, 15.7 per s |
| `scan_shapes`, `scan_rates`, `scan_wide` | the scan of §8.3: 140 worlds' shapes; the rates of those that parse; 222 further modules searched for zero-argument builders (89 not importable here, 11 worlds built, one more floating node, in a legacy family at 0.67) | 47 with a floating node, no hit; 69 without one equal bit for bit in both rates; 17 refused at the parse; 23 skipped, 22 of them replacement worlds, whose control records the probe's reader does not handle and which hold no floating node |
| `mode_rates` | the planted cycles' mode rates in the store world against their blocks' eigenvalues and the largest over species | §6.3 |
| `material_check` | the rule of §8.2 for the routes and the cycles against the eigenvalues of the live explicit rates' Jacobian at fixed potentials, Ca and Na rows, at the start and at a thousandth of the calcium | the rule is 1.25 to 1.27 times the true rate at the start, 1.08 times at the trace; §8.2 |
| `proton_rows` | FR-4's buffers: n_eff, n_C and their ratio at two pH, with and without a closure | §6.3 |
| `nkcc_probe`, `symport_forms` | the symports' forms: `errors()`, parse, 4,000 and 200 random states against `legacy/processes/cotransport.py` and the closed form; non-neutral bindings | §7.2 |
| `two_cell` | the two-cell closed world (E's source absent, so the release is ungated at 0.238 of its permeability): parse, one host evaluation, compile and five steps of 12.5 µs | version 2 refused at the parse; version 3: parse 1.7 s, two free offsets, energy balance -5e-14 pJ/s, charge rate 5,268 per s, material rate 0.91 per s, compile and run 27.4 s, capacitor error 1.7e-28 C, electrode error 0 C, worst relative energy ledger 7.3e-5 |

**Not run:** a step of the full four-world re-expression, buffers against a kinetic reference, any compiled GPU
path, anything to 20 ms, the hooks of §6.5 (they do not exist), a compiled run of the corrected charge rule, and the
scan over saved trajectories. No other agent has read this revision.

## Appendix B. The store world as a definition

The four worlds' numbers map onto today's blocks (legacy's on the left):

| Legacy | Here |
| --- | --- |
| `stores[].model.compartments[er]` | a finite outside node; `cell_owned_compartments@1` names it with its patch and owner |
| `membrane.area_m2`, `specific_capacitance_F_per_m2` | the bounding patch's `area_m2`, `capacitance_F` = area x specific capacitance |
| `membrane.initial_voltage_V` | `initial_charge_C` at the store = C_b V0, and the fixed charge that follows from it |
| `permeability_m_per_s.K` (store) | the patch's `permeability_m_per_s.K` |
| `permeability_m_per_s.Ca` (store, plasma, junction) | `passive_constant_field_permeation@1` routes |
| `release` | a `passive_constant_field_permeation@1` route with `factors: [ca_source, ip3_source]` |
| `pump` (store) and `plasma_transport.pump` | populations of `atp_driven_transporter_mass_action_positive@2`: capacity, `km_role_mM` = K_Ca, `km_atp_mM` = K_ATP, held rows ATP, ADP, Pi at the cell. The registry's potentials give dG0: mu(ATP) = mu(Pi) = 0, mu(ADP) = dG0/RT at c0 = 1 mM |
| `plasma_transport.exchanger` | a population of `sodium_calcium_exchange_symmetric_barrier@1`: capacity, `km_na_mM`, `km_ca_mM` |
| `calcium_channels[]` | a channel population of `cav1p2_m2h@1`: permeability, abundance, gates, permeant ion Ca |
| `reactions[]` | `local_species_reactions@1` at the cell and the store, c0 = 1 mM, each passive, `forward_rate_per_s` as listed |
| `store_controls`, `plasma_controls`, `calcium_channel_controls` (all constant 1) | `reaction_controls`, `transporter_controls`, `membrane_controls`, `channel_controls`; none per passive route |
| `ionic` | @3's cells, outside nodes, patches, junctions and faces; calcium's permeability out of the patches and junctions and into routes |

## Appendix C. The cycle forms, as the probes planted them

Data only. Each becomes an inert module on the pattern of `laws/cycles/electrogenic_nucleotide_exchange.py`, with
its page, citation (or "parity") and test.

```python
EXCHANGE = CycleForm(
    kinetics="monomial",
    roles=(("Na", 1), ("Ca", 2)),
    rows=(("Na", "N"), ("Na", "P"), ("Ca", "N"), ("Ca", "P")),
    modes=(("exchange", (3, -3, -1, 1)),),
    parameters=(Parameter("km_na_mM", "mM", positive=True), Parameter("km_ca_mM", "mM", positive=True)),
    monomial=MonomialForm(
        (MonomialRate(
            orders=((Reference("Na", "P"), 3.0), (Reference("Ca", "N"), 1.0)),
            zeta=-0.5,
            factors=(
                MonomialFactor(1.0, (
                    MonomialTerm(Scaled("km_na_mM", 1.0, -3), ((Reference("Na", "N"), 3.0),)),
                    MonomialTerm(Scaled("km_na_mM", 1.0, -3), ((Reference("Na", "P"), 3.0),)))),
                MonomialFactor(1.0, (
                    MonomialTerm(Scaled("km_ca_mM", 1.0, -1), ((Reference("Ca", "N"), 1.0),)),
                    MonomialTerm(Scaled("km_ca_mM", 1.0, -1), ((Reference("Ca", "P"), 1.0),))))),
            constants=(Scaled("km_na_mM", 1.0, -3), Scaled("km_ca_mM", 1.0, -1))),),
        standard_state_mM=1.0))

TRANSPORT = CycleForm(
    kinetics="factored",
    roles=(("role", None), ("ATP", 0), ("ADP", 0), ("Pi", 0)),
    rows=(("role", "N"), ("role", "P"), ("ATP", "N"), ("ADP", "N"), ("Pi", "N")),
    modes=(("cycle", ("-stoichiometry", "stoichiometry", -1, 1, 1)),),
    parameters=(
        Parameter("stoichiometry", "1", low=1, high=4, integer=True, positive=True),
        Parameter("km_role_mM", "mM", positive=True), Parameter("km_atp_mM", "mM", positive=True)),
    fuel_roles=("ATP", "ADP", "Pi"),
    saturation=((Saturation(("role", "N"), "km_role_mM", "stoichiometry"),
                 Saturation(("ATP", "N"), "km_atp_mM", 1)),))

NA_K_2ANION = CycleForm(
    kinetics="monomial",
    roles=(("Na", 1), ("K", 1), ("anion", -1)),
    rows=(("Na", "N"), ("Na", "P"), ("K", "N"), ("K", "P"), ("anion", "N"), ("anion", "P")),
    modes=(("import", (1, -1, 1, -1, 2, -2)),),
    monomial=MonomialForm((MonomialRate(factors=(MonomialFactor(1.0, (MonomialTerm(1.0, (
        (Reference("Na", "N"), 1.0), (Reference("Na", "P"), -1.0),
        (Reference("K", "N"), 1.0), (Reference("K", "P"), -1.0),
        (Reference("anion", "N"), 2.0), (Reference("anion", "P"), -2.0))),)),)),)))

SALT = CycleForm(
    kinetics="monomial",
    roles=(("cation", None), ("anion", None)),
    rows=(("cation", "N"), ("cation", "P"), ("anion", "N"), ("anion", "P")),
    modes=(("import", ("n_cation", "-n_cation", "n_anion", "-n_anion")),),
    parameters=tuple(Parameter(n, "1", low=1, high=2, integer=True, positive=True) for n in ("n_cation", "n_anion")),
    monomial=MonomialForm((MonomialRate(factors=(MonomialFactor(1.0, (MonomialTerm(1.0, (
        (Reference("cation", "N"), Affine("n_cation", 1.0)), (Reference("cation", "P"), Affine("n_cation", -1.0)),
        (Reference("anion", "N"), Affine("n_anion", 1.0)), (Reference("anion", "P"), Affine("n_anion", -1.0)))),)),)),)))
```

All four declare `host="cells.transporter@1"`. The exchanger and the transport law declare `stage_term`. All but the
transport law's fuel rows are ions moved in base forms, so each declares `forms="base"` and
`reads=("rapid_binding@1",)`. All declare `material_term` from step 5 on. The transport law declares
`maintained_held_rows@1` as its one fuel kind; the last law declares `electroneutral`.
