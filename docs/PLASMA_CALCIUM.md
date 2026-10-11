# Plasma calcium extrusion and exchange

`spatial_calcium@2` adds named plasma calcium transport to the
[owned spatial calcium model](SPATIAL_CALCIUM.md). The
[ionic example](../configs/plasma_calcium_cluster.json) and
[assembly example](../configs/assembly_regulated_plasma_calcium_cluster.json)
use synthetic parameters. Current status and run evidence live only in
[PROGRESS.md](../PROGRESS.md).

The [qualification protocol](../validation/chemistry/plasma_protocol.json)
addresses a concrete new risk: active calcium transport and electrogenic
exchange must transfer the correct ions, charge and energy between the same
finite inventories already owned by the spatial/ER model. Adding a duplicate
free-calcium pool or counting NCX as ATP work would violate that contract.

## Transport laws and evidence scope

`betse_1_5_plasma_calcium_pump_positive@1` preserves the positive-concentration
equation in pinned BETSE 1.5.0
[`pumpCaATP`](https://github.com/betsee/betse/blob/v1.5.0/betse/science/sim_toolbox.py).
With `Vm = inside minus outside`, positive cycles move one calcium outward:

```text
drive = delta_g0 + RT ln(ADP * Pi / ATP)          [numeric mM quotient]
G_pmca = drive + RT ln(Ca_out / Ca_in) - 2 F Vm
r_pmca = capacity * availability
         * Ca_in/(Km_Ca + Ca_in) * ATP/(Km_ATP + ATP)
         * (1 - exp(G_pmca / RT))                [fmol/s]
```

Capacity is the membrane-integrated native `alpha_Ca * area / 1e-15`.
The native function returns inward flux per area, giving the opposite sign.
Its `block` argument is unused; Cells' explicit availability multiplier is a
separately tested extension. Native input clipping and zero-denominator repair
are excluded from the strictly positive domain. This is function correspondence,
not a claim about complete native trajectories or a proton-resolved pump cycle.
ATP, ADP and phosphate are maintained external parameters; their work is recorded.

`ncx_3na_1ca_symmetric_barrier@1` is a **synthetic reversible kinetic law**.
The forward cycle is `3 Na_out + Ca_in -> 3 Na_in + Ca_out`, moving one net
positive charge inward. Giant-patch experiments support electrogenic exchange
with reversal close to the 3-Na/1-Ca relation
([Hilgemann and colleagues, 1992](https://pubmed.ncbi.nlm.nih.gov/1336540/)).
Those measurements do not determine the capacities or kinetic denominator used
here; this law is neither a native BETSE NCX implementation nor a fitted model.

```text
a = Na_in/Km_Na; b = Na_out/Km_Na
c = Ca_in/Km_Ca; d = Ca_out/Km_Ca; x = F Vm/(RT)
D = (1 + a^3 + b^3) (1 + c + d)
r_ncx = capacity * availability * (b^3 c exp(-x/2) - a^3 d exp(x/2)) / D
G_ncx = RT ln((Na_in/Na_out)^3 * Ca_out/Ca_in) + F Vm
```

This denominator preserves the specified reversal potential. Production uses
logarithms and `expm1` for stable near-stall evaluation; the independent reference
uses direct forward/reverse products. NCX has no ATP work term. Each route's
dissipation is `-1e-3 * rate * G` pJ/s and is nonnegative in either direction.
The affinity limit is `abs(G/RT) <= 80`, with `abs(Vm) <= 0.15 V`.

## Ownership, controls and execution

The model requires explicit calcium and sodium species roles and exactly one
route record per membrane. A pump or exchanger can be `null`; availability and
zero capacity disable transfers exactly. Each membrane has its own schedule
starting at zero, with pump/exchanger availability between zero and one. Its
boundaries join existing channel, junction and ER control boundaries.

Every RK4 stage gathers free cytosolic ions and finite outside amounts. It adds
`-(r_pmca + r_ncx)` calcium and `3*r_ncx` sodium to cytosol and whole-cell exchange
ledgers, and the opposite changes to outside inventories. Plasma voltage uses
whole-cell charge. ER exchange remains internal and cannot charge the outer
capacitor. New checkpoint fields retain both cycle counts and each route's
dissipation; no transported amount is silently repaired.

Total energy includes the existing chemical/capacitor terms, all route
dissipation and maintained PMCA work `-1e-3 * drive * cycles`. Its tolerance
remains **1e-9 pJ**. Both stage domains and read-only observation cubics retain
positive amounts, bounded affinities and monotone dissipation. An additional
concentration-independent substrate-loss bound includes the PMCA reverse rate
and NCX rates at the maximum admitted voltage. Shared outside owners accumulate
all contributions. Actual step times the combined chemical/plasma bound must be
at most 0.25, alongside inherited spatial guards; this is not an accuracy proof.

The ordinary float64 CPU/GPU scalar, batch, window and complete-checkpoint APIs
apply. Assembly continues to regulate potassium-channel availability; plasma
transport changes calcium and voltage without changing the declared protein
event streams. Ensemble planning retains this model identity and independent
world IDs through the existing four-node/16-GPU target.

The bounded CPU/L4 panel freezes source and reference inputs and compares full
trajectories with independent DOP853/Radau solutions, timestep refinement,
blockers, reversal, exact reductions, restart/partition replay and assembly
event histories. It also runs the previous spatial/ER/chemistry regression panel:

```bash
PYTHONPATH=src /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  validation/assembly/qualify_cell.py launch \
  /mnt/workspaces/Cells/plasma-calcium-YYYYMMDD-NN \
  --chemistry --chemistry-case plasma
```

The runner detaches and writes completion or failure artifacts. After a GPU
timeout with a completed CPU report, `--cpu-baseline /mnt/workspaces/Cells/previous-run`
copies the frozen scientific source and authenticated CPU evidence into the new
run for the matching `plasma`, `gated` or `ip3` panel. Only the runner may change;
test identities, exact GPU-only deferrals, protocol, scalar/assembly baseline
checksums and CPU runtime must match. The entire GPU phase runs afresh, with
per-test logs and a complete report. With CPU reuse, optional
`--gpu-retry-wall-seconds 14400` registers a separate four-hour retry allowance
without editing the frozen protocol or its numerical tolerances. It cannot
shorten the original allowance. Compilation caches are copied independently
and the original run remains untouched.

Throughput profiling follows numerical qualification separately. Native full trajectories,
finite ATP, volume/water, mechanics, calcium feedback on assembly and
biological calibration remain open. The versions below add explicitly scoped
calcium channels and IP3 control; qualification status is recorded in `PROGRESS.md`.

## Voltage-gated calcium entry (`spatial_calcium@3`)

The [ionic example](../configs/gated_calcium_cluster.json) and
[assembly example](../configs/assembly_regulated_gated_calcium_cluster.json)
add one explicitly owned CaV1.2 channel per plasma membrane alongside the
existing potassium channel. Each calcium channel has separate `m`/`h` gates,
a signed inward calcium transfer ledger, a dissipation ledger and a timed
availability schedule. The old `@1` and `@2` definitions retain their meanings.

`betse_cav1p2_m2h@1` follows the pinned BETSE 1.5.0
[`Cav1p2` equations](https://github.com/betsee/betse/blob/v1.5.0/betse/science/channels/vg_ca.py):
use `u = Vm - 0.010 V`, with opening `m^2 h` and
`dg/dt = (g_inf - g)/tau`. Targets and time constants are:

```text
m_inf = 1 / (1 + exp(-(u + 0.030)/0.006))
h_inf = 1 / (1 + exp( (u + 0.080)/0.0064))
tau_m = 0.005 + 0.020/(1 + exp((u + 0.025)/0.005))  [s]
tau_h = 0.020 + 0.050/(1 + exp((u + 0.040)/0.007))  [s]
```

The −10 mV shift and gate powers are checked directly against the pinned
native class. BETSE's semi-implicit gate update is separately checked for
convergence to the held-voltage continuous solution. Cells advances the gates
with the shared RK4 stages; finite-step native trajectory equivalence is not
implied. The supported voltage interval is −120 to +60 mV at the existing
298.15 K engineering fixture. No temperature correction is inferred from the
source's experimental-temperature annotation.

Permeability is `maximum * abundance * availability * m^2 h`. Calcium flux uses
the existing reversible constant-field law with valence +2 and the current
finite concentrations. Its reversal follows those concentrations; the native
class's fixed `vrev` annotation is not a replacement for that transport law.
Each flux updates the owned free cytosolic calcium, the whole-cell charge ledger
and the corresponding outside region at the same solver stage. The dissipation
rate is `-flux * delta_mu`, with no ATP work assigned to the passive channel.
Gates can keep relaxing while availability or permeability is zero.

The [qualification protocol](../validation/chemistry/gated_protocol.json)
addresses gate-unit/sign/power errors and double counting of calcium, charge or
energy. It retains the 1e-9 pJ energy tolerance, inventory/domain checks,
independent adaptive references, timestep refinement and complete scalar/batch/
assembly restart checks on CPU and L4. New gate and energy cubics are enclosed
between observations. Conservative channel inventory loss joins the existing
chemical/plasma loss bound; gates also have a step/minimum-time-constant bound.

Assembly continues to regulate the potassium channels. Changes to voltage can
therefore influence calcium entry, but calcium does not yet change protein
assembly rates. The examples use synthetic channel abundance/permeability and
explicit initial gates. Biological calibration, calcium-dependent inactivation,
gating charge/energy and native whole-simulator correspondence remain separate.

## Finite IP3 control of ER release (`spatial_calcium@4`)

The [ionic example](../configs/ip3_calcium_cluster.json) and
[assembly example](../configs/assembly_regulated_ip3_calcium_cluster.json)
give each cell an explicit `ip3_release` binding to its own free cytosolic `IP3`
species. The required `IP3` moiety distinguishes free ligand from bound complexes.
At every shared RK4 stage, concentration is the current finite amount divided
by cytosolic volume. The existing calcium-dependent ER release permeability is
multiplied by:

```text
a = (IP3_cytosol_mM / activation_mM)^activation_n
IP3_factor = a / (1 + a)
```

`betse_1_5_ip3_er_release@1` follows the IP3 branch of pinned BETSE 1.5.0
[`EndoRetic.channels`](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/organelles/endo_retic.py).
The native source searches molecule, metabolic and GRN networks in that order.
With a network present but no IP3 it disables the regulated route; with all
networks absent it retains calcium-only regulation. Cells makes the IP3 choice
explicit through `@4`; prior model identities keep their original behavior.
The qualification checks the native branches, priorities, units and Hill powers.
It does not reproduce those networks' initialization or lifecycle.

This gate changes release flux without consuming ligand. The same ER transfer,
charge and energy ledgers account for that flux; no second calcium or IP3 pool
is introduced. IP3 evolves through ordinary compartment chemistry. The examples
use **synthetic reversible binding**, `IP3 + IP3_buffer <-> IP3_bound`, to exercise
changing ligand levels while conserving both ligand and binding sites. Their
concentrations, rates and affinities are engineering parameters. The nominal
−3 charge assigned to free and bound IP3 is an explicit synthetic convention,
not a measured protonation state or a pH-dependent biochemical model.

The [qualification protocol](../validation/chemistry/ip3_protocol.json) addresses
reading the wrong cell/compartment, freezing IP3 between stages, and losing
chemical conservation during coupling. It retains the same reference, CPU/GPU,
energy and domain tolerances as `@3`, with whole-cubic positive-inventory checks,
independent DOP853/Radau trajectories, timestep refinement, complete checkpoints,
batch partitions and assembly event-history comparisons. IP3 concentration and
release fraction appear in observations and per-cell ensemble summaries. All
integrated ligand state uses the existing chemical checkpoint arrays; the new
binding parameters and model identity are checked during restart.

```bash
PYTHONPATH=src /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  validation/assembly/qualify_cell.py launch \
  /mnt/workspaces/Cells/ip3-calcium-YYYYMMDD-NN \
  --chemistry --chemistry-case ip3
```

The runner detaches with frozen inputs, logs and completion/failure artifacts.
This adds a signaling route to the integrated simulator: finite IP3 influences
ER release, calcium and voltage while assembly regulates potassium channels.
Calcium/IP3 feedback onto protein assembly rates, IP3 synthesis/degradation,
intercellular IP3 diffusion and biological calibration remain separate work.
