# Origin of life, OL2 and OL3: the design check (docs only)

**Status: proposed, 18 November 2026, for the lead.** Docs only until the lead says move 2 has
landed. Branch `ol2-design-check` from main bbcbec69.
- **OL1** was read at `ol1-laws` 06ee359e. Its engine package is unchanged since c685d821.
- **OL5's references were not read.** While orienting, only the last three commit subjects of the
  `ool-references` branch were listed, and nothing else.

**Engine models: none run.** This note plans the models of OL2 and OL3 on `cells.assembly_lineages@2`
(§1, §2).

**Marks.**
- **R:** ruled (§0.2a, §0.2b, D215).
- **S:** settled: standard physics, a derivation or a probe.
- **P:** proposed here, for the lead. Every **P** that is a physical choice is a question in §7.

**Evidence:** `/mnt/workspaces/Cells/ol2-check-20261118/`.
- `probe_rule7.py`: exact fractions.
- `probe_lumen.py`: decimal arithmetic at 60 digits, because V_sph and ln V are irrational.
- The outputs and a README.

## 0. Summary

| Item | Finding or proposal |
| --- | --- |
| How OL2 enters OL1's kernel | OL1's three hooks keep their kind: reaction laws (θ⁺ and an extent on m), a factor on m, and terms of F. OL2 adds a geometry kind and a population structure for K assemblies sharing one pool (§1) |
| Invariance | A new key is absent unless its feature is declared, and an absent key is never written, so OL1's world ids and fingerprints stay as they are. New behaviour enters only through new token values and new laws, chosen statically, so OL1's programs are unchanged (§4) |
| The reverse rate when V moves (rule 2) | OL1's form carries over exactly. The lumen's ideal part is taken at X = 1, the rest of the lumen is an excess term, and the V(m) normalisation is a factor on m (§1.4). Probe L1: the pair rule closes 40 of 40 squares; the products' rule at V(m) fails 23 |
| Rule 7 | Of six candidate rules, two meet all three properties exactly: C3x and C4. The properties do not fix the law at unequal a_L, since rules that pass differ by up to a total variation of 1. **P: C3x**, which runs on G1's draw (§2.2) |
| The lumen split | Multinomial, conserving, and exchangeable jointly with the membrane, for weights taken from each daughter's own membrane. The daughters' volumes cannot be the weights, since they depend on the split (§2.3) |
| D199's debts | Every descendant: the shared pool's slots, with relations rows. External help: a sources row for every supply and every payer. Labels: integer label counts on the reserved `label` stream (§3) |
| Questions | Q1–Q21 for the lead, Q7 among them (the coordinator's on `count_on_m`), and U1 for the user (§7) |
| Estimate | OL2 6.5–9.5 and OL3 5–8 agent-days, plus 1–1.5 for labels if they fall here. §8 gave 5–8 and 2.5–4 (§8 here) |

## 1. OL2 in OL1's kernel

### 1.1 What OL1 provides (S)

- **State:** an integer count per place (a species in a phase: pool, membrane or lumen). A held
  pool place has no count.
- **Steps:**
  - at most 3 + 3 molecules, stored as 6 entries;
  - 2R channels, forwards then reverses, folded serially;
  - two uniforms per event from the occupant's stream (domain 1).
- **Rates:**
  - forward: k_f·exp(ln θ⁺(n) + ln E(m) + ln g(m));
  - reverse: the products' mass action with k⁻ = k_f e^(Σνμ°), times the same g(m), times
    exp(F_ex(n′) − F_ex(n′ − ν)) for the excess terms.
  - The ideal term is folded into the reverse. That is exact only because each dilute ln X is a
    constant of the layout.
- **Hooks:** `cells.reaction_law@1`, `cells.rate_factor_law@2` and `cells.free_energy_term@1`.
- **Checks:**
  - the kernel identity, on probe worlds and on each world (balance.py);
  - the ledger's closure at every row;
  - the host oracle's replay.
- **Conventions:** six tokens, each required, none defaulted. An unknown key is refused.

### 1.2 The components (P unless marked)

| Component | ID (interface) | The world declares | In the kernel | Records and refusals |
| --- | --- | --- | --- | --- |
| **Geometry** | `cells.bilayer_geometry@1` (new: `cells.assembly_geometry@1`) | A `geometry` block: the law; an area quantum q (m²); each membrane species' area per molecule per leaflet as an integer k_i of quanta (Q9); `vesicle_floor` {membrane_molecules, provenance `unsourced`}; `closure_cost_kT` {value, provenance `unsourced`}; `sigma_max_N_per_m` with its source | W(n) = Σ n_i k_i, an exact int64, so A = qW/2; R = (A/4π)^½, V_sph = A^(3/2)/(6√π) and v are derived, never stored (R4). It supplies A(m) and R(m) to the encounter laws. Its F is C_close for each living vesicle: a constant whose change is 0 at every step, entering only fission and lysis | Rows: W, A, V, v and σ. Refused: a membrane species without k_i; a founder below the floor; a floor without `last_molecule: kept` (Q8) |
| **Phase exchange** | `cells.phase_exchange@1` (`cells.reaction_law@1`) | A join of one molecule from the pool into the membrane, of the same species, in the join's direction (Q5). Its constant's key matches the token: `insertion_velocity_m_per_s` (k_ins) or `diffusivity_m2_per_s` (D_i). The token `exchange_encounter` (R, rule 1; conditional, Q1) | θ⁺ is the pool's activity (n/X_pool, or c/c0 when held). The extent on m is A(m)·ρ0 (`insertion_area`) or 4πR(m)·ρ0 (`diffusion_radius`), with ρ0 = N_A c0. The leave comes from F | Refused: no geometry; a step declared as the leave; a change of species; a key that does not match the token |
| **Permeation** (rule 6) | `cells.membrane_permeation@1` (`cells.reaction_law@1`; a new ID, Q17) | An entry of one molecule from the pool into the lumen, of the same species (Q5). Its key is `permeability_m_per_s` (P_s) | θ⁺ is the pool's activity. The extent is P_s·A(m)·ρ0 (`permeation_area`, R). The exit comes from F | Refused: no geometry or no lumen; a step declared as the exit |
| **Osmotic lumen** (rule 2) | `cells.osmotic_lumen@1` (`cells.free_energy_term@1`, excess) | `lumen_volume: osmotic` (a new value; `declared` keeps its meaning); a free-energy entry with `outside_osmolarity_mM` (c_ext, held, R); a lumen block without `volume_L` | F_osm(n) = −N_L(n) ln(N_A c0 V(n)) + N_A c_ext V(n), with V(n) = min(V_osm, V_sph(A(n))) and V_osm = N_L/(N_A c_ext), N_L as Q2 settles. The lumen's ln X in the layout is 0, so `cells.ideal_mixing@1` carries only μ° and ln n! there. Its factor on m is X(V(m))^(1−α_L) for a lumen-locus step and X(V(m))^(−α_L) for a membrane-locus step with lumen reactants, the same in both directions (§1.4, §1.6) | Rows: V, Δp and σ. Refused: osmotic without a geometry or a lumen; `volume_L` declared; the steps Q3 excludes |
| **Lysis** (rule 3, R) | Part of the osmotic lumen, with the geometry's σ_max | — | An event whose end state has σ > σ_max fires at its pair-rule rate and ends the life `lysed`. The lumen's and the membrane's counts go to their pool places, and q = −(F_after − F(n)) + w (Q10) | A lysis table: time, slot, key, σ at the end state, the returned counts. The status `lysed` (one assembly), or a freed slot (a shared pool). Refused: a membrane or lumen species without a pool place; a founder beyond σ_max |
| **Vesicle floor** (rule 4, R) | In the geometry block | N_floor | Both rates are 0 for a pair with an end state below N_floor, tested on the end states, never on m. A division is admitted only if every daughter is at or above the floor | — |
| **Selection order** (rule 5, R as a requirement) | — | — | Each bundle declares its fold order and its map from uniforms to events. One assembly: OL1's. A shared pool: §1.8 | `run.json` declares both |
| **Shared pool** | `cells.shared_pool@1` (the first of a new interface, `cells.population_structure@1`, Q17) | A `population` block: the structure; K slots, a capacity bucket; the assemblies' founders (membrane and lumen counts). `founder` gives the pool | State: the pool's counts plus [K, P_asm] counts, each slot's occupant key and its alive flag. F = F_pool + Σ_slots F_asm. Draws come from the reserved `world` domain (5) (Q16) | Rows per slot, with occupancy. Refused: more founders than K; `population` under `single_lineage` |

### 1.3 New keys and token values (P, Q1)

| Key or value | Required when | Refused when | Absent means |
| --- | --- | --- | --- |
| `geometry` | Any step's law is phase exchange or permeation, or `lumen_volume` is `osmotic` | — | No areas. `count_on_m` holds on every membrane-locus step, as in OL1 |
| `conventions.exchange_encounter`: `insertion_area`, `diffusion_radius` | `geometry` is declared (rule 1's "each world declares one", read as each world with a geometry) | No geometry | OL1's six tokens exactly |
| `lumen_volume: osmotic` | — | No geometry or no lumen | `declared` keeps OL1's meaning |
| `vesicle_floor`, `closure_cost_kT`, `sigma_max_N_per_m` | `geometry` (σ_max is required under `osmotic`) | Outside `geometry` | — |
| `population` | `execution.mode: shared_pool` | `single_lineage` | One assembly, as in OL1 |
| A step's encounter constant | Its law | Any other law | — |

- **`to_dict` never writes an absent key.** A written default would move every OL1 world's id
  (the SHA-256 of its canonical JSON) and its fingerprint.
- **A world with a geometry and `lumen_volume: declared`** is admitted: its extents come from areas,
  and its lumen's volume is constant.

### 1.4 The reverse rate when V moves (rule 2; S)

Write the lumen's ideal part at X_ref = 1, and F_osm for the rest. For a pair n → n′ = n + ν with
common state m, whose forward has α_L lumen reactant molecules:
- **Forward:** a⁺(n) = k_f·s(m)·θ⁺_ref(n)·X(V(m))^(−α_L).
  - s(m) is the extent with g(m).
  - θ⁺_ref(n) is the reactants' activities, with the lumen's X set to 1.
- **OL1's identity at any constant X:** k⁻·θ⁻_ref(n′) = k_f·θ⁺_ref(n)·e^(ΔF_id,ref − w).
- **So the kernel's OL1 reverse, with the same factor on m and F_osm as an excess term, gives
  a⁻(n′) = a⁺(n)·e^(ΔF − w) exactly,** where ΔF is the physical change between the end states.

What follows:
- **The claims are the ones rule 2 names:** cycle closure and the exact-F identity.
  - "The reverse is the products' rule at V(m)" is false wherever V moves.
  - Probe L1 (a closed world with 22 floppy and 32 tense states): the pair rule closes 40 of 40
    squares (largest |ln ratio| 1e-59); the products' rule at V(m) fails 23 of 40 (largest 0.23).
  - Probe L2: the pair rule's stationary law is exp(−F)/Z to a total variation of 3e-59, and the
    products' rule's is off by 0.031.
- **No new reverse path in the kernel.** The V(m) factor joins g(m) as a factor on m, and F_osm is
  one more excess term.
  - Both read their areas exactly from integers: the factor and the encounter extents at
    W(m) = W(n) − Σ_e k_e (n_e − m_e), and F_osm at the two end states.
  - So the forward at n and the reverse at n′ compute the same s(m), bit for bit.
- **The `declared` path is untouched.**
  - The layout keeps OL1's ln X = ln(N_A V c0), and there is no factor and no F_osm.
  - The Structure gains a field `lumen` (`declared` or `osmotic`), and the kernel branches on it at
    trace time, so OL1's worlds trace OL1's program.
- **Under Q3(a), no admitted step's rate depends on V(m) at all** (§1.6).
  - The only lumen-reactant steps left are lumen-locus steps with one reactant molecule, whose
    factor is X(V(m))^0 = 1.
  - So in OL2's first worlds the volume enters only through the exact ΔF.

### 1.5 Areas in integer quanta (P, Q9)

- **The quantum.** Each a_L,i = k_i·q, so W(n) = Σ n_i k_i and A = qW/2.
- **Exact integer identities:**
  - the floor;
  - the split's conservation;
  - the cuts of C3x (§2.2);
  - W(m) for both directions of a pair.
- **Float64 comparisons, each declared:** V_osm against V_sph, σ against σ_max, and D2's admission,
  36πkV² ≤ A³.

### 1.6 The empty lumen at m (Q3, Q4)

In the floppy regime V(m) = V_osm(m), which is 0 when m's lumen is empty (probe L4). The factor
X(V(m))^(1−α_L) then behaves as follows:

| Step | On m | At the firing state's V(n) |
| --- | --- | --- |
| Lumen locus, one reactant molecule (a lone molecule changing form) | 0⁰: rule 2's 0/0, whose cancelled form is 1 | 1 |
| Lumen locus, two reactant molecules (the last two) | 1/0 = +inf. It is not 0/0, so no cancelled form exists | Finite (0.5 per unit k in L4's units) |
| Membrane locus with a lumen reactant (an exit declared as the forward) | X(V(m))^(−α_L) = +inf | Finite |
| The extent on m with the normalisation at n (one reactant) | X(m)/X(n) = 0, so the lone molecule is frozen | — |

**Options:**
- **(a), proposed:** refuse such steps under `osmotic`. OL2 needs none of them: permeation is
  declared as the entry, and no lumen chemistry enters before OL4 and OL8.
- **(b):** take the lumen's X at the firing state's V(n), for both the extent and the
  normalisation. There is no singularity, and the reverse still comes from the exact ΔF.
- **(c):** (a) now, and (b) when lumen chemistry arrives.

**Q4 is the same reading.** "ff/X^α on m" is read as the count part at the firing state and X at
V(m). Under (a) the question is moot for OL2.

### 1.7 Steps under `count_on_m` once a geometry exists (the coordinator's question; Q7)

**What OL1 does.**
- Under `count_on_m`, OL1's permeation fires at an empty membrane with E(m) = N(m) − c + 1:
  1 under `multinomial`, 0 under `multinomial_less_one`. That agrees with §0.2a.
- Rule 6's `permeation_area` makes the same rate 0 by geometry, since A(m) = 0.

**P: in a world that declares a geometry:**
- `cells.stochastic_mass_action@1` with `count_on_m` is admitted only on steps whose places all lie
  in the membrane (rule 1).
- A cross-phase step with locus `membrane` takes a geometric encounter law: phase exchange for a
  join, permeation for an entry.
- **The same answer for every other step whose extent stays positive at an empty membrane:**
  - an interfacial reaction (a pool molecule with a membrane one);
  - a join from the lumen;
  - a pool-to-lumen reaction.

  Each is refused in a geometry world until a geometric encounter is declared for it (Q6).
- **Worlds without a geometry keep `count_on_m` on every membrane-locus step:** OL1's worlds, the
  probes, abstract worlds and the GARD limit (invariance, §4).
- **In a geometry world the floor (N_floor ≥ 1) makes the empty membrane unreachable.** A(m) = 0
  arises only in a probe's rate table, where permeation's rate is 0 by geometry.

### 1.8 The shared pool (R5; rules 2 and 5)

- **F is additive over the pool and the assemblies** (S, since they are separate phases).
- **Channels:**
  - each slot has its steps' 2R channels;
  - the pool's own steps (pool locus) form the pool group.
- **The selection map (P, Q16):**
  - groups in order: the pool, then slots 0 to K − 1 in slot order, never in key order (after a
    fission the two differ);
  - each group's total is a serial fold over its channels, and a0 is a serial fold over the
    groups;
  - three uniforms per event from domain 5 (`world`), with the counter at the world's event count:
    u1 gives τ = −ln u1/a0, u2 the first group with C_g > min(u2·a0, nextafter(a0, 0)), and u3 the
    channel within it, by the same rule on a_g.
  - It is exact in distribution, with P(j) = a_j/a0 (S). The residual of one uniform could stand
    in for u3, but it loses bits.
- **The cost per event (S):**
  - the event's slot recomputes its channels: O(C);
  - a change in the pool also changes every slot's joins and entries, J per slot, and the folds
    cost O(K);
  - in all, O(K·J + C).
- **c_ext is held** (R, rule 2). The pool's own solutes do not enter it in OL2; that is a declared
  approximation (Q20).
- **A world with K = 1 has the single assembly's rate table** (S). Its stream differs, so that is a
  check on rates, not a bitwise claim.
- **Lanes are worlds** (§5.2 of the design note).

## 2. OL3

### 2.1 Shear fission (D2): `cells.shear_fission@1`

- **The schedule:** declared times, or a Poisson rate on a `schedule` stream (Q21), each event
  with a stress τ.
- **At an event,** each living assembly is tested in slot order (Q14). It needs:
  1. τ ≥ τ_crit (declared, with its source);
  2. v ≤ k^(−1/2), that is, 36πkV² ≤ A³ (S);
  3. then the split (§2.2, §2.3);
  4. then every daughter at or above N_floor (R, rule 4). Otherwise the fission is refused and
     recorded, and the parent stays.
- **k** is declared per schedule (P), or is ⌊v^(−2)⌋ up to a declared cap (Q13).
- **Unequal daughters hold at least what equal ones hold** (S, Jensen). A^(3/2) is convex, so
  Σ_j V_sph(A_j) ≥ k·V_sph(A/k) whenever Σ_j A_j = A. The equal-sphere test is therefore
  conservative for C3x's unequal areas.
- **A daughter born beyond σ_max lyses at birth** (R, rule 3).
- **The draws (P):** domain 2, keyed by the parent's carrier key, with the counter at the parent's
  number of attempts.

### 2.2 Rule 7: the membrane split (probe `probe_rule7.py`)

Twelve parents were probed: four with equal weights (N = 4, 5, 6, 7 with k = 2, 3) and eight with
unequal integer weights (1:2, 1:3, 2:3, 1:2:3; k = 2, 3). The daughters' target areas are equal
(W/k). Every law is exact, by enumeration.

| Rule | What it does | P1 | P2 | P3 | Areas (mean \|W_j − W/k\|, unequal cases) | Device |
| --- | --- | --- | --- | --- | --- | --- |
| C0 | G1's rule: floor(N/k) molecules to each daughter in label order, the last takes the rest | ✓ | ✓ (G1's form) | ✗: TV 1 at N = 5 and 7, and in four unequal cases | Areas ignored: 1/3–8/5 | Yes |
| C1 | C0's sizes, given to the daughters in a random order | ✓ | ✓ | ✓ | Areas ignored: 1/3–8/5 | Yes |
| C2 | Fill each daughter until its area reaches W/k; the last takes the rest | ✓ | ✗ | ✗: 4/15–1 | 4/15–1; the straddling molecule lands in the earlier daughter (bias up to +1) | Yes |
| C3 | Cut at the prefixes nearest t·W/k, ties low, blocks in label order | ✓ | ✗ | ✗: 4/15–1 | 4/15–4/5 | Yes |
| C3c | C3 with a fair coin at each tie | ✓ | ✗ | ✓ at k = 2; ✗ at k = 3 (1/5–1) | As C3 | Yes |
| **C3x** | C3, with the blocks given to the daughters in a uniformly random order | ✓ | ✓ | ✓ | 4/15–4/5, under w_max/2 per cut | **Yes:** G1's ranks, an integer prefix sum, an argmin per cut, and k uniforms |
| C4 | Uniform over labelled assignments at the most balanced achievable areas | ✓ | ✓ | ✓ | 0 wherever the targets can be met exactly | No: a constrained sampler (a dynamic programme over areas); host only |
| C5 | A random order, cut where a prefix's area is exactly W/2, otherwise redraw | ✓ | ✓ | ✓ (defined in 5 of 12) | 0 | No: unbounded redraws, and undefined when W/2 cannot be reached |
| Plant | Binomial labels (G1's `binomial`) | ✓ | ✗ | ✓ | — | — |
| Plant | Independent samples of floor(N/k) | ✗ | ✗ | ✓ | — | — |

**Findings (S):**
1. **P1 holds for any rule that assigns whole molecules,** so it separates only the plant.
2. **P2 and P3 conflict in G1's form when k does not divide N.**
   - Floor-to-first is the hypergeometric given its sizes, but the first daughter is always the
     smaller: a total variation of 1 under relabelling.
   - The exchangeable reading gives the same size vector to the daughters in a random order. The
     four rules that pass P3 in every case (C1, C3x, C4, and C5 where it is defined) match it
     exactly at equal weights, with total variation 0.
   - **P:** read P2 so (Q11). G1's D1 keeps floor-to-first for the GARD limit.
3. **k = 3 separates reversal symmetry from exchangeability.** C3c passes at k = 2 and fails at
   k = 3.
4. **Fill-to-area rules size-bias the straddling molecule.**
   - At weights 1:2 with n = (3, 2), the straddler is the larger species with probability 3/5,
     against an area share of 4/7 and a count share of 2/5.
   - First-reach gives the straddler to the earlier daughter.
   - Nearest cuts with a random daughter order remove the bias, so each daughter's mean area is
     its target.
5. **The three properties do not fix the law at unequal a_L.**
   - C1, C3x, C4 and C5 all pass, but their laws differ, by up to a total variation of 1.
   - C4 and C5 differ by 3/77 at weights 1:2 with n = (4, 2).

**P: C3x** (Q11). It reduces exactly to the exchangeable hypergeometric, and it keeps each
daughter's area within w_max/2 at each cut, which is negligible at vesicle scale. It runs on G1's
draw with static shapes. Its law at unequal a_L is procedural, so OL5 replays it from the uniforms
or enumerates the sequences. **C4 is the alternative** if exact areas matter more than the device.

**C3x, exactly:**
1. List the parent's membrane molecule places by species, in declared order (G1's list). Draw M
   uniforms (domain 2). Rank the occupied places by u, ascending, ties by place.
2. Prefix areas: S_c = Σ k_i over the first c ranked molecules (integers).
3. For t = 1, …, k − 1, c_t is the smallest c minimising |k·S_c − t·W| (integer arithmetic), and
   no less than c_(t−1).
4. Block t is the ranked molecules from c_(t−1) + 1 to c_t.
5. k more uniforms from the same stream, after the M, give the daughter order π = argsort. Block t
   goes to daughter π(t).
6. Daughter j takes the next count of the parent's sub-lineage, in daughter order (relations §1.3).

### 2.3 The lumen split

- **§4.4's weights V_j/V are circular.**
  - A daughter's V depends on its own lumen count, which is the split's outcome.
  - The daughters' volumes need not sum to the parent's, since water moves.
- **So the weights come from the parent or the daughters' membranes (Q12):**
  - **(a), proposed:** V_sph(A_j)/Σ_l V_sph(A_l). Each daughter takes the same fill fraction of its
    sphere;
  - (b) A_j/A;
  - (c) 1/k.
- **Each lumen molecule place goes to daughter j with probability p_j:** a multinomial, from G1's
  one uniform per place. The cumulative weights are taken in the daughter order π (P), so rounding
  favours no label.
- **The probe:**
  - conservation, and the joint (membrane, lumen) law's exchangeability, hold exactly for (b) and
    (c) with C3x and with C4;
  - (a) is irrational, but has the same structure: a symmetric function of each daughter's own
    membrane;
  - the plants:
    - sequential binomials at p = 1/k fail at k = 3 (TV 8/27 and 266/729);
    - independent binomials fail conservation;
    - weights by block position fail exchangeability (TV 31/162, 73/343 and 29/135 with C3x).

### 2.4 Shear work (S, §4.4)

**w_shear = F(daughters) − F(parent) for each fission.** It includes:
- (k − 1)·C_close;
- the membranes' mixing: each daughter's −ln(N_j − c)! + Σ ln n_ij!, less the parent's;
- each daughter's excess terms;
- the lumens' terms, at each daughter's own V_j(n_j).

It is booked to `source:shear/<schedule>` (kind `schedule`, class `energy`). A daughter that lyses
at birth books its release as heat, after the split.

### 2.5 Continuation and every daughter

- **A single lineage** (OL1's mode): G1's `daughter_continuation@1`, generalised to k daughters
  (`first`, or `uniform` over k, with its rule for an empty daughter). The others end
  `not_followed`, and their material and F go to the sink.
- **A shared pool:** every daughter lives.
  - Daughter 0 takes the parent's slot, and the others take free slots in slot order.
  - With too few free slots, the run stops `slots_full` before the split, and every life is
    censored (P, Q15).
- **Keys** follow relations@1 §1.3.

### 2.6 Serial transfer: `cells.serial_transfer@1`

- **At declared times:**
  - K_keep living assemblies are drawn uniformly without replacement, all of them if fewer live,
    from the `schedule` stream;
  - the rest end `removed`;
  - the pool is replaced by the declared fresh composition, with c_ext unchanged.
- **Bookings (S):**
  - before the transfer, F = F_kept + F_removed; after it, F = F_kept + F_fresh;
  - the sink gains F_removed, and schedule work gains F_fresh (payer `source:transfer/<schedule>`);
  - so the closure holds.

### 2.7 One run loop with @1 (D215, R)

- **Shared:**
  - the host loop: chunks, lanes due to divide, continuation;
  - the fission table and relations rows;
  - the every-descendant program.
- **The family's own:** the event program and the split rule.
- **@1's files are edited** behind @1's invariance gate (GARD's records and programs bitwise, and
  the ten rows of G2's references). Ownership of those files is Q18.
- **The cost is in §8:** 1.5–2.5 agent-days.

## 3. What D199 still owes, for OL2 and OL3

### 3.1 Every descendant

| Mode | What lives | Rows (`cells.relations@1`) |
| --- | --- | --- |
| A shared pool | Every daughter, up to K slots; a full set of slots stops the run | `lives`: founders and every daughter, with parent, share and generation. End reasons: `divided`, `removed` (a transfer), `censored`, and `lysed` (Q10) |
| A single lineage | One daughter followed | The others `not_followed`, with their compositions in the fission table |
| A single lineage with a held pool | Every daughter, by P-a (RELATIONSHIPS §1.4) through the shared loop | P-a is exact only when the pool is held: a finite pool couples the assemblies |

### 3.2 External help made visible

| Supply or payer | Source row (kind, class) | Record it weighs |
| --- | --- | --- |
| A held pool species | `source:held/<species>` (chemostat, substrate) | `reservoir_supplied`; it pays the reservoir work |
| Shear | `source:shear/<schedule>` (schedule, energy) | Shear work |
| A transfer's fresh pool | `source:transfer/<schedule>` (schedule, substrate); its bottleneck is an event of class intervention | Schedule work; the removed material and F go to the sink |
| Lysis | No source: an internal release | Heat |

Every work field names its payer, and an unnamed one is refused (RELATIONSHIPS §3.3).

### 3.3 Material provenance: labels (P, Q19)

| Event | Labels |
| --- | --- |
| A molecule leaves a finite place (a step's reactant) | Drawn from that place's label composition: one uniform per molecule, from domain 4 (`label`) at a counter derived from the event's |
| A move: a join, an entry, a leave or an exit | The molecule keeps its label |
| A reaction's product | Species origin, `production/<step>` (RELATIONSHIPS §2.5) |
| From a held place | The source's label, with no draw |
| A fission | Places listed by label within each species, so the split's uniforms are unchanged and no draw is needed (RELATIONSHIPS §2.7) |
| Lysis | The content returns to the pool places with its labels |
| A transfer | The kept assemblies keep their labels. The removed content and the old pool leave for the sink with theirs. The fresh pool takes the transfer's label (pulse and chase) |

### 3.4 The four relationship checks (D199)

| Check | OL2 and OL3 |
| --- | --- |
| Descent | Keys unique across a world; each row has its parent and its end reason; the same row shape as tissue division (the writer's own checks). Plants: a dropped daughter; a duplicated key |
| Provenance | Labels (§3.3) |
| Dependence | Who fed whom: `moves_to` edges between each slot and the pool, weighted by its one-way join and leave records, which are one-way by nature, plus the labels |
| History | Out of scope (P). @2 has no checkpoints in OL2 or OL3, so D195's refusal across move 2 never applies to it |

### 3.5 The SOTA note's two fit tests (S)

- **A fibre that grows and breaks under shear fits as a later geometry kind.** Its length comes
  from the counts, its encounter is end capture, its end-cap cost works like C_close, and each
  break adds two ends as shear work.
- **SpudCell's plasmid-set inheritance needs pieces from three milestones:**
  - OL3's lumen split of low-copy species;
  - shared-pool descent;
  - OL4's driven replication.

## 4. Invariance

- **The rule (R, §0.2a).** Existing token values keep their meaning. New behaviour comes only from
  new values (`osmotic`, `exchange_encounter`'s two) and new laws.
- **Mechanisms:**
  - absent keys are never written (§1.3);
  - new Structure fields take the values that reproduce OL1's structure, and the kernel branches on
    them in Python, at trace time;
  - OL1's laws and arrays are untouched.
- **The comparison set, which must be bitwise:**
  - every world id and definition fingerprint;
  - every array of `records.npz`, of the trace and of the uniforms;
  - every `probe.npz` and its hash;
  - every refusal message;
  - the program text, compared as crossrev compares it (without debug metadata).

  It excludes the revision field and timings.
- **The gate:**
  - OL1's probe driver re-run from a snapshot of the OL2 head, on OL5's registered inputs;
  - every role's outputs equal to OL1's landing run;
  - one program per structure equal.
  - **The plant:** a written default, which must fail the gate.

## 5. Claims for §7.1, for OL5's references

Each claim is proved once, at the cheapest level, with its planted error. Symbols:
- n′ = n + ν, and m = min(n, n′);
- ρ0 = N_A c0;
- X(V) = N_A c0 V;
- a_i is a pool activity: n_i/X_pool, or c/c0 when held.

| ID | Claim | Cheapest proof | Planted error |
| --- | --- | --- | --- |
| G1 | A = (q/2) Σ n_i k_i; R = (A/4π)^½; V_sph = A^(3/2)/(6√π); v = V/V_sph ≤ 1 | Closed forms on random states | a_L per bilayer, so A doubles |
| G2 | Every pair with an end state below N_floor has a⁺ = a⁻ = 0. A closed world's law is exp(−F)/Z on the truncated space | Rate tables at N_floor and N_floor + 1; exact enumeration | The floor tested on m. It is caught by the rate table, not the stationary law, which zeroing a pair does not change |
| G3 | C_close changes no rate. It enters ΔF only as +(k − 1)C at a fission and −C at lysis | Rate tables equal for C = 0 and C ≠ 0 | C_close charged per molecule |
| X1 | a⁺(n) = k_ins·A(m)·ρ0·a_i (insertion area) or D_i·4πR(m)·ρ0·a_i (diffusion radius), with m = n. a⁻(n + e_i) = a⁺(n)·e^(F(n + e_i) − F(n) − w) | The kernel identity on random states; Kolmogorov's test on squares | A first-order leave with no tension term; the extent taken at n′ |
| X2 | At equal a_L, insertion area and c = 1: the rate table equals the `count_on_m` world's with k_f = k_ins·(qk/2)·ρ0 | Rate tables, to rounding | c = 0 in one of the two (N against N + 1) |
| X3 | One amphiphile, with a finite pool and no lumen: the stationary law is exp(−F)/Z. In the large-vesicle limit, c_cac = c0·e^(μ°_bil − μ°_sol) | Exact enumeration; the closed form | The transfer potential's sign |
| P1 | Entry a⁺ = P_s·A(m)·ρ0·a_s; exit = a⁺·e^(ΔF − w). In the large-N limits: n_s/N_L = c_s/c_ext (floppy) and n_s = N_A·V_sph·c_s (tense) | The kernel identity; exact stationary law | P·A(n′) |
| L1 | F_osm = −N_L ln X(V(n)) + N_A c_ext V(n), with V(n) = min(N_L/(N_A c_ext), V_sph(A)), which is F's minimiser over V ≤ V_sph | Closed form; minimisation over V | A lumen species left out of N_L. Probe L5: V is then not the minimiser |
| L2 | a⁻(n′)/a⁺(n) = e^(F(n′) − F(n) − w) for every pair, and every square closes, in both regimes and across the kink | The kernel identity; Kolmogorov's test | The reverse as the products' rule at V(m) (probe L1) |
| L3 | σ = max(0, Δp·R/2), with Δp = k_BT(N_L/V − N_A c_ext). σ is continuous at V_osm = V_sph. A join's lumen part of ΔF is −σ·a_L/2·(1 + O(1/N)) | Closed forms; probe L3 | Δp·R, with no 1/2 |
| L4 | A closed world that crosses the kink relaxes to exp(−F)/Z | Exact master-equation solve | The products' rule at V(m) (probe L2) |
| Y1 | n → n′ with σ(n′) > σ_max fires at a⁺(n) and ends the life `lysed`. Its counts go to the pool, and q = −(F_after − F(n)) + w, with F_after holding no vesicle and no C_close | A small world whose only route crosses σ_max; the ledger closes | Lysis as a zero rate; lysis tested on m |
| Y2 | A daughter born with σ > σ_max lyses at birth, and that is recorded | A forced split | No record |
| S1 | Two assemblies on one finite pool relax to exp(−F_pool − Σ F_asm)/Z | Exact enumeration | A join that reads the pool at n′ |
| S2 | The declared map replays every event (§1.8) | The host oracle, with common uniforms | Groups folded in key order after a fission |
| S3 | P(channel j) = a_j/a0 | Exact rationals over the map | The group chosen uniformly |
| S4 | A world with K = 1 has the single assembly's rate table | Rate tables | — |
| D1 | Admitted only if τ ≥ τ_crit, 36πkV² ≤ A³ and every daughter is at or above N_floor | Closed forms at the thresholds | The threshold at k^(−1/3) |
| D2 | The split as ruled (C3x): P1 on counts; P2, the exchangeable hypergeometric at equal a_L; P3, the joint pmf invariant under relabelling | Exact pmfs by enumeration at small N; χ² at N = 80 with registered power | Floor-to-first at odd N (P3); binomial labels (P2); independent samples (P1) |
| D3 | The lumen: multinomial with the ruled weights, conserving, and jointly exchangeable | Enumeration | Sequential binomials at p = 1/k with k = 3; independent binomials |
| D4 | w_shear = F(daughters) − F(parent), including (k − 1)·C_close; the ledger closes | A forced split | C_close left out |
| T1 | Each K_keep-subset is equally likely; the sink gains F_removed and schedule work gains F_fresh | Enumeration over the sampler's map | Sampling with replacement; the fresh pool booked as heat |
| E1 | F(n_t) − F(n_0) = W_res + W_shear + W_sched − Q − S_sink at every saved row | The composed world | A heat sign error; shear work booked as heat |
| B1 | Label content sums to the counts; per label, founder + supplied − removed = content | Ledgers | A dropped booking |
| B2 | Labels change no event: the comparison set is equal with labels on and off | Bitwise | A label draw from the event stream |
| B3 | A closed world's label marginals at equilibrium | Exact enumeration | The destination's composition used for a move |
| B4 | Given the species split, each label's split is hypergeometric | Enumeration | Places ordered by label before species |
| R1 | Lives = founders + every daughter; keys unique; every non-founder has its parent and every ended life a reason | The writer's checks, plus counts | A dropped daughter; a duplicated key |
| I1 | OL1's registered worlds: the comparison set (§4) is unchanged | The gate | A written default |

## 6. Testing

| Test file (`tests/unit/`) | Claims | Tier (P) |
| --- | --- | --- |
| `test_assembly_lineages_v2_geometry.py` | G1–G3; conditional parsing and refusals | 1 |
| `test_assembly_lineages_v2_exchange.py` | X1–X3, P1 | 2 |
| `test_assembly_lineages_v2_lumen.py` | L1–L4, Y1–Y2 | 2 |
| `test_assembly_lineages_v2_pool.py` | S1–S4 | 2 |
| `test_assembly_lineages_v2_division.py` | D1–D4. Exact pmfs in tier 2; χ² at N = 80 in tier 3 | 2 and 3 |
| `test_assembly_lineages_v2_transfer.py` | T1, E1 | 1 |
| `test_assembly_lineages_v2_labels.py` | B1–B4, R1 | 2 |
| `test_assembly_lineages_v2_invariance.py` | I1, over OL1's registered worlds through `validation/assembly_lineages_v2/registered.py` | 2 |

**Gates:**
- **At each landing:** tiers 1 and 2 with no change against the baseline. The tier rows are
  re-measured on the timed lane.
- **Code-level:**
  - §4's invariance gate;
  - @1's gate for the shared loop: G1's tests and GARD's records bitwise against a frozen run;
  - crossrev and the results gate unchanged, since no tissue file is touched.
- **D187:** one composed world (a finite pool, two assemblies, shear division and a transfer, with
  every ledger closing and replay checked), and one baseline world in the results gate.
- **For OL5:** the probe driver gains OL2's and OL3's roles, and OL5 judges against its saved
  outputs.

## 7. Questions

### 7.1 For the lead

1. **Q1, conditional keys.** Is `exchange_encounter` required exactly when a geometry is declared?
   That is this note's reading of rule 1. Is every new key absent unless its feature is declared,
   and never written when absent (§1.3)?
2. **Q2, N_imp.** Does every declared lumen species count, a permeating one included? F's lumen
   gives each of them a ln V term, so V(n) is F's minimiser only if all count (probe L5: an F
   difference of −0.55 k_BT).
3. **Q3, the empty lumen at m.** (a) Refuse under `osmotic` the steps whose rate there is +inf
   (proposed). (b) Take the lumen's X at V(n). (c) (a) now, (b) with lumen chemistry (§1.6).
4. **Q4, reading "ff/X^α on m".** Is the count part at the firing state and X at V(m)? It is moot
   under Q3(a).
5. **Q5, directions.** Are phase exchange declared only as joins and permeation only as entries,
   so that θ⁺ is the pool's activity and each reverse comes from F?
6. **Q6, the other interfaces.** Are a join from the lumen (the inner leaflet), an interfacial
   reaction and a pool-to-lumen reaction refused in geometry worlds until a geometric encounter
   is declared?
7. **Q7, `count_on_m` in geometry worlds (the coordinator's question).** Is
   `cells.stochastic_mass_action@1` with `count_on_m` admitted there only for steps whose places all
   lie in the membrane? Cross-phase steps would then take geometric laws, and worlds without a
   geometry would be unchanged (§1.7).
8. **Q8, the floor.** Is `vesicle_floor` required with a geometry, counted in membrane molecules,
   with N_floor ≥ 1 and `last_molecule: kept`? Should it count area instead?
9. **Q9, areas in integer quanta.** Are they acceptable, so that A(m), the floor, the cuts and
   conservation are exact integers (§1.5)?
10. **Q10, lysis.**
    - (a) The closure cost is released at lysis. Rule 4 names only a division's ΔF, but lysis
      also ends a vesicle.
    - (b) The membrane molecules return as pool monomers of their own species, so every membrane
      and lumen species needs a pool place.
    - (c) Lysis is strict (σ > σ_max), a founder beyond σ_max is refused, and σ_max is required
      under `osmotic`.
    - (d) `lysed` is not among `cells.relations@1`'s end reasons, and that format is bound. Does it
      go to the requirements of the next relations version?
11. **Q11, rule 7.** C3x (proposed) or C4? Is P2 read as the exchangeable hypergeometric when k
    does not divide N, with G1's floor-to-first kept for D1 (§2.2)?
12. **Q12, the lumen's weights.** (a) V_sph(A_j)/Σ V_sph (proposed), (b) A_j/A, or (c) 1/k?
13. **Q13, D2's k.** Declared per schedule (proposed for OL3), or ⌊v^(−2)⌋ up to a cap, closer to
    A4's many daughters (for OL7's protocol)?
14. **Q14, shear events.** Do they act on every admissible assembly at once, in slot order? A
    fission refused at the floor would be recorded and the parent kept, and the partition's
    counter would count attempts.
15. **Q15, a full set of slots.** Does the run stop `slots_full`, never dropping a daughter?
16. **Q16, the selection map.** Three uniforms from domain 5, with groups in slot order (§1.8)?
17. **Q17, IDs and interfaces.**
    - `cells.shared_pool@1` as the first `cells.population_structure@1`, or a mode token?
    - Two new IDs: `cells.membrane_permeation@1` and the geometry interface
      `cells.assembly_geometry@1`. The permeation name should be checked against the tissue laws'
      names.
    - §8's other IDs are confirmed.
18. **Q18, the shared loop (D215).**
    - Who owns @1's `runner.py`, `records.py`, `fission.py`, `continuation.py` and `keys.py` now?
    - What is "the probe-set comparison", and which of its exemptions widen after the demo?
19. **Q19, labels.** In OL3, after fission, on domain 4 (proposed)? Or in the relationships lane's
    RT4, for @2?
20. **Q20, c_ext.** Is it held, with the pool's own permeating solutes kept out of it, as a declared
    approximation for A1 and A4, whose 0.2 M buffer dominates?
21. **Q21, streams.** A new `schedule` domain (6) for Poisson shear times and for the transfer's
    sampling?

### 7.2 For the user (marked)

- **U1 (for the user, through the lead): the estimate.** OL2 and OL3 come to about 11.5–17.5
  agent-days, plus 1–1.5 if labels fall here, against §8's 7.5–12. The difference is D215's shared
  run loop, D199's relations and labels, and rule 3's lysis. The programme was approved whole (U8,
  33–51).

## 8. Files and estimate

**Files** are named relative to the family package. Their root follows move 2's map, which is not
committed yet, so no post-move path is guessed here.

| Where | Files |
| --- | --- |
| `assembly_lineages_v2/`, new | `geometry.py`, `exchange.py`, `permeation.py`, `lumen.py`, `population.py`, `division.py`, `transfer.py`, `labels.py` |
| `assembly_lineages_v2/`, changed | `__init__.py`, `interfaces.py`, `conventions.py`, `world.py`, `spec.py`, `model.py`, `kernel.py`, `balance.py`, `ledger.py`, `records.py`, `runner.py`, `streams.py`, `reference.py` |
| `assembly_lineages/` (@1, shared through D215's loop; Q18) | `runner.py`, `records.py`, `fission.py`, `continuation.py`, `keys.py`, and a new shared loop module |
| Registry | `registry/model_table.py`: homes and interfaces |
| Validation | `validation/assembly_lineages_v2/`: `FORMAT.md`, `probes.py`, `registered.py` |
| Tests | `tests/assembly_lineage_v2_fixtures.py`; §6's eight files; `tests/test_tiers.json` |

**The estimate** (agent-days, S):

| Milestone | Item | Days |
| --- | --- | --- |
| OL2 | Conditional keys, world blocks and refusals | 0.5 |
| | Geometry: integer areas, the floor, the closure cost, σ_max | 0.5–1 |
| | Phase exchange and permeation | 0.5–1 |
| | The osmotic term, static dispatch and lysis | 1–1.5 |
| | The shared pool: K slots, the world stream, two-level selection, the oracle | 1.5–2.5 |
| | Probe worlds, the ledger, records, FORMAT and OL5's roles | 1–1.5 |
| | The invariance gate | 0.5 |
| | Tests and tier rows | 1 |
| | **OL2** | **6.5–9.5** |
| OL3 | The shared run loop, behind @1's gate | 1.5–2.5 |
| | Shear fission: admission, C3x, the lumen split, shear work | 1.5–2 |
| | Continuation in both modes, slots, keys, relations rows and sources | 1–1.5 |
| | Serial transfer | 0.5–1 |
| | Tests and tier rows | 0.5–1 |
| | **OL3** | **5–8** |
| Either | Labels (Q19) | 1–1.5 |

## Sources

- **Read:**
  - AGENTS.md;
  - `docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md` (the whole note);
  - DECISIONS.md: D188, D195, D199, D200, D202, D212, D215;
  - GARD_DESIGN.md;
  - CORE_SEAMS_DESIGN.md §3 and §16;
  - RELATIONSHIPS_DESIGN.md;
  - SOTA_ORIGIN_OF_LIFE.md;
  - SOURCE_LAYOUT_MOVES_DESIGN.md (the target layout).
- **Code read:**
  - OL1's package and `validation/assembly_lineages_v2/` at `ol1-laws` 06ee359e;
  - @1's fission, continuation, lineage-operator and type-family modules and its kernel's
    docstring;
  - `records/relations.py`'s vocabularies;
  - `registry/model_table.py`.
- **Cited from memory, not read for this note:** Jensen's inequality, Laplace's law, Smoluchowski's
  rate and the inspection paradox. No web search was made.
