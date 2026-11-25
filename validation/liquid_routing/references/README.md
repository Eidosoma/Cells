# The decimal references of `liquid-routing-v1` (FR-54 and FR-57)

Written by the code-blind references agent from `../spec/` alone (README, SPEC, LAWS, READOUTS, CRITERIA, TABLE,
`inputs.json`, and Amendment 1 of 25 November 2026), before anyone ran the engine on these worlds. No engine code, test,
protocol, design note, decision text or engine output was read. Standard library only: `decimal` at 110 digits (120 inside
the quadratures, 260 in the few checks that need it), published at 40.

**Disclosure of what was in my context.** The harness put into my session, unasked, the text of `AGENTS.md`, a memory index
of one-line project notes, and the subjects of five recent commits. None holds a value of this comparison, and none was
used. Finding the least busy processor listed other agents' command lines (`ps`), of which I read nothing more.

## 1. Files

| File | What it is |
| --- | --- |
| `write_references.py`, `lrrefs/` | The writer. `python -B -P write_references.py --out DIR --revision REV [--only invented\|registered] [--arms 1,3]`, with `PYTHONPATH` empty. The package is loaded by its location, so nothing of the repository is importable |
| `component_tests.py` | The writer's own parts, each alone, against results known independently of it |
| `self_check.py` | An independent program that shares no code with the writer: names, classes, values, plants and margins, all again by other formulas |
| `mutation_tests.py` | Deliberate changes of a published file, each of which `self_check.py` must flag |
| `regenerate.py` | The writer again under two other hash seeds, byte for byte; writes `SHA256SUMS` and `provenance.json` |
| `out/inputs_invented.json`, `out/reference_invented.json` | The invented set (SPEC §8), written and committed first |
| `out/reference_arm1.json` … `arm6.json` | The references |
| `out/component_tests.json`, `out/self_check.json`, `out/mutation_tests.json` | What those three programs found |
| `out/SHA256SUMS`, `out/provenance.json`, `out/run_times/` | Hashes; seeds, platform and versions; run times, apart |

## 2. The layout, where it says more than SPEC §7

SPEC §7's keys are all present in every file, with these additions (the judge ignores keys it does not know):

- `cases`: each case has `accuracy`, the same keys with their bounds. `levels_*` are `[n_T_1, n_T_2]` in fmol.
- `events`: arm 2's block has `class`, `time_s` and `accuracy`. Arm 4's list entries have `amount`, `time_s`, `class` and `accuracy`
  beside `volume_pL`, `loss`, `resident` and `arriving`.
- `plants`: each row has `class` (the check's class), and the S rows say which step-error model sized them. A row of class E has
  `expected_tolerance` "0", `margin` null, `no_margin` true (Amendment 1, item 2).
- `plants_reported`: P8's `H_missing`, one entry per engine plant: the exchange's heat for `P8 event`, and `H_tot` at every output for
  `P8 flow` (the stop row is the run's to show).
- `reported`: check 10's three clauses at the four default starts outside the expansion's domain (Amendment 1, item 1).
- `worlds` of arm 1 hold t = 0 alone (the two levels, class R, and `H_face`, class E): a value at h belongs to a `case`.
- `accuracy` is an absolute bound to three digits, rounded up. A published amount's or closed form's is 1e-39 of the value:
  publication rounds to 40 digits (5e-40), and the computation agrees with its second method to 1e-50 of the value or better
  (`checks`), so the bound is twice what is needed. An integral's adds four times the largest disagreement of its two quadratures.

## 3. Method

| Quantity | First method | Second method | Third |
| --- | --- | --- | --- |
| Amounts and labels of a flow | the propagator by scaling and squaring (Taylor, entrywise 1e-112) | uniformization (Jensen: no squaring, no negative number) | Taylor continuation of y′ = G y; for chains the closed forms of LAWS §4; for arm 6 the eigenvalues of the two-node system |
| `V_K`, `supplied` | exact sums of Q Δt | the propagator with levels 1 (volume as a species) | – |
| `H_tot` of a flow | the state function of LAWS §5 | ideal mixing of finite portions, telescoped, at every registered step | the integral of every holder's rate, at doubling outputs |
| `H_<i>`, `H_face` (arms 5, 6) | tanh-sinh, levels by closed form | graded Gauss-Legendre, levels by Taylor series (no closed form, no squaring) | Σ = `H_tot`; `H_A` in closed form by the dilogarithm; the limit of finite portions |
| Two wells | closed form | the 2 × 2 propagator; the scheme by its explicit stages | D as the integral of the affinity, by two quadratures |
| The default heat | the two-well form | the J̄²/W form | – |
| An exchange, a portion | LAWS §3's and §6's two forms | each other | the state function |
| Arm 6's splits (plants) | decimal P(h/2) E(h) P(h/2) and E(h) P(h) | – | orders 4 and 2 a halving (component tests) |

The published integral is the tanh-sinh value. The propagator's stopping rule is entrywise, so small entries keep their
relative accuracy, and every squaring is of a non-negative matrix (a compartment network has no negative propagator entry).

## 4. Readings of the spec

**Adopted by the lead (Amendment 1), so that the judge can conform:**

1. SPEC §9 check 10, third clause: at the judged default starts of arm 1 only; the four others' three clauses are in `reported`.
   Clauses 1 and 2 also stay in `checks` at those four (they pass). The `eq-mid` stop is in neither list.
2. CRITERIA §6.2: a class-E plant has no margin (P9).
3. CRITERIA §3.2: the sum for `F7`'s L includes `bound_L_S`. I publish n_L_A, n_L_B, n_L_K, n_T_S and n_U_S (R), and no value for
   `n_L_S`, `free_sites_S` and `bound_L_S`: LAWS has no binding law.
4. SPEC §7: `planted_series` is keyed `<world>|<step>` for P7, P11, P14, P15 and P19, `<world>` for P2, P3, P4, P5 and P9. P1, P10,
   P16, P17 and P18 have none.
5. READOUTS §1 and §3: arm 6's `H_tot` is LAWS §8's total (Σ H_holder + H_face); `H5`'s H_A, H_B, H_K are class U, value 0.
6. SPEC §8: every invented name has the prefix `inv-`, and `arm` is 0 in `reference_invented.json`.
7. LAWS §0: N_A and k_B are read as their nearest doubles (the other reading, the exact decimals, differs by 4.5e-17 of RT).
8. `levels_*` are amounts; `cases` carry H_def and B_def at every step; arm 4's events hold `amount`; rows after t = 0 and before the
   first portion, and `label_T_plain_A` at t = 0, are class R with value 0; `plants_reported` holds P8's H_missing.

**Mine, with no effect on a verdict that I can see:**

9. LAWS §11, P3 ("the chain of §4 with b replaced by a (x as honest)"): the equation dn_B/dt = a n_A − a n_B, so B relaxes to V_A x.
   Keeping V_B x in the closed form instead would change the planted amounts by at most 6e-12 fmol.
10. LAWS §11, P11 ("Σ_j P_Kj n_j"): the whole portion that arrives at K, the inlet's own liquid included (a part in 1e13).
11. CRITERIA §6.1, P14 and P15 at class B: listed for `n_T_1` and `n_T_2` (one transfer, two wells).
12. CRITERIA §6.1, P17: the reference sizes it with the exact no-event solution at 16.25 s.
13. CRITERIA §6.2, P19: the expected tolerance is three times `est` of the decimal Strang map; the rounding and accuracy terms of τ,
    which are many orders smaller, are left out. Likewise P5 uses 3 (h/2) TV(r), with r_A monotone (dr_A/dt = −RT Q a (y − x)²/y).
14. SPEC §3.3: arms 3 to 6 publish `H_tot`, so arm 4 has it beside `H_K` (they are equal).
15. READOUTS §3: `supplied` is class R in arm 6 too, and in `J0` it is R with value 0 after t = 0; both labels' amounts in K are E at
    t = 0 ("the collector's contents").
16. SPEC §9 check 11: the fractions are measured against LAWS §9's bounds with the registered steps; arm 6's crossing species are
    measured against the decimal Strang map (their truncation error is not a rounding error), and its energy identity on its own rows.
17. `provenance.revision` is the commit of the Amendment 1 tag, the last spec I read.

**Adopted by the lead for Amendment 2 (both concern the judge, and nothing here):**

18. CRITERIA §3.2 and READOUTS §3's arm 2 "the sums": after the exchange n_T_1 + n_T_2 − supplied is not the start, because the sample has
    left; the sum is n_T_1 + n_T_2 + sample − supplied, over the exchanges before the row, with the run's own event numbers.
19. READOUTS §2: a portion's or an exchange's own supplied amount counts in the scale of its `amount`, `loss` and `heat` (a literal "to
    that time" gives a first portion a scale of 0).

## 5. Checks

The bound and residual of each are in each file's `checks`. Every check of SPEC §9 passes in every file. Families, with the
largest residual over all files, are tabulated in §10. Two kinds of bound: agreement of two decimal methods, 1e-50 of the
quantity's scale; an integral's, 1e-40 of s_F (SPEC §3 asks for 1e-12).

The rounding emulation of check 11 (`lrrefs/emulation.py`) is binary64, written from LAWS alone, and is used for nothing else.
`self_check.py` and `component_tests.py` add to `checks`; they never replace one.

## 6. Plants

Margins (distance over the expected honest tolerance) are tabulated in §10. They are computed from the references alone. P8 has
no margin: its missing heat is in `plants_reported`. P9 has no margin, and its distance is not zero.

## 7. The invented set

Every registered role is represented by the world whose name is the registered one with `inv-` before it. All volumes, flows,
times, amounts and concentrations are mine (a flow of exactly 0 in `inv-J0` and the labelled share of 1 are roles; the
temperature is the registered one, which SPEC §8 does not list). Every node's throughput is at most 1 except in the expected
refusal (`inv-F6 h=8.25 refused`, 1.326 at B), and kh of every default-heat run is at most 0.01465 (the expected stop holds a
trace, as `eq-tr` does, so its kh is in the bound too). Classes exercised: E (the labelled chain, the site node without its
router, the restart, the no-event twin, the still face, the structural zeros, the first portion), R, B and L (arm 1), S at p = 1
(arm 5) and p = 2 (arms 2 and 6), U (`inv-H5`), N, M and D, one expected stop, one expected refusal, one recorded run, and one
plant of each kind: mapping (P1, P10), record (P2 to P5, P7, P9, P11, P14 to P17, P19) and engine (P8).

Arm 6's invented worlds need the second snapshot (the lift of the faced-node refusal), as the registered ones do.

I confirmed with my own decimal portion map and scheme that an honest run of the invented set lies inside every order window
(0.95 to 1.04 at p = 1; 1.99 to 2.02 at p = 2; 2.96 to 3.00 for the one-step orders).

## 8. Adversarial self-review

**For each closed form, a second derivation** is the third column of §3 and the rows of `checks`. `self_check.py` recomputes each
published value by another formula still: flows column by column by uniformization, the heat of a flow as one ideal mixing from t = 0,
two wells as a relaxation to the common level, the free energy lost by logarithms of ratios, H_def by J̄²/W, arm 5's and 6's
heats by Clenshaw-Curtis with hyperbolic-function levels, and every plant with the same second formulas.

**What a careless reading would have got wrong,** and what stands against it:

- *The −1 in f and F.* Dropped from the supplied term alone, H_tot is off by RT times the supplied amount; dropped from every term
  consistently it cancels by conservation, which is why the self-check can use the logarithmic form. Against it: Σ H_holder = H_tot.
- *The row at an event's time is the state before it.* G1's rows at 2 s and 4 s, and arm 2's at 16 s, are before. Against it: SPEC §1
  states it, and the self-check re-derives each row.
- *The collector's volume grows.* F(n_K, V_K(t)) needs V_K at t, and y_K = n_K/V_K has a finite limit at t = 0.
- *G5's inlet switches:* two entries, not one; its heat to 4 s is exactly 0.
- *Two labels, one inlet.* The inlet's liquid is the base label's, so a tag obeys the equations with its inlet off.
- *An equal-rate chain* must be taken by its own form: E(t) with a ≠ b cancels, and the published values never use it there.
- *The trace:* 10 pL times the double of 1e-12 is not the double of 1e-11, so `F3`'s B starts 1e-27 fmol off a uniform level. Every
  start is read as its own double, and the propagator is used rather than a formula that assumes equality.
- *The default heat's law* uses the scheme's transfer m_R, not m*, and levels half a step on; B_def takes |A′| at m/2 and at s*, |A″| at
  0 and at m.
- *Arm 6:* the face is not a flow, so the holders' rates hold the links only; the total holds the face; `J0`'s router is zero and its total
  is not.
- *The sum over the species* in a heat scale (Σ N_x) and the (S + 1), once each.
- *`H_tot` of `F7`* holds the router's holders alone; the site node is not one of them.

**Faults found in my own work, and how:**

- The tanh-sinh rule's positions already included the left end of the interval, and I added it again, so only the first interval of a
  series was right. The two-quadrature check found it (a gap of 8.7e-3 of s_F, where Gauss closed the sum identity to 1e-91), before any file
  was written.
- `expm` first stopped its Taylor series on the matrix's largest entry, which left small entries (a fifth power of a short time) with a
  relative error of 1e-88. A component test found it; the rule is now entrywise. No published value moved.
- My first singularity test used one Gauss piece on [2, 16] s and missed its bound by 1e-28 of its scale for every trace alike; the fault
  was the piece (it more than doubles its distance from the singular end), not the laws. `by_gauss` now splits any such interval.
- A cache of propagated states was keyed by an object's address, which Python may reuse after the invented inputs are freed. Each world
  now holds its own cache, and each arm reads its inputs afresh.
- Sets are never iterated in their own order.

**What I could not check:** whether the engine admits the invented worlds (a trace beside 14.9 fmol, a 1.25 pL portion, 62 runs), whether
LAWS §9's counts cover the engine's operation path (only the rehearsal can), the engine's own sign of zero, the retry's rows, and the
judge's reading of these files. Nothing here bears on `n_L_S`, `free_sites_S` and `bound_L_S`.

## 9. Regenerating

`regenerate.py` writes the files into scratch folders under two other values of `PYTHONHASHSEED` and compares bytes; the seeds, the
platform, the Python and libmpdec versions, and the spec files' hashes are in `out/provenance.json`, and each file's sha256 is in
`out/SHA256SUMS`. Run times are in `out/run_times/`, apart.

## 10. Numbers

**Checks.** 771 rows over the seven files, all passing (the invented file 296; arms 1 to 6: 88, 52, 156, 50, 90, 39). Largest residual against its bound, by SPEC §9's item, over every file:

| Item | What | Largest residual | Bound |
| --- | --- | --- | --- |
| 1 | 1 − 2/e and 1 − 1/e, by both methods; m = 1 to 8 equal chambers | 2.9e-108 | 1e-50 |
| 2 | closed form against the propagator, every entry, relative | 6.0e-107 | 1e-50 |
| 2 | the gap to the confluent form: E's slope; successive ratio; the chain's amounts (each scaled so that 1 is the bound) | 0.093; 0.83; 0.27 | 1 |
| 3 | node columns; amounts; volumes (the last two against the start plus the supplied) | 5e-111; 7.4e-107; 4.5e-106 | 1e-100; 1e-50 |
| 4 | e^(−Gt) e^(Gt); P(h)^S = P(Sh) at every registered h | 8.7e-102; 7.2e-109 | 1e-50 |
| 4 | every amount by uniformization and by Taylor continuation, relative | 1.2e-106 | 1e-50 |
| 5 | the remainder falls by 4 (last halving: 4 ± 3.3e-4); its leading term (error over f 0.34) | 3.3e-4; 0.34 | 2⁻⁴; 1 |
| 6 | closed form against the propagator; D against ∫A dm by two quadratures; D′(0) = A(0) | 8.8e-108; 1.1e-53; 8.8e-91 | 1e-50; 1e-40; 1e-60 |
| 6 | `N-buffered` and `N-clean` hold 8 and 2 fmol at 16 s | 6.3e-16 | 8.9e-16, the two starts' half-ulps carried through the relaxation |
| 7 | R(z) − e^(−z) ≥ 0, and over z³/6 | 0; 0.99954 | 0; 1 |
| 8 | Σ H_holder (and H_face) = H_tot, tanh-sinh and Gauss (over s_F); the two quadratures agree | 1.7e-58; 2.5e-65; 1.7e-58 | 1e-40 |
| 8 | `H_A` by the dilogarithm; H_tot by finite portions at every registered step; H_tot by the holders' rates | 3.1e-64; 2.1e-108; 4.2e-41 | 1e-40; 1e-50; 1e-40 |
| 8 | a uniform stream; the second portion's loss RT (3 ln 3 − 4 ln 2), both forms, either order; the first portion | 1.6e-105; 8e-110; 0 | 1e-60; 1e-50; 0 |
| 9 | labels sum to their species; arm 6 at Q = 0 is two wells, its face heat D(m*) | 8.9e-110; 1.7e-107; 7.9e-65 | 1e-50; 1e-50; 1e-40 |
| 10 | J̄²/W against the two-well form; \|H_def − D\| ≤ B_def (largest ratio 0.9999975, `eq-hi` at 1/64 s); third clause over 8z (arm 1's judged starts, and the invented) | 1.2e-108; 1; 0.067 | 1e-50; 1; 1 |
| 11 | the largest fraction of LAWS §9's bound over every network, run, quantity and output (`F1`, the amounts' sum) | 0.0413 | 1 |

Check 8's Gauss route to `G5` (4.2e-41 of s_F) is the one row within a factor of three of its bound: it is the integral of a collector's
rate after the switch, where the integrand's nearest singularity lies at 2.67 s, 1.33 s before the piece, and is not used for any
published value (`G5`'s heat is the portion law). The bound was set before it was computed.

**Plant margins** (distance over the expected honest tolerance; each must be at least 10). No margin falls below 10; the smallest are
P15 on `eq-hi` (13.2) and P14 at the coarsest step (15.8).

| Plant | Check (class) | World | Margin |
| --- | --- | --- | --- |
| P1 | `n_T_K` at 8 s (R) | `F1` and `F2` | 8.4e12 each |
| P2 | `n_T_B`, `n_T_K` (R) | `F1`; `F3` | 1.3e13; 1.5e13 |
| P3 | `n_T_B`, `n_T_K` (R); `V_K` (R) | `F3`; `F1` and `F3` | 3.3e12; 1.2e13 each |
| P4 | `n_U_B`, `n_U_K` (R) | `F1` | 1.3e7 each |
| P5 | `H_A` (S) | `H1` | 129 |
| P7 | `H_tot` (R) | `H2`, `H3`, `H4` | 2.1e10, 2.2e10, 2.2e10 |
| P8 | no margin: H_missing in `plants_reported` | `N-buffered`, `F1` | – |
| P9 | the first loss (E) | `G1` | none (distance 2.4e-3 pJ) |
| P10 | `n_T_K` at 8 s (R) | `F1` | 7.5e12 |
| P11 | `label_T_tag_K` (R) | `F1L` at h = 8 | 3.1e12 |
| P14 | `n_T_1`, `n_T_2` (B) | `r4-mid`, h = 2, 1, 0.5, 0.25 | 15.8, 69.1, 291, 1195 |
| P15 | `n_T_1`, `n_T_2` (B) | `eq-lo`, `eq-mid`, `eq-hi` at h = 0.25 | 3838, 877, 13.2 |
| P16 | `H_face` (B, default, the four steps; R, exact j = 0) | `eq-mid` | 107, 215, 431, 862; 3.7e11 |
| P17 | `sample` (R) | `N-buffered` exact j = 2 | 6.6e11 |
| P19 | `n_T_A` (S), order 0.997 against a limit of 1.25 | `J1` | 123 |

In the invented file the same plants have margins of at least 15.2.

**Programs.** `component_tests.py`: 83 of 83 tests pass. `self_check.py`: 569 of 569 rows over the seven files. `mutation_tests.py`: each of 40 deliberate changes is flagged and the unchanged file is clean. The residuals are in `out/`.
