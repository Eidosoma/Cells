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

- Run the author's code out of process, after checking its licence; it is never
  copied or imported.
- Reproduce the nucleation experiment and the forcing experiment in the paper's
  units, and settle the Remark 4 question.
- Evidence goes in a dated directory under `/mnt/workspaces/Cells`.

**Phase 1: group 1 on the current engine.** Predictions are written first, from
the paper's theory converted through Cells' current–voltage curve.

| Test | Paper | Cells measurement |
| --- | --- | --- |
| T1 | Maxwell condition (Eq. 33) | Which state invades in a long, strongly coupled chain |
| T2 | Coupling limit (Conjecture 2) | Disc coupling limit against disc size, compared with the Allen–Cahn critical nucleus, at H and at loaded composition |
| T3 | Critical depolarised fraction (Conjecture 1) | Whether a sheet with a random D fraction ends all-D or all-H |
| T4 | Nucleation from noise | Probability that a pattern forms, against the amplitude of random initial voltage |
| T5 | Forcing threshold (Conjecture 3) | Strength–duration curve for switching, using the Na-permeability cue validated in parity P3 |
| T6 | Memory time scale | Whether a transient write leaves a lasting fingerprint through slow composition loading (time constant 40–50 min) |

**Phase 2: group 2 features**, each with its literature step first, then the
model, tests and its own qualification.

**Phase 3: regeneration after a lesion**, then planarian anterior–posterior
polarity on fixed geometry (D134).

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
