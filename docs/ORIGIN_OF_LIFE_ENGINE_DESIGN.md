# Cells' own origin-of-life engine: physical chemistry in assemblies (design)

**Status: proposed, 17 November 2026, for the lead and then the user.** Options first, then the
discussion (D142, D197). Docs only: nothing here is built. Branch `ool-engine-design` from main
a5caecbc. **S** marks this note's own derivation, probe or reading. "From memory" marks standard
theory cited without being read for this note; it is cited properly when a law is built. Evidence:
`/mnt/workspaces/Cells/ool-design-20261117/` (exact-rational probes E1–E3, results and a README).

**The request.** D197, the user on 17 November: "we will also do our own first principle engine,
GARD is only for comparison". GARD (D192) becomes one declared law set on G1's machinery. This
engine is Cells' own: its laws come from physical chemistry, its catalysis keeps detailed balance,
its assemblies are physical, and its free energy has explicit sources.

**Engine models (AGENTS.md).** This note runs none. Its milestones (§8) run G1's family,
`cells.assembly_lineages@1` as G1 builds it (the ID proposed in GARD_DESIGN §1), with the laws,
free-energy providers and operators proposed in §2–§4. Each milestone names the ones it runs.
- **Names are mechanisms' (D144).** Nothing is named for the origin of life, protocells or GARD.
- **The same pieces are general.** They are Syn3A's F11 (exact stochastic reactions) and F14
  (state-triggered division with a stochastic partition), and part of the endogenous lifecycle.

**What it builds on.** G1's scope only as GARD_DESIGN §7.2 lists it. Every further need is put to
the lead as a requirement (§6.3), not assumed.

## 0. The plan

### 0.1 One rule for every law (**S**)

Every change is a forward and reverse event pair, n ⇌ n′ = n + ν. Its two rates are

  a⁺(n) = s(m) θ⁺(n),  a⁻(n′) = s(m) θ⁻(n′),  with  θ⁺(n)/θ⁻(n′) = exp(−[F(n′) − F(n)]/k_BT).

- **F** is one free-energy function of the counts. It is built from the species registry's standard
  potentials, mixing in each phase, the assembly's geometry and its lumen (§2.2).
- **m = min(n, n′),** elementwise, is the pair's common state: what is present before and after.
- **s ≥ 0** is the law's kinetic factor: encounter, barrier or catalysis. It is evaluated on m, so
  it is the same for both directions.

**What follows from the rule:**
- local detailed balance holds by construction;
- a closed world relaxes to exp(−F/k_BT), whatever the catalysts;
- each event's heat is a state-function difference plus booked work.

**How it relates to the engine.** It is the core-seams pass's contract for cycles in stochastic
form: thermodynamics in the kernel, kinetics in the law (CORE_SEAMS_DESIGN §3.2). GARD_DESIGN
§2.2's finding is the case where s is evaluated on each direction's own state.

**The probes behind it** (exact rational arithmetic, `probe_ldb.py`):

| Probe | s on m, or rates from one F | The planted form |
| --- | --- | --- |
| **E1.** A closed three-type world: A ⇌ B and B ⇌ C, with B catalysing its own formation (GARD's kept diagonal). 28 states, 15 unit squares | No square fails Kolmogorov's test, and the stationary law is the product form exactly. Writing the catalysts into the stoichiometry (A + B ⇌ 2B) is also exact | The factor at each direction's own state: all 15 squares fail, with cycle ratios up to 143/128 (\|ln\| 0.11). The stationary law is off by a total variation of 0.083 |
| **E2.** An assembly exchanging two types with a finite reservoir, with a pairwise interaction (ω = 3/2 per contact). 36 states, 25 squares | Leave rates from one F: no square fails, and the law is Boltzmann's exactly | Type 1's off rate slowed by type 2, with no reciprocal term: all 25 fail, ratio up to 2/3, total variation 0.54 |

**E2's lesson (S).** A composition-dependent off rate is admissible only as a derivative of one
free energy. That is the Maxwell condition, ∂μ_i/∂n_j = ∂μ_j/∂n_i. So such a term moves the
equilibrium: it is thermodynamics, not catalysis. Budin and Szostak's phospholipid effect (§7.4, A2)
is such a term.

### 0.2 Decisions

| # | Decision | Options | Recommended |
| --- | --- | --- | --- |
| 1 | First entities (§1.1) | E1 abstract types (GARD's); E2 amphiphile assemblies with lumped geometry; E3 E2 plus oligomers; E4 spatial membranes | **E2 now, then E3's oligomers.** E1 stays GARD's law set. E4 waits for mechanics |
| 2 | Resolution (§1.2) | Counts; sequences; geometry, lumped or spatial; how to reach vesicle scale | **Integer counts.** Sequences only as a declared, bucketed family. Geometry algebraic in the counts. Exact events up to about 10⁴ molecules, and the deterministic limit of the same laws for vesicle-scale anchors |
| 3 | Thermodynamic basis (§2.1, §2.2) | Rate constants per law, with checks; one F from the registry | **One F;** laws supply only s ≥ 0 on m |
| 4 | Catalysis (§2.4) | Explicit steps; an effective factor on m; GARD's factor at each state | **The first two.** The third only inside GARD's law set (D192) |
| 5 | Mixing (§2.5) | Ideal; regular (pairwise); general excess functions | **Ideal and regular** in OL1. Others are later providers |
| 6 | Templating (§2.6) | Now; after oligomers; never | **After oligomers,** if the user chooses it (U5) |
| 7 | Energy (§3) | Chemostats; activated monomers and fuel; schedules; shear; light | **The first four.** Light later. Unsourced driven laws refused |
| 8 | Division (§4.3) | Size threshold; geometry plus shear events; spontaneous budding; resolved shape mechanics | **Geometry plus shear,** with k ≥ 2 daughters. The size threshold is kept for GARD |
| 9 | Selection (§5.2) | Moran replacement; a finite shared pool; serial transfer | **A finite pool and serial transfer.** Moran only for comparisons |
| 10 | Verification (§7) | Kernel and closed-world proofs; the GARD limit; experimental anchors | **All three.** A1 and A4 judged; A2 reported until §7.4's question is settled (D138, U6) |

### 0.2a The lead's rulings for OL1 (17 November 2026; D215)

Three physical choices, ruled from this note and D199, not settled between the builder and the
references. Both sides cite this subsection.
- **Kinetics by phase.**
  - Steps inside an assembly (a condensed phase) use counts on m: activities drawn without replacement,
    with the extent evaluated on m (`membrane_kinetics: count_on_m`). An assembly has no volume until
    OL2.
  - Steps in a dilute phase (the pool or the lumen) are mass action scaled by physical volume (R1).
  - OL2 adds the membrane's geometry as new token values. Existing values keep their meaning.
- **The last molecule.** `last_molecule: extinct` covers a step in either direction whose result
  empties the assembly. Its rate is the pair rule at the boundary, in its **cancelled** form.
  - Written through F, with F(empty) = 0, the factor E(m) is zero, so a literal product would give
    zero and the last molecule would never leave.
  - Written on the leaving side, the rule is 0/0. Cancelling E(m)/ff(N−1, r) to 1/ff(N−1, r−1)
    gives exactly G1's k⁻ for the last leave. A forward step that empties the assembly takes the
    same cancelled form.
  - A zero last-leave rate is therefore an error. There is no separate boundary formula.
  - `kept` and `reversible` are as their tokens declare.
  - (Amended the same evening, after a reading showed the literal form gives zero.)
- **The empty common state** (amended the same evening, before any engine output was handed over).
  - **Wherever the membrane factor is 0/0,** the cancelled form applies, under every `last_molecule`
    token. That is the case when a step's common state m has an empty membrane while neither end
    state does: a lone molecule changing form, or two joining.
  - **It is the factor's continuous extension,** so detailed balance holds as for every other pair.
  - **`last_molecule: kept`** gives rate zero only to a pair whose step changes the membrane's count
    and one of whose end states has an empty membrane. That way the membrane never empties, and
    nothing else is frozen.
    - A step in which the membrane takes no part fires at its own rate under every token. A pool
      step at a probe state with an empty membrane fires at the pool's mass action.
    - (Reworded 18 November 2026 by the lead, at OL5's reading. The earlier wording, "a pair one of
      whose end states has an empty membrane", read literally, also zeroed those pool steps.)
  - **This replaces the earlier wording,** "a pair whose common state has an empty membrane has rate
    0", which froze a lone molecule's reactions for no physical reason.
- **The catalysing phase.** In OL1 only the assembly's condensed phase catalyses. A dilute catalysing
  phase is refused until a declared meaning exists, since its fraction would have to include the
  solvent.
  - **A catalysed step touches the membrane** (the lead's ruling of 20 November 2026). A factor on a
    step that lies wholly in the pool or wholly in the lumen is refused until a meaning is declared.
    A single lineage would scale such a step by the membrane's fractions, while a population
    evaluates the pool's steps at an empty vesicle, where g = 1. No registered world is affected:
    the one refusal world that declares such a factor is refused earlier, for its dilute catalysing
    phase.
- **The measure** (D215, which amends U6(a)):
  - the GARD limit uses `multinomial_less_one` with `extinct`, which reproduces G1's rates exactly;
  - physical worlds use `multinomial` with `kept`.

  The line "G1's ideal-mixing exchange is its first instance" holds only with G1's ln N term.

### 0.2b The lead's rulings for OL2 and OL3 (17 November 2026; reviewed with the advisor)

The lead names each key and value here, so that neither side's draft leads. These rulings follow §2.5,
§4, §5.2 and D199.

1. **The exchange encounter: `exchange_encounter`, with no default.**
   - Its values:
     - `insertion_area`: extent k_ins·A(m);
     - `diffusion_radius`: extent 4πD_i·R(m).
     - (18 November: with ρ0 and the units, §0.2d item 2.)
   - Each world declares one. An anchor's choice belongs to its OL7 protocol. (18 November: each
     world that declares a geometry, §0.2c rule 1.)
   - **A(m)** = Σ_i n_i(m)·a_L,i/2 over every member of the membrane phase. A membrane species
     without a declared a_L is refused at parse.
   - **R(m)** = (A(m)/4π)^(1/2), the area-equivalent radius. For a floppy vesicle (v < 1) this is a
     declared approximation.
   - **Steps inside the membrane** keep `membrane_kinetics: count_on_m` in OL2's first worlds.
2. **The lumen, a dilute phase.**
   - **Kinetic factors** (extents, and the activity normalisations ff/X^α) are evaluated on the
     pair's common state m, with V(m) = min(V_osm(m), V_sph(A(m))).
   - **ΔF is exact** between the two end states.
   - **Admissibility** (lysis, rule 3; the floor, rule 4) is tested on the two end states, never on
     m.
   - **An empty lumen at m** takes the cancelled form, as in §0.2a. (18 November: a step whose rate
     on m is +inf there, rather than 0/0, is refused, §0.2c rule 7.)
   - **N_imp** counts the declared impermeant solutes in the lumen. (Superseded 18 November by §0.2c
     rule 6: N_L counts every lumen species, and c_ext includes the pool's solutes. That gives the
     same volume at permeation equilibrium, and V(n) minimises F.)
   - **c_ext,** the outside osmolarity, is held (declared constant) in OL2's first worlds. A world
     that makes it follow a finite pool recomputes it at every pool event, so every assembly's F
     updates. That is declared and costed.
   - **The claims the references check** are cycle closure and the exact-F identity
     (a⁻/a⁺ = e^(ΔF − w)). "The reverse equals the products' rule" is not claimed, because V moves.
3. **Lysis is an ending with a recorded reason,** not a silent zero rate.
   - An event whose end state takes a vesicle beyond its declared maximal tension σ_max fires and
     ends the life with reason `lysed`.
   - Its lumen contents and its membrane molecules return to the pool, with the release booked as
     heat. Resealing fragments come later. (18 November: the closure cost is released too, and the
     molecules return as monomers to their pool places, §0.2c rule 8.)
   - **A daughter born beyond σ_max** (the lumen's split can make one tense) lyses at birth, and that
     is recorded.
   - **Stationarity references** use worlds that cannot reach lysis.
   - **The tension** is σ = max(0, Δp·R/2), which is continuous and zero at the kink V_osm = V_sph,
     since Δp = 0 there.
4. **The vesicle floor: `vesicle_floor`, declared per world.**
   - The value of N_floor is unsourced and marked so. It is not in this note. (18 November: the
     floor counts area, in quanta, §0.2c rule 5.)
   - A step whose end state is below the floor has rate zero. That is a declared truncation of the
     state space, and it stays reversible. (18 November: only a step that changes the membrane's
     area, §0.2c rule 5.)
   - A division is admitted only if every daughter is at or above the floor.
   - **The closure cost** 8πκ + 4πκ̄ is constant per vesicle, so it enters no exchange rate, only a
     division's ΔF. Its value is declared per world and unsourced. (18 November: and lysis's,
     §0.2c rule 8.)
   - No micelle or droplet term enters OL2's first worlds.
5. **Selection order** is a numerical convention, ruled only as a requirement.
   - Each bundle declares its fold order (the pool's reactions, the assemblies, the channels) and its
     map from uniform numbers to events. The oracle replays from that declaration.
   - §5.2's two-level selection (an assembly by its total rate, then a channel within it) is exact in
     distribution.
   - After a fission, slot order and key order differ, so the declaration says which one is used.
6. **Permeation:** a step between the pool and the lumen, with locus `membrane`.
   - Its encounter is `permeation_area`, with extent P_i·A(m).
   - Its activities are the pool's, by the pool's volume, and the lumen's, by V(m) (rule 2).
     (18 November: an entry's θ⁺ is the pool's activity alone, and the lumen enters only through F,
     §0.2c rule 2 and §0.2d item 4.)
7. **The membrane split at unequal areas per molecule is held for OL3's design check.** Any rule
   must:
   - sum the daughters' areas exactly to the parent's;
   - reduce exactly to the multivariate hypergeometric when every a_L is equal (18 November: on the
     balanced size vector, assigned to the daughters in a random order, §0.2c rule 9);
   - treat the daughters as exchangeable, so that no daughter is favoured by filling order.

   The lumen's split must conserve its contents and treat the daughters as exchangeable.
8. **The singular rate** under `condensed_measure: multinomial_less_one` (a step with a membrane
   place on both sides, which is +inf at N = r) is admitted only in a world whose declared role is a
   probe (`world_role: probe`). There the probe reports +inf. Any other world declaring such a step is
   refused at parse.
   - `world_role` is optional, and `probe` is its only value. A world without it is an ordinary world.
   - A probe world may still be run. A run that reaches N = r stops `stalled`.
   - **"A membrane place on both sides"** means that one and the same membrane species is among both
     the step's reactants and its products, as the membrane catalyst E is in A + B + E → C + E
     (confirmed 18 November 2026 by the lead, at OL5's reading).
     - Under `multinomial_less_one` the draw's denominator, ff(N − 1, r), vanishes only at N = r,
       where every membrane molecule is drawn.
     - Only a step that returns a drawn membrane species keeps a molecule in the common state m
       there. The extent on m is then positive, and the rate is +inf.
     - A step whose membrane species differ between its sides leaves m's membrane empty at N = r.
       That is §0.2a's 0/0, which takes the cancelled form.

### 0.2c The lead's rulings on OL2's and OL3's design check (18 November 2026)

These answer questions Q1–Q21 of the builder's design check, `docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md`.
It is on branch `ol2-design-check` at 96070878 and lands after its amendment to these rulings. Both
sides cite this subsection, never the check note. §0.2b carries dated pointers to the rules here
that refine it.

**Keys and worlds**
1. **Conditional keys (Q1).** A world that declares a geometry declares `exchange_encounter`, and a
   world without a geometry may not. Every new key is absent unless its feature is declared, and an
   absent key is never written. So OL1's world ids and fingerprints do not move.
2. **Directions (Q5).** Phase exchange is declared only as a join (pool to membrane), and
   permeation only as an entry (pool to lumen). Each moves one molecule of one species. θ⁺ is then
   the pool's activity, and each reverse comes from F.
3. **Steps in a world that declares a geometry (Q6, Q7):**
   - `cells.stochastic_mass_action@1` with `count_on_m` is admitted only on steps whose places all
     lie in the membrane;
   - a cross-phase step takes a geometric encounter law: phase exchange for a join, permeation for
     an entry;
   - a join from the lumen, an interfacial reaction and a pool-to-lumen reaction are refused until
     a geometric encounter is declared for them.
   - **Amended 20 November 2026 (§0.2f):** one interfacial shape is admitted, a pool molecule
     binding a declared site to form its declared complex.
   - **Amended 23 November 2026 (FR-46, D323; §0.2f item 6):** a second shape is admitted, in a
     prescribed shell only. A lumen molecule binds a declared inner site. Each pair binds on its own
     face, one face per complex, and a wall that joins the two faces is a carrier, refused.

   Worlds without a geometry keep `count_on_m` on every membrane-locus step. That covers OL1's
   worlds, the probes and the GARD limit.
4. **Areas in integer quanta (Q9).** Each species' area per molecule per leaflet is k_i·q, with k_i
   an integer and q a declared quantum. The rounding of its sourced area to q is declared.
   W(n) = Σ_i n_i k_i counts the molecules' footprints in quanta, and the bilayer's area is
   A = q·W/2, rule 1's A(m). The floor, the cuts and conservation are in W, so all are exact
   integers. (Wording corrected 18 November, at OL5's question: W is not the bilayer's area.)
5. **The floor counts area (Q8).** `vesicle_floor` is required with a geometry and is given in
   quanta, with W_floor ≥ 1, not in molecules. It stands for the smallest closed vesicle, which is a
   geometric limit.
   - It requires `last_molecule: kept`.
   - A pair whose step changes the membrane's area, and one of whose end states is below the floor,
     has rate 0. The test is on the end states. A step that leaves the membrane's area unchanged
     fires at its own rate. That covers a pool step, a lumen step, or an entry, at a probe state
     below the floor.
   - A division is admitted only if every daughter is at or above the floor.

**The lumen**
6. **N_L and c_ext (Q2, Q20).**
   - **N_L counts every lumen species,** permeating ones included. Each is an ideal solute in the
     lumen, and only then is V(n) F's minimiser.
   - **c_ext is the outside's total osmolarity:** every pool solute, the permeating ones at their
     declared concentrations, plus the implicit buffer. It is held.
     - A world is refused if its c_ext is below its declared pool solutes' total. The same check
       applies to every serial transfer's fresh pool.
     - At permeation equilibrium the permeating solutes' terms then cancel inside and out. V(n) is
       the van 't Hoff volume of the impermeants, as rule 2 intended.
   - **Exactness.** It is exact for held pool species. For a finite pool it is a declared
     approximation, since the pool's volume is not tracked. The run reports the largest relative
     drift of the pool's solute osmolarity against c_ext.
7. **The empty lumen at m (Q3, Q4).** Under `lumen_volume: osmotic`, parse refuses every step whose
   rate on m is +inf at an empty lumen (1/0, not rule 2's 0/0):
   - a lumen-locus step with two or more lumen reactant molecules;
   - a membrane-locus step with a lumen reactant.

   OL2 needs neither. The question reopens with lumen chemistry (OL4, OL8), and Q4's reading is moot
   until then.
8. **Lysis (Q10).**
   - **The closure cost.** Lysis ends a vesicle, so its closure cost is released with it. Rule 4's
     "only a division's ΔF" extends to every change in the number of vesicles: the cost is added for
     each daughter beyond the first, and released at lysis.
   - **Where the molecules go.** The membrane's and the lumen's molecules return to their pool places
     as monomers of their own species. So in a world that can lyse, every membrane and lumen species
     has a pool place.
   - **The threshold.** Lysis is strict, at σ > σ_max. σ_max is required under `osmotic`, with its
     source. A founder beyond σ_max is refused.
   - **The relations format.** `lysed` is a requirement for the next relations version, which OL2
     adds, with tissue division's rows unchanged. No substitute end reason is ever written.

**Division (OL3)**
9. **The membrane split (Q11; rule 7).**
   - **The reading of rule 7's second property.** At equal areas, the split is the multivariate
     hypergeometric on the balanced size vector, assigned to the daughters in a uniformly random
     order. In that vector, N mod k daughters take ⌈N/k⌉ molecules and the rest take ⌊N/k⌋. For
     example, at N = 5 and k = 3 the sizes are 2, 2 and 1; G1's floor-to-first gives 1, 1 and 3.
     Equal target areas mean the most even split. G1's floor-to-first stays for D1 and the GARD
     limit.
   - **The rule is C3x.** The builder's exact probe confirmed it the same day. C3x matches the
     reading above with total variation 0 in all six equal-weight cases, including N = 5 and N = 8
     at k = 3. It stays exchangeable in the two unequal cases with N mod k = 2. G1's sizes, in
     either order, fail the reading there.
   - **C3x, exactly.** All its uniforms are drawn from the parent's fission draws (domain 2), in this
     order:
     1. List the parent's membrane molecules by species, in the world's declared species order.
        Draw one uniform per molecule, in list order. Rank the molecules by their uniforms,
        ascending, breaking ties by list position.
     2. Let S_c be the summed k_i of the first c ranked molecules, so that S_0 = 0 and S_N = W.
     3. Set c_0 = 0 and c_k = N. For t = 1, …, k − 1, c_t is the smallest c ≥ c_(t−1) that
        minimises |k·S_c − t·W|.
     4. Block t is ranked molecules c_(t−1) + 1 to c_t.
     5. Draw k more uniforms, after the N. Their argsort, ascending with ties by index, is π, and
        block t goes to daughter π(t).
   - **OL3's first worlds have equal target areas.** A declared size distribution is a later token
     value.
10. **The lumen split (Q12).** The weights are p_j = V_sph(A_j)/Σ_l V_sph(A_l).
    - Each daughter takes the same fill fraction of its sphere, so the parent's contents split at
      uniform concentration.
    - Each lumen molecule goes to daughter j with probability p_j, a multinomial. The uniforms come
      after C3x's: one per lumen molecule, listed by species in declared order.
    - A molecule with uniform u goes to daughter π(t) for the smallest t with u < Σ_(s ≤ t) p_π(s).
      The last cumulative weight is taken as 1.
11. **D2's k is declared per schedule (Q13).** The largest admissible k, ⌊v^(−2)⌋ up to a cap, waits
    for OL7's protocol (A4) as a new token value.
12. **Shear events (Q14)** act on every admissible assembly, in slot order. A fission refused at the
    floor is recorded and the parent kept. The partition's counter counts attempts.
13. **A full set of slots (Q15)** stops the run `slots_full` before the split. No daughter is ever
    dropped.
14. **Streams (Q16, Q21).**
    - The shared pool's selection map takes three uniforms per event from the `world` domain (5).
      Its groups are in slot order: the pool, then slots 0 to K − 1.
    - Shear times and the transfer's sampling take a new `schedule` domain (6).

**Interfaces, ownership and labels**
15. **IDs (Q17).** Two new interfaces, each with its first implementation:
    - `cells.population_structure@1`, with `cells.shared_pool@1`;
    - `cells.assembly_geometry@1`, with `cells.bilayer_geometry@1`.

    `cells.membrane_permeation@1` is confirmed, as are §8's other IDs.
16. **@1's files (Q18).** The OL2/OL3 builder owns @1's `runner.py`, `records.py`, `fission.py`,
    `continuation.py` and `keys.py` for OL3's shared loop (D215).
    - It edits them only behind @1's invariance gate:
      - the freeze test;
      - the part-1 references;
      - @1's probe set, re-run and compared: arrays bitwise, JSON equal but for provenance;
      - G2's ten rows.
    - The probe-set comparison moves into the checkout with OL2's invariance gate.
    - No exemption widens by default. Any widening is a listed amendment at OL3, with a reason per
      field, ruled by the lead after the demo (D215).
17. **Labels come in OL3 (Q19),** as @2's instance of RELATIONSHIPS_DESIGN §2.
    - They are state beside the counts, and no law reads them.
    - They move by draws on the `label` domain (4).
    - Totals are conserved per label.
    - With tracking off, every array is bitwise the same.

### 0.2d The lead's rulings on OL5's questions for OL2's and OL3's references (18 November 2026)

1. **Area (Q1).** A = q·W/2, as §0.2c rule 4 now reads. The floor W_floor and C3x's cuts are in W.
2. **Encounter rates (Q2).** The forward rate of a join or an entry is a⁺ = k·E(m)·ρ0·θ⁺(n), times
   any declared factor on m.
   - ρ0 = N_A·c0, in molecules per m³ (c0 in mol/L, times 10³ L/m³).
   - The constant k and the extent E(m) depend on the encounter token:

     | Token | k | E(m) |
     | --- | --- | --- |
     | `insertion_area` | k_ins, in m/s | A(m), in m² |
     | `diffusion_radius` | D_i, in m²/s | 4πR(m), in m |
     | `permeation_area` | P_i, in m/s | A(m), in m² |

   - θ⁺ is the pool's activity: n/X_pool for a finite place, c/c0 for a held one. So ρ0·θ⁺ is the
     pool's number density.
   - No constant absorbs c0; c0 enters through ρ0 alone.
3. **The lumen's F (Q3).** Confirmed:
   - F_lumen(n) = Σ_s [n_s(μ°_s − ln X_L) + ln n_s!] + N_A·c_ext·V(n), with X_L = N_A·c0·V(n);
   - V is in L, c0 and c_ext in mol/L, and μ°_s is the species' standard potential in solution, in
     k_BT;
   - V(n) = min(V_osm(n), V_sph(A(n))), with V_osm = N_L/(N_A·c_ext). V_sph(A) = A^(3/2)/(6√π)
     comes out in m³ from A in m², and is converted to L (times 10³) before the minimum;
   - at an empty lumen V(n) = 0 and F_lumen = 0.
4. **An entry's forward rate (Q4).** Confirmed: θ⁺ is the pool's activity alone. The lumen enters an
   entry only through F, and its reverse, the exit, comes from the exact ΔF.
5. **The two-level map (Q5).** Confirmed, with the guard:
   - τ = −ln(u1)/a0, under OL1's convention for the time uniform;
   - the group is the first, in slot order (the pool, then slots 0 to K − 1), whose running total
     exceeds min(u2·a0, nextafter(a0, 0));
   - the channel is the first, in the group's declared order (forwards, then reverses), whose running
     total exceeds min(u3·a_g, nextafter(a_g, 0));
   - every total is a serial fold in those orders.
6. **Serial transfer and shear times (Q6).** The builder confirmed the draw maps and the schedule
   streams against G1's stream layout the same day, so they are no longer provisional.
   - A schedule's declared index is the carrier word in domain 6, and nothing else draws there.
   - Each uniform of the transfer, and each Poisson gap, is its own draw: a block of one, with its
     own counter.
   - **The transfer** draws one uniform per living assembly, in slot order, and keeps the K_keep
     smallest, with ties broken by slot. That is a uniform sample without replacement.
     - It draws even when every assembly is kept, so every transfer advances its counter by the
       number living.
   - **Slots.** Kept assemblies keep their slots. A removed one's slot becomes free, and later
     daughters take free slots in slot order.
   - **Shear times** are declared, or drawn as a Poisson process of declared rate λ. The gaps are
     −ln(u)/λ from successive uniforms, under the time uniform's convention. Both forms are replayed
     bitwise.
   - **Streams.** Each schedule draws on the `schedule` domain (6) under its own key, its declared
     index, with the counter at its own draw count. So schedules never interleave.
   - **The clock at a declared time (ruled).**
     - The `world` draw's counter counts draws, not events.
     - A draw whose time crosses the next declared schedule time is discarded. The clock moves to
       that time, the scheduled event applies, and the next draw takes the next counter.
     - The exponential's memorylessness makes this exact. Re-reading a discarded draw would bias
       τ.
     - Without a schedule, draws and events coincide, so OL1's worlds and every schedule-free world
       are unchanged.
     - The followed assembly's own event stream in a single-lineage world (domain 1, OL1's `age`
       counter) follows the same rule when the world has a schedule.
7. **Booking (Q7).**
   - **Shear.** F carries the closure cost C_close = 8πκ + 4πκ̄ once per living vesicle (§0.2c rule
     8). The shear work is therefore w_shear = Σ_j F(daughter_j) − F(parent), which already holds
     (k − 1)·C_close; it is not added again.
     - The fission is booked as §4.4 books it: as work from the shear's source.
     - That the fission's own dissipation is not modelled is a declared limit (the lead's).
   - **Lysis writes one ledger row per lysing event:** the triggering step and the release
     together.
     - The release moves the lysed vesicle's molecules to their pool places and drops its closure
       cost, so its F terms become the pool's.
     - The row books q = −(F(n_after) − F(n)) + w. Here n is the state before the event, and
       n_after the state after the release.
     - w is the event's booked work: the step's own, plus the reservoir work for any held place that
       receives molecules, as for any step that produces into a held place.
8. **Labels** stay out of the references for now. The engine's own tests carry their conservation
   and tracking-off claims (§0.2c rule 17). A references row joins if a law for label draws is
   claimed.
9. **Partitionable threefry (the builder's addition).** A block draw gives the same values at any
   block size only when JAX's threefry is partitionable. Examples are a partition's uniforms (rules
   9 and 10 of §0.2c) and OL1's two per event.
   - The pinned JAX has the flag on by default.
   - The family refuses to start a run with the flag off.
   - The run's environment record states the flag.
   - No world's identity or records change, and the invariance comparison already exempts the
     environment record.
10. **Replay conventions.** These are OL5's seven readings, which the builder confirmed against its
    design the same day. They bind the engine and the references alike.
    1. **Which assemblies a shear event acts on.**
       - The set is fixed when the event begins: the assemblies alive at its start, processed in slot
         order. Daughters born during the event are not tested again in it.
       - Two scheduled events at the same time apply in order of their schedule index, each to the
          assemblies alive at its own start.
       - A declared time equal to t_end applies. One later than t_end never does.
    2. **An attempt runs in this order:**
       1. the stress test, then v ≤ k^(−1/2);
       2. in population mode, k − 1 free slots, or else the run stops `slots_full`;
       3. the draw: rule 9's uniforms, then rule 10's;
       4. the split and the floor test;
       5. the fission is applied, or refused and recorded with the parent kept.

       The fission counter counts draws. An assembly that fails the stress or the v test neither
       draws nor advances its counter.
    3. **A daughter that lyses at birth.**
       - Every daughter counts as born, both for the shear work (its F at its own V, with its closure
         cost) and for keys.
       - Each takes its slot before any lysis at birth. A birth lysis then frees the slot.
       - The birth lysis is booked as a lysis: one row, q = −(F(after release) − F(as born)) + w.
    4. **The first Poisson shear time** is t₁ = −ln(u₀)/λ, measured from t = 0.
    5. **A diagnostic record,** absent by default.
       - It records every draw: its address (domain, key, counter), its uniforms and its fate. That
         includes discarded draws, the draw that ends the run, a Poisson gap past t_end, every
         transfer uniform, and each partition block's used prefix.
       - It also records each event's changes, and its ledger terms by payer.
       - OL1's `event_uniforms` keeps its meaning: committed events only.
    6. **Every counter starts at 0:**
       - the world counter (domain 5);
       - each assembly's event counter, at its birth (domain 1, in single-lineage worlds);
       - each parent's fission counter (domain 2);
       - each schedule's counter (domain 6).

       A new sub-lineage's starting key counter follows the relations rule, s′·2³² + 1 with s′
       assigned in world event order. It is read from the `lives` table.
    7. **A group's channels** are its declared steps forward, then the same steps reverse, as in
       OL1.
       - A step with any membrane or lumen place belongs to every slot's group.
       - A pool-locus step belongs to the pool group.

    **What the record carries.** Every single-lineage attempt records the daughter it follows: G1's
    `fission_followed`, generalised to k. A missing field is a replay error; the replay never
    assumes daughter 0.

### 0.2e The lead's rulings for OL2's remaining milestones and OL3 (19 November 2026)

These answer the builder's status note of 19 November, after D230 resumed the work. OL5's pinned
export of the registered OL2 and OL3 inputs, made at main e8759b48, showed what its worlds carry.

1. **What OL2's first milestone is.** ol2-engine 9190ae78 holds `cells.bilayer_geometry@1` (the
   first `cells.assembly_geometry@1`), `cells.phase_exchange@1` and `cells.membrane_permeation@1`,
   with §0.2c rule 5's floor and the refusals of rules 2, 3 and 5. A world with a geometry runs with
   a declared lumen only. It is development: it is not yet compared against OL5's references, which
   need the probe roles (item 2, step 4).
   - Still OL2's: the osmotic lumen (σ, σ_max, and c_ext as the total) and lysis; the shared pool;
     the relations version with `lysed`; the diagnostic record; and §0.2d item 9's refusal.
2. **The order,** on one branch, `ol3-engine`. Each landing-ready head is named by its milestone,
   and its landing says whether it was compared against OL5's references or is development only.
   1. OL2 milestone 2: the osmotic lumen and lysis. Division needs them: each daughter's own
      volume, the v test, the lumen's terms in the shear work, and lysis at birth.
   2. OL3 milestone 1: single-lineage division.
   3. OL2 milestone 3: the shared pool and serial transfer, labels, the diagnostic record and
      §0.2d item 9.
   4. OL5's probe roles, from the export.
3. **Every declared physical value carries its provenance.** A value without a source says so: its
   provenance begins "unsourced". The registered-inputs mapper copies a registered world's own source
   text where it has one, and otherwise writes "unsourced; registered OL5 world <id>".
4. **The floor** is `vesicle_floor = {quanta, provenance}`, with quanta an integer ≥ 1.
5. **Areas.** The world declares `area_quantum_m2`, and each species `area_per_leaflet = {quanta,
   provenance}`, with `sourced_m2` and `source` optional and given together.
   - With a sourced area, §0.2c rule 4's rounding is the nearest quantum: |k − sourced_m2/q| ≤ ½,
     and either integer is accepted at a tie.
   - Without one, k is declared directly and no rounding check applies. A mapper never invents a
     sourced area.
6. **The closure cost.** The engine accepts the bending moduli κ and κ̄ and computes the closed
   sphere's closure cost, 8πκ + 4πκ̄ in k_BT, by its declared law, recorded in the footprint. A
   directly declared `closure_cost_kT = {value, provenance}` stays allowed. A mapper maps fields
   and computes no physics.
7. **The rate keys** are `insertion_velocity_m_per_s`, `diffusivity_m2_per_s` and
   `permeability_m_per_s`, each with its provenance.
8. **Rule 16's widened exemption, accepted after the fact.** validation/assembly_lineages/
   compare_probes.py exempts `^files\..*\.json$`: roles.json's checksums of JSON files.
   - The reason, for each such field: the file it checksums is compared leaf by leaf, so its
     checksum adds nothing. Array checksums stay compared.
   - The demonstration: at main e8759b48 the frozen tool's only differences were exactly these 47
     checksums, and @1's 625 exempted paths are the same under both tools.
   - It shipped in OL2 milestone 1 on 18 November, so it is recorded there as rule 16's listed
     amendment. Before that milestone lands, the lead checks that each of the 47 files is in the
     tool's leaf-compared set.

### 0.2f The lead's rulings for FR-21's site step (20 November 2026; D244, D246)

The user delegated FR questions to the lead (D244). The lead decided these with the advisor; they
are not the user's approval.

1. **Rule 3 of §0.2c is amended** to admit exactly one interfacial shape, one-step site binding:
   X@pool + site@membrane -> complex@membrane.
   - It is admitted under the existing `cells.stochastic_mass_action@1` with `count_on_m`. No new
     law is added.
   - Its encounter is the site count, since the law's membrane factor cancels to n_site. So
     a⁺ = k_f·θ⁺·n_site, and a⁻ = k_f·exp(Σνμ°)·n_complex, its reverse from F.
   - The world declares the pair, `"sites": [{"site": ..., "complex": ...}]`: both are membrane
     species, distinct, and a complex belongs to one site.
2. **Admission is keyed on the declaration** (D246), never on stoichiometry alone.
   - The step must be declared in the binding direction: one pool molecule and the declared site
     form the site's declared complex.
   - Still refused:
     - an undeclared pair;
     - a binding of two ligands;
     - a ligand in the lumen, except on a declared inner pair in a prescribed shell (item 6, FR-46);
     - the step declared as the release;
     - every other interfacial step, as before.
   - **OL5's registered refusal worlds stay refused.** `refuse_count_on_m_cross_phase` has the
     shape but declares no site or complex.
3. **On a bilayer, sites and complexes take area,** as every membrane species does. The shell's
   own geometry, where sites set nothing, comes after this step lands.
4. **Not yet settled:**
   - **OL5's reference parser,** `refusals2.validate` in `validation/ool/references/`, refuses every
     cross-phase step under a geometry. It needs OL5's own amendment before an FR-21 world can be
     registered. That is OL5's work, later.
   - **k_f's provenance.** FR-21's note says k_f carries its provenance (§0.2e item 3). The
     mass-action law's rate key is a bare number, so where the provenance lives is a world-format
     question for the lead before a world is registered.
5. **The acceptance** is the requester's, relayed on 20 November 2026. It is a test in
   `tests/unit/test_assembly_lineages_v2_replacement.py`:
   - on the one-particle fixture, a bound ligand stays through FR-20's wash;
   - a released one rebinds.

6. **The inner face** (FR-46; the user's rulings of 23 November 2026, D323):
   - **A pair may declare its face,** `"face": "outer"` (the default, never written) or `"inner"`.
   - **An inner pair** admits X@lumen + site@membrane -> complex@membrane, in a prescribed shell
     only. It is under the same law with `count_on_m`; θ⁺ is the lumen's activity, and the reverse
     returns X to the lumen.
   - **A pair binds on its own face only.** An inner pair outside a prescribed shell is refused by
     name.
   - **One face per complex, by ligand moiety.** Each admitted binding seeds its complex with its
     face, for each moiety of its ligand. Every step, binding and release steps included, joins per
     moiety each membrane reactant that holds the moiety with each membrane product that holds it.
     A component holding both faces is a carrier across the wall, refused by name with its wall
     states.
   - **The cases refused:**
     - a direct conversion;
     - conversions through ligand-bearing wall states with no pair of their own;
     - a co-ligand bound from the other face onto a site that already holds the ligand (a
       reviewer's case).
   - **Accepted as a limitation of version 1:** stepwise binding of one ligand from both faces on
     one site is refused too, since the moieties cannot tell which molecule is which.
   - **In `cells.rate_equations@1`,** inner-face binding is refused by name.
   - **Rule 3's refusal message** names both shapes. Its recorded string in probes2, for OL5's
     `refuse_count_on_m_cross_phase`, is declared at the landing. All 22 registered refusals still
     refuse.

### 0.2g The lead's rulings for FR-21's prescribed shell (20 November 2026; D244, D246)

The design is [ASSEMBLY_SHELL_DESIGN.md](ASSEMBLY_SHELL_DESIGN.md) §4.2–§4.3, built to the
requester's acceptance (docs/FEATURE_REQUESTS.md, FR-21).

1. **`cells.prescribed_shell@1` is a geometry kind beside the bilayer.**
   - It declares `area_m2` (value, provenance), and its lumen is `lumen_volume: declared` with
     `phases.lumen.volume_L`.
   - The wall is the membrane phase, and its species carry no area quanta. So the wall's counts,
     binding sites included, set neither the area nor the lumen.
2. **It has its own entry law, `cells.shell_permeation@1`:** a⁺ = P_s·A_sh·ρ0·θ⁺, with the exit
   the same law applied to the products.
   - The extent is a constant of the world, so G_s = P_s·A_sh. The run reports G_s per permeant,
     in world.json's `derived.shell`.
   - `cells.membrane_permeation@1`'s text is unchanged (D147).
3. **The gate factor, `cells.gate_factor@1` (the note's G2).** Its fractions are over the gate's
   declared forms only: g = Σ m_j e^ΔΔG‡ / Σ m_j over the gate.
   - So the site count cannot dilute a gated entry, which the transition-state factor's
     whole-wall fractions would do.
   - It is evaluated on the common state m, as that factor is, so detailed balance is kept.
   - A gated shell is therefore built, not refused.
4. **A shell refuses,** at the parse and each with its reason:
   - a join (phase exchange);
   - the bilayer's permeation;
   - an osmotic lumen;
   - `exchange_encounter`;
   - the bilayer's keys: area quanta, a floor, a closure cost, a lysis tension;
   - a missing lumen;
   - division and shear.

   A bilayer refuses the shell's permeation.
5. **One shell type per world** in version 1, with its area and lumen as world constants.
   - Population mode admits it: a prescribed wall cannot empty.
   - FR-22's checkpoints carry over, since the state stays integer counts.
6. **Dispatch is static, by the geometry's ID,** so every bilayer and OL1 program traces as
   before. Every existing world stays bitwise, which the invariance gate checks.
7. **The run's verdict** on a shell world is the shell probe's (`balance.shell_verdict`). The other
   verdicts are unchanged, so no other run's record moves.

### 0.2h The lead's rulings for FR-35's pool withdrawal (21 November 2026; D261)

The design is [ASSEMBLY_WITHDRAWAL_DESIGN.md](ASSEMBLY_WITHDRAWAL_DESIGN.md), decided by the lead with
the advisor. It is built as `cells.pool_withdrawal@1`.
1. **A new operator.** `cells.pool_replacement@1` stays as registered. `fraction` on a replacement
   is refused, with a message that names the withdrawal kind.
2. **The draw:** each molecule leaves independently with probability f, in per-place blocks on
   the schedule's own stream at draw number w·P_f + j.
   - w is derived from FR-22's applied stops, so it is one number and the checkpoint gains no key.
   - The addresses are disjoint from a transfer's and a Poisson shear's, because each schedule's
     index is its own carrier word.
3. **The buffer:** integer counts in the withdrawn volume fV. Its concentration is checked against
   c_ext at parse, and the realized pool's drift is reported.
4. **Booking A:**
   - the sink takes F(before; V) − F(kept; (1 − f)V), recorded as `pool_loss_kT`. It differs from
     the sample's own F by the outcome's surprisal σ, which is recorded apart;
   - the work column takes F(buffer; fV);
   - the heat takes the mixing heat, which is never negative.

   The free energies at fV and (1 − f)V go through the guarded table read.
5. **Capacity:** the wash is refused before the draw when a place's pre-wash count plus its buffer
   count exceeds `molecule_capacity`, so no refusal depends on the draw.
6. **The legend entry** is written only when a world declares a withdrawal, so existing worlds stay
   bitwise.

### 0.3 Estimate, order and questions

- **The estimate** (§8): about 33–51 agent-days in ten milestones, plus 3–5 if templating is chosen.
  - The first results come after about 17–27: the laws, the physical assemblies, division, the
    GARD limit, the deterministic representation and the references they need.
  - Compute is CPU-hours. The L4 is optional, for the first experiment.
- **The order.** Code starts once G1's kernel, ledger and fission are on main and seam F's law
  registry exists. Until then the work is desk work: this note's discussion and the lead's answers
  to §6.3.
- **The cheapest moment for §6.3's kernel generality is during G1's build,** before its channel
  layout freezes.
- **Questions:** eight for the user (§9.1, marked), six for the lead (§9.2).

## 1. Entities and state

### 1.1 Options for the first entities

| Option | Entities | For | Against |
| --- | --- | --- | --- |
| E1 Abstract types | GARD's: assemblies of N_G types, a held reservoir, a matrix β | In G1 already | Phenomenological. No CAC, no geometry, no chemistry, and no energy source beyond the held bath |
| **E2 Amphiphile assemblies, lumped geometry** | Amphiphiles (fatty acids; a diacyl lipid), lumen solutes, a monomer pool, assemblies with a geometry kind (vesicle; micelle and droplet declared) | Physical growth, competition and division, with open experimental numbers (§7.4). Reuses G1's exchange, fission and lineage | Heredity is compositional only, as in GARD |
| E3 E2 plus oligomers | A declared binary-polymer family up to length L inside assemblies, made from activated monomers | Chemistry that stores and spends energy; catalysis tied to identities; autocatalytic-set theory as a reference | Species grow as 2^(L+1); it needs E2's assemblies first |
| E4 Spatial membranes | Shapes, meshes, mechanics | Real shape transitions and pearling | Mechanics the engine lacks (Syn3A's F12), at far higher cost |

**Recommended: E2, then E3** (OL8).
- Coacervate droplets are E2 with a droplet geometry kind, surface tension in place of bending.
  They are declared, but not in OL2's first acceptance.
- Micelles enter first as the feedstock: a packet of amphiphiles in the pool (§1.2).

### 1.2 Resolution

- **Counts.** Integers per species per assembly, advanced by G1's exact SSA.
- **Sequence.**
  - None in E2.
  - In E3, a declared family of all binary strings up to length L, in capacity buckets: 254
    species at L = 7, 510 at L = 8, 1,022 at L = 9. The count is (κ^(L+1) − κ)/(κ − 1) for an
    alphabet of κ (Hordijk, Kauffman and Steel 2011).
  - No species is ever created at run time, so shapes stay static.
- **Geometry.** Lumped, and algebraic in the counts (§4.1): area from the amphiphiles, lumen volume
  from the impermeant solutes (§0.2c rule 6), and from them the reduced volume and the tension.
  There are no positions and no shapes; those are E4.
- **Scale (S).**
  - **The problem.** A real 100 nm vesicle holds about 1.9 × 10⁵ amphiphiles, at an assumed
    0.3 nm² per molecule per leaflet. At an off rate of 0.1–1 s⁻¹, a minute of competition is
    10⁶–10⁷ exact events per vesicle.
  - **(a) Exact single-molecule events:** assemblies of up to about 10³–10⁴ molecules. That is
    GARD's scale.
  - **(b) Packets of q molecules per event,** with ΔF taken for the whole packet.
    - The thermodynamics stay exact: the same equilibrium and the same ledger.
    - The kinetics do not. A packet's reverse rate carries e^(−qΔF₁/k_BT), where ΔF₁ is the
      per-molecule drive. At A1's tension drive, 0.36 k_BT, and q = 100, that is e^(−36), so every
      packet step is effectively one-way. No constant rescaling of s matches the single-molecule
      flux both near and far from equilibrium.
    - So packets are rejected as a coarse-graining. They are physical only where the packet is a
      real species, such as a micelle fusing with a vesicle (Chen and Szostak 2004's feed). That
      is ordinary mass action with a micelle species, not a representation.
  - **(c) τ-leaping:** G1's later fast mode. It is approximate in time, and needs step control.
  - **(d) The deterministic limit of the same laws:** J = Σ s θ⁺ (1 − e^(ΔF/k_BT)) on continuous
    counts. That is the cycle kind's factored form (CORE_SEAMS_DESIGN §3.2), exact in the
    large-system limit (Kurtz 1972, from memory). It is valid only where every count is large.
  - **Recommended:** (a) for heredity experiments, and (d) as a declared representation for
    vesicle-scale anchors, qualified against (a) where both run (ARCHITECTURE.md, "Levels of
    detail"). The anchors' measured quantities are means over very many vesicles, so fluctuations
    do not enter them. (c) waits for a stochastic run at vesicle scale.

### 1.3 State and ownership

| Entity | State it owns | Layout (declared) |
| --- | --- | --- |
| **Assembly** | Integer counts per species in two compartments, membrane and lumen; its carrier key and event counter (G1's) | Geometry kind; area per molecule per amphiphile type; bending moduli or surface tension, with sources |
| **Pool** | Finite: counts per species, shared by the world's assemblies. Held: nothing | Its volume; the held activities of chemostatted species |
| **Species** | — | The registry: identity, standard potential per phase (solution, bilayer, droplet), moieties (seam E, CORE_SEAMS §7.3), and family declarations |
| **Reaction network** | — | Stoichiometry over species and phases; each law's s parameters; catalyst assignments as per-world data, as GARD's β is |
| **Lineage and world** | G1's | G1's |
| **Schedules** | Their event counters | Shear events, transfers (dilution, bottleneck) and steps in held activities |

**Never stored:** area, volume, reduced volume, tension and concentrations. They are functions of
the counts, so the event state stays integer. A continuous variable outside the counts would need a
numerical plan of its own (§6.3, R4).

## 2. Laws from physical chemistry

### 2.1 The event-pair contract

- **Mass-action θ.** For an elementary step with reactant coefficients α in volume V,
  θ⁺ = k (N_A V)^(1−r) ∏_s n_s!/(n_s − α_s)!. Here r = Σα is the step's order, and k is the
  macroscopic rate constant (Gillespie 1977, from memory). θ⁻ then follows from F.
  - For ideal dilute species, this recovers textbook reversible mass action, with
    k⁺/k⁻ = exp(−Σ ν μ°/k_BT) at the declared standard concentration (**S**, standard).
- **The split.** By default s carries the barrier, θ⁺ the reactants' encounter, and θ⁻ the
  thermodynamics. A law may declare a symmetric split instead. The choice is kinetic, and both are
  admissible.
- **The kernel.**
  - It computes each channel's ΔF incrementally: in O(1) for ideal terms, and in one row of work
    for regular mixing.
  - A check in G1's form (GARD_DESIGN §2.4, item 1) verifies ln(a⁺/a⁻) = −ΔF/k_BT on random
    states, to rounding.
- **The domain** is |ΔF/k_BT| ≤ 80 per event, as for the cycle kind. A strongly exergonic step
  keeps its reverse rate at the value detailed balance gives; it is negligible, but present.

### 2.2 One free-energy function

| Term | Form | Numbers from |
| --- | --- | --- |
| **Pool** | Σ_s n_s [μ°_s,sol + k_BT(ln(n_s/(N_A V_pool c0)) − 1)]. A held species has a fixed μ_s instead | Registry potentials; measured CACs give the transfer potentials (§2.5) |
| **Assembly, ideal mixing** | Σ_i n_i μ°_i,phase + k_BT Σ_i n_i ln(n_i/N), with N the assembly's total | Registry potentials per phase |
| **Assembly, regular mixing** (optional) | (k_BT/2N) Σ_ij χ_ij n_i n_j | Fitted or cited (A2) |
| **Geometry** | Vesicle: 8πκ + 4πκ̄ per closed vesicle, independent of size (Helfrich, from memory). Micelle: a surface term in N^(2/3) (Israelachvili, from memory). Droplet: γ 4πR² | κ, κ̄ and γ declared with sources |
| **Lumen** | Impermeant solutes ideal in V, plus c_ext k_BT V, with V from §4.1 | §4.1 |

- **Every term is a function of the counts.** So μ_i = ∂F/∂n_i is integrable, and rates from §2.1
  are consistent.
- **No law carries a ΔG° of its own.** That is the cycle kind's rule (CORE_SEAMS §3.2) and seam E's
  check (§7.1 there).

### 2.3 Mass action with registry potentials

**`cells.stochastic_mass_action@1`:**
- **Steps** may act inside an assembly, in the pool, or across the boundary.
- **Its rules are D152's:** at most three reactant molecules, integer coefficients, and moieties
  checked at parse (seam E).
- **It shares its declaration with D152's passive law,** `ideal_detailed_balance_mass_action@1`. One
  declaration then has two executions: deterministic on @3's nodes, and stochastic in assemblies.
  ARCHITECTURE.md ("Levels of detail") asks for exactly that: "Reaction declarations are reused
  where valid, but stochastic execution needs count-based propensities and its own qualification".

### 2.4 Catalysis that keeps detailed balance

**The physics** (transition-state theory, from memory):
- A catalyst lowers the transition state's free energy by ΔΔG‡. Both directions' rates rise by
  exp(ΔΔG‡/k_BT), and the equilibrium is unchanged.
- That is IUPAC's definition of a catalyst, as Blokhuis, Lacoste and Nghe 2020 cite it.

**Two admissible forms:**
- **(a) Explicit elementary steps.** The catalyst is written on both sides (E + S ⇌ E + P), or with
  intermediates (E + S ⇌ ES ⇌ EP ⇌ E + P).
  - Saturation (Michaelis–Menten) and the Haldane relation then emerge (**S**).
  - E1 shows the explicit autocatalytic step, A + B ⇌ 2B, exact.
- **(b) An effective factor on m:** s(m) = s0 g(m), for any g ≥ 0 of the common state.
  - For example, single-contact stabilisation in an ideal mixture (**S**):
    g = Σ_j x_j(m) e^(ΔΔG‡_ij/k_BT) = 1 + Σ_j β_ij x_j(m), with β_ij = e^(ΔΔG‡_ij/k_BT) − 1.
  - Inhibition is β_ij in [−1, 0), a destabilised transition state. A factor g ≤ 0 is refused.

**The case that discriminates** is a catalyst that is also a reactant or product of the step it
catalyses: autocatalysis, or GARD's kept diagonal.
- On m, the moving molecule never catalyses its own reverse step. That is GARD's pair-consistent
  form.
- In form (a), the catalyst cancels exactly from ΔG (D152 §2.2).
- **Refused:** a factor evaluated on each direction's own state (E1's planted form). GARD's published
  form keeps it, so that form lives only inside GARD's law set, as D192 decided.

**Catalyst assignments are per-world data,** as β is. Each is a sparse list of (catalyst, step,
ΔΔG‡). They are generated in `validation/` with a recorded seed and law. Three generators are
proposed:
- uniform random, as in the binary-polymer model of autocatalytic-set theory;
- template matching (Hordijk, Kauffman and Steel 2011's variant);
- GARD's lognormal.

**`cells.transition_state_factor@1`** is form (b). G1's pair-consistent `member_catalysis@1` is its
special case.

### 2.5 Exchange between phases: the CAC, tension and composition

**`cells.phase_exchange@1`.** A molecule of species i joins an assembly from the pool. The leave is
the reverse step, with its rate from F.
- **The join's s is the encounter:**
  - reaction-limited insertion is k_ins A, which is ∝ N for a bilayer;
  - diffusion-limited uptake is 4πD_i R (Smoluchowski, from memory), which is ∝ N^(1/2) for a
    vesicle and ∝ N^(1/3) for a droplet (**S**). (Units and ρ0: §0.2d item 2.)

**The CAC emerges from F.**
- For one amphiphile and a large ideal vesicle, the pool is at equilibrium at
  c_cac = c0 exp((μ°_bilayer − μ°_sol)/k_BT).
- So measured CACs calibrate the registry's transfer potentials (**S**, E3, from Zhu and Szostak
  2009's CACs, at c0 = 1 M):

  | Acid | CAC (as stated) | Transfer potential |
  | --- | --- | --- |
  | Oleic acid | ~80 µM | −9.43 k_BT |
  | Myristoleic acid | ~4 mM | −5.52 k_BT |
  | Decanoic acid | ~30 mM | −3.51 k_BT |

- **A check on those numbers (S).** The two monounsaturated acids differ by 0.98 k_BT per CH₂. The
  classical value is about 1 k_BT per CH₂ (Tanford, from memory). Decanoic acid is saturated, so
  it is not comparable.
- **The caution.** Fatty-acid CACs depend strongly on pH, and the source gives the conditions only
  as its buffer.

**The mixed aggregation threshold (S).** With ideal mixing, an assembly can coexist with pool
activities ρ_i only where Σ_i K_i ρ_i = 1. That is the multicomponent CAC. Above it, every assembly
grows.

**Tension (S).**
- When a vesicle's lumen is limited by its area (§4.1), each amphiphile's potential in the membrane
  falls by σ a_L/2.
- At oleate's maximal sustainable tension, about 10 dyn/cm (Chen, Roberts and Szostak 2004), that
  is about 0.36 k_BT per molecule, at the assumed a_L of 0.3 nm².
- It is small against the 9.4 k_BT transfer potential, but it is the whole drive of their
  competition (A1).
- It comes from F's lumen term. It is not a separate law.

**Composition (S).**
- An off rate that changes with composition, at an unchanged on rate, is a change in the
  potential.
- Budin and Szostak 2011 measured 22% slower oleate desorption from membranes with 10 mol% DOPA
  (A2). It has two readings, and the protocol must say which one the measurement supports:
  - **per oleate molecule:** an excess potential of k_BT ln(1/0.78) ≈ 0.25 k_BT;
  - **per area of membrane:** ideal dilution (x = 0.9) accounts for 10% of it, which leaves
    k_BT ln(0.9/0.78) ≈ 0.14 k_BT of excess. The paper names the smaller releasing surface as a
    separate effect.
- Either way it is a regular-mixing term, so by E2 it must be reciprocal: DOPA's own potential
  changes with the oleate content as well.

### 2.6 Templating: an option, after oligomers

- **The form (S).** Template-directed ligation as explicit steps, each keeping detailed balance:
  substrates bind the template with a declared hybridisation free energy, ligation's transition
  state is stabilised while they are bound, and the products dissociate.
- **What theory predicts** (from memory). Product inhibition through duplex stability gives
  parabolic, square-root growth, and so coexistence (von Kiedrowski; Szathmáry and Gladkih 1989).
  Exponential growth needs strand separation driven by a cycle, such as a temperature schedule
  booked as work.
- **Needs and gains.** It needs E3's sequences and a hybridisation model with cited parameters.
  Copying fidelity then meets its thermodynamic bound (Hopfield 1974, from memory).
- **Data.** The open template-copying kinetics found (Li et al. 2017) is under a non-commercial
  licence, so it is analysis only (D173) and no number is quoted. A judged anchor needs a
  permissive source.

### 2.7 GARD as a limit, assumption by assumption

| GARD's assumption | A limit of these laws? | Where it comes from, or what breaks (**S**) |
| --- | --- | --- |
| The rate law b_i (k_f ρ_i N − k_b n_i) | Yes | Phase exchange with reaction-limited insertion into a bilayer (join ∝ area ∝ N), a first-order leave, and ideal mixing |
| The factor 1 + Σ_j β_ij x_j, unsaturated | Yes | Single-contact transition-state stabilisation on m, with β_ij = e^(ΔΔG‡_ij/k_BT) − 1. Weak contacts do not saturate; catalysis limited by binding, through explicit complexes, does |
| Lognormal β = exp(−4 + 4Z) | As data only | Read as stabilisations (E3): a median of 0.018 k_BT; 1.4 at the 90th percentile; 5.3 at the 99th; 8.4 k_BT (21 kJ/mol) at the 99.9th. They are modest, and no chemistry ties β to identities |
| The published evaluation at each state | No | It fails detailed balance for generic β (GARD_DESIGN §2.5; E1). It stays only in GARD's law set |
| Catalysis never moves the equilibrium | Only under ideal mixing | Real membranes have composition-dependent potentials (A2). GARD cannot express that thermodynamic selection |
| A held reservoir with Σ K_i ρ_i = 100 | Yes | A chemostat at a supersaturation of 100 over the mixed aggregation threshold, ln 100 = 4.6 k_BT. Holding it costs reservoir work, which is booked. A finite pool depletes and couples the assemblies: competition, which a held reservoir excludes |
| No size-dependent free energy | Only with geometry dropped | Real assemblies have a CAC, and either preferred sizes (micelles) or a closure cost independent of size (vesicles) |
| Fission at N = 80, an exact half, the first daughter | Only as the limit of symmetric division | At fixed, equal daughter areas the membrane's split is multivariate hypergeometric, which is GARD's exact half. The lumen's split is multinomial by volume. Physical division needs a reduced volume v ≤ 2^(−1/2) and work (shear), and gives k ≥ 2 daughters of unequal size |
| A nominal clock | No | Physical units throughout: seconds, molar and k_BT at a declared temperature |

## 3. Energy

### 3.1 Sources

| Source | Declared as | Who pays | Booked as |
| --- | --- | --- | --- |
| **A chemostat** | A pool species whose activity is held (G1's held phase) | The reservoir | Reservoir work, Σ μ_s × the amount supplied (G1) |
| **Activated monomers, finite** | Species with high registry potentials, consumed by steps that release a leaving group | Their stored free energy | A fall in stored energy, with event heat. A moiety ledger keeps activated plus spent constant |
| **Activated monomers, held** | As above, with held activities | The reservoir | Reservoir work |
| **A fuel-to-waste cycle** | fuel + precursor ⇌ activated + waste, then activated ⇌ precursor. Every step keeps detailed balance with registry potentials | The fuel's Δμ against its waste | Stored energy or reservoir work. Anchor A5 |
| **Schedules:** dilution, serial transfer, steps in held activity; temperature later | Operator schedules | The experimenter | Schedule work: the free-energy change each step imposes, as the bath schedule books it |
| **Shear** | Shear events, at declared times or a declared rate, with a stress | The flow | Work equal to each fission's ΔF (§4.4) |
| **Light** | Photon absorption as an event with a declared photon potential | The lamp | Later |

### 3.2 Nothing runs uphill unpaid

- **No driven law without a source.** D152's driven class (irreversible mass action,
  Michaelis–Menten with a catalyst it only reads, Hill factors) is refused in this family.
  - A driven step is written with its fuel species, so it is passive in the extended network
    (**S**).
- **Every step's ΔG° comes from the registry,** by seam E's check, and conserves its moieties (seam
  E §7.3). Activation chemistry declares its moieties: monomer cores and leaving groups.
- **Fission and transfers are external operators.** Their ΔF is work by a named payer, the shear or
  the schedule, never "an unmodelled agent". G1's split booking gains a payer field.
- **A strongly exergonic step keeps its reverse rate** at the detailed-balance value (§2.1).

### 3.3 Ledgers

- **Per lineage and per world:** event heat, declared non-monotone (seam D); reservoir work;
  stored energy, for finite fuel and activated species; schedule work; shear work; and sinks, for
  unfollowed daughters and assemblies transferred out.
- **Closure (S).** At every saved row, F(n_t) − F(n_0) equals the works minus the heat minus the
  sinks' free energy, to rounding. This is GARD_DESIGN §2.4's closure, with these terms added.

## 4. Growth and division

### 4.1 The physical state, algebraic in the counts (S)

- **Area:** A = Σ_i n_i a_L,i/2 for a bilayer, where a_L,i is the area per molecule in one leaflet.
- **Lumen volume:** V = min(V_osm, V_sph(A)).
  - V_osm = N_imp/c_ext: the impermeant lumen solutes over the outside osmolarity. (18 November:
    the engine writes it as N_L/c_ext, with N_L over every lumen species and c_ext the outside's
    total osmolarity, §0.2c rule 6. At permeation equilibrium that gives this volume.)
  - V_sph(A) = A^(3/2)/(6√π), the sphere of that area.
  - Water is treated as fast. That is an assumption, to be checked against each anchor's time
    scale.
- **Reduced volume:** v = 6√π V/A^(3/2), at most 1.
- **Tension:**
  - It is zero while V_osm < V_sph(A): the vesicle is floppy, and v < 1.
  - At V_osm ≥ V_sph(A), the lumen term of F gives Laplace's σ = Δp R/2, with
    Δp = k_BT(N_imp/V − c_ext). (18 November: Δp = k_BT(N_L/V − c_ext), §0.2c rule 6.)
  - Beyond the maximal tension (about 10 dyn/cm for oleate) the vesicle lyses. Version 1 refuses
    the state; lysis as an event comes later. (17–18 November: lysis is an event in OL2, §0.2b
    rule 3 and §0.2c rule 8.)
- **Solutes:** permeant ones equilibrate and do not count. Slowly permeating ones are exchange
  channels, as glycine is in Zhu and Szostak 2009.

### 4.2 Growth mechanisms, all from F and the exchange law

- **A supersaturated pool, such as micelle feeding.** Area grows faster than volume when the lumen's
  solutes are impermeant, so v falls below 1: the filaments of A4. Permeant solutes keep v near 1,
  and the vesicles stay spheres.
- **Tension.** Swollen vesicles take amphiphiles from relaxed ones until σ reaches 0 (A1).
- **Composition.** A membrane where the amphiphile's potential is lower takes from the others (A2).
- **Synthesis.** Amphiphiles made inside from activated precursors: a reaction whose product is in
  the membrane phase. That is a later anchor.
- **Feedback from internal chemistry.** Polymers change the lumen's osmolarity (Chen, Roberts and
  Szostak 2004's argument). That arrives with E3.

### 4.3 Division: the options

| Option | Trigger | Physics | Status |
| --- | --- | --- | --- |
| D1 Size threshold (G1's `size_threshold_fission@1`) | N ≥ N_split | None; it is GARD's | Kept for GARD and the GARD limit |
| **D2 Geometric admissibility, at shear events** | At a shear event, an assembly with v ≤ k^(−1/2) may split into k daughters. Equal spheres need exactly that (**S**): k of them have k^(1/3) times one sphere's area, so the thresholds are 0.707, 0.577 and 0.5 for k = 2, 3 and 4 | Zhu and Szostak 2009: filaments divide under shear above a critical shear rate of about 15 s⁻¹ | **Recommended** (`cells.shear_fission@1`) |
| D3 Spontaneous budding | v ≤ 2^(−1/2), plus a criterion on spontaneous curvature | Helfrich-type shape theory (from memory) | Later; its parameters are not measured in the sources read |
| D4 Resolved shape mechanics (pearling, filaments) | From a shape model | E4 | With mechanics |

- **D2's stress threshold** is an admission test at the event.
- **Daughter sizes** are equal by default (k equal spheres), or drawn from a declared distribution.
  Their areas always sum exactly to the parent's.
- **`cells.serial_transfer@1`** samples a fixed number of assemblies into a fresh pool at declared
  times. It is the bottleneck of population runs.

### 4.4 Partition and booking

- **The split (S).** The membrane's composition at given daughter areas is multivariate
  hypergeometric; the lumen's contents are multinomial, with probabilities V_j/V; the pool is not
  touched. G1's stochastic partition kernel does both, with its streams and fission table,
  extended to k daughters and two compartments per assembly. (18 November: the membrane splits by
  C3x, §0.2c rule 9. The lumen's weights are V_sph(A_j)/Σ_l V_sph(A_l), §0.2c rule 10, because a
  daughter's V_j depends on its own split.)
- **The split's ΔF** is booked as shear work and reported per fission. It includes the closure cost
  of each new vesicle and the lumen's terms. The admission gate (v and stress) is kinetic, not
  energetic (**S**).
- **Continuation** is G1's `daughter_continuation@1` in single-lineage mode. In population mode
  every daughter lives, up to the slot capacity, and serial transfer is the bottleneck.
- **Reused from the engine's division:**
  - S5's lineage record shape, carrier keys and G1's slot reuse;
  - seam B's field roles: counts extensive, split by the stochastic rule; heat and work history;
    the geometry kind structural;
  - the partition's rule that the daughters' amounts sum exactly to the parent's, the second
    daughter taking the complement (S5 §3.3).
- **Not reused:** the anchor rule, since counts are integers, and the capacitor and electrical
  terms. Version 1's assemblies are neutral. Fatty-acid charge is a declared limit, to be revisited
  with charged amphiphiles.

## 5. Inheritance and selection

### 5.1 Measures

| Measure | Definition | Comparable with GARD | Where |
| --- | --- | --- | --- |
| **H**, boundary similarity | The cosine between the parent before fission and each daughter, over a declared species set | Yes: GARD's H when the set is every type | The engine: G1's on-device observer |
| **Inherited fraction and F12** | The programme's contract: H > 0.9 strictly; then a break followed by three inherited fissions within twelve | Yes | `validation/`, with G1's definitions in a neutral module |
| **Composomes and compotypes** | Markovitch and Krasnogor's definitions, with the clustering registered in advance | Yes | `validation/` |
| **Heritability of traits** | Parent–offspring regression of declared traits: composition axes, growth rate, interdivision time, tension (quantitative genetics, from memory) | New | `validation/` |
| **Selection** | Relative growth rate in a shared pool; the Price equation's selection and transmission terms in population runs (Price 1970, from memory) | Vasas et al.'s population layer | `validation/` |
| **The cost of heredity** | Heat and work per generation and per inherited boundary, in k_BT | GARD_DESIGN §8, item 5 | The engine's ledgers, then `validation/` |
| **Mechanism** | Whether the inherited composition holds an autocatalytic core: Blokhuis et al.'s stoichiometric criterion, and RAF sets | New | `validation/`, a static analysis of the realised network |

**They map onto SCIENTIFIC_BASIS.md's operational distinctions.** Transmission is H; retention, a
run of inherited boundaries; renewal, F12; autonomous renewal, growth and division with no prepared
carriers, which is this engine's default; and adaptive benefit, selection under a changing feed, a
later experiment.

### 5.2 Selection needs a finite pool, and that has a cost

- **Why a finite pool.** With a held pool, assemblies are independent between fissions. That is why
  G1's population mode is exact lane by lane. Competition needs a finite shared pool, and that
  couples every assembly in a world.
- **The architecture (S).** One SSA per world runs over all its assemblies. Joins depend on the
  pool's counts, so every change to the pool updates every assembly's join channels.
- **The cost.**
  - A two-level selection (an assembly by its total rate, then a channel within it) costs
    O(K + C) per event, for K assemblies of C channels each. A flat cumulative sum costs O(K·C).
  - D182's serial left fold runs over K, then over C.
- **Lanes become worlds,** not assemblies. K per world is a capacity bucket, for example 64–256,
  and serial transfer keeps it bounded.
- **Moran replacement** (G1's later `population_replacement@1`) stays for the GARD comparison.

## 6. Reuse, and what is new

### 6.1 Reused

| From | What | How it is used |
| --- | --- | --- |
| **G1** (GARD_DESIGN §7.2) | The exact SSA with keyed streams | The kernel, with its channels generalised (§6.3) |
| | Stochastic partition of integer counts | The membrane and lumen splits, into k daughters |
| | Repeated fission, slot reuse, carrier-keyed lineage, continuation | As built |
| | Exchange with an ideal-mixing phase | The ideal special case of §2.5 |
| | The detailed-balance-keeping common factor | A special case of the factor on m (§2.4) |
| | The stochastic thermodynamic contract | Extended with F's new terms and §3's works |
| | Restored-state branching; run records | As built; the records are extended (§6.3) |
| **D152** | Reaction declarations, molecularity at most 3, registry potentials, moieties | One declaration, two executions (§2.3) |
| **The species registry** | One authority for standard potentials; seam E's potential check and moieties | Gains entries per phase (§6.3) |
| **Seam A** (the cycle kind) | Thermodynamics in the kernel, kinetics in the law | §0.1's rule is its stochastic form. The same law's s gives a deterministic rate J = s θ⁺ (1 − e^(ΔF/k_BT)) |
| **Seams B, D and F** | Field roles at a split; heat declared non-monotone; the law template, registry and `cells.modules` | Assembly fields; event heat; every law here is one module |
| **FR-1 and its door V** | The closed node; the lumen's dilution and mixing-heat terms | The deterministic counterpart of an assembly's lumen. Assemblies bind to @3 later (GARD_DESIGN §4.2, option C) |
| **Membrane state and insertion** | Area as state; insertion's capacitor law | Area is derived from counts here. The capacitor law returns with charged amphiphiles |
| **The partition and S5** | Exact sums, lineage records, carrier keys | As in §4.4 |
| **The run view and ensembles** | Records; lanes and queues | Geometry and works are added; worlds become lanes |

### 6.2 Genuinely new

1. Channels with general stoichiometry in the stochastic kernel, with a free-energy provider that
   gives ΔF per channel.
2. The free-energy function F: phases (pool, bilayer, micelle, droplet, lumen), regular mixing, the
   geometric terms, and the lumen's osmotic term with its tension.
3. Standard potentials per phase in the registry.
4. A finite shared pool, with world-level SSA and two-level selection.
5. Geometric division at shear events into k daughters; serial transfer.
6. Fuel and activation chemistry as passive steps with fuel species; the refusal of unsourced driven
   laws; named payers for operators' work.
7. The binary-polymer family and catalyst assignments as data; templating, if chosen.
8. The deterministic limit of the same laws, as a declared representation for large assemblies.
9. Analysis in `validation/`: heritability, the Price equation, core detection and cost.

### 6.3 Requirements on G1 beyond §7.2, for the lead (not assumed)

- **R1.** Channels with general stoichiometry: up to three reactant molecules, with products in the
  membrane, the lumen or the pool. Falling-factorial propensities, scaled by physical volume.
- **R2.** A free-energy provider per world structure, giving ΔF per channel, updated incrementally.
  G1's ideal-mixing exchange is its first instance, but only with G1's ln N term. G1's measure is
  −ln (N − 1)!: exact multinomial mixing (−ln N!) plus ln N, the token
  `condensed_measure: multinomial_less_one` (§0.2a; D215).
- **R3.** Physical units: a clock in seconds, volumes and a declared temperature.
- **R4.** Derived continuous quantities (area, volume, tension), algebraic in the counts and
  evaluated in the kernel, with no ODE state.
- **R5.** World-level SSA over K assemblies sharing a pool, with two-level selection.
- **R6.** Fission into k ≥ 2 daughters, triggered by a state predicate at external events (the shear
  schedule), with two compartments per assembly and a payer field on the split's work.
- **R7.** The registry: standard potentials per phase, and sequence families in capacity buckets.
- **R8.** Run records: geometry, the pool's counts, works by payer, and the shear events.

## 7. Verification (D187)

### 7.1 Component claims

Each claim is proved once, at the cheapest level, with a planted error it must catch. The
references are written by an agent who never reads the engine.

| Claim | Cheapest proof | Planted error |
| --- | --- | --- |
| Every channel keeps local detailed balance | The kernel identity ln(a⁺/a⁻) = −ΔF/k_BT on random states (G1's check, extended) | A factor at each direction's own state; a one-sided off rate |
| A closed world relaxes to exp(−F/k_BT) | An exact master-equation solve for 2–3 types at small N (E1 and E2, in exact arithmetic) | The same planted forms (total variation 0.083 and 0.54) |
| Catalysis is kinetic only | The closed world's stationary law does not depend on s. A uniform factor rescales time, with identical event sequences under shared uniforms | Catalysis in one direction only |
| Mass action with registry potentials | SSA means converge to the same network's ODE as the volume grows (Kurtz 1972, from memory), against an independent SciPy integration | A coefficient off by one. The moiety check at parse also catches it |
| The CAC and the size distribution | One amphiphile in a closed world: the equilibrium size distribution of aggregates, in closed form from F with its geometric term | The finite-size term's sign |
| Tension-driven exchange | The end state at zero tension (V_sph(A) = V_osm), and the equilibrium split between two vesicles, in closed form | a_L off by a factor of two; a wrong Laplace factor |
| Division admissibility and the partition | Closed-form thresholds on v; multinomial and hypergeometric pmfs, by enumeration at small N and a χ² test with registered power | A split at 0.55; daughter areas that do not sum to the parent's |
| The ledgers | At every saved row, F(n_t) − F(n_0) equals the works minus the heat minus the sinks, to rounding | A heat sign error; a fuel step booked without its stored term; an unsourced driven law, which must be refused |
| The deterministic representation | Agreement with exact events where both run (10³–10⁴ molecules), within a declared error budget that shrinks with size. One case outside the envelope, an assembly with sparse counts, must fail (ARCHITECTURE.md's rule for reductions) | The envelope's own check: a sparse case admitted |
| Streams, replay and branching | G1's tests, re-run if the kernel changes | G1's |

**Then:**
- one composed world: a finite pool, two assemblies, fuel and shear division, with every ledger
  closing and replay checked;
- one baseline world in the results gate (D187, rule 2).

### 7.2 Independent references

They are NumPy and SciPy code, written from this note's equations by a fresh agent:
- exact enumeration of closed worlds, with fractions;
- a host SSA compared with common random variates (G1's pattern);
- closed forms for the geometry, the CAC distribution and the tension end state;
- an ODE of the rate laws, for the large-system limit.

An external SSA run out of process would add little, and none is proposed.

### 7.3 The GARD limit, declared (a D138 question, U6)

**The configuration:**
- ideal mixing;
- reaction-limited insertion into a bilayer (join ∝ N);
- the factor on m, with β_ij = e^(ΔΔG‡_ij/k_BT) − 1 taken from GARD's β;
- a held pool at Σ K_i ρ_i = 100;
- no geometric term;
- D1 fission at 80, with an exact half and the first daughter.

**The claim.** It reproduces G1's pair-consistent GARD law set. The event sequences are bitwise
under shared streams where the propensity arithmetic matches; otherwise the agreement is
distributional, at registered tolerances. A planted change to one β entry must fail.

**Then each departure is switched on, one at a time:** the finite pool, the geometry, physical
division and non-ideal mixing. Each one's effect on H and on composomes is measured. These are the
first experiment's arms (§8, OL9).

### 7.4 Experimental anchors (open papers; numbers as read; D186)

Every comparison here is a D138 question for the user (U6). Each judged anchor calibrates one
quantity and predicts another, registered before any judged run.

**A1. Chen, Roberts and Szostak 2004, *Science*.** NIH author manuscript, PMC4484590; no licence
stated (D186).
- **Numbers:**
  - 100 nm oleate vesicles in 0.2 M bicine, pH 8.5; 1 M sucrose inside the swollen ones;
  - at 1:1, swollen vesicles grow and isotonic ones shrink by about 25%, first order with
    k ≈ 0.1 s⁻¹ (0.6 s⁻¹ for myristoleate);
  - the swollen vesicles' largest gain, about 35%, is the paper's calculated value at zero tension;
  - the isotonic vesicles' largest loss is about 35%, against about 27% needed to make them
    spheres;
  - the maximal sustainable tension is about 10 dyn/cm, and vesicles rupture at gradients of 0.7 M
    or more.
- **What it tests:** the lumen and tension terms of F. Calibrate the off rate on k. Then predict,
  with no kinetic parameter, two end states (**S**):
  - the 1:1 end state, about 25% each way, where the two populations' tensions are equal;
  - the isotonic vesicles' largest loss, about 35%, beyond the 27% that makes them spheres. F
    reaches it only by water leaving tense vesicles against their osmotic gradient, so it is a
    sharp test of the lumen term.
- **What it does not test.** The swollen vesicles' 35% gain is the paper's own zero-tension
  calculation, so it checks the implementation, not the physics.
- **The protocol's osmotic conditions** are read from the paper when the protocol is registered.
- **Role:** judged, on the two end states.

**A2. Budin and Szostak 2011, *PNAS*.** PMC3069173; PNAS licence.
- **Numbers:**
  - 10 mol% DOPA vesicles grow about 16% at 1:1 with pure oleate vesicles, k = 0.1 s⁻¹;
  - DOPA slows oleate desorption by 22%;
  - desorption is three times faster from pure fatty acid than from an almost pure phospholipid
    bilayer;
  - the paper calculates 14% from the 22%;
  - CAC 100 µM; 23 °C; 0.2 M bicine, pH 8.5.
- **What it tests:** composition as an excess potential (§2.5), under one of its two readings.
- **The open question (S).** Under F, even ideal mixing alone (k_BT ln 0.9 ≈ −0.105 k_BT at
  10 mol%) keeps the acceptor's oleate potential below the pure donors'. Any excess adds to that.
  So every reading predicts continued transfer, not a plateau.
  - The plateau then needs a further limitation, for example exchange confined to the outer
    leaflet on the experiment's time scale.
  - The paper's own 14% comes from a calculation this note did not read.
- **Role:** reported until the representation is settled, then judged at the user's choice.

**A4. Zhu and Szostak 2009, *JACS*.** NIH author manuscript, PMC2669828.
- **Numbers:**
  - CACs of about 80 µM (oleic), 4 mM (myristoleic) and 30 mM (decanoic acid);
  - 5 equivalents of micelles give about 4-fold area, an efficiency of 50–60%;
  - threads form in about 30 min;
  - permeant ammonium acetate keeps the vesicles spherical;
  - the critical shear rate is about 15 s⁻¹ (0.35 dyn/cm² at 2.3 cP);
  - extrusion loses about 40% of the RNA, against a trace with shear;
  - vesicle counts rise about 6-fold per cycle, and the volume recovers in 24 h.
- **What it tests:** the reduced-volume law (impermeant solutes give v ≪ 1, permeant ones give
  spheres), D2's admission, and the calibration of transfer potentials.
- **Role:** judged. The shape prediction is qualitative, with a sharp criterion.

**The others, reported or later:**

| Anchor | Numbers as read | What it tests | Role |
| --- | --- | --- | --- |
| **A3.** Chen and Szostak 2004, *Biophys J*; PMC1304506; no licence stated | A fast phase k₁ ≈ 2.5 s⁻¹ (about 40% in area) and a slow phase k₂ ≈ 0.1 s⁻¹; yields close to 100% at 0.5 equivalent of micelles and about 50% at 2; micelle radius 1.3 nm; the fast phase needs a micelle-to-vesicle ratio above 0.4 | Micelle feeding, and its competition with de novo vesicles | Later: it needs the nucleation of new assemblies, which version 1 lacks |
| **A5.** Tena-Solsona et al. 2017, *Nat Commun*; PMC5520059; CC BY 4.0 | Anhydride hydrolysis at 3.8 × 10⁻² s⁻¹ (Fmoc-AVD) and 3.8 × 10⁻⁴ s⁻¹ (Fmoc-D), pH 6.0; lifetimes of 87–164 min at 5–20 mM EDC; side product at most 2% of the fuel | A fuel-driven activation cycle, its ledger, and lifetime against fuel | Reported. A judged test needs the rate constants in the Supplementary Information, not read |
| **A6.** Hordijk, Kauffman and Steel 2011, *IJMS*; PMC3116177; CC BY 3.0 | f_A(n) = 1.0970 + 0.0189n reactions catalysed per molecule for a RAF set at probability 0.5, with food strings up to length 2, n = 7–20 | The network generator and the RAF analysis, both static | A reported cross-check of `validation/` |
| **A7.** Vasas et al. 2012, *Biol Direct*; PMC3284417; CC BY 2.0 | Binary polymers with food up to length 4; Moran populations of 100 compartments; 5 of 460 runs with persistent growth in non-food mass | Whether selectable cores exist in compartments | A comparison of claims in an experiment, not an anchor |
| **A8.** Blokhuis, Lacoste and Nghe 2020, *PNAS*; PMC7568248; PNAS licence | The stoichiometric definition of autocatalysis; five types of core | — | The analysis's definitions |

**Why A1 and A4 lead (S).**
- They test the physics this engine adds and GARD lacks: tension, permeability and shear.
- Their quantities are means over many vesicles (fractional area, first-order rates, shape class),
  so the deterministic representation reaches them at vesicle scale.
- A1's end states are minima of F, so they do not depend on the representation; its rate does.
- Their buffer, 0.2 M bicine at pH 8.5, is shared, so one calibration of transfer potentials serves
  both.

## 8. Milestones, estimate and order

| Milestone | Content | Engine models it runs | Needs | Agent-days (**S**) |
| --- | --- | --- | --- | --- |
| **OL0** Desk | The user's choices; the lead's answers to R1–R8; this note's probes (done) | None (design) | — | 0.5–1 |
| **OL1** Laws | The event-pair contract in G1's kernel: general stoichiometry, the factor on m, F with ideal and regular mixing, the kernel check, ledgers for reactions | G1's family with `cells.stochastic_mass_action@1`, `cells.transition_state_factor@1`, `cells.ideal_mixing@1`, `cells.regular_mixing@1` | G1 landed; seam F's registry | 4–6 |
| **OL2** Physical assemblies | Geometry kinds (bilayer first), phase exchange, the lumen and tension, the finite shared pool with two-level selection | Plus `cells.phase_exchange@1`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.shared_pool@1` | OL1 | 5–8 |
| **OL3** Physical division | D2 with shear schedules, k daughters, the two-compartment partition and shear work; serial transfer | Plus `cells.shear_fission@1`, `cells.serial_transfer@1` | OL2 | 2.5–4 |
| **OL4** Energy | Chemostatted and finite activated species; fuel-to-waste steps; schedule work; the refusal of unsourced driven laws; moiety ledgers | OL1's laws with fuel species | OL1; seam E's moieties | 2–3 |
| **OL5** References | §7.1–7.2, by a fresh agent, in parallel with OL1–OL4 | OL1–OL4's models against the references | The user's choices | 4–6 |
| **OL6** Limits | The GARD limit (§7.3); the deterministic representation of the same laws (§1.2 (d)) and its qualification against exact events | OL1–OL3's models, and G1's GARD law set | OL3; G1's pair-consistent form | 3–5 |
| **OL7** Anchors (D138) | Protocols, calibration, judged runs: A1 and A4, and A2 if settled | OL2–OL3's models | OL6; the user's D138 answer | 4–6 |
| **OL8** Oligomers | The binary-polymer family up to L, ligation from activated monomers, catalysts as data; core and RAF analysis in `validation/` | OL1's and OL4's laws over the family | OL4 | 4–6 |
| **OL9** First experiment | A ladder of physics, matrix-paired: the GARD limit; then plus the finite pool; plus geometry and shear; plus regular mixing; plus fuel and oligomers. H, composomes, heritability and cost, in single-lineage and serial-transfer modes. Registered before any judged run | All of the above | OL6–OL8 | 4–6 |
| **Total** | | | | **33–51** (+3–5 for templating) |

**The order:**
- **Now:** OL0, desk work. The lead and G1's owner see R1–R8 while G1's channel layout is open.
- **After G1's kernel, ledger and fission land, and seam F's registry exists:** OL1, with OL5
  alongside. Then two builders on disjoint files: OL2 and OL3 (geometry, the pool, division), and
  OL4 and OL8 (energy, oligomers). OL6 follows OL3; OL7 follows OL6 and the user's D138 answer;
  OL9 is last.
- **Staffing:** at most three agents (two builders and the references agent) within seven (D171),
  alongside GARD's G3 and G4, mitochondria and the core pass.
- **Elapsed:** about 23–35 working days after G1 lands (**S**). The critical path is OL1, OL2, OL3,
  OL6, OL7 and OL9; OL4 and OL8 finish beside it. No dates are given (D194).
- **Compute:** CPU-hours. OL7 runs in the deterministic representation, in CPU minutes. OL9 is
  about 10⁸–10⁹ events, where the L4 may help.

## 9. Questions

### 9.1 For the user (marked)

1. **U1, entities.** Amphiphile assemblies with lumped geometry first, then oligomers (recommended)?
   Or oligomer chemistry first, in abstract assemblies?
2. **U2, energy.** One free-energy function for every law, with driven laws that have no declared
   source refused in this family?
3. **U3, mixing.** Mixing beyond ideal in OL1 (thermodynamic selection; A2)?
4. **U4, selection.** By a finite shared pool and serial transfer, which is physical, with Moran
   replacement only for comparisons?
5. **U5, templating.** After oligomers (recommended), now, or not at all?
6. **U6, comparisons (D138):**
   - **(a)** the GARD limit against G1's pair-consistent law set;
   - **(b)** A1 and A4 as judged experimental anchors, and A2 judged once its question (§7.4) is
     settled;
   - **(c)** A3 later; A5 to A8 reported only.
7. **U7, scale.** The deterministic limit of the same laws as a declared representation for
   vesicle-scale anchors, qualified against exact events where both run? The alternatives are
   τ-leaping, or packets of molecules, which §1.2 rejects.
8. **U8, scope.** Approve OL0–OL9 (about 33–51 agent-days) as one programme? Or OL0–OL7 first, the
   engine and its anchors (about 25–39), with oligomers and the experiment decided after?

### 9.2 For the lead

1. **R1–R8 (§6.3).** Which does G1 build, and which come in OL1? Who owns the kernel's files after
   G1?
2. **Names.** The laws and operators as named here, in G1's family namespace? G1's own IDs used
   here (`cells.assembly_lineages@1`, `size_threshold_fission@1`, `daughter_continuation@1`,
   `member_catalysis@1`, `population_replacement@1`) are as proposed in GARD_DESIGN §1, to be
   confirmed against G1 as built.
3. **The registry.** Standard potentials per phase and sequence families, with the registry's owner
   (seams C and E)?
4. **The run view.** Geometry and works, with the view's owner?
5. **Staffing.** When does OL1 start, against GARD's G3 and G4 and mitochondria?
6. **Licences.** The non-commercial template-copying source stays analysis only, with no numbers
   in the repository?

## Sources

**Searching and fetching.**
- Web searches used plain queries with no identity. Each page was fetched once through the web
  fetch tool, which summarised it against a prompt.
- Numbers are cited only where the fetched text stated them. Nothing was copied into the
  repository.

| Source | Result |
| --- | --- |
| Chen IA, Szostak JW (2004), *Biophys J* 87:988, PMC1304506 | Read. The kinetic scheme and its model equations are images. No licence stated |
| Zhu TF, Szostak JW (2009), *J Am Chem Soc* 131:5705, PMC2669828 | Read (NIH author manuscript). Filament sizes appear only in figures |
| Chen IA, Roberts RW, Szostak JW (2004), *Science* 305:1474, PMC4484590 | Read (NIH author manuscript). Table 1 read as text |
| Budin I, Szostak JW (2011), *PNAS* 108:5249, PMC3069173 | Read. Desorption rate constants appear only in figures |
| Hordijk W, Kauffman SA, Steel M (2011), *Int J Mol Sci* 12:3085, PMC3116177 | Read. CC BY 3.0 |
| Vasas V et al. (2012), *Biol Direct* 7:1, PMC3284417 | Read; the first 100,000 characters only. Equation 1 is garbled in the page. CC BY 2.0 |
| Blokhuis A, Lacoste D, Nghe P (2020), *PNAS* 117:25230, PMC7568248 | Read. PNAS licence |
| Tena-Solsona M et al. (2017), *Nat Commun* 8:15895, PMC5520059 | Read. Its Supplementary Information was not read. CC BY 4.0 |
| Li L et al. (2017), *J Am Chem Soc* 139:1810, PMC6326525 | Read. ACS AuthorChoice, non-commercial: analysis only (D173); no number is used |
| Mavelli F, Ruiz-Mirazo K (2007), *Phil Trans R Soc B* 362, stochastic protocell simulations | Search records only; the full text was not retrieved |

**Cited from memory, not read for this note:** Gillespie 1977 (the SSA); Kurtz 1972 (the
large-system limit); transition-state theory; Smoluchowski (diffusion-limited uptake); Helfrich
(bending energy); Israelachvili (micelle thermodynamics); Tanford (about 1 k_BT per CH₂); von
Kiedrowski, and Szathmáry and Gladkih 1989 (parabolic growth); Hopfield 1974 (proofreading); Price
1970; and quantitative genetics' parent–offspring regression. No text, figure or data file from
them is used.

**Engine documents read:** AGENTS.md; DECISIONS.md (D138, D142, D144, D152, D185–D187 and
D192–D197); GARD_DESIGN.md; CORE_SEAMS_DESIGN.md; ARCHITECTURE.md;
SHARED_INVENTORY_REACTIONS_DESIGN.md; CLOSED_COMPARTMENT_DESIGN.md; CELL_DIVISION_DESIGN.md and
CELL_DIVISION_S5_DESIGN.md; SYN3A_MINIMAL_CELL_TRACK.md and SOTA_SYN3A.md; SCIENTIFIC_BASIS.md; the
module design's §5; README.md; and the code's docstrings for mass action, the assembly kernel,
membrane state and osmotic water.

## 10. The lead's review and the user's decisions (17 November 2026)

**Decided (D199):**
- U1: assemblies first, then oligomers.
- U4: a finite pool and serial transfer.
- U5: templating after oligomers.
- U6(b): A1 and A4 judged, A2 reported until settled, A3 later, A5–A8 reported.
- **The lead's calls:** U2 (one F; GARD's single-event law is the labelled exception), U3 (ideal
  and regular mixing in OL1) and U7 (the deterministic limit for vesicle-scale anchors).
- **U6(a) is a consistency check:** G1's pair-consistent rule is §0.1's kinetic factor on the
  common state, so the GARD limit agrees by construction and carries a planted control.
- **U8:** recommended OL0–OL9 as one programme, waiting for the user.

**G1's names, as built** (gard-g1):
- `cells.assembly_lineages@1`;
- `cells.reservoir_exchange@1`;
- `cells.size_threshold_fission@1` and `cells.daughter_continuation@1`;
- GARD's comparison set, `cells.gard_catalysis_single_event@1` and
  `cells.gard_catalysis_pair_consistent@1`.

They replace the provisional names this note took from GARD_DESIGN §1.

**G1 and §6.3:**
- **Admitted now:** a declared channel table in the run record, in today's order, and an optional
  `units` block (seconds, temperature).
- **Already true:** R2 in substance; the provider rename comes later. R8 is true structurally.
- **Later:** R1's general-stoichiometry channels, a 2–4 day redesign of the channel layer.
- **Wait for this note's milestones:** R4–R6.
- **Belongs to the core-seams registry owner:** R7.

**Still to add to this note,** from D199:
- the four relationship-tracking checks, with a design section for material provenance (labels);
- the measures kept apart: resemblance, function and renewal;
- every descendant tracked;
- external help visible;
- the two fit tests from `docs/SOTA_ORIGIN_OF_LIFE.md`.
