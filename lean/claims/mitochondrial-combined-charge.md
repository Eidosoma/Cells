<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Zero outer current preserves combined matrix and intermembrane-space charge

At fixed compartment water volumes the change in total matrix and intermembrane-space row charge equals the signed charge admitted through the outer membrane. A conducting passive face has a unique zero-current voltage. The initial inventory needs an intermembrane-space charge as well as a matrix charge.

## Assumptions

- Sum all species with their physical valences, including charge redistributed by internal redox and binding. There is no hidden counter-ion, external current source or outer-membrane capacitive charge.
- The seven inner-cycle columns conserve charge across both sides. Additional internal reactions must also conserve charge.
- The passive single-face uniqueness result uses positive total charged conductance. Zero outer voltage at the anchor and start is the G5 initialization rule. Later voltages follow the current constraint.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.MitochondrialCharge.cycles_cancel](../CellsProofs/Chemistry/MitochondrialCharge.lean#L18)
- [CellsProofs.Chemistry.MitochondrialCharge.inventory_change](../CellsProofs/Chemistry/MitochondrialCharge.lean#L30)
- [CellsProofs.Chemistry.MitochondrialCharge.conserved_iff](../CellsProofs/Chemistry/MitochondrialCharge.lean#L46)
- [CellsProofs.Chemistry.MitochondrialCharge.zero_current_iff](../CellsProofs/Chemistry/MitochondrialCharge.lean#L51)
- [CellsProofs.Chemistry.MitochondrialCharge.anchor_ne](../CellsProofs/Chemistry/MitochondrialCharge.lean#L63)
- [CellsProofs.Chemistry.MitochondrialCharge.form_flux_charge](../CellsProofs/Chemistry/MitochondrialCharge.lean#L68)

Direct proof subject `cells.nadh_ubiquinone_proton_cycle@1`, `cells.ubiquinol_cytochrome_c_proton_cycle@1`, `cells.cytochrome_c_oxygen_proton_cycle@1`, `cells.proton_coupled_atp_synthesis_cycle@1`, `cells.electrogenic_nucleotide_exchange@1`, `cells.phosphate_proton_symport@1`, `cells.potassium_proton_exchange@1`

Proof sources [Cells inner-cycle charge columns specialized to arbitrary signed extents](../CellsProofs/Chemistry/MitochondrialCycles.lean) · [Mathlib finite sum distribution, imported for the weighted row balance](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L267-L269) · [Cells G5 and the seventh inventory](https://github.com/Eidosoma/Cells/blob/e924f450ad74a878eda6727ac255527ec5d74ff7/docs/MITOCHONDRIA_DESIGN.md#g5-the-outer-membranes-potential) · [Mathlib exchange of finite sums, imported for form and ligand fluxes](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Sigma.lean#L112-L121)

## Numerical comparison

**Open.** In two compiled seven-cycle worlds with a potassium-only outer face, combined charge changed by at most 1.27 × 10⁻¹⁸ fmol of charge equivalents. Initial IMS-minus-bath voltage was 0 mV at matched K and −85.61293 mV at a 140:5 gradient. The original outer face admitted K and AMP individually and refused five other declared rows. The forms-aware law now has a [separate transport comparison](forms-face-carriage.md). The full MT-1b anchor/start comparison remains open.

**Engine** `resolved_pump_tissue@3`, `cells.nadh_ubiquinone_proton_cycle@1`, `cells.ubiquinol_cytochrome_c_proton_cycle@1`, `cells.cytochrome_c_oxygen_proton_cycle@1`, `cells.proton_coupled_atp_synthesis_cycle@1`, `cells.electrogenic_nucleotide_exchange@1`, `cells.phosphate_proton_symport@1`, `cells.potassium_proton_exchange@1`, `cells.logmean_electrodiffusion@1`

[Seven-cycle host and its public start](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/tests/unit/test_mito_cycle_laws.py#L85-L144) · [Compartment topology and held bath](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/validation/compartment_ph_engine/definitions.py#L118-L175) · [Public parser](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/src/cells/definitions/specs.py) · [Time stepping](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/src/cells/execution/runner.py) · [Floating field and charge allowance](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/src/cells/numerics/surface_field.py#L34-L65) · [Node charges and compiled face transfer ledger](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/src/cells/models/surface_pump_v3.py) · [Form valences and transport admission](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/src/cells/registry/species_registry.py#L1493-L1550) · [Admission for rows with several forms](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/src/cells/registry/species_registry.py#L1620-L1652) · [Closure rows at a face](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/src/cells/registry/species_registry.py#L1809-L1852) · [Definition of capacitor topology and start-state charge](https://github.com/Eidosoma/Cells/blob/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b/docs/MITOCHONDRIA_DESIGN.md#g5-the-outer-membranes-potential) · [Form flux translated to stored row charge](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/CellsProofs/Chemistry/MitochondrialCharge.lean) · [Seven-cycle fixture](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/checks/mitochondrial_cycles.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/checks/mitochondrial_outer_face.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/PROGRESS.md#mt1b-outer-admission)

[Tested engine 57c3cb909db5](https://github.com/Eidosoma/Cells/commit/57c3cb909db5ebe9a24b90f3d78d7c6a182fd72b) · [Evidence checkpoint cecbe3627a7a](https://github.com/Eidosoma/Cells/commit/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78)

**Engine** `resolved_pump_tissue@3`, `cells.nadh_ubiquinone_proton_cycle@1`, `cells.ubiquinol_cytochrome_c_proton_cycle@1`, `cells.cytochrome_c_oxygen_proton_cycle@1`, `cells.proton_coupled_atp_synthesis_cycle@1`, `cells.electrogenic_nucleotide_exchange@1`, `cells.phosphate_proton_symport@1`, `cells.potassium_proton_exchange@1`

[Complex I](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/laws/cycles/nadh_ubiquinone_proton_cycle.py#L20) · [Complex III](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/laws/cycles/ubiquinol_cytochrome_c_proton_cycle.py#L35) · [Complex IV](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/laws/cycles/cytochrome_c_oxygen_proton_cycle.py#L37) · [ATP synthesis](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/laws/cycles/proton_coupled_atp_synthesis_cycle.py#L35) · [Nucleotide exchange](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/laws/cycles/electrogenic_nucleotide_exchange.py#L34) · [Phosphate import](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/laws/cycles/phosphate_proton_symport.py#L28) · [Potassium–proton exchange](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/laws/cycles/potassium_proton_exchange.py#L16) · [Seven-cycle public host fixture](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/tests/unit/test_mito_cycle_laws.py#L85-L144) · [Public engine runner](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/execution/runner.py) · [Signed N and P ledger contributions](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/kinds/transporter.py#L844) · [Generic passive open-circuit face component](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/numerics/extracellular_field.py#L78-L139) · [Charge and thermal constants](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/src/cells/laws/electrochemistry.py) · [Per-form outer face outstanding in the mitochondrial comparison](https://github.com/Eidosoma/Cells/blob/fe6d25e9eee7a7d0422568fd356a57e67ef03301/validation/mitochondria/component_comparison.py#L35-L41) · [Signed cycle stoichiometry](https://github.com/Eidosoma/Cells/blob/b475c62fbfbcb913f12498b71681e8cbf057d433/lean/CellsProofs/Chemistry/MitochondrialCycles.lean) · [Combined inventory and passive-face proof](https://github.com/Eidosoma/Cells/blob/b475c62fbfbcb913f12498b71681e8cbf057d433/lean/CellsProofs/Chemistry/MitochondrialCharge.lean) · [Seven-cycle world](https://github.com/Eidosoma/Cells/blob/b475c62fbfbcb913f12498b71681e8cbf057d433/lean/checks/mitochondrial_cycles.py) · [Cellular outer-potential measurement](https://github.com/Eidosoma/Cells/blob/b475c62fbfbcb913f12498b71681e8cbf057d433/lean/checks/data/abrantes2026_outer_voltage.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b475c62fbfbcb913f12498b71681e8cbf057d433/lean/checks/mitochondrial_charge.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b475c62fbfbcb913f12498b71681e8cbf057d433/lean/PROGRESS.md#mt1b-combined-charge)

[Tested engine fe6d25e9eee7](https://github.com/Eidosoma/Cells/commit/fe6d25e9eee7a7d0422568fd356a57e67ef03301) · [Evidence checkpoint b475c62fbfbc](https://github.com/Eidosoma/Cells/commit/b475c62fbfbcb913f12498b71681e8cbf057d433)

## Biological evidence

**Open.** Intermembrane-space and bath voltage in the isolated mitochondrial preparation at the declared anchor and start, together with valence-weighted inventories.

**Unit** mV from IMS to external reference and fmol of charge equivalents

### abrantes2026_outer_voltage

In intact cells from a human cell line, compartment-targeted measurements gave mean bulk IMS pH 7.96 and mean cytosolic pH 7.41. The authors inferred +33 ± 11 mV, positive on the IMS side. Figure 1E, equation 1 and accompanying Results. [Abrantes et al. (2026), Mitochondrion 102218](https://doi.org/10.1016/j.mito.2026.102218)

- **Evidence role** descriptive

The pH observations have reported SDs of 0.08 (IMS) and 0.17 (cytosol). Converting the gradient to voltage assumes proton equilibrium.

The cellular gradient makes the compartment definition consequential. It leaves the voltage of isolated mitochondria in their declared bath and the initial combined charge unmeasured. [Dataset manifest](../checks/data/abrantes2026_outer_voltage.json) · [Comparison verdict](../PROGRESS.md#mt1b-combined-charge)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
