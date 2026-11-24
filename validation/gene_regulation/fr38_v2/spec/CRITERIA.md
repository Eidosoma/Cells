# FR-38's second comparison: criteria, bands and plants

**These are fixed on 24 November 2026, before any reference exists** (D334). Every number here is
a formula's constant, fixed now, and none comes from a reference or an engine run of these worlds.
- "The reference" is the references agent's files (SPEC.md §7).
- "The engine" is `templated_polymerisation@1` with §9's release and FR-42's label owner, through
  `validation/gene_regulation/engine_run.py`, at the registration's frozen revision.
- The pair rule is `validation/assembly_lineages_v2/agreement.py`. It is FR-47's, tagged
  `fr47-shell-exchange-registered-2026-11-24`, and reaches main with FR-47.

## 1. Runs and rungs

**The rungs.**
- Every honest run is made at 2, 1 and 0.5 s (4h, 2h and h, with h = 0.5 s), and judged at h.
- **The retry:** once, for inconclusive runs only, at 1, 0.5 and 0.25 s, with their support runs
  (their blank and twin). It is judged at 0.25 s.

**The engine's runs per rung:**

| Family | Labelled runs | Support runs |
| --- | --- | --- |
| AF | p = 0, p = 1 and p_sched, each with `returned` and `held` | a blank per machine option; the unlabelled twin of p_sched `returned` |
| AN | p = 0 and p = 1 with `returned`; p_sched with `returned` and `held` | the blank (`returned`); the twin of p_sched `returned` |
| B | `p=0.55 returned`, `p=0.55 held` | the unlabelled twin of each |
| C | p_sched `returned`, with the store | the blank, with the store; the twin |
| D | p_sched `returned`, swelling | the blank, swelling; the twin |

**The restart,** at h only: AN's p_sched `returned`, checkpointed at 7200 s through snapshot files
and resumed to 14,400 s.

## 2. The classes

| Class | What | Judged by |
| --- | --- | --- |
| `constant` | The reference's `constant` entries (SPEC.md §4), and three engine-only equalities: each labelled run's physical readouts and checks equal its unlabelled twin's; the resumed run's records, labels included, equal the uninterrupted run's; AF's two blanks equal each other | C1 |
| `derived` | The engine-only identities of C4 | C4 |
| `stepped` | Every other entry against the reference | C2, outside the pair rule, as FR-47's C1 is |
| `spread` | None | A `spread` entry is refused |

- No entry is excluded after a run, and no class changes after it.
- No ruling assigns a class (the first comparison's sixth ruling assigned "zero" to a pool
  difference that was not zero; D313, D316).

## 3. The criteria

**C0, the first read,** before any engine run.
- The judge's reader parses `reference_invented.json`, then each reference file, by SPEC.md §7.
- **It checks:**
  - every unit;
  - every class against SPEC.md §4's rules;
  - every input echoed against SPEC.md;
  - every judged entry's accuracy ≤ 10⁻¹¹ s_y (READOUTS.md §3).
- **It refuses on any fault,** naming it. It also refuses:
  - an engine run whose definition differs from SPEC.md's inputs for its run name (checked to
    10⁻¹² relative, as the first comparison's erratum 1 checked);
  - a missing output time, run or readout;
  - a non-finite value.

  A refusal is never read as a gap.

**C1, constants.** `agreement.judge_constant`, bit for bit, the sign of zero included, at every
rung. One wrong value fails.

**C2, stepped entries against the reference.** For readout r of run w, over its compared times:
- **Compared times:**
  - every output, for every judged series (READOUTS.md §4);
  - for `route2` and `survival`, each sample time.
- **The step differences:** d₁ = max_t |y_2h − y_h| and d₂ = max_t |y_4h − y_2h|.
- **The step estimate,** the larger of the two pairs:

      est = max( d₁ / (2^p − 1),  d₂ / (2^p (2^p − 1)) )

- **The rounding:** e_round = 8 ε S_h s_y, with ε = 2⁻⁵², S_h the number of steps at h, and s_y the
  readout's scale on the engine's own series (READOUTS.md §3).
- **The tolerance:** τ_r = 3 est + e_ref + e_round. Here 3 is Roache's factor of safety, as in
  FR-25's and the first comparison's rules, and e_ref is the reference's stated accuracy (its
  largest over the compared times).
- **Pass:** max over the compared times of |y_h − y_ref| ≤ τ_r.
- **Route 2,** which is not stepped: τ = 3 g(ts) + e_ref + e_round at each sample time, with g(ts)
  the known-rate form's grid error on the engine's own counters (LAWS.md §6; the first
  comparison's erratum 1, Q4). There is no order check.
- **A survival ratio:** τ = the ratio times the sum of its two counts' relative tolerances.

**The declared orders p:**

| Readouts | p | Why |
| --- | --- | --- |
| AF and AN: amounts, the hold, occupancies, extents, `excess_over_blank`, `G_minus_G0` | 3 | SSPRK(3,3) on the gene unit's own variables, with no other writer |
| AF and AN: heats | 2 | Each route's heat is its share of the exact total, by divided-difference potentials: a second-order discrete gradient |
| AF and AN: labels, `released_present_gross`, `survival` | 2 | The share update's split (erratum C) |
| B, C and D: every readout | 2 | Strang's split: A1's turnover and factor (B), the D152 network (C), water's Heun half-steps (D) |

**C3, the order.**
- Where d₁ and d₂ both exceed 10 e_round, the readout is resolved. Its observed order
  q = log₂(d₂/d₁) must lie in [p − 0.5, 3.5], D271's window. Otherwise the run is inconclusive.
- Where either difference is at most 10 e_round, q is reported, not judged.

**C4, the engine-only identities** (`agreement.judge_derived`), each bound stated from arithmetic,
as release_check's:
- **The membership sum.** |Σ_c `label_<row>_c` − `n_<row>`| ≤ 128 ε n_row, at every output, the
  shares' domain.
- **§9.7's identities** (the hold, per producer, each fate row, the machines). Each residual is at
  most FLOOR + 8 ε S max|terms|, with FLOOR the operator's own ledger floor of 10⁻²² fmol.
- **G's identity.** |G − G(0) + Σ heats| ≤ 8 ε S (E + Σ the moving rows' G terms), with E the
  bookings' magnitude.
  - In C the heats include `H_store`.
  - In D the identity is G − G(0) + U(V) − U(V₀) + Σ heats − `W_bath` = 0, with the same form of
    bound.

**Reported, not judged:**
- per readout:
  - the observed order;
  - the effective factor 3 (2^q − 1)/(2^p − 1);
  - the engine's error against the reference at 2h and at h, and their ratio;
- a saturation flag, where that ratio is below 1.5 while the error at h exceeds 10 (e_ref + e_round);
- route 1 against route 2, within route 2's grid error plus erratum C's split bound;
- in arm A, the stage complexes and `W_tx`, and in arm B, A1's own readouts (READOUTS.md §4). For
  each: its gap to the reference, its tolerance as C2 would form it, and its observed order.

## 4. Verdicts

- **A run:**
  - fails if any C1 or C4 entry fails, or any C2 entry fails whose readout's order is inside its
    window or unresolved;
  - otherwise it is inconclusive if any judged readout's resolved order is outside its window. Its
    estimate is then not trusted, and it takes the retry (FR-25's precedence, D278 and D282);
  - otherwise it passes.
- **A refused run** cannot pass. A run refused by the engine at run time is scored refused, and its
  arm is then at best inconclusive.
- **An arm,** after the retry:
  - fails if any of its runs fails;
  - otherwise it is inconclusive if any run is inconclusive or refused;
  - otherwise it passes.
- **A plant** is caught when its criterion fails at any compared entry, or when its run is refused
  by its own books or checks.
- **FR-38's second comparison:**
  - passes when arms A and B pass and every core plant is caught in its must-catch worlds;
  - fails when arm A or B fails, or a core plant is not caught;
  - is inconclusive otherwise.
- **Families C and D** each carry their own verdict, reported beside FR-38's and never deciding it.
  Each passes when it passes and its plant is caught (and, for C, its negative control passes). It
  fails when it fails or its plant is not caught, and is inconclusive otherwise.
- **The verdict is recorded beside D313's failed verdict,** never in its place.

## 5. What a miss in AN means, stated before any run

AN's residue potential (μ°_res = −10.368889) lies outside §3.3's range. It is a declared world for
numerical discrimination, and it claims no biology: no RNA degradation runs this close to
equilibrium. It exists because only there do the gross and net readings differ by more than about
10⁻⁸. Precedent: D306's checker world.

- **A fail in AN fails FR-38's second comparison as registered,** exactly as a fail in AF would.
  - AN has no exemption.
  - It is not dropped, rescaled or re-potentialed after a run.
- **What a fail there would mean:** the engine's treatment of the two-sided loss departs from the
  sheet's law where re-synthesis is about a tenth of the gross loss, or the reference's treatment
  does. That covers:
  - the degradation's one-way parts;
  - the label owner's following of them;
  - the share update with large base-labelled arrivals;
  - the monomers' coupling.

  The code path is the same at every potential. At the sheet's own state such a defect would be
  scaled by e^(y_f), about 10⁻⁸: invisible there, not absent.
- **What it would not mean:**
  - nothing about biology;
  - no failure at the sheet's own potentials, which AF judges on its own.
- **What follows a fail:**
  - a labelled, non-blind diagnosis, by someone other than this registration's author, the judge
    and the checker;
  - it states which side the miss lies on, and the miss's size scaled to the sheet's own state,
    before the user decides anything about FR-38's use;
  - the verdict stands as scored.
- **An inconclusive AN** makes arm A, and so FR-38's comparison, inconclusive after the retry.
- **A domain refusal in AN** (y_f above X_DOM = −1, or c_f above 1 M) cannot occur by the
  registration's analytic bound: even if every molecule of RNA ever present degraded, e^(y_f)
  stays at or below 0.190. If one occurs, the run is scored refused, so arm A is at best
  inconclusive. The diagnosis then starts from that bound.

## 6. The plants

**How they run.**
- **World-data plants** run in their own process, from the registration's snapshot, at h only. They
  are scored with the honest run's tolerance at h.
- **Record plants and mapping plants** act on copies of honest records or of the judge's mapping
  file.
- **Host-side plants** are scoped patches under `validation/`, never in `src/`.

**Sizing.** The references size every plant before any run (SPEC.md §6).
- **The rule:** a must-catch plant's relative distance (|planted − honest|/s_y, at its largest)
  must be at least 10 times the honest relative tolerance expected for the readout that catches it.
- **The expectations,** from a probe of arm A's shape on made-up values (the protocol's
  disclosures):
  - labels and `released_present_gross` 2 × 10⁻⁸;
  - amounts, the hold and releases 10⁻⁹;
  - `G_minus_G0` 10⁻⁸;
  - heats 5 × 10⁻⁸;
  - route 2 10⁻⁵, relative to its s_y.
- **No plant is sized against the stage complexes.**
- **If the references' sizing puts a must-catch plant below its 10×,** the plant is enlarged or
  replaced by a dated amendment before the registration's tag, with the reason, never after a run.
- **If an honest tolerance exceeds a must-catch plant's distance** after the runs, that plant is not
  caught, and FR-38's comparison fails (FR-47's rule).

**The plants.** The core plants are P1 to P7, with P1′ and P1″ (arms A and B). P8 and P9 belong to
families C and D.

| Plant | Mechanism | Kind | Must be caught in | By |
| --- | --- | --- | --- | --- |
| P1 | **The first comparison's confusion:** the mapping pairs the engine's `label_<row>_win` with the reference's `cohort_net_<fate>`, the net tracker | mapping | AN (in AF it is scored and reported) | C2 |
| P1′ | Route 2 at the net rate: the host's net-rate form (LAWS.md §6) on the engine's counters, in place of the known-rate form at k_f | host-side | AN | C2 (route 2) |
| P1″ | The excess over the blank taken for the released molecules still present: the engine's `excess_over_blank_<fate>` paired with the reference's `released_present_gross_<fate>` | mapping | AN, and every idle fate of AF and AN | C2; C1 at an idle fate, where the reference's value is the constant +0.0 |
| P2 | An idle route that leaks: AF's `p=1 returned` with p = 1 − 2⁻³⁰ | world data | AF | C1: the idle releases, release heat and classes are not +0.0 |
| P3a | The window opens one step late: transcription's schedule switches to `win` at 1800.5 s | world data | AN `p_sched returned` | C2 (`label_<row>_win`) |
| P3b | The window closes one step late: back to `post` at 5400.5 s | world data | AN `p_sched returned` | C2 (`label_<row>_win`) |
| P4 | The window marked at completion, not at release (`label: {at: completion}`, the hold carrying the shares) | world data | AN `p_sched returned`; B `p=0.55 returned` | C2 (`label_<row>_win`) |
| P5 | k_s × (1 + 10⁻⁴) in the engine's definition | world data | AF `p_sched returned` | C2 (`n_R_s`, `int_D_R_s`, `label_R_s_*`) |
| P6 | `G_minus_G0` recomputed without the hold's standard term | record | AF `p_sched returned` | C2 (`G_minus_G0`) |
| P7 | AF's p_sched `held` run declared `returned`, judged against the `held` reference | world data | AF `p_sched held` | C2 (`F_pol`, `E_tx`) |
| P8 | The store's forward rate × 1.01 | world data | C | C2 (`n_M`, `n_Mx`, `excess_over_blank`, `label_*_resyn`). **Negative control:** its `pool0`, `pre`, `win` and `post` classes must pass against the honest reference, whose laws do not read M |
| P9 | The gene unit reads the declared V₀ = 1.0 pL for its concentrations and bookings, while water reads the current volume | host-side (FR-43's V₀ plant form) | D | C2 (`n_R`, `n_R_s`, the labels, the release heats, `G_minus_G0`). No negative control: initiation reads the volume, so the releases change too |
