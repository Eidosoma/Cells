# Calcium: channels that carry it, a store, and the sodium/calcium exchanger (design)

**Status: proposed, 25 November 2026, for the lead.** Desk work only: no engine code. Written on branch
`calcium-store-design` from 43b22d40 (main's 49529e71 differs from it by docs only). **No second reader yet:** the
advisor was asked three times and timed out each time, so the checks below are this note's own.

**What it answers.** Candidates G-1 (calcium-permeant channels) and G-4 (a calcium store) and row B2 (the 3 Na : 1
Ca exchanger) of the legacy port plan, with the corrections of its re-expression map (`legacy-port-plan` at
a1db6ab9, §14). This is the map's stream D. Stream E owns the factor source that opens the store's release (G-5) and
G-7.

**Engine models (AGENTS.md).** `resolved_pump_composite@1` over `resolved_pump_tissue@3` ("@3"), with the kinds
`cells.passive_routes@1` and `cells.transporter@1` and the operators `cell_owned_compartments@1` and
`local_species_reactions@1` ("D152's reactions").

**Marks.**
- **(M)** measured by this note's probes, listed with their commands and outputs in Appendix A;
- **(R)** read in the code at 43b22d40. Paths start at `src/cells/` unless they say otherwise;
- **(S)** this note's own derivation, arithmetic or estimate. Nothing marked (S) was run;
- sources: [abs] the abstract, or the page as a reader tool showed it; [rec] the bibliographic record only; [sec: X]
  through X.

## 0. Summary

1. **Most of the store runs on today's engine (M).** Two planted law modules, data only, were enough for a one-cell
   world with a store: pump, leaks, a release route (ungated, since its source is E's), kinetic buffers, a plasma
   pump and the exchanger. It parses, steps under the composite, and closes its energy ledger.
2. **What is missing is small** (the table below). The pieces are general. None is written for one experiment.
3. **Every piece keeps the ensemble's equations.** Only the integrator and the splitting change. So a derived band
   can apply to every row, and no row needs the consumer's own 3e-9 criterion (§12).
4. **The price is about 6 to 7.5 agent-days (S),** against the plan's 7.5 to 13 for the same three items (§15).
5. **No new family word is needed** (§13). One question goes to the user, nine to the lead (§16).

| Piece | Today | What this note adds | Equations |
| --- | --- | --- | --- |
| Calcium as a species row | runs | nothing | unchanged |
| Calcium through a gated channel (G-1) | refused at the parse; then the buffers refuse it (M) | the law as the one authority for its ions' valences; a per-stage material bound for channels; a door for the buffers; the module `cav1p2_m2h@1` | unchanged |
| A store with its own voltage | runs on @3; its declaration is refused in a closed world (M) | refusal 6's door | unchanged |
| The store's pump | @3's own pump is refused there (R); a planted cycle law is admitted and matches bit for bit (M) | the cycle law `atp_driven_transporter_mass_action_positive@2`; the transporter's material bound for the charged rows it moves | unchanged |
| The store's leaks | run (M) | nothing | unchanged |
| The release | its route and its `factors` list run (M, R) | the bound on the feedback a factor brings (§6.5); the source is E's | unchanged |
| Buffers, cytosol and store | run (M) | nothing beyond G-1's door | unchanged |
| The exchanger (B2) | a planted law is admitted and matches to 1.9e-15 (M) | the module `sodium_calcium_exchange_symmetric_barrier@1` | unchanged |
| The plasma pump (B1) | @3's live law equals the legacy kernel bit for bit with a converted constant (M) | nothing needed; one law for both pumps is recommended (§6.3) | unchanged |

**The choices, each with one recommendation:**

| | Choice | Recommended | The main alternative, and why not |
| --- | --- | --- | --- |
| C1 | Where calcium lives | one row of free calcium per node, bound forms as their own rows (the ensemble); a row of totals under `rapid_binding@1` (the cardiac plan). Both are on main; a world picks per node | a second row for the store's calcium inside the cell's node: it loses the store's volume and voltage |
| C2 | How a channel carries calcium | a channel population on @3, whose law declares each ion's valence, with constant-field flux | gates as a factor source on a charged passive route: no core change, but a second home for voltage-gated channels (§5.1) |
| C3 | Where the store lives | a compartment of FR-1 with its own capacitor, for the ensemble | pools at the cell's potential (the cardiac plan's): a changed model for the ensemble, and the right form for a dyadic subspace (§6.1) |
| C4 | A closed exterior | the compartment's node must not be its component's representative | a held bath: a changed model (the map, §14.1) |
| C5 | The pump | one cycle law on the transporter kind, any valence, any host | per-stage terms for @3's own pump: a special case in the core, and no host for the cardiac SR (§6.3) |
| C6 | The release's opening | the existing charged route, its `factors` list, and a stage bound for the feedback | a law of its own: it would hold the gate and the flux together, for one ligand |
| C7 | Buffers | D152's mass action, as today | the rapid closure: a changed model for the ensemble, and the cardiac plan's form |
| C8 | The exchanger | one module in the monomial form | the cardiac lane's four-state cycle: a changed model (§7, the user's question) |

## 1. What is refused today, and where

| # | Refused | Where | Shown |
| --- | --- | --- | --- |
| 1 | a channel's calcium ion: "Channel ion requires its law's species and valence" | `definitions/surface_pump_v3_spec.py:169, 328-329` | (M), with a planted law |
| 2 | any calcium channel law by name: none is registered on @3 ("Channel requires a resolved_pump_tissue@3 law and permeant ions") | the same file, 321-322 | (M) |
| 3 | a reaction that writes calcium while a channel carries it: "acts on species with zero membrane, junction and channel permeability only" | `operators/species_common.py:167-192` | (M) |
| 4 | calcium as a covered counter-ion. The threshold is 100. Its margin is 4.6 on the plasma patch with a held bath (M); the map's arithmetic for the closed worlds gives 3.7 there, 10.5 on the store's patch and 1.3 on the junction | `operators/species_common.py:204, 207, 255` | (M) |
| 5 | @3's calcium pump, its Na/K pump, or a channel population on a compartment's bounding patch | `operators/compartments.py:356-366` (refusal 4) | (R) |
| 6 | a cycle law's move at a compartment's node, unless the law declares a step term that its kind holds. Of the cycle laws only the proton pump declares one | `operators/compartments.py:270-342`; `laws/pumps/proton_pump.py:264` | (R); a planted law that declares both terms is admitted (M) |
| 7 | a compartment in a world without a held bath | `operators/compartments.py:513-518` (refusal 6) | (M) |
| 8 | declared kinds, reactions and routes at a compartment under RK4 | `models/surface_pump_v3.py:3412-3427` | (M) |
| 9 | the composite on a GPU in the vector windows, and device row checks on any GPU | `execution/vector_windows.py:213-230`; `execution/row_checks.py:72-76` | (R) |

**Not refused, but not bounded.** Each is a gap that the pieces here would otherwise widen.

| # | No bound today | Where | Shown |
| --- | --- | --- | --- |
| 10 | a trace ion's material relaxation through a channel. Adding the calcium channel left the stage's material rate at 2.42 per second | `models/surface_pump_v3.py:3701-3727` | (M) |
| 11 | a charged row that crosses in a cycle: the material term counts neutral rows, and charged rows changed at one end only | `kinds/transporter.py:2240-2250` | (R); named by `docs/CHARGED_TRACE_SPECIES_DESIGN.md` §6 for the kinds owner |
| 12 | the feedback of a factor on the row it reads. The stage rules use the routed value, never its slope | `models/surface_pump_v3.py:3682, 3721` | (R) |

Row 12 is the reason the coupling operator refuses an instantaneous read of a charged species: "could close a loop
@3's bound does not see" (`operators/species_regulated_availability.py:748-753`).

## 2. The two consumers, and what they share

### 2.1 The calcium ensemble

Four worlds (`configs/{spatial,plasma,gated,ip3}_calcium_cluster.json`), two cells each, all synthetic. The map's
§14.2 and §14.3 hold their equations and file lines. In short, each adds to the one before:

| World | Needs | From |
| --- | --- | --- |
| `spatial_calcium@1` | a store per cell (pump, K and Ca leak, release), buffers in the cytosol and the store, Ca on the plasma patch, the junction and the faces | G-4; E's calcium factor |
| `@2` | the plasma calcium pump and the exchanger | B1; §7 |
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
| Na/Ca exchange | one mode, 3:1, a symmetric barrier | a four-state cycle with a sodium leak mode | the transporter's population axis, in both | two kinetic forms: the user's question (§16) |
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
declared trace (`background`), as FR-4's worlds do. It is inert there: no route, no reaction, zero diffusivity.

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

**Recommended: A.** C is the map's other form, and it is real: it needs no core edit and it reads concentrations for
free. But it gives voltage-gated channels a second home, chosen by whether an ion is scarce. The same law could not
be hosted in both. Nothing that acts on channel populations would act on it, G-7's assembly factor included. D211's
22 calcium and HCN laws, some of which carry Na and K as well, would leave the channel interface. **C stays the
fallback** if the lead wants no core edit in this cleanup. Its equations are the same, so it can be replaced by A
later without a changed model.

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

**The module `cav1p2_m2h@1`.** The existing kernel (`laws/channels/calcium_gates.py`), as a `ChannelLaw` on @3:

```text
u = V - 0.010 V                          (the source's shift, part of the law)
m_inf = 1/(1 + exp(-(u + 0.030)/0.006))  h_inf = 1/(1 + exp((u + 0.080)/0.0064))
tau_m = 0.005 + 0.020/(1 + exp((u + 0.025)/0.005)) s
tau_h = 0.020 + 0.050/(1 + exp((u + 0.040)/0.007)) s
open = m^2 h;  permeant (("Ca", 2, 1.0),);  V in [-0.120, 0.060] V;  no temperature term
```

Its code is the host's next free one, its numbers are the source's, and its RK4 bound is the resolved channel
family's 25 µs. Its page and docstring use neutral words: the live module's text names its source in its first line
and calls the shift "native" (`laws/channels/calcium_gates.py:1-5`).

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
- **The charge bound** is today's: F²/(RT) sum z² P r a open v A max(c), so z = 2 counts four times.
- **The material bound (new).** A channel law may declare `material_term`. Its populations then add to the stage's
  material rate, at each explicit stage, at that stage's voltage:

```text
at the cell:     T_c,s = 1e15 A P r_s a open v u B(-x_s) / V_c     1/s
at the outside:  T_o,s = 1e15 A P r_s a open v u B(+x_s) / V_o     1/s
```

  Each end takes both terms where the other end relaxes too (a finite outside node), and its own where the other is
  a held bath: D310's form. A node's rate is the largest over species of the sums, added to the kinds' rates. The
  step is refused where dt times it exceeds 1 (`EXPLICIT_STEP_BOUND`). FR-51's part through the reversal potential
  is added to the direct part where a block uses it, and the direct part is never counted twice. At the ensemble's
  Cav1.2 it is 0.02 per second at the start and 0.7 at full opening (S).
- **Where the term is:** `models/surface_pump_v3.material_rate`, with the kernel that exists
  (`laws/routes/constant_field_permeation.material_slope_per_s`). Under N2 it stays, since N2 is implicit in
  voltage, not in amounts.

### 5.4 The door for the buffers

`species_common.check_impermeant` refuses a written row with a channel route because nothing bounds that route. So:
- a channel route whose law declares `material_term` no longer counts, for `local_species_reactions@1` only (the one
  operator that admits charged rows, and one that refuses RK4);
- @3's membrane and junction permeabilities still count. Calcium's leaks and its junction route are
  `passive_constant_field_permeation@1` routes, as the map has them;
- with that clause lifted in a probe, the buffers and a calcium channel parse together, and the composite steps (M).

### 5.5 Heat, integrator, refusals, restart

- **Heat and work:** passive, heat only. Default booking, or `heat_bookings: {"channels":
  "trapezoid_nonnegative@1"}`.
- **Integrator:** the flux is explicit at each ARS(2,2,2) stage; the gates take the exponential stage update; second
  order. N2 treats the slope in voltage implicitly.
- **Refused by name:** an ion whose valence differs from its law's; a gate outside [0, 1]; a voltage outside -120 to
  +60 mV; a channel on a compartment's bounding patch (refusal 4, unchanged); a population of other gate counts
  beside two-gate laws (today's `NotImplementedError`, `models/surface_pump_v3.py:619`, H1's seam); a reaction that
  writes a channel-carried row whose law declares no material term (today's words).
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

### 6.2 Refusal 6's door

- **Today:** a compartment's owner must lie in a capacitor component that holds a held bath.
- **The rule:** the compartment's node is not its component's representative. The solver picks the gauge where the
  component holds it, else the component's lowest outside node (`numerics/surface_field.py:299-304`). One host-side
  helper beside `bind` gives that node, so the two never drift.
- **Closed worlds** (one gauge, no held bath): the gauge is the representative, and refusal 1 already says a
  compartment is never the gauge. The ensemble's gauge, `local`, is in its owners' component.
- **A floating component without the gauge** is admitted where its lowest outside node is not a compartment, and
  refused by name where it is.
- **Measured (M):** in a closed store world the store's node is free and the bath node is fixed; 80 steps hold the
  capacitor rows to 5e-29 C, the material to 1e-20 fmol and the energy to 2e-7 of the flows.
- **Not extended:** FR-1's silence claims S1 to S3 stay claims of the held-bath topology until a row shows them in a
  closed one.
- **D148:** host only. No program changes.

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
the ensemble's start (M).

| | P-A. Per-stage terms for @3's own pump | P-B. A cycle law on the transporter kind (recommended) | P-C. @3's pump on the plasma patch, the cycle law on the store |
| --- | --- | --- | --- |
| What | refusal 4 admits @3's calcium pump; `membrane_rate` and `material_rate` gain its slopes at both ends | the new law, on any host the table knows | the map's first form |
| Law count | one | one in the world; @3's own stays for other worlds until it moves | two hosts for one equation in one world |
| Fuel | constants, no rows | three held rows | both |
| Hosts | patches | patches now, a pool route when the core adds that host kind (`models/surface_pump_v3.py:3775`) | mixed |
| Core edit | yes, static, for one law | none | none |
| Cardiac uptake and sarcolemmal pump | cannot serve the SR | serves both, as two populations for the phosphorylated form | serves the SR only |
| Price (S) | 1 to 1.25 days | 0.5 for the law, 0.75 for the kind's bound | as P-B |

**Recommended: P-B, for both of the ensemble's pumps.** The store needs the fuel rows in any case, so the plasma
pump adds none. @3's `ca_atp_mass_action_positive@1` is the same equation: bit for bit on 2,000 random states when
the constant is converted, dG0(1 M) = dG0(mM) + RT ln 1000 = -19,875.97 J/mol here (M). So P-C's plasma pump is no
changed model either, and the lead may keep it. @3's own pump retires with the roadmap's "pumps moved onto the kind"
(`docs/CORE_LAWS_ROADMAP.md`, family 2), not here. A definition that puts both laws on one patch for one species is
refused: one representation of a pathway per patch (D175).

**The law: `atp_driven_transporter_mass_action_positive@2`.** The neutral law's factored form with the role's
valence free (`CycleForm` roles `("role", None)`), held fuel only in this build. @1 and the proton law keep their
IDs and their judged worlds. At z = 0 @2 is @1's equation, so @1 can retire when its own worlds move to @2, as the
roadmap queues for the pumps.
- **Why a new major, not a calcium name:** the mechanism is ATP-driven transport of one species. Nothing in it is
  calcium's.
- **Its potentials:** the three fuel rows' are the species registry's, at its c0. D152's standard concentration is
  checked against it (`check_potentials`), and both are 1 mM here, so the drive is the ensemble's numeric-mM
  quotient.
- **Finite fuel under a charged role** waits for a consumer (G-6).
- **Its declared step terms:** `stage_term` and `material_term`, so refusal 4 admits it at a compartment's node. The
  kind supplies both.

**The kind's material bound (kinds owner's file).** Where a population's law declares `material_term`, its charged
crossing rows count too: for each moved row k at node v, sum over modes of |nu dJ/dn_k|, plus the partner end's
where that end relaxes (D310's two-end sum). A static field, as K3b's, so a definition whose laws declare none keeps
its fields and programs. The neutral rows are as today.

- **State:** `cycle_count`, `cycle_dissipated_energy_pJ`, `cycle_metabolic_work_pJ`, `cycle_supplied_fmol`
  (existing).
- **Ledgers:** role -n at N and +n at P per cycle; charge through the field; heat -J x RT, work -J times the fuel's
  drive, the held fuel's supply recorded. **Roles:** heat and work.
- **Refused:** |x| above 80; K or K_ATP not positive; n outside 1 to 4; fuel rows that are not neutral or that
  another route moves; @3's calcium pump on the same patch for the same species (a host-side check in the kind: one
  law moves a species by this mechanism on a patch); RK4.
- **Provenance:** the form is the engine's own mass-action completion
  (`laws/pumps/nak_atp_mass_action_positive.py`), no number taken. One calcium per ATP is the ensemble's declared
  stoichiometry. A two-calcium cycle is the biological SERCA's (Tran et al. 2009 [rec]); n = 2 is a parameter.
- **Not claimed:** a SERCA or PMCA mechanism, proton counter-transport, or any kinetic constant.

### 6.4 The leaks

- **K on the bounding patch:** @3's own constant-field permeability. K is a major ion, so the charge rule holds it.
- **Calcium on the plasma patch, the bounding patch and the junction:** `passive_constant_field_permeation@1`
  routes: charge slope, material slope and heat exist, and a junction host exists (D310). In these worlds no
  junction crosses a floating component, since both cells lie in the gauge's (S), so D310's refusal does not arise.
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
m = (the patch's availability) x f_Ca(c_cytosol) x f_IP3(c_IP3, cytosol)     the product of the sources in its `factors` list
J = 1e15 A P_release m [c_store B(x) - c_cytosol B(-x)],  x = 2 F V_b / (RT)    fmol/s into the cytosol
```

Nothing changes in the route: its `factors` list, its routed control and its slopes at the routed opening are on
main (R).

**What the route needs from any source of its kind:**
1. its value at each explicit stage, on the stage's read, in [0, 1], finite;
2. the concentration of a declared species (any valence) at a declared node, through the stage read, so that a
   closure's free calcium is what a closure's world sees;
3. two host-side and device hooks, used only for the bound below: `factor_rows(declaration)`, the (species, node)
   each source reads, and `factor_log_slopes(read, p)`, |d ln f / dn| in 1/fmol.

**The feedback bound (recommended).** Calcium released raises the calcium the factor reads. The stage rules use the
routed value but not its slope (§1, row 12). For each routed slot r whose sources read a row that the same route
moves at the same node:

```text
loop rate at that node  =  |J_r| x sum over its sources of |d ln f / dn|     1/s, added to the stage's material rate
```

- **At binding** the core pairs a slot's `routed_rows` with its sources' `factor_rows`, so the pairs are static. A
  world with none has no term, and its programs are today's.
- **A sink gains** two hooks: `routed_rows(declaration)`, the rows each routed slot moves (host), and
  `routed_flux(read, potentials, control, p)`, its slots' |J|. The passive routes have both, and @3's channel
  populations too, so the same rule covers an inactivation factor on a calcium channel.
- **Its size in the ensemble (S):** J_r 0.0157 fmol/s, d ln f/d ln c = 0.38, 0.001 fmol free: 6 per second, 7.5e-5
  per 12.5 µs step. Nothing there binds.
- **Its limit, stated:** loops through two routes (one moves X and gates on Y, another moves Y and gates on X) are
  not bounded.
- **The alternative** is to state the missing bound and build nothing. It would pass the ensemble. It would leave a
  hole that the coupling operator already refuses for this reason.
- **Owner:** the core's part and the sinks' are this stream's, the two source hooks E's. 0.75 of a day (S), for the
  lead to place (§16).

**Integrator, heat, restart.** Explicit at each stage, at the stage's own calcium, as legacy's. A route books heat
only. The factor books nothing. No state of its own. **Refused by name:** an unknown source, a source outside [0,
1], a factor held through the step (a changed model). **Provenance:** the flux is the constant-field form; the
factor's is E's. **Same equations:** yes, with the factor at each stage.

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
do not (§16, L9). In these worlds the calcium routes stay far from reversal, and the K leak's power near its own
zero is below the tolerance (S).

**Closure measured:** energy-rate balance -1.4e-16 of 0.85 pJ/s; the largest relative ledger over 80 host steps at
12.5 µs is 1.6e-7, and it falls by four per halving (1.6e-7, 4.1e-8, 1.0e-8); the composite's, with buffers, after 5
steps at 6.25 µs is 9.5e-9 (M). The engine's own limit is 2e-3 of the flows plus 2e-8 pJ.

### 6.8 Not claimed

- A biological ER, SR or any calibrated constant. Every value is synthetic.
- That the voltage, the counter-ion and the pump stoichiometry are right for any cell.
- S2's equivalence to S1 in any regime.
- The division, fusion or growth of a store: FR-1's later doors.

## 7. The exchanger (B2): one module, no engine change

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
| Declared | `stage_term`, `material_term`; `forms="base"`, `reads=("rapid_binding@1",)` (a pure exchange of ions: its rows are base forms, so a closure may hold them) |

- **Checked (M):** the planted module parses in the store world and gives the legacy kernel's rate to 1.9e-15
  relative. Its free energy needs no registry potential, since nothing is converted.
- **State, ledgers, heat:** as §6.7's row. The trapezoid booking is admitted.
- **Same equations:** yes. The kind's domain is x <= 80, one-sided; legacy's is |x| <= 80 and |V| <= 0.15 V. Those
  differ only outside the worlds' range.
- **Provenance:** cited form. Measured reversals close to a 3:1 exchange (Matsuoka and Hilgemann 1992, the third of
  a series on giant patches, the one PMID 1336540 names [abs]), and a whole-cell study of guinea-pig myocytes finds
  3:1 (Hinata et al. 2002 [abs]). **Against it:** one 2000 study of the same cells in inside-out patches concluded
  4:1 or variable (Fujioka, Komeda and Matsuoka [abs]), and a 2004 study reports minor transport modes beside the
  3:1 (Kang and Hilgemann [abs]). 3:1 is the form's. The evidence for it is not one study's, and neither is the
  evidence against it.
- **The denominator and the equal barrier are synthetic.** The same 1992 work reports that voltage dependence
  changes with calcium and sodium on either side, which a fixed half split does not do [abs].
- **Not claimed:** a calibrated exchanger, its inactivation, calcium activation, or any other mode.
- **The name:** `sodium_calcium_exchange_symmetric_barrier@1`. The live constant says
  `ncx_3na_1ca_symmetric_barrier@1`; names state a mechanism and its form, not a protein family.
- **The plasma pump (B1)** is re-parameterised, as the map says. Nothing else is designed for it (§6.3).

## 8. The step, and the rules it is held to

**One composite step of size h:**
1. Event maps (none in these worlds).
2. D152's first half, h/2, at every reaction site (cytosol and store).
3. @3's IMEX step, ARS(2,2,2). At each explicit stage: the stage's read; the routing door, which multiplies the
   release by its factors at that read; the field solve (C + a h L) phi = q, with faces implicit; the rates of @3's
   patches, pumps, channels and junctions and of the kinds; the stage's checks. Gates take the exponential update.
4. D152's second half, h/2.

Second order in h. `cell_owned_compartments@1` runs no part.

**Every explicit stage refuses the step where:**
- charge: h times the largest sum of conductances over capacitance (cells, and free outside nodes, the store's
  included) exceeds 1. At the ensemble's store it is 5,291 per second (M), the K leak's 5,257 of it (S), so 0.066 at
  12.5 µs, well below the limit. FR-4's 0.05 was a limit of the energy ledger in other worlds; here the ledger holds
  at 1.6e-7 (M);
- material: h times the largest material rate exceeds 1, now with the channels' term (§5.3), the cycles' charged
  rows (§6.3) and the feedback (§6.5). 2.4 per second measured, 8 with the feedback (S);
- domain: each law's own. D152's halves hold h L <= 1 at each stage, on unidirectional rates.

**RK4 is refused** for every world with a store (§1, row 8).

## 9. Ledgers

| Ledger | How it closes |
| --- | --- |
| Amount, per species and node | every route writes two nodes equal and opposite; D152's extents times its stoichiometry; held rows do not move |
| Amount, whole world | the sum of all nodes (the worlds are closed, so it is constant) |
| Charge | z-weighted: each node's row, the capacitor rows, the electrode at the gauge. Reactions add zero by construction |
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
| `scheduled_bath_composition@1` | composes beside a held bath; a closed world has none | composes | composes |
| `templated_polymerisation@1`, `neutral_arrival_labels@1`, `population_unit_turnover@1`, membrane state | as the compartments' list says | as their own rules | as their own rules |
| `scheduled_cell_replacement@1`, `@2`; trafficking | refused: a declared kind is present | composes (no kind) | refused: a declared kind is present |
| Insertion, division, lumens | refused by the compartment | as their own rules | refused or admitted by the kinds' lifecycle roles |
| Water, `k_anion_symport` | refused by the compartment (volume) | as today | as today |
| Compartment wash, site occupancy, bridge | refused by the compartment's list | as today | as today |
| RK4 | refused | admitted on @3 alone, to the law's 25 µs bound; no material rule runs there | refused |
| `rapid_binding@1` | the closure refuses @3 routes and pumps on its rows; a Ca channel reads through the closure but is refused there today (§2.3, H2's) | refused on a held row | admitted for laws that declare the read |

## 11. D148, CPU, GPU, restart

- **D148 (bit for bit when not declared).** The parser's valence check, the reactions door and refusal 6's door are
  host only. The channel material term exists only where a declared channel law declares it; the transporter's,
  where a population's law does; the feedback, where a routed source reads a row its sink moves. Each is a static
  choice by shape or structure, as K3b, FR-51 and B1 are. Every world of today's keeps its programs, layouts and
  Every world of today's keeps its programs, layouts and fingerprints. Proof: the cleanup's one gate, with
  crossrev's sets, G1's 113 worlds and FR's set.
- **CPU:** everything here runs there. The probe's composite world took 26 s to parse, compile and step five steps
  (M).
- **GPU:** nothing in these laws blocks one (no host callback, no data-dependent loop). What blocks is the
  composite's path: refused in the vector windows (D338), and a plain, unflagged run on a GPU is the user's open
  choice (D380). The buffers and the identity declaration make the world a composite; the rest of the store is @3
  and its kinds. **So two routes stay open for later:** a GPU qualification of the composite (G-8), or the store on
  @3 with `rapid_binding@1` as its buffers, which is a changed model.
- **Restart:** no new state. Gates, cycle counts, transfers and heats are checkpointed. The store's nonzero charge
  anchor is admitted on import, since the world declares kinds and IMEX (refusal 5).

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
  half a day (§16, L7).

## 13. IDs, registry pieces and pages

**On the branch, code is written with today's bare IDs** and the scripted move follows (D383). Every ID below takes
a family that exists.

| Piece | Today's ID | After the move | Family word |
| --- | --- | --- | --- |
| Channel law | `cav1p2_m2h@1` (in the catalogue) | `cells.channel.cav1p2_m2h@1` | existing |
| Cycle law, the pump | `atp_driven_transporter_mass_action_positive@2` | `cells.cycle.atp_driven_transporter_mass_action_positive@2` | existing |
| Cycle law, the exchanger | `sodium_calcium_exchange_symmetric_barrier@1` | `cells.cycle.sodium_calcium_exchange_symmetric_barrier@1` | existing |
| E's source and its law | E's note | `cells.kind.*`, `cells.transfer_factor.*` | existing; `transfer_factor` is D383's |

- **No new interface** here. `ChannelLaw` gains one defaulted field, `material_term` (D191's precedent for
  `JunctionLaw`); the declarations manifest shows it.
- **Four optional `Kind` hooks** (§6.5): a source's `factor_rows` and `factor_log_slopes`; a sink's `routed_rows`
  and `routed_flux`.
- **Model table:** three new homes on @3's row, each an inert module.
- **Library pages:** one for each of the three laws, with their independent reference, plant and stated limits.
  `transporter@1`'s generated blocks, the index and the glossary follow `library_pages.py --write`. The glossary
  gains "store".
- **Notes to amend:** CLOSED_COMPARTMENT_DESIGN §3.5 (the door), CHARGED_TRACE_SPECIES_DESIGN §6 (the transporter's
  bound is built), HUMAN_CARDIAC_LAWS_DESIGN §1 and §6 (§2.2 above), CORE_LAWS_ROADMAP families 1, 2, 5 and 9.
- **At the deletion,** `laws/reactions/er_calcium.py` and `plasma_calcium.py` reduce to one function, `pump_rates`,
  which the live pump law uses: it can move into that law's module. Their first lines name BETSE, and so does
  `calcium_gates.py`'s.

## 14. Tests (rows, with plants; D224)

Rows go into existing files. One new file holds the world-level rows. Times are estimates from the probes (S); each
is measured at the landing. A planted row must fail the criterion it names.

| # | Row | File | Plant | Est. |
| --- | --- | --- | --- | --- |
| 1 | the parser reads each ion's valence from its law | `test_chloride_leak_law.py`, `test_inner_laws.py` | a law that says Ca is +1; a model whose Ca is +1 | < 1 s |
| 2 | `cav1p2_m2h@1` against its independent reference at 1,801 voltages | `test_kv1_channel_laws.py`, a new row beside its laws | the 10 mV shift dropped; m² for m³ | 1 s |
| 3 | its flux, transfer and heat at a state (valence 2, both directions) | the same | z = 1 | 1 s |
| 4 | the channel material term against a NumPy finite difference of dJ/dn at each end, over voltages and openings; largest over species | new `tests/unit/test_calcium_store.py` | B(x) and B(-x) exchanged; the term absent at a store's node | 2 s |
| 5 | the reactions door: a Ca channel beside a written Ca row, with and without the term; RK4 | `test_species_reactions_refusals.py` (its charged-rows table) | a law that declares none; a membrane permeability | 1 s |
| 6 | refusal 6: a closed store world admitted, a store as a component's lowest outside node refused, the gauge refused, and the helper equal to `bind`'s fixed nodes | `test_cell_owned_compartments.py` (its refusal table) | a representative picked the other way | 3 s |
| 7 | refusal 4: the new cycle laws at a store's node, moved by step terms; both pump laws on one patch refused | the same (its planted-moves table) | a law that declares one term or none | 2 s |
| 8 | the pump @2 against the NumPy closed form, at z = 2, 1, -1 and 0 (at 0 its rate is @1's), n = 1 to 4; the slopes at both ends against finite differences | `test_cycle_kind.py` | the electrical sign; n applied to K twice | 2 s |
| 9 | the exchanger against the product formula at random states, and its reversal, heat sign and slopes | the same | zeta +1/2; K^3 for K; Ca and Na roles exchanged | 2 s |
| 10 | the material bound counts charged crossing rows where declared, and nothing else changes | `test_cycle_kind.py` | a world without the declaration differs by one bit | 2 s |
| 11 | the feedback bound against a finite difference of the stage's derivative; no term without a loop | `test_passive_routes_kind.py` | the slope dropped; a source on another node | 2 s |
| 12 | a one-cell store world against a code-blind SciPy solution, NumPy steps at h, h/2, h/4: amounts, V_b, heat, the order | the same new file | the release's sign; the pump's electrical term; a 1% change of each constant must exceed the band | 15 s |
| 13 | the composite store world, 5 compiled steps, restart equal | the same | the store's anchor dropped on import | 30 s |

**About 60 s in all (S).** The code-blind reference for rows 8, 9 and 12 is written by a fresh agent from this
note's equations, and never from the code.

## 15. Price, order and owners

| Step | Work | Files | Days (S) |
| --- | --- | --- | --- |
| 1 | the parser's valence rule; `cav1p2_m2h@1` | `definitions/surface_pump_v3_spec.py`, `laws/channels/cav1p2_m2h.py`, `model_table.py` | 0.75 |
| 2 | the channel material term and the reactions door | `models/surface_pump_v3.py`, `registry/laws.py`, `operators/species_common.py` | 1 to 1.25 |
| 3 | refusal 6's door | `operators/compartments.py`, `numerics/surface_field.py` | 0.5 |
| 4 | the pump @2 and the exchanger, with their references | `laws/cycles/`, `laws/pumps/` | 1 |
| 5 | the transporter's material bound | `kinds/transporter.py` | 0.75 |
| 6 | the feedback bound (with E's hooks) | `models/surface_pump_v3.py`, `registry/kind_registry.py`, `kinds/passive_routes.py` | 0.75 |
| 7 | the store world: references, rows 12 and 13 | `tests/unit/` | 1 to 1.5 |
| 8 | pages, notes, matrix, the roadmap | `docs/` | 0.5 to 0.75 |
| | **In all** | | **6.25 to 7.25, so about 6 to 7.5** |

- **Order.** 1, 3 and 4 are independent. 2 follows 1. 5 follows 4. 6 waits for E's source. 7 waits for all. The
  re-expression of the four worlds follows.
- **Not in this price:** the re-expression and its qualification (the plan's 8 to 12 days); H1's and H2's own work;
  D211's other channel laws (about 0.15 to 0.25 of a day each).
- **Files two streams share:** `models/surface_pump_v3.py` (one owner for steps 2 and 6), `registry/model_table.py`
  (three new lines, coordinated with E), `kinds/` (the passive routes and transporter are this stream's).

## 16. Questions

### 16.1 For the user

**U1. The exchanger: two kinetic forms, one mechanism (D210, D211).** The ensemble's exchanger is one mode with a
synthetic denominator. The cardiac lane plans a four-state cycle with a sodium leak mode. D211 folds the exchanger
into that lane. Options:
- (a) register the ensemble's form now as its own law, and when the cardiac cycle lands, either declare it a
  representation of that law (D175) or retire it. **Recommended:** it keeps the ensemble's equations and stays on
  one kind. It costs half a day. The cardiac law takes nothing from it.
- (b) wait for the cardiac exchanger and re-express the ensemble on it: a changed model, judged by the ensemble's
  own criterion, with no date.
- (c) register it and keep it for good beside the cardiac law, against D210's reading of one law per mechanism.

### 16.2 For the lead

- **L1. C2, the calcium channel's form** (§5.1): A, recommended, or C as a stopgap with no core edit.
- **L2. C5, the pump** (§6.3): P-B for both pumps, recommended, or P-C (the map's form), or P-A.
- **L3. The feedback bound** (§6.5): build it now with E's hooks, recommended, 0.75 day, or state its absence as a
  limit of the release.
- **L4. Refusal 6's rule** (§6.2): "not the representative", recommended, or "the gauge's component only".
- **L5. The scope of the buffers' door** (§5.4): `local_species_reactions@1` only, recommended.
- **L6. The energy criterion** (§12): the 1e-9 pJ bound measured first, or the engine's rule.
- **L7. Passive-route schedules** (half a day, a general feature): only if a registered row switches a leak or the
  release.
- **L8. `validation/betse/spatial_cluster/reference.py`** (§12): keep or move with the references.
- **L9. The trapezoid booking for passive routes** (§6.4): half a day, not needed by the ensemble. A charged route's
  heat is the tableau's, so a release that crosses its reversal within a step could be refused.

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
| 8 | the planted exchanger with the declarations of §7 (`reads`, base forms), and a store pump whose law declares no step term | parses, same rate; refused by name without a step term; a charge term alone is admitted (refusal 4's version 1.3) |

**Not run:** a step of the full four-world re-expression, buffers against a kinetic reference, any compiled GPU
path, and anything to 20 ms.

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

## Appendix C. The two cycle forms, as the probes planted them

Data only. Each becomes an inert module on the pattern of `laws/cycles/electrogenic_nucleotide_exchange.py`, with
its page, citation and test.

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
```

Both laws declare `host="cells.transporter@1"`, `stage_term` and `material_term`. The exchanger also declares
`forms="base"` and `reads=("rapid_binding@1",)`. The transport law declares `maintained_held_rows@1` as its one fuel
kind.
