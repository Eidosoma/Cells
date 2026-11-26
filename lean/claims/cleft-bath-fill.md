<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Fluid from a held bath dilutes a growing cleft in proportion to its added volume

Filling a well-mixed cleft conserves solute. Its concentration stays between the original cleft and bath concentrations, and its excess above the bath scales with the retained volume fraction. Subdividing the fill gives the same endpoint. Dividing a facing patch between daughter cells preserves its total contribution to cleft volume.

## Assumptions

- The cleft has positive initial volume. Added volume is nonnegative and arrives at the held bath concentration. The solute has no other source or sink during the fill.
- Gap width stays fixed. The two daughter patches inherit the same fractions of current area and onset area, and replace the parent in the sum over live patches.
- In the compiled comparison a neutral tracer is impermeant and face diffusion is zero. The account records the completed fill. The observer also includes the most recent half-step of membrane growth.

## Lean proof

**Proved**

- [CellsProofs.Tissue.RestrictedLumen.material_balance](../CellsProofs/Tissue/RestrictedLumen.lean#L18)
- [CellsProofs.Tissue.RestrictedLumen.mixed_pos](../CellsProofs/Tissue/RestrictedLumen.lean#L23)
- [CellsProofs.Tissue.RestrictedLumen.dilution](../CellsProofs/Tissue/RestrictedLumen.lean#L29)
- [CellsProofs.Tissue.RestrictedLumen.mixed_bounds](../CellsProofs/Tissue/RestrictedLumen.lean#L35)
- [CellsProofs.Tissue.RestrictedLumen.fills_compose](../CellsProofs/Tissue/RestrictedLumen.lean#L50)
- [CellsProofs.Tissue.RestrictedLumen.split_volume](../CellsProofs/Tissue/RestrictedLumen.lean#L57)

Direct proof subject `cells.operator.restricted_cleft_lumen@1`, `cells.operator.restricted_cleft_lumen@2`

## Numerical comparison

**Checked.** Five compiled controls checked all seven rows for volume, bath supply, tracer concentration and cumulative heat. When 0.010 pL at 4 mM grew to 0.020 pL from a 1 mM bath, both versions and a 60:40 patch split in version 2 gave 2.5 mM. The maximum concentration error was 4.45 × 10⁻¹⁶ mM.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.membrane_entity_state@1`, `cells.scheduled_membrane_insertion@1`, `cells.scheduled_membrane_insertion@2`, `cells.restricted_cleft_lumen@1`, `cells.restricted_cleft_lumen@2`, `cells.isopotential_partition@1`

[Area target for one patch](https://github.com/Eidosoma/Cells/blob/d16976560e255eba8ff600068a326a0946e22f62/src/cells/operators/restricted_lumen.py#L229) · [Supply from the held bath and volume booking](https://github.com/Eidosoma/Cells/blob/d16976560e255eba8ff600068a326a0946e22f62/src/cells/operators/restricted_lumen.py#L292) · [Observed volume and concentration](https://github.com/Eidosoma/Cells/blob/d16976560e255eba8ff600068a326a0946e22f62/src/cells/operators/restricted_lumen.py#L527) · [Area summed over live facing patches](https://github.com/Eidosoma/Cells/blob/d16976560e255eba8ff600068a326a0946e22f62/src/cells/operators/restricted_lumen_v2.py#L201) · [Partition event map](https://github.com/Eidosoma/Cells/blob/d16976560e255eba8ff600068a326a0946e22f62/src/cells/operators/partition.py#L879) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/e106a3da24cbd8443c3b3cb60091e4820b8a1375/lean/checks/restricted_lumen.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/e106a3da24cbd8443c3b3cb60091e4820b8a1375/lean/PROGRESS.md#cleft-bath-fill)

[Tested engine d16976560e25](https://github.com/Eidosoma/Cells/commit/d16976560e255eba8ff600068a326a0946e22f62) · [Evidence checkpoint e106a3da24cb](https://github.com/Eidosoma/Cells/commit/e106a3da24cbd8443c3b3cb60091e4820b8a1375)

## Biological evidence

**Open.** Cleft width and bath access. A test of dilution during growth requires a paired cleft-volume and tracer-concentration time series.

**Unit** µm

### spring1979_cleft_geometry@1

Live Necturus gallbladder epithelium in NaCl Ringer. The optically resolved area omits fine membrane folds. Table I and pp. 291–292 give lateral area and assigned interspace volume. Table III gives pooled control volume per border length. [Spring and Hope (1979), Tables I and III](https://doi.org/10.1085/jgp.73.3.287)

- **Evidence role** calibration
- **Fit** Resting lateral area and assigned interspace volume per cell

Area was 3,540 ± 150 µm² per cell (SEM, n = 32). Assigned interspace volume was about 2,080 µm³ per cell. Volume per border length was 41.1 ± 4.7 µm³/µm (SEM, n = 19).

The resting geometry gives an effective full gap width of 1.18 µm. The section-based estimate of 1.19 µm reuses the same images. [Dataset manifest](../checks/data/cleft_measurements.json) · [Comparison verdict](../PROGRESS.md#cleft-bath-fill)

### dolega2021_intercellular_space@1

Neighbouring cells in living CT26 spheroids. Confocal dye profiles measured width and bath tracers probed access to the extracellular matrix. Appendix 1, sections C.1–C.2, reports the layer width and size-dependent access. [Dolega et al. (2021), Appendix 1, Figs. 3–4](https://doi.org/10.7554/eLife.63258)

- **Evidence role** descriptive
- **Observed** 0.9 µm

Reported width was 0.9 ± 0.1 µm across 132 profiles, with a correction for 0.27 µm optical resolution.

Tracers of 4.4 and 5.8 nm radius entered the space. Tracers above 14.8 nm were largely excluded. Access therefore depends on the solute. [Dataset manifest](../checks/data/cleft_measurements.json) · [Comparison verdict](../PROGRESS.md#cleft-bath-fill)

### ikonomov1985_cleft_ions@1

Ion-selective micropuncture of lateral spaces in Necturus gallbladder epithelium. The abstract reports the result under the three bath and current conditions. [Ikonomov, Simon and Frömter (1985)](https://doi.org/10.1007/BF00583604)

- **Evidence role** descriptive

The authors report no reliable ion-concentration difference between lateral spaces and bath. A tracer-specific detection threshold and a mixing time are unavailable from this comparison.

Local ion measurements support bath-like concentrations under those conditions. Dilution during growth remains untested. [Dataset manifest](../checks/data/cleft_measurements.json) · [Comparison verdict](../PROGRESS.md#cleft-bath-fill)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
