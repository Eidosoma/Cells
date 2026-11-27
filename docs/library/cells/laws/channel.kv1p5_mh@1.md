# Kv1.5-type potassium channel gating (`cells.channel.kv1p5_mh@1`)

**In one sentence:** A potassium channel that opens within milliseconds when the membrane voltage rises, then slowly shuts over seconds, letting potassium out so that the voltage falls back.

## In plain words

Every cell holds a voltage across its membrane, and [channels](../../GLOSSARY.md#channel) are the
pores that let ions cross it. This law says when one type of potassium channel is open. It has two
[gates](../../GLOSSARY.md#gate). The first opens within milliseconds when the inside of the cell
becomes less negative; the second shuts over seconds after the same change. Ions pass only while
both are open. Potassium usually leaves the cell, so opening this channel brings the voltage back
down. Because the slow gate remembers the last few seconds, two cells with the same open fraction
can respond differently next. The law leaves out temperature (it is fixed at 25 °C), the charge
that moves when a gate moves, and the energy of the channel protein itself.

## Seen from each field

- **Biology:** a voltage-dependent outward potassium current with slow inactivation, as SPEC-006
  relays for Kv1.5 expressed in oocytes. Its form and numbers come from another simulator's
  description of the Kv1.5 channel, not from a fit to any cell type.
- **Chemistry:** each gate is an open–shut equilibrium whose rates depend on voltage; the two
  gates are independent.
- **Physics:** two first-order relaxations toward sigmoid targets, with time constants linear in
  voltage.
- **Computing:** a pure function from voltage to targets and time constants. The host advances the
  gates and computes the current.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Law, interface `cells.channel_law@1` ([its fields](../../DECLARATIONS_FORMAT.md#channel-laws)) |
| ID | `cells.channel.kv1p5_mh@1`; definitions write `cells.channel.kv1p5_mh@1` |
| Runs in | `cells.model.resolved_pump_tissue@3`, its host. Definitions of `cells.model.resolved_pump_composite@1` and `cells.model.resolved_pump_tissue@3` can declare it |
| Registry code | 0 |
| Provenance | `parity`: moved from an older family; moving is not calibrating |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Role | What | Unit | Which way is positive |
| --- | --- | --- | --- |
| Reads | None declared | | |
| Changes | `K`: valence 1, relative permeability 1.0 | Not stated | Not stated |
| Its gates, kept by the host | `m` and `h` | | |

Energy role: not yet extracted; the law template has no energy role yet.

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

| Declared | Value | Unit |
| --- | --- | --- |
| Voltage domain | -0.12 to 0.06 | V |
| Reference RK4 step | 2.5e-05 | s |
| Stage term | `constant_field_slope` |  |

<!-- /generated -->

With $V$ the [membrane voltage](../../GLOSSARY.md#membrane-voltage) (inside less outside, in volts),
$t$ in seconds and $\sigma(x) = 1/(1 + e^{-x})$:

$$m_\infty = \sigma\!\left(\frac{V + 0.0060}{0.0064}\right), \qquad h_\infty = \sigma\!\left(-\frac{V + 0.0253}{0.0035}\right)$$

$$\tau_m = 0.008330 - 0.1163\,V, \qquad \tau_h = 1.620 - 15.50\,V$$

$$\frac{dm}{dt} = \frac{m_\infty - m}{\tau_m}, \qquad \frac{dh}{dt} = \frac{h_\infty - h}{\tau_h}, \qquad \text{open fraction} = m\,h$$

- **Domain:** −0.120 V ≤ V ≤ 0.060 V, chosen so that both time constants stay positive ($\tau_m$
  from 1.35 to 22.3 ms, $\tau_h$ from 0.69 to 3.48 s). A step outside it is refused, never clipped.
- **Assumptions:** each gate lies between 0 and 1 and relaxes monotonically at fixed $V$. Both are
  kept as state, since equal products $m h$ can have different futures. The temperature is fixed
  at 298.15 K, with no temperature law.
- **The current:** the host multiplies the [open fraction](../../GLOSSARY.md#open-fraction) by the
  population's permeability, abundance and availability, and moves potassium by the
  [constant-field flux](../../GLOSSARY.md#constant-field-flux), the form of the route law
  `cells.route.constant_field@1`. Which way a positive flux points is not declared.
- **Integration:** the host advances each gate by its exponential stage update. The reference RK4
  step is at most 25 µs.
- **Left out:** gating charge, conformational energy and protein turnover.
- **Scope (D351):** the law has no pH input. Three labs agree in sign, not in size, that
  acidifying the outside shifts Kv1.5's activation (+11.7, +17.3 and +7.8 mV). Its potassium–pH
  interaction is an indication, from different readouts. The law carries neither.
- **The acid shift is declared on the population, not in the law (D356, FR-64).** A world gives
  its m gate a pH shift on the outside (`voltage_shift`, `{"ph": {...}}`). The gate then reads
  V - sigma (pH - pH_ref), its target and its time constant together. Each preparation's slope is
  a two-point secant through its own midpoints, so it is calibrated, not judged (D399). The
  time constant's shift is unclaimed.

## Sources

<!-- generated: provenance -->

Provenance: `parity` (moved from an older family; moving is not calibrating). No citation is declared.

<!-- /generated -->

| Work | What was taken | Mark |
| --- | --- | --- |
| BETSE v1.5.0's `Kv1p5` channel, at the commit that SPEC-006 pins | The two-gate form and its coefficients, converted to SI units, with both gate powers one | Relayed from [SPEC-006](../../../VOLTAGE_GATED_CHANNEL_SPEC.md) (D049), which read the source |
| Philipson et al. 1991, which that source cites | Nothing directly. SPEC-006 states that its abstract reports Kv1.5 expressed in oocytes, with a slowly inactivating outward current, which does not establish each coefficient | Relayed from SPEC-006, which read its abstract |

**Departures, as SPEC-006 states them:** the gates follow the continuous equations, not the
source's semi-implicit update; the source's reversal-voltage constant is not used, since the
current is the constant-field flux; the domain and the fixed temperature are Cells' own choices.

**The licence of the numbers:** not stated by the declaration.

## How it is checked

<!-- generated: tests -->

Declared test: [`tests/unit/test_channel_law_kernels.py`](../../../../tests/unit/test_channel_law_kernels.py), `test_kv1p5_meets_the_independent_decimals_and_each_plant_misses_them`.

<!-- /generated -->

The kernels are compared with an independent copy of the equations above, in SI decimals, at 19
voltages across the domain, from −0.12 to 0.06 V, in NumPy and compiled. Each value must lie within
1e-14 of the reference's, relatively; the largest distance measured is 3.8e-15. Moving any one of the
eight coefficients by a part in 10⁹ must miss the targets or the time constants, and $m h^2$ for
$m h$ must miss the open fraction. The 19 voltages are those of an older model family's cases, whose
check moved beside the law (D196).

Other rows run the source's unchanged class out of process and compare its targets, time constants,
gate powers and update clock with these kernels. No run was compared with a measurement.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/laws/channels/kv1p5_mh.py`](../../../../src/cells/laws/channels/kv1p5_mh.py) (`cells.laws.channels.kv1p5_mh`).
- Kernels: `kinetics`, `cells.laws.channels.kv1p5_mh.kinetics`; `opening`, `cells.laws.channels.kv1p5_mh.opening`.
- Runs in `cells.model.resolved_pump_tissue@3`.
- Manifest entry: (law, `cells.channel.kv1p5_mh@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.channel.kv1p5_mh@1`.

<!-- /generated -->

Further reading: [SPEC-006](../../../VOLTAGE_GATED_CHANNEL_SPEC.md); the inner model's
declarations, [the inner-model design](../../../INNER_MODEL_V4_DESIGN.md), §7.1.
