# Native active-temperature correspondence and proposed policy

This investigation addresses the active 298.15 K composition gap. It does not
change an existing model, guard, accepted state or thermal law. Chief assigned
new `validation/temperature/*` files and this specialist note; shared scientific
documents and `PROGRESS.md` remain Chief's responsibility. The unrelated CPU5
voltage-transition run is left untouched and unpolled.

## Pinned evidence and scope

BETSE 1.5.0 revision `5269a714aa2593ed2a6708c4516289977d8ae1a2` is the
authority for numerical correspondence. `validation/temperature/source_manifest.json`
pins the complete 129-file science scan and every executed source file.
`protocol.json` declares temperatures 273.15, 288.15, 298.15, 310.15 and 323.15 K,
two constant profiles, ordinary voltages, explicit singular probes, immutable
tolerances and CPU4/resource limits. These are computational probe points, not
biological validity bounds or evidence of calibration at these temperatures.

The probes execute unchanged AST bodies, preserving the upstream equations and
line numbers. They use manufactured arrays and minimal state owners, not a
native simulation. Pure logging is replaced with a no-op; the native exception
type has a local RuntimeError stand-in, outside the positive probe paths. The
actual native `update_gj` caller delegates to the actual native flux body. Three
actual reaction expression generators are executed before their expressions
are evaluated. Independent Decimal/scalar references do not call Cells, JAX or
BETSE. The separate replay imports saved columns and independent references
with all three production package roots denied. Raw numerical arrays, warnings,
source failures and missing whole-simulation coverage remain explicit.

## Source findings

Paths and line numbers below refer to the exact pinned revision. Executable
inventory artifacts retain complete supported class bodies, comments, source
hashes, exact temperature sites and enclosing functions.

| Path/site | Temperature semantics and limitation |
| --- | --- |
| `betse/science/sim.py:528`; `tissue/tishandler.py:784` | Initialization copies `p.T` into `sim.T`; the global pulse assigns `sim.T = p.T * (1 + multT*pulse)` without changing `p.T`. The pulse multiplier is dimensionless. A global setter alone is not a uniform replacement of all configured temperatures. |
| `sim_toolbox.py:18,71,124,184` | GHK, Na/K, PMCA and SERCA take explicit T in K. Their usual membrane/store callers pass live `sim.T`. `R*T` has J/mol units and `F*V/(R*T)` is dimensionless. No Q10 is implied by these factors. |
| `sim.py:2162` (`update_gj`) | The actual gap-junction flux call passes **configured `p.T`**, not runtime `self.T`. The caller probe varies both independently and retains the discrepancy. Its voltage-sensitive junction branch is disabled in this isolated caller fixture; channel inventory supplies separate gate evidence. |
| `sim_toolbox.py:385,415,442,1363`; `sim.py:974,986,1426,2016` | Nernst–Planck entry points take T but conductivity uses configured `p.T`; multiple Debye/conductivity/precomputed coefficients also use `p.T`. Both `q/kb` and `F/R` conventions occur. A whole native thermal program cannot be claimed from a single flux probe. |
| `channels/channelsabc.py:40,60` | Fixed source HH backward Euler clock uses `dt = p.dt*time_unit`. Dynamic Morris–Lecar also uses its fixed `Phi`; instantaneous ML overwrites m by its target and has no physical gate relaxation time. |
| Seven supported channel modules, 55 class bodies | Actual initialization, target/tau calculation, state update and opening are probed across both runtime-only and reinitialization T changes, full/reordered targets, with voltage held fixed. Their live equations do not read T. This is direct invariance of the isolated classes, not invariance of coupled voltage/calcium feedback or proof all classes are reachable from native YAML. |
| `channels/vg_ca.py:155,209,265,314,366,425,491,549,602,662,718` | Source `Texpt` metadata includes 0, 21, 36 and 23 degrees C. Commented `2.3**((simT-Texpt)/10)` is not executable scaling; live `qt` is 1 where present. No universal empirical reference temperature or Q10 follows. In particular, the Cells 298.15 K guard is a composition contract, not evidence all 55 native curves were fitted at 25 C. |
| `tissue/channels_o.py:11` (`cagPotassium`) | Separate legacy instantaneous opening explicitly reads `sim.T`, free calcium and voltage, with factors `6182`, `1.64`, `1e6`, `10.22`, `.89` retained literally. No direct caller is present in the 129-file scan; indirect/dynamic reachability is not proved. This is the 56th supported catalog law, not another temperature-invariant class. |
| `chemistry/networks.py:1493,1756,2011` | Cytosol/mitochondria/exterior reaction generators use `exp(-delta_Go/(p.R*sim.T))`. A constant input `delta_Go` in J/mol gives T-dependent equilibrium; freezing a dimensionless `mu_RT` gives a different law. Transporter generation around 2604 also includes live T; generated influencer expressions around 5210/5413 use configured `p.T`. |

Native constants are literal `F=96485`, `R=8.314`, `q=1.602e-19`,
`kb=1.3806e-23`, `NAv=6.022e23`, in SI units (`parameters.py:1105–1116`).
The literal and matched-SI profiles remain separate evidence. The latter
explicitly sets exact SI q, kb, NAv and derives F and R, exposing rather than
hiding the native `q/kb` versus `F/R` discrepancy. Native `deltaGATP=-37000`
is J/mol; one pump comment labels it J/(mol K), inconsistent with the parameter
declaration and the dimensionless exponent. References use the equation's J/mol
interpretation and retain the conflicting comment in the frozen source.

### Pump and standard-state distinctions

The native Na/K quotient converts numeric mM to molar activities with `1e-3`.
Its hydrolysis factor is `ADP*Pi/(1000*ATP)`; it returns `(-3*j, 2*j, 3*j)`,
including the documented legacy extra return. PMCA and SERCA use numeric-mM
hydrolysis factors `ADP*Pi/ATP` without that conversion. Sharing the same
literal standard energy across all three therefore leaves a chemical-drive
offset of **RT ln(1000) J/mol**. For a declared shared 1 M pool, the explicit
calcium legacy projection is

```
deltaG0_legacy(T) = deltaG0_1M - R*T*ln(1000).
```

This is a standard-state conversion, not thermal kinetics. The probe keeps the
literal native shared-energy case and a separately labelled projected case,
using the original 1 M energy for Na/K. No native global setter supplies this
projection automatically. PMCA/SERCA voltage signs and first/second calcium
argument conventions are retained independently.

Na/K and PMCA accept `met` but read fixed `p.cATP/cADP/cPi`; the tested paths
ignore the optional argument. PMCA also accepts `block` but does not use it,
whereas Na/K scales by it. These are native correspondence limits, not proposed
Cells behavior. Native PMCA clips negative calcium via `no_negs` and floors a
zero denominator; the diagnostic preserves that mutation without admitting
negative physical inputs to Cells. Native gate 0/0 singularities and GHK's
in-place `1e-25` voltage/valence nonce are preserved without source repair or
finite comparison credit at singular voltages. GHK's formula has flux-density
units mol/(m² s), despite a mol/s return label in its docstring.

## Separately versioned proposal, not adoption

Proposed future policy identifier:
**`active_uniform_isothermal_fixed_empirical_kinetics@1`**.
It must be attached to new model versions or an explicit new composition
contract. Existing fixed-298.15 K model IDs and their references remain valid
and guarded. The proposal defines a reproducible computational isothermal
family; it does not establish biological temperature response.

1. Use one positive prescribed Kelvin temperature for all actual ionic,
   environment, membrane, junction, reservoir, ER and finite-pool owners.
   Recompute every electrochemical field/RHS term with that T and a coherent SI
   constant set. Applying current T to gap-junction electroflux intentionally
   differs from native configured/runtime split semantics. Preserve that split
   as a separately named compatibility reference, not a claim of coupled parity.
2. Hold source empirical channel/junction voltage and calcium curves, time units,
   Phi, pump capacities/Km, diffusion/permeability, geometry, capacitance and
   valence fixed as declared parameters. Gates continue to evolve from actual
   changed voltage/calcium; only direct unprovided thermal scaling is absent.
   Preserve the live T in legacy calcium-K opening. Do not activate commented
   Q10, add Arrhenius coefficients or reinterpret mixed Texpt metadata.
3. Explicitly choose fixed reference **standard Gibbs coefficients in J/mol**,
   using `mu0_ref = R*T_ref*standard_mu_RT_ref` at `T_ref=298.15 K` for ER species.
   For this policy, `standard_mu_RT(T) = (T_ref/T)*standard_mu_RT_ref`; recompute
   reaction `delta_mu_RT` from stoichiometry. Hold declared forward rate
   coefficients fixed and derive backward rates from the changed dimensionless
   equilibrium. This matches the native fixed-delta_Go numerical convention
   at a reaction level. It is an operational convention: enthalpies, entropies,
   heat capacities and activation energies are absent, so their experimentally
   correct dependence is not inferred from this algebra.
4. Hold the pool's declared 1 M `deltaG0_J_mol` fixed and reevaluate all finite
   pool chemical potentials, regeneration affinities and pump drives at T.
   Apply the explicit `-RT ln(1000)` projection to PMCA/SERCA, including shared
   ER routes, rather than preserving a 298.15 K converted cache. Pool amounts,
   charge and owner associations remain physical state variables.
5. Qualify a new held active readout first. Require independent complete field,
   gate, reaction, ER, pool and open-reservoir derivatives across supported
   compositions, conservation, detailed balance, dissipation, owner ordering,
   stage-energy checks and all existing tolerances. Reconcile every cached
   drive/store temperature and source contract before any admission change.
   Isolated native results are evidence for these choices, not these missing
   coupled checks. Accepted stepping requires its own explicit authorization
   and completed numerical evidence.

Changing a setpoint is not a thermal transition. Existing accepted histories,
electrostatic anchors, chemical references and cumulative energy ledgers must
not be resealed under another T. Heat, thermal internal energy, entropy exchange
during a jump, heat capacity and thermal transport remain undefined here.

## Reproduction and review

Run the new source probe runner with an unused output directory, the pinned
BETSE checkout and the established CPU-only environment. It snapshots inputs,
references, native source and this proposal; reuses the existing bounded
subprocess guard; records runtime files, affinity, versions and raw failures;
and runs one fresh import-denied saved-data replay. Per-phase cap is 480 s,
process-tree RSS 1 GiB and host reserve at least 8 GiB on CPU4, one thread.
No follow-up coupled regression or unrelated job poll is scheduled.
