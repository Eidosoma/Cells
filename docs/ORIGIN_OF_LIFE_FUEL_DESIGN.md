# Fuel for the assembly engine (OL4): design note

**Status: option (d) chosen (D245), conditional on the desk probe, which confirmed §2.3's
condition (20 November 2026).** This note is desk work: options, a recommendation, files, tests and
a price (D142).
- It contains no engine code, and no engine or fueled world was run.
- A result marked **S** is this note's own derivation, done by hand. §2.3 says what the lead's
  host-only desk probe then checked.
- "Cited from memory, not verified" marks standard theory that was neither read nor checked for
  this note.
- Line numbers are at main ecc7c131. The branch is `ol4-fuel-design`.

**The decisions, 20 November 2026** (D245, and the lead's rulings on §10's questions):
- **U1:** option (d) was chosen, conditional on the desk probe confirming §2.3's condition. The
  probe confirmed it (§2.3, C1).
- **U4:** F12 is kept as the preprint defines it. A second reading, each parent against the next
  parent, gets its own name and registration. H's species set is declared per experiment: for (d),
  the amphiphiles only.
- **U2:** fuel reacting at the membrane, option (b1), comes later.
- **U3:** A9 and A10 join §7.4 as reported comparisons only, after their numbers were checked
  (done: §3, Sources).
- **L1:** the refusal of a factor on a pool-only step goes to the first builder.
- **L3:** A5 stays reported. No other host is tried for its Supplementary Information.
- **L4:** the desk probe of §2.3 was approved, host only. It has run; its results are in §2.3.
- **L5:** no per-species transfer record for now. The fuel reader uses the diagnostic record.

**The request.** D212 sets the user's target: a first-principles lipid simulation in which
vesicles take lipids and chemicals in and out, grow and divide, so that "break and renew" of
compositional inheritance can be tested across fissions. F12 is that test
(`validation/assembly_lineages/inheritance.py`). On 20 November the lead raised a caveat.
Catalysis in `cells.assembly_lineages@2` keeps detailed balance, so without a drive the vesicles
may relax to one composition, and the result could be null. The user chose the lipid route and
asked for everything to work, fuel included (D242). Fuel is OL4 in ORIGIN_OF_LIFE_ENGINE_DESIGN.md
(§3, §8; anchor A5 in §7.4).

**Engine models it would run.** `cells.assembly_lineages@2`, with:
- `cells.stochastic_mass_action@1`, `cells.phase_exchange@1`, `cells.transition_state_factor@1`
  and `cells.ideal_mixing@1`;
- in vesicle worlds, also `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`,
  `cells.shear_fission@1`, `cells.shared_pool@1` and `cells.serial_transfer@1`.

Option (b1) would add one new reaction law (§3).

**Terms used here.**
- **A held species** (a chemostat) is a pool species kept at a declared concentration by an
  implicit reservoir. It has no count. The free energy its reservoir supplies is booked as
  *reservoir work*.
- **A moiety** is a part of a molecule that every step conserves, such as an acyl chain or a
  fuel's reactive group.
- **The drive** of a cycle of steps is the free energy, in k_BT, released by one turn of it. For a
  fuel-to-waste cycle with held fuel F and held waste W, it is μ_F − μ_W.
- **The factor** is `cells.transition_state_factor@1`: catalysis by membrane species ("members").
  It multiplies both directions of a step by the same g = 1 + Σ_j β_j x_j, where x_j are the
  catalysts' fractions in the membrane and β = e^ΔΔG‡ − 1. It is evaluated on the step's common
  state m, which holds, for each place, the smaller of its counts before and after the step.
- **A vesicle world** declares a geometry. Division needs one, together with an osmotic lumen
  (`division.py:61–65`).
- **A stable composition** is a membrane composition to which the deterministic (mean-field)
  dynamics return after a small push.

## Summary

1. **Most of §3 already exists** in the version-2 family (§1):
   - held species and their reservoir work;
   - species moieties and registry potentials;
   - mass action with held activities;
   - stored energy inside F;
   - the refusal of driven laws;
   - work for shear and transfer schedules.

   **Four things are missing:**
   - a fuel step between pool species and membrane species in vesicle worlds (§0.2c rule 3
     refuses it);
   - a consistent meaning for members catalysing a pool-only step;
   - per-species records across a transfer;
   - a step in a held concentration at a declared time. Option (d) does not need it.
2. **The crux (S, §2; checked by the desk probe).** Fuel lets catalysis set the composition: the
   steady state of a driven cycle depends on its rates, while an equilibrium does not. But fuel
   alone gives *one* stable composition per environment. Two or more need three things together:
   - the step that makes a membrane species is autocatalytic in its stoichiometry (the member is
     both a reactant and a product);
   - members catalyse that step through the factor;
   - a drive above a threshold.

   **What the probe found:**
   - The threshold condition held exactly, across 4,000 random parameter sets.
   - No lineage of real size switches between the two compositions on its own. The switching time
     grows exponentially with the amphiphile count (C8).
   - The drive can be a fuel's cycle affinity, which works even in vesicles that do not grow.
   - Or it can be a feed's supersaturation with no fuel at all, which works only while the
     vesicles grow. That is a no-fuel variant, (d0).
   - Option 0, (a) and (c) lack the autocatalytic stoichiometry. They give one stable composition
     in every sampled set whose vesicle grows or holds its size. Two appeared only in shrinking,
     dissolving ones (the largest γ at such a stable state was −0.0005).
   - Vasas, Szathmáry and Santos 2010 found one dominant steady state for GARD's deterministic
     dynamics, which agrees.
3. **Chosen: option (d)** (D245), a full fuel-to-waste cycle with the activation catalysed and the
   deactivation uncatalysed (§4).
   - It is built first with the fuel recharging a building block in the pool, which the membranes
     then turn into amphiphiles.
   - It is registered with its own nulls, true equilibrium and β = 0, in the same world. Its no-fuel
     variant (d0) can run beside it as a further control.
   - It needs no new law, token or record. The one refusal it relies on is the first builder's (L1).
   - It costs about 4.75–5.75 agent-days, OL5's references included; (d) alone, 4–5.
   - Fuel reacting at the membrane, option (b1), comes later (U2).
4. **A risk outside OL4 (S, §2.4; C8).**
   - F12 scores each fission by comparing the parent with its daughter at the split. From about a
     hundred molecules up, with a few species, every split is inherited for every option.
   - The generational reading (D245) can see a switch between fissions. But no lineage of real size
     switches on its own (C8).
   - So OL9's breaks must be induced, or its vesicles kept to a few tens of amphiphiles. That is a
     new question for the user (U5).

## 1. What of §3 exists in the version-2 family

| §3 item | Where it is (main ecc7c131) | What is missing or refused |
| --- | --- | --- |
| **Held species (chemostats)** | `world.py:105–117`: a place's `held_mM`. `world.py:305–330`: parsed for the pool only. `world.py:39`: "Held places take part only as pool places". A held place has no count and no term in F (`ideal_mixing.py` docstring) | Held only in the pool. A held concentration cannot change at a declared time (see schedule work) |
| **Mass action with held activities** | `mass_action.py:6–13`: (c_s/c0)^a for a held reactant. `mass_action.py:119`: its term. The reverse comes from F, with held activities on the products' side | Nothing |
| **Reservoir work** | `ledger.py:12–13` and `:37–38`. `model.py:135–137`: each step's forward books w = −Σ_held ν μ_held. `kernel.py:490` and `:501`: each event books ±w and the reservoir's net supply | One total is recorded, `reservoir_work_kT` (`records.py:93`). The split by payer (fuel against waste) is not recorded, but it is exact from `reservoir_supplied` (`records.py:75`) times each held place's μ. `validation/` can read it, so `records.py` need not change |
| **Species moieties and registry potentials** | `world.py:90–103`: the species. `world.py:191–220`: moieties, and potentials per phase kind. `world.py:428–445`: every step conserves every declared moiety, held places counted. Docstring `:24–26`: no step carries a ΔG° of its own | The potentials are the world's own table until the registry holds them per phase (R7) |
| **Stored energy of finite fuel and activated species** | Present inside F. A finite species' μ° is in the ideal term, so burning a finite fuel lowers F and the event heat books the fall. The closure F(n_t) − F(n_0) = W − Q (`ledger.py:16–23`) holds | No separate "stored energy" line. None is needed, since it is F's fall. `validation/` can split ΔF by phase |
| **Moiety ledgers** | A parse guard (`world.py:428–445`). One unit test checks at every row that Σ M·n − Σ M·(net supply) is constant (`tests/unit/test_assembly_lineages_v2_ledger.py:141`) | Not a record and not a run-time check. Across a serial transfer the books need the pool's counts just before it, and a transfer does not record them (ASSEMBLY_WASHOUT_DESIGN §2). On `ol-fr20-replacement` (ccf10915) a replacement records them; as that branch's diff reads, a transfer still does not. The diagnostic record (§0.2d item 10.5) holds the pool after every event when it is on |
| **Fuel-to-waste cycles** | A pool step F + S → B + W, with F and W held or finite, is admitted in every world. The unit fixture's `make_L` (`tests/assembly_lineage_v2_fixtures.py:105`) is the one-step case: a held precursor making an amphiphile in the pool | In a vesicle world a step between pool species and membrane species is refused, unless it is a one-molecule join or entry (`spec.py:342–350` and `:370–387`; §0.2c rule 3). OL5 registered that refusal (`refuse_interfacial_reaction`). So fuel can react in the pool, or inside the membrane if the fuel itself has a membrane place, but not between the two. Under the osmotic lumen, a lumen step with two lumen reactants is refused (`spec.py:279–292`; §0.2c rule 7) |
| **The refusal of unsourced driven laws** (D152's driven class) | Structural. `interfaces.py:50–62` refuses at registration every law whose energy role is not passive, or that names an energy source. `tests/unit/test_assembly_lineages_v2_registration.py:156` plants both, `energy_role="driven"` and `energy_source="fuel"` | Nothing is missing. OL4 keeps the refusal total, because fuel is a species, never a law's role (§3.2). The message says sources come "(OL4)". It is a registration message, not a world refusal, so its wording may change when OL4 lands |
| **Schedule work** | Shear: `shear_work_kT` (`records.py:143`). Serial transfer: `schedule_work_kT` (`records.py:370`); its column pays F of the fresh pool (`transfer.py` docstring). FR-20's replacement, on its branch | A step in a held concentration is not built. It waits for the ruling on the washout note's Q3, and is priced there at +1 day. A transfer's `fresh_pool` already refuels a finite fuel, paid by the transfer's column |
| **Catalysis on fuel steps** | `transition_state.py:53–96` accepts an entry on any declared step. `kernel.py:289–290` applies the factor to every step | On a pool-only step the two modes disagree. A single lineage multiplies the rate by the one membrane's fractions. A population evaluates the pool group at an empty vesicle (`population.py:205`), so g = 1 there. Never exercised with a geometry: no unit test and no registered world declares a factor in a vesicle, population or division world. It is admitted by the code and never qualified there |

**Not needed by any option:**
- a driven law, a new token value or a new record;
- lumen chemistry. Rule 7 stays closed until OL8. Reopening it would retire OL5's registered refusal
  world `refuse_lumen_step_two_lumen_reactants`, which is an amendment for OL5.

**Osmotics.** Fuel and waste are pool solutes, so they count toward c_ext. A world whose c_ext is
below its pool solutes is refused (`spec.py:303–317`). A5's concentrations (5–20 mM fuel, 10 mM
precursor) fit under an outside osmolarity of a few hundred mM. A finite fuel changes the pool's
solute count as it burns (two acids become one anhydride, for example). The run reports that
drift, as for any finite pool (§0.2c rule 6).

## 2. The crux: what fuel must do

### 2.1 A cycle through the membrane

- **The rule.** Fuel changes composition only if its free energy drives a cycle that passes through
  the membrane: a step that makes a membrane species and a step that unmakes it. Member catalysis
  must act on a step of that cycle.
- **Where the fuel reacts does not decide this.** The drive belongs to the whole cycle: at a steady
  state, one cycle carries the same net flux through every one of its steps (S). The fuel molecule
  may react in the pool, upstream, or at the membrane. That is a choice of chemistry and realism,
  not of principle.
- **Fuel burnt in a cycle that never touches membrane species changes no composition.** The lead's
  remark is right.

### 2.2 Option 0: what today's worlds already do

A vesicle world is already driven by its feed: a supersaturated pool, held or refreshed at each
transfer. GARD_DESIGN §2.1 calls GARD's composomes non-equilibrium kinetic states for that reason.
Members can catalyse each join through the factor. So "driven" is not the test.

- **Between transfers,** a finite pool runs down toward equilibrium with the vesicles, and the
  vesicles relax toward one composition. A closed world relaxes to exp(−F) whatever the catalysts
  (§0.1).
  With ideal mixing, that law has one most likely composition for each set of conserved totals
  (Horn and Jackson 1972, cited from memory, not verified).
- **During growth** the composition is kinetic, and catalysed joins shape it. But a join is first
  order in the joining species and the factor is linear in the fractions, so one composition is
  stable (§2.3).
- **Vasas, Szathmáry and Santos 2010** analysed GARD's growth and splitting deterministically. They
  found one dominant steady state, a positive eigenvector, for a network in which every type can
  reach every other. The composomes of stochastic runs were quasi-stationary and turned into each
  other and back.
- **Non-ideal mixing** (`cells.regular_mixing@1`) beyond its critical value makes F non-convex, but
  it is no substitute (S, not run). One lumped membrane cannot hold two domains, so two minima of
  its F would be an artefact of the lumping: real lipids at that strength split into domains.

### 2.3 When more than one composition can be stable (S; checked by the desk probe)

This section is a derivation by hand, checked by the lead's approved desk probe (L4).
- **The probe** is host-only: no engine import and no fueled world. C1–C7 are deterministic and
  mean-field. C8 is one small stochastic chain.
- **Its files:** `/mnt/workspaces/Cells/ol4-fuel-design-20261120/probe/`. They are `README.md`, with
  the criteria written before each run; `probe.py`, `results.json` and `run.log`; and
  `probe_switching.py`, `switching.json` and `switching.log` for C8.
- **References below:** "C1"–"C8" are the probe's criteria.
- **The outcome.**
  - C1–C3 passed, and so did C8's implementation check.
  - C6 and C7 failed as written, for the reasons given below.
  - Nothing refutes (d)'s condition.

**The test.** Let r_i be the net rate, per molecule, at which amphiphile i is made in a membrane:
its making per molecule minus its unmaking per molecule. With two amphiphiles at fractions x_1 and
x_2 (T = x_1 + x_2), the share f = x_1/T changes as

    df/dt = f(1 − f)(r_1 − r_2).

The membrane's fractions sum to one, so growth dilutes them all alike. An even mixture is stable
when the minority's r is the larger. Two compositions are stable when the majority's is.

- **Uptake by a catalysed join** (option 0, (a)). Making per molecule is proportional to
  (1 + β x_i)/x_i, and its 1/x_i favours the minority.
  - With catalysis (β > 0), the leave favours the minority too. **One composition.**
  - With inhibition (β < 0), the leave favours the majority. The probe found two stable
    compositions in 270 of 4,000 random sets. Every one was in a membrane that shrinks: the growth
    rate γ was below zero at every stable state (C7).
  - A shrinking vesicle is dissolving. It cannot carry a dividing lineage.
- **Catalysis of, or protection against, unmaking** ((c)). Unmaking per molecule is
  h(1 + β x_i), against a supply that members do not catalyse.
  - With catalysis (β > 0): **one composition.**
  - With protection (β in (−1, 0)): two stable compositions in 298 of 4,000 sets. Again, all were in
    shrinking membranes (C7).
  - **A correction.** This note's first version claimed one composition for every β. That
    derivation assumed a membrane that neither grows nor shrinks, and so missed these cases.
- **Autocatalytic making** ((b), (d)). In the step B + L_i → 2 L_i, catalysed by L_i
  (g_i = 1 + β x_i), making per molecule is k1 x_B (1 + β x_i). It grows with x_i, so it favours
  the majority.

**(d)'s condition, in a reduced model.**
- **The model.** One membrane holds the activated block B and the spent form S at fractions x_B and
  x_S, set by fast exchange with the pool. It also holds two amphiphiles L_1 and L_2, and
  optionally an inert lipid.
- **The steps.**
  - B + L_i ⇌ 2 L_i: forward constant k1, catalysed by L_i with β > 0.
  - L_i ⇌ S: forward constant k2, uncatalysed.
- **The reverses come from F:** k1·e^Δ1 and k2·e^Δ2. Here Δ1 = μ°_L − μ°_B and Δ2 = μ°_S − μ°_L.
  Both are negative, so each step runs downhill.
- **The result.** The even mixture splits into two stable compositions, an L_1-rich one and an
  L_2-rich one, exactly when

      β·x_B > e^Δ1·(1 + β·T) + 4·(k2/k1)·e^Δ2·x_S/T².

- **Confirmed (C1).**
  - The sample: 4,000 random parameter sets, each converted exactly to fractions.
  - Against an independent count of stable states from the raw fluxes, the inequality's sign was
    right in every set (1,024 of them bistable).
  - Exact rational brackets confirmed every predicted state's position and stability.
  - 1,200 RK4 integrations ended on the predicted states. Σx = 1 held to 3 × 10⁻¹³, and halving the
    step changed nothing beyond 2 × 10⁻¹³.

**The two drives.** Write A = ln(x_B/x_S) − (Δ1 + Δ2) for the cycle's drive, its affinity in k_BT
per turn. Write ρ = T/T_eq for the supersaturation, where T_eq = 2·e^Δ2·x_S is the amphiphiles'
fraction at equilibrium with S. The inequality then reads

    A > A* = ln[2ρ + 2/(β·T_eq) + 4·(k2/k1)/(β·e^Δ1·ρ²·T_eq²)].

- **At true equilibrium (A = 0 and ρ = 1): never** (C2: 0 of 4,000 sets). For ρ ≥ ½, A* exceeds
  ln 2ρ ≥ 0, so zero affinity never suffices there (C2: 0 of 4,000 at ρ from ½ to 4).
- **At β = 0: never** (C3: 0 of 4,000). The factor is necessary.
- **A fuel's affinity works without growth.**
  - 121 of the 1,024 bistable sets had γ ≤ 0 at their stable states, so their vesicles did not
    grow. All were at A ≥ 3.5 k_BT (C1).
  - In C4b, a fuel-driven set's even mixture neither grows nor shrinks (γ = 0 exactly).
- **A feed's supersaturation works without fuel, but only while the vesicle grows.**
  - At zero affinity and ρ < ½, two compositions appear once β is large enough.
  - The trial set is C4: Δ1 = Δ2 = 0, x_B = x_S = 0.45, T = 0.1 (ρ = 1/9), k2/k1 = 0.01 and β = 20.
    It is bistable, at f = 0.082 and 0.918, and it grows at γ ≈ 1.06 per unit time.
  - So the drive can be the feed as well as fuel. At zero affinity it needs growth, which a finite
    pool loses as it runs down between transfers.
- **The map (C5).** In a strongly downhill regime (e^Δ1 = e^Δ2 = 1/8, x_S = 1/20, k2/k1 = 1/10,
  T_eq = 1/80):
  - Where the threshold fits in the membrane, A* falls from 6.6 to 3.4 k_BT as β rises from 2 to
    64, for ρ between 4 and 64.
  - At ρ ≤ 1 the threshold needs more block than the membrane can hold, except at β ≥ 32 and
    ρ = 1 (A* = 6.5 and 5.8 k_BT).
  - The closed form for A* matched the exact threshold to rounding in every cell.
  - On the zero-affinity line, two compositions need ρ = ¼ and β ≥ 6.6 × 10⁵ there
    (ΔΔG‡ ≥ 13.4 k_BT).
  - In the feed regime (Δ1 = Δ2 = 0, x_S = 0.45, k2/k1 = 0.01) they need only β ≥ 8
    (ΔΔG‡ ≥ 2.2 k_BT), at ρ = 1/9.
- **When T follows x_B and x_S.** 
  - **With no inert lipid** (T = 1 − x_B − x_S; C5b):
    - for every β from 1 to 64 there is one window of x_B, from about 0.11–0.22 (A ≈ 4.9–5.6 k_BT)
      up to about 0.89–0.94 (A ≈ 7.0–7.1 k_BT);
    - above the window the amphiphiles are too dilute (T below 0.06) to hold two states.
  - **With finite exchange** (Tier F: B, S and the inert lipid join and leave at rate κ; C6):
    - The two compositions persist while exchange outpaces the block's use: at κ = 100 and 10 for
      both bistable sets, and at κ = 1 for the fuel set.
    - They merge into one when supply is slow: κ = 0.1 for the fuel set, κ ≤ 1 for the feed set.
      There the block is drawn down; at κ = 0.1 the fuel set holds x_B = 0.04 against the pool's
      0.1.
    - At every κ the Tier F state satisfies Tier P's formula at its own x_B, x_S and T, to 10⁻¹³.
  - **C6 fails as written.** At κ = 100 the feed set's state lies at f = 0.931, against Tier P's
    0.918 at the pool's values. Its fast growth (γ ≈ 1.08) moves x_B and T about 1% off them.
- **Switching against size (C8, added at the lead's request).**
  - **The chain:** §2.3's reduced model as exact events, with growth, and a hypergeometric halving
    at each fission. The followed daughter starts with M_0 amphiphiles.
  - **The scaling.** The mean time to switch from the L_1-rich to the L_2-rich state grows
    exponentially with M_0:

    | Set | ln τ per amphiphile | Generations to a switch |
    | --- | --- | --- |
    | F1 (fuel, A = 4.85 k_BT) | 0.234 | 137 at M_0 = 4; 1.2 × 10⁸ at M_0 = 64 |
    | C4b (fuel, an even mixture that does not grow) | 0.134 | 21 at M_0 = 4; 1.5 × 10⁸ at M_0 = 128 |
    | C4 (feed, zero affinity) | 0.071 | 46 at M_0 = 4; 4.4 × 10⁹ at M_0 = 256 |

  - **Extrapolated:**
    - to 10³ amphiphiles, 10³³ to 10¹⁰³ generations;
    - to 10⁴, 10³¹¹ to 10¹⁰¹⁸;
    - to 10⁵, beyond 10³⁰⁰⁰. A 100 nm vesicle holds about 2 × 10⁵ molecules (§1.2).
  - **No spontaneous break at real size.** In this model a lineage of real size never switches on
    its own.
    - By this note's arithmetic on C8 (twelve over the generations to a switch), a switch within
      twelve fissions has a chance above 5% only up to about 6 (F1), 16 (C4) or 24 (C4b)
      amphiphiles at birth.
    - At real size a break must be induced, for example by a pulse of the other amphiphile through
      FR-20's replacement. The renewal is then the lineage's settling into a state.
  - **The checks.** A host SSA of the same chain matched the exact times within 3 standard errors at
    two small sizes per set (C8a). The largest exact times used were 4 × 10⁸ to 3 × 10⁹, where
    τ·λ_min lies within 0.1% of 1; larger sizes failed the accuracy rule. The extrapolation assumes
    the exponential scaling continues beyond M_0 = 64–256.
- **The limits.**
  - The model is reduced: B and S are pinned, and the amphiphiles never leave the membrane.
  - The stochastic part is this one chain. The engine's own events, and the stationary law's two
    modes, are OL5's to compute (§5).

**So three things are needed together:**
- autocatalytic stoichiometry in the making of a membrane species;
- the factor on that step (β > 0);
- a state away from equilibrium with enough drive. That is either a fuel's cycle affinity, which
  works without growth, or a feed's supersaturation, which works only while the vesicles grow.

At true equilibrium, or at β = 0, one composition is stable.

### 2.4 What F12 can see (S)

`inheritance.py` scores each fission by H, the cosine between the parent's counts just before the
split and the followed daughter's counts just after it (`lineage_marks`, `inheritance.py:92–99`).
The fission is inherited if H > 0.9, and a break otherwise. For (d), H is taken over the amphiphiles
only, the L_i, never the block B or the spent form S (D245).
- **H sees the split's sampling, not a change of state between fissions.**
  - Take two species at equal shares. For H ≤ 0.9, a daughter's share must differ from the parent's
    by 0.24, since H = 1/√(1 + 4δ²).
  - A half split of N molecules moves the share by about 1/(2√N), one standard deviation.
  - So a break needs a deviation of about 0.48·√N standard deviations: 2 at N = 17, and 15 at
    N = 1,000.
- **From about a hundred molecules up, F12 scores 0 for every option.** §1.2 plans exact events
  for assemblies of up to 10³–10⁴ molecules; OL9's sizes are not yet set.
  - At N = 100, a break already needs a 4.8-standard-deviation split, fewer than two in a million
    (normal approximation).
  - So from about a hundred molecules up, with a few species, every mark is 1. A run of inherited
    fissions with no earlier break scores zero.
  - At GARD's tens of molecules, breaks come from sampling, for every option.
- **What (d) changes, and what it does not.**
  - It changes how often a split is a break: a composition dominated by one amphiphile splits more
    faithfully.
  - It changes what follows a break: a noisy split can send a daughter across to the other state.
  - A switch between fissions leaves no mark.
- **So from about a hundred molecules up, F12's marks cannot tell (d) from option 0.** F12 stays
  as the preprint defines it (D245).
- **A second reading** (D245) compares each parent at its fission with the next parent on the same
  path.
  - It has its own name and registration, and is never called F12. This note proposes "the
    generational reading", with H_gen its similarity.
  - It would see a switch between fissions as one low H_gen.
  - But by C8, a lineage of real size does not switch on its own (§2.3).

## 3. Options

Every option keeps every step passive, with its ΔG° from the species' potentials. The fuel's drive
is μ_F − μ_W per turn of the cycle when fuel and waste are held. With a finite fuel, the drive is
the fall of F. The event domain |ΔF| ≤ 80 k_BT (§2.1 of the engine note) bounds a single step. A
fuel that releases more goes through an intermediate, as A5's O-acylisourea does.

No source was read for the potentials of A5's fuel (EDC) or its urea, so a world declares them
unsourced (§0.2e rule 3) until one is read. §5 lists the checks OL5 writes for every option.

| Option | The step fuel pays for | More than one stable composition? | New law? | Anchor | Agent-days, builders + OL5 |
| --- | --- | --- | --- | --- | --- |
| 0 | None (the feed drives growth) | No | No | A1, A4 as planned | 0 |
| **(a)** | Making an amphiphile from a pool precursor; members catalyse its join | No (only in a shrinking vesicle, with inhibition) | No | A5, reported | 1.75 + 1.5–2 (builders + OL5) |
| **(b)** | Activation or synthesis of membrane species at the membrane, catalysed by members | Only with autocatalytic stoichiometry | (b1) yes; (b2) no | None in §7.4 | (b1, later) 3.5–4.5 + 2.5–3.5; (b2) as (d) |
| **(c)** | Destruction (turnover) of membrane species; members protect or catalyse | No: it selects one (two only in a shrinking vesicle, with protection) | No (spontaneous destruction) | A5; A9, reported | 1.75 + 1.5–2 |
| **(d)** | A full cycle: activation catalysed (autocatalytic), deactivation uncatalysed | **Yes, above a drive threshold, with or without growth** | No (fuel upstream) | A10, reported; A8's definitions | 2 + 2–3 |
| (d0) | None: (d)'s autocatalytic step driven by the feed's supersaturation | Yes, but only while the vesicles grow | No | As (d) | 2 + 2–2.5; beside (d), +0.25 + 0.5 |

### (a) Making an amphiphile from a pool precursor

- **The scheme.**
  - In the pool, F + P → A + W. Fuel turns a precursor P that does not assemble into an amphiphile
    A that does, as EDC turns a dicarboxylate into an anhydride in A5.
  - A joins membranes, and members catalyse its join through the factor.
  - A decays back to P, in the pool and in the membrane, and P leaves.
- **What it makes possible.**
  - Fuel holds the pool's A above equilibrium by remaking it, not by holding it. A finite fuel
    runs down, and the assemblies then vanish: A5's lifetime against fuel.
  - With decay in the membrane, membranes turn over. Their composition is then a steady state in
    which catalysed joins matter.
  - The join is first order and the factor linear, so there is **one composition** per environment
    (§2.3). The exception is inhibition (β < 0) in a shrinking, dissolving vesicle (C7). Against
    option 0, (a) adds realism (fuel, waste, lifetime), not alternatives.
- **What the engine needs.** Every step exists today:
  - the pool step (mass action, in any world);
  - the join (phase exchange);
  - the decay as an all-membrane step (`count_on_m`, admitted in vesicle worlds);
  - the factor on the join.

  Nothing else is new. The first builder's refusal (§6, L1) guards it.
- **The anchor: A5.** Tena-Solsona et al. 2017, CC BY 4.0; numbers as read through the fetch
  tool:
  - anhydride hydrolysis 3.8 × 10⁻² s⁻¹ (Fmoc-AVD) to 3.8 × 10⁻⁴ s⁻¹ (Fmoc-D), at pH 6.0 in 200 mM
    MES and room temperature;
  - Fmoc-D samples at 10 mM precursor stay turbid for 87 to 164 ± 5 min at 5 to 20 mM EDC;
  - critical anhydride concentrations of 0.3 ± 0.1 mM (Fmoc-D) and 0.07 ± 0.02 mM (Fmoc-E);
  - a side reaction takes at most 2% of the fuel.

  How it maps:
  - A5 fits (a) directly: in solution, fuel turns a non-assembling precursor into an assembling
    product. It anchors the cycle, its ledger and the lifetime against fuel, not member-catalysed
    activation.
  - Its assemblies are fibres and colloids, so its worlds have no geometry. They use a condensed
    phase under `count_on_m`, OL1's kind of world. Their pool must be small enough for exact
    events: 10 mM in 1 aL (10⁻¹⁸ L) is about 6,000 molecules, and in 1 fL about 6 × 10⁶ (S,
    arithmetic).
  - Role: reported, as D199 set it. A judged anchor would need Supplementary Table 1's
    activation constants, which were not read (§11).
- **OL5's references.**
  - The shared checks (§5).
  - The batch ODE of the cycle with a finite fuel, as the large-volume limit of the engine's mean
    (Kurtz 1972, cited from memory, not verified).
  - The time the assembling species stays above a declared threshold.
- **Price.** Second builder 1.25 shared + 0.25 for its worlds; first builder 0.25 (L1). OL5 1.5–2.

### (b) Activation or synthesis of membrane species at the membrane

- **The scheme.** Fuel from the pool reacts with membrane species: F + L → L* + W (activation), or
  F + 2 L → D + W (synthesis of a two-chain lipid). Members catalyse the step through the factor.
- **What it makes possible depends on the stoichiometry.**
  - With a catalyst that is not a reactant, there is one composition, as in (a).
  - With autocatalytic stoichiometry plus the factor, there are two above a threshold (§2.3). An
    example is F + L + L* → 2 L* + W, with three molecules on each side, D152's limit.
  - That limit leaves no room for an autocatalytic synthesis of a two-chain lipid with the fuel in
    the same step: F + 2 L + D → 2 D + W has four reactants. With an activated chain made upstream
    it fits: B + L + D → 2 D.
- **What the engine needs.** In a vesicle world such a step is refused (§0.2c rule 3). There are
  two routes.
  - **(b1) A new reaction law** for a step between one pool reactant and membrane species, with a
    geometric encounter. Its rate is a⁺ = k·A(m)·ρ0·θ_pool times the membrane reactants' draw,
    ff(n_i, a_i)/ff(N − c, r). That is phase exchange's kernel (`exchange.py:40–63`) on a wider
    shape. The lead would set its rules:
    - at most one pool reactant molecule in each direction, and the step is declared in a
      direction that has one;
    - no lumen place, since an inner-surface reaction needs rule 7 reopened;
    - the two leaflets lumped, assuming fast flip-flop, as a declared approximation.

    Mass action on such steps stays refused, so OL5's registered refusal worlds
    (`refuse_interfacial_reaction`, `refuse_count_on_m_cross_phase`) keep their messages. The
    law's ID and rate key are the lead's to name (§0.2b; question L2).
  - **(b2) Fuel and waste with membrane places.** They join and leave by phase exchange and react
    inside the membrane under `count_on_m`. No new law is needed. But they take membrane area,
    since each membrane species needs its area quanta (§0.2e rule 5), and they need bilayer
    potentials. That is physical only for a fuel that partitions into membranes, such as a
    hydrophobic carbodiimide. It does not fit A5's water-soluble EDC.
- **Anchor.** None in §7.4 tests activation at a membrane catalysed by members. A5's activation
  happens in solution. A10's fuel acts in water, upstream, so it maps to (d).
- **OL5's references.** The shared checks. For (b1), the law's closed form at random states and its
  refusals. For autocatalytic stoichiometry, (d)'s checks.
- **Price.**
  - (b1), later (U2): second builder 1.25 shared + 0.5 worlds + 1.5–2.5 for the law, so
    3.25–4.25; first builder 0.25. OL5 2.5–3.5.
  - (b2): as (d).

### (c) Fuel-driven turnover: the destruction step

- **The scheme.** A step of the fuel's cycle unmakes membrane species into waste or precursor. A
  step that members do not catalyse remakes them. Members catalyse the destruction, or protect
  against it (ΔΔG‡ < 0, so β is in (−1, 0)).
- **What it makes possible.**
  - Turnover gives each membrane species a finite lifetime. The composition is renewed constantly,
    as a steady state of making against unmaking.
  - Protection selects the species that protects itself, as A5's Fmoc-E and A9's droplets show.
  - In every sampled vesicle that grows or holds its size, protection did not outweigh a supply
    that favours the minority: **one composition** (§2.3). It selects; it does not hold
    alternatives. Two compositions appeared only in shrinking, dissolving membranes (C7).
- **What the engine needs.**
  - Spontaneous destruction inside the membrane needs nothing new: hydrolysis is an all-membrane
    step, with the factor.
  - Destruction by a pool reagent at the membrane needs (b1) or (b2).
- **Anchors.**
  - **A5:** assemblies slow their own hydrolysis. Fmoc-E's assembled anhydride hydrolyses at a
    zero-order 1.5 × 10⁻⁶ M s⁻¹.
  - **Candidate A9:** Tena-Solsona et al. 2018, *Nat Commun* 9:2044, PMC5966463, CC BY 4.0. Every
    number below was confirmed by a second targeted reading through the fetch tool, which returned
    the paper's own sentences. EDC-fuelled anhydrides of C3–C6 acids:
    - anhydrides that form droplets persist, with persistence factors 1.0 (C3), 1.26 (C4), 18.4
      (C5) and 118 (C6);
    - solubilities of 11 mM (C4C4), 1.0 mM (C5C5) and 0.05 mM (C6C6);
    - EDC's own hydrolysis at 1.3 × 10⁻⁵ s⁻¹, a value the paper takes from earlier work;
    - periodic batches of fuel selected better than continuous feeding.

    The outcome is one winner, which fits (c)'s single composition. Its assemblies are droplets.
- **OL5's references.** The shared checks. The protected steady state in closed form. One winner in
  a two-species world.
- **Price.** Second builder 1.5; first builder 0.25. OL5 1.5–2.

### (d) A full fuel-to-waste cycle: activation catalysed, deactivation uncatalysed

- **The scheme, with the fuel acting upstream (today's laws).**
  - In the pool, F + S → B + W recharges a spent building block S into an activated block B.
  - B joins membranes.
  - Inside a membrane, B + L_i → 2 L_i, for two amphiphiles L_1 and L_2. Each of these steps is
    catalysed by its own product L_i, through the factor with β > 0.
  - L_i decays to S, uncatalysed. S leaves for the pool, where fuel recharges it.
  - Moieties: B, S, L_1 and L_2 share the building block's moiety; F and W share the fuel's.
  - Places: B, S, L_1 and L_2 each have a pool place and a membrane place, since in a world that
    can lyse every membrane species needs a pool place (§0.2c rule 8). Each membrane species
    declares its area quanta (§0.2e rule 5). F and W are pool places only, held or finite.
- **What it makes possible.**
  - It is the one option with two stable compositions in the deterministic limit (§2.3): an
    L_1-rich state and an L_2-rich state, each kept by its own autocatalysis, above a drive
    threshold.
  - Turnover renews the composition. A lineage keeps its state across fissions while switches stay
    rare.
  - At true equilibrium, or at β = 0, it has one composition. Those are the control arms, in the
    same world.
  - In a population, vesicles of the two kinds compete for the shared B, which gives selection at
    each transfer. Exchange of L through the pool couples them, weakly when L's CAC is low.
- **Registration** (D245). (d) is registered with its own nulls, zero drive and β = 0, in the same
  world, and H is taken over the amphiphiles only. The probe shows that "zero drive" needs care
  (question L6 for the lead).
  - **At zero affinity a strongly supersaturated feed can still split the mixture** (C4, ρ < ½).
    Zero affinity alone is therefore not a null.
  - **True equilibrium** (zero affinity *and* ρ = 1) holds one composition, but a vesicle that
    does not grow never divides. It is OL5's stationary-law control (§5, check 4), not a lineage
    arm.
  - **A null that divides: zero affinity with ½ ≤ ρ < 1.**
    - The vesicles grow and divide, and they hold one composition, since A* > ln 2ρ ≥ 0 (C2).
    - A post-run check on 1,016 sampled sets found none bistable, and γ > 0 in every one (the
      smallest 1.0 × 10⁻³; the probe's `null_check.py`).
    - This note proposes it as (d)'s zero-drive lineage arm, beside β = 0.
- **What the engine needs.**
  - Every step exists today: the pool step, the joins and two all-membrane steps, with the factor
    on the autocatalytic step.
  - That step has a membrane place on both sides. It is admitted under `multinomial`, the physical
    worlds' measure (D215). Outside probe worlds it is refused under `multinomial_less_one`
    (`spec.py:390–401`; §0.2b rule 8).
  - Nothing else is new. The first builder adds the refusal it relies on (§6, L1).
  - A held B, §3.1's "activated monomers, held", is the simplest first world and needs no fuel
    species. Finite fuel can be refilled by each transfer's `fresh_pool`.
  - **Neither a held-B world nor (d0) may run before registration.** Both share (d)'s core step,
    so running either early spends the blindness of (d)'s references. Whether D245's fuel line
    covers them is question L6.
  - For fuel reacting at the membrane instead of upstream, add (b1) or (b2).
- **A no-fuel variant, (d0)** (found by the probe, §2.3).
  - The same autocatalytic step and factor, driven by the feed's supersaturation instead of fuel:
    the building block is held, or refreshed at each transfer, above its equilibrium level.
  - It needs no fuel species, and it holds two compositions only while the vesicles grow. A finite
    pool runs down toward equilibrium between transfers, so its compositions last only while the
    feed is renewed. Fuel's affinity also holds them in a vesicle that does not grow.
  - Beside (d), it is the natural control arm: the same world, without the fuel. It falls under
    the same no-run-before-registration rule.
- **The drive.** μ_F − μ_W per turn, or μ_B − μ_S with a held block. It must exceed the threshold
  of §2.3.
- **Anchors.**
  - **Candidate A10:** Morrow, Colomer and Fletcher 2019, *Nat Commun* 10:1011, PMC6397266, CC BY
    4.0. Every number below was confirmed by a second targeted reading through the fetch tool,
    which returned the paper's own sentences.
    - A surfactant forms from octanethiol and a disulfide, and its micelles catalyse its own
      formation.
    - Its breakdown, a slower exchange with excess thiol, is not accelerated by micelles.
    - Hydrogen peroxide, the fuel, slowly added at 1.2 M, regenerates the building block from the
      waste in water. The text read does not say whether 1.2 M is the stock's concentration.
    - The CMC is about 0.2 mM (ring tensiometry, 500 mM Tris, pH 7.5). The micelles' hydrodynamic
      diameter is 15–20 nm (dynamic light scattering).
    - Without fuel the surfactant is consumed.
    - The main text gives no kinetic model and no steady-state number, so A10 is qualitative and
      reported.
    - It has (d)'s structure with one replicator, in micelles. The engine design declares a
      micelle geometry, but the engine has not built one.
  - **A8:** Blokhuis, Lacoste and Nghe's definitions classify B + L → 2 L as autocatalytic.
  - **Not anchored:** two competing replicators and their threshold. They are the engine's
    prediction, to be registered before any judged run (OL9).
- **OL5's references.**
  - The shared checks.
  - The deterministic steady states and their stability: the inequality of §2.3 and its threshold.
  - In small exact worlds, the stationary law: unimodal at true equilibrium and at β = 0, bimodal
    above the threshold.
  - The mean switching time between the two states, by an exact first-passage solve, against the
    engine's.
- **Price.** Second builder 1.25 shared + 0.5 worlds, so 1.75; first builder 0.25; the desk probe
  is done. OL5 2–3. With (d0) beside it as its control arm: +0.25 builder, +0.5 OL5.

## 4. Recommendation

**Option (d), with the fuel recharging the building block in the pool, and (d0) beside it.** The
lead decided (d) with the advisor, under the user's delegation (D245), before the probe had
reported. The probe then confirmed its condition.
- It is the only option that held two stable compositions in sampled vesicles that grow or hold
  their size (§2.3, checked by the desk probe).
- It carries its own control arms: true equilibrium, β = 0, and (d0), the same world without fuel.
  - (d0) holds the two compositions only while its vesicles grow.
  - So comparing (d) with (d0) shows what fuel adds: compositions held without growth.
- It runs on today's laws: no new law, token or record. The one refusal it relies on is the first
  builder's (L1).
- Its structure is A10's, a fuelled surfactant that catalyses its own formation.
- **Then (b1)**, only if the user wants fuel to react at the membrane.
- **(a) and (c)** come almost free in the same machinery, as rungs of OL9's ladder, with A5 and A9
  reported.

**Two cautions.**
- **The probe checked a reduced model, not the engine.**
  - C1–C7 are deterministic; C8 is one stochastic chain with growth and fission.
  - OL5's references (§5) and the engine's own runs, after registration, are still to come.
- **F12's marks may not show what (d) adds** from about a hundred molecules up (§2.4). The
  generational reading would. But no lineage of real size switches on its own (C8), so a break at
  real size must be induced, or the vesicles kept to a few tens of amphiphiles.

## 5. The checks OL5 writes, for every option

Each check below is followed by its planted error, which it must catch (D187).
1. **The pair identity with fuel.** ln a⁺ − ln a⁻ = −ΔF + w, with w = −Σ_held ν μ_held.
   Planted: a fuel step without its reservoir work.
2. **Closure with fuel.** F(n_t) − F(n_0) = W − Q at every row. With held fuel, W gains
   μ_F − μ_W per net fuel event. With finite fuel, the fuel's free energy is inside F.
   Planted: the fuel's term dropped from F.
3. **The cycle's drive.**
   - Around a cycle that turns fuel to waste, Σ ln(a⁺/a⁻) = μ_F − μ_W. Around every other cycle
     it is 0.
   - Kolmogorov's test then fails by exactly the drive.
   - Planted: a drive of the wrong sign.
4. **The zero-drive control: true equilibrium.**
   - Take μ_F − μ_W equal to the cycle's standard balance, with the pool at its aggregation
     threshold, so no vesicle grows. The stationary law is then exp(−F)/Z, and the factor does not
     change it.
   - A zero affinity with a supersaturated pool is not this control; it can split the mixture
     (§2.3, C4).
   - Planted: the factor at each direction's own state (OL1's E1), which moves it.
5. **Moieties.** For the building block's moiety and the fuel's (fuel plus waste),
   Σ_s M_s·n_s(t) − Σ_held M_s·supplied_s(t) is constant at every row.
   - Planted: the reservoir's supply ignored.
   - In a population across a transfer, the check reads the diagnostic record, or a per-species
     transfer record (§1).
6. **Heat at stationarity.** With held fuel, the mean heat rate equals the cycle's flux times its
   drive (Schnakenberg 1976, cited from memory, not verified). Planted: the flux counted without
   its reverse events.

**The order** (D242, D245): no fueled world runs before OL5's references for it are registered.
That includes (d0) and held-B worlds, which share (d)'s core step.
1. Option (d) was chosen (D245), and the desk probe confirmed it.
2. This note is merged and tagged.
3. OL5 writes its fuel references from the tag alone, and registers them: designs and inputs,
   before any engine output.
4. The builder runs the probe driver on the registered inputs and compares the outputs.

## 6. Files and owners

**Open origin-of-life heads**, all the first builder's (D243):
- **`ol-fr20-replacement` (ccf10915):**
  - `diagnostic.py`, `division.py`, `population.py`, `records.py`, `transfer.py` and the new
    `replacement.py`;
  - `src/cells/registry/model_table.py` and `tests/test_tiers.json`;
  - `tests/unit/test_assembly_lineages_v2_registration.py` and the new
    `test_assembly_lineages_v2_replacement.py`;
  - `validation/assembly_lineages_v2/FORMAT_OL2.md` and `docs/ASSEMBLY_WASHOUT_DESIGN.md`.

  The lead's list adds `runner.py`, `spec.py` and `world.py` for FR-20's later slices.
- **`ol-pool-declared-lumen` (83155c65):** `population.py`,
  `tests/unit/test_assembly_lineages_v2_geometry.py` and the tier file.
- **`ol-lean-repairs` (49e505f2):**
  - @1's `gard.py`, `reference.py` and `ledger.py` docstring;
  - @2's `lumen.py` and `transition_state.py`, whose factor state and layout it rewrites;
  - `tests/assembly_lineage_fixtures.py` (@1's) and the two kernel test files.

**OL4 is built by the second builder** after this note is ruled (D243). That builder's own
break-and-renew branch, `ol-break-renew`, is still empty.

**The refusal, the first builder's (L1):**
- **`src/cells/models/assembly_lineages_v2/transition_state.py`:** in `parse_data`, one new
  refusal. It refuses an entry on a step whose places all lie in the pool, as a second pass over
  the entries after every existing check. Placed there, no existing message moves (§7). The file is
  already the first builder's: the Lean repair stack rewrites its layout, state and factor (not
  `parse_data`).
- **`tests/unit/test_assembly_lineages_v2_spec.py`:** rows in
  `test_the_rate_factor_is_refused_out_of_its_scope`.

**What OL4 touches (the second builder), under the recommended route and under (a) and (c):**
- **`tests/assembly_lineage_v2_fixtures.py`:** a `fuel=` switch, off by default, so every existing
  call is unchanged. It is shared by every v2 test file, so the change is announced; no open head
  edits it.
- **Ledger and kernel test rows** (§8), after OL5's registration.
- **New files in `validation/assembly_lineages_v2/`:**
  - a fuel ledger reader: work by payer, moiety totals, cycle counts from `channel_fired`, and the
    heat rate;
  - the fueled worlds' definitions.

**OL4 never edits** `population.py`, `runner.py`, `records.py`, `diagnostic.py`, `division.py`,
`transfer.py`, `replacement.py`, `lumen.py` or @1's files.

**If (b1) is chosen,** these are added:
- a new law file, `src/cells/models/assembly_lineages_v2/<law>.py`;
- one constant in `__init__.py`;
- `spec.py`: `_geometric_shape` and the law's refusals;
- `model.py`: `geometry_layout`'s encounter code for the new law;
- `src/cells/registry/model_table.py`: one law home;
- rows in the geometry and registration tests;
- a section of `FORMAT_OL2.md`.

`spec.py`, `model_table.py` and `FORMAT_OL2.md` are FR-20's too, so (b1) lands **after FR-20**.

## 7. What stays bitwise

Every existing @1 and @2 world must be unchanged.

**The mechanisms:**
- **Nothing existing changes:** no token value, no law's kernel, no layout array, no Structure field
  and no record. A world's id moves only if its definition does.
- **The one new refusal runs after every existing check,** in a second pass. Every registered
  refusal world therefore keeps its message.
  - OL1's `refuse_dilute_catalyst` names a pool step (`p1`) with a pool catalyst.
  - An existing check refuses it first, and must still do so.
- **The sweep.** No registered world declares a factor on a pool-only step:
  - OL1's inputs do so only in `refuse_dilute_catalyst`;
  - no world in OL5's export of OL2 and OL3 declares a factor at all;
  - the unit fixtures catalyse `join_L`, `dimerise` and the closed world's membrane steps only.

  The frozen inputs read were `/mnt/workspaces/Cells/ol1-laws-20261117/inputs-ab3dd700` (OL1) and
  `/mnt/workspaces/Cells/ool-references-20261117/inputs-e8759b48` (OL2 and OL3, pinned at main
  e8759b48). The builder repeats the sweep at landing.
- **For (b1):**
  - the new law's ID is in no existing world, and existing shapes, encounter codes and messages are
    unchanged;
  - mass action on a cross-phase step stays refused in vesicle worlds.

**How it is shown:**
- **`scripts/assembly_lineages_invariance.sh` on the OL4 head:**
  - @1's freeze test, its part-1 references, its probe set and G2's rows;
  - OL1's probe set against probes-3e39bcc5: arrays bitwise, JSON leaf by leaf except provenance.
- **OL2's and OL3's registered inputs,** once the first builder's probe roles exist (D243), compared
  in the same way.
- **The unit test files,** unchanged except for their new rows.
- **The plant.** A refusal that also catches membrane steps must fail the gate.

## 8. Tests (D224)

No new test file. The NESS, bistability and switching claims are OL5's references, compared
through the probe driver, not unit tests.

**Parse-only rows.** These can land any time after the source change, at about 0 s:
- `test_assembly_lineages_v2_spec.py` (tier 1, 2.02 s): a factor entry on `make_L` is refused, and
  one on `join_L` is admitted.
- For (b1), in `test_assembly_lineages_v2_geometry.py`: the law's shapes and refusals as `REFUSALS`
  rows. That file is tier 2: 28.85 s at main, 43.92 s on `ol-pool-declared-lumen`. Also one
  registration row (tier 1).

**Rows that compile and run a world.** These wait for OL5's registration of the fueled worlds. The
seconds are estimates, to be measured at landing:
- **`test_assembly_lineages_v2_ledger.py`** (tier 2, 39.38 s): the fueled fixture, held fuel and
  waste with one cycle, as one row of the closure test and one of the moiety test, under the
  physical pair. About +10–15 s.
  - Planted: the fuel's reservoir work dropped.
  - Planted: the waste's supply ignored.
- **`test_assembly_lineages_v2_kernel.py`** (tier 2, 43.32 s):
  - the fueled fixture in the identity-on-worlds row, about +2–5 s;
  - the zero-drive control as a row of the stationary-law test (an exact solve at small N), about
    +3–5 s.
- **For (b1)** (`test_assembly_lineages_v2_geometry.py`): the law's closed-form rate, about +3–5 s.

## 9. Price

| Part | Agent-days |
| --- | --- |
| The first builder (L1): the refusal and its parse rows, for any option | 0.25 |
| Second builder, shared: the fuel ledger reader in `validation/` | 0.5 |
| Second builder, shared: the rows that run a world, after registration | 0.25 |
| Second builder, shared: comparison with OL5's references, landing, invariance gate | 0.5 |
| Second builder, worlds for registration: (a) 0.25, (b) 0.5, (c) 0.25, (d) 0.5, (d0) 0.5; (d0) beside (d) +0.25 | 0.25–0.75 |
| (b1), later (U2): the new law, its rules, shapes and rows | 1.5–2.5 |
| The desk probe of §2.3 (L4): done | (0.25, spent) |
| **Second builder: (a) 1.5; (b1) 3.25–4.25; (c) 1.5; (d) 1.75; (d0) 1.75; (d) with (d0) 2** | |
| **OL5's references (its own line): (a) 1.5–2; (b1) 2.5–3.5; (c) 1.5–2; (d) 2–3; (d0) 2–2.5; (d) with (d0) 2.5–3.5** | |
| **Recommended, (d) with (d0) as its control arm, in all** | **4.75–5.75** |
| (d) alone, in all | 4–5 |
| (d) with the fuel at the membrane, adding (b1) and its references (later) | +2–3 |
| Optional: a step in held concentration, after the washout note's Q3 | +1 |
| Optional: a fuel dose that adds without replacing the pool (washout Q2 (b)) | +0.5 |

§8 of the engine note priced OL4 at 2–3 agent-days for the builder. OL5's references for OL1–OL4
were 4–6 there.

## 10. Questions

**For the user** (each can be answered in a word):
- **U1 (decided: (d), D245, conditional on the probe, which confirmed it).** Which step fuel pays
  for. (d0), the no-fuel variant the probe found, can run beside (d) as a further control. That
  costs about +0.25 builder and +0.5 OL5 agent-days.
- **U2 (ruled: later).** Fuel reacting at the membrane itself, option (b1), a new law, about +2–3
  agent-days.
- **U3 (ruled: reported comparisons only, after the numbers were checked; done).** A9,
  Tena-Solsona et al. 2018 (selection by protection), and A10, Morrow et al. 2019 (a fuelled
  surfactant that catalyses its own formation). Both are CC BY 4.0.
- **U4 (decided: (ii), D245).** F12 is kept, and a second reading, each parent against the next
  parent, is registered under its own name. This note proposes "the generational reading" (§2.4).
- **U5 (new, for the user).** By the probe (C8), no lineage of real size switches between the two
  compositions on its own. Should OL9's break be:
  - (i) induced, for example a pulse of the other amphiphile through FR-20's replacement;
  - (ii) spontaneous, in vesicles of a few tens of amphiphiles;
  - or (iii) both, as separate arms?

**For the lead:**
- **L1 (ruled: the first builder).** The refusal of a factor entry on a pool-only step. Still
  open: should a lumen-only step's factor also need a declared meaning?
- **L2 (open when (b1) is taken up).** Name (b1)'s law and its rate key, and confirm its three rules
  (§3 (b)).
- **L3 (ruled: A5 stays reported).** Its Supplementary Information was not read: on PMC the PDF
  returned a browser check, and nature.com redirected to a login. No other host was tried.
- **L4 (ruled: approved, host only; done).** The desk probe of §2.3.
- **L5 (ruled: not now).** A per-species transfer record. The fuel reader closes the moiety books
  across a transfer from the diagnostic record.
- **L6 (new).** Two questions on D245's "zero drive" and fuel line.
  - D245 names the null "zero drive". Should (d)'s dividing null be zero affinity with ½ ≤ ρ < 1
    (§3 (d), Registration), with true equilibrium kept as OL5's stationary control?
  - Does D245's fuel line cover held-B worlds and (d0)? They share (d)'s core step, so this note
    treats them as falling under the no-run-before-registration rule.

## 11. What this note could not verify

- **A5's activation constants** (Supplementary Table 1). Not read (L3), so A5 stays reported.
- **§2.3's results** were checked by the desk probe, not by the engine.
  - The probe is a reduced model: B and S are pinned, and the amphiphiles stay in the membrane.
  - C6 and C7 failed as written, as §2.3 explains.
  - C8's extrapolation to real sizes assumes the exponential scaling holds beyond M_0 = 64–256.
- **The factor in vesicle and population worlds:** that it passes the kernel's check there, and that
  the two modes disagree on a pool-only step. Both come from reading the code
  (`kernel.py:289–290`, `population.py:205`), not from running it. No test or registered world
  declares a factor with a geometry.
- **(d)'s core step in a vesicle world.** A step with a membrane place on both sides parses under
  `multinomial` (`spec.py:390–401`), but no vesicle world has run one.
- **The F12 numbers in §2.4.** They are arithmetic on `inheritance.py`'s definition. The species set
  of @2's F12 reader is not yet written.
- **FR-20's later slices touching `runner.py`, `spec.py` and `world.py`.** That is the lead's list;
  those files are not yet on the branch.
- **The potentials of A5's fuel and its urea.** No source was read.
- **The sources' numbers.** All were read through the fetch tool, which summarises a page against
  a prompt.
  - A9's and A10's numbers were confirmed by a second targeted reading, asking for the exact
    sentences.
  - A5's numbers and Vasas's findings had one reading only.
- **Theory cited from memory, not verified:** Horn and Jackson 1972, Schnakenberg 1976 and Kurtz
  1972.

## Sources

**Searching and fetching.** Web searches used plain queries with no identity. Each page was fetched
once through the web fetch tool, which summarised it against a prompt. Numbers are cited only where
the fetched text stated them (D186, D201, D227). Nothing was copied into the repository.

| Source | Result |
| --- | --- |
| Tena-Solsona M et al. (2017), *Nat Commun* 8:15895, PMC5520059 (A5) | Main text read once; its numbers here had that one reading. CC BY 4.0. Supplementary Information not read: PMC returned a browser check, and nature.com redirected to a login (L3) |
| Tena-Solsona M, Wanzke C, Riess B, Bausch AR, Boekhoven J (2018), *Nat Commun* 9:2044, PMC5966463 (candidate A9) | Main text and methods read. Every number quoted confirmed by a second targeted reading of the paper's own sentences. CC BY 4.0 |
| Morrow SM, Colomer I, Fletcher SP (2019), *Nat Commun* 10:1011, PMC6397266 (candidate A10) | Main text and methods read. Every number quoted confirmed by a second targeted reading of the paper's own sentences; whether 1.2 M is the stock's concentration is not stated. CC BY 4.0. No kinetic model or steady-state number in the main text |
| Vasas V, Szathmáry E, Santos M (2010), *PNAS* 107:1470, PMC2824406 | Read. No reuse licence stated (PNAS, free to read); used under D201 for its findings only |

**Cited from memory, not verified (not read for this note):**
- Horn and Jackson 1972: one equilibrium per conservation class for complex-balanced mass action;
- Schnakenberg 1976: network theory of stationary states and their entropy production;
- Kurtz 1972: the large-system limit.

**Engine documents and code read:**
- AGENTS.md;
- DECISIONS.md: D152, D197, D199, D212, D215 and D242–D245 in full (D244 only for its context);
  D237–D241 by their headings;
- ORIGIN_OF_LIFE_ENGINE_DESIGN.md: §0.1–§0.2e, §1–§10;
- ORIGIN_OF_LIFE_OL2_OL3_CHECK.md: §1.6, §1.7 and §4;
- SHARED_INVENTORY_REACTIONS_DESIGN.md: §2 and §3.1–§3.3;
- ASSEMBLY_WASHOUT_DESIGN.md, GARD_DESIGN.md §2.1 and §8, and FEATURE_REQUESTS.md's FR-20 to
  FR-22;
- in `src/cells/models/assembly_lineages_v2/`:
  - in full: `world.py`, `ledger.py`, `mass_action.py`, `transition_state.py`, `spec.py`,
    `kernel.py`, `interfaces.py`, `model.py`, `exchange.py` and `permeation.py`;
  - in part: `population.py`, `division.py`, `transfer.py` and `records.py`;
  - their docstrings only: `geometry.py`, `lumen.py`, `runner.py`, `diagnostic.py`, `balance.py`,
    `ideal_mixing.py`, `conventions.py` and `__init__.py`;
  - not opened: `regular_mixing.py`, `checkpoints.py`, `streams.py` and `reference.py`;
- `validation/assembly_lineages/inheritance.py`, the v2 test files' claims, the v2 fixtures, the
  invariance script and the tier records;
- the open branches' file lists: `ol-fr20-replacement`, `ol-pool-declared-lumen` and
  `ol-lean-repairs`.

The references' code under `validation/ool/references/` was not read. Only the frozen exports of
registered inputs were read, for the sweep in §7.

**The desk probe's tools:** Python 3.13.5, NumPy 2.5.3 and SciPy 1.18.1, from the project's CPU
virtual environment, on CPUs 6 and 7 at nice 10. Its record is in the probe's `README.md`.
