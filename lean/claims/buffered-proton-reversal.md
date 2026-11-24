<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# The local free proton concentration at each buffered endpoint sets leak reversal

The general binding closure determines a unique free proton read at either endpoint when its equilibrium exists. At zero voltage and on the regular branch, the open leak reverses at (RT/F) times the outside-minus-inside difference in free log proton concentration. At fixed inside concentration and voltage, raising outside free H⁺ increases inward flux.

## Assumptions

- Positive absolute temperature and route scale, valence +1, inside-minus-outside voltage and a common concentration standard. Binder totals are nonnegative. Held ligand totals and unheld free ligands agree when comparing solutions at one endpoint.
- The Bernoulli evaluator agrees with the analytic reversal at zero and for |FV/(RT)| ≥ 10⁻⁴. At small nonzero voltage the earlier two-branch proof gives the evaluator’s own reversal ratio.
- For the mitoplast comparison, the solution pH is used as the free-proton activity proxy. The reference temperature is the 24 °C specified for the authors’ Nernst line.

## Lean proof

**Proved**

- [CellsProofs.Transport.BufferedProtonLeak.endpoint_read_unique](../CellsProofs/Transport/BufferedProtonLeak.lean#L13)
- [CellsProofs.Transport.BufferedProtonLeak.reversal_from_free_logs](../CellsProofs/Transport/BufferedProtonLeak.lean#L24)
- [CellsProofs.Transport.ProtonLeak.outside_change](../CellsProofs/Transport/ProtonLeak.lean#L138)
- [CellsProofs.Transport.ProtonLeak.strictMono_outside](../CellsProofs/Transport/ProtonLeak.lean#L145)

Direct proof subject `cells.proton_constant_field_leak@2`

Proof sources [Cells held-ligand equilibrium uniqueness, specialized at the proton row](../CellsProofs/Chemistry/BindingEquilibrium.lean#L96) · [Cells constant-field reversal, specialized with the two free logs](../CellsProofs/Transport/ProtonLeak.lean#L112) · [Mathlib logarithm of the real exponential, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Basic.lean#L70)

Uses [Voltage and free proton concentrations set the leak reversal](proton-leak.md) · [Prescribed totals admit at most one binding equilibrium](binding-equilibrium-unique.md)

## Numerical comparison

**Checked.** Across three matrix/bath pH pairs and outside buffers of 1 and 100 mM, all six clamped reversals agreed with the independent Nernst calculation within 10⁻⁶ mV. The sign changed across every root. Substituting stored total proton equivalents gave nonzero flux at each free-proton reversal.

**Engine** `resolved_pump_tissue@3`, `resolved_pump_composite@1`, `proton_constant_field_leak@2`, `proton_constant_field_leak@1`

[Version-2 route and stage read](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/src/cells/laws/transport/proton_leak_v2.py) · [Inward flux](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/src/cells/laws/transport/proton_leak.py#L31) · [Clamped route flux](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/src/cells/kinds/passive_routes.py#L778) · [General binding read](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/src/cells/kinds/proton_buffer.py#L752) · [Buffered model and admission controls](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/tests/unit/test_rapid_binding_world.py#L839) · [One-site starting inventory](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/validation/compartment_ph_engine/parameters.py#L98) · [Reversal and closure proof](https://github.com/Eidosoma/Cells/blob/d2258d4f81a5a6e4a04277b51df0217e0b044289/lean/CellsProofs/Transport/BufferedProtonLeak.lean) · [Reference flux helper](https://github.com/Eidosoma/Cells/blob/d2258d4f81a5a6e4a04277b51df0217e0b044289/lean/checks/proton_leak.py) · [Individual reversal voltages](https://github.com/Eidosoma/Cells/blob/d2258d4f81a5a6e4a04277b51df0217e0b044289/lean/checks/data/bertholet2019_proton_reversal.json) · [Compartment pH measurements](https://github.com/Eidosoma/Cells/blob/d2258d4f81a5a6e4a04277b51df0217e0b044289/lean/checks/data/cortese1992_ims_ph.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/d2258d4f81a5a6e4a04277b51df0217e0b044289/lean/checks/ims_proton_leak.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/d2258d4f81a5a6e4a04277b51df0217e0b044289/lean/PROGRESS.md#mt1b-buffered-reversal)

[Tested engine fd2bb88ce444](https://github.com/Eidosoma/Cells/commit/fd2bb88ce444b48344236024a2a18844f59041a4) · [Evidence checkpoint d2258d4f81a5](https://github.com/Eidosoma/Cells/commit/d2258d4f81a5a6e4a04277b51df0217e0b044289)

## Biological evidence

**Open.** Measured voltage at zero proton current at controlled pH on each side, with a separate comparison for current magnitude under a buffer change.

- [The reversal voltage of a selective proton current shifts with the free pH gradient in the Nernst direction.](../WET_LAB_EVIDENCE.md#pair-proton-reversal-ph) · Supported by both studies

The three mitochondrial mean reversal voltages have the predicted directions. All three model values lie within the descriptive 95% Student t intervals for the corresponding means. The endpoint comparison leaves intact mitochondrial compartment pH and absolute leak current open.

**Unit** mV, matrix minus bath

### cherny1995_proton_reversal@1

Isolated rat alveolar epithelial cells, whole-cell clamp. Fig. 2 and abstract. [Cherny et al. (1995), Fig. 2](https://doi.org/10.1085/jgp.105.6.861)

- **Evidence role** descriptive

Rounded slope reported across gradients. No standard error for this slope is used.

With strongly buffered solutions the reversal shifted about 52 mV per pH unit over four units. This tests pH dependence in alveolar cells. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

### bertholet-2019-proton-reversal

Fatty-acid-activated proton current in mouse skeletal muscle mitoplasts. Three matrix/bath pH pairs, 13 individual voltages. The group means are −62.23, −91.13 and +28.82 mV. Extended Data Figure 3d and its source workbook. [Bertholet et al. (2019), Nature 571, 515–520](https://doi.org/10.1038/s41586-019-1400-3)

- **Evidence role** descriptive

Calculated sample SEMs are 1.92, 1.82 and 6.70 mV (n = 6, 3 and 4). The workbook gives individual readings and sample SD. Group intervals use the 95% Student t interval for independent observations. The figure specifies 24 °C for the Nernst reference.

The unfitted Cells roots were −58.96, −88.44 and +29.48 mV. Each lies within its group interval. This retrospective check concerns reversal of the observed proton current. It supplies no absolute permeability calibration. [Dataset manifest](../checks/data/bertholet2019_proton_reversal.json) · [Comparison verdict](../PROGRESS.md#mt1b-buffered-reversal)

### decoursey-1996-external-buffer

Voltage-gated proton current in rat alveolar epithelial cells as external buffer fell from 100 to 1 mM. Whole-cell external-buffer comparison in the abstract. [DeCoursey and Cherny (1996), Biophysical Journal 71, 182–193](https://doi.org/10.1016/S0006-3495(96)79215-9)

- **Evidence role** descriptive

The authors give a typical range for the amplitude change. An uncertainty for the reversal difference was unavailable.

Reversal was unchanged and current typically fell 10–30%. The fixed-free-pH Cells clamp holds its amplitude at the common probe voltage. Buffer supply and channel behavior limit amplitude comparison across these preparations. [Dataset manifest](../checks/data/decoursey1996_proton_buffer.json) · [Comparison verdict](../PROGRESS.md#mt1b-buffered-reversal)

### cortese-1992-ims-ph

Soluble FITC-dextran in isolated rat liver mitochondria across the reported external pH range 6.0–8.5. Abstract, intermembrane-space pH relative to the medium. [Cortese et al. (1992), Biochimica et Biophysica Acta](https://doi.org/10.1016/0005-2728(92)90081-C)

- **Evidence role** descriptive

The reported ranges span preparation conditions. Replicate uncertainty and matched respiratory states were unavailable.

Intermembrane-space pH was 0.4–0.5 units lower in the condensed configuration and 0–0.2 lower in the orthodox configuration. This tests the choice of local compartment. Flux and reversal were not measured. [Dataset manifest](../checks/data/cortese1992_ims_ph.json) · [Comparison verdict](../PROGRESS.md#mt1b-buffered-reversal)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
