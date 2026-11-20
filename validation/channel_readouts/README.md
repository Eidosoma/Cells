# Channel population readouts (FR-34): count, availability and signed current

A maintained example of the fields that report a membrane channel population's surface count,
availability and signed current today, with the request's control (D251). The code is in
`example.py`. The test `tests/unit/test_channel_readouts_example.py` runs it.

## The fields, their units and signs

| Quantity | Field | Units | Sign and meaning |
| --- | --- | --- | --- |
| Surface count | `population_units`, membrane_entity_state@1's readout, per channel slot | units | The population's units: its declared count plus every writer's increment. Only where membrane state is composed |
| Relative abundance | `channel_abundance`, @3's view field | 1 | a = N / (A rho_ref). A view field, not an observation column |
| Availability | `channel_availability`, @3's observation, per channel slot | 1 | The scheduled availability, **before the routing door**. Where species_regulated_availability routes factors onto the population, it runs at this value times the factors, which that operator records separately as `coupling_factor` |
| Flux | `channel_flux_fmol_s`, @3's observation, per species and channel slot | fmol/s | **Positive outward:** a positive amount leaves the cell of the population's patch for that patch's outside node |
| Current, derived | I = 1e-15 F sum_s z_s J_s, from the flux | A | **Positive outward** (for a cation, outward flux). Derived in `example.py`; no field holds it |
| Voltage | `membrane_voltage_V`, @3's observation, per patch | V | Inside minus outside |

## The control

The world holds two gate-free K populations (`kleak_always_open@1`) on one patch of one cell, with
the same count:
- `kir_0` at availability 1;
- `leak_1` at availability 0.5.

On one patch they share the voltage and both ends' concentrations at every row, so the same driving
force. So `leak_1`'s current must be half of `kir_0`'s at every observed row, and it is, to
rounding.

## At a declared voltage

No field yet gives a population's current at a voltage the user declares. That readout is engine
work in its owner's queue (D251), and this example will use it when it lands.

Until then:
- **Row 0 is at a declared voltage.** The first observed row, t = 0, is the declared initial state.
  Its voltage is the definition's charge anchor over the cell's capacitance, q0/C. So row 0's
  current is the current at that declared voltage. The output's `first_row_at_declared_voltage`
  checks it, and the test asserts it.
- **Later rows are at the run's own, evolving voltage.**

## Not covered here (engine work, in its owners' queues, D251)

- A population's current at any declared voltage.
- One record of the effective availability: the held value times its routed factors.
- Flux or current records per route for the kinds' routes, such as the passive-routes rectifier,
  which record only `passive_transferred`, cumulative and inward.

## Run it

```
PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu /mnt/workspaces/Cells/venv-cpu/bin/python -m validation.channel_readouts.example
```
