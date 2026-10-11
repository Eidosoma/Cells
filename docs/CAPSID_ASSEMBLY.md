# Stochastic capsid assembly on CPU and GPU

`capsid_graph@1` is a Cells model family with an event solver, exposed through
`cells assembly` or `python -m cells.assembly`. It implements a constrained,
fixed-bath assembly model based on Supplementary Note 7 of
[Asor et al., Nature (2026)](https://www.nature.com/articles/s41586-026-10948-z).
Current verification and run receipts are recorded in [Progress](../PROGRESS.md).
No experimental fit or biological qualification is implied by implementation.

The paper contains real mass-photometry measurements of an engineered protein
cage. This implementation reconstructs the described stochastic model from its
mathematical/event description; it does not execute the authors' code or import
their raw trajectories. The measured system, inferred structures and simulation
assumptions remain distinct.

## Model and scope

Each world contains a single connected assembly on 20 permitted sites. A site
represents one trimer, or three protein monomers. The full cage is a
dodecahedron with 30 contacts and three neighbors per site. Its contact graph
is the generalized Petersen graph G(10,2): nodes 0–9 form a decagon, nodes
10–19 form two pentagons with increment-two connections, and spokes join i to
i+10. This prescribed geometry is part of the model, not an emergent choice
among arbitrary shapes.

Occupancy is a 20-bit integer. Occupied neighboring sites form contacts. A
declared root remains in the tracked assembly. The initial sites must form a
connected set containing that root. The controls supplied are:

| Definition | Initial material | Meaning |
| --- | --- | --- |
| [Pentamer](../configs/assembly_pentamer.json) | Five trimers in a closed ring | Prepared structural seed |
| [Open chain](../configs/assembly_open_chain.json) | Five trimers in an open path | Matched initial material with different contacts |
| [Single trimer](../configs/assembly_single_trimer.json) | One retained trimer | Conditional nucleation from an anchored starting subunit |

Each occupied–empty edge provides an association channel with propensity
`k_on_M_inv_s * free_trimer_M`. Arrival occupies the empty site and forms all
its available contacts. If several encounter edges lead to the same empty
site, each is a separate channel; this multiplicity is explicit.

Each occupied bridge edge provides a dissociation channel with propensity
`k_off_s_inv`. Removing it returns the entire component not containing the
root to the bath. Edges in cycles cannot break under this rule. Consequently,
closed loops are protected by a model assumption. This is not evidence for
zero physical dissociation over unlimited time. Completed 20-site cages are
absorbing endpoints.

The bath maintains a constant **free-trimer** concentration. It is not the
total protein-monomer concentration used on some experimental axes. The
example `17 nM`, `k_on = 10^7 M^-1 s^-1`, `k_off = 10 s^-1` corresponds to the
illustrative 1 micromolar dissociation constant used in the paper's simulation,
not a newly fitted parameter set or its measured 2D surface coefficients.
Every association/detachment updates integer transfer counters:

`occupied_trimers = initial_trimers + added_trimers - removed_trimers`

These counters are in trimer units, not fmol. The reservoir is maintained externally; its
signed material exchange is accounted for, without a finite-pool or energy
conservation claim. Detached components do not remain independent, explicitly
tracked oligomers in the bath.

This model does not yet include 2D membrane diffusion, finite pool depletion,
ring breaking, new binding geometries, protein production, turnover, division,
or coupling to the ionic models. Those require explicitly versioned extensions.

## Event clocks, randomness and observations

The direct Gillespie method samples an exponential waiting time from total
propensity and selects a channel in proportion to its propensity. Channels
are ordered by sorted graph edge: 30 association entries followed by 30
dissociation entries. A host oracle enumerates bridge events using graph
traversal. The JAX kernel independently computes connectivity with bit masks
and runs batches of independent event histories on the selected device.

Random draws use JAX's explicitly selected `threefry2x32` generator, folding
in the declared seed, stable uint32 world ID and committed event count. The
two variates lie strictly inside (0,1), using midpoints of 2^52 equal bins.
Changing batch partitioning does not change a world's random stream.
Independent simulations can be divided among devices using `world_id_start`;
the [ensemble launcher](GPU_ENSEMBLES.md) distributes these independent batches
across GPUs. A shared reservoir remains a separate model extension.

A checkpoint includes occupancy, physical observation clock, last event time,
event count, sampled pending event/time/target, integer material ledgers,
completed dwell exposure, first-passage observations and fault state. The
configuration supplies complete random stream identity. A future event beyond
a recording boundary remains pending; resuming does not resample it.

Completed sojourns are accumulated only on committed events. The unfinished
tail is added by the read-only summary. This avoids changing floating-point
accumulation when an observation window splits a waiting period. Event ties
at the requested boundary are committed before the observation.

First-passage times and exposure are reported by occupied-site count. They do
not claim that every configuration with that count has the same topology.
Unreached sizes use -1; unfinished trajectories remain censored. A complete
shell means exactly 20 occupied sites, distinct from experimentally unresolved
late intermediates. The reported mean completion time conditions on successful
completion and must not be interpreted without the censored count.

`recording: "summary"` retains full restart state and accumulated observations.
`recording: "events"` also writes bounded event chunks with time, complete
occupancy and channel index; negative indices are padding, not events. The
initial occupancy is in the resolved definition. No camera-noise, blur or
detection model has been applied to these exact simulated histories.

## Running on this machine

Code lives in the Cells checkout. Generated outputs, caches and environments
for this workspace belong under `/mnt/workspaces/Cells`; an explicit
`CELLS_OUTPUT_ROOT` selects a remote site's scratch root. Use the existing
GPU environment for both backends, or `venv-cpu` for CPU-only runs.

```bash
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B -m cells assembly validate configs/assembly_pentamer.json
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B -m cells assembly run configs/assembly_pentamer.json --backend gpu --output /mnt/workspaces/Cells/assembly-example-01 --detach
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B -m cells assembly status /mnt/workspaces/Cells/assembly-example-01
```

Choose a fresh output directory for every run. `--backend cpu` selects the CPU
kernel explicitly. Requesting an unavailable GPU fails; it does not fall back
to CPU. `--device-index` selects a device of that backend. GPU support here is
specific to this assembly family; the existing ionic model runner has its own
device and qualification contracts.

`--checkpoint-at 30` saves an additional complete checkpoint. Continue its
unchanged dynamics with `assembly resume <checkpoint-directory> --until 600
--backend gpu --output <new-directory> --detach`. The event budget counts from
the original start. Source and runtime identity are checked on load. CPU/GPU
floating-point clocks are compared within numerical tolerances; exact replay
is tested on the same backend. Altering physical rates or the seed while
loading a saved state is not a supported CLI branch operation.

Runs copy the Cells package into the output's `source/` directory. Detached
runs execute that copy with durable stdout/stderr, registration, progress,
checkpoint and completion/failure artifacts. Use that captured source and the recorded
runtime when later code changes prevent checkpoint loading. Status is read
once on request; no polling service or automatic retry is installed.

Event, array and artifact budgets are checked before allocation. The wall
budget is checked between chunks and after compilation; it is cooperative,
not a preemptive compiler timeout. Exceeding an event/wall budget produces a
failure and partial state, rather than silently counting the run as finished.
Recording and host validation costs are included in the reported total time;
compile and synchronized kernel times are reported separately. A speedup must
be measured at a matched batch size, horizon and recording policy.

## Verification targets

The focused checks cover dodecahedral geometry, event propensities and bridge
targets against independent graph traversal, full short histories against a
scalar Gillespie oracle with common variates, exponential waiting times and
symmetry of the first event, exact material accounting, absorbing controls,
saved pending-event replay, chunk/batch partition invariance, resource failures,
checkpoint corruption, explicit device use and the public CLI. Large ensembles
and comparison to experimental distributions are separate scientific work.

The seed/open-chain comparison asks whether organization changes future
assembly under matched material and local interaction parameters. Successful
seeded growth alone does not demonstrate acquisition, replication of the seed,
or renewable heredity.

## Finite material and breakable bonds

`finite_bond_assembly@1` is a separate CPU/GPU family, exposed through
`cells assembly-pool`. It retains the prescribed 20-site graph and an anchored
root, but stores occupied sites **and individual bonds**. It does not change
the paper-derived `capsid_graph@1` rules. This extension is a kinetic hypothesis,
not a fit to the measured mi3 trajectories.

Each world owns a finite free-trimer count, a fixed volume in litres, one
rooted assembly and counts of detached fragments by size. Its 79 reaction
channels are:

| Reaction | Rate and material change |
| --- | --- |
| Occupied–empty edge association | `k_on * N_free / (N_A * volume_L)` per encounter edge; consumes one free trimer and creates only the encounter bond |
| Closure between occupied, unbonded neighbors | `k_close` per edge; adds a bond without consuming material |
| Breaking any existing bond | `k_off` per bond, including bonds in cycles; retain the root-connected component |
| Detached-fragment dissolution | `k_fragment_dissolve * fragment_count[size]`; returns the fragment's entire trimer count to the free pool |

A detached single trimer returns directly to the free pool. Larger fragments
remain in their size bin until dissolution; their internal topology is not
tracked, and they cannot attach as intact oligomers. Whole-fragment dissolution
and the independent closure rate are explicit new assumptions. There is no
free-energy or detailed-balance claim. Root anchoring, prescribed geometry,
and the absence of spontaneous nucleation remain limitations.

Every checked world must satisfy the exact integer identity
`free + attached + sum(size * fragment_count[size]) == initial_total`.
Separate reaction and transfer counters reconcile attachment, detachment,
single returns and dissolved material. A full cage requires all 20 sites and
30 bonds and remains able to break. Full-cage dwell and first passage therefore
differ from merely reaching 20 attached trimers.

Complete checkpoints include bonds, all pools, reaction counters, pending
event/time, random-stream identity and dwell/first-passage records. Same-backend
continuation preserves complete state bytes across observation boundaries,
chunk sizes and world partitions. Source/runtime checks and output budgets
follow the existing assembly workflow. All clocks use float64.

```bash
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B -m cells assembly-pool validate configs/assembly_finite_pool.json
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B -m cells assembly-pool run configs/assembly_finite_pool.json --backend gpu --output /mnt/workspaces/Cells/finite-pool-example-01 --detach
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B -m cells assembly-pool status /mnt/workspaces/Cells/finite-pool-example-01
```

Use `--until` to save a complete intermediate state and `assembly-pool resume
<checkpoint-directory> --until <later-time> --output <fresh-directory>` to
continue unchanged dynamics. Resume defaults to the definition's end time;
specify `--backend gpu` for GPU continuation. The shared multi-GPU ensemble
scheduler now accepts `finite_bond_ensemble@1` campaigns, using the same queue,
persistent workers, complete pause/resume and allocation accounting. It records
first passage to all 20 sites **and 30 bonds** as cage completion; the number of
cages present at the end is reported separately. An ensemble cannot mix the two
scientific families. Test/run evidence is linked from [Progress](../PROGRESS.md).

## One-way assembly regulation of a cell

Assembly can provide an explicit molecular state between cell chemistry and
membrane function. Candidate mechanisms include a regulatory scaffold that
changes channel availability, a receptor complex that retains a response after
a cue ends, or a molecular structure that recruits replacement subunits. These
are hypotheses for new model families. The mi3 cage is not an ion channel, and
the paper does not establish any of these cellular couplings.

`assembly_regulated_cell@1`, exposed through `cells assembly-cell`, composes
one `finite_bond_assembly@1` world with one `finite_extracellular@2` ionic cell
and its Kv1p5-derived channel. The declared `root_component_has_cycle@1` rule
selects one of two availability values: for a connected rooted component,
`bond_count >= occupied_count` means at least one cycle exists. Availability
multiplies the configured channel control; intrinsic m/h gating, passive leaks,
the Na/K pump, finite bath and their ledgers retain their existing laws.
This control rule is a hypothesis about organization affecting cell function.
It does not identify the paper's cage as a channel or establish that cells use
this mechanism. Pool amounts, bound material and detached oligomers have explicit owners;
neutral protein cannot be inserted into the present charged-ion schema under
an invented valence. Trimer counts and ionic fmol require an explicit unit
conversion when material models meet. Any supplied matter or chemical work
would have its own reservoir accounting.

The GPU kernel retains both components on device. Each ionic interval ends at
the next assembly event or the next point on a fixed global ionic grid, whichever
comes first. The preceding assembly state controls the interval; the event's
new structure controls the following interval. Every ionic RK4 trial and endpoint
retains the existing domain checks. Global-grid observation boundaries preserve
the same integration path on continuation; arbitrary cuts between grid points
are refused. There is no interpolation across a structural jump. A failed ionic
stage leaves a fault artifact, not an accepted complete world.

The complete checkpoint contains both component states, the integer grid clock,
pending assembly event, availability exposure and material/charge/ionic-energy
ledgers. Loading requires the same source, runtime and backend. The initial
family requires constant external controls and one cell/channel; multiple cells,
shared protein pools, protein energetic costs and chemical feedback are absent.
Its CPU/GPU qualification compares event-split histories with an independent
ODE integration, timestep refinement, organization/disabled controls and exact
same-backend restart/window/world-partition checks. Current qualification status
is in [Progress](../PROGRESS.md).

```bash
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B -m cells assembly-cell validate configs/assembly_regulated_cell.json
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B -m cells assembly-cell run configs/assembly_regulated_cell.json --backend gpu --output /mnt/workspaces/Cells/assembly-cell-example-01 --detach
```

Use `--until` at a registered ionic grid point for an intermediate checkpoint;
continue with `assembly-cell resume <checkpoint> --backend gpu --until <later-grid-time>
--output <fresh-directory> --detach`, within the original horizon. The
[shared ensemble scheduler](GPU_ENSEMBLES.md) accepts this family through
`assembly_cell_ensemble@1`, with complete assembly/ionic pause and resume.
Current qualification and local throughput evidence are recorded in
[Progress](../PROGRESS.md); four-GPU scaling still needs measurement.

A later feedback from calcium, pH or another chemical state needs a
named rate law and its own evidence. Changing a propensity invalidates the
current model's pre-sampled future event time: a coupled extension must retain
and integrate reaction hazards, or qualify an equivalent event-clock method.
Simply replacing concentrations between calls to `capsid_graph@1` is incorrect.

| Question | Concrete comparison |
| --- | --- |
| Does organization change cell function? | Ring versus open seed with the same initial material, pool and coupling law; report channel activity and voltage as well as assembly size |
| Does a response persist after cue removal? | Common initial state, declared supply/production pulse and withdrawal, plus sham and disconnected-coupling controls |
| Can organization renew its material? | Permit actual bond breaking and subunit turnover, track old/new material, and test functional return against matched replacement controls |
| Can it be inherited? | Add explicit growth/partition laws and descendant functional assays; a parent checkpoint copied into a new world is not inheritance |

Finite supply and reversible bonds must precede a renewal claim: protected
cycles and absorbing complete shells otherwise build indefinite retention into
the model. Preserve the current paper-derived preset as a separate baseline.
Assembly and ionic kernels should retain array state on the GPU, exchanging
coupling variables at qualified common boundaries. Independent cells sharing a
pool are coupled components of one world; only independent worlds belong in the
ensemble queue. Whole-world checkpoints must include pools, assembly/hazard
state, ionic state, ledgers and the common clock. The current one-way family
provides that first composition; feedback and inheritance remain separate work.

## Assembly regulation in interacting cells

`assembly_regulated_cluster@1` composes a finite assembly pool for each cell
with `spatial_extracellular@2`. The example
[assembly_regulated_cluster.json](../configs/assembly_regulated_cluster.json)
contains two cells, their junction and three extracellular regions. Both cells
face the same local extracellular region, as required by the current spatial
field closure. Qualification status lives in [Progress](../PROGRESS.md).

Each `pools` entry names its `cell_id`, `stream_id`, finite-pool definition and
cycle-dependent channel availability. Every cell requires one pool and one
channel. Pool definitions share world IDs, horizon and resource policy; reaction
rates and initial structures may differ. Distinct uint32 stream IDs bind seeds
as `(ensemble_seed + stream_id) mod 2^32`. Ownership follows cell IDs, independent
of the input binding order or placement of a whole world on a worker. Protein
material is conserved separately in each cell; it cannot move through the ionic
junction or be counted as charged ions.

The device kernel advances the entire ionic cluster to the earliest of the next
global ionic grid point and any cell's next assembly event. All preceding
assembly states control that interval. Events at the same time commit together;
their changed channel availability applies to the following interval. Pending
events retain their sampled times as other cells change. Every RK4 trial retains
the spatial inventory, gate, charge and field-domain checks. Observation and
checkpoint boundaries lie on the global ionic grid. A dynamic window length
lets one compiled kernel serve full windows, observation boundaries and tails.
The outer independent-world loop maps complete windows with `lax.map`, retaining
scalar field/energy arithmetic for each world regardless of batch width. Cell
event operations within that world remain vectorized. Exact world-partition
replay is a qualification requirement; this execution choice still needs a
throughput measurement for the combined model.

The checkpoint records every pool and pending event, the full spatial ionic
state, common clock, per-cell availability exposure and all material/charge/ionic
energy ledgers. CLI observations include per-cell assembly summaries, voltages,
channel transfer and accounting checks. The new checkpoint format has an explicit
cluster identity; older one-cell models keep their existing identity and laws.

```bash
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B -m cells assembly-cluster validate configs/assembly_regulated_cluster.json
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -B -m cells assembly-cluster run configs/assembly_regulated_cluster.json --backend gpu --output /mnt/workspaces/Cells/assembly-cluster-example-01 --detach
```

`assembly-cluster resume CHECKPOINT --backend gpu --until GRID_TIME --output
FRESH_DIRECTORY --detach` retains the complete coupled state. The existing
ensemble queue accepts `assembly_cluster_ensemble@1`; see
[GPU ensembles](GPU_ENSEMBLES.md). A cell inside a coupled cluster is not an
independent ensemble sample. Per-cell cage statistics therefore remain separate.

The [bounded qualification protocol](../validation/assembly/cluster_protocol.json)
tests the new union of event clocks against independent scalar pool histories
and the independently implemented spatial DOP853/Radau equations. It includes
CPU/L4 agreement, timestep refinement, exact restart/window/world partition
checks, the one-cell reduction and a real two-worker L4 queue. Matched ring/open
controls preserve protein amounts. A blocked junction still permits coupling
through the shared bath, so the panel also uses a receiver with all membrane
exchange and junction transport disabled to test zero transmission.

This remains a one-way kinetic hypothesis about assembly organization controlling
a channel. Chemical feedback, protein energetic costs, cross-region junctions,
experimental validation and multi-GPU scaling are separate work.
