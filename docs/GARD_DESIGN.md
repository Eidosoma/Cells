# GARD in Cells: catalytic assemblies, exchange, fission and lineage (design)

**Status: DECIDED, 16 November 2026: the recommendations of §4, and the comparison of §6.2 (D192).**
Built in step 4 of D194's order. An independent check of §2.2's finding, and its scope, is in §2.5.
Proposed the same day, written by the GARD design lane for the lead. The advisor
reviews it before its options go to the user (D142: options first, then discussion). Docs only;
nothing here is built. Branch `gard-design` from 3c10b833 (integration-d172's c1).

**The request.** The user, 16 November: "look into the laws, operators etc we need for an origin
of life simulation GARD, which our plastic heredity paper was based on". The architecture is to be
"clean, extendable and fast", and the testing "as little as possible but still enough, no
compromises on quality of science" (D187).

**Engine models (AGENTS.md):** none exists today, and this note runs none. The lane's milestones
would run new models, proposed in §1 and §4.6: an assembly-lineage family
(`cells.assembly_lineages@1`) with an exchange law, a catalysis factor in two forms, a fission
operator and a continuation operator. Reused unchanged: the stream, checkpoint and oracle patterns
of the assembly kernels (`cells/assembly*`), the ensemble queue (`cells.ensemble`), the species
registry's identities and the run-view writer (with additions, §5). The composite over
`resolved_pump_tissue@3` is not used by the recommended option.

**S** marks our own derivation, probe or reading. Evidence:
`/mnt/workspaces/Cells/gard-design-20261116/` (probe script, results, environment; README).

## Summary

1. **GARD in the engine's terms** (§1). An *assembly* holds integer counts of N_G molecule types.
   It exchanges molecules with a *held reservoir*. Members of the assembly catalyse each
   type's joining and leaving through a fixed matrix β. The assembly grows to a size limit and
   splits at random, and one daughter continues the *lineage*. The matrix and the reservoir are the
   environment: layout, never state (SCIENTIFIC_BASIS.md: "fixed environmental constraints").
2. **Thermodynamics** (§2). As published, the same catalytic factor multiplies joining and
   leaving.
   - **The rate law (mean field) is admissible.** Each type's net flux has the sign of its own
     affinity, so catalysis is kinetic only. With the preprint's numbers no composition can
     equilibrate: the held reservoir drives growth, and composomes are non-equilibrium states.
   - **The single-event jump process the preprint states is not microscopically reversible (**S**,
     new; checked independently, §2.5).** A join is
     evaluated before the molecule arrives, and its reverse leave after. Kolmogorov's cycle test
     fails. In a closed two-type world, the published kernel's stationary law departs from
     equilibrium (total variation 0.58) with no free-energy source.
   - **A pair-consistent form fixes this exactly:** a transfer and its reverse see the same
     catalysts. It equals the published factor to O(1/N), except under strong self-catalysis.
   - **For stochastic laws, the engine's heat check becomes local detailed balance, checked at the
     kernel,** with a non-monotone event-heat ledger that closes against a state function (§2.4).
3. **Recommendations** (§4):

   | Choice | Recommended |
   | --- | --- |
   | Kinetics | The exact SSA (direct method), single-molecule events. τ-leaping later, only as a qualified fast mode. Mean field as an analysis tool, not a simulator (P5: it cannot hold integer sparsity) |
   | Assemblies | Abstract assemblies first, with the laws declared over a generic ideal-mixing phase, so vesicles in the physical world can bind them later |
   | Matrix | Dense lognormal, β = exp(−4 + 4Z) with the diagonal kept, N_G = 100 as published. Up to about 1,000 types dense; sparse or structured β only when a consumer needs more. β is per-world data |
   | Kernel form | Both. The published form, declared non-reversible, for the reference comparison; the pair-consistent form as the engine's passive law. The difference is measured in the first experiment |
   | Reference experiment | S01's reconstructed GARD, contract T2-02 (exact events, exact-half split, first daughter), against an independent reference and the programme's own MIT code. Markovitch and Krasnogor 2018's compotype counts follow as a reported cross-check |
   | Architecture | A stochastic family beside the assembly kernels, registered as modules (D185). Not kinds in the composite |

4. **The D138 question** is in §6.2.
5. **Effort** (§7): about 20–29 agent-days in four milestones, CPU-hours of compute. No
   prerequisite beyond D172's landing. The composition gaps 1a and 1b are prerequisites only for
   vesicles in the physical world.

## 1. GARD in the engine's terms

### 1.1 The model as published, per source

The sources disagree on parameters, so they are kept apart. "Read" means the text was read; several
pages render their equations as images, which were not read.

| Source | Access | Kinetics | β | N_G; sizes | k_f, k_b, ρ | Split; lineage |
| --- | --- | --- | --- | --- | --- | --- |
| *Plastic Heredity* v5.0, Appendix F (S01 is v2.3; its GARD sections are the same in substance, **S**) | Read; CC BY 4.0 | Six contracts: vector-Poisson steps (O-02, O-03, T1-02, T1-03, T2-03) or direct categorical single-molecule events (T2-02) | exp(−4 + 4Z), diagonal kept; one matrix per environment | 100; mass 40 (40 distinct types) to 80 | 1e-2, 1e-4, 0.01, held, no depletion | Binomial p = ½ or exact hypergeometric half; first, second or random daughter |
| Pigozzi and Levin's released code, the preprint's target study (as reported in the preprint's Appendix A) | Not read | Single-molecule events | exp(N(−4, 4²)) | 100; mass 5 to 10 | 1e-3, 1e-5, 0.01 | Exact half (archive); binomial (intervention runs) |
| Segrè, Ben-Eli and Lancet 2000, PNAS | Read; equations are images, not read | Monte Carlo with Poisson increments per Δt = 0.05 (citing Gillespie 1977) | ln β normal, μ = −4, σ = 4 ("high"); μ = −6 ("medium") | 100; N_min 40, split at 80 | 1e-2 and 1e-5 (as read); a finite environment of 1,000 molecules per type | Binomial p = ½; the followed daughter is not stated; in one figure, a population of 8 with one assembly decomposed after each split |
| Markovitch and Krasnogor 2018, PLOS ONE | Read; CC BY 4.0; equations are images | Gillespie, single-lineage | ln β normal, μ = −4, σ = 4 | 100; split at 100 | 1e-2, 1e-4, 1e-2 | Random split into two daughters of 50; one random daughter followed |
| Vasas, Szathmáry and Santos 2010, PNAS | Read; equations are images | Analysis of the GARD equation, plus Moran populations | Lognormal (parameters in images) | 10 types | In images | Fission at a threshold (value in images) |

Reported results that a comparison could use:
- **Segrè 2000:**
  - fidelity H of 0.88 ± 0.10 at μ = −4, 0.81 ± 0.10 at μ = −6 and 0.65 ± 0.07 for random
    similarity;
  - in one example, three composomes over 20,000 growth–split steps, with prevalences 0.13, 0.37
    and 0.50.
- **Markovitch and Krasnogor:**
  - 10,000 matrices (3 runs failed), 5,000 growth–split cycles each;
  - compotypes found by k-means, with k chosen by silhouette: 1–6 per run, 20,235 in all.
- **Vasas et al.:**
  - "imposing Darwinian selection to the GARD model has, at most, negligible effects on the
    background distribution";
  - in their replication–mutation analysis, the dominant quasispecies is the positive eigenvector
    of the largest eigenvalue.
- **The preprint, at matched scale:**
  - F12 prevalence of 33.0–38.8% in the clean rooms and 35.4–37.8% in the originating workflow;
  - branch-half reliability of 0.911–0.938;
  - "Homogeneous and fission-only generators produced no renewals" (one implementation).

**Two facts the preprint states,** which Segrè 2000's text supports:
- The catalytic factor multiplies both directions. Segrè: "the final state is related only to the
  ratio of the basal rate constants, i.e., to thermodynamic equilibrium parameters".
- The reservoir is fixed, and the matrix is fixed except during imposed interventions. Neither is
  written by an assembly.

### 1.2 Entities

| Entity | State it owns | Notes |
| --- | --- | --- |
| **Assembly** | Integer counts n [species] (N = Σ n), its carrier key (int64, written at birth), its event counter | No volume, area or charge in the abstract option. Born at a fission or as a founder; retired at its own fission or by extinction |
| **Reservoir** (the environment) | None: held activities ρ [species] and the catalytic matrix β [species, species] are layout, per world | Fixed through a run. An edit to β (the preprint's network surgery) is a recorded operator event at a lineage boundary, never a write by an assembly |
| **Lineage** | Its fission table (§5.2) and its cumulative ledgers | One continuing assembly in single-lineage mode; a fixed population of K slots in population mode |
| **World** | One environment plus its lineages | A branch (a future from a restored landmark) is its own world with a branch key |

### 1.3 Species

- **A declared type family**, `t000…t{N_G−1}`, not N_G hand-written entries. Identities go in the
  registry as `label_only`, with no catalogue entry and no valence.
- **One standard transfer potential per type,** Δμ°_i = −RT ln K_i with K_i = k_f/k_b, declared
  once where the type is declared (the registry's one-authority rule, D174/D176).
- **N_G is the family's own static axis** (capacity buckets such as 128, 256 and 1,024). @3's
  `MAX_SPECIES` (16, FR-9) does not apply, because these types are not @3 inventory rows.

### 1.4 Laws, named by mechanism

1. **`cells.reservoir_exchange@1`: exchange between a held reservoir and an ideal-mixing
   assembly.**
   - Join of type i: k_f ρ_i N, first order in the reservoir activity and proportional to the
     assembly's size. Leave: k_b n_i.
   - Its equilibrium is x_i = n_i/N = K_i ρ_i.
2. **`cells.member_catalysis@1`: a composition-weighted rate factor, pair-consistent (the
   engine's passive form).**
   - For a transfer of type i between states n and n + e_i, the factor is
     g_i = 1 + Σ_j β_ij n_j / N, evaluated on n, the assembly without the moving molecule.
   - So a join from n and the reverse leave from n + e_i see the same catalysts. The leaving
     molecule does not catalyse its own leaving.
   - Exactly reversible (§2.2). Requires β ≥ 0 and finite; the domain refuses g_i ≤ 0, which a
     variant with inhibitory entries could reach.
3. **`cells.member_catalysis_at_state@1`: the published evaluation.**
   - b_i(n) = 1 + (βn)_i/N at the current state, for both directions.
   - Declared not microscopically reversible: admitted as a driven law, with its cycle affinity
     reported (§2.3), for fidelity to published results.

Factors multiply (SHARED_INVENTORY_REACTIONS_DESIGN.md §2.2). GARD is the first consumer of what
D152 noted and left unbuilt: "A species-dependent common factor would keep detailed balance, but
no consumer needs one".

### 1.5 Operators

1. **`cells.size_threshold_fission@1`.**
   - **Trigger:** N reaches N_split. With single-molecule events the boundary is exact, so there is
     no overshoot and no trim. The preprint's vector-Poisson trims remove material by rule, which
     the engine refuses ("refuses, never repairs").
   - **Split:** a declared random partition, `binomial` (each molecule independently, p) or
     `exact_fraction` (multivariate hypergeometric, ⌊fN⌋ molecules to daughter 1).
   - **Bookings and records:** it books the split's free-energy change as work (§2.4) and writes
     the fission table (§5.2).
   - **Its read of N is `current`,** declared statically in the composition note's sense
     (OPERATOR_COMPOSITION_DESIGN.md, branch `composition-design`, C1–C4). Within one family that
     is a read of the exchange law's own counts, and no cross-operator gap arises.
2. **`cells.daughter_continuation@1`.**
   - Which daughter continues: `first`, `second` or `uniform` (with a nonempty fallback, as T2-03).
   - The other daughter's material goes to a declared sink, or back to the reservoir; in a held
     reservoir the two are physically the same, but the ledger says which.
3. **Extinction.** Joining is proportional to N, so an empty assembly cannot regrow. The lineage
   ends with an extinct status, ARCHITECTURE.md's biological death, not a numerical failure. Each
   contract's rule for an empty selected daughter is declared in its definition.
4. **Later, by consumer:**
   - **`cells.population_replacement@1`:** a Moran step for K slots, in which a fission removes a
     member at random. This is Vasas et al.'s and Segrè 2000's population layer.
   - **Recorded interventions:** composition substitutions at lineage boundaries, and β edits
     (the preprint's Part III).

### 1.6 Observables

- **In the engine, cheap and on the device:** the boundary similarity H(P_t, D_t), the cosine
  between the pre-fission parent and each daughter, recorded per fission (§5.1).
- **In `validation/`, as analysis (D144):**
  - **F12,** a source-specific measurement contract (SCIENTIFIC_BASIS.md): inheritance strictly
    H > 0.9, so equality is a break; a break followed strictly later by three inherited fissions
    within twelve;
  - the strict F32 event;
  - composomes (an assembly highly similar to its parent and to a child, Markovitch and
    Krasnogor's definition) and compotypes (clusters);
  - fidelity (mean boundary H against the random-split baseline);
  - committor shooting from restored states.
- **The GARD definitions live in `validation/gard/`:** the preprint's contracts, the matrix
  generator with its recorded seed, and the generative nulls.

### 1.7 Units and clock

ARCHITECTURE.md (§"System shape"): GARD needs "explicit contracts if supported; they do not share an
assumed universal physical clock".
- **Time** is nominal: the source's rate constants carry no calibrated unit, and the natural clock
  is the fission count.
- **Amounts** are molecule counts.
- **Energies** are in k_BT per molecule. A declared temperature converts them to pJ only when a
  physical consumer needs it (option B).
- No calibration to lipid chemistry is claimed.

## 2. Thermodynamic admissibility

### 2.1 The rate law (mean field)

Write K_i = k_f/k_b and x_i = n_i/N. With the factor b_i > 0, the net flux of type i is

  J_i = b_i (k_f ρ_i N − k_b n_i) = k_b b_i N (K_i ρ_i − x_i).

Its affinity is A_i = ln(a_i⁺/a_i⁻) = ln(K_i ρ_i / x_i) = (μ_i^R − μ_i^A)/RT, with
μ_i^R = μ°_R + RT ln ρ_i, ideal mixing in the assembly, μ_i^A = μ°_A + RT ln x_i, and
K_i = exp((μ°_R − μ°_A)/RT) for each type (**S**).

Since b_i > 0, sign(J_i) = sign(A_i). No type's net flux runs against its own gradient, and the
heat rate RT Σ_i J_i A_i is non-negative term by term. What follows (**S**):
- **Catalysis is kinetic only.** It scales rates and never the force, so it cannot move an
  equilibrium.
- **What the composition does at β = 0 depends on the leave constants.** Write θ_i = K_i ρ_i.
  - Zero net exchange, a true fixed point at x_i = θ_i, needs Σ_j θ_j = 1. Otherwise the assembly
    grows (Σ_j θ_j > 1) or shrinks.
  - With a common leave constant k_b, as written above, a fraction changes at
    dx_i/dt = k_b(θ_i − x_i Σ_j θ_j). So the composition relaxes toward θ_i / Σ_j θ_j while N
    changes: x_i ∝ K_i ρ_i, the reservoir's composition when K is uniform.
  - Cells also accepts a leave constant per type, k_b,i (`cells.reservoir_exchange@1`'s
    `leave_rate`). The proportions then depend on the k_b,i as well, and need not stay at
    θ_i / Σ_j θ_j. For example, counts (1, 1), θ = (1, 1) and k_b = (1, 2): both types grow, yet
    the first type's fraction starts at ½ and falls at ¼ per nominal time unit. The compiled engine
    agrees. (Corrected 19 November 2026 from the Lean proofs project's finding, lean/PROGRESS.md
    and lean/CellsProofs/Chemistry/ReservoirExchange.lean. The earlier wording stated the common-k_b
    result without its condition.)
- **With the preprint's numbers nothing can equilibrate.** K_i ρ_i = (1e-2/1e-4)·0.01 = 1 for every
  type, while an equilibrium needs Σ_i K_i ρ_i = 1. Here that sum is 100.
  - Every type's affinity is ln(1/x_i) > 0 unless the assembly holds one type, so every type joins
    on net.
  - The held reservoir supplies the free energy. At P3's states, the propensity-weighted mean drive
    per join is 1.97 k_BT.
  - Fission resets the size every cycle, so the assembly is always growing and never near an
    equilibrium. Composomes are non-equilibrium kinetic states sustained by that drive, not
    equilibria shaped by catalysis.
- **So the mean-field law is admissible as a passive law.** It books heat and never work, and its
  free energy comes from the held reservoir. In @3's terms the reservoir is a chemostat, the role a
  held bath plays (D152 §2.2).

### 2.2 The jump process (single-molecule events)

**What "published" means in this section.** It means the single-event kernel that the preprint
states (S01, p. 10 and Appendix F): the event-by-event split of the original rate law, Eq. 4 of
Segrè, Ben-Eli and Lancet 2000. See §2.5 for what the original papers state.

A join takes n → n + e_i at rate a_i⁺(n), and its reverse leave takes n + e_i → n at rate
a_i⁻(n + e_i). Their ratio, in the published form, is

  a_i⁺(n) / a_i⁻(n + e_i) = [K_i ρ_i N/(n_i + 1)] · [b_i(n) / b_i(n + e_i)],

where b_i(n + e_i) = 1 + ((βn)_i + β_ii)/(N + 1) (**S**).
- **The first factor is thermodynamic.** It is exactly consistent with the product measure
  π(n) ∝ (N − 1)! Π_i (K_i ρ_i)^{n_i} / n_i!.
- **The second factor is not 1, and no single potential of the state produces it,** because b_i
  depends on the moving type. The arriving molecule catalyses its own leaving through the kept
  diagonal β_ii, and every member's weight is diluted from 1/N to 1/(N + 1).

So Kolmogorov's cycle criterion fails. Probes (CPU 22, NumPy, `probe/probe_results.json`):

| Probe | Published form | Pair-consistent form; β = 0 |
| --- | --- | --- |
| P1: the cycle n → +e_1 → +e_2 → −e_1 → −e_2 on a two-type square, only β_11 nonzero; ln(forward/reverse rates) | 0.012, 0.080, 0.113, 0.117 at n = (1, 1) for β_11 = 1, 10, 100, 1000; 1.7e-5 to 1.5e-4 at (40, 40) | ≤ 7e-15 everywhere |
| P2: a closed two-type world with a finite reservoir (8 molecules per type); the exact stationary law against the β-independent product form; total variation | 0.58 (β_11 = 50 only), 0.15 (β_12 = 50 only), 0.004 (a small lognormal pair) | ≤ 6e-14; 3e-15 |
| P3: the published regime (one lognormal matrix, N_G = 100, T2-02-like, 200 fissions); the kinetic bias ln(b_i(n)/b_i(n + e_i)) of joins | Propensity-weighted mean 0.023 against a mean drive of 1.97 (1.6%), but heavy-tailed: 99.9th percentile 3.4, maximum 4.0, at 0.064% of join weight; this matrix's diagonal reaches 2,618. Random-pair cycle affinities: median 1.2e-4, 99th percentile 0.012, maximum 0.087 | 0 by construction |

### 2.3 What follows

1. **The published jump kernel would create cycle currents in a closed world with no source.**
   P2's stationary law is far from equilibrium. Under Cells' rule it cannot be a passive law: its
   "heat" would not be a state-function difference.
2. **The pair-consistent form is the minimal correction.**
   - It is exactly reversible (P1, P2), with β invariance of the closed world's stationary law.
   - It equals the published form to O(1/N), except where self-catalysis is strong. There it
     retains strongly self-catalytic types a little more, since their leaving is no longer
     self-catalysed.
3. **In the published regime the difference is small on average and large in the tail** (P3).
   Strongly self-catalytic types are exactly the ones that shape composomes. Whether composomes or
   break-and-renewal depend on the difference is an empirical question that only a run answers.
   That run is the first experiment (§8), not this note.
4. **The rate law is unaffected,** so deterministic analyses of the GARD rate law keep their
   meaning.

### 2.4 The guard for stochastic laws, and event heat

"Heat never decreases" is a deterministic, per-element check. A single stochastic leave in a
supersaturated state legitimately goes uphill, so for stochastic laws the check is replaced by three
others (**S**):
1. **Local detailed balance, a static property checked at the kernel.**
   - For every propensity pair on random states (S5's R-ops form, 200 states),
     ln(a⁺(n)/a⁻(n + e_i)) must equal the declared affinity to rounding.
   - A law that fails is refused as passive. It may be declared driven, with its unsourced cycle
     affinity reported (the published form).
2. **Event heat, booked per committed event:**
   - each event books q = k_BT ln(w(n→n′)/w(n′→n)) into a cumulative ledger that may fall at single
     events, declared non-monotone;
   - for the pair-consistent law that ledger is a state function: cumulative heat =
     k_BT [ln π(n_t) − ln π(n_0)], plus the fission and sink terms below. So the ledger closes
     exactly at every saved row;
   - for the published form the same booking leaves a residual against ln π, the unsourced cycle
     work, which is reported rather than closed.
3. **Fission and sink bookings:**
   - the split's change in −k_BT ln π is booked as signed work, from an unmodelled agent: a
     prescribed operator, as the partition operator books its work;
   - an unfollowed daughter's material and −k_BT ln π leave to the declared sink.

Ensemble inequalities are not used as checks. The entropy-production rate at a state is
non-negative for any positive rates, so it cannot fail; mean heat alone is not bounded (the second
law bounds heat plus the ensemble's entropy change); and a fluctuation theorem in a closed world
started at equilibrium is trivially satisfied. The kernel identity, the product-form stationary law
and the ln π closure carry the teeth, each with its planted control (§6.1).


### 2.5 The independent check, and its scope (16 November 2026)

An agent that had read neither this note nor the engine checked §2.2's finding by exact rational
enumeration (evidence: `/mnt/workspaces/Cells/verify-gard-beard-20261116/`).
- **The preprint's kernel.** In a closed two-type world, with 15 to 48 states, the preprint's
  single-event kernel fails Kolmogorov's criterion on every unit square for generic β. One
  hand-checkable square gives a cycle ratio of 44/63. The events-only form of T2-02 has the same
  cycle ratios, and so does the preprint's buffered reservoir.
- **The exception is a rank-one 1 + β, with one added to every entry, not a rank-one β.** If
  1 + β_ij = u_i v_j with positive factors, the single-event kernel's extra heat is a difference of
  state values and cancels around any closed path, so the chain is reversible, with a shifted
  equilibrium; the corrected log weight is Φ(n) − ln(Σ_j v_j n_j / N). A rank-one β alone does not
  suffice: with β_AA = 1 and every other entry 0, the four-step cycle +A, +B, −A, −B at counts
  (1, 1) has a rate-product ratio of 81/80, not 1. So "different factors, hence irreversible" holds
  generically, not always. (Corrected 19 November 2026 from the Lean proofs project's proof and
  exact example, lean/PROGRESS.md and lean/CellsProofs/Chemistry/GardCatalysis.lean; the earlier
  wording said "a rank-one β". The exact finite-reservoir reference already used the entrywise
  shift.)
- **The original authors' kernel is not established either way.** The three papers read (2000,
  2014, 2018) state the rate law but no event rates. The 2000 paper's stochastic scheme draws
  Poisson changes on the net rate. That is a different kernel, irreversible even at β = 0, for a
  reason unrelated to this finding. The preprint's code repository was not inspected.
- **Not tested:** the preprint's vector-Poisson contracts.
- **The preprint's runs are not affected.** They are driven (a held reservoir, growth and
  fission), where detailed balance is not expected. The finding is about the kernel's microscopic
  consistency.
- **The pair-consistent form** (the leaving molecule does not catalyse its own leave) has no failing
  square for any β. It keeps the β-independent equilibrium exactly, and agrees with the preprint's
  rates to leading order in 1/N, except for strongly self-catalytic types.

## 3. What exists and what is new

| Need | Exists (where) | New |
| --- | --- | --- |
| Exact stochastic events | `cells/assembly/kernel.py`: direct Gillespie in JAX, vmapped over worlds, with a pending event across observation cuts; `cells/assembly/reference.py`: a host oracle compared with common random variates; the finite-pool variant (`assembly_pool`) and the coupled cell and cluster variants (`assembly_cell`, `assembly_cluster`; the cluster advances its RK4 ionic grid to each cell's next assembly event) | A general many-channel kernel. Its propensities are floats over 2·N_G channels; the capsid kernel's integer prefix counts do not apply. The cumulative sum uses D182's serial left fold. βx is updated by one column per event (elementwise, so device-independent) with an exact refresh at each fission |
| Random streams | Threefry with `fold_in(seed, world ID, event count)`, open-interval float64 uniforms (`assembly/kernel.py`, `random_pair`); ARCHITECTURE.md's rules (separate initialisation, process, partition, intervention and analysis streams; keys from run, replicate, lineage and event; diagnostics never consume them); S5 §6.1: "keyed random streams need a numeric carrier key per slot" | Keys from (campaign seed, environment, lineage, branch, carrier key, domain, counter), with one domain each for exchange, partition, continuation and initial composition. The module design's RNG contract (§5: Cells owns streams and keys, "null today") gets its first consumer |
| Many species | @3's cap of 16, raised on need (D165); A7's fold costs +4% at 150 species on the L4 (D182) | Not needed in option A: N_G is the family's own axis. The registry gets an indexed type family |
| Populations on the GPU | `cells.ensemble`: stable world-ID ranges, a seed per arm, multi-GPU queues, pause and resume (GPU_ENSEMBLES.md) | Lanes over (matrix × landmark × branch), masked when finished. Population mode is exact by independent clocks between fissions, because a held reservoir decouples the exchange; fissions commit in time order (**S**) |
| Checkpoints and branching | The assembly checkpoints keep the pending event and the stream identity, and resume without resampling; the CLI's `branch` "continue[s] with explicitly changed future inputs". The composite's checkpoint refuses random state (`io.py`) | Landmarks at post-fission states, where nothing is pending; futures as branch-keyed worlds |
| Division | `isopotential_partition@1`: prescribed, deterministic fraction, scheduled on the clock's grid (D283), fresh slots, no reuse (S5 §6.2) | State-triggered, stochastic, repeated fission with slot reuse and carrier-keyed lineage: the endogenous lifecycle's open items in miniature (CURRENT_PLAN.md, "Gate: lifecycle operators") |
| Lineage | S5's record shape (carrier_id, slot, kind, parent_carrier, sibling, birth_s, death_s, successors, route) shared with replacement's | The same shape, written by the run at scale (§5.2), with the followed daughter and the split |
| Thermodynamics | D152's passive and driven classes, exact ΔG bookings and the dissipation check | The stochastic-law contract of §2.4 |
| Observers and analysis | Run-view records, saved outputs, `validation/` analysis | H on the device; F12, F32 and compotypes in `validation/` |

## 4. Options for the user

### 4.1 Kinetics

| Option | For | Against |
| --- | --- | --- |
| **(a) Exact SSA, direct method** | Exact; the size boundary is exact; matches T2-02 and Markovitch and Krasnogor. P3: 51 joins and 11 leaves per fission, 62 events, ≤ 70 µs per event in plain NumPy with the probe's overhead | Sequential in events within a lane (parallel across lanes) |
| (b) τ-leaping, or the preprint's vector-Poisson steps | Fewer steps at large N; five of the six preprint contracts | Approximate. Clipped leaves and boundary trims are repairs, which the engine refuses; a refusing variant needs step control |
| (c) Mean field with stochastic fission sampling | Cheap | P5: the deterministic law converges to one composition (cosine change 1.4e-7 over 10 cycles). At its parent all 100 types are present and 87 hold under half a molecule; the stochastic parents hold 24 types on average (7–47). It cannot express integer sparsity, within-growth noise or switching, and splitting fractional counts is ill-defined |

**Recommended: (a)** as the simulator of record. (b) only as a qualified fast mode against (a), if
the cost ever binds; at N ≤ 100 it will not. (c) as analysis: the deterministic attractor is a
reference composition against which composomes can be placed. In P5's one matrix, the stochastic
parents' cosine to it has a median of 0.82, with a 10th percentile of 0.42.

### 4.2 Abstract assemblies or vesicles in the physical world

| Option | What it takes |
| --- | --- |
| **(A) Abstract assemblies** | §1–§3, all new and contained. Nominal clock, no volume or charge |
| (B) Vesicles in the composite | Each assembly is a cell or an FR-1 compartment, and the amphiphiles are @3 inventory rows (the cap rises to N_G plus the ions, past A7's measured 150). It also needs: a membrane-composition kind with ideal mixing; growth by area; fission by the partition from the current volume (composition gaps 1a and 1b, plus gaps 3 and 4 where they apply); triggered division, slot reuse and lineage (the endogenous lifecycle); and random state in the composite's checkpoints. No published GARD result exists for it |
| (C) A, with the laws declared over a generic ideal-mixing phase | A's cost, plus a declaration discipline |

**Recommended: (C),** that is A built so that B can bind the same laws to membrane patches later,
as its own design, after the composition gaps and the endogenous lifecycle.

### 4.3 The catalytic matrix

- **Form:**
  - **for the reference:** dense lognormal, β_ij = exp(μ + σZ_ij) with the diagonal kept, μ = −4,
    σ = 4;
  - **variants as definitions in `validation/gard/`:**
    - μ = −6 (Segrè 2000's "medium");
    - the preprint's generative nulls: a homogeneous matrix at the prior's mean exp(μ + σ²/2) = e⁴,
      coupling derangement (one permutation applied to rows and columns) and fission-only (no β);
    - "excess mutual catalysis" (Markovitch and Lancet 2012) is unparameterised here, because the
      paper was not retrieved.
- **As data:**
  - β is a per-world layout value, never closed over, so one compiled program serves every matrix
    (INNER_MODEL_V4_DESIGN.md §7.4 (a), rule P5);
  - it is generated in `validation/` with a recorded seed and law, and saved as an array beside the
    definition, which the manifest's checksums cover;
  - the engine accepts any finite, non-negative matrix.
- **Size:**
  - N_G = 100 for the reference;
  - dense up to about 1,000 types on one GPU (8 MB per matrix; per lane about 30 KB of counts, βx
    and propensities);
  - beyond about 2,000, dense β (32 MB to 800 MB per matrix) and O(N_G) per event argue for sparse
    or community-structured β, as Markovitch and Krasnogor's within-community β* analysis
    suggests. That is a separate option, taken when a consumer needs it.

**Recommended:** dense lognormal at N_G = 100, then 1,000. Sparse β waits for a consumer.

### 4.4 The kernel's form (from §2)

| Option | Consequence |
| --- | --- |
| (i) The published form only | Fidelity to published numbers, but no passive law: a driven law with an unsourced cycle affinity, reported |
| (ii) The pair-consistent form only | Exactly reversible; it departs from the published kernel at O(1/N) and under strong self-catalysis, so published numbers are no longer directly comparable |
| **(iii) Both** | The reference comparison runs (i). The engine's passive law is (ii). The first experiment measures the difference |

**Recommended: (iii).**

**The pair-consistent form's version 2** (`cells.gard_catalysis_pair_consistent@2`; D244, D246).
@1 caches x = βn and forms a leave's factor from x_i − β_ii. With β_ii = 2^54 and one other
catalyst, that subtraction loses the catalyst (the Lean proofs project's finding of 19 November
2026). @1 keeps its bits (D148). Version 2 is the same law with its cache held exactly.
- **The cache** is a pair of float64 words (hi, lo), hi = fl(x) and lo = x − hi.
  - An event adds ±β[:, i] by two error-free two-sums: O(C), as @1.
  - The founder and each daughter refold it from the counts. Each entry is split into its top 33
    bits and the rest, so every product with a count up to 2^20 is exact.
  - The leave forms x_i − β_ii exactly and rounds it once.
  - So the join from m and the leave from m + e_i evaluate the same correctly rounded Σ_j β_ij m_j:
    the factor cancels from every transfer pair bit for bit.
- **The budget, proved.** Row i's values are multiples of 2^q_i, its entries' lowest set bit, and at
  most max_j β_ij · S, with S the fission size. Below 2^(q_i + 106), each two-sum's error and the low
  word are at most 2^(q_i + 52), so their sum is exact. At 107 bits a unit can be lost (a
  constructed state loses one).
- **Refused at parse beyond it.** The message names the bits needed. At fission size 80, 0.2% of
  1,000 T2-02-like matrices (100 types, β = e^(−4 + 4Z)) need more; the median needs 98 bits. An
  experiment that draws matrices records each refused draw and how it handled it (redrawn or
  excluded), as its protocol declares, and never falls back silently to @1.
- **Evidence:**
  - the Lean project's own driver functions run under version 2, all four reverse-subtraction
    cases included;
  - the kernel against an oracle in rationals, on the stress world;
  - a dropped low word, planted, which the ledger catches.

  The Lean project's driver stays on @1 until that project points it at version 2.

### 4.5 The reference experiment

| Option | Specification and access | Comparable quantities |
| --- | --- | --- |
| **(a) S01's reconstructed GARD, contract T2-02** | Fully specified in Appendix F, with exact single-molecule events, an exact-half split and the first daughter. The programme's code is public under MIT (clean-room test 2, `replicators.13.8.2026.fable/replication/` in Eidosoma/PlasticHeredity). The user's own study | Boundary H, the inherited-boundary fraction, F12 prevalence per state, branch-half reliability, all per matrix |
| (b) Markovitch and Krasnogor 2018 | An open paper (CC BY), but its equations are images, its composome threshold and clustering details are only partly specified, and its code's licence is not stated | The distribution of compotype counts per matrix (1–6) |
| (c) Segrè 2000 | Poisson-step kernel, finite environment, populations of 8; few details legible | Fidelity H against random |

**Recommended: (a) first, as the judged comparison** (§6.2). It is the fully specified, open
contract with an exact event kernel, so differences can be attributed. (b) follows as a reported
cross-check, using numbers from the open paper under D186.

### 4.6 Architecture

| Option | For | Against |
| --- | --- | --- |
| **(F1) A stochastic family beside the assembly kernels** (`cells/assembly_lineages/`, `cells.assembly_lineages@1`), its laws and operators declared and registered as modules in their own namespace (D185) | It reuses proven patterns: keyed streams, pending-event checkpoints, the host oracle and the ensemble queue. Event-driven. The composite and its qualifications are untouched | A second runner shape beside the composite's fixed-step one |
| (F2) Kinds and operators in the composite over @3 | One runner | Kinds need IMEX and a fixed dt (§7.4 (k) 3). Operator events sit on the clock's grid (D283), not at state triggers. The checkpoint refuses random state. The species cap binds. Amphiphiles have no charge or voltage role. This is option B's route, later |

**Recommended: (F1).**
- **Clean (D142):** entities, laws, operators and observers are separate objects; the environment
  is layout; the hot loop is one functional JAX event step.
- **Extendable:** a new partition rule, continuation rule or intervention is a new registered
  operator, with no edits elsewhere.
- **Fast:** one program per structure (N_G bucket, kernel form, split rule) serves every matrix;
  the state stays on the device between fission batches.

## 5. Run records and the run view

This section is in the terms of `docs/RUN_VIEW_DESIGN.md` and the writer on main since 16 November
(`cells/records/run_view.py`; the contract's `RECORD_KINDS`, `view_events`, `living_intervals`,
`time.event_rows` and `resets`).

### 5.1 What a run saves of an assembly

Saved by default: counts, the cumulative exchange totals, heat and work, and H. Individual joins and
leaves are saved only on request; the totals carry them.

| Record | `RECORD_KINDS` | Axes | Unit | Default |
| --- | --- | --- | --- | --- |
| `assembly_count`: each type's count | `amount` | [row, species, assembly] | molecules | Saved at each fission's two rows (before and after); at cadence rows if declared |
| `joined_total`, `left_total` | `cumulative`, since the lineage's start; never restart | [row, species, assembly] | molecules | Saved |
| `discarded_total`: material leaving with unfollowed daughters (or removed members) | `cumulative` | [row, species, assembly] | molecules | Saved. Exact integer identity per slot in single-lineage mode: count = founders + joined − left − discarded. Population mode adds a between-slot transfer at fissions |
| `exchange_heat_kT` | `cumulative`, declared non-monotone (single events fall) | [row, assembly] | k_BT | Saved; closes against ln π (§2.4) |
| `fission_work_kT` | `cumulative` | [row, assembly] | k_BT | Saved |
| `occupant`, `generation` | `level` | [row, assembly] | carrier key; count | Saved: the slot's current assembly and its generation |
| `join_rate`, `leave_rate` (propensities) | `rate` | [row, species, assembly] | per nominal time unit | On request (they follow from counts and β) |
| `catalytic_factor` | `level` | [row, species, assembly] | 1 | On request |
| `boundary_similarity` (H) | `level` | [fission, 2] on the fission table: parent against each daughter | 1 | Saved |
| Event trace (time, type, ±1) | A diagnostic event table | [event] | nominal time | On request; about 62 entries per fission |

**Time bases:**
- `fission`: two rows per fission;
- an optional `cadence` base (every k events or a nominal interval);
- the unit is nominal, not seconds (§1.7).

**Checkpoints from before D188's move 2 (D195 item 4, its one exception, accepted by the user on
18 November 2026).**
- `cells.assembly_lineages@1`'s lineage checkpoints written before move 2 are refused by the
  family's frozen reader (`models/assembly_lineages/checkpoints.read`, unchanged under D215).
- The reader refuses any changed engine source, so the refusal is clean, but it names no tag.
- These checkpoints restore in the tree tagged `pre-d188-move2-2026-11-18`, the last tree before
  the move.

### 5.2 How a fission is recorded

- **The fission table,** arrays the fission operator owns, one entry per fission per world:
  - `fission_time` (nominal), `fission_slot`;
  - `fission_parent` and `fission_daughters` [fission, 2], as carrier keys;
  - `fission_followed` (which daughter takes the slot);
  - `fission_split` [fission, species]: daughter 1's counts, with daughter 2 = parent − daughter 1;
  - `fission_similarity` [fission, 2];
  - the partition stream's counter.

  This is S5's lineage shape (§3) written by the run.
- **The slot idiom is replacement's, not the partition's:**
  - The lineage's slot is kept, and its occupant changes ("Replacement keeps the slot and changes
    its occupant, which the view gives as events and the `generation` record").
  - S5's partition idiom takes fresh slots with no reuse: 201 slots for 100 fissions of one
    lineage, half of them holding discarded daughters.
  - In population mode the K slots are the capacity. A fission writes its two daughters into the
    parent's slot and the removed member's slot.
- **Events per fission:**
  - `fission` at {assembly: slot}, from the parent's occupant;
  - `retirement` of the parent;
  - `birth` of the followed daughter in the slot.
  - The unfollowed daughter has `birth` and `retirement` at the same time. Its composition is in
    `fission_split` and its material in `discarded_total`, booked to the declared sink (or the
    reservoir, if declared).
  - In population mode it is born into the removed member's slot, and that member's retirement is
    recorded.
- **`time.event_rows` gives the parent:** the row saved at a fission's time holds the parent before
  the split (P_t), and the next row holds the followed daughter (D_t). H(P_t, D_t) from those two
  rows must equal `fission_similarity`, which is a check.
- **`resets.mask` is not used.** The slot never closes, and lineage-cumulative totals never restart.
  Per-occupant totals would restart at every fission, which `resets` as worded (a closing mask)
  does not describe; hence the lineage totals.
- **A branch** (a future from a landmark) is its own world, with one view per world as the batch
  rule says. Its landmark identity and branch key go in `run`.

### 5.3 Where the run view v1 does not fit (for its owner)

1. **Events from the run.** `living_intervals` and `view_events` are computed on the host from the
   definition's schedule, on the clock's grid (D283). Fissions here are state-triggered and
   stochastic, so their events must come from the run's saved fission table.
2. **Event tables as arrays.** 100 fissions across 10⁴ lanes are 10⁶ events, too many for
   `view.json`. The view should name the fission table as an event record. JSON events stay for
   scheduled interventions.
3. **A nominal time unit,** where the writer's time bases state `s`.
4. **Scope.** The writer's version 1 refuses every family but the composite and @3.

### 5.4 The viewer's request (17 November 2026), for the build

The visualizer's assembly-run contract is `visualizer/schema/ASSEMBLY_RUN.md`. The viewer binds to no
name until it is on main. Against §5.1–5.2:
- **Already covered:** the counts, the exchange totals, H, and the fission table (parent, first
  daughter, the followed daughter, H, time).
- **New:**
  - **A world record, written once, with an id that its runs name:** the ordered type list, β at
    full precision, the supply, the basal join and leave constants, and the founder, fission, split
    and continuation rules. Two runs of one world share it.
  - **Per run:**
    - the law's form as a declared field of its own (the preprint's single-event form, or the
      pair-consistent form), beside the law id and version;
    - the revision and the registered model ids;
    - the mode (one lineage now, a population later);
    - the random stream's identity.
  - **A pair of forms starts from one founder and says so,** so that only the law differs.
  - **The event trace saved by default** for single-lineage runs: each event's type and sign, and
    the events per growth. That is about 12 kB a run.
  - **Optional: which member's catalysis drew a join.** If it is built, it draws from its own
    stream, so a run's events and results are the same with it on or off.
  - **One file, or one adapter call, holding both runs of a pair** under one clock.
- **Not the engine's:** the analysis. Inheritance (what is compared, the threshold, a mark per
  fission) and any composome clustering (method and settings) are validation outputs, saved beside
  the run.

## 6. Verification

### 6.1 Component references (D187: each claim once, at the cheapest level, with teeth)

Written by an agent that never reads the engine's code.

| Claim | Independent reference | Planted control it must catch |
| --- | --- | --- |
| The exchange law (mean field) | The closed form at β = 0: N(t) = N_0 e^{rt}, r = k_f Σρ − k_b for uniform k_f and k_b, and n_i(t) | A wrong k_b |
| Catalysis is kinetic only | Uniform β = c gives b = 1 + c exactly: the β = 0 process with time scaled by 1 + c, and the same event sequence under shared uniforms | A factor on joins only |
| Local detailed balance (pair-consistent) | The identity at the kernel on 200 random states; P1's square | The published form, refused as passive |
| The stationary law in a closed world | The product form π(n) ∝ (N − 1)! Π θ^{n_i} C(M_i, n_i) for every β; a finite-state master-equation solve for N_G = 2–3 | The published form (P2, total variation 0.58) |
| The SSA is exact | The host oracle with common random variates (the capsid pattern); at β = 0 the total size is a linear birth–death process, with closed-form mean and variance of N(t) | A biased channel choice |
| The fission partition | Exact binomial and multivariate hypergeometric pmfs: enumeration at small N, a χ² test at N = 80 with registered power | A split at 0.55 |
| Conservation | The exact integer identity per slot (§5.1) | A dropped molecule |
| The thermodynamic ledger (pair-consistent form) | Cumulative heat equals k_BT Δln π plus the fission and sink terms, at every saved row | A heat sign error |
| Streams | Bitwise replay on one backend; batch-partition invariance; independence of branches; restart mid-growth and across a fission | A reused key |
| Observers | H against NumPy; F12 against an independent predicate on all 4,096 twelve-boundary sequences (exhaustive, as the preprint did) | H = 0.9 counted as inherited |
| CPU against GPU | Distributional; event sequences are also compared, measured rather than presumed (ARCHITECTURE.md). P4: summation orders differ by ≤ 1.1e-15 relative, and gave 0 changed choices in 600,000 shared-uniform draws | — |

Then:
- **one composed check:** a full lineage world with conservation, ledger closure and replay;
- **one baseline world** added to the results gate;
- **one registered judged run** (§6.2).

### 6.2 The comparison with S01's GARD: the D138 question

> **D138 and D151: does the user approve one comparison, for *Plastic Heredity*'s reconstructed
> GARD only, contract T2-02?**
> - **(A) An independent reference,** written from the preprint's Appendix F (contract T2-02 and the
>   common kinetics) by an agent who reads neither the engine nor the programme's code.
> - **(B) The programme's own clean-room test 2 code** (Eidosoma/PlasticHeredity, MIT, at the
>   commit the preprint pins), run unmodified and out of process, keeping only saved outputs. Its
>   exact package versions were not retained (the preprint's limitation 10), so the lane records
>   the environment it uses; a distributional comparison needs no bit-exact one. One plain attempt
>   is made; if the code does not run unmodified, the lane stops and reports.
> - **(C) The comparison,** on 40 fresh matrices, saved once and given to all three arms, with five
>   post-fission landmarks each (generations 20, 35, 50, 65, 80) and 64 F12 futures per state. The
>   matrix is the inference unit, and the arms are matrix-paired. Whether (B) loads a supplied
>   matrix unmodified is not yet confirmed; if it cannot, (B) draws its own 40 and the (A)–(B)
>   comparison is unpaired, with tolerances registered for that case. Random streams are not
>   portable, so every comparison is distributional, at tolerances registered before the run:
>   - the engine (published kernel) against (A), judged: per-matrix boundary-H distribution,
>     inherited-boundary fraction and F12 prevalence; branch-half reliability, a campaign-level
>     correlation, by a matrix bootstrap;
>   - (A) against (B), judged, on the same quantities;
>   - the engine against the preprint's published values (F12 33.0–38.8%, reliability
>     0.911–0.938), reported and not judged;
>   - **teeth:** a homogeneous-β arm (no renewals in the preprint's one implementation of that
>     null) must be distinguished from the heterogeneous arm in all three, and a planted kernel
>     error (catalysis on joins only) must fail the judged comparison;
>   - **out of scope:** the frozen predictor, the interventions, the strict F32 event and Phi-r.

Cost: about 10⁷ events per arm (12,800 futures × 12 fissions × 62 events), about ten minutes per
arm on one core at the probe's NumPy rate.

### 6.3 Licences of external code and tools (all run out of process only)

| Item | Licence | Use |
| --- | --- | --- |
| The programme's code (Eidosoma/PlasticHeredity) | MIT; third-party materials keep their terms | (B) |
| The historical GARD repository (ModelingOriginsofLife/GARD at 86dff63, the preprint's ref. 12) | No licence file shown. MATLAB | None. One file was read once to confirm how the factor enters; nothing was copied (Sources) |
| The preprint's target-study code (pigozzif/OriginOfLifePhi at 5e77bbf) | No licence shown | None |
| Markovitch and Krasnogor's code and data (S1 File; Zenodo 10.5281/zenodo.56534) | Not stated on the article page; the article is CC BY 4.0 | Numbers from the paper only (D186) |
| NumPy, SciPy (references) | BSD-3-Clause | (A) and §6.1's references |
| MATLAB, or GNU Octave (GPL-3.0) | — | Not needed |

## 7. Prerequisites, order, effort and cost

### 7.1 Prerequisites

- **For (F1) with option A:** D172's landing only.
  - The family registers through today's registry chain, and adopts the module registry when
    D180's stage 1 lands. It is a natural stage-2 consumer: a stateful mechanism.
  - It implements the RNG contract of the module design's §5.
  - The run view needs the additions of §5.3, from its owner.
- **The composition gaps:**
  - **Not needed in option A.** Its fission reads its own family's counts, declared `current`.
  - **Option B needs them:** 1a (production reads the current volume), 1b (the partition takes the
    daughters' volumes from the current volume beside water), 3 (masks) and 4 (pumps on a dividing
    cell) where they apply, plus the endogenous lifecycle.

### 7.2 What is general

- **The exact SSA kernel with keyed streams:**
  - Syn3A's F11 ("exact stochastic reactions per node with keyed random streams");
  - a consolidation of the assembly pools' kernels;
  - channel gating as jump processes.
- **Stochastic partition of integer counts at division:** low-copy molecules in cell division, and
  the endogenous lifecycle.
- **Size-triggered, repeated fission with slot reuse and carrier-keyed lineage:** the endogenous
  lifecycle's open items (triggered division, slot reuse, lineage across storage, checkpoints at
  events).
- **Exchange with an ideal-mixing phase:** membrane composition (Syn3A's lipid membranes, option B).
- **A detailed-balance-keeping common factor:** catalysis on passive routes (D152's unbuilt case).
- **The stochastic thermodynamic contract (§2.4):** any stochastic chemistry.
- **Restored-state branching with branch keys:** finite-horizon probabilities in any stochastic
  assay.

### 7.3 Milestones and effort (agent-days)

| Milestone | Content | Effort |
| --- | --- | --- |
| **G1: the family** | Model, entities, spec, the type family, β and ρ as layout (1.5–2); the SSA kernel with keyed streams, the fold and incremental βx (2–3); the laws and the kernel's detailed-balance check (1–1.5); fission, continuation, lineage table and sinks (1.5–2); ledgers (1–1.5); checkpoints and branching (1–1.5); run-view declarations with the view's owner (1); the ensemble arm and a CPU/GPU measurement (1–1.5) | 10–14 |
| **G2: component references** | §6.1, by an independent agent, in parallel with G1 | 3–4 |
| **G3: the comparison** | (A) 2–3; (B) 0.5–1; protocol, judged run and analysis 1–2. After G1, G2 and the user's approval | 4–6 |
| **G4: the first experiment** | §8: protocol, runs, analysis | 3–5 |
| **Total** | | **20–29** |

### 7.4 Compute

- **G3:** about 10⁷ events per arm.
- **G4:** about 2×10⁸ events with its nulls, about 5 core-hours at the probe's NumPy rate; JAX
  lanes cut that.
- **The preprint's largest campaign,** about 10⁹ events, is where the GPU path pays. The GPU rate
  is an estimate to be measured in G1, not a claim.

## 8. The first experiment: composome emergence and inheritance under exact, reversible kinetics

**Why.** *Plastic Heredity* asks when parent–daughter resemblance breaks and renews, and names its
own next tests:
- "Mapping retained episodes onto independently defined compotypes is therefore a direct next
  test";
- "quantify material cost and the inheritance-frequency–diversity trade-off";
- and the origin-of-life question, "When did hereditary episodes become frequent, durable,
  recoverable, and variable enough for selection to act?"

Cells can add two things the preprint did not measure: the effect of exact microscopic
reversibility, and energy accounting.

**Design (proposed; registered before any judged run).**
- **The world:** T2-02's world (N_G = 100, lognormal(−4, 4), held ρ = 0.01, 40 → 80, exact-half
  split, first daughter) on 200 fresh matrices.
- **The arms:** both kernel forms, matrix-paired, plus the preprint's nulls (homogeneous,
  derangement, fission-only) at the published form.
- **Per matrix:** one 100-fission natural lineage, and five landmarks with 64 F12 futures each.
- **Readouts, per matrix:**
  1. composome emergence: boundary H against the random-split baseline, and the inherited fraction;
  2. compotypes, by a clustering registered in advance on held-out lineages: their number and
     occupancy, compared with Markovitch and Krasnogor's 1–6;
  3. F12 probability per state, and its branch-half reliability;
  4. F12 episodes mapped onto the compotypes: is a break an exit, and is a renewal an entry?
  5. the cost of heredity: heat and fission work in k_BT per inherited and per broken boundary;
  6. the kernel-form contrast: matrix-paired differences in 1–5, with equivalence margins
     registered in advance.
- **Teeth:** the homogeneous null must be distinguished from the heterogeneous arms; the planted
  errors of §6.1.
- **The layer after it** (the preprint's "next experimental layer"): population mode with selection,
  which is Vasas et al.'s test, as a second experiment.

## 9. Questions for the lead

1. **The unlicensed MATLAB file.** I fetched one file of the historical GARD repository once, which
   has no licence file, to confirm how the factor enters. The tool returned a description and two
   quoted lines. Nothing was saved, copied or used in this note: the claim rests on the preprint's
   Appendix F and the papers. Keep the record as written here, or drop the read under D184's
   precedent?
2. **The kernel's form.** Is §4.4 (iii) the right way to put it to the user, with the published
   form admitted only as a driven law with its cycle affinity reported?
3. **The run view.** §5.3's four additions go to the view's owner, on branch `run-view-d154`. Now,
   or in G1?
4. **Modules.** Should the family register through today's chain first, or be D180's stage-2
   consumer?
5. **The RNG contract** (the module design's §5). Is the core owner content that this family
   implements it first?
6. **A citation in the user's preprint.** Its reference 1 lists Deamer among the authors of Segrè,
   Ben-Eli and Lancet 2000; the PMC record lists three authors. Pass this to the user?
7. **CPU against GPU.** Accept distributional cross-device checks, with event sequences measured
   rather than presumed?
8. **The queue.** Option A waits on nothing but the landing. Where does it sit against the
   composition gaps, which are high priority after the landing?

## Sources

Each web source was attempted once, through the web fetch tool, with no account and no identity.
The preprint's Zenodo PDF (16 MB) exceeded the fetch tool's 10 MB limit, so its text was read from
the author's own copy of version 5.0 and was not compared with the Zenodo PDF. Nothing was copied
into the repository.

| Source | Result |
| --- | --- |
| *Plastic Heredity*, Zenodo 10.5281/zenodo.22143269 (resolves to v5, 10.5281/zenodo.22799362, CC BY 4.0) | The record was read; the PDF exceeded the fetch tool's size limit. The author's copy of v5.0 was read (abstract, Part I's framework, Part II, discussion, Appendices A, B and F), not compared with the PDF; S01 (v2.3) was compared on its GARD sections |
| Segrè D, Ben-Eli D, Lancet D (2000), PNAS 97:4112, PMC18166 | Read; the equations are images and were not read |
| Segrè D, Ben-Eli D, Deamer DW, Lancet D (2001), Orig Life Evol Biosph 31:119 | Not retrieved: Springer redirected to its authorization service |
| Vasas V, Szathmáry E, Santos M (2010), PNAS 107:1470, PMC2824406 | Read; the equations are images |
| Markovitch O, Lancet D (2012), Artif Life 18:243 | Refused (MIT Press, HTTP 403) |
| Lancet D, Zidovetzki R, Markovitch O (2018), J R Soc Interface 15:20180159 | Refused (HTTP 403) |
| Kahana A, Segev L, Lancet D (2023), Cell Rep Phys Sci 4:101384 | Not retrieved: a redirect page only |
| Gross R, Fouxon I, Lancet D, Markovitch O (2014), BMC Evol Biol 14:265 | Not retrieved: Springer authorization redirect |
| Markovitch O, Krasnogor N (2018), PLOS ONE 13:e0192871 | Read; CC BY 4.0; the equations are images |
| ModelingOriginsofLife/GARD at 86dff63 | The listing was read (no licence file); one file was read once (§9 Q1); nothing was copied |
| pigozzif/OriginOfLifePhi at 5e77bbf | Listing only; no licence shown |
| Eidosoma/PlasticHeredity at 90f5c33d | README read: MIT; clean-room test 2 is in `replicators.13.8.2026.fable/replication/` |
