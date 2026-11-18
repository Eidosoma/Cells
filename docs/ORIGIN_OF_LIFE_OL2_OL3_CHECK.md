# Origin of life, OL2 and OL3: the design check (docs only)

**Status: the lead ruled on Q1–Q21 on 18 November 2026,** in §0.2c of
`docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md` (main 5f2d16ed). This note is amended to cite those rulings.
- **§0.2b–c are the authority.** OL5 builds from them, never from this note. Where this note and
  §0.2c differ, §0.2c holds.
- **The probes that rule 9 and the rulings asked for were added after them** (§2.2, §1.6 and
  §1.3). None disagrees with a ruling.
- **Scope.** Docs only until the lead says move 2 has landed. Branch `ol2-design-check` from main
  bbcbec69.
- **OL1** was read at `ol1-laws` 06ee359e. Its engine package is unchanged since c685d821. OL1 has
  not landed: once it does, §1.1, §1.4, §4 and claim X2 are diffed against the landed head.
- **OL5's references were not read.** While orienting, only the last three commit subjects of the
  `ool-references` branch were listed, and nothing else.

**Engine models: none run.** This note plans the models of OL2 and OL3 on `cells.assembly_lineages@2`
(§1, §2).

**Marks.**
- **R:** ruled (§0.2a, §0.2b, §0.2c, D215). "Rule n" with no section means §0.2c's rule n.
- **S:** settled: standard physics, a derivation or a probe.
- **P:** proposed here and not ruled. None remains that is a physical choice.

**Evidence:** `/mnt/workspaces/Cells/ol2-check-20261118/`.
- `probe_rule7.py` and `probe_floor.py`: exact fractions.
- `probe_lumen.py`: decimal arithmetic at 60 digits, because V_sph and ln V are irrational.
- The outputs and a README.

## 0. Summary

| Item | Finding or proposal |
| --- | --- |
| How OL2 enters OL1's kernel | OL1's three hooks keep their kind: reaction laws (θ⁺ and an extent on m), a factor on m, and terms of F. OL2 adds a geometry kind and a population structure for K assemblies sharing one pool (§1) |
| Invariance | A new key is absent unless its feature is declared, and an absent key is never written (rule 1), so OL1's world ids and fingerprints stay as they are. New behaviour enters only through new token values and new laws, chosen statically, so OL1's programs are unchanged (§4) |
| The reverse rate when V moves (§0.2b rule 2) | OL1's form carries over exactly. The lumen's ideal part is taken at X = 1, the rest of the lumen is an excess term, and the V(m) normalisation is a factor on m (§1.4). Probe L1: this kernel form equals the pair rule at all 93 reverses (relative 2e-58), and both close 40 of 40 squares; the products' rule at V(m) fails 23. Re-run under rule 6's c_ext, and again with the permeating solute held, the two forms still agree (§1.3) |
| Rule 7 | **Ruled C3x, which the added probe now confirms** (rule 9). At equal weights, C3x is the balanced exchangeable hypergeometric exactly, with total variation 0, in all six cases, including N mod k = 2 (N = 5 and 8 at k = 3). C1, with G1's size vector, fails that reading at N mod k = 2 (TV 1). The properties do not fix the law at unequal a_L (§2.2) |
| The lumen split | Ruled (rule 10): multinomial at weights V_sph(A_j)/Σ V_sph, conserving and jointly exchangeable with the membrane (§2.3) |
| The floor | Ruled to count area (rule 5). Probe: closure and the stationary law stay exact under either floor; only the reachable count changes, and a step that keeps the area fires below the floor (§1.3) |
| D199's debts | Every descendant: the shared pool's slots, with relations rows. External help: a sources row for every supply and every payer. Labels come in OL3 (rule 17) (§3) |
| Questions | Q1–Q21 are ruled (§7). U1, the estimate, is for the user |
| Estimate | OL2 7–11 and OL3 6–9.5 agent-days, labels included, after rules 8, 16 and 17. §8 gave 5–8 and 2.5–4 (§8 here) |

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

### 1.2 The components (R where §0.2c cites; the IDs are rule 15's)

| Component | ID (interface) | The world declares | In the kernel | Records and refusals |
| --- | --- | --- | --- | --- |
| **Geometry** | `cells.bilayer_geometry@1` (new: `cells.assembly_geometry@1`) | A `geometry` block: the law; an area quantum q (m²); each membrane species' area per molecule per leaflet as an integer k_i of quanta, with its rounding to q declared (rule 4); `vesicle_floor` in quanta, W_floor ≥ 1, provenance `unsourced` (rule 5); `closure_cost_kT` {value, provenance `unsourced`}; `sigma_max_N_per_m` with its source | W(n) = Σ n_i k_i, an exact int64, so A = qW/2; R = (A/4π)^½, V_sph = A^(3/2)/(6√π) and v are derived, never stored (R4). It supplies A(m) and R(m) to the encounter laws. Its F is C_close for each living vesicle: a constant whose change is 0 at every step, entering only where the number of vesicles changes (rule 8) | Rows: W, A, V, v and σ. Refused: a membrane species without k_i; a founder below the floor; a floor without `last_molecule: kept` (rule 5) |
| **Phase exchange** | `cells.phase_exchange@1` (`cells.reaction_law@1`) | A join of one molecule from the pool into the membrane, of the same species, in the join's direction (rule 2). Its constant's key matches the token: `insertion_velocity_m_per_s` (k_ins) or `diffusivity_m2_per_s` (D_i). The token `exchange_encounter` (§0.2b rule 1; conditional, rule 1) | θ⁺ is the pool's activity (n/X_pool, or c/c0 when held). The extent on m is A(m)·ρ0 (`insertion_area`) or 4πR(m)·ρ0 (`diffusion_radius`), with ρ0 = N_A c0. The leave comes from F | Refused: no geometry; a step declared as the leave; a change of species; a key that does not match the token |
| **Permeation** (§0.2b rule 6) | `cells.membrane_permeation@1` (`cells.reaction_law@1`; rule 15) | An entry of one molecule from the pool into the lumen, of the same species (rule 2). Its key is `permeability_m_per_s` (P_s) | θ⁺ is the pool's activity. The extent is P_s·A(m)·ρ0 (`permeation_area`). The exit comes from F | Refused: no geometry or no lumen; a step declared as the exit |
| **Osmotic lumen** (§0.2b rule 2) | `cells.osmotic_lumen@1` (`cells.free_energy_term@1`, excess) | `lumen_volume: osmotic` (a new value; `declared` keeps its meaning); a free-energy entry with `outside_osmolarity_mM`, c_ext, the outside's total osmolarity, held (rule 6); a lumen block without `volume_L` | F_osm(n) = −N_L(n) ln(N_A c0 V(n)) + N_A c_ext V(n), with V(n) = min(V_osm, V_sph(A(n))), V_osm = N_L/(N_A c_ext), and N_L every lumen species (rule 6). The lumen's ln X in the layout is 0, so `cells.ideal_mixing@1` carries only μ° and ln n! there. Its factor on m is X(V(m))^(1−α_L) for a lumen-locus step with one reactant molecule, the only lumen-reactant step admitted (rule 7), and so 1 (§1.4) | Rows: V, Δp and σ, and for a finite pool the largest relative drift of the pool's solute osmolarity against c_ext (rule 6). Refused: osmotic without a geometry or a lumen; `volume_L` declared; c_ext below the declared pool solutes' total, for the world and for each transfer's fresh pool (rule 6); rule 7's steps |
| **Lysis** (§0.2b rule 3; rule 8) | Part of the osmotic lumen, with the geometry's σ_max | — | An event whose end state has σ > σ_max fires at its pair-rule rate and ends the life `lysed`. The lumen's and the membrane's molecules return to their pool places as monomers. q = −(F_after − F(n)) + w, where F_after drops the vesicle's terms and its C_close | A lysis table: time, slot, key, σ at the end state, the returned counts. The status `lysed` (one assembly), or a freed slot (a shared pool). `lysed` enters the next relations version, which OL2 adds (rule 8). Refused: a membrane or lumen species without a pool place; a founder beyond σ_max |
| **Vesicle floor** (§0.2b rule 4; rule 5) | In the geometry block | W_floor, in quanta | A pair whose step changes the membrane's area, with an end state below W_floor, has rate 0, tested on the end states. A step that keeps the area fires at its own rate. A division is admitted only if every daughter is at or above the floor | — |
| **Selection order** (rule 5, R as a requirement) | — | — | Each bundle declares its fold order and its map from uniforms to events. One assembly: OL1's. A shared pool: §1.8 | `run.json` declares both |
| **Shared pool** | `cells.shared_pool@1`, the first `cells.population_structure@1` (rule 15) | A `population` block: the structure; K slots, a capacity bucket; the assemblies' founders (membrane and lumen counts). `founder` gives the pool | State: the pool's counts plus [K, P_asm] counts, each slot's occupant key and its alive flag. F = F_pool + Σ_slots F_asm. Draws come from the reserved `world` domain (5) (rule 14) | Rows per slot, with occupancy. Refused: more founders than K; `population` under `single_lineage` |

### 1.3 New keys and token values (rules 1, 5 and 6)

| Key or value | Required when | Refused when | Absent means |
| --- | --- | --- | --- |
| `geometry` | Any step's law is phase exchange or permeation, or `lumen_volume` is `osmotic` | — | No areas. `count_on_m` holds on every membrane-locus step, as in OL1 |
| `conventions.exchange_encounter`: `insertion_area`, `diffusion_radius` | `geometry` is declared (rule 1's "each world declares one", read as each world with a geometry) | No geometry | OL1's six tokens exactly |
| `lumen_volume: osmotic` | — | No geometry or no lumen | `declared` keeps OL1's meaning |
| `vesicle_floor` (quanta, W_floor ≥ 1; rule 5), `closure_cost_kT`, `sigma_max_N_per_m` | `geometry` (σ_max is required under `osmotic`, rule 8) | Outside `geometry` | — |
| `outside_osmolarity_mM`, the total (rule 6) | `lumen_volume: osmotic` | Below the declared pool solutes' total, or below a transfer's fresh pool's | — |
| `population` | `execution.mode: shared_pool` | `single_lineage` | One assembly, as in OL1 |
| A step's encounter constant | Its law | Any other law | — |

- **`to_dict` never writes an absent key.** A written default would move every OL1 world's id
  (the SHA-256 of its canonical JSON) and its fingerprint.
- **A world with a geometry and `lumen_volume: declared`** is admitted: its extents come from areas,
  and its lumen's volume is constant.

**The probes of rules 5 and 6, added after the rulings (S):**
- **Rule 5, the area floor** (`probe_floor.py`, exact). The world is a membrane of A (k = 1) and its
  dimer B (k = 2), whose dimerisation keeps the area.
  - Under either floor, the 24 squares close and the stationary law is exp(−F) on the truncated
    space (total variation 0).
  - Only the reachable counts change: 37 states under the area floor (W ≥ 6), 39 under a molecule
    floor (N ≥ 4).
  - At a probe state below both floors, the area-keeping dimerisation fires at its own rate
    (4/9 forward, 3/5 reverse), and the join is 0. Under the molecule floor both are 0.
- **Rule 5 in the lumen world** (L7). It has one membrane species, so W = N: its closure, counts and
  results are unchanged. Below the floor, an entry fires at its own rate.
- **Rule 6, c_ext as the total** (L6).
  - **The finite world re-run** at c_ext = buffer + pool solutes (1.175): it is not refused, and
    the pool's solute drift against c_ext is at most 0.149. Its 40 squares close, and the kernel
    form equals the pair rule at 93 reverses (2e-58).
  - **A world with the permeating solute held:** 48 squares close, the two forms agree at 110
    reverses, and the stationary law is the grand weight exp(−F + s·μ_held) (1e-59).
  - **Van 't Hoff:** a floppy lumen's mean volume is the impermeants' volume, n_I/c_buf, to
    relative 5e-3, 1.2e-3 and 3e-4 at n_I = 20, 80 and 320. With c_ext as the buffer alone it stays
    a third too large, at 1/(1 − c_S/c_buf).
  - **L5** is unchanged: V(n) is F's minimiser for any held c_ext once every lumen species
    counts.

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
- **The claims are the ones §0.2b rule 2 names:** cycle closure and the exact-F identity.
  - "The reverse is the products' rule at V(m)" is false wherever V moves.
  - Probe L1, on a closed world with 22 floppy and 32 tense states, has three arms:
    - this kernel form: OL1's reverse at X = 1, the same extent on m, times
      e^(F_osm(n′) − F_osm(n)). It equals the pair rule's reverse a⁺·e^(ΔF − w) at all 93 reverses
      (largest relative difference 2e-58);
    - the pair rule and the kernel form each close 40 of 40 squares (largest |ln ratio| 1e-59);
    - the products' rule at V(m) fails 23 of 40 (largest 0.23).
  - Probe L2: the pair rule's and the kernel form's stationary laws are exp(−F)/Z to a total
    variation of 3e-59, and the products' rule's is off by 0.031.
- **No new reverse path in the kernel.** The V(m) factor joins g(m) as a factor on m, and F_osm is
  one more excess term.
  - Both read their areas exactly from integers: the factor and the encounter extents at
    W(m) = W(n) − Σ_e k_e (n_e − m_e), and F_osm at the two end states.
  - So the forward at n and the reverse at n′ compute the same s(m), bit for bit.
- **The `declared` path is untouched.**
  - The layout keeps OL1's ln X = ln(N_A V c0), and there is no factor and no F_osm.
  - The Structure gains a field `lumen` (`declared` or `osmotic`), and the kernel branches on it at
    trace time, so OL1's worlds trace OL1's program.
- **Under rule 7, no admitted step's rate depends on V(m) at all** (§1.6).
  - The only lumen-reactant steps left are lumen-locus steps with one reactant molecule, whose
    factor is X(V(m))^0 = 1.
  - So in OL2's first worlds the volume enters only through the exact ΔF.

### 1.5 Areas in integer quanta (rule 4)

What follows from rule 4 (S):

- **The quantum.** Each a_L,i = k_i·q, so W(n) = Σ n_i k_i and A = qW/2.
- **Exact integer identities:**
  - the floor;
  - the split's conservation;
  - the cuts of C3x (§2.2);
  - W(m) for both directions of a pair.
- **Float64 comparisons, each declared:** V_osm against V_sph, σ against σ_max, and D2's admission,
  36πkV² ≤ A³.

### 1.6 The empty lumen at m (rule 7)

The evidence behind rule 7 (probe L4, S). In the floppy regime V(m) = V_osm(m), which is 0 when m's
lumen is empty. The factor X(V(m))^(1−α_L) then behaves as follows:

| Step | On m | At the firing state's V(n) |
| --- | --- | --- |
| Lumen locus, one reactant molecule (a lone molecule changing form) | 0⁰: rule 2's 0/0, whose cancelled form is 1 | 1 |
| Lumen locus, two reactant molecules (the last two) | 1/0 = +inf. It is not 0/0, so no cancelled form exists | Finite (0.5 per unit k in L4's units) |
| Membrane locus with a lumen reactant (an exit declared as the forward) | X(V(m))^(−α_L) = +inf | Finite |
| The extent on m with the normalisation at n (one reactant) | X(m)/X(n) = 0, so the lone molecule is frozen | — |

**Ruled (rule 7):** parse refuses the two singular rows under `osmotic`. The question reopens with
lumen chemistry (OL4, OL8), where taking the lumen's X at the firing state's V(n) avoids the
singularity, with the reverse still from the exact ΔF.

### 1.7 Steps under `count_on_m` once a geometry exists (rule 3)

**What OL1 does.**
- Under `count_on_m`, OL1's permeation fires at an empty membrane with E(m) = N(m) − c + 1:
  1 under `multinomial`, 0 under `multinomial_less_one`. That agrees with §0.2a.
- §0.2b rule 6's `permeation_area` makes the same rate 0 by geometry, since A(m) = 0.

Here "physical world" means a world that declares a geometry. D215 uses the phrase for the token
pair `multinomial` with `kept`, and a geometry world may declare either measure (X2).

**Ruled (rule 3)**, as proposed:
- geometric encounter laws for cross-phase steps;
- `count_on_m` only on all-membrane steps;
- the other interfaces refused until declared;
- worlds without a geometry unchanged.

What follows (S):
- **In a geometry world the floor (W_floor ≥ 1, rule 5) makes the empty membrane unreachable.**
  A(m) = 0 arises only in a probe's rate table, where permeation's rate is 0 by geometry.
- **An entry at a sub-floor probe state fires** at its own rate, since it keeps the area (rule 5).

### 1.8 The shared pool (R5; §0.2b rules 2 and 5; rule 14)

- **F is additive over the pool and the assemblies** (S, since they are separate phases).
- **Channels:**
  - each slot has its steps' 2R channels;
  - the pool's own steps (pool locus) form the pool group.
- **The selection map (rule 14):**
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
- **c_ext is the outside's total osmolarity, held** (rule 6). It is exact for held pool species. For
  a finite pool it is a declared approximation, and the run reports the drift (§1.3's probe).
- **A world with K = 1 has the single assembly's rate table** (S). Its stream differs, so that is a
  check on rates, not a bitwise claim.
- **Lanes are worlds** (§5.2 of the design note).

## 2. OL3

### 2.1 Shear fission (D2): `cells.shear_fission@1`

- **The schedule:** declared times, or a Poisson rate on the `schedule` domain (6) (rule 14), each
  event with a stress τ.
- **At an event,** each living assembly is tested in slot order (rule 12). It needs:
  1. τ ≥ τ_crit (declared, with its source);
  2. v ≤ k^(−1/2), that is, 36πkV² ≤ A³ (S);
  3. then the split (§2.2, §2.3);
  4. then every daughter at or above the floor, in area (rule 5). Otherwise the fission is refused
     and recorded, and the parent stays (rule 12).
- **k** is declared per schedule (rule 11).
- **Unequal daughters hold at least what equal ones hold** (S, Jensen). A^(3/2) is convex, so
  Σ_j V_sph(A_j) ≥ k·V_sph(A/k) whenever Σ_j A_j = A. The equal-sphere test is therefore
  conservative for C3x's unequal areas.
- **A daughter born beyond σ_max lyses at birth** (§0.2b rule 3).
- **The draws:** domain 2, in rule 9's and rule 10's order. The counter counts the parent's
  attempts (rule 12).

### 2.2 Rule 7: the membrane split (rule 9; probe `probe_rule7.py`)

**The cases.** Sixteen parents, every law exact by enumeration:
- six at equal weights: N = 4, 5, 6 and 7 at k = 2 or 3, and, added after the rulings, N = 5 and
  N = 8 at k = 3, where N mod k = 2;
- ten at unequal integer weights (1:2, 1:3, 2:3, 1:2:3, at k = 2 or 3), two of them added with
  N mod k = 2: n = (3, 2) and (4, 4) at weights 1:2 with k = 3.

**The targets are equal** (W/k; rule 9's "first worlds"). A declared size distribution is a later
token value and was not probed.

**P2 is rule 9's reading:** the hypergeometric on the balanced size vector, in a random order. The
note's first reading, G1's size vector in a random order, agrees with it only where N mod k ≤ 1,
which is all that the first twelve cases had. The columns P1–P3 are the lead's three properties;
areas and the device are this note's criteria.

| Rule | What it does | P1 | P2 (rule 9) | P3 | Areas (mean \|W_j − W/k\|, unequal) | Device |
| --- | --- | --- | --- | --- | --- | --- |
| C0 | G1's rule: floor(N/k) molecules to each daughter in label order, the last takes the rest | ✓ | ✗ (TV 1/2–1) | ✗ (TV 1, in 10 cases) | Areas ignored: 1/3–8/5 | Yes |
| C1 | C0's sizes in a random order | ✓ | ✗ at N mod k = 2 (TV 1) | ✓ | Areas ignored: 1/3–8/5 | Yes |
| C1b | The balanced sizes in a random order (added) | ✓ | ✓ | ✓ | Areas ignored: 1/3–6/5 | Yes |
| C2 | Fill each daughter until its area reaches W/k; the last takes the rest | ✓ | ✗ | ✗ (4/15–1) | 4/15–58/45; the straddling molecule lands in the earlier daughter (bias up to +1) | Yes |
| C3 | Cut at the prefixes nearest t·W/k, ties low, blocks in label order | ✓ | ✗ | ✗ (4/15–1) | 4/15–4/5 | Yes |
| C3c | C3 with a fair coin at each tie | ✓ | ✗ | ✓ at k = 2; ✗ at k = 3 (1/5–1) | 4/15–4/5 | Yes |
| **C3x** | C3, with the blocks given to the daughters in a uniformly random order (rule 9's procedure) | ✓ | **✓** (TV 0 in all six) | ✓ | 4/15–4/5, under w_max/2 per cut | **Yes:** G1's ranks, an integer prefix sum, an argmin per cut, and k uniforms |
| C4 | Uniform over labelled assignments at the most balanced achievable areas | ✓ | ✓ | ✓ | 0–1/2 (0 wherever the targets can be met exactly) | No: a constrained sampler (a dynamic programme over areas); host only |
| C5 | A random order, cut where a prefix's area is exactly W/2, otherwise redraw | ✓ | ✓ | ✓ (defined in 5 of 16) | 0 | No: unbounded redraws, and undefined when W/2 cannot be reached |
| Plant | Binomial labels (G1's `binomial`) | ✓ | ✗ | ✓ | — | — |
| Plant | Independent samples of floor(N/k) | ✗ | ✗ | ✓ | — | — |

**The size multisets at N mod k = 2, equal weights (rule 9's example):**
- C3x, C1b and C4 always give {1, 2, 2} at N = 5 and {2, 3, 3} at N = 8: the balanced vectors.
- C0 and C1 give G1's {1, 1, 3} and {2, 2, 4}.
- C2, C3 and C3c give the balanced multisets, but in a fixed label order (TV 2/3).

**Findings (S):**
1. **P1 holds for any rule that assigns whole molecules,** so it separates only the plant.
2. **P2 and P3 conflict in G1's form when k does not divide N,** and rule 9 resolves it with the
   balanced vector in a random order.
   - Floor-to-first is the hypergeometric given its sizes, but its first daughters are always the
     smaller: a total variation of 1 under relabelling.
   - C3x, C1b, C4 and C5 (where defined) match rule 9's reading exactly at every equal-weight case
     (TV 0). C1 matches it only where N mod k ≤ 1.
   - **Why C3x gives the balanced vector (S):** its cuts at equal weights are the integers nearest
     t·N/k, whose differences are ⌊N/k⌋ or ⌈N/k⌉, with N mod k of them the larger.
   - G1's D1 keeps floor-to-first for the GARD limit (rule 9).
3. **k = 3 separates reversal symmetry from exchangeability.** C3c passes at k = 2 and fails at
   k = 3.
4. **Fill-to-area rules size-bias the straddling molecule.**
   - At weights 1:2 with n = (3, 2), the straddler is the larger species with probability 3/5,
     against an area share of 4/7 and a count share of 2/5.
   - First-reach gives the straddler to the earlier daughter.
   - Nearest cuts with a random daughter order remove the bias, so each daughter's mean area is
     its target.
5. **The three properties do not fix the law at unequal a_L.**
   - The rules that pass differ by up to a total variation of 1.
   - C4 and C5 differ by 3/77 at weights 1:2 with n = (4, 2).
   - At N mod k = 2 and weights 1:2, C3x stays exchangeable (TV 0). Its areas for n = (4, 4) are
     {4, 4, 4} with probability 3/7 and {3, 4, 5} with 4/7. C4 always gives {4, 4, 4}.

**Ruled C3x (rule 9), and the probe now confirms it.** Rule 9 gives its procedure exactly, as the
authority: the ranks, the cuts, the daughter order and the uniforms' order. The probe implements the
same procedure, enumerated:
- its constrained argmin (c_t ≥ c_(t−1)) equals the clamped global argmin used here, ties
  included, since |k·S_c − t·W| is V-shaped in c;
- its uniform daughter order is enumerated over all k! orders.

A daughter's key is the next count of the parent's sub-lineage, in daughter order (relations §1.3).

### 2.3 The lumen split (rule 10)

- **§4.4's weights V_j/V are circular**, which is why rule 10 takes them from the membranes.
  - A daughter's V depends on its own lumen count, which is the split's outcome.
  - The daughters' volumes need not sum to the parent's, since water moves.
- **Ruled (rule 10):** p_j = V_sph(A_j)/Σ_l V_sph(A_l). The uniforms come after C3x's, in rule 10's
  order and with its cumulative rule.
- **The probe:**
  - conservation, and the joint (membrane, lumen) law's exchangeability, hold exactly for weights
    A_j/A and 1/k, with C3x and with C4;
  - rule 10's weights are irrational, but have the same structure: a symmetric function of each
    daughter's own membrane, so the same result holds;
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
    censored (rule 13).
- **Keys** follow relations@1 §1.3.

### 2.6 Serial transfer: `cells.serial_transfer@1`

- **At declared times:**
  - K_keep living assemblies are drawn uniformly without replacement, all of them if fewer live,
    from the `schedule` domain (rule 14);
  - the rest end `removed`;
  - the pool is replaced by the declared fresh composition, with c_ext unchanged. The fresh pool's
    solutes may not exceed c_ext (rule 6).
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
- **@1's files** (`runner.py`, `records.py`, `fission.py`, `continuation.py`, `keys.py`) are this
  builder's for OL3's shared loop (rule 16).
  - They are edited only behind @1's invariance gate, as rule 16 lists it.
  - The probe-set comparison moves into the checkout with OL2's invariance gate.
  - No exemption widens by default.
- **The cost is in §8.**

## 3. What D199 still owes, for OL2 and OL3

### 3.1 Every descendant

| Mode | What lives | Rows (`cells.relations@1`, and the next version for `lysed`) |
| --- | --- | --- |
| A shared pool | Every daughter, up to K slots; a full set of slots stops the run (rule 13) | `lives`: founders and every daughter, with parent, share and generation. End reasons: `divided`, `removed` (a transfer), `censored`, and `lysed`, which OL2's new relations version adds with tissue division's rows unchanged (rule 8) |
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

### 3.3 Material provenance: labels in OL3 (rule 17)

Rule 17 places labels in OL3, as @2's instance of RELATIONSHIPS_DESIGN §2. The table is this note's
reading of how each event moves them (S):

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

## 5. Claims for §7.1, kept consistent with §0.2b–c

OL5 builds from §0.2b–c and the design note, not from this table. The table states the claims as
this note reads those rulings. Each claim is proved once, at the cheapest level, with its planted
error. Symbols:
- n′ = n + ν, and m = min(n, n′);
- ρ0 = N_A c0;
- X(V) = N_A c0 V;
- a_i is a pool activity: n_i/X_pool, or c/c0 when held.

| ID | Claim | Cheapest proof | Planted error |
| --- | --- | --- | --- |
| G1 | A = (q/2) Σ n_i k_i; R = (A/4π)^½; V_sph = A^(3/2)/(6√π); v = V/V_sph ≤ 1 | Closed forms on random states | a_L per bilayer, so A doubles |
| G2 | Rule 5. A pair whose step changes W, with an end state below W_floor, has a⁺ = a⁻ = 0. A step that keeps W fires at its own rate at any probe state. A closed world's law is exp(−F)/Z on the truncated space | Rate tables at a probe state below the floor; exact enumeration (as `probe_floor.py`) | The floor on every step: a molecule floor, which zeroes the area-keeping dimerisation. Also the floor tested on m. Both are caught by the rate table, not the stationary law, which zeroing a pair does not change |
| G3 | C_close changes no rate. It enters ΔF only as +(k − 1)C at a fission and −C at lysis | Rate tables equal for C = 0 and C ≠ 0 | C_close charged per molecule |
| X1 | a⁺(n) = k_ins·A(m)·ρ0·a_i (insertion area) or D_i·4πR(m)·ρ0·a_i (diffusion radius), with m = n. a⁻(n + e_i) = a⁺(n)·e^(F(n + e_i) − F(n) − w) | The kernel identity on random states; Kolmogorov's test on squares | A first-order leave with no tension term; the extent taken at n′ |
| X2 | At equal a_L, insertion area and c = 1: the rate table equals the `count_on_m` world's with k_f = k_ins·(qk/2)·ρ0, on every pair whose end states are both at or above the floor | Rate tables, to rounding | c = 0 in one of the two (N against N + 1) |
| X3 | One amphiphile, with a finite pool and no lumen: the stationary law is exp(−F)/Z. In the large-vesicle limit, c_cac = c0·e^(μ°_bil − μ°_sol) | Exact enumeration; the closed form | The transfer potential's sign |
| P1 | Entry a⁺ = P_s·A(m)·ρ0·a_s; exit = a⁺·e^(ΔF − w). In the large-N limits, with c_ext the total (rule 6): floppy, n_s/N_L = c_s/c_ext and V → n_imp/(N_A(c_ext − c_s)), the impermeants' van 't Hoff volume; tense, n_s = N_A·V_sph·c_s | The kernel identity; exact stationary law (as L6) | P·A(n′); c_ext without the permeant's concentration (V stays a third too large in L6) |
| L1 | F_osm = −N_L ln X(V(n)) + N_A c_ext V(n), with N_L every lumen species and c_ext the outside's total osmolarity (rule 6). V(n) = min(N_L/(N_A c_ext), V_sph(A)) is F's minimiser over V ≤ V_sph | Closed form; minimisation over V | A lumen species left out of N_L. Probe L5: V is then not the minimiser |
| L5 | Rule 6. A world whose c_ext is below its declared pool solutes' total is refused, and so is a transfer's fresh pool. A finite pool's run reports the largest relative drift of its solute osmolarity against c_ext | Parse; one run | Such a world accepted; the drift not reported |
| L2 | a⁻(n′)/a⁺(n) = e^(F(n′) − F(n) − w) for every pair, and every square closes, in both regimes and across the kink | The kernel identity; Kolmogorov's test | The reverse as the products' rule at V(m) (probe L1) |
| L3 | σ = max(0, Δp·R/2), with Δp = k_BT(N_L/V − N_A c_ext). σ is continuous at V_osm = V_sph. A join's lumen part of ΔF is −σ·a_L/2·(1 + O(1/N)) | Closed forms; probe L3 | Δp·R, with no 1/2 |
| L4 | A closed world that crosses the kink relaxes to exp(−F)/Z | Exact master-equation solve | The products' rule at V(m) (probe L2) |
| Y1 | Rule 8. n → n′ with σ(n′) > σ_max fires at a⁺(n) and ends the life `lysed`. Its molecules go to their pool places as monomers, and q = −(F_after − F(n)) + w, with F_after holding no vesicle and no C_close | A small world whose only route crosses σ_max; the ledger closes | Lysis as a zero rate; lysis tested on m; C_close kept after lysis |
| Y2 | A daughter born with σ > σ_max lyses at birth, and that is recorded | A forced split | No record |
| S1 | Two assemblies on one finite pool relax to exp(−F_pool − Σ F_asm)/Z | Exact enumeration | A join that reads the pool at n′ |
| S2 | The declared map replays every event (§1.8) | The host oracle, with common uniforms | Groups folded in key order after a fission |
| S3 | P(channel j) = a_j/a0 | Exact rationals over the map | The group chosen uniformly |
| S4 | A world with K = 1 has the single assembly's rate table | Rate tables | — |
| D1 | Admitted only if τ ≥ τ_crit, 36πkV² ≤ A³ and every daughter is at or above the floor in area (rule 5), with k declared (rule 11) | Closed forms at the thresholds | The threshold at k^(−1/3) |
| D2 | Rule 9's C3x. P1 on counts. P2: at equal a_L, the hypergeometric on the balanced size vector in a random order. P3: the joint pmf invariant under relabelling | Exact pmfs by enumeration at small N, including N mod k = 2 (as `probe_rule7.py`); χ² at N = 80 with registered power | Floor-to-first (P2, P3); G1's sizes in a random order at N mod k = 2 (P2); binomial labels (P2); independent samples (P1) |
| D3 | Rule 10. The lumen: multinomial at weights V_sph(A_j)/Σ V_sph, with the ruled uniform order, conserving and jointly exchangeable | Enumeration | Sequential binomials at p = 1/k with k = 3; independent binomials; weights by block position |
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
| `test_assembly_lineages_v2_lumen.py` | L1–L5, Y1–Y2 | 2 |
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
  - @1's gate for the shared loop, as rule 16 lists it;
  - crossrev and the results gate unchanged, since no tissue file is touched. The new relations
    version leaves tissue division's rows unchanged (rule 8).
- **D187:** one composed world (a finite pool, two assemblies, shear division and a transfer, with
  every ledger closing and replay checked), and one baseline world in the results gate.
- **For OL5:** the probe driver gains OL2's and OL3's roles, and OL5 judges against its saved
  outputs.

## 7. Questions, and the lead's rulings (§0.2c)

**All 21 are ruled in §0.2c** (main 5f2d16ed). §0.2c is the authority, and this table only maps
the questions to its rules.

| Question | Rule | As this note proposed? |
| --- | --- | --- |
| Q1, conditional keys | 1 | Yes |
| Q2, N_L | 6 | Yes: every lumen species counts |
| Q3 and Q4, the empty lumen at m | 7 | Yes: (a). Q4 is moot until lumen chemistry |
| Q5, directions | 2 | Yes |
| Q6 and Q7 (the coordinator's), steps in geometry worlds | 3 | Yes |
| Q8, the floor | 5 | **No:** area in quanta, W_floor ≥ 1. Only a pair that changes the area is zeroed |
| Q9, integer areas | 4 | Yes, with the rounding to q declared |
| Q10, lysis | 8 | Yes. OL2 adds `lysed` as the next relations version |
| Q11, rule 7 | 9 | C3x, now confirmed (§2.2). **P2's reading differs:** the balanced size vector, not G1's |
| Q12, the lumen's weights | 10 | Yes: (a), with the uniforms' order ruled |
| Q13, D2's k | 11 | Yes: declared |
| Q14, shear events | 12 | Yes |
| Q15, a full set of slots | 13 | Yes |
| Q16 and Q21, streams | 14 | Yes |
| Q17, IDs | 15 | Yes: both interfaces |
| Q18, @1's files | 16 | This builder owns them, behind @1's gate. The probe-set comparison moves into the checkout, and no exemption widens by default |
| Q19, labels | 17 | Yes: in OL3 |
| Q20, c_ext | 6 | **No:** the outside's total osmolarity, held, with the refusal and the drift report |

**No probe disagrees with a ruling** (§1.3, §2.2). This check leaves no question open for the lead.

**For the user (marked):**
- **U1 (for the user, through the lead): the estimate.** OL2 and OL3 come to about 13–20.5
  agent-days, labels included, against §8's 7.5–12. The difference comes from:
  - D215's shared run loop;
  - D199's relations and labels (rule 17);
  - the next relations version (rule 8);
  - rule 3's lysis.

  The programme was approved whole (U8, 33–51).

## 8. Files and estimate

**Files** are named relative to the family package. Their root follows move 2's map, which is not
committed yet, so no post-move path is guessed here.

| Where | Files |
| --- | --- |
| `assembly_lineages_v2/`, new | `geometry.py`, `exchange.py`, `permeation.py`, `lumen.py`, `population.py`, `division.py`, `transfer.py`, `labels.py` |
| `assembly_lineages_v2/`, changed | `__init__.py`, `interfaces.py`, `conventions.py`, `world.py`, `spec.py`, `model.py`, `kernel.py`, `balance.py`, `ledger.py`, `records.py`, `runner.py`, `streams.py`, `reference.py` |
| `assembly_lineages/` (@1; this builder's for OL3's shared loop, rule 16) | `runner.py`, `records.py`, `fission.py`, `continuation.py`, `keys.py`, and a new shared loop module |
| Records | `records/relations.py`: the next relations version, with `lysed` and tissue division's rows unchanged (rule 8) |
| Registry | `registry/model_table.py`: homes and interfaces |
| Validation | `validation/assembly_lineages_v2/`: `FORMAT.md`, `probes.py`, `registered.py`; @1's probe-set comparison, moved into the checkout with OL2's invariance gate (rule 16) |
| Tests | `tests/assembly_lineage_v2_fixtures.py`; §6's eight files; `tests/test_tiers.json` |

**The estimate** (agent-days, S):

| Milestone | Item | Days |
| --- | --- | --- |
| OL2 | Conditional keys, world blocks and refusals | 0.5 |
| | Geometry: integer areas, the floor, the closure cost, σ_max | 0.5–1 |
| | Phase exchange and permeation | 0.5–1 |
| | The osmotic term, static dispatch and lysis | 1–1.5 |
| | The shared pool: K slots, the world stream, two-level selection, the oracle | 1.5–2.5 |
| | Probe worlds, the ledger, records, FORMAT and OL5's roles; the c_ext refusal and drift report (rule 6) | 1–1.5 |
| | The invariance gate, with @1's probe-set comparison moved into the checkout (rule 16) | 0.5–1 |
| | The next relations version, with `lysed` (rule 8) | 0.5–1 |
| | Tests and tier rows | 1 |
| | **OL2** | **7–11** |
| OL3 | The shared run loop, behind @1's gate (rule 16) | 1.5–2.5 |
| | Shear fission: admission, C3x, the lumen split, shear work | 1.5–2 |
| | Continuation in both modes, slots, keys, relations rows and sources | 1–1.5 |
| | Serial transfer | 0.5–1 |
| | Labels (rule 17) | 1–1.5 |
| | Tests and tier rows | 0.5–1 |
| | **OL3** | **6–9.5** |

## Sources

- **Read:**
  - AGENTS.md;
  - `docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md` (the whole note at bbcbec69; §0.2b–c at 5f2d16ed);
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
