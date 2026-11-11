# Test plan: Cortés-Poza (2026), hybrid framework for morphogenesis and regeneration

Y. Cortés-Poza, "A hybrid mathematical framework for morphogenesis and
regeneration", *Journal of Mathematical Biology* 93(3), article 43 (2026),
doi:10.1007/s00285-026-02459-2, CC BY-NC-ND 4.0 (read through Europe PMC,
PMC13529881). Author's code: <https://github.com/YuririaCP/bioelectricity/>.
This plan cites equation numbers only and reproduces none of the paper's text or
tables. User decision: [D137](DECISIONS.md).

## What the paper models

The paper uses a dimensionless model on a cell graph (a chain or square lattice).
Each cell has:

- a voltage with a cubic bistable current (Eq. 19);
- four abstract regulatory modules: proliferation, differentiation, positional
  identity and regenerative response;
- a slow memory variable (Eq. 13);
- a diffusing wound signal with a lesion source (Eqs. 14–15).

The gap-junction conductances are adaptive (Eq. 20). A discrete morphological
state (Eqs. 16–17) and a birth rule for vacant sites (Eq. 18) complete it.

The model has no ions, no conservation laws and no absolute time units. Its
comparison with planarian experiments is qualitative.

Claims:

- target morphology is an attractor of the coupled dynamics;
- homeostasis and regeneration after a lesion;
- switching between attractors under transient forcing (Eq. 46);
- nucleation, coupling and forcing thresholds (Conjectures 1–3).

Results proved for reduced subsystems:

- single-cell bistability;
- no Turing instability in the reduced voltage–proliferation subsystem;
- energy descent for the pure bioelectric layer, with an Allen–Cahn limit
  (Eq. 45) and a Maxwell condition (Eq. 33).

**Unverified reading note.** Remark 4's barrier formula, evaluated with the
paper's own parameter values, does not reproduce its continuum nucleation estimate.
Integrating the cubic current does reproduce it, so the formula is probably a
typo. Phase 0 settles this.

## Independent review and what we verified

The user supplied an independent review (10 November 2026). Its conclusion: the
reduced bioelectric results stand, but the full-model analysis and the numerical
evidence for regeneration and memory have material problems. We checked what we
could against the author's code at the commit the paper links (`2b53a08`, MIT
licence, holder "YuririaCP") and against the cited literature.

**Confirmed in the code at `2b53a08`:**

- **Switching curve.** The panel showing switching probability against memory
  time scale comes from a closed-form logistic formula, commented as a conceptual
  approximation, not from simulated trials (`experiment_polarity_reversal` in
  `attractor_analysis.py`). A separate amplitude–duration switching sweep is
  simulated.
- **Energy coupling term.** The energy routine computes the coupling term as half
  the sum over the full symmetric conductance matrix (`lyapunov_energy`). That
  counts every undirected edge twice relative to Eq. 34. The same file uses the
  per-edge convention elsewhere.
- **Regeneration fidelity.** Fidelity and success (`_regen_success`, cutoff 0.55
  at the call site) count only originally depolarised cells that end depolarised.
  Originally hyperpolarised cells that become depolarised are ignored.
- **Figure 3 lesion.** The experiment behind Figure 3 resets voltage and sets a
  wound signal. It keeps the cells, their regulatory state, memory and
  conductances.
- **Removed cells and births.** In the model, removed cells stay coupled through
  their conductances, held at zero state. The birth routine updates sites
  sequentially, so a newborn can parent the next site within the same update.

**Checked by calculation:**

- **Boundedness.** With the nominal values of Table 3 and every variable at 1, the
  differentiation equation (Eq. 10) gives a positive rate, so its stated [0, 1]
  bound does not hold without the clipping that Section 5.1 discloses.
- **Energy derivative.** Eq. 39 omits the term from time-varying conductances in
  dE/dt. That term is one half of Σ_edges dG_ij/dt (V_i − V_j)².

**Reported by the review, not checked by us** (we have not seen the figures):

- Figure 4's full-model energy rises over part of the run, and its perturbation
  ratio exceeds one.
- Figure 8's final state tracks the initial depolarised fraction almost linearly.
  That points to interface pinning, not majority selection.

**Literature:**

- **Beane et al. 2011** (Chem Biol 18:77): drug-induced headless animals re-wounded
  without the drug regrow a head when a blastema forms (75% head rescue, n = 24;
  no blastema, 100% headless, n = 16). Headless outcomes are therefore not stored
  headless memory.
- **Durant et al. 2017** (Biophys J 112:2231, abstract): transient bioelectric
  modulation gives a stable ratio of double-headed regenerates, plus a cryptic
  phenotype revealed only on cutting. Reversing the bioelectric state resets
  regeneration to wild type.
- **Pietak & Levin 2017** (J R Soc Interface, doi:10.1098/rsif.2017.0425,
  abstract): bioelectricity-integrated gene and reaction (BIGR) networks with Vm
  memory, hysteresis, state switching and a planarian regeneration model. The paper
  omits it. It is the closer prior work, and a reference for parity rung P8.

**Consequence for this plan.** The paper is a hypothesis source and a candidate
benchmark. Its reported regeneration fidelity and its memory-dependent switching
curve are not used as validation.

The guiding question is the review's:

> After tissue or state is genuinely removed, which surviving information causes
> the correct organization to return, and can that information be erased,
> transferred or rewritten independently?

It matches what the heredity pre-screens found. In pre-screen 9, the junction
state carried across a replacement decided rim renewal, and slow ion composition
decided whether converted cells could pass D on.

## Phase 0 results (11 November 2026)

This is tooling under D137; no Cells engine model ran. The author's code at
`2b53a08` (MIT) was run unmodified, out of process, in its own environment.
Corrections were applied as runtime subclasses, and a plain bistable chain with
fixed conductances was the baseline. Evidence:
`/mnt/workspaces/Cells/cortes-poza-2026-phase0-20261111-01/`. The runner restates
upstream protocol lines (parameters, initial conditions, loops) to stay bit-identical,
so it is kept with the evidence and not added to this repository.

- **Shipped settings differ from the paper.**
  - The experiments use dt 0.05; the paper says 0.01.
  - Several parameters differ from Table 3 (β1, β2; a and G in Fig. 4).
  - No entry point matches the paper's settings.
- **Remark 4 is a typo.** The printed barrier is 4× too large. Integrating the
  cubic gives 81a/64 = 1.519, so √(2ΔU) = 1.743, the paper's estimate. The general
  form is (a/12)(V₀ − V₋)³(2V₊ − V₋ − V₀).
- **Nucleation (Exp. 1)** reproduces δ* ≈ 1.9–2.0, but only under the code's "12% of
  cells above 0.75" metric. With the paper's own both-phases criterion,
  δ* ≈ 1.25. The plain chain nucleates at least as easily (code metric 1.74,
  both-phases 1.1), so the threshold does not come from the regulatory or memory
  layers. At dt 0.05, 1–9 of 30 runs per δ ≥ 1.7 go non-finite and are counted as
  "no pattern".
- **Regeneration (Exp. 2)** reproduces fidelity 1.00 only with the one-sided coded
  metric.
  - With the paper's two-sided definition, agreement is 0.93, 0.83, 0.73 and 0.63
    at lesion fractions 0.1, 0.3, 0.5 and 0.7. No run reaches 0.95.
  - Correcting the lesion (removing cells and their junctions) and the birth rule
    gives 0.93–0.80.
  - The plain chain recovers better: 0.97–1.0 for a centred lesion, and 1.0–0.89
    for a shifted one.
- **Energy.**
  - The per-edge energy never rises in the fixed-conductance system or in the
    code's "pure" adapting case, so Theorem 1's system holds.
  - In the full model it rises in 4,649 of 5,000 steps, driven by the dG/dt term
    that Eq. 39 omits.
  - The code's double-counted coupling term makes even the frozen system rise.
  - Remark 8's statements and Fig. 4's caption are contradicted by the author's own
    outputs.
- **Switching.**
  - Fig. 7's τ_ε curve is the closed-form logistic.
  - In a simulated τ_ε sweep, τ_ε ≤ 10 gives no complete reversal at any amplitude.
    The code's switching rule nevertheless reports p = 1, because it counts collapse
    to uniform depolarisation as a switch.
  - Conjecture 3 (A*(12) < 2.5) holds, but also in the plain chain (A* ≈ 1.48), so it
    needs neither the regulatory nor the memory layer.
- **The paper's patterns are not long-lived.** In every author parameter set the
  unforced, unlesioned half-depolarised pattern collapses to uniform depolarisation,
  by t ≈ 160–450. With the memory variable frozen it persists to t = 562, and the
  plain chain persists in every case. So the slow memory erases the pattern rather
  than storing it. The route (through conductances or the regulatory network) is not
  separated.
- **Limits of this reproduction:**
  - N, seeds and grids that the paper does not give were chosen by us and labelled
    in the results;
  - regeneration outcomes were identical across seeds, so each condition is
    effectively one trial;
  - the long-horizon controls used one seed each;
  - the paper's figures were not seen;
  - dt was checked only for Exp. 1 and the energy runs.
- **Conclusion for Phase 1.** The bioelectric layer's own physics (bistability,
  pinning, nucleation, strength–duration switching) carries every reproduced effect.
  Phase 1 therefore tests those effects in Cells against the plain bistable baseline,
  not against the author model's added layers.

## Mapping to Cells

Cells tests whether the paper's attractor claims survive conserved ion-level
biophysics. It does not add the abstract modules to the engine (D136).

| Group | Claims | In Cells |
| --- | --- | --- |
| 1. Testable now | Single-cell bistability; wall width and pinning (Eq. 45); Maxwell condition (Eq. 33); coupling limit (Conjecture 2); critical depolarised fraction (Conjecture 1); nucleation from noise; switching by a transient cue (Conjecture 3); a slow memory time scale | `stationary_continuation_analysis@1` already qualifies bistability. MG0b already passed wall width and pinning. Everything else is new runs on `resolved_pump_tissue@3` |
| 2. Needs an engine feature | Activity-dependent junction conductance (Eq. 20); slow memory; wound signal | Literature-sourced opt-in models (D136): connexin abundance turnover; expression-based memory (heredity Stage D); a diffusing injury signal on `reaction_transport@1` |
| 3. Needs removal and regrowth | Regeneration after a lesion | Cell replacement (G2), cutting, birth and growth, then MG1 |
| 4. Not testable as written | The abstract modules and the polarity mechanism built on them | Only physically mapped versions can be tested |

The bridge for group 1 is Cells' own steady current–voltage curve of the heredity
cell. The stationary analysis computes it twice, with composition frozen at H and
at loaded D. The paper's predictions are converted through this curve and written
down before any run.

## Phases

**Phase 0: reference reproduction (tooling; approved in D137).**

- Run the author's code out of process, pinned to commit `2b53a08` (MIT). It is
  never copied or imported.
- Reproduce the nucleation experiment and the amplitude–duration forcing sweep in
  the paper's units, and settle the Remark 4 question.
- Rerun with the corrections the review identifies:
  - two-sided pattern agreement over all original cells;
  - the per-edge energy convention, including the dG/dt term;
  - a simulated switching sweep against memory time scale, in place of the
    formula.
- Run a plain bistable network with fixed conductances as the baseline every
  claim is compared against.
- Label results as "author model, corrected" and keep them apart from the
  paper's own claims.
- Evidence goes in a dated directory under `/mnt/workspaces/Cells`.

**Phase 1: group 1 on the current engine.** Predictions are written first, from
the paper's theory converted through Cells' current–voltage curve.

| Test | Paper | Cells measurement |
| --- | --- | --- |
| T1 | Maxwell condition (Eq. 33) | Which state invades in a long, strongly coupled chain |
| T2 | Coupling limit (Conjecture 2) | Disc coupling limit against disc size, compared with the Allen–Cahn critical nucleus, at H and at loaded composition |
| T3 | Critical depolarised fraction (Conjecture 1) | Whether a sheet with a random D fraction ends all-D, all-H or pinned in mixed domains; pinning is expected (MG0b, and the review's reading of Figure 8) |
| T4 | Nucleation from noise | Probability that a pattern forms, against the amplitude of random initial voltage |
| T5 | Forcing threshold (Conjecture 3) | Strength–duration curve for switching, using the Na-permeability cue validated in parity P3 |
| T6 | Memory (the guiding question) | True ablations, not time-scale changes. After a write, independently reset (a) voltage, (b) ion composition and (c) junction gate state, then ask which surviving state brings the pattern back. Permanence needs convergence evidence, not one window |

**Phase 2: group 2 features**, each with its literature step first, then the
model, tests and its own qualification.

**Phase 3: regeneration after a lesion**, then planarian anterior–posterior
polarity on fixed geometry (D134).

- **Removal:** a lesion removes the cells' internal state and their junctions, as
  an engine operation with ledgers (G2).
- **Regrowth:** follows a defined, timed birth process.
- **Metric:** recovery is scored as two-sided pattern agreement.
- **Generalisation:** tests cover varied cuts and fragment sizes, repeated
  regeneration, and comparison with a plain bistable baseline.
- **Biological targets:** persistent double-head and cryptic outcomes (Durant
  2017), kept separate from blastema-dependent head rescue (Beane 2011).

## Blockers

- **Junction-heat refusal.** The pump family refuses steps in which a junction's
  power drops by more than about 59% (see PROGRESS). Moving fronts, nucleation and
  switching (T1, T4, T5) hit it at 5 ms steps, so its fix is on the critical path.
- **Per-cell current injection.** The engine has no per-cell injected current: its
  electrodes feed only held nodes. Forcing therefore uses permeability events, or
  injection is added as a feature.
- **Time scales.** Cells' junction gates act in 0.05–0.4 s, while the paper's
  conductances adapt slowly. Only ratios of time scales are comparable.
- **Coupling limits.** T2 waits for the frozen-composition stationary comparison,
  because pre-screen 7's coupling limits are on hold.

## Order

1. Phase 0 on the next free agent slot.
2. Cell replacement (G2) on the slot after that.
3. Phase 1 once the junction-heat fix lands and the frozen-composition run
   reports.
4. Phases 2 and 3 follow the engine-feature queue (D136).
