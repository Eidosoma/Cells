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

**Declared-voltage evaluation exists for passive routes and transporter populations,** not yet
for @3's channel populations, which this example reads (81a29442, D252):
- `cells.passive_routes@1`: a route with `readout: true` records `passive_flux_fmol_s` (inward) and
  `passive_current_A` (outward-positive) at each observed row. `clamped_flux` gives every route's
  flux and current at declared patch voltages.
- `cells.transporter@1`: a population with `current_readout: true` records `cycle_current_A`
  (outward-positive). `clamped_rates` gives each population's rates and current at declared host
  voltages.
- **Neither runs these twins' channel law** (`kleak_always_open@1`, one of @3's channel laws):
  - a passive route opens with its patch's availability, times any routed factor, and has no
    population count of its own. So two routes on one patch can't carry their own counts and
    availabilities;
  - a transporter population runs a carrier cycle, one of the kind's cycle laws, not a channel's
    permeation.
- **@3's channel populations record only `channel_flux_fmol_s`,** at the cell's own voltage.
  Evaluating their current at a declared voltage is the @3 owner's engine work (FR-34: after N2,
  about 1–1.5 agent-days).

Until then:
- **Row 0 is at a declared voltage.** The first observed row, t = 0, is the declared initial state.
  Its voltage is the definition's charge anchor over the cell's capacitance, q0/C. So row 0's
  current is the current at that declared voltage. The output's `first_row_at_declared_voltage`
  checks it, and the test asserts it.
- **Later rows are at the run's own, evolving voltage.**

## Not covered here (engine work, in its owners' queues, D251, D252)

- **@3's channel populations at a declared voltage:** the @3 owner (above).
- **One record of the effective availability,** the held value times its routed factors: the @3 or
  operators owner.

The kinds' routes now have their per-route flux and current records, on request (81a29442).

## Run it

```
PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu /mnt/workspaces/Cells/venv-cpu/bin/python -m validation.channel_readouts.example
```
