<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A closing daughter bridge scales flux by its remaining aperture

Successive intervals compose for capped linear and exponential aperture closure. Linear closure reaches zero at its declared deadline. Exponential closure stays positive at every finite time from a positive starting aperture. The remaining aperture scales the fully open bridge's permeability–area product.

## Assumptions

- Closure is continuously enabled over the tested intervals, with a positive initial aperture and a fixed positive closure time.
- The flux comparison evaluates the same concentrations, potentials and gate before and after changing only bridge availability. The single-stalk biological comparison assumes proportionality between stalk diameter and aperture.

## Lean proof

**Proved**

- [CellsProofs.Tissue.DivisionBridge.linear_steps](../CellsProofs/Tissue/DivisionBridge.lean#L52)
- [CellsProofs.Tissue.DivisionBridge.linear_closed](../CellsProofs/Tissue/DivisionBridge.lean#L61)
- [CellsProofs.Tissue.DivisionBridge.exponential_steps](../CellsProofs/Tissue/DivisionBridge.lean#L68)
- [CellsProofs.Tissue.DivisionBridge.exponential_positive](../CellsProofs/Tissue/DivisionBridge.lean#L73)
- [CellsProofs.Tissue.DivisionBridge.aperture_factor](../CellsProofs/Tissue/DivisionBridge.lean#L78)

Direct proof subject `cells.operator.cytoplasmic_bridge_closure@1`

Uses [Charge carriers reconcile daughter volume and membrane shares at division](isopotential-division.md) · [Reversing a junction reverses its flux](junction-flux-reversal.md)

## Numerical comparison

**Checked.** After the checked division, both eight-step worlds matched the corresponding analytic aperture. At the 3 ms deadline availability was 0 for linear closure and 0.367879 for exponential closure. Species fluxes agreed with the same-state open flux scaled by analytic aperture within 5.09 × 10⁻²¹ fmol/s.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.constant_field@1`

**Operators** `cells.cytoplasmic_bridge_closure@1`, `cells.isopotential_partition@1`, `cells.membrane_entity_state@1`

[Open bridge geometry and permeability](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/definitions/partition_spec.py#L46) · [Time update and aperture fraction](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/operators/bridge_closure.py#L246) · [Division opens the daughter bridge](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/operators/partition.py#L994) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5/lean/checks/division_bridge.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5/lean/PROGRESS.md#daughter-bridge-closure)

[Tested engine b30e3298523e](https://github.com/Eidosoma/Cells/commit/b30e3298523e49bd6c33bba01aa11561f8fba449) · [Evidence checkpoint bad3c2a2f8b6](https://github.com/Eidosoma/Cells/commit/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5)

## Biological evidence

**Open.** Bridge diameter and inter-daughter transport during late cytokinesis in the same bridge, including the time and conditions of isolation.

**Unit** µm, s, nS, normalized tracer exchange per second

### adarlevor2021_bridge_stalk@1

Developing zebrafish embryos. The first plotted frame sets elapsed time. Diameter ratios equal aperture ratios under the proxy assumption. Fig. 1D, microtubule-stalk diameter at the midbody rim in one representative bridge. Fig. 1E relates microtubule loss to membrane closure. [Adar-Levor et al. (2021), Fig. 1D–E](https://doi.org/10.1073/pnas.2021210118)

- **Evidence role** held out from fitting
- **Fit** 0 min, 2.5 µm, 5 min, 1.6 µm
- **Evaluation** 10 min, 15 min, 20 min, 23 min, 24 min

The plotted series has no pointwise error bars. The overall series comprised 18 bridges in five embryos. Membrane continuity can outlast tubulin visibility.

The held-out diameter at 15 min was about 1.6 µm. The first two readings predicted 0 µm for linear closure and 0.655 µm for exponential closure. Both miss the plateau in this bridge. Actual ionic aperture and variability among bridges remain open. [Dataset manifest](../checks/data/trafficking_division_measurements.json) · [Comparison verdict](../PROGRESS.md#daughter-bridge-closure)

### antanaviciute2018_bridge_conductance@1

Dividing sister-cell pairs from a human cell line with a visible midbody bridge. Conductance was measured across the two daughters. Original measurements in section 5. Fig. 2A shows the midbody and 2C reports the conductance distribution. [Antanavičiūtė et al. (2018), Fig. 2A–D](https://doi.org/10.3390/medicina54040053)

- **Evidence role** descriptive

Fifteen bridges, with a reported mean of 32 ± 6 nS. The authors do not identify the error statistic. Elapsed time in Fig. 2B follows a recording, and bridge age since furrowing was unreported.

Conductance ranged from below 1 to 70 nS. This supplies an electrical scale. The study lacks simultaneous repeated radii for testing conductance as a function of aperture. [Dataset manifest](../checks/data/trafficking_division_measurements.json) · [Comparison verdict](../PROGRESS.md#daughter-bridge-closure)

### green2013_daughter_isolation@1

First division of C. elegans embryos. The observable is 10 kDa dextran exchange normalized by the initial inter-daughter fluorescence difference. Fig. 4D–E, control dextran exchange slopes, with time measured from furrow ingression. [Green et al. (2013), Fig. 4D–E](https://doi.org/10.1083/jcb.201306036)

- **Evidence role** descriptive

Approximate graph readings with 90% intervals, about ten slopes per bin and partially overlapping windows.

The exchange slope fell from 0.0108/s (0.0085–0.0130) at 30 s to −0.0004/s (−0.0019–0.0011) at 260 s. The late interval includes zero. This establishes loss of measurable tracer exchange without fixing the ionic conductance or its time law. [Dataset manifest](../checks/data/trafficking_division_measurements.json) · [Comparison verdict](../PROGRESS.md#daughter-bridge-closure)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
