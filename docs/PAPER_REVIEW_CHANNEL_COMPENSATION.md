**Ion channel compensation and implications for Cells — reviewed 13 October 2026**

Hananel Hazan and Michael Levin, *Computational Framework for Identifying Ion
Channel Mutation-Compensating Interventions*, unreviewed bioRxiv v1, posted 25 September
2026. [Preprint](https://www.biorxiv.org/content/10.64898/2026.09.20.753002v1),
[full text](https://www.biorxiv.org/content/10.64898/2026.09.20.753002v1.full).

**A useful reference for searching for functional recovery, testing robustness
and running large GPU ensembles.** For Cells, the strongest application is to
ask whether a damaged system can recover specified functions through other
permitted mechanisms, then test the recovered state under new challenges.
This belongs alongside BETSE calibration and BITSEY replication as an assay
and search reference, rather than expanding their feature-parity claims.

This follow-up is retained in the
[development priorities](ROADMAP.md#current-development-priorities) and the
[functional-recovery experiment](EXPERIMENTS.md#functional-recovery-through-channel-compensation),
which specify its prerequisites and completion evidence. Those planning entries
should be revisited after the current assay and its immediate diagnosis close.

The study's interventions are computational; patient-specific treatment and
experimental rescue remain future work. Its Kv7.2 example reports **88.9% less
spike-count discrepancy**, with the mutant M-current unchanged. Retaining 80%
of the intervention's unperturbed efficacy tolerates conductance changes of
**±11% at the median and ±3% in the worst sign combination**. These quantities
are model scores and parameter perturbations, not clinical outcomes or drug-dose
tolerances. The **37 R859C configurations** reproduce mutant firing counts;
they are alternative compatible models, not 37 cures. Gradient descent succeeds
in one of four compared cases, versus four for direct search. The proposed
fast-to-detailed search pipeline was not exercised as a combined workflow.
[Sections 2.1, 3.2, 3.4, 3.6–3.7 and 4.2](https://www.biorxiv.org/content/10.64898/2026.09.20.753002v1.full).

There is an experimental foundation: the
[Barela model record](https://modeldb.science/87585) describes a clinically
identified sodium-channel variant expressed and measured in Xenopus oocytes;
the [Miceli model record](https://modeldb.science/118986) supplies a CA1 neuron
model with altered Kv7.2 gating. Reproducing these models verifies source
behaviour. Biological calibration of a new Cells model would additionally need
the original measurement protocols, uncertainties and held-out responses.

**Checks of the released implementation**

The [author repository](https://github.com/Hananel-Hazan/channelopathy-compensation/tree/1e15885a0e1011d89279616cb95112aee47c8db2)
was inspected at commit `1e15885a0e1011d89279616cb95112aee47c8db2`.
These are static source findings; the authors' computations were not rerun.

- **The damaged-channel constraint needs a precise definition.** The R859C
  search's `runMT` assigns all three conductances, including
  `gnatbar_ichanR859C1`; its intervention loop adds or subtracts a three-component
  vector without holding sodium conductance fixed. The later replay helper does
  the same. Keeping mutant kinetics while changing its maximal conductance is
  a different constraint from leaving the affected channel untouched. This
  qualifies the preprint's general description. The Kv7.2 implementation does
  keep its separate M-current outside the three searched conductances.
  [Original search](https://github.com/Hananel-Hazan/channelopathy-compensation/blob/1e15885a0e1011d89279616cb95112aee47c8db2/pipeline/r859c/Explore8/exploration.v3.run.exp.py#L139),
  [R859C replay](https://github.com/Hananel-Hazan/channelopathy-compensation/blob/1e15885a0e1011d89279616cb95112aee47c8db2/experiments/wo97/wo97_lib.py#L62),
  [Kv7.2 controls](https://github.com/Hananel-Hazan/channelopathy-compensation/blob/1e15885a0e1011d89279616cb95112aee47c8db2/experiments/wo6/phase2/wo6b_lib.py#L58).

- **The GPU headline is a normalized integration benchmark.** The timing
  script excludes initialization, compilation and warm-up, times a shorter
  integration, and scales per-step timing to a nominal 30,000-step unit. Its
  batch contains 35 elements per nominal candidate, but the harness uses a
  common constant current and separately drawn conductances, not an actual
  35-stimulus evaluation of each shared parameter triple. It uses float32 and
  omits the complete search, scoring, validation and output costs. This supports
  an integration-throughput comparison, not a measured end-to-end Cells rate.
  [Timing script](https://github.com/Hananel-Hazan/channelopathy-compensation/blob/1e15885a0e1011d89279616cb95112aee47c8db2/experiments/wo3/wo3_taskC2_clean.py),
  [benchmark harness](https://github.com/Hananel-Hazan/channelopathy-compensation/blob/1e15885a0e1011d89279616cb95112aee47c8db2/experiments/wo3/wo3_gpu_lib.py).

- **Batching and fusion are concrete implementation leads.** The released
  table reports about **543 to 34,279 nominal candidates/s** on the same RTX
  2070 when fusion is added, and **63,649/s** on an RTX 4070 Ti. Its CPU
  spike-count rate is **16.4/s**, whereas the preprint text says **11.9/s**;
  keep these source versions separate. The streaming search library retains
  running spike statistics instead of every voltage sample. Those are useful
  patterns to investigate in our existing JAX execution, subject to equivalent
  physics, precision and output requirements.
  [Released table](https://github.com/Hananel-Hazan/channelopathy-compensation/blob/1e15885a0e1011d89279616cb95112aee47c8db2/figures/throughput_table.md),
  [streaming library](https://github.com/Hananel-Hazan/channelopathy-compensation/blob/1e15885a0e1011d89279616cb95112aee47c8db2/experiments/wo5/wo5_lib.py).

- **Reproduction is possible in parts, with documented gaps.** Figure data,
  scripts and environment records are supplied. The reproduction notes identify
  archived traces with an unknown generating script and other unsaved analysis
  steps. They also distinguish preprint and journal-submission figure numbering;
  submission does not establish peer review. The candidate databases are listed
  as a separate Zenodo deposit, which was not downloaded in this review.
  [Reproduction notes](https://github.com/Hananel-Hazan/channelopathy-compensation/blob/1e15885a0e1011d89279616cb95112aee47c8db2/docs/REPRODUCE.md),
  [external data](https://github.com/Hananel-Hazan/channelopathy-compensation/blob/1e15885a0e1011d89279616cb95112aee47c8db2/docs/DATA_EXTERNAL.md).

- **Keep implementation provenance compatible with Cells' MIT repository.**
  The code carries Apache 2.0 with a Tufts rider restricting use to academic,
  non-commercial research; the data have separate CC BY 4.0 terms. The planned
  Cells implementation should use independently written code from equations
  and specifications, preserving attribution for reference data. No upstream
  source is incorporated into Cells by this review.
  [Code terms](https://github.com/Hananel-Hazan/channelopathy-compensation/blob/1e15885a0e1011d89279616cb95112aee47c8db2/LICENSE),
  [data terms](https://github.com/Hananel-Hazan/channelopathy-compensation/blob/1e15885a0e1011d89279616cb95112aee47c8db2/LICENSE-DATA).

**A bounded first experiment in Cells**

After the current assay is closed, choose one qualified model and a small,
explicit impairment. Freeze the damaged mechanism, allowed compensating
parameters, physical bounds, reference trajectories and success criteria.
Search only the declared controls; changing a kinetic law, a channel's maximum
availability and its current opening are different interventions. Any new
mechanism or longer horizon needs its own qualification. The ordinary BETSE
junction model's microsecond domain does not qualify neuronal millisecond or
second protocols.

Use a small ensemble of compatible baseline states so the search cannot succeed
only on one fitted parameter set. Compare bounded log-space sampling with a
simple baseline under equal evaluation budgets where multiplicative parameter
ranges justify it. Keep calibration/search stimuli separate from held-out
stimuli, preparations and perturbations. Preserve untreated, impairment-only,
sham and unsuccessful interventions, including divergence. Evaluate waveform,
timing and the relevant task functions separately; a favourable scalar score
must not hide loss of another function or invalid charge/material accounting.

Measure joint perturbations and adverse combinations as well as one-parameter
sensitivity. Test the entire path into the recovered state: several acceptable
endpoints do not guarantee a safe or dynamically reachable route between them.
If a reduced model proposes candidates, retain its identity and verify those
candidates in the detailed model before interpreting recovery. Our
[two-task assay](TWO_TASK_READOUT_ASSAY.md) supplies an appropriate lesson:
location and timing need separate margins and a joint criterion. Keep its
existing cues, readers and registered outcomes fixed; a search is a new assay.

For *Plastic Heredity* and *How Forms Become Reconstructible*, the proposed
connection is recovery of function through different underlying configurations.
External optimization establishes reachability under supplied control. To test
adaptive reconstruction, add a lawful local controller, remove external help,
challenge the resulting state, then examine transfer and carrier replacement
when those mechanisms are implemented. These are different claims from finding
two parameter sets with the same output. The
[polycomputing design](MULTISCALE_EXECUTION_ARCHITECTURE.md#polycomputing-several-functions-in-the-same-evolving-substrate)
already separates analyst readouts from physical consumers.

Assembly could later constrain channel production or replacement through an
explicit finite-material coupling, allowing a comparison between an imposed
conductance change and physically rebuilding the relevant machinery. The
[assembly model](CAPSID_ASSEMBLY.md) provides some coupling foundations;
arbitrary conductance optimization does not supply synthesis, trafficking or
turnover laws.

For GPU work, qualify bounded summaries against full recordings, retain complete
restart state and failure evidence, and profile device work, transfers and output
costs separately. Record both warmed throughput and whole-job throughput, plus
GPU-busy and measured SM-active with coverage. Schedule comparable independent
batches across future Jupiter workers using measured costs and stable world IDs.
The paper's rates do not predict L4 performance or 4–16 GPU scaling.

The review used the full HTML text and captions, primary model records, and the
selected pinned source files above. The publisher PDF and expanded table were
unavailable; the released table was inspected separately. Downloaded sources,
hashes and the review check live under
[/mnt/workspaces/Cells/paper-review-levin-channel-compensation-20261013](/mnt/workspaces/Cells/paper-review-levin-channel-compensation-20261013).
These notes introduce no simulation changes or additional jobs. Current run
status remains in [Progress](../PROGRESS.md).
