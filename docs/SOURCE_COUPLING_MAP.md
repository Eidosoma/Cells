# Source correspondence: what a contact actually means

R005 / D021, reviewed 2026-09-08. This is the first completed correspondence
slice of CONTACT-003, not coupled source-assay acceptance. The proposed
[physical pair](SELECTIVE_CONTACT_SPEC.md) and a future source-compatible model
share engine responsibilities but have different equations and fidelity labels.

Later boundary update (SPEC-004/R006): [E02-SW1](E02_SWITCHING_PROTOCOL.md)
selects an ungated three-cell switching experiment with fresh, fully disconnected
500-unit preparation and exact endpoints. The historical neighbour helper turns
off miRNA rather than all ionic exchange, reuses ionic context between directions,
and selects plotting samples. These differences preclude calling E02-SW1 an exact
historical threshold reproduction. The current nominal pair's short acceptance
does not yet cover this topology, preparation or horizon.

NUM-005a now checks a separate [independent graph reference](SOURCE_EMT_GRAPH_REFERENCE.md)
against 45 full native instantaneous inputs, including mixed per-edge gates,
route controls and zero-edge/disconnected cases. This is source-equation and
composition evidence only; it supplies neither prepared states nor long-time
switching or production-graph acceptance.

NUM-005b subsequently qualifies [fresh isolated preparation](SOURCE_PREPARATION_REFERENCE.md)
with six independent implicit trajectories and complete exact-endpoint packets.
This is independent source-equation evidence, not a long native/helper recapture;
the preparation/sampling differences above remain explicit. Connected switching,
production graph support and a long-time RK4 candidate remain unqualified.
NUM-005c1 now registers the [long implicit reference panel](SOURCE_GRAPH_PATHS_REFERENCE.md)
from those exact packets, with all controls and no native long driver. Its
numerical and readout evidence is separate from the continuing exploration,
historical source-threshold claims, and subsequent production acceptance.
The [continuation evidence](../reports/NUM005C1_CONTINUATION.md) now contains ten
qualified conditions and a retained reverse miRNA-only reference disagreement.
All new dense paths pass independent domain/accounting auditing, but that does
not qualify the failed trio or establish a biological switching result for it.
The separately registered [A1 tighter-BDF diagnostic](../reports/NUM005C1_A1_BDF_REFINEMENT.md)
meets the unchanged reference threshold with the same source equations. This is
numerical-refinement evidence, not a new native or biological confirmation;
the original failed trio and qualification status remain preserved.

The explicit [A2 decision](../reports/NUM005C1_A2_REFERENCE_PANEL.md) now accepts
that refined reference, records its observers and completes the three remaining
controls. All 14 amended-policy reference cases pass independent auditing.
This is a mixed-setting, accuracy-qualified source-equation panel, not a change
to native evidence or the original failed campaign. The long-time production
candidate, production graph/assay implementation and biological validation remain
unqualified; no native long driver or continuing exploration experiment was run.

[D037 bounded candidate engineering](../reports/NUM005C2A_CANDIDATE_ENGINEERING.md)
now passes twelve short RK4 prefixes against those exact reference inputs, with
independent recorded-path auditing and exact recording-width identity. This is
numerical/engineering evidence for a bounded candidate, not long-time method
selection, a new source mechanism or a production graph implementation.

D038's [cached batched readouts](E02_DIAGNOSTIC_OPTIMIZATION.md) optimize the
observation axis only, with differential checks against the unchanged scalar
source-equation evaluator. The underlying reference inputs, native witnesses,
integration policy and scientific thresholds do not change. Computational
agreement is not additional experimental validation of the source model.

D039's [lossless evidence codec](E02_LOSSLESS_EVIDENCE.md) reconstructs recorded
RK4 state/curve arrays, retaining complete checkpoints and all reference
comparison samples. It changes storage/publication mechanics, not source laws,
native witnesses or biological acceptance. Its short-only qualification remains
separate from selecting a long-time candidate or implementing production graphs.

D040's [reference-backed comparison representation](E02_COMPARISON_RECORDING.md)
retains the same logical numerical evidence through exact reconstruction. Pinned
storage dependencies do not provide new native witnesses, change source laws
or establish biological or long-time candidate acceptance.

D041's [immutable scalar evaluation](E02_INTEGRATION_EVALUATION.md) caches only
fixed source-equation factors and keeps all numerical checks. Its complete
derivatives and short recorded stage slopes are bitwise checked against the
frozen graph evaluator. This adds an implementation-equivalence check, not new
native evidence, a new source law or production/biological acceptance.

## Evidence and boundaries

The clean local [BITSEY checkout](../upstream/bitsey/README.md) is pinned to
`b2cb370aaecbc8299f259bc4251d5396c81f19a6`. Reviewed executable paths include
`sim.py`, `sim_toolbox.py`, `GJ_lib.py`, `cancer_GJ_sims/GRN_miRNA.py`, and
`cancer_GJ_sims/zombie.py`. File hashes and native numerical outputs are retained
in the [contact fixture](../tests/fixtures/contact_source_probes.json).

[Native capture](../scripts/capture_contact_reference.py) called instantaneous
functions in a fresh, 60-second-bounded process using the separate reference
environment. It imported neither `zombie.py` nor the continuing experiment
harness, invoked no integrator, changed no source file, and checked checkout
identity before and after. [Independent checks](../scripts/check_selective_contact_contract.py)
verify source formulas separately from our physical design. There is no copied
upstream implementation in Cells. No license-named path was found in the pinned
tree; this is not permission to redistribute its implementation.

## Correspondence table

| Boundary | Pinned source behaviour | Cells consequence |
| --- | --- | --- |
| Junction voltage | Executable `sim_slopes` uses `V_from - V_to`; a `GJ_lib` header describes the opposite sign | Follow executable orientation and test it, particularly for asymmetric heterotypic gates |
| Junction transport | Fick diffusion plus upwind electrical drift using the donor selected by drift direction | Preserve as an identified source approximation; do not rename our Bernoulli/constant-field flux as equivalent |
| Junction gate | Algebraic opposing-gate factor at the current voltage; time argument unused | No evolving gate or relaxation time in a corresponding model; physical gate memory is an explicit new model |
| Gate amplitude | Species-specific minimum plus open fraction times amplitude range; normalized conductance can exceed one | Keep probability, amplitude, residual selectivity and external inhibition distinct; do not clip amplitude to `[0,1]` |
| miRNA transport | Simple free proxy equals primary total; transported proxy flux updates the total row once | Recompute derived coordinates at each stage; never create a second miRNA inventory or duplicate flux |
| miRNA charge | Current executable effective drift valence is -1; global charge-closure valence remains zero | Identify this as a legacy tracer approximation, not a charge-conserving physical RNA species |
| Membrane leaks | Constant-field/GHK with permeability `D_mem/tm`, rounded source constants and a zero-voltage regularization | Related physical law, but exact comparison must preserve constants, geometry and numerical convention |
| Pump | Source ATP/ADP/Pi, saturation and reversal law; additionally disabled if all cell membrane diffusion coefficients are zero | Cells' synthetic affinity-limited pump is different; independent leak/pump controls are deliberate engineering semantics |
| Electrical closure | Absolute concentration-charge sum includes immobile P; shared spherical geometry and specific capacitance | A physical affine anchor can represent corresponding fixed charge, but the current synthetic fixture is not the source initial state |
| Regulatory clock | Source-scaled coordinates and unresolved hour/second annotations | Preserve literal nominal source time for compatibility; do not silently mix with physical seconds/fmol |
| Regulatory feedback | Active tumour/K-channel scaling functions are immediate functions of current concentrations | Triple-quoted `slow_tumorness` and old `ST` code are inactive, not evidence of a hidden dynamic gate |

## Native gate and transport equations

Writing the executable edge voltage as `d = V_from - V_to`, the source computes
an on fraction and then a per-species normalized conductance factor:

```text
o(d) = 1 / [1 + exp(A1*(-d - V01)) + exp(A2*(d - V02))]
scale_s = Gmin_s + (Gmax_s - Gmin_s)*o(d)
```

`set_ion_fully_blocked` sets both amplitudes to zero.
`set_ion_blocked_when_closed` removes the residual while preserving the maximum,
giving `Gmax_s*o(d)`. The native probes cover 45/45, 40/37 and 43/45 at -80,
-40, 0, +40 and +80 mV. They verify time independence and both selectivity
operations. For example, the 40/37 scale at zero voltage is 1.0138070588692694;
a unit-interval clamp would change the source. The 45/45 parameter `Gmax=1.56`
is an amplitude, not an opening probability.

The associated primary paper describes steady voltage gating and normalized
conductance, not the synthetic relaxation kinetics proposed for our physical
pair. Its distinction between initial and steady conductance explains why
normalized amplitude need not be bounded by one.
[Chen-Izu et al. (2001)](https://cardiacsignalinglab.bme.ucdavis.edu/files/2016/01/2001_AJP_GapJunction.pdf).

For source diffusion `D_s`, path length `L`, and
`x_s = z_s*q*d/(kb*T)`, the ungated source junction flux is:

```text
j_s = (D_s/L) * [c_from_s - c_to_s + x_s*c_upwind_s]    # mol/(m² s)
c_upwind_s = c_from_s if x_s >= 0, otherwise c_to_s
```

At zero drift the choice of donor is immaterial. Native probes check positive,
negative and neutral valences; both voltage polarities; blocked species; and
reversed edge endpoints. A full `sim_slopes` probe with no membrane exchange
also checks the executable voltage sign and final conservative scatter.

The two transport laws differ even at moderate dimensionless voltage. With
`c_from=1`, `c_to=2`, positive valence, and normalization by `D/L`:

| Dimensionless voltage | Native upwind flux | Constant-field flux |
| --- | --- | --- |
| `x=log(2)` | -0.3068528194400547 | 0 |
| `x=0.8` | -0.2 | 0.14722702326712467 |

At the first point the exact ideal-solution electrochemical potentials are equal.
At the second, the native approximation has a positive flux-times-exact-potential
product while the constant-field law is downhill. These bounded counterexamples
identify an approximation difference; they are not a judgement that all upstream
experiments are invalid. A source-compatible comparison must keep that difference
visible, not tune parameters to conceal it or apply the physical law's invariants
to a different source discretization.

## Geometry, quantities, and clocks

Source ionic concentrations are numerically mol/m³. Its shared geometry is
radius 5e-6 m, area `4*pi*r²`, volume `4*pi*r³/3`, specific capacitance
0.05 F/m², junction length 1e-7 m, temperature 310 K. All surface fluxes,
including junction fluxes, are normalized to the **whole cell membrane area**;
the effective diffusion coefficients include channel-area scaling.

For ionic quantities, conversion to amounts is `n_fmol = c * V_m3 / 1e-15`.
The source concentration derivative from a junction is `±j*A_cell/V_cell`.
With our explicit junction area, matching the transport prefactor would require
`A_junction*P_s = A_cell*D_s/L`. That identity alone neither makes the different
flux laws equal nor identifies a physical junction plaque area. Do not multiply
by an additional area fraction after adopting an already effective coefficient.
Unequal-volume tests belong to our physical model; the pinned source uses shared
geometry and is not an independent unequal-volume reference.

The source uses separately rounded `F=96485`, `R=8.314`, `q=1.602e-19`,
`kb=1.3806e-23`. Consequently `q/kb` and `F/R` are not exactly the same ratio.
Native drift probes use the former; source charge and GHK calculations use the
latter where specified. Our physical model uses consistent SI constants.

[EMT's isolated contract](EMT_REFERENCE.md) retains the regulatory scale factors
and binding approximation. There is no established conversion from those
regulatory coordinates to physical fmol/concentration, or from their nominal
clock to calibrated seconds. A future **source-compatible** coupled model may
retain the entire original nominal clock and explicitly typed regulatory
coordinates to reproduce source arithmetic. This does not require inventing a
physical conversion. Conversely, attaching EMT to the physical pair does require
a separate molecular/clock/charge/energy mapping and calibration decision.

## miRNA trace and assay-specific switches

In the pinned `EMT_GJ_gate`, the free proxy temporarily gets drift valence -1
and the configured diffusion coefficient. Its flux is returned to the primary
total-miRNA row, then temporary valence and diffusion are restored to zero. Native
probes verify that changing total/free miRNA does not alter `compute_Vm`, that
the transport call leaves primary/derived concentrations unchanged, and that
the temporary parameters are reset. Some surrounding comments still say -20;
the executable default is -1. No override was applied during capture.

When a voltage gate is enabled, the medium-sized miRNA setting gives the primary
route zero residual permeability. The proxy itself, mRNA, proteins and bound
complexes are blocked by the scale gate. This is source model semantics, not a
claim that these molecular permeability choices have been biologically calibrated.

Do not assume all continuing exploration assays enable these gates:

- The reviewed [memory-probe harness](../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/scripts/run_memory_probe.py)
  builds with default gate switches off and explicitly refuses unexpected
  intracellular or junction-scale gates. Active phases retain ionic exchange
  and configured miRNA drift/diffusion; blocked phases remove transport.
- The reviewed [pilot harness](../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/scripts/run_pilot.py)
  adds K-channel expression and junction voltage gates for `voltage`/`both`
  cancer-isolation strategies. Its ungated and expression-isolation strategies
  have different declared mechanisms.

The full protocol configuration, not the phrase “Levin tests,” defines a reference
case. Later H3/H4 route adapters require their own pinning and review before a
Cells reproduction; this review does not certify every subsequent harness.

## Remaining acceptance gate

CONTACT-003's broader E02 switching gate remains in progress. The original 106
source checks cover instantaneous equations and roles, not full source
trajectories, threshold tables, relay, PH, or wet-lab agreement. The staged
acceptance sequence is:

1. Specify one complete model identity (SPEC-003 design now complete) with explicit
   nominal units, source electrical state, pump/leak/gating switches and regulatory refresh semantics.
   Preserve algebraic gating; do not introduce extra memory to match endpoints.
2. Pin complete prepared source states and bounded positive/negative two-cell
   cases (SPEC-003 inputs now frozen). Compare full trajectories, fluxes, derived
   voltages and endpoint rules
   under independently refined numerical settings, not labels alone.
3. Implement on reusable stage, state, coupling, schedule, checkpoint and observer
   boundaries. Source quirks belong in the named model contract, not generic
   runner branches or physical-model defaults.
4. Only then add selected memory/relay protocols, reporting source reproduction,
   engineering validity and biological validation as separate evidence levels.

The build sequence SPEC-002 -> NUM-003 independent physical pair -> MODEL-004
physical JAX pair is now complete; see the [production guide](BIOELECTRIC_PAIR.md).
SPEC-003/D024 now completes item 1 and freezes the inputs for item 2:
the [complete source-compatible contract](SOURCE_EMT_PAIR_SPEC.md) separates six
evolving coordinates from P/Snail/ST context and plotting caches, retains the
source pump eligibility rule, and pins complete earlier prepared E/M packets.
3192 instantaneous checks cover the full coupled RHS under 17 control settings
from 14 cases, including asymmetric orientation and stale-cache refresh.
See [design evidence](../reports/SPEC003_DESIGN_CHECK.md). These are additional
source equation checks, not native trajectories or production acceptance.
NUM-004 now completes the bounded coupled reference gate in item 2: all 14
independent paths pass, and native comparisons qualify with the recorded S12
event-clock refinement. See the [numerical contract](SOURCE_EMT_PAIR_NUMERICS.md)
and [evidence](../reports/NUM004_REFERENCE.md); native requested and realized
clocks must remain distinct. MODEL-005 now implements that bounded nominal
profile with [production/reference, replay and regression acceptance](../reports/MODEL005_ACCEPTANCE.md);
selected longer E02 switching and memory/relay protocols remain unexecuted.
The cancer expression/neighbor strategies are not included in this first profile.
The physical panel and its JAX acceptance alone do not establish those source gates.
