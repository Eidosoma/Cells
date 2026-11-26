<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Sodium coupling sets net charge and the stall voltage of an anion carrier

A forward cycle imports n sodium ions and one monovalent anion. The two source-side saturations and capacity scale the net rate. With n > 1 the carrier imports below its unique stall voltage. With n = 1 its rate is independent of voltage.

## Assumptions

- Positive concentrations at N and P and a forward cycle from P to N. Both roles use the same standard state at their two ends. The engine admits n = 1, 2, 3 or 4. Capacity, availability and both saturations are positive in the active-stall theorem.
- Equal-fraction external sodium and substrate changes assume fixed internal activities. Measured whole-cell voltage shifts yield the isolated shift ratio if both changes carry the same nonzero conductance weighting.

## Lean proof

**Proved**

- [CellsProofs.Transport.SodiumAnionSymport.source_rate](../CellsProofs/Transport/SodiumAnionSymport.lean#L23)
- [CellsProofs.Transport.SodiumAnionSymport.transported_rows](../CellsProofs/Transport/SodiumAnionSymport.lean#L35)
- [CellsProofs.Transport.SodiumAnionSymport.electrical_work](../CellsProofs/Transport/SodiumAnionSymport.lean#L40)
- [CellsProofs.Transport.SodiumAnionSymport.energy_relative_to_stall](../CellsProofs/Transport/SodiumAnionSymport.lean#L45)
- [CellsProofs.Transport.SodiumAnionSymport.symport_stall_iff](../CellsProofs/Transport/SodiumAnionSymport.lean#L51)
- [CellsProofs.Transport.SodiumAnionSymport.import_iff](../CellsProofs/Transport/SodiumAnionSymport.lean#L56)
- [CellsProofs.Transport.SodiumAnionSymport.export_iff](../CellsProofs/Transport/SodiumAnionSymport.lean#L63)
- [CellsProofs.Transport.SodiumAnionSymport.neutral_rate](../CellsProofs/Transport/SodiumAnionSymport.lean#L67)
- [CellsProofs.Transport.SodiumAnionSymport.capacity_scaling](../CellsProofs/Transport/SodiumAnionSymport.lean#L73)
- [CellsProofs.Transport.SodiumAnionSymport.external_shift_ratio](../CellsProofs/Transport/SodiumAnionSymport.lean#L80)

Direct proof subject `cells.cycle.na_anion_symport_factored@1`

Uses [Free energy sets ATP-driven transport direction and stall](atp-cycle.md)

## Numerical comparison

**Checked.** All 120 stages agreed with independent 60-digit free energies, saturation, rates and heat. The panel covered both orientations, all four sodium counts and twelve active stalls. The two-step tissue run gained exactly the lactate amount recorded as transported cycles and reported zero global charge error.

**Engine** `resolved_pump_tissue@3`, `cells.na_anion_symport_factored@1`

[Carrier rows and source saturations](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/laws/cycles/na_anion_symport_factored.py#L42) · [Host state and free energy](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/kinds/transporter.py#L1407) · [Numerically stable factored rate](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/laws/cycles/forms.py#L923) · [Charge and heat readout](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/src/cells/kinds/transporter.py#L1877) · [Decimal constants](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/validation/core_seams/references/exact.py#L44) · [Roundoff floors](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/validation/core_seams/references/design.py#L39) · [Tissue carrier fixture](https://github.com/Eidosoma/Cells/blob/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984/tests/unit/test_na_anion_symport_factored.py#L44) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/40dfe4de2a04559196bddef7e32c01cffc056e7b/lean/checks/sodium_anion_symport.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/40dfe4de2a04559196bddef7e32c01cffc056e7b/lean/PROGRESS.md#19-november-2026--inward-rectification-and-sodium-anion-symport)

[Tested engine ced58d2a1edc](https://github.com/Eidosoma/Cells/commit/ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984) · [Evidence checkpoint 40dfe4de2a04](https://github.com/Eidosoma/Cells/commit/40dfe4de2a04559196bddef7e32c01cffc056e7b)

## Biological evidence

**Open.** Charge per lactate, particles per charge and the ratio of voltage shifts with external sodium and substrate halving in human SMCT1.

- [Each human SMCT1 cycle imports two Na⁺ per propionate.](../WET_LAB_EVIDENCE.md#pair-smct-propionate-stoichiometry) · Different experimental results

**Unit** net positive charges per lactate

### gopal2004_propionate_charge@1

Human SMCT expressed in Xenopus oocytes. Integrated substrate-induced current and radiolabel uptake. Fig. 9B and accompanying human SLC5A8 results, p. 44530. [Gopal et al. (2004), Fig. 9B](https://doi.org/10.1074/jbc.M405365200)

- **Evidence role** descriptive

The ± is the authors' reported SE. The human series is distinct from the mouse series and from Fig. 9A lactate.

Human SMCT1 gave 2.7 ± 0.2 net charges per propionate. With a monovalent anion and entirely coupled current, the implied sodium count is 3.7 ± 0.2. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

### coady2007_smct1@1

Human SMCT1 in Xenopus oocytes. The Cells declaration cites this study for the two-sodium coupling. Fig. 1 compares lactate uptake with current, and Fig. 2 compares volume with current. Fig. 4 uses both 96 to 48 mM and 48 to 24 mM sodium steps, each paired with substrate halving. [Coady et al. (2007), Figs. 1, 2 and 4](https://doi.org/10.1529/biophysj.107.108555)

- **Evidence role** descriptive
- **Evaluation** Lactate charge and particle ratios, Lactate and propionate zero-current shift ratios
- **Excluded** Mixed inhibitor-sensitive clamp reversal, Propionate tracer uptake
- **Observed** 1.04 net positive charges per lactate
- **Predicted** 1 net positive charges per lactate

The reported charge uncertainty was ±0.07 across five batch slopes. The volume/current and shift ratios are reported as mean ± SE.

The two-sodium carrier also predicted 3 osmolytes per charge versus 3.1 ± 0.1 measured. It predicted a shift ratio of 2 for both sodium halvings. The experimental means were 2.2 ± 0.2 for lactate and 2.3 ± 0.3 for propionate. Absolute stall and Hill kinetics remain open. [Dataset manifest](../checks/data/coady2007_smct1.json) · [Comparison verdict](../PROGRESS.md#19-november-2026--law-and-evidence-review)

### gopal2004_lactate@1

An independent laboratory measured human SMCT in Xenopus oocytes. The coupling was fixed from the Coady study. Human series, square symbols. The x axis is integrated charge and the y axis is radiolactate uptake. [Gopal et al. (2004), Fig. 9A](https://doi.org/10.1074/jbc.M405365200)

- **Evidence role** held out from fitting
- **Fit** Coupling n = 2 from Coady et al.
- **Evaluation** Four distinguishable human lactate uptake/current pairs
- **Excluded** Mouse series and propionate

Approximate figure readings rounded to 5 pmol. Individual experimental uncertainties are unavailable.

Measured net charge exceeded the prediction at all four human points by approximately 65–85 pmol. At 370 pmol lactate, Cells predicted 370 pmol net charge and the figure gives about 450 pmol. [Dataset manifest](../checks/data/gopal2004_lactate.json) · [Comparison verdict](../PROGRESS.md#19-november-2026--inward-rectification-and-sodium-anion-symport)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
