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
