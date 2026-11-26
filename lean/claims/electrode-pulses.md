<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Signed electrode pulses deliver the declared carrier charge

A pulse delivers the time-integrated current times the sum of the carrier fractions. For fractions summing to one this equals Ih at either polarity. On a single clamped patch the source books the change in chemical and capacitor energy less the clamp work.

## Assumptions

- Current is constant over the interval h. Each active carrier has nonzero signed charge per fmol and the cell can supply every amount removed.
- The tolerance theorem assumes the exact sum of the represented fractions is within the bound. The parser tests their floating-point sum. The one-patch energy identity assumes fixed capacitance and bath potential.
- The physical comparison closes the background transport and uses an ideal solution at fixed cell volume.

## Lean proof

**Proved**

- [CellsProofs.Tissue.CurrentInjection.booked_charge](../CellsProofs/Tissue/CurrentInjection.lean#L18)
- [CellsProofs.Tissue.CurrentInjection.pulse_charge](../CellsProofs/Tissue/CurrentInjection.lean#L28)
- [CellsProofs.Tissue.CurrentInjection.charge_error](../CellsProofs/Tissue/CurrentInjection.lean#L34)
- [CellsProofs.Tissue.CurrentInjection.single_patch_work](../CellsProofs/Tissue/CurrentInjection.lean#L45)

Direct proof subject `cells.operator.electrode_current_injection@1`

Proof sources [ATOMS Lab base dimensions and energy, imported in the optional units check](https://github.com/ATOMSLab/LeanDimensionalAnalysis/blob/de263eed945693058ef2b8a1fa56c2ec5642ea7a/DimensionalAnalysis/Dimensions.lean#L10-L43) · [Cells specialization for charge times voltage](../checks/units/FacePower.lean)

## Numerical comparison

**Checked.** Three carrier mixtures passed opposite 1 pA pulses. All material, charge and work ledgers matched the independent calculation. A fraction sum of 1.0000000005 delivered 2.000000001 fC for a nominal 2 fC.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.electrode_current_injection@1`

[Fraction-sum tolerance](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/operators/current_injection.py#L107) · [Cell, carrier reservoir and clamp bookings](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/operators/current_injection.py#L168) · [Ideal chemical and capacitor energies](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/models/pump_composite_adapter.py#L825) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/checks/current_injection.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/PROGRESS.md#electrode-pulse-ledgers)

[Tested engine b9d6452dff1c](https://github.com/Eidosoma/Cells/commit/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc) · [Evidence checkpoint b4353f85b18d](https://github.com/Eidosoma/Cells/commit/b4353f85b18d489a277818bfe43e20c8416b6066)

## Biological evidence

**Open.** Calibrated delivered current, the carrier-specific supply and removal, and clamp work on the same cell and pulse interval.

**Unit** C, fmol and pJ

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
