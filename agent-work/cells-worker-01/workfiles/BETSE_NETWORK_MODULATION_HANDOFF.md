# Native network modulation and regulator dispatch contract

The component preserves BETSE's signed control factors and ordered target
replacement, plus channel voltage/floor regulation and the explicit outer
diffusivity factor. It reuses the frozen reaction regulator parser and
activation/direct kernel without editing it. Shared models, dispatch,
documentation and root PROGRESS remain Chief-owned and unchanged.

- Law: `betse_network_modulation_source_v1_5_0@1`.
- Process: `src/cells/processes/betse_network_modulation.py`.
  SHA `c7b2129bf47ac8cd2ab02aa3626c62ec238cf8eaf31bcae95e650aedceebe100`.
- Reference, fixtures, native capture and protocol:
  `validation/regulation/betse_network_modulation*`.
- Complete receipt:
  `/mnt/workspaces/Cells/betse-network-modulation-development-20261028-04/result.json`.
  SHA `6cd841eb45b7c2774527d7f5032533be291a296a0b8d8b2c3ff4724070a31b09`.
- Frozen handoff metadata:
  `/mnt/workspaces/Cells/betse-network-modulation-handoff-20261028-01/result.json`.

The complete run passes **75 tests: 71 host and four CPU JAX**, with no skips.
Actual native captures cover **38 valid configurations and 14 limitations**.
Native/host/JAX guarded phases take **1.021 / 3.801 / 16.725 s**. Peak RSS is
**318,382,080 B**, minimum available host memory **18,221,760,512 B**, on CPU7
with one BLAS thread, <=1-GiB RSS and >=8-GiB reserve. No GPU, detached job or
persistent compilation cache ran.

## Native target and regulator semantics

There is no pinned `write_modulators` method: `read_modulators` compiles the
expressions and `run_loop_modulators` writes the factors. Reachable modulator
targets are exactly **GJ**, **Na/K-ATPase** and **TJ**. Labels advertised elsewhere
(including MT, H/K-ATPase, lower-case gj or Na/K-ATP) are not accepted branches.

`factor = max_effect * alpha`. Finite signed maximum effects and direct terms
are retained without a [0,1] clamp. Ordinary activator Hills multiply,
independent `!` activator Hills add to that product, inhibitors multiply, and
the optional signed raw-concentration direct `&` sum multiplies the expression.
Independent-only activation starts from baseline 1. Inhibitor `!` is stripped
and remains multiplicative. Broken direct-inhibitor order and only-direct
activator plus only-direct inhibitor groups are rejected as native limitations.

GJ and Na/K-ATPase regulators use native **mem_concs**, or environment samples
through the explicit `map_mem2ecm`. They do not use the cell-average array.
Each factor replaces the entire live membrane control; later source dictionary
entries win. These factors do not multiply the previous control.

TJ uses environment concentrations at the environment owner. A regulator tagged
cell becomes literal 1, including **positive 1** for a direct inhibitor. One
shared `TJ_targets` mask selects global environment sites. A target ion selects
one ion row; None/string None selects all rows. Other ion/site entries retain
their previous exact values. Later all-ion/single-ion writes replace earlier
overlapping writes. `Modulator.init_modulator` resets original `*_block_o`
arrays to ones; it does not reset live GJ/NaK factors or allocate TJ_modulator.
The component therefore requires explicit caller-owned prior live controls.

Ordinary modulators strip trailing `*` but pass `in_mem_tag=False`; they have no
voltage dependence. Channel generation passes `in_mem_tag=True`. A channel Hill
term ending in `*` uses
`Km_effective = Km * exp(sign*z*Vm*F/(R*p.T))`, with positive sign for environment
and negative for membrane. The temperature is **p.T**, not sim.T. Direct `&`
terms do not use the generated Km. Native rounded defaults are F=96485 C/mol
and R=8.314 J/(mol K), both explicit parameters; temperature is configured K.

Channel activator maxima are ignored by the actual source loop. Channel
inhibitor maxima are inserted as unparenthesized additions. For example,
`a1+m1*a2+m2` is the generated two-inhibitor expression, where
`a_j=(1-m_j)/(1+loading_j)`. It is not `(a1+m1)*(a2+m2)`. The kernel evaluates
this source sum of products in order, including zero, negative or >1 finite
maxima. It reuses the frozen activation/direct kernel and handles this
additional inhibitor polynomial explicitly.

## Binding and pure numerical API

`bind(modulators, channels, species_ids, species_valence,
membrane_to_environment, environment_count, ion_ids, ...)` returns `(topology,
parameters)`. Modulator dictionaries use the native fields. Channel dictionaries
accept full `read_channels` fields, while core construction remains caller-owned.
Names are unique within each source dictionary; duplicate overwrite is preserved
as native evidence and rejected in supported binding.

All membrane, environment, species and ion axes are explicit and nonempty.
Samples are `[...,species,membrane+environment]`, voltage `[...,membrane]`.
Membrane samples precede environment samples; cell-average-to-membrane mapping
belongs to the caller. `TJ_targets` is a boolean environment mask. The binder
currently uses physical membrane/environment/ion slots and supports neutral
**rule** padding through `rule_capacity`; it does not infer padded physical axes.

Rules are modulators in insertion order followed by channels in insertion order.
Factors are `[...,rule,site]`, with `site=max(membrane_count,environment_count)`.
Each rule uses the correct prefix of that site axis; remaining site/rule slots
are neutral zero. Parameters have final rule axes; F/R/p.T are scalars or
`[...,1]`. Parameter arrays may carry leading independent-world axes.

`evaluate(samples, Vm, topology, parameters, xp=...)` returns numeric factor and
alpha arrays. `Controls(gj, nak, tj, channel_modulator)` explicitly supplies live
prior state: membrane GJ/NaK vectors, `[...,ion,environment]` TJ and
`[...,rule,membrane]` channel modulators. Nonchannel/padded rows of the latter
are zero. `apply(factors, controls, topology, initialization=bool, xp=...)` returns
new arrays with ordered replacement and no input mutation.

`channel_run_mask(...)` implements native phase gating: INIT skips channels
whose `init_active` is exactly False, while SIM runs configured channels.
Skipped channels keep their old modulator. Named core profiles require explicit
boolean membrane masks. Alpha itself remains unmasked; source core targets are
carried in `topology.channel_targets` for the composing channel core.

Source `express` selects every membrane. It scales `channelMax` **after maxDm
was already assigned**, so the native maxDm remains the unscaled value. The
component carries all membrane targets for express and rejects a supplied
partial mask. `max conductivity` takes precedence over `max Dm` if non-None.
The source stores either value directly as maxDm and uses it as a diffusion
coefficient; there is no automatic conductance-unit conversion.

After the composing core has received its modulator and run,
`channel_diffusivity(core_P, relative_permeability, controls, topology, parameters)`
returns `[...,ion,rule,membrane]`:

`DChan = core.P * rel_perm * maxDm * applied_channel_modulator`.

Input P axes are `[...,rule,membrane]`, permeability `[...,ion,rule]`, maxDm m2/s.
P must be the actual post-update core output, with its own profile handling.
Some cores may already include the modulator in P; this explicit outer source
factor must still occur once. The helper does not run or identify a channel
isoform, enforce core state bounds, or invent missing dynamics. Respect the
run mask when deciding whether to recompute/use DChan for skipped channels.

`domain_valid(...)` is one scalar predicate for its supplied world/batch;
`vmap` gives independent world rejection. It requires nonnegative finite samples
(zero regulators are supported), finite signed factors/prior controls, positive
Km/Hill powers/F/R/p.T, nonnegative maxDm, explicit booleans/ownership and
representable factor/target outputs. Numerical kernels are unchecked. The
caller separately validates core.P/permeability, resulting diffusivity/fluxes
and its physical domain. A downstream process restricted to bounded availability
must explicitly reject or model incompatible signed factors; do not silently
clip source factors or claim they establish passive dissipation.

## Authenticated capture and dispatch boundaries

Pinned source revision is `5269a714aa2593ed2a6708c4516289977d8ae1a2`. Installed and
checkout source bytes are authenticated/copied. Captures execute actual
read_modulators/read_channels, Modulator constructor/init, Channel constructor/
init, default_zones/get_influencers and full normal/fast network channel and
modulator loop bodies. The channel initializer's seven class-dispatch branches
are exercised with a recorded **Probe** core; no native isoform dynamics is
claimed. Its prescribed P and targets are recorded. Electroflux/update_Co/
conductivity hooks record DChan and produce no transport/current, isolating the
factor and order contract. Native child imports neither Cells nor JAX.

Actual normal/fast simulator molecule/GRN network `if` blocks are also extracted
with line ranges and executed with recording handlers. The order is:
clear -> transporters -> channels -> modulators -> local network, first for
molecules and then GRN. This gives later GRN control writes precedence over
molecule writes at overlapping targets. It does not execute an entire native
simulator step. Normal-path pump/GJ/ECM consumers occur elsewhere; fast-path
source expressions differ (including direct use of G_gj in its displayed GJ
current expression). Assigning a control does not by itself prove a physical
effect in every solver mode. Composing models own consumer timing and use of
prior controls, rather than treating all fields as simultaneous gates.

Fourteen retained limitations cover unsupported target spellings/labels (four),
unknown TJ ion, broken direct inhibitor order, only-direct groups, unknown
regulator zone, duplicate-name overwrite, uninitialized live TJ array,
unsupported channel class, missing core type, missing legacy sim.dyna and short
inhibitor-max lists. Partial native state/expressions and exceptions remain in
the evidence. Core registration and the legacy sim.dyna lookup are caller-owned;
an explicit pure factor/profile declaration can be valid even when that native
core construction path fails. No source failure is silently converted to a
working native channel.

The independent 80-digit Decimal reference imports only stdlib and evaluates
factors/target writes with scalar dictionary loops. Qualified checks compare
all 38 source configurations and both normal/fast call traces, including signed
factors, overwrite order, ion/site preservation, zero regulator values,
inhibitor precedence, voltage temperature, core-target behavior and maxDm units.
The frozen dependency hash is bound in the protocol and run snapshots:
`src/cells/processes/betse_network_reactions.py`
`4731a672c7ebca1db101480f4ae4d0e13d6d9585282387384d8489b5bc184364`.

CPU JAX covers independent batches/phases, invalid-world isolation and exact
array-carry restart over four prescribed control samples 50 ms apart (sample
span 200 ms). This is a control sequence, not kinetic settling. The voltage
derivative is **0.6667209074754705 /V**, versus central difference
**0.6667209077916569 /V** at h=1e-6 V. Shared checkpoint identity, physical
clocks/events, core state and amount/energy inventories remain caller-owned.

## Evidence freeze

Attempt 01 retains a missing capture-formatting-helper failure. Attempt 02 is
explicitly source preflight (38/14, no unit-test count). Attempt 03 stops at
lint. Attempt 04 is the complete 75-test receipt. Metadata finalization only
verifies existing hashes/resources and copies this contract. No additional
scientific computation, follow-up audit or regression is running.

```sh
taskset -c 7 env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  agent-work/cells-worker-01/workfiles/check_betse_network_modulation.py \
  --output /mnt/workspaces/Cells/betse-network-modulation-development-NEW
```

All seven owned scientific files/evidence and the earlier frozen components are
unchanged after qualification. No tissue, transport, ATP, physical heat or energy
parity is inferred from a dimensionless numeric control assignment.
