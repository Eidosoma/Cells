# Native standalone GRN orchestration

This separate prefix qualifies an explicit prepared-phase boundary around the
actual standalone `MasterOfGenes.run_core_sim` workflow. Its purpose is to test
the different clock, reinitialization, history/cache and dispatch semantics of
`sim_grn`. The supplied phase represents initialized ions/geometry; seed/init/sim
file loading, automatic initialization and full SimRunner parity are excluded.
The accepted neutral GRN source supplies unchanged scientific bodies and readers;
the new package imports neither pending charged GRN nor transporter code.

The original SimRunner new-owner branch constructs a local MasterOfGenes and
reads its real native configuration. The entire original `run_core_sim` body is
retained, including real `reinitialize`, `clear_cache`, Core/Molecule calls,
`write_data`, `report`, `init_saving` and both CSV exporter bodies. The owner is
local; this boundary executes no normal solver guarded GRN dispatch or ordinary
ion/pump/gate/current/voltage step. Source publication is forced False. Configured
modulators remain present and are never dispatched, and no per-step
`clear_run_loop` is inserted.

Source time is unusual: `N=int(total/dt)` points span `linspace(0,N*dt,N)`.
The first `t=0` point still advances a numerical dt, and for N>1 the timestamp
spacing is N*dt/(N-1). Sampling repeatedly truncates `i+t_resample`. A sampling
interval below dt can stall that original loop; the supported boundary refuses
it explicitly without altering native timing. N=1, fractional sampling/truncated
total duration, sparse sampling, different successive clocks, temperature split
and time dilation have separate declared cases.

Each advancing invocation forces publication off and rewrites clock parameters,
then reinitializes properties without resetting concentrations. Original sampled
histories and owner time reset; simulator sample times append to the supplied
existing list. Every public owner/Core/Molecule/reaction/modulator field, the
prepared simulator/parameter fields and boundary vector are captured and carried.
The port explicitly hydrates immutable parents and rebuilds live aliases, while
the native comparison retains actual live objects between invocations. Typed
full-state, chemistry/mover/order, sample and CSV-output comparisons cover both.

File output is an explicit in-memory boundary. The original init_saving body
updates its paths and checks plot-cell admission; original CSV exporters write
their actual output into StringIO. Directory operations are recorded, and the
saveSim call records its argument identities and complete scientific snapshot.
Actual pickle serialization/filesystem persistence is excluded and receives no
credit. The late invalid-plot-cell case preserves all completed Core steps and
the preceding save/directory calls before the original capacity/config exception.

Independent cold and local Decimal90/140 references reuse the accepted equations.
The only warm-reference change removes modulator dispatch to match standalone
source order; a static inverse AST check recovers the accepted warm reference.
A separate standard-library clock specification independently predicts the
binary64 endpoint grid and sample indices, and Decimal counts the numerical dt
advanced. All inputs precede constructors/outgoing Core calls. Error/budget arrays
are archived before assertions; budgets use independent gross terms and inherited
concentration/flux/rate floors. Source-effective amounts, declared single-bath
defects and directed-GJ changes remain distinct and explicitly checked.

Raw cases preserve cold configuration failure, first/second molecule instability,
a second-invocation reinitialize failure before cache clear, and late output
admission failure. Unsupported ECM, mitochondria, fluid/cuts, unsafe sampling,
missing owner/boundary state and file restart have exact admission witnesses.
There is no mitochondrial/ECM substitution, physical/energetic conservation,
finite/shared-fuel, biological or independently carried trajectory claim.

Chief owns any numerical scheduling. Preparation uses only source parsing,
original-AST builders, compilation without import, hash/ownership checks and
Ruff. Frozen neutral, charged and transporter scientific files stay unchanged.
