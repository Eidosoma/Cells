# Osmotic water flow and cell volume (`cells.operator.ideal_osmosis_linear_compliance_water@1`)

**In one sentence:** Water crosses each cell membrane toward the side with more dissolved particles, so cells swell or shrink until an elastic back-pressure balances that pull.

## In plain words

Water crosses membranes by osmosis: it moves toward the side where dissolved particles are more
concentrated. This [operator](../../GLOSSARY.md#operator) gives every cell, and every finite space
outside the cells, a volume that changes as water flows. The flow across a membrane patch grows
with its area, its water permeability and the difference in
[water potential](../../GLOSSARY.md#water-potential) between its sides: the pressure of the
stretched compartment, less the osmotic pressure of what is dissolved in it. Concentrations are
amounts divided by current volumes, so swelling dilutes everything inside, which changes voltages
and rates. A large bath keeps its own volume and composition; the water it gives or takes is
booked as supply, with its work. Left out: changes of membrane area, water through junctions or in
open solution, and the effect of temperature on permeability.

## Seen from each field

- **Biology:** osmotic swelling and shrinking. Aquaporins raise the water permeability, which is a
  value of the definition.
- **Chemistry:** the ideal (van 't Hoff) osmotic pressure: RT times the total concentration of
  dissolved particles.
- **Physics:** flow driven by a difference of water potential through a hydraulic conductance, with
  a linear elastic pressure–volume law. The dissipated power is the flow times that difference, and
  is never negative.
- **Computing:** an operator of the composite. Half-steps of Heun's method advance the volumes
  before and after the inner model's step (Strang splitting). It owns the volume increments and
  four water ledgers.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Operator, interface `cells.operator@1` ([its fields](../../DECLARATIONS_FORMAT.md#operators)) |
| ID | `cells.operator.ideal_osmosis_linear_compliance_water@1`; definitions write `cells.operator.ideal_osmosis_linear_compliance_water@1` |
| Runs in | `cells.model.resolved_pump_composite@1`, its host. Definitions of `cells.model.resolved_pump_composite@1` can declare it |
| Where it acts in the step | A split part, by `heun_frozen_amount_water@1`; scheduled by `water_controls` |
| Needs | No law or kind |
| Provenance | Not yet extracted: the composite's operator contract has no provenance field yet |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Field | Role | Axes | Unit | Which way is positive |
| --- | --- | --- | --- | --- |
| `membrane_area` | Reads (fixed, at the split stage) | | m2 | |
| `volume_increment_pL` | Owns | cell_slot | pL | Not stated |
| `extracellular_volume_increment_pL` | Owns | extracellular_slot | pL | Not stated |
| `water_transferred_pL` | Owns | membrane_slot | pL | Not stated |
| `water_dissipated_energy_pJ` | Owns; heat | membrane_slot | pJ | Not stated |
| `bath_water_supplied_pL` | Owns | extracellular_slot | pL | Not stated |
| `bath_water_work_pJ` | Owns; work | extracellular_slot | pJ | Not stated |
| `volume` | Provides | | pL | Not stated |
| `extracellular_volume` | Provides | | pL | Not stated |
| `cell_volume_pL` | Provides | | pL | Not stated |
| `extracellular_volume_pL` | Provides | | pL | Not stated |
| `cell_concentration_mM` | Provides | | mM | Not stated |
| `extracellular_concentration_mM` | Provides | | mM | Not stated |
| `osmotic_pressure_Pa` | Provides | | Pa | Not stated |
| `hydrostatic_pressure_Pa` | Provides | | Pa | Not stated |
| `water_potential_Pa` | Provides | | Pa | Not stated |
| `water_flow_pL_s` | Provides | | pL/s | Not stated |
| `water_dissipation_pJ_s` | Provides | | pJ/s | Not stated |
| `bath_water_supply_pL_s` | Provides | | pL/s | Not stated |
| `water_availability` | Provides | | Not stated | Not stated |
| `energy_balance_pJ` | Provides | | pJ | Not stated |
| `water` | Controls | | Not stated | |

Writes into other pieces' fields: none. Ledgers: `water_local`, `water_outside`, `water_total` and `bath_water_work`. Records: none declared.

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

None declared.

<!-- /generated -->

With amounts $n$ in fmol, volumes $V$ in pL, pressures in Pa and energies in pJ:

$$\Pi = \frac{R T \left(\sum_s n_s + n_\text{imp}\right)}{V}, \qquad P = K\left(\frac{V}{V_\text{ref}} - 1\right) + P_0, \qquad \psi = P - \Pi$$

$$Q = 10^{15} A\, L_p\, a\, (\psi_\text{cell} - \psi_\text{out}) \ \text{pL/s, cell to outside}, \qquad D = 10^{-3}\, Q\, (\psi_\text{cell} - \psi_\text{out}) \ge 0 \ \text{pJ/s}$$

- **The terms:**
  - $\Pi$ is the ideal (van 't Hoff) [osmotic pressure](../../GLOSSARY.md#osmotic-pressure) of the
    declared amounts and the neutral impermeants;
  - $P$ is a linear elastic pressure, with stiffness $K$ about the reference volume
    ([compliance](../../GLOSSARY.md#compliance));
  - $A$ is the patch's area and $L_p$ its
    [hydraulic permeability](../../GLOSSARY.md#hydraulic-permeability);
  - $a$ is the patch's scheduled water [availability](../../GLOSSARY.md#availability), from 0 to 1.
- **A [held bath](../../GLOSSARY.md#held-bath)** keeps its volume and composition, so its water
  potential $\psi_b = P_b - RT\sum_s c_{b,s}$ is fixed. The water it exchanges is booked as supply,
  with the work $10^{-3}\,\psi_b\,dS$.
- **In the step:** $\Phi_{dt} = W_{dt/2} \circ I_{dt} \circ W_{dt/2}$, a
  [split step](../../GLOSSARY.md#split-step). $I$ is the inner model's own step at frozen volumes,
  and $W$ advances the volumes at frozen amounts by Heun's method. Under RK4, the water rates join
  the coupled right-hand side instead.
- **Refused, never repaired:** a volume at its bound; $dt$ times the water relaxation rate above
  0.05; an availability outside [0, 1].
- **Assumptions:** an ideal dilute solution; membrane areas and capacitances held fixed; water
  carries no solute and no charge; each declared species counts once; fixed-charge equivalents
  carry no particles.

## Sources

<!-- generated: provenance -->

Provenance: not yet extracted; the composite's operator contract has no provenance field yet.

<!-- /generated -->

| Work | What was taken | Mark |
| --- | --- | --- |
| The ideal (van 't Hoff) osmotic pressure, and a linear compliance | The forms of $\Pi$ and $P$ | Standard forms, named in [the water guide](../../../PUMP_WATER_MODEL.md); no work is cited |
| Manning and Kay 2023, J Gen Physiol 155:e202313332, Eq. 6 | $L_p = P_f V_w / (RT)$, to set $L_p$ from an osmotic permeability $P_f$ | Relayed from the water guide; unread here |

The parameter values ($P_f$, $K$, $P_0$, the volume bounds and the impermeants) belong to each
definition, not to this operator. The water guide's "Parameters" table gives their sources, with
its own marks.

## How it is checked

<!-- generated: tests -->

Declared test: not yet extracted; the composite's operator contract has no test field yet.

<!-- /generated -->

The water kernel is compared with an independent reference written for its thermodynamics and its
graphs: the stage values, conservation over an owned graph, sealed edges and the pressure gauge,
the relaxation bound, and the refusal of invalid volumes.

Recorded evidence, with its scope: on 11 November the water law was qualified as the model
`cells.model.resolved_pump_water@1`. Its judged run passed 25 of 25 criteria against predictions frozen from an
independent reference ([Progress](../../../../PROGRESS.md), "Osmotic water and volume qualified and
landed"). This operator is that law, moved unchanged. But the record names the model, not this
operator in today's compositions, so no status is copied from it.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/operators/osmotic_water.py`](../../../../src/cells/operators/osmotic_water.py), class `OsmoticWater` (`cells.operators.osmotic_water`).
- Runs in `cells.model.resolved_pump_composite@1`.
- Manifest entry: (operator, `cells.operator.ideal_osmosis_linear_compliance_water@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.operator.ideal_osmosis_linear_compliance_water@1`.

<!-- /generated -->

Further reading: [the water guide](../../../PUMP_WATER_MODEL.md);
[the water reference](../../../WATER_VOLUME_REFERENCE.md); [the composite](../../../PUMP_COMPOSITE.md).
