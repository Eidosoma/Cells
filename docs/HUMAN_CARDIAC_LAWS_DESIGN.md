# Human cardiac laws: design (proposed)

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

**Status: PROPOSED, 16 November 2026; its choices for the user decided by D184 the same day.**
The user delegated the choices to the lead with the advisor and gave the go (D184, on main at
98c49993). Decided:
- the source is O'Hara–Rudy 2011's endocardial cell; the endocardial cell comes first;
  Hodgkin–Huxley sodium gates; 310 K;
- D138's and D151's approval for arms (A), (B) and (C) of §5.2, for O'Hara–Rudy 2011 only;
- D167's expectation for the human set: new channel laws, with the catalogue's laws kept as parity
  references (§9.2's question 12);
- FR-11's human loop: no generic stand-in.

The questions for the lead and the core owner (§9.2) are ruled after the landing. Design only: no
engine code yet. Written on branch `cardiac-laws` from 3c10b833, integration-d172's landing
candidate; the note reached main after D172's landing (merge b92b4c2b, 16 November 2026).

**The decision it serves: D183** (16 November 2026; on main at e9f19dff). The user: "let's bring
the human cardiac laws forward". Track E's human ventricular law set
([EXCITABLE_TISSUE_DESIGN.md](EXCITABLE_TISSUE_DESIGN.md) §3.3 and §7, and M4 and M5 of §11) starts
now as its own lane on the inner model that D172 lands. FR-11's human loop becomes a paced human
ventricular cell on this law set, with no generic stand-in, and waits for it. D184 corrects D183's
record: "no generic stand-in" was the lead's reading of the user's answer, which the delegation
keeps. The planarian loop stays first. D183 asks this note for options on the source of equations and parameters, the cell
types, the sodium current's form, the temperature and the verification, and for the D138 question.

**What stays as it was (D183):**
- each law is general and named by its mechanism, never after a protein or for one experiment
  (D144). Protein names below are biological context only, never IDs;
- a whole-cell comparison against a published model needs the user's approval (D138, D151), and
  §9 asks for it;
- external simulators run only out of process, against saved outputs. Parameter values from papers
  are facts, used with their citations; no external code is imported or copied (AGENTS.md).

**Engine models.** This note runs none. The laws it proposes would join `resolved_pump_tissue@3`,
D172's one modular inner model, as declared laws and kinds. The paced cell runs
`resolved_pump_composite@1` over it, with `electrode_current_injection@1` for pacing.

**Evidence and sources.**
- The engine as built: code read at 3c10b833 (file and function named where used), and the core
  owner's branch `core-next` (commits named where used).
- The design notes: EXCITABLE_TISSUE_DESIGN.md and its equations appendix; INNER_MODEL_V4_DESIGN.md
  §7 and §13 (on main, and §7.4 (l)–(n) on core-next); CLOSED_COMPARTMENT_DESIGN.md;
  COMPARTMENT_PH_TRANSFER_DESIGN.md; LOOPING_REPLAY_DESIGN.md on `run-view-d154` (fd008813).
- **The citation checks.** Two web-search subagents checked the cardiac conduction and
  action-potential citations on 14 November; their findings are in EXCITABLE_TISSUE_DESIGN §7.3
  and §13, with the same tags. Three more checked the source models and the licences on
  16 November (Sources, at the end). Tags: [full] full text, [abs] abstract only, [code] a published model
  file or the authors' code, [sec: X] a secondary source. **S** marks our own derivation,
  arithmetic or interpretation.
- No number below is typed from memory: each carries its source, or **S**.

## 0. The choices, in plain terms

1. **The source: O'Hara–Rudy 2011's endocardial cell (ORd), recommended and decided (D184)**
   (§4.1). It has no Markov
   form, its equations and tables are open (CC BY), its errors are documented, and it publishes
   its steady state. ToR-ORd (2019) is the better-calibrated successor, but it needs a Markov IKr,
   ionic-strength activities and Cl⁻ currents, and its paper and code differ in documented places.
   TP06 (2006) is the smallest, but ten of its currents are printed only in a 2004 paper that
   could not be read openly.
2. **The law set** (§2): eight new channel laws, two new transporter cycles (the Na⁺/Ca²⁺ exchanger
   and the Na⁺/K⁺ pump), a release law, a rapid Ca²⁺ buffer read and CaMKII. Moved from the
   catalogue (D167): the Na⁺ and Ca²⁺ leaks, the sarcolemmal Ca²⁺ pump, the SR pump and the
   constant-field route between pools. No catalogue channel law can carry ORd's gating.
3. **Calcium handling needs one new idea in the inner model** (§3): pools that share their cell's
   potential (a dyadic subspace and two SR pools). It opens "subspace calcium", which the
   inner-model note closes in version 1, so the lead rules on it.
4. **Cells closes energy for every route, and some published formulas do not** (§3.8). Each source
   formula is screened first. ORd's departures are listed in one closed table (§3.9): six definite
   (IKs per ion, the exchanger's own fluxes booked, two pump completions, a Fickian SR leak, exact
   constants) and three conditional on screens. TP06 needs more, one of which changes the model
   itself. Separately, reading the code shows that the engine's heat booking would refuse a
   current crossing its reversal within a step (§3.8; not yet run, so H1's first probe tests it).
   ORd's rest lies 0.17 mV below E_K, and the exchanger reverses every beat.
5. **The engine's route** (§4.5): extend @3's channel-law declaration with per-law gates, domains
   and reads, a declared linear driving force (most cardiac currents are G(V − E)), and kinetic
   coefficients as cited data, so cell types and re-fits are parameter sets, not laws.
6. **Cell types, INa and temperature** (§4.2–§4.4), decided (D184): the endocardial cell first;
   Hodgkin–Huxley sodium gates; 310 K.
7. **Verification** (§5): each law under voltage clamp against an independent reference (no
   approval needed), then a whole-cell comparison against the published model, **approved by D184
   for O'Hara–Rudy 2011 only (D138, D151; §9.1)**. The references go to fresh agents that read
   neither the engine nor the authors' code. External tools run out of process: Myokit is BSD
   3-Clause, desktop OpenCOR and ToR-ORd's code are GPL 3.0, and no licence read has a
   non-commercial clause (§5.3).
8. **FR-11's human loop** (§7): the paced cell at 1 Hz with a K⁺-only carrier. The slow ion
   inventories set its closure, and a periodic state costs minutes to days on one core, depending
   on the step. A single cell needs no junction law.
9. **Effort** (§8, **S**): about 33–48 agent-days for H1–H3, about 20–30 working days elapsed with
   three owners. Tissue (H4) is a milestone of its own, after `junction_ungated@1`, and it is where
   ORd's known weakness lies: at a common coupling it conducts the slowest of six human models,
   though its own strand gives 45 cm/s at 1 Hz (§4.1).

## 1. What the engine has, and what a human ventricular cell needs

A human ventricular cell needs, beyond D155's generic cell: a plateau carried by an L-type Ca²⁺
current with Ca²⁺-dependent inactivation; repolarization by the rapid and slow delayed rectifiers
and a time-dependent inward rectifier; a fast sodium current with slow recovery; Na⁺/Ca²⁺ exchange
and the Na⁺/K⁺ pump in the source model's forms; and calcium handling: a dyadic subspace, the
sarcoplasmic reticulum (SR), buffers, uptake and release. The table lists each gap as the engine
stands at 3c10b833 (code read for this note; **S** where it is our reading).

| Need | As built at 3c10b833 | Where |
| --- | --- | --- |
| Ca²⁺ (and, for ToR-ORd, Cl⁻) as channel ions | Channel ions are Na⁺ and K⁺ only | `definitions/surface_pump_v3_spec.py`: `SPECIES_VALENCE = {"Na": 1, "K": 1}`, `LAW_PERMEABILITIES` |
| Gating that reads concentrations: subspace Ca²⁺ (ICaL's Ca²⁺-dependent inactivation), cytosolic Ca²⁺ (IKs), extracellular K⁺ (IK1, IKr), and the CaMKII state | `ChannelLaw.kinetics(voltage, *, xp)`: voltage only. `reads` and `loop_term` are reserved and empty for every law | `models/inner_laws.py` (`ChannelLaw`); `surface_pump_v3.potential_kinetics` |
| Laws with more than two gates, and different gate counts in one world | `gate_rows` is the larger of 2 and the largest declared count, and a gated law whose count differs from it raises `NotImplementedError` | `surface_pump_v3.channel_kinetics` |
| Each law's own voltage domain | Declared per law (`ChannelLaw.voltage_domain_V`, −0.120 to +0.060 V for all five), but checked as one domain for every active population, leaks included | `surface_pump_v3.channel_domain_valid` (`VOLTAGE_DOMAIN_V`) |
| A linear driving force, G(V − E) | Every population's flux is the constant-field (GHK) flux | `surface_pump_v3.channel_rates` → `coupling/selective.selective_flux` |
| Kinetic coefficients as data, so cell types and source models are parameter sets | Coefficients are kernel literals. A population carries its law, P_max, abundance, initial gates and permeant ions only | `core/surface_kinetic_spec.ChannelPopulation` |
| An exchanger with no fuel (Na⁺/Ca²⁺ exchange), and the source model's Na⁺/K⁺ pump | The transporter kind's laws hydrolyse one ATP per cycle and move one role across a patch, one population per patch in version 1 | `kinds/transporter.py` |
| Rapid Ca²⁺ buffering | B4's closure, for protons only; its declaration admits one read in version 1 | `kinds/proton_buffer.py` |
| Intracellular pools at the cell's potential (dyadic subspace, network and junctional SR) | A cell is one well-mixed node. FR-1's compartments are capacitor nodes with one bounding patch, V_b = −q/C_b | CLOSED_COMPARTMENT_DESIGN §3.1 |
| SR release; CaMKII | None | — |
| Markov-form laws; subspace calcium | Closed in version 1 | INNER_MODEL_V4_DESIGN §13.1 |
| A source kind's factor (CaMKII's) reaching a channel population's availability | The routing door's sinks are kinds' own control fields | core-next 207393ba (INNER_MODEL_V4_DESIGN §7.4 (n) there) |
| A whole-cell voltage clamp | None. "Prescribed voltage here is an isolated gate input, not a supported whole-cell voltage clamp" | VOLTAGE_GATED_CHANNEL_SPEC.md |

**What carries over unchanged:** the per-law declarations and static dispatch (the inner-model
note's §7.4 (b), (c)), so an undeclared law adds nothing to any program; the exponential stage
gates (`exponential_mean_rate_linear_target_gates@1`); the kind interface with its seams (§7.4 (k)),
time-varying kind controls (core-next 614a081b, 5fcfe9ed), the stored-energy rate and the
`produced` ledger role (3e7095cc), the routing door (207393ba) and the kinds' run-view
declarations (74a75241); the transporter kind's held fuel (`maintained_held_rows@1`); B4's
stage-read pattern; `electrode_current_injection@1` for pacing; and Ca²⁺ already as a species
with a plasma-membrane Ca²⁺ pump in @3 (`ca_atp_mass_action_positive@1`).

**core-next's seams, by consumer here (S):** the routing door carries CaMKII's φ (§3.7); the kinds'
run-view declarations serve FR-11's loop (§7); the stored-energy rate serves a buffer read only if
its read does not carry its own term (B4's does); time-varying kind controls would serve scheduled
block or availability protocols later; the `produced` role has no consumer here, since no law
creates or consumes a species.

## 2. The law set for a human ventricular myocyte

The table is written for O'Hara–Rudy 2011's endocardial cell (ORd), the recommended source (§4.1);
§4.1 gives ToR-ORd's and TP06's differences. Every ORd fact is from the paper and its Text S1
[full], as read on 16 November 2026, with PLOS's correction of 14 September 2011 applied. ORd has
41 state variables (31 without CaMKII), and it uses no Markov model: its Discussion states the
"Exclusion of Markov models" [full].

**The "moved" test** (D167): a catalogue law moves only if its functional form can carry the
paper's parameters. The catalogue's gated channel laws are parity laws that hold their sources'
coefficients in the kernels: @3's three (BETSE v1.5.0's, in `laws/channels/sodium_channels.py`,
`potassium_channels.py` and `voltage_gates.py`), and the rest of the catalogue as read for this
note (literals in `sodium_catalog.py`, `potassium_catalog.py` and `cav_channels.py`, module tables
for Morris–Lecar's tanh and cosh forms in `morris_lecar_channels.py`). None of them can carry ORd's gating. What moves
are the leaks, two pumps and the routes whose parameters are already data. This departs from
EXCITABLE_TISSUE_DESIGN §3.3, which expected moved laws to cover IK1 and the delayed rectifiers
for the mouse; §9.2 asks the lead to rule on it.

**Names.** IDs are proposed (**S**) and name the mechanism and its form, never a protein; the
three already proposed in EXCITABLE_TISSUE_DESIGN §3.3 keep their names. With kinetic coefficients
as data (§4.5 (c)), one ID covers the endocardial, epicardial and M cells, the CaMKII-phosphorylated
forms (§3.7) and any re-fit of the same form.

**Gates per population.** The table counts ORd's gates as ORd's state list does, CaMKII's copies
included. Under §3.7 each modulated current becomes two populations of one law, so a population
carries INa's 4 (m, h_fast, h_slow, j), INaL's 2, Ito's 3 or ICaL's 7 (**S**), and the world's
gate rows are the largest of these (`gate_rows`), 7.

**The domain.** Every new law declares its own voltage domain. −120 to +60 mV covers ORd's cell:
its published peak is +40.0 mV and its rest −88.0 mV (Paci et al. 2015's table, via
EXCITABLE_TISSUE_DESIGN §7.3) [sec].

| Current or flux (ORd) | Mechanism and proposed ID | Moved or new | Gates and reads (ORd) | Driving force: the paper's → the engine's | Source of equations and parameters |
| --- | --- | --- | --- | --- | --- |
| INa, fast sodium | Fast sodium current with fast and slow inactivation and slow recovery: `fast_sodium_m3hj@1` | New | 6: m, h_fast, h_slow, j, and CaMKII's h_slow and j (its h_fast is h_fast). Reads none beyond E_Na | Linear, G(V − E_Na), G 75 mS/µF → the linear form (§4.5 (b)) | Text S1, the INa section [full] |
| INaL, late sodium | Late sodium current: `late_sodium_mh@1` | New | 3: m_L, h_L and CaMKII's h_L | Linear, G 0.0075 mS/µF → linear | Text S1 [full] |
| Ito, transient outward | `transient_outward_potassium@1`, an activation gate times two inactivation components | New. The catalogue's A-type laws (`kv3p4_mh@1`, `k_fast_mh@1`) hold BETSE's coefficients | 6: a, i_fast, i_slow, and CaMKII's three. The epicardial cell multiplies both inactivation time constants by δ_epi(V), a kinetic difference | Linear, G 0.02 mS/µF → linear | Text S1 [full] |
| ICaL, with ICaNa and ICaK | L-type current with voltage- and Ca²⁺-dependent inactivation, permeant to Ca²⁺, Na⁺ and K⁺: `l_type_calcium_cdi@1` | New | 9, shared by the three ions: d, f_fast, f_slow, fCa_fast, fCa_slow, jCa, n, and CaMKII's f_fast and fCa_fast. n, the fraction of channels in the Ca²⁺-inactivation mode, is a two-state reaction driven by subspace Ca²⁺: a relaxation gate whose target reads Ca²⁺ in the subspace. The current faces the subspace | GHK: P_Ca 1·10⁻⁴ cm/s, P_Na and P_K 0.00125 and 3.574·10⁻⁴ of it, CaMKII's form 1.1 P_Ca; activity coefficients γ_Ca 1.0 inside and 0.341 outside, γ_Na = γ_K = 0.75 on both sides → constant-field with relative permeabilities. The symmetric Na⁺ and K⁺ factors fold into the permeabilities exactly. The asymmetric Ca²⁺ factor puts the law's zero (RT/2F)·ln 0.341 = −14.4 mV (**S**, at 310 K) below E_Ca: admissible while the state stays out of that window, which the law declares as its domain; a symmetric factor is the declared fallback (§3.8) | Text S1 pp. 10, 15 (activity coefficients) [full] |
| IKr, rapid delayed rectifier | `rapid_delayed_rectifier_potassium@1` | New | 2: x_r,fast, x_r,slow; an instantaneous rectification R_Kr(V). Reads K⁺ outside, through √(K_o/5.4) | Linear, G 0.046 mS/µF → linear | Text S1 [full] |
| IKs, slow delayed rectifier | `slow_delayed_rectifier_potassium@1` | New | 2: x_s1, x_s2. Reads cytosolic Ca²⁺, through 1 + 0.6/(1 + (3.8·10⁻⁵/Ca_i)^1.4) | Linear with a mixed reversal, E_Ks = (RT/F) ln[(K_o + 0.01833 Na_o)/(K_i + 0.01833 Na_i)], but booked wholly to K⁺ (Text S1 pp. 6, 18). **Inadmissible as written** (§3.8). → linear, one conductance per ion (K⁺ and Na⁺), in the ratio that puts the zero at E_Ks at the source's concentrations (**S**); each ion runs down its own gradient | Text S1 [full] |
| IK1, inward rectifier | `inward_rectifier_potassium@1`, a time-dependent gate times an instantaneous rectification | New. `kir_ml_instantaneous@1` and `kir2p1_mh2@1` hold BETSE's coefficients | 1: x_K1; instantaneous R_K1. Reads K⁺ outside, through √K_o | Linear, G 0.1908 mS/µF → linear | Text S1 [full] |
| IKb, background K⁺ | A K⁺ current with an instantaneous voltage factor: `potassium_instantaneous_factor@1` | New | 0; x_Kb(V) | Linear, G 0.003 mS/µF → linear | Text S1 [full] |
| INab, background Na⁺ | A constant-field Na⁺ leak | **Moved:** `naleak_always_open@1`, already in @3 | 0 | GHK, P 3.75·10⁻¹⁰ cm/s, no activity coefficients → the same, exactly | Equations: the moved law's constant-field flux, ORd's form; parameter: Text S1 [full] |
| ICab, background Ca²⁺ | A constant-field Ca²⁺ leak | **Moved:** `caleak_always_open@1` (`laws/channels/calcium_catalog_extra.py`) | 0 | GHK, P 2.5·10⁻⁸ cm/s, γ 1.0 inside and 0.341 outside → as ICaL's: the same window, against bulk Ca²⁺, as the leak's domain; the symmetric factor as the fallback | Equations: the moved law's constant-field flux with the activity factors; parameters: Text S1 [full] |
| IpCa, sarcolemmal Ca²⁺ pump | A saturable ATP-driven Ca²⁺ pump | **Moved:** `ca_atp_mass_action_positive@1`, already in @3 | 0; reads cytosolic Ca²⁺ | One-way, 0.0005·Ca_i/(0.0005 + Ca_i) µA/µF → the law's saturation times (1 − e^{ΔG_cyc/RT}), a completion (§3.8) | Equations: the moved law's ([PLASMA_CALCIUM.md](PLASMA_CALCIUM.md)); parameters: Text S1 [full] |
| INaCa, Na⁺/Ca²⁺ exchange (80% facing the bulk, 20% the subspace) | A four-state exchange cycle at steady state, after Kang and Hilgemann: `sodium_calcium_exchange_cycle@1`, a fuel-free transporter | New. The catalogue's `ncx_3na_1ca_symmetric_barrier@1` is a synthetic law of another form | 0; reads Na⁺ and Ca²⁺ on both sides at its pool, with an allosteric Ca²⁺ activation (constant 150·10⁻⁶ mM) | The cycle includes the observed Na⁺ leak mode, but the concentration equations book 3·I_NaCa to Na⁺ and −2·I_NaCa to Ca²⁺, not the cycle's own fluxes (Text S1 pp. 13, 18). So the zero current need not lie at the 3:1 equilibrium: **to be screened** (§3.8). → the cycle's own Na⁺ and Ca²⁺ fluxes, booked as the cycle moves them, a declared change | Text S1 and Fig. S1A [full] |
| INaK, Na⁺/K⁺ pump | A lumped four-state pump cycle after Smith and Crampin: `sodium_potassium_pump_cycle@1`, on held fuel | New. The form of `nak_atp_mass_action_positive@1` (Hill saturations, with voltage only through the cycle's free energy) cannot carry ORd's | 0; reads Na⁺ and K⁺ on both sides; MgATP 9.8, MgADP 0.05, total phosphate 4.2 and H⁺ 10⁻⁷ mM, held | A cycle → the same cycle, screened (§3.8). Its rate constants imply a hydrolysis free energy, which must agree with the species registry's fuel potentials, or the transporter kind refuses it (INNER_MODEL_V4_DESIGN §7.4 (h)). Two reported errors in the printed cycle (a β₂ that should be β₃, and an H⁺ of 10⁻⁷ mM, which is pH 10) are carried as ORd prints them, and stated; the comment finds neither significant at baseline [sec: a PLOS reader comment, 7 March 2024] | Text S1, Fig. S6 [full] |
| Jrel, SR release (junctional SR to subspace) | Graded release whose flux relaxes to a target proportional to the L-type current: `graded_sr_calcium_release@1` | New | Two flux states (non-phosphorylated, and CaMKII's with β_τ × 1.25). Target α_rel·(−I_CaL)/(1 + (1.5/Ca_jsr)⁸), α_rel = 0.5 β_τ, β_τ 4.75 ms; time constant β_τ/(1 + 0.0123/Ca_jsr), floored at 0.001 ms. Reads the L-type current (its Ca²⁺ part, in Myokit's re-implementation [code]) and junctional SR Ca²⁺; the M cell's target is 1.7 times the endocardial | A flux down a gradient while Ca_jsr > Ca_ss: admissible, with that as its domain (**S**) | Text S1 p. 18. Its p. 4 text names the myoplasm as the destination; the equations put it in the subspace, which this note follows [full] |
| Jup, SR uptake, with its leak | A saturable ATP-driven Ca²⁺ pump between pools | **Moved:** `er_calcium_pump_positive@1`, as two populations (non-phosphorylated, and CaMKII's at 2.75 times the rate with its constant lowered by 0.00017 mM) | 0; reads cytosolic Ca²⁺, constant 0.00092 mM | One-way, 0.004375·Ca_i/(0.00092 + Ca_i) → the law's saturation times its thermodynamic factor (§3.4). The leak, 0.0039375·Ca_nsr/15, → a route between pools (§3.4) | Equations: the moved law's ([ER_CALCIUM.md](ER_CALCIUM.md)); parameters: Text S1 [full] |
| Jtr and Jdiff, between pools | Fick's law between pools at the cell's potential | **Moved:** `constant_field@1` at zero voltage, on a route between two pools (§3.2) | — | (Ca_nsr − Ca_jsr)/100 ms; subspace to bulk with time constants 0.2 ms (Ca²⁺) and 2.0 ms (Na⁺, K⁺), on free concentrations → the same, exactly, with P·A = V/τ on the free amounts the buffer read gives (**S**) | Equations: `constant_field@1` at zero voltage; parameters: Text S1 [full] |
| Buffers | Rapid buffering: the closure of §3.3 | New, B4's sibling | Bulk: CMDN 0.05 mM (K_m 0.00238) and TRPN 0.07 (0.0005). Subspace: BSR 0.047 (0.00087) and BSL 1.124 (0.0087). Junctional SR: CSQN 10.0 (0.8). The network SR, Na⁺ and K⁺ are unbuffered | ORd's factor β = 1/(1 + Σ[B]K_m/(K_m + Ca)²) multiplying dCa/dt is the closure's differential form (**S**) | Text S1 p. 18, after Hund, Decker and Rudy [full] |
| CaMKII | One trapped state; the bound fraction from subspace Ca²⁺; the active fraction φ = 1/(1 + 0.15/CaMK_active) mixes the phosphorylated forms of INa, INaL, Ito, ICaL, Jrel and Jup. Named by its mechanism, a Ca²⁺-triggered phosphorylation with trapping: `calcium_triggered_phosphorylation_trapping@1`, a source kind | New | 1: CaMK_trap, with d(trap)/dt = 0.05·bound·(bound + trap) − 0.00068·trap and bound = 0.05·(1 − trap)/(1 + 0.0015/Ca_ss) | No transport | Text S1 [full] |

**Conditions of the source** [full]: 310 K; Na_o 140, Ca_o 1.8 and K_o 5.4 mM; a cylinder of length
0.01 cm and radius 0.0011 cm, capacitive area A_cap = 2·A_geo = 1.534·10⁻⁴ cm², and a capacitance
printed as "1.0 µF", read as 1 µF/cm² since its currents are densities per µF (**S**);
the bulk, network SR, junctional SR and subspace take 0.68, 0.0552, 0.0048 and 0.02 of the cell's
volume (38·10⁻⁶ µL). Its stimulus is −80 µA/µF for 0.5 ms, and "for charge conservation sake,
stimulus has K⁺ identity as described by Hund et al." The cell types multiply conductances by
factors in Text S1 p. 19's table; the epicardial cell's δ_epi is its one kinetic difference.

**Corrections the reference applies** [full]: PLOS's correction of 14 September 2011 (the Na⁺
equation lists INaL twice, "IKur" in the K⁺ equation reads IKb, and G_NaCa's units are µC/µF).
The Results call CaMKII's effect on ICaL's fast inactivation "2.5 fold faster", while Text S1 p. 10
makes its time constant 2.5 times larger, that is slower; the reference follows the equations.

## 3. Calcium handling in the inner model (D167's move)

D167 moves calcium handling "with excitable tissue". The old families hold it as BETSE-parity laws
on their own state: `er_calcium@1`'s cytosol/ER pair (two-site buffers through ideal reactions, an
ER capacitor with K⁺ counterflow, `er_calcium_pump_positive@1` and `er_calcium_release@1`) and
`spatial_calcium@2`'s plasma routes (`plasma_calcium_pump_positive@1` and the synthetic
`ncx_3na_1ca_symmetric_barrier@1`) ([ER_CALCIUM.md](ER_CALCIUM.md),
[PLASMA_CALCIUM.md](PLASMA_CALCIUM.md)). Every candidate source model needs more than those laws
give: a dyadic subspace, two or three intracellular pools, rapid buffers, graded release, and the
source's exchanger.

### 3.1 The parts, by source model

| Part | ORd and ToR-ORd | TP06 | In the inner model (proposed) |
| --- | --- | --- | --- |
| Pools | Bulk, subspace, network SR, junctional SR: 0.68, 0.02, 0.0552 and 0.0048 of the cell's volume [full] | Cytoplasm, subspace, SR [full: AM]; the volumes as the authors' 2006 code corrects them [code: its `Main.cc`] | Pools at the cell's potential (§3.2) |
| Buffering | Rapid buffering: CMDN and TRPN in the bulk, BSR and BSL in the subspace, CSQN in the junctional SR [full] | Rapid buffering, one lumped buffer each in the cytoplasm, SR and subspace [full: AM] | A rapid Ca²⁺ buffer read, B4's sibling (§3.3) |
| Uptake and leak | One-way saturating uptake with a CaMKII form; a leak in proportion to network SR Ca²⁺ [full] | Uptake V_maxup/(1 + K_up²/Ca_i²); a Fickian leak V_leak(Ca_SR − Ca_i) [full: AM] | A pump between pools on held fuel; the leak as a route between pools (§3.4) |
| Release | A flux state relaxing to a target in proportion to −I_CaL, with a CaMKII copy [full] | V_rel·O·(Ca_SR − Ca_ss), with O from one state driven by subspace Ca²⁺ and the SR's load [full: AM] | A release law with its own state (§3.5) |
| Transfer and diffusion between pools | Network to junctional SR (100 ms); subspace to bulk for Ca²⁺ (0.2 ms), Na⁺ and K⁺ (2.0 ms) [full] | Subspace to cytoplasm, V_xfer(Ca_ss − Ca_i) [full: AM] | `constant_field@1` at zero voltage between pools (§3.2) |
| Na⁺/Ca²⁺ exchange | A cycle after Kang and Hilgemann, 80% facing the bulk and 20% the subspace [full] | A saturating formula with a factor α = 2.5 on one direction, facing the bulk [code: TP06's CellML, the model repository's e/80d; full: AM Table 1 and §2.1.1] | A fuel-free exchanger law (§3.6) |
| Sarcolemmal Ca²⁺ pump | One-way saturating [full] | One-way saturating, G_pCa 0.1238, K 0.0005 mM [full: AM] | `ca_atp_mass_action_positive@1`, moved (in @3 already) |
| CaMKII | One trapped state; six targets [full] | None | A source kind through the routing door (§3.7) |

### 3.2 Pools at the cell's potential: the subspace and the SR

The source models give the dyadic subspace and the SR no membrane potential of their own: every
pool of a cell shares the cell's voltage, and only the plasma membrane is a capacitor. ORd's 41
states and TP06's 19 (V, Ca_i, Ca_SR, Ca_ss, Na_i, K_i, twelve gates and R̄) each hold one membrane
voltage [full; code: TP06's 2006 code]. Three representations were weighed (**S**):

- **(a) Pools at the cell's potential. Recommended.**
  - A cell declares pools, each with its volume and its own species rows. The field solve gives
    every pool the cell's potential and counts its charge in the cell's row. So the plasma
    membrane sees the whole charge the cell holds, as FR-1's Gauss relation does for a
    compartment (CLOSED_COMPARTMENT_DESIGN §3.1).
  - A route between two pools of one cell sees zero voltage, so a charged species crosses it by
    Fick's law. That is the existing constant-field route at zero voltage (`constant_field@1`,
    B(0) = 1), so the transfer, diffusion and Fickian leaks need no new law.
  - Each plasma-membrane route declares the pool it faces: ORd's L-type current and its
    subspace share of Na⁺/Ca²⁺ exchange face the subspace, the rest face the bulk pool. The
    simplest form is two patches of the one membrane, whose insides are the subspace and the bulk
    pool; their capacitances add, since both pools sit at the cell's potential.
  - **Three hosts are new:** a pool, a patch whose inside is a pool, and a route between two pools
    of a cell (for transfer, diffusion, uptake, leak and release).
  - **What it represents (D175):** the SR membrane potential and the counter-ion currents that
    keep it small are left out, as the source models leave them out. The detailed
    representation is (b), which stays available to check the reduction later.
  - **Cost:** a change to the cell entity, the field solve's binding and the adapter's views,
    with crossrev identity for every world that declares no pool. It is the core owner's work,
    about 3–5 agent-days (**S**). It opens "subspace calcium", which §13.1 of the inner-model
    note closes in version 1: the lead's ruling.
- **(b) The SR as FR-1 compartments with charged doors.**
  - The SR becomes a capacitor node whose voltage is −q/C_b. Ca²⁺ release and uptake then
    charge it, so counter-ion routes (K⁺ or Cl⁻) on its bounding patch must carry the release
    current at a small SR voltage. Their G/C_b is then large, and FR-4's charged-patch test
    measured the explicit limit at dt × G/C_b of about 0.05 with today's booking
    (COMPARTMENT_PH_TRANSFER_DESIGN §7.2). So it needs the implicit patch (§7.3 there).
  - **It cannot carry any of the three models alone.** A compartment has exactly one bounding
    patch to its owner, so the subspace (bounded by no membrane, with the L-type current on one
    side and release on the other) is not one, and FR-1 has no route between two compartments
    (network to junctional SR).
- **(c) Lump the subspace into the bulk.** No new entity, but Ca²⁺-dependent inactivation and
  release then see bulk Ca²⁺. That changes the source model's dynamics, so the comparison would
  test a different model. Not recommended.

### 3.3 Rapid Ca²⁺ buffering

- **Recommended: a rapid-buffer stage read for Ca²⁺, B4's sibling.** At a buffered pool the Ca²⁺
  row holds total Ca²⁺ and each buffer row its total. At every stage the read gives free Ca²⁺ to
  every law, and the binding free energy is booked as the closure's declared term, as B4 books
  its own (COMPARTMENT_PH_TRANSFER_DESIGN §4.4). This is the exact fast limit, and the source
  models' rapid-buffering factor is its differential form (**S**), so the two agree to the
  integration error.
- **Generalised once:** one closure for "a declared species and its buffers" serves H⁺ and Ca²⁺
  (D144). Reads on disjoint rows compose under the kind interface, which refuses only two reads
  that share a row (§7.4 (k)). What must change is B4's own declaration, which admits one read in
  version 1; or a sibling kind adds the Ca²⁺ read.
- **Not recommended:** kinetic buffering through D152's reactions. It is stiff at the buffers'
  on-rates, and it is not the sources' form.
- **The species budget (S):** for ORd, Na⁺, K⁺, Ca²⁺, one anion row and one impermeant row, five
  buffer rows (CMDN, TRPN, BSR, BSL, CSQN) and the three held fuel rows (ATP, ADP, Pi) make 13
  against FR-9's cap of 16. ToR-ORd's Cl⁻ can be the anion row; TP06's three buffers make 11. A
  species row exists at every node, so each pool also costs a node of the dense field solve.

### 3.4 Uptake and leak

- **Uptake** is a pump from the bulk pool into the network SR (TP06: the SR), on held fuel
  (`maintained_held_rows@1`). For ORd it is the moved `er_calcium_pump_positive@1`: one Ca²⁺ per
  formal cycle, saturating in cytosolic Ca²⁺, with its thermodynamic factor
  ([ER_CALCIUM.md](ER_CALCIUM.md)), as two populations for CaMKII's mixing (§3.7). Its kernel
  moves unchanged; its host becomes a route between two pools. TP06's Hill uptake is a different
  form, a law of its own.
- **Its stoichiometry is a declared choice (S).** The thermodynamic factor (1 − e^{ΔG_cyc/RT}) has
  ΔG_cyc = Δ_rG_ATP + n (μ_SR − μ_cyt), so one Ca²⁺ per ATP keeps it nearest 1 and nearest the
  source's saturating rate, but books twice the ATP per Ca²⁺ of a two-calcium SERCA cycle (the
  biological cycle that ER_CALCIUM.md cites, Tran et al. 2009). Two per ATP is the biological
  stoichiometry, and it lowers uptake against the source when the SR is loaded. The component
  reference reports the factor at the source's own conditions either way.
- **The leak.** ORd's, 0.0039375·Ca_nsr/15 [full], runs from the network SR to the bulk in
  proportion to Ca_nsr alone. As a Fick route between pools it is P·A·(Ca_nsr − Ca_i), so it
  departs from ORd's by Ca_i/Ca_nsr relative: 5.3·10⁻⁵ at ORd's published diastolic state
  (§3.9's D5). TP06's leak is Fickian already.

### 3.5 Release

- **ORd's release is phenomenological.** Its flux is a state that relaxes to a target in
  proportion to the L-type current, scaled by the junctional SR's load (§2). It is not driven by
  Ca²⁺ at the release sites. ToR-ORd keeps it, driven by the subspace's L-type current only [code].
- **In the inner model:** a release law with its flux states (two, with CaMKII) as its own state
  fields, on a route from the junctional SR to the subspace.
  - **Its read crosses laws.** It needs the L-type populations' Ca²⁺ current at each stage. Those
    populations are @3's, not a kind's, so the kind interface's rule (no cross-kind reads) does not
    cover it. The seam: the core hands a kind the stage current of channel populations it names
    (the core owner's change).
  - **Its domain:** Ca_jsr above Ca_ss, so the flux runs down its gradient and its heat is
    non-negative (**S**).
  - **Its step:** its relaxation rate joins the stage rule. Text S1 floors its time constant at
    0.001 ms, which binds only as the junctional SR empties (**S**: from the time constant's form).
- **TP06's release is mechanistic:** a Fickian flux through an open fraction from one state, driven
  by subspace Ca²⁺ and the SR's load. It would be a gated route between pools, with no cross-law
  read.

### 3.6 Na⁺/Ca²⁺ exchange

- **A fuel-free exchanger:** per forward cycle 3 Na⁺ in and 1 Ca²⁺ out, net one charge in, with no
  ATP. For ORd, the cycle's own Na⁺ and Ca²⁺ fluxes are booked, its Na⁺-leak mode included (§2).
- **What the transporter kind must admit** (`kinds/transporter.py` today: one ATP per
  cycle, one moved role, one population per patch in version 1):
  - several roles per cycle, and no fuel;
  - two populations on one membrane facing two pools (80% bulk, 20% subspace).
  - Owner: the transporter kind's owner, or a sibling kind in this lane (the lead's call).
- **Its admissibility** (§3.8): with its own fluxes booked, each step's dissipation is
  J_Na·Δμ̃_Na + J_Ca·Δμ̃_Ca. That is non-negative if the cycle's rate constants obey detailed
  balance at the engine's potentials (**S**). The screen checks it on a grid of states, and a
  cycle that fails is refused, never repaired.

### 3.7 CaMKII (ORd and ToR-ORd)

- **A source kind with one state per cell,** CaMK_trap, reading subspace Ca²⁺ (§2's row).
- **Its mixing becomes availability:**
  - each modulated current becomes two populations of one law, non-phosphorylated and
    phosphorylated, each at the full conductance, with availabilities 1 − φ and φ;
  - their sum equals ORd's mixing, (1 − φ)·I_np + φ·I_p, exactly (**S**): where ORd's two forms
    share a gate (INa's m, ICaL's d), the copies have the same kinetics and start, so they stay
    equal;
  - the phosphorylated forms are parameter sets of the same law IDs (§4.5 (c)).
- **The routing door** (core-next 207393ba) carries φ and 1 − φ at every stage. Its sinks are kinds'
  own control fields today, so they must reach @3's channel availability, and the uptake's and the
  release's populations (the core owner's seam change).

### 3.8 Thermodynamic admissibility: a screen every source law passes first

Cells closes material, charge and energy for every route. Every `*_dissipated_energy_pJ` field is
checked non-negative and non-decreasing per element, on the host and on the device
(`surface_pump_v3.dissipation_fields`), and a channel's is kept per species and population
(`channel_dissipated_energy_pJ`, [species, channel_slot]). So each ion of each population must
dissipate, never gain, free energy at every step: a flux that runs against its own ion's
electrochemical gradient is refused, as the default junction-heat booking was refused mid-wave
(EXCITABLE_TISSUE_DESIGN §2.2). The check's tolerance is an absolute 1e-12 pJ between rows
(`surface_pump.checked_rows`), so even a tiny flux against its gradient, held for a few rows, is
refused. Published cardiac models are partly phenomenological, so each source formula is screened
before it becomes a law (**S**):

- **Admissible as written:**
  - a single-ion current with a linear driving force, G(V − E_s), whose dissipation is
    G(V − E_s)² ≥ 0;
  - a constant-field flux with no activity factor, or with the same factor on both sides;
  - a Fickian route between pools;
  - a cycle whose rate constants obey detailed balance at the engine's potentials, its fuel's
    included.
- **Admissible after completion:** a one-way saturating pump, written without its back reaction,
  is multiplied by (1 − e^{ΔG_cyc/RT}), the mass-action positive form of today's pumps. Its
  departure from the source is e^{ΔG_cyc/RT}, which the component reference reports at the
  source's conditions. This covers ORd's sarcolemmal pump and SR uptake.
- **Admissible while the state stays out of a window, declared as the law's domain:** a
  constant-field flux with asymmetric factors has its zero off the Nernst potential, and between
  the two its flux runs against its ion's gradient.
  - ORd's ICaL and ICab: the zero lies 14.4 mV below E_Ca. TP06's ICaL, with its −15 mV shift and
    0.25 internal factor: 15 + (RT/2F)·ln 4 = 33.5 mV above E_Ca (**S**, at 310 K).
  - The window moves with the concentrations. E_Ca falls as subspace Ca²⁺ rises during release,
    so the window can reach the plateau's voltages (**S**). Whether the source's own trajectory
    enters it is measured on the reference's trajectory.
  - If it does, the declared fallback is the same factor on both sides, reported in the
    comparison. ToR-ORd itself replaced ORd's fixed factors with activity coefficients computed
    from each side's ionic strength (Davies), which after the authors' 2021 fix lie near 0.35
    [code; the authors' annotation (sec)].
- **Inadmissible as written,** each changed by a declared, cited modification, reported in the
  comparison (§5.2) and never silently repaired:
  - **A current with a mixed reversal booked to one ion:** ORd's and TP06's IKs. Between E_K and
    E_Ks, K⁺ would move against its gradient. The window is (RT/F)·ln[(K_o + p·Na_o)/K_o] wide,
    10.4 mV for ORd (p = 0.01833) and 15.4 mV for TP06 (p = 0.03), at their K_o and Na_o. The
    factor K_i/(K_i + p·Na_i) that the formula leaves out moves it by less than 1% for K_i above
    100 mM and Na_i below 10 mM (**S**). The membrane crosses the window late in every
    repolarization. The change: one conductance per ion, each down its own gradient (§2's IKs
    row). The alternative, a constant-field IKs with ORd's 0.01833, has its zero at E_Ks exactly,
    but a constant-field I–V.
  - **A cycle booked at a stoichiometry other than its own:** ORd's exchanger, whose current comes
    from a cycle with a Na⁺-leak mode but whose ions are booked 3:1 (§2's INaCa row). The change:
    book the cycle's own fluxes; the current is unchanged.
  - **An exchanger formula whose zero is off its equilibrium:** TP06's INaCa, whose α = 2.5 puts
    its zero at E_NCX + (RT/F)·ln α = E_NCX + 24.5 mV, with E_NCX = 3E_Na − 2E_Ca (**S**, at 310 K).
    The membrane crosses that window on every beat. A change would alter the model itself.
- **A cycle's fuel must agree with the registry:** a pump cycle whose rate constants imply their
  own hydrolysis free energy (ORd's Na⁺/K⁺ pump) is checked against the registry's fuel potentials
  (§2's INaK row).

**A law that dissipates at every state can still be refused: the booking.** This finding is read
in the code (**S**). No run has shown it; the probe below tests it first.
- **How the heat is booked.** `imex_step` books a channel population's heat with the tableau's
  explicit weights, like every route except the junctions under `trapezoid_nonnegative@1`
  (`surface_pump_v3.imex_step`). ARS(2,2,2)'s weights are (δ, 1 − δ) with δ < 0, and the code's own
  comment on the junction booking says they "book a negative junction heat increment where a
  junction's power falls by more than 59% in a step".
- **When that happens to a channel (S).** A current that crosses its reversal within a step: its
  power falls to zero there. The 1e-12 pJ tolerance then refuses even a crossing a fraction of a
  millivolt wide.
  - The exchanger: E_NCX = 3E_Na − 2E_Ca is about −28.5 mV at ORd's diastolic Na_i 7.23 mM and
    Ca_i 8.54·10⁻⁵ mM [full], so the membrane crosses it on every upstroke and every
    repolarization.
  - K⁺ currents: ORd's published rest, −87.84 mV, lies 0.17 mV below the E_K of its published
    K_i, 143.79 mM (−87.67 mV with Text S1's R = 8314 J/(kmol·K) and F = 96485 C/mol; Text S1
    pp. 2 and 5 [full]; the arithmetic **S**). So every K⁺ population open at rest (IK1 above all)
    crosses its reversal at each stimulus and again late in each repolarization.
  - This holds for every source model and for the declared linear form alike. Track E's generic
    cell did not meet it: its after-hyperpolarization, −87.6 mV (EXCITABLE_TISSUE_DESIGN §1.2),
    stays above its E_K, −88.3 mV at the equations appendix's K⁺ concentrations (**S**), and its
    Na⁺ currents stay below E_Na.
- **The probe, an H1 prerequisite.** One channel population whose current crosses its reversal
  within a step under ARS(2,2,2), on @3 as it stands: for example a cell's K⁺ leak while an
  injected current step drives the voltage through E_K.
  - **Expected:** the dissipation check refuses the step.
  - **Why (S):** ARS(2,2,2) has γ = 1 − 1/√2 and δ = 1 − 1/(2γ) ≈ −0.707. Its booked increment is
    dt·[δ·q(0) + (1 − δ)·q(γ·dt)], with q a population's power. That is negative when q(γ·dt) is
    below −δ/(1 − δ) ≈ 0.41 of q(0): a fall of more than about 59% in a step.
  - **Recorded:** the step, both powers and the refusal. If the step is not refused, the seam's
    need is revisited before H1 builds it.
- **So H1 needs a channel-heat booking that cannot be negative:** the junctions'
  `trapezoid_nonnegative@1`, which averages the step's start and end powers (each ≥ 0 for a
  single-ion route), extended to channel populations, and a booking of the same kind for the new
  kinds' routes, through their `book` hook. The state is unchanged; only the ledger's quadrature
  is, and the energy ledger's 2e-3 tolerance still bounds it. It is a declared choice, as
  excitable runs declare the junctions' (EXCITABLE_TISSUE_DESIGN §4.4).
- **For the exchanger, the per-cycle heat** (−cycles × ΔG_cyc, as the transporter kind books it)
  is the quantity that must not be negative. Its two ions' terms have opposite signs by design.

### 3.9 Every departure from the source, in one list

Arm (A) of the D138 question (§9.1) approves a reference with these departures, so the list is
closed here. Any departure found while the laws are written is added to it and reported to the
lead and the user before the judged run, never introduced silently.

| | Departure | Law | Status | Why | Its size |
| --- | --- | --- | --- | --- | --- |
| D1 | IKs carried by one conductance per ion, K⁺ and Na⁺, with its zero at E_Ks at the source's concentrations | `slow_delayed_rectifier_potassium@1` | Definite | ORd books IKs to K⁺ with a mixed reversal (§3.8) | The same total current at the source's concentrations; a Na⁺ flux ORd does not book (**S**) |
| D2 | The exchanger's own Na⁺ and Ca²⁺ fluxes booked, not 3:1 of its current | `sodium_calcium_exchange_cycle@1` | Definite | A cycle with a Na⁺-leak mode booked 3:1 (§3.8) | The current is unchanged; the ion booking differs by the leak mode's share |
| D3 | The sarcolemmal Ca²⁺ pump completed by (1 − e^{ΔG_cyc/RT}) | `ca_atp_mass_action_positive@1` | Definite | A one-way rate | e^{ΔG_cyc/RT}, reported |
| D4 | SR uptake completed the same way, at one Ca²⁺ per cycle | `er_calcium_pump_positive@1` | Definite; two per ATP is the declared alternative (§3.4) | A one-way rate | e^{ΔG_cyc/RT}, reported |
| D5 | The SR leak Fickian, P·A·(Ca_nsr − Ca_i), not in proportion to Ca_nsr alone | `constant_field@1` between pools | Definite | A route between pools runs on its gradient | Ca_i/Ca_nsr relative: 5.3·10⁻⁵ at ORd's published diastolic state (Ca_i 8.54·10⁻⁵, Ca_nsr 1.61 mM [full]; **S**) |
| D6 | The engine's exact SI constants, against Text S1's R = 8314 J/(kmol·K) and F = 96485 C/mol (p. 2) [full] | All | Definite | One authority for constants | 5.6·10⁻⁵ in R and 3.4·10⁻⁶ in F, relative (**S**) |
| C1 | ICaL's and ICab's Ca²⁺ activity factor made symmetric (0.341 on both sides) | `l_type_calcium_cdi@1`, `caleak_always_open@1` | Conditional: only if the source's own trajectory enters the window (§3.8) | An asymmetric factor | Measured if triggered |
| C2 | The exchanger cycle refused if it fails detailed balance at the engine's potentials | `sodium_calcium_exchange_cycle@1` | Conditional on the screen | §3.6 | A further change would go to the user |
| C3 | ATP's standard potentials declared from ORd's pump cycle, if they disagree with the registry's | `sodium_potassium_pump_cycle@1` and the species registry | Conditional on the screen | One authority for each standard potential (INNER_MODEL_V4_DESIGN §10.2) | — |

**Not departures** (exact, or different only at the integration error): the rapid-buffer closure
against ORd's buffer factor; CaMKII as two populations; the Fickian transfer and diffusion; the
constant-field Na⁺ leak; K⁺ as the stimulus's carrier (ORd's own convention); the non-negative
heat booking (a ledger quadrature, not a state change); and the two reported INaK errors, kept as
printed.


## 4. Options for the user

### 4.1 The source of equations and parameters

Read on 16 November 2026 by two web-search subagents (Sources): ORd's paper, Text S1 and reader
comments, ToR-ORd's article XML with its appendix and the authors' repository at 11e463d, and
TP06's accepted manuscript as its author hosts it (tbb.bio.uu.nl, dated 6 March 2006) with the
authors' 2006 C++ code and TP06's CellML. TP06's [code] tags below mean that 2006 code or that
CellML; nothing here rests on the authors' 2004 code (Sources). Tags as in the header.

| | **ORd 2011, endocardial** | **ToR-ORd 2019** | **TP06 (2006)** |
| --- | --- | --- | --- |
| State variables | 41 (31 without CaMKII) [full] | 43 [code]; 45 in the dynamic-chloride version | 19 [code: the 2006 code's `Variables.h`; and Elshrif & Cherry 2014 (sec)] |
| Pools | Bulk, subspace, network SR, junctional SR | The same | Cytoplasm, subspace, SR |
| Markov forms | None, by design: "Exclusion of Markov models" [full] | **IKr is a Markov model** (Lu and Vandenberg's five states) [full; code] | The release: a four-state scheme reduced to one state [full: AM] |
| CaMKII | Yes, on six currents and fluxes | Yes | No |
| Formulas needing a change or a domain in Cells (§3.8) | IKs booked to K⁺ with a mixed reversal; the exchanger's 3:1 booking of a cycle with a Na⁺ leak (to be screened); ICaL's and ICab's asymmetric Ca²⁺ activity (a state-dependent window) | ORd's, with activity coefficients computed from each side's ionic strength (Davies equation) in ICaL and ICab, a narrower window | IKs as ORd's (p_KNa 0.03); INaCa's α = 2.5, whose zero lies 24.5 mV (**S**) off the 3:1 equilibrium; ICaL's −15 mV shift and 0.25 internal factor, which move its zero 33.5 mV (**S**) above E_Ca |
| Laws to write (§2's count) | 8 channel laws, 2 transporter cycles, the release, the buffer read and CaMKII; 4 laws moved, and the constant-field route on a new host | ORd's, with a Markov IKr, a Grandi-type INa, an instantaneous IK1, two Cl⁻ currents and Cl⁻ as a channel ion | About 11, simpler, without CaMKII |
| Single cell at 1 Hz, as reported | APD 273 ms against "∼275 ms" in human endocardial preparations; maximum dV/dt 254 V/s against 234 ± 28 measured [full] | Ca²⁺ transient 312 nM; 54 of 62 drugs' risk correct [full] | Epicardial: APD90 306 ms, maximum dV/dt 289 V/s, rest −85.8 mV [full: AM]; 304.3 ms and 368.4 V/s by Elshrif & Cherry 2014 [sec], not reconciled |
| In tissue | Slow at a common coupling: in Elshrif & Cherry's cable, the endocardial cell's maximum velocity is 38.2 cm/s (37.8 epicardial) and its tissue upstroke 83.9 V/s (81.6 epicardial), "unphysiologically slow" against 62.2–74.6 cm/s for five other human models under the same settings (Elshrif & Cherry 2014, Table 2) [full]. In ORd's own strand: 45 cm/s at 1 Hz and 70 cm/s from quiescence [full]. The two are reconciled below. Remedies: O'Hara's own suggestion of the 2004 ten Tusscher INa (PLOS reader comment, 5 October 2012) [sec]; Passini et al. 2016's refit of h∞ = j∞ (its two constants, 82.9 and 6.09 mV, to 78.5 and 6.22 mV), which keeps CaMKII [full] | A Grandi-type INa for "conduction velocity and excitability"; fibre velocity 65 cm/s [full] | Tissue upstroke 266.3 V/s [sec: Elshrif & Cherry 2014]; the cell of the N-version benchmark, epicardial [sec: openCARP's benchmark example] |
| Equations, openly | Paper and 44-page Text S1, CC BY; PLOS's 2011 correction; reader comments report two INaK errors [full] | Paper CC BY 4.0. Documented paper/code differences: P_Nab (1.9238·10⁻⁸ printed, 1.9239·10⁻⁹ in code), the SR transfer time (60 ms in code, unprinted), INa's printed equation without (V − E_Na), and the activity's logarithm base (fixed only in alternative files, 2021) [full; code] | Ten of its currents are "unchanged" from TNNP04 (2004), whose printed equations could not be read openly; TP06 itself only as the accepted manuscript. The authors' 2006 code corrects printed table values it calls typos (volumes, V_rel, k₄) [code: its `Main.cc`] |
| Published model files | The authors' Matlab and C++ (BSD-style notice); a CellML 1.0 encoding (terms unspecified) | The authors' Matlab and CellML (GPL 3.0); one encoding also in the repository under CC BY 3.0; three versions (2019, dynamic chloride 2020, the 2021 fix) | The authors' 2006 C++ code; CellML (terms unspecified); an epicardial file in Chaste's BSD 3-Clause repository, which states no model licence of its own |
| Effort for H1–H3 (**S**, §8) | About 33–48 agent-days | About 41–59 | About 28–41, plus the papers |

**Recommended: ORd's endocardial cell (O'Hara et al. 2011).**
- **It fits the engine's version 1:** no Markov form, so the inner-model note's §13.1 closure on
  Markov laws can stay closed. Only subspace calcium opens, which every candidate needs.
- **It is the best-documented source:** open equations and tables, a published correction, reader
  comments that pin two errors, the authors' code under a BSD-style notice, and published
  steady-state values for all 41 states ("Single endocardial cell, at 1 Hz steady state, in
  diastole") [full].
- **It is built on undiseased human data,** and reports its single cell against them (APD 273 ms
  against about 275 ms; 254 against 234 ± 28 V/s) [full].
- **Its departures are listed and bounded** (§3.9): six definite, each confined to one law and
  reported with its size, and three that apply only if a screen requires them.
- **Its cost:** CaMKII and four pools, so the most laws of the two Markov-free candidates.
- **Its weakness is conduction,** which matters for Track E's tissue milestone (H4), not for
  FR-11's single cell. The published remedies are a parameter set on the same INa form (Passini
  et al. 2016) or another INa form (TNNP04's, as O'Hara suggested; ToR-ORd's). H4 chooses, with
  its own evidence. The remedies come from other papers, so D184's approval does not cover them.

**The conduction figures, reconciled (for H4).** Read from the open copies of the two papers, and
Decker et al. 2009's open article page:
- **ORd's own: 45 cm/s at 1 Hz, and 70 cm/s from quiescence** [full: the Results' "Fast Na⁺
  current"; Text S1's "APD Rate Dependence in Homogeneous Multicellular Fiber"].
  - The tissue: a 100-cell homogeneous endocardial strand on "the conduction equations of Decker
    et al. (-200 µA/µF, 1 ms stimulus delivered to fiber end, zero flux boundary conditions)".
  - ORd's sodium conductance was set to give it: "We determined appropriate channel conductance at
    37°C based on conduction velocity, and maximum dVm/dt." So 45 cm/s is a calibration target,
    matched to dog experiments; 70 cm/s matches in vivo human measurements (ORd's refs 48 and 49).
  - Decker et al.'s own strand, of 96 cells, used a gap-junction conductance of 2.5 µS (Decker et
    al. 2009, Methods [full]). ORd's text does not restate it, and Decker's other strand settings
    are in a supplement not read.
- **Elshrif & Cherry's: 38.2 cm/s for the endocardial cell (37.8 epicardial), the largest value
  of the conduction-velocity restitution** [full: Methods and Table 2].
  - The tissue: a continuous monodomain cable, 1.5 cm long, with one diffusion coefficient for
    every model compared, 0.001171 cm²/ms.
  - The numerics: a spatial step of 0.015 cm; a time step of 0.02 ms, with ORd's Ca²⁺ equations
    split at 0.001 ms; Rush–Larsen gates; no-flux ends.
  - The protocol: paced for 30 s at a cycle length of 1000 ms from the published initial
    conditions, with the velocity measured between two adjacent cells mid-cable.
- **Why they differ: mainly the coupling (S).**
  - In the continuum limit of a chain of cells, D = g_j L²/C. For ORd's cell (L = 0.01 cm,
    C = 153.4 pF), Elshrif & Cherry's D corresponds to g_j ≈ 1.8 µS, and Decker's 2.5 µS to
    D ≈ 0.00163 cm²/ms.
  - Velocity scales as √D in a continuum, and 38.2 × √(0.00163/0.001171) = 45.1 cm/s, which is
    ORd's own value at 1 Hz.
  - So the two agree once the coupling is matched, if ORd's strand used Decker's 2.5 µS. The
    discretizations also differ (discrete cells against a 0.015 cm grid), so this is an estimate,
    not a computed reconciliation.
  - What Elshrif & Cherry show is relative: at a common coupling, ORd's cell conducts the slowest
    of six human models. Its sodium current needs more coupling to reach a given velocity.
- **H4's targets (recommended):**
  - **Judged, as verification:** ORd's own strand at its own coupling, 45 cm/s at 1 Hz and
    70 cm/s from quiescence, once Decker's supplement confirms the coupling and cell spacing.
    Cells' tissue is a discrete chain of cells joined by junctions, as that strand is, so the
    comparison is like for like. D184 approved the single-cell comparison only, so this strand
    comparison is put to the user with H4.
  - **Reported, not judged:** velocity against coupling over a range that includes Elshrif &
    Cherry's D (about 1.8 µS at ORd's cell size), and the human values: 70 cm/s in vivo (ORd's
    ref 49) and Kaese and Verheule's 80 cm/s (EXCITABLE_TISSUE_DESIGN §13).
  - **The junction step bound at these couplings (S):** at 2.5 µS, Σg_j/C is 32,600/s in a chain
    (a bound of 15 µs) and 97,800/s at a hexagon's interior (5.1 µs). At 1.8 µS it is 23,400/s
    (21 µs) and 70,200/s (7.1 µs). So §4.2's condition holds at the 5 µs step in chains, and only
    just in a sheet at 2.5 µS.

**Why not the others now.**
- **ToR-ORd** is the better-calibrated successor (Ca²⁺ transient, drug block, conduction), but it
  needs a Markov kind (its IKr), activity coefficients read from each pool's ionic strength, Cl⁻
  as a channel ion, and a choice among three versions whose paper and code differ in documented
  places. Its code is GPL 3.0, so it could be run, never copied. Its improvements can follow as
  laws and parameter sets on the same pools and kinds, once Markov forms are opened.
- **TP06** is the smallest and conducts well, and it is the N-version benchmark's cell. But an
  independent reference cannot be written from its papers as they stand: ten currents are printed
  only in TNNP04, which could not be read, and TP06's own tables carry typos that its code
  corrects. Two of its formulas (the exchanger's α and ICaL's shift) would need changes to the
  model. If the user prefers TP06, the user could supply the two papers, as the user was asked
  for D155's tables; we fetch nothing that needs the user's identity.

### 4.2 Cell types

- **Recommended: the endocardial cell first.** It is ORd's base model and the cell its human
  preparations measured, and FR-11's loop and the comparison need one cell.
- **Epicardial and M cells follow as parameter sets** (Text S1 p. 19's factors, and δ_epi on
  Ito's inactivation) when tissue needs a transmural gradient (H4). With kinetic coefficients as
  data (§4.5 (c)) they cost a parameter set each, not a law.

### 4.3 The sodium current's form

- **Recommended: Hodgkin–Huxley gates, as all three sources write it.** It fits the exponential
  stage gates and the inner-model note's version 1 (§13.1). ORd's Discussion says "interested users can modularly replace
  any current or flux with more detailed Markov formulations of mutation or drug effects as
  desired" [full].
- **A Markov INa later, as a general kind,** when a consumer needs mutations or state-dependent drug
  block. Candidates: Clancy and Rudy 2002, nine states for the wild type in its CellML curation
  [abs; code: the repository's e/513]; Moreno et al. 2011, for flecainide and lidocaine [abs]. The
  kind would hold a state-occupancy vector per population with its own stiff update, and opens
  the inner-model note's Markov closure.

### 4.4 Temperature

- **Recommended: 310 K, the temperature of all three sources** [full]. The engine's declared
  temperature enters the constant-field fluxes, the Nernst potentials and the pumps, and the
  gates carry none (`definitions/surface_pump_v3_spec.py`'s docstring), so 310 K reproduces the source.
- **Another temperature** (room-temperature clamp data, say) needs a Q10 law on the gates' rates,
  a general feature of its own. Not proposed now.

### 4.5 The engine's route (for the lead and the core owner)

These choices follow from any source model. They are the lead's and the core owner's, not the
user's, and are set out so the user sees what the law set costs.

**(a) Where the gated currents live.**
- **Extend @3's channel-law declaration. Recommended.** The declaration already reserves reads, a
  loop term, a stage term and provenance (the inner-model note's §7.1 and §7.4 (b)). The seams to
  add, each present only where a declared law uses it, so every existing world keeps its programs
  (its §2.3):
  - Ca²⁺ and Cl⁻ as permeant ions;
  - each law's own gate count, with unused gate rows held fixed and ignored by its opening;
  - each law's own voltage domain, checked on its own populations;
  - reads at the stage: concentrations at the pool the population faces, and outside;
  - an opening that may depend on voltage and reads (ORd's instantaneous R_Kr, R_K1 and x_Kb),
    with its opening-slope term in the stage rule, as §7.1 there foresees;
  - a declared driving force, constant-field (today's) or linear (b below);
  - kinetic coefficients as per-law layout data (c below);
  - a route that faces a declared pool (§3.2);
  - the routing door's sink extended to channel availability, for CaMKII's mixing (§3.7).

  It keeps one population concept, @3's exponential stage gates, its channel controls, ledgers
  and observations, and `channel_transferred`, which FR-11's loop reader already takes.
- **The alternative: the currents as a kind** (for example `cells.gated_currents@1`, name **S**).
  It needs no change to @3's channel path, follows D180's module pattern, and the routing door
  serves it as built. But it duplicates the population concept, its gates would integrate with
  the tableau unless the kind books an exponential update of its own, and the moved leaks would
  live in two places.

**(b) The driving force.** Most cardiac currents are written with a linear driving force,
G·(V − E) (§2). Two ways to carry them:
- **A declared linear form. Recommended.** Each permeant ion's flux is G_s·(V − E_s)/(z_s F), with
  E_s the Nernst potential at the stage's concentrations. A single-ion law's dissipation rate is
  G_s(V − E_s)² ≥ 0 at every state (**S**); its booked increment is non-negative only with the
  non-negative booking of §3.8. A mixed-ion current takes one conductance per ion, each down its
  own gradient (IKs, §2).
- **Constant-field only, with each permeability matched to the paper's conductance at one
  voltage.** No new form, but the I–V relation then differs from the paper's away from the
  matching voltage (strongly for K⁺ currents, whose constant-field relation rectifies). The
  component references could not compare against the paper's equations, and the whole-cell
  comparison would test a different model.

**(c) Kinetic coefficients.**
- **As declared, cited data. Recommended.** A law ID names a mechanism and its functional form.
  Its coefficients are layout fields present only where it is declared, bound per population, so
  a cell type or another source model is a parameter set in an organism definition
  (SYN3A_MINIMAL_CELL_TRACK §10: "Parameter sets: values bound to declared parameters, each
  pointing to evidence records"), not a new law. Equal structures share executables (P5).
- **As kernel literals,** as today's laws hold them. Simpler kernels, but every cell type whose
  kinetics differ, and every re-fit, is a new law ID (D147).

**(d) Pools:** §3.2's (a), recommended.

## 5. Verification

### 5.1 Component references: each law under voltage clamp (no approval needed)

Single cited laws need no approval (EXCITABLE_TISSUE_DESIGN §11). Each law and flux is checked on
its own before any whole cell runs.
- **The reference.** One fresh agent writes it from the source paper's equations and tables, and
  reads neither the engine, the driver nor the authors' code, as Track E's references were written
  (D170). It runs out of process and saves its outputs. It computes each current's density, or each flux, under the
  source's own clamp protocols, at a grid of held concentrations:
  - steady-state activation and inactivation, time constants and recovery from inactivation, and
    the I–V relation, for each channel law;
  - rates over voltage and concentrations, for the transporters and the exchanger;
  - free Ca²⁺ from totals, for the buffer read; and the release flux at prescribed inputs.
- **The engine side is a kernel harness.** The law's declared kinetics, opening and driving form,
  advanced by the engine's own gate update (`exponential_mean_rate_linear_target_gates@1`) at the
  engine's step, under the prescribed voltage. That is VOLTAGE_GATED_CHANNEL_SPEC's isolated gate
  input; no whole-cell clamp is needed or claimed. With the protocol's breakpoints on step
  boundaries, the exponential update is exact at a constant voltage, so the comparison is to
  rounding there (**S**), and converges with the step elsewhere.
- **Then the law inside the inner model.** A single cell carrying the law and a leak, under
  current clamp, against the reference's integration of the same pair. It checks charge, the
  ledgers, the domain and the run paths. It reproduces no published model, so it needs no
  approval.
- **The admissibility screen** (§3.8) on the declared domain grid: dissipation non-negative, the
  zero current against the thermodynamic equilibrium, and each completion's departure reported.
- **Controls, from D150's and MG0c's lessons:** a coefficient moved by a registered amount must be
  caught; each tolerance comes from the reference's own convergence or a stated physical scale,
  never from the engine's spread.
- **Engine models:** `resolved_pump_tissue@3`, with the new laws declared.

### 5.2 The whole-cell comparison (needs the user's approval: D138, D151)

D138 and D151 make reproducing a paper's model, or writing a reference solution for it, tooling that
needs the user's approval per paper. The proposal, for ORd's endocardial cell:

**What runs.**
- **The engine:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with §2's law set,
  §3's calcium handling, and `electrode_current_injection@1` carrying K⁺. One endocardial cell in a
  held bath at Na_o 140, Ca_o 1.8 and K_o 5.4 mM, at 310 K, paced at 1 Hz with ORd's stimulus. It
  starts from ORd's published steady state and is paced to its own periodic state (§7). CPU.
- **Who writes the references.** This note's author has read the engine, so it writes neither R1
  nor R2. Both go to fresh agents, when a slot frees.
- **R1, an independent whole-cell reference.** A fresh agent writes it from the paper and Text S1,
  with PLOS's correction, and reads neither the engine nor the authors' code (D184). It runs out
  of process with its own stiff integrator at tight tolerances, with its own convergence check. It
  has two arms:
  - **R1-published:** the equations as printed;
  - **R1-declared:** the same, with §3.9's departures, one switch each.
- **R2, the published model itself, unmodified, run out of process** (route B, as D184 rules it).
  - **One plain attempt at the authors' own code** (C++, under its BSD-style notice), compiled and
    run out of process. A subagent could not reach its Box share without JavaScript on
    16 November.
  - **Any wall ends the attempt:** an account, JavaScript or a guard. The lane then stops trying
    and uses Myokit 1.40 (BSD 3-Clause), in its own environment, on the Physiome Model Repository's
    CellML 1.0 encoding of ORd. Its terms are unspecified, so it is used by reference only and
    never committed. No workaround.
  - Myokit's own curated encoding (`myokit/models`, `ohara-2011.mmt`, version 20240904) states no
    licence either, and its README asks users to cite the original papers [code].
  - Every encoding read starts from rounded values (V −87 mV, K_i 145 mM [code]), so R2 starts
    from Text S1's published steady state.
  - Only saved outputs enter the evidence.

**What is compared, over one beat of the periodic state at 1 Hz:**
1. V(t), with APD30, APD50 and APD90, the peak, the resting potential and the largest dV/dt;
2. free Ca²⁺ in the bulk (diastolic, peak, time to peak, decay) and in the subspace, and the
   network and junctional SR's Ca²⁺;
3. every current and flux over the beat;
4. bulk Na⁺ and K⁺ at the periodic state;
5. R2 against the paper's printed values: APD 273 ms and the largest dV/dt 254 V/s at 1 Hz [full].

**How it is judged.** Registered before its run, with D150's and MG0c's lessons: a scope line,
tolerances from the references' own convergence or a stated physical scale (never from the
engine's spread), a planted coefficient change that must be caught, and CPU named as the backend.
- **The engine against R1-declared: judged.** The same equations, so every difference is numerical.
- **R1-published against R2: judged, as the references' own check.** Two implementations of the
  printed equations must agree. That validates R1, and R2 against the paper.
- **The engine against R2: reported, not judged.** The difference is attributed to each declared
  change by R1's two arms, switching one change at a time. This is the scientific statement: how
  the Cells human cell differs from the published model, and why.
- **Scope:** one endocardial cell, held bath, 1 Hz, CPU. Not tissue, not other rates, not drugs.

### 5.3 External tools, model files and their licences (read on 16 November 2026)

Each licence below was read from its licence file or page by a web-search subagent on 16 November
2026 [full]. None has a non-commercial clause. "Unspecified" means the file states no terms.

| Item | Licence as read | Where read | Note |
| --- | --- | --- | --- |
| **Myokit** 1.40.0 (2 November 2026) | BSD 3-Clause | `LICENSE.txt` on GitHub `myokit/myokit`; PyPI's metadata | Its documentation: "Methods to import and export CellML 1.0, 1.1, and 2.0 are provided"; some CellML encodings need their stimulus converted by hand |
| OpenCOR, desktop (v0.8.3, 29 July 2025) | GPL 3.0 or later (copyleft) | opencor.ws/licensing.html | Runs CellML 1.0 and 1.1; its documentation says CellML 2.0 "is not yet supported" |
| OpenCOR, web app, and libOpenCOR | Apache 2.0 | opencor.ws/libopencor/licensing.html | Parses CellML 1.x and 2.0 (a source comment); that it simulates 1.x models was not verified |
| Chaste (`Chaste/Chaste`) | BSD 3-Clause | `LICENSE` on its `develop` branch | Ships one cardiac file, `TenTusscher2006Epi.cellml`; no ORd or ToR-ORd file |
| `Chaste/cellml` (a separate repository) | No licence file or text | Its README | Holds ORd endo and epi, TP06 endo, epi and M, and ToR-ORd's dynamic-chloride version; taken from models.cellml.org in about 2011, with later additions |
| ORd's CellML in the Physiome Model Repository (e/639, which supersedes e/71) | "Unspecified" | The entry's licence page | A CellML 1.0 encoding by S. Niederer from the Rudy lab's Matlab code. The site carries a general sentence that public content is under CC BY 3.0; whether it covers an "unspecified" entry was not concluded |
| TP06's CellML in the repository (e/80d: endo, epi, M) | "Unspecified" | Each file's licence page | As above |
| ToR-ORd's CellML in the repository (e/5f1: endo, epi, mid) | CC BY 3.0 | The entry's licence page | The same encoding (header and model ID) is in the authors' repository under GPL 3.0, so one encoding carries two licences |
| **ORd's own code** (Matlab and C++, Rudy lab) | A BSD-3-style notice in `main.m` and `main.cpp` ("Copyright (c) 2011-2015 by Thomas O'Hara, Yoram Rudy, Washington University in St. Louis. All rights reserved. Redistribution and use…", three conditions); the download page states no terms | rudylab.wustl.edu/code-downloads/ | `model.m` has no header |
| ToR-ORd's own code (`jtmff/torord`) | GPL 3.0 or later (copyleft); ORd's BSD-style notice appended on 22 May 2025 | `LICENSE.txt`, `cellml/LICENSE.txt`, `matlab/LICENSE.txt` | Matlab and CellML 1.0. Versions by commit date: first release 22 December 2019; dynamic chloride 24 May 2020; "updatedPhiCaL" variants 29 June 2021 |
| ORd's paper (PLoS Comput Biol 2011) and Text S1 | Creative Commons Attribution, version not stated on the article | The article page; Europe PMC | Text S1 (44 pages) states no licence; we read it as covered by the article's |
| ToR-ORd's paper (eLife 2019) | CC BY 4.0 | eLife's API record (version 4, 13 May 2020) | — |
| TP06 (2006) and TNNP04 (2004) papers | Not verified; the publisher is the American Physiological Society | Crossref | The publisher's site refused automated access (HTTP 403), as on 14 November; no PMC copy |

**What follows (S).**
- **Running a model file out of process and saving its outputs** distributes nothing, so a copyleft
  tool (desktop OpenCOR) or a GPL model file (ToR-ORd's) may be run that way under AGENTS.md's
  rule. Nothing from them enters the repository but our own saved outputs and our own code.
- **The cleanest pairing is Myokit (BSD 3-Clause) on a model file with permissive terms.** For
  ORd, the authors' own code carries a BSD-style notice, and Myokit imports the repository's
  CellML 1.0 encoding of it, whose terms are unspecified. For ToR-ORd, the CC BY 3.0 entry in the
  repository is the permissive copy of a GPL encoding. TP06's encodings are unspecified; the copy
  in Chaste's BSD 3-Clause repository states no model licence of its own.
- **A file with unspecified terms is used by reference only:** downloaded under
  `/mnt/workspaces/Cells`, never committed, with only our own saved outputs kept as evidence (the
  rule SYN3A_MINIMAL_CELL_TRACK §10 gives for values with no stated terms).
- **Myokit, like BETSE, runs in its own environment** (for example `venv-myokit` beside
  `venv-betse`), and only one directory under `validation/` runs it. No such environment exists
  today (checked: `/mnt/workspaces/Cells/venv-*` holds `venv-betse`, `venv-cpu`, `venv-gpu` and
  `venv-tyssue`).

## 6. Prerequisites, by milestone

**A single paced cell has no junction.** So `junction_ungated@1` and §4.2's junction step condition
(or the junction-implicit solver) gate only the tissue milestone (H4, §8), not the paced cell or
FR-11's loop.

| Prerequisite | Gates | Status |
| --- | --- | --- |
| D172's landing: one modular inner model | Everything | Landing candidate 3c10b833 |
| The channel-law seams (§1, §4.5): Ca²⁺ and Cl⁻ as permeant ions; per-law gate counts, domains, reads, openings and driving form; kinetic coefficients as data; routes that face a pool | H1 | New; the core owner's |
| The booking probe (§3.8): one channel population crossing its reversal within a step under ARS(2,2,2), expected to be refused | H1, before the booking seam | A short probe on @3 as it stands |
| A channel-heat booking that cannot book a negative increment (§3.8) | H1, for any human cell: ORd's rest lies below E_K, and the exchanger reverses every beat | New; the core owner's, if the probe confirms the need |
| Calcium handling (§3): pools at the cell's potential (opening subspace calcium, INNER_MODEL_V4_DESIGN §13.1); the rapid Ca²⁺ buffer read (B4's closure generalised, or a sibling kind); pumps between pools and a fuel-free exchanger; the release law, with its read of the L-type current; CaMKII through the routing door into channel availability | H2 | D167's move, with new laws; the lead's rulings on the openings |
| The source paper's equations and tables | H1's and H2's component references | ORd: open (the paper and its 44-page Text S1, CC BY), read on 16 November, with PLOS's 2011 correction. ToR-ORd: open (CC BY 4.0). TP06 and TNNP04: not openly readable; the user could supply them (§4.1) |
| D155's paper's Supplementary Tables 1–2 | Not this lane. They map the paper's transcript changes to availabilities for Track E's perturbation (M4's mouse comparison) | Requested under D155 |
| The user's D138 and D151 approval | H3's whole-cell comparison only. Component references of single cited laws need none | Asked in §9.1 |
| Each new kind's run-view declarations (core-next 74a75241) | FR-11's loop | The interface is built on core-next |
| `junction_ungated@1` | H4 only: a cell whose peak-to-rest range exceeds 120 mV is refused at a block site by the gated junction's domain (EXCITABLE_TISSUE_DESIGN §1.2). ORd's is 128 mV (Paci et al. 2015's table, via §7.3 there) [sec] | Queued as the first law after R (INNER_MODEL_V4_DESIGN §13.2) |
| §4.2's step condition, or the junction-implicit solver | H4 only | As EXCITABLE_TISSUE_DESIGN §4.2 states it |
| Markov-form laws opened (INNER_MODEL_V4_DESIGN §13.1) | Only ToR-ORd's IKr, if chosen, and a later Markov INa (§4.3) | Closed in version 1 |

## 7. FR-11's human loop: a paced cell at 1 Hz

D183 makes FR-11's human loop a paced human ventricular cell on this law set, with no generic
stand-in (LOOPING_REPLAY_DESIGN §5 on run-view-d154, amended at fd008813). D184 keeps it: that
was the lead's reading of the user's answer, kept under the user's delegation. The viewer has no
human loop until the cell is ready (H3, §8); a labelled interim generic cell remains a one-line
amendment. The planarian loop stays first.

- **Engine models:** `resolved_pump_composite@1` over `resolved_pump_tissue@3` with the chosen
  law set and calcium handling, and `electrode_current_injection@1` as the pacing train. The cell
  sits in a held bath at the source model's concentrations, at the source's temperature (§4.4).
- **The drive:** a 1 Hz train of the source model's stimulus (ORd's: −80 µA/µF for 0.5 ms [full]),
  converted from current density to current at the cell's capacitance (153.4 pF at ORd's
  A_cap and 1 µF/cm², **S**). It is periodic, as FR-11's loops require.
- **The carrier is K⁺ alone.** The electrode declares `carriers: {"K": 1.0}`.
  - ORd: "For charge conservation sake, stimulus has K⁺ identity as described by Hund et al."
    [full]. TP06 books its stimulus to K⁺ too [code: TP06's CellML and the 2006 code]. Hund et
    al. (2001): "When ions carried by the stimulus current are taken into account, the
    algebraic and differential methods yield identical results and neither shows drift in
    computed parameters" [abs].
  - The operator's default carriers are 3 M KCl (K⁺ 0.4912, Cl⁻ 0.5088,
    `current_injection.DEFAULT_CARRIERS`). ORd and TP06 have no Cl⁻ route, so injected Cl⁻ would
    accumulate beat by beat, and the cell would have no periodic state to close a loop on.
- **The closure:** the writer measures `closes.within` on every level, amount and rate record
  (FR-11 §2). The fast records (voltage, gates, currents) repeat within a few beats. The slow
  inventories set `within`: intracellular Na⁺ and K⁺, and the SR's Ca²⁺ load. So the number of
  beats to a periodic state is the cost driver, and the tolerance the caller declares decides it.
- **The starting state:** ORd publishes all 41 states at its 1 Hz steady state ("Single
  endocardial cell, at 1 Hz steady state, in diastole"), and says "∼1000 beats are needed,
  depending on the CL" to reach it [full]. The Cells cell starts from those values: gates to
  gates, free concentrations to amounts (the buffer read's totals from the free values), and the
  release and CaMKII states to their kinds' fields. Then k beats take it to its own periodic state,
  which differs from the source's by the declared changes (§3.8); k is measured in a development
  run.
- **Cost (S, from EXCITABLE_TISSUE_DESIGN §9's measured costs):**
  - **The step is unmeasured for this cell.** Track E's evidence brackets it: 5 µs is accepted in
    chains, and 50 µs in a single cell from a kick (EXCITABLE_TISSUE_DESIGN §2.2). A single cell
    has no junction bound, so its step is set by the upstroke, the stage rule and the energy
    ledger.
  - At 5 µs a 1 s beat is 200,000 steps. At the single cell's measured 0.13–0.21 ms per step with
    @3's five laws, that is 26–42 s per beat. The human cell's step does more work (41 states and
    about twenty routes against @3's few), so 1–3 minutes per beat on one core is a working
    estimate at 5 µs, and about a tenth of that at 50 µs.
  - So 100 beats take about 2–5 hours at 5 µs, or 10–30 minutes at 50 µs; 1,000 beats about 1–2
    days, or 2–5 hours, on one core.
  - **Two general features would cut it, neither needed first:**
    - **a declared step plan,** fine steps for some milliseconds after each stimulus and coarse
      elsewhere. ORd's own explicit scheme does this: 0.005 ms for 25 ms after the stimulus, and at
      most 1.0 ms elsewhere [full]. Whether @3's energy ledger and stage rule admit coarse steps on
      the plateau is to be measured;
    - **a periodic-orbit solve,** shooting on the one-beat map, a mode beside D135's mode E.
    - Each would be its own design.
- **The package:** one beat observed every 1 ms is 1,000 rows, within FR-11's 1 MB with a
  recording subset (**S**). Its label says what it is: a human ventricular cell on cited laws,
  with the laws' qualification status, as an illustration (FR-11 §1).
- **What the viewer needs from each new kind:** its run-view declarations (KindView, core-next
  74a75241), so every transfer and cycle total carries its kind and sign, as the loop reader
  requires.

## 8. Milestones, effort and cost

Estimates are ours (**S**), in agent-days, for the recommended route (§4) with ORd's endocardial
cell.
They follow the inner-model note's costs for comparable seams (§7.4 (h): the per-structure schema
about 1, the stage-read slot 1–1.5, the transporter kind 2.5–3.5, the passive law 2–3).

| Milestone | Engine models | Content | Effort |
| --- | --- | --- | --- |
| H0 (this note) | None | The options and the D138 question | Done |
| H1: the channel-law seams and the membrane laws | `resolved_pump_tissue@3` with the new laws declared | The booking probe first, then the core owner's seams (§4.5 (a)–(c)) and the non-negative channel-heat booking (§3.8); the eight channel laws of §2, each tested at prescribed voltage and concentrations (the L-type law's Ca²⁺-dependent inactivation at a prescribed subspace Ca²⁺, then in the model with H2); the moved leaks; each with its component reference (§5.1), admissibility screen and planted control; crossrev identity for every existing world | Seams about 6.5–8.5, the booking about 1 more; laws about 4–6; references about 3–4 (a fresh agent, in parallel) |
| H2: calcium handling, D167's move | @3 with pools, the Ca²⁺ buffer read, the transporter kind's exchanger and pumps, the release law and CaMKII | §3: pools at the cell's potential (the core owner's); the buffer read; uptake, leak, exchange, release; the L-type current with Ca²⁺-dependent inactivation; their component references | About 14–20, of which the core owner's pools 3–5 |
| H3: the paced human cell | `resolved_pump_composite@1` over @3, with `electrode_current_injection@1` | The human ventricular cell's definition as cited parameter sets in `validation/` (no species-specific code in `src/cells`, D144); the periodic state at 1 Hz; FR-11's loop (§7); the whole-cell comparison if the user approves it (§5.2) | About 5–9, and CPU minutes to days for pacing, depending on the step (§7) |
| H4: human tissue (Track E's human arm) | As H3, with `junction_ungated@1` and the junction-implicit solver or §4.2's condition | Conduction on chains and sheets of human cells; the N-version benchmark only with its own approval (EXCITABLE_TISSUE_DESIGN §6's R-benchmark) | A milestone of its own, after Track E's M2 and M3 |

- **H1 to H3 in all: about 33–48 agent-days** for ORd (**S**); ToR-ORd about 41–59, and TP06
  about 28–41 once its papers are in hand (§4.1).
- **The critical path is the laws owner's** (H1's laws, then H2's, then H3), with the core owner's
  seams and pools ahead of each stage. Laws and references run in parallel on disjoint files.
  With three owners (the core owner, a laws owner and a references agent) it is about 20–30
  working days elapsed (**S**), less with two laws owners.
- **CPU:** the component references and the kernel harness take minutes. Pacing to a periodic
  state takes minutes to days on one core, depending on the step (§7). The external tool's runs,
  if approved, take minutes (**S**).
- **What is refused or not authorised by this note:** any engine code before the user chooses;
  a law named after a protein; a feature for one experiment (D144); a whole-cell comparison, a
  whole-cell reference or a run of a published model file without the user's approval (D138,
  D151); importing or copying any external code.

## 9. Questions

### 9.1 For the user: decided by D184

The user delegated these decisions to the lead with the advisor, and gave the go ("on the other
decisions get adviser with you then its go from me"). D184 records them on main at 98c49993. Each
question is kept as it was put, with its decision.

1. **The source model.** O'Hara–Rudy 2011's endocardial cell (recommended), ToR-ORd 2019, or ten
   Tusscher–Panfilov 2006 (§4.1)? If TP06: can you supply its paper and TNNP04's (2004), since
   neither is openly readable and we fetch nothing that needs your identity?
   - **Decided: O'Hara–Rudy 2011's endocardial cell.**
2. **Cell types.** The endocardial cell first, with epicardial and M cells later as parameter sets
   when tissue needs them (recommended, §4.2)?
   - **Decided: as recommended.**
3. **The sodium current's form.** Hodgkin–Huxley gates, as all three sources write it
   (recommended), with a Markov form later as a general kind (§4.3)?
   - **Decided: as recommended.**
4. **Temperature.** 310 K, the sources' own (recommended, §4.4)?
   - **Decided: 310 K.**
5. **The D138 question, for O'Hara–Rudy 2011's endocardial cell (§5.2).** Do you approve:
   - **(A)** an independent whole-cell reference of the model, written from the paper and Text S1
     by an agent who never reads the engine, run out of process, in two arms: as published, and
     with §3.9's listed departures (any later addition reported to you before the judged run)?
   - **(B)** running the published model itself, unmodified and out of process, keeping only saved
     outputs: in Myokit (BSD 3-Clause, in its own environment) from the model repository's CellML
     encoding (used by reference, never committed), or the authors' own C++ code, compiled and run
     as published?
   - **(C)** comparing the Cells cell over one beat at 1 Hz as §5.2 lists: judged against the
     declared arm at tolerances registered before the run; the two references judged against
     each other; and the Cells cell against the published model reported, not judged, with each
     difference attributed to a declared change?

   Answer yes to all three; yes to A and C without B (the comparison then rests on R1 alone,
   checked against the paper's printed values); or no (the lane stops at the component references
   of §5.1, which need no approval).
   - **Decided: (A), (B) and (C) approved, for O'Hara–Rudy 2011 only.** H4's conduction remedies
     come from other papers and are not covered.
   - **(A)'s author reads neither the engine nor the authors' code.** This note's author has read
     the engine, so R1 and R2 go to fresh agents when a slot frees (§5.2).
   - **(B) is one plain attempt at the authors' own code.** Any wall (an account, JavaScript, a
     guard) ends it, and the lane uses Myokit with the model repository's CellML encoding, by
     reference. No workaround.
**Also decided by D184:**
- **D167's expectation for the human set** (§9.2, question 12). The human set's channel laws are
  new, the catalogue's laws stay as D167's parity references, and the mouse's expectation is
  unchanged.
- **FR-11's human loop,** as D183 records it: no generic stand-in. The viewer has no human loop
  until the human cell is ready, about 20–30 working days after the landing by §8's estimate. A
  labelled interim generic cell remains a one-line amendment.

### 9.2 For the lead, with the core owner

Not covered by D184's delegation: these are ruled after the landing. Opening subspace calcium,
which the inner-model note closes in version 1, goes to the user if it changes an approved
closure. Question 12 is decided (D184; §9.1).

6. **Open subspace calcium,** closed in version 1 (INNER_MODEL_V4_DESIGN §13.1): pools at the
   cell's potential (§3.2 (a), recommended), for the core owner to design?
7. **The channel-law route** (§4.5): extend @3's channel-law declaration (recommended), with a
   declared linear driving force and kinetic coefficients as data?
8. **The Ca²⁺ buffer read** beside FR-4's proton read (§3.3): B4's closure generalised to a declared
   species (its declaration admits one read in version 1), or a sibling kind?
9. **The transporter kind:** several roles per cycle, no fuel, and two populations on one membrane
   facing two pools (§3.6). Its owner's, or a sibling kind in this lane?
10. **The routing door's sinks** into @3's channel availability (CaMKII, §3.7), and a seam for a
    kind to read a declared channel population's stage current (ORd's release, §3.5)?
11. **Where the human cell's definition lives:** a cited parameter set in `validation/` as an
    organism definition (SYN3A_MINIMAL_CELL_TRACK §10's structure), with FR-11's builder in
    `validation/replay/`?
12. **D167's move for the channel laws.** No catalogue channel law can carry ORd's gating (§2), so
    the human set's channel laws are new and the catalogue's stay as the parity references
    D167 freezes. Track E's §3.3 expected moved laws for the mouse's IK1 and delayed rectifiers;
    a human set built on new laws changes that expectation for the human, not the mouse. Accept?
13. **The non-negative channel-heat booking** (§3.8): the junctions' `trapezoid_nonnegative@1`
    extended to channel populations, and a matching booking for the new kinds' routes, as an H1
    seam for the core owner, after the probe confirms the need?

## Sources

**How they were checked.** Three web-search subagents read the sources below on 16 November 2026:
one the licences (§5.3), one ORd and ToR-ORd, one TP06 and the Markov sodium models. They used
paper titles, authors and scientific terms only, and fetched nothing behind a login. Two earlier
checks, of the cardiac conduction and action-potential citations, are recorded in
EXCITABLE_TISSUE_DESIGN §7.3 and §13 (14 November). Access as tagged in the text: ORd's paper and
Text S1 [full]; ToR-ORd's article XML with Appendix 1 and its peer review [full], and its code at
11e463d [code]; TP06 as the authors' accepted manuscript (6 March 2006, hosted by the author)
[full: AM], with the authors' 2006 C++ code and TP06's CellML [code]; the 2004 paper (TNNP04) not
read. For §4.1's conduction figures, the ORd and Elshrif & Cherry copies those subagents saved
were read again, and Decker et al. 2009's open article page once (PMC2670702).

**The authors' 2004 code: fetched, then discarded unused.** The TP06 subagent fetched the authors'
2004 (TNNP04) C++ code after the worktree guard had refused the command. It did so by splitting
the command's text. The authors' page offers the code publicly, with no licence stated. Under D184
the code and its index page were deleted on 16 November, unused. No statement in this note rests
on them. Three facts in the subagent's report rested on them alone, and none had entered the
note: TNNP04's state count in that code; that code's L-type current formula; and that code's half
of a statement about how K_o enters IK1, whose 2006 half stands. A copy of the paywalled 2004 paper
was separately blocked by the permission classifier and never obtained.

**Models and their corrections.**
- O'Hara T., Virág L., Varró A., Rudy Y. (2011). Simulation of the undiseased human cardiac
  ventricular action potential: model formulation and experimental validation. PLoS Comput Biol
  7:e1002061, with Text S1 and PLOS's correction of 14 September 2011; reader comments of
  5 October 2012 (O'Hara) and 7 March 2024.
- Tomek J. et al. (2019). Development, calibration, and validation of a novel human ventricular
  myocyte model in health, disease, and drug block. eLife 8:e48890. Code: github.com/jtmff/torord
  (GPL 3.0). The dynamic-chloride version: bioRxiv 10.1101/2020.06.01.127043 [abs].
- ten Tusscher K. H. W. J., Panfilov A. V. (2006). Alternans and spiral breakup in a human
  ventricular tissue model. Am J Physiol Heart Circ Physiol 291:H1088–H1100.
- ten Tusscher K. H. W. J., Noble D., Noble P. J., Panfilov A. V. (2004). Am J Physiol Heart Circ
  Physiol 286:H1573–H1589.

**On their use and successors.**
- Elshrif M. M., Cherry E. M. (2014). PLoS One 9:e84401.
- Passini E. et al. (2016). J Mol Cell Cardiol 96:72–81.
- Decker K. F., Heijman J., Silva J. R., Hund T. J., Rudy Y. (2009). Properties and ionic
  mechanisms of action potential adaptation, restitution, and accommodation in canine epicardium.
  Am J Physiol Heart Circ Physiol 296:H1017–H1026 (PMC2670702; its Methods read, its supplement
  not), the strand equations ORd used.
- Paci M. et al. (2015). Br J Pharmacol 172:5147 (ORd's peak and rest, via EXCITABLE_TISSUE_DESIGN
  §7.3).
- Hund T. J., Kucera J. P., Otani N. F., Rudy Y. (2001). Ionic charge conservation and long-term
  steady state in the Luo–Rudy dynamic cell model. Biophys J 81:3324–3331 [abs].
- Niederer S. A. et al. (2011). Phil Trans R Soc A 369:4331–4351; its cell, TP06's epicardial
  variant, as openCARP's benchmark example states it [sec].

**Markov sodium models.**
- Clancy C. E., Rudy Y. (2002). Circulation 105:1208–1213 [abs]; its CellML curation, the model
  repository's e/513 [code].
- Moreno J. D. et al. (2011). Sci Transl Med 3:98ra83 [abs].

**Cited through the sources above, not read here:** Kang and Hilgemann 2004 (ORd's exchanger),
Smith and Crampin 2004 (ORd's Na⁺/K⁺ pump), Hund, Decker and Rudy (ORd's buffers), Lu et al. 2001
(ToR-ORd's IKr), Grandi et al. 2010 (ToR-ORd's INa and Cl⁻ currents), Carro et al. 2011 (ToR-ORd's
IK1), Shannon et al. 2004 and Stern et al. 1999 (TP06's release), Tran et al. 2009 (the SERCA
cycle, via ER_CALCIUM.md).

**Tools and model files:** Myokit (github.com/myokit/myokit); OpenCOR (opencor.ws); Chaste
(github.com/Chaste/Chaste, github.com/Chaste/cellml); the Physiome Model Repository
(models.cellml.org; entries e/639, e/80d, e/5f1); the Rudy lab's code (rudylab.wustl.edu). Their
licences are in §5.3.
