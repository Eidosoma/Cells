# Channel population readouts (FR-34): count, availability and signed current

A maintained example of the fields that report a membrane channel population's surface count,
availability and signed current today, with the request's control (D251). The code is in
`example.py`. The test `tests/unit/test_channel_readouts_example.py` runs it.

## The fields, their units and signs

| Quantity | Field | Units | Sign and meaning |
| --- | --- | --- | --- |
| Surface count | `population_units`, cells.operator.membrane_entity_state@1's readout, per channel slot | units | The population's units: its declared count plus every writer's increment. Only where membrane state is composed |
| Relative abundance | `channel_abundance`, @3's view field | 1 | a = N / (A rho_ref). A view field, not an observation column |
| Availability | `channel_availability`, @3's observation, per channel slot | 1 | The availability the population runs at, **before the routing door**. In a composite it already holds the operators' factors (species_regulated_availability's writes and step-view routes, which that operator also records as `coupling_factor`): **do not multiply it by them again**. `channel_effective_availability` adds only the routing door's factors (D265) |
| Flux | `channel_flux_fmol_s`, @3's observation, per species and channel slot | fmol/s | **Positive outward:** a positive amount leaves the cell of the population's patch for that patch's outside node |
| Current, derived | I = 1e-15 F sum_s z_s J_s, from the flux | A | **Positive outward** (for a cation, outward flux). Derived in `example.py`; no field holds it |
| Voltage | `membrane_voltage_V`, @3's observation, per patch | V | Inside minus outside |

## The control

The world holds two gate-free K populations (`cells.channel.kleak_always_open@1`) on one patch of one cell, with
the same count:
- `kir_0` at availability 1;
- `leak_1` at availability 0.5.

On one patch they share the voltage and both ends' concentrations at every row, so the same driving
force. So `leak_1`'s current must be half of `kir_0`'s at every observed row, and it is, to
rounding.

## At a declared voltage

**Declared-voltage evaluation now exists for @3's channel populations too:** @3's
`clamped_channel_flux` (FR-34, D252), and in a composite the composition's own entry point (below,
D265). The rest of this section is the record from before it landed. It covered passive routes and
transporter populations, not yet @3's channel populations, which this example reads (81a29442,
D252):
- `cells.kind.passive_routes@1`: a route with `readout: true` records `passive_flux_fmol_s` (inward) and
  `passive_current_A` (outward-positive) at each observed row. `clamped_flux` gives every route's
  flux and current at declared patch voltages.
- `cells.kind.transporter@1`: a population with `current_readout: true` records `cycle_current_A`
  (outward-positive). `clamped_rates` gives each population's rates and current at declared host
  voltages.
- **Neither runs these twins' channel law** (`cells.channel.kleak_always_open@1`, one of @3's channel laws):
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

## In a composite world (D265)

A composite runs @3 at its **control view**: the stored control times the operators' factors, and
its providers' layout view. So:
- **`channel_availability` already holds the operators' factors.** Multiplying it by the
  recorded `coupling_factor` applies the factor twice.
- **@3's `clamped_channel_flux` given the composite's stored state, controls and layout loses the
  operators' factors.** A population held at 0.5 by cells.operator.species_regulated_availability@1 read 11.10328
  pA at -50 mV, where the composite runs at 5.55164 pA. In a composite, call the composition's
  own entry point, `model.clamped_channel_flux(state, control, p, voltages_V)`
  (`cells.models.pump_composite`). It hands @3 the step's views (`clamp_inputs`), and at the
  cell's own voltage it gives the recorded flux bit for bit.
- **The kinds' clamped evaluations** (`clamped_flux`, `clamped_rates`) take the same views through
  `model.clamped_kind(function, state, control, p, voltages_V)`.

## Not covered here

Both items this section once listed as pending engine work (D251, D252) have landed:
- **@3's channel populations at a declared voltage:** @3's `clamped_channel_flux` (merge
  121aca27). In a composite, use the composition's own `model.clamped_channel_flux` and
  `model.clamped_kind` (merge 07022ddf, D265; above). Tests:
  - `tests/unit/test_surface_pump_v3_populations.py`:
    `test_a_population_s_current_at_a_declared_voltage_with_the_halving_control`;
  - `tests/unit/test_species_regulated_availability.py`:
    `test_a_composites_clamped_current_runs_at_its_effective_availability` and
    `test_a_composites_clamped_kinds_are_the_steps_own_rates`.
- **One record of the effective availability:** `channel_effective_availability`, @3's observation
  per channel slot (merge d0104950). It is the held availability times the population's
  routing-door factors, the value its flux runs at.
  - It is recorded only where a population declares `factors`. Elsewhere that value is
    `channel_availability`, and the column does not exist.
  - In a composite, `channel_availability` already holds the operators' factors, and this column
    adds only the door's.
  - Test: `tests/unit/test_surface_pump_v3_populations.py`:
    `test_the_effective_availability_is_recorded_where_the_door_routes_into_channels`.

The kinds' routes have their per-route flux and current records, on request (81a29442).

**What these readouts still do not give:**
- **A current after the gates settle.** The clamped entry points keep the state's gates, so they
  give the instantaneous current at the declared voltage, not a steady-state current-voltage curve.
- **A one-way flux.** `channel_flux_fmol_s`, `passive_transferred` and `passive_flux_fmol_s` are
  net, so equal and opposite one-way flows cancel.
- **A recorded current column for @3's channel populations.** Derive it from
  `channel_flux_fmol_s`, as in the table above, or with
  `cells.models.surface_pump_v3.channel_current_A(flux, p)`.

## Run it

```
PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu /mnt/workspaces/Cells/venv-cpu/bin/python -m validation.channel_readouts.example
```
