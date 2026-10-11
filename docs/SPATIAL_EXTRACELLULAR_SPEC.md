# Minimal spatial extracellular transport and electrical closure

2026-09-11, D059 / SPEC-009. Design and independent **instantaneous** arithmetic
reference; not a production model, spatial trajectory qualification or mesh
convergence result. Cells remains 0.14.0. This extends the ownership reasoning of
[SPEC-008](FINITE_EXTRACELLULAR_SPEC.md), without changing its frozen equations,
references, accepted finite-outside family or maintained-bath families.

## Decision and smallest useful example

Choose a bulk-electroneutral electrodiffusive compartment graph with explicit
membrane capacitance. Concentrations and extracellular potentials are coupled;
potential is an algebraic constraint, not an independently integrated variable.
Keep Python/JAX as the eventual implementation path, with an independently
qualified field-solver interface rather than requiring every solve to be a local
array kernel.

```text
cell interior -- capacitive, ion-permeable membrane -- near outside
                                                        |
                                              electrodiffusive face
                                                        |
                                                finite bulk outside
                                                (no membrane)
```

This is one cell and two finite outside volumes, not an organ-specific solver.
Compartment count, geometry and connections are data. A second cell or a longer
outside chain must not require a different ownership rule. A membrane-free bulk
compartment is essential: spatial refinement must not add fictitious capacitors.

| Closure option | Appropriate use | Decision now |
| --- | --- | --- |
| Every outside potential fixed independently | Explicitly maintained reservoirs/electrodes with accounted exchanges | Not a closed spatial environment; retain old bath models separately |
| Diffusion only, no electric drift | Named approximation or neutral solutes | Useful negative control, not the ionic spatial closure |
| Bulk electroneutrality plus membrane charge/current continuity | Coarse ionic environments without resolving bulk charge relaxation | Selected reference direction |
| Poisson–Nernst–Planck | Questions needing resolved bulk space charge and boundary layers | Separate future fidelity, not the first organ-scale default |

Solbrå et al. distinguish diffusion, drift and the electroneutral approximation
to rapid bulk charge relaxation. Their formulation retains membrane charge and
does not treat capacitive current as a second species source. This motivates the
choice, not a claim that our discretization reproduces their implementation.
[Primary paper, 2018](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006510).
Compartmental charge-capacitor relations and a single reference potential also
appear in [Sætra and Mori, 2024](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012114).

## First reference scope and independent owners

- Fixed positive compartment volumes, membrane capacitances and temperature;
  ideal dilute species with explicit integer valence and immobile background charge.
- One membrane per intracellular compartment, facing one named outside compartment.
  Several cells may face the same outside. Outside compartments may have no membrane.
- A connected, static extracellular face graph, or one outside with no faces.
  Faces have positive area/length and nonnegative effective species diffusivities;
  at least one charged species conducts on every face. Closed outer boundaries.
- Passive membrane GHK transfer is reused from the independent multispecies
  reference for the coupled witness. Bulk transport and potential closure are new,
  independently coded arithmetic, with no production dynamics/observer import.
- Every compartment owns its inventory. Membranes and bulk faces each own one
  oriented species-transfer vector. Their ledgers are histories, not extra matter.

This reference isolates the new electrical/environment interface; it does not
remove pumps, gates or junctions from existing production families. Reusing those
mechanisms in a spatial production family needs a separately frozen coupled
panel. In particular, gap junctions between cells facing different outside
regions create return-current constraints and potentially a nonlinear field
solve. They are **not implemented by this first passive reference**. Multiple
membrane patches per cell, intracellular spatial transport, electrodes, baths,
barrier switching, disconnected conducting domains, changing geometry, osmosis,
fluid flow and reactions also require explicit extensions.

## Units, anchors and charge constraints

Amounts `n[k,s]` are fmol, volume is pL, so `c = n / volume` is mM, numerically
equal to mol/m³. Let `a = 1e-15 mol/fmol`, with SI Faraday constant `F` and gas
constant `R`. Potentials are V; capacitances F; currents A; power W.

Immutable initial inventories, initial membrane voltages, fixed charge `X[k]`
in charge-equivalent fmol, and geometry define a consistent initial state.
Store/evolve **every** amount increment `dn[k,s]` explicitly; do not recover one
outside inventory as the remainder of the world total. At initialization verify

```text
q_ionic,0[k] = a F (X[k] + sum_s z[s] n0[k,s])
q0 = Bm diag(C) Vm,0
q_ionic,0 = q0
```

`Bm` has +1 at the inside and −1 at the outside of each membrane. Subsequently
use `q = q0 + a F sum_s z[s] dn[:,s]`, preserving the anchored-coordinate advantage
from NUM-009 v2. Fixed backgrounds and voltage anchors are declared data; neither
the loader nor a field solve may silently repair them. Initial-charge and
subsequent constraint discrepancies are errors, not assigned to a counterion.

Define the membrane-capacitance graph Laplacian `Lc = Bm diag(C) Bmᵀ`. The closure
requires `q = Lc phi`. Its nullspace matters. If `P` contains indicator columns
for the connected components of the **capacitance graph**, including isolated
bulk nodes, compatibility is `Pᵀ q = 0`, not merely zero total world charge.
Individual membrane-facing volumes need not have zero net charge: they include
the small membrane-associated charge. A membrane-free bulk node does have zero
net charge under this approximation. Do not impose electroneutrality on each
membrane-facing inventory and thereby erase its capacitor charge.

A solve of `Lc phi = q` alone leaves a different undetermined offset for every
capacitance component. Write `phi = phi_hat + P lambda`, where `phi_hat` solves
each component with a temporary local gauge. Only the final common reference
potential is an arbitrary physical gauge; the relative offsets `lambda` must
come from **current continuity**, not independently grounded outside nodes.

## Owned bulk-face law and field solve

For an oriented extracellular face `u -> v`, define `k[s] = D_eff[s] area / length`
in m³/s. Area is the actual conducting cross-section and volumes are actual
accessible solution volumes. `D_eff` already contains any declared hindrance;
do not multiply porosity/tortuosity twice. This first two-point rule is for
one-dimensional/orthogonal connections with scalar diffusivity, not a validated
arbitrary nonorthogonal 3-D mesh discretization.

The proposed log-mean mobility law is our discrete design:

```text
L(cu,cv) = (cu - cv) / (ln(cu) - ln(cv)),       L(c,c) = c
mu_uv[s] = RT ln(cu[s]/cv[s]) + z[s] F (phi[u]-phi[v])
J[s] = (k[s] L(cu[s],cv[s]) / a) * mu_uv[s] / RT   [fmol/s, u -> v]
I = a F sum_s z[s] J[s] = I_diff + G (phi[u]-phi[v])
G = F²/RT * sum_s z[s]² k[s] L(cu[s],cv[s])        [S]
```

Evaluate the equal/near-equal concentration limit stably, with no concentration
floor or clipping. This law is exactly Fickian when the potential drop is zero,
vanishes at electrochemical equilibrium, and has nonnegative instantaneous
dissipation `a sum_s J[s] mu_uv[s]`. These are algebraic properties, **not** proof
of positivity or energy decay for a time integrator. Spatial accuracy and the
behavior at large gradients must be separately assessed; Scharfetter–Gummel or
other fluxes can be separately versioned alternatives, not silent replacements.

Let `Bf` have +1 at a face's source and −1 at its destination. Bulk amount rate is
`-Bf J`. The closed passive subset obeys

```text
Pᵀ qdot = 0
Pᵀ Bf [I_diff + diag(G) Bfᵀ (phi_hat + P lambda)] = 0
```

This is a reduced, gauge-fixed positive graph-Laplacian solve for component
offsets at a given admissible concentration state. Check charge compatibility,
matrix rank/connectivity and the **physical current residual**, not just a
solver success flag. Never add epsilon grounding to conceal a singular model.
Future cross-component transport contributes to this equation with its true
potential dependence; it cannot be omitted merely to keep the solve linear.

For the first one-membrane-per-cell subset, each capacitance component consists
of one outside and its attached cells, or one membrane-free outside. Membrane
ionic transfers cancel within that component. Bulk current is divergence-free
at its component nodes. A one-face example therefore has zero **net electrical
current**, not zero species flux. On a graph with cycles, node balance does not
require every individual face current to vanish.

## Membrane coupling, accounting and observations

Compute membrane voltage as `phi[inside] - phi[outside]`. Convert the existing
reference's inward GHK convention explicitly to the common outward orientation.
Scatter each membrane flux to inside and outside exactly once with opposite
signs; do likewise for each bulk face. Never add a capacitive species flux on
top of those transfers. The capacitor is charge accounting, not a second ion path.

For this closed passive subset, each species' total amount is conserved. The
stored energy is the ideal chemical energy of **all** finite compartments plus
`sum_m C[m] Vm[m]² / 2`, counting each membrane capacitor once. There is no
additional invented bulk capacitor energy. At a fixed-volume, isothermal state:

```text
dE/dt = a RT sum_(k,s) ln(c[k,s]/1 mM) ndot[k,s] + phiᵀ qdot
      = - sum_owned_interfaces a sum_s J[s] mu_drop[s] <= 0
```

Future driven pumps add their declared supply work; reservoirs/electrodes/flow
require explicit material, charge and power ports. Thermodynamic consistency is
an architectural requirement, informed by the energy-structured modeling in
[Mori, Liu and Eisenberg, 2011](https://arxiv.org/abs/1101.5193), not a claim that
our passive graph implements that paper's moving-membrane/water-flow model.

## Analytic witness and bounded design checks

With a binary monovalent salt, each outside initially has equal cation/anion
concentration, `cu` and `cv`. For one face with diffusivities `D+` and `D-`, the
zero-current solution and common salt flux are

```text
F (phi[u]-phi[v]) / RT = -(D+ - D-) / (D+ + D-) * ln(cu/cv)
J+ = J- = area / (a length) * 2 D+ D- / (D+ + D-) * (cu - cv)
```

Equal diffusivities imply no diffusion potential. Unequal diffusivities and a
gradient imply a nonzero potential; forcing both outside potentials to zero
produces spurious charge accumulation. A separate pure-bulk reduction verifies
that neither a cell nor a fictitious capacitor is needed to define this solve.

The [frozen arithmetic panel](../configs/reference/spatial_extracellular_v1.json)
uses synthetic inputs, not measured biology. Its reference checks include
single-outside reduction, unequal/equal diffusion, uniform outside, a ternary
loop, two cells, a divalent salt and pure bulk transport. Unit tests add gauge,
label/species/orientation changes, finite increments, owner conservation,
power identity, near-equal mobility and invalid-state/geometry/charge refusal.
The [design report](../reports/SPEC009_DESIGN_CHECK.md) records executed evidence
separately from this prospective contract.

The arithmetic panel fixes `rtol=2e-12`, voltage `1e-10 V`, charge `1e-20 C`,
current `1e-23 A`, flux `1e-12 fmol/s` and power `1e-23 W` absolute allowances.
These are small-reference comparison limits, **not** selected production field
solver tolerances or trajectory error budgets. No timestep is inherited from
the old 1 ms RK4 qualification. No interpolation of independently stored outside
potentials is qualified here.

## Multiscale/GPU boundary and next gates

Separate compartment, membrane, species and bulk-face axes and their IDs. Keep
one owner per face, shared conservative scatter, and immutable physical anchors.
A biological cell is not a field mesh point, and an organ is not a GPU partition.
Independent worlds may be batched; different regions of this coupled outside
graph may not be treated as independent worlds.

Future production should expose a field block with stage-state inputs, gauge/
boundary identity, physical residuals and explicit scratch/cache ownership.
Potential is reconstructed from complete state; warm starts must not become
unrecorded physics. Every actual stage and reconstructed observation must satisfy
the selected closure. Fine/coarse transfer must preserve amounts, interface
charge/energy and declared capacitance, not just average voltages. Dynamic
coarsening is not supplied by this graph.

Single-world GPU partitioning needs halo concentrations/potentials, single-owned
boundary transfers and a coupled sparse solve/reductions. Small dense NumPy
reference matrices are not the proposed production storage. Preconditioner,
precision, tolerance and synchronization costs must be qualified. Benedusi et al.
report a KNP-EMI method using IMEX, mixed finite elements and AMG-preconditioned
GMRES. The reviewed abstract reports CPU-core scaling, **not a Cells or GPU
benchmark**; its lesson is to reserve a genuine solver-block interface.
[Primary paper, 2024](https://epubs.siam.org/doi/10.1137/24M1644717).

Next: NUM-010, a separately frozen short CPU spatial-trajectory protocol. It must
select reference methods for the differential/algebraic coupling; test salt
relaxation, membrane feedback, positivity, charge/current/energy, temporal and
spatial refinement, and exact blocking under the chosen topology policy. Define
dense-output/restart state and residual tolerances before running it. Only after
qualification should CORE-010 assemble a separately versioned CPU/JAX family
through the existing engine. GPU execution, coupled-junction spatial panels,
multiple membrane patches, arbitrary meshes, tissue barriers, biological
validation and organ presets remain separate gates.
