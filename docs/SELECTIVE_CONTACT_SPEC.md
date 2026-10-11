# Stateful selective contact: first physical pair

SPEC-002 / D021, 2026-09-08. Accepted design with verified instantaneous
equations; subsequent [NUM-003](SELECTIVE_CONTACT_NUMERICS.md) now qualifies
independent trajectories and a bounded numerical candidate. **Production is now
implemented in Cells 0.6.0**; see the [run guide](BIOELECTRIC_PAIR.md) and
[MODEL-004 acceptance](../reports/MODEL004_ACCEPTANCE.md).
[Design evidence](../reports/SPEC002_DESIGN_CHECK.md) and the separate
[source-correspondence map](SOURCE_COUPLING_MAP.md) define what has been checked.

The physical model is `bioelectric_pair@1`: two copies of the
[one-cell physical model](BIOELECTRIC_CELL_SPEC.md), coupled through one
species-selective, voltage-sensitive junction. Start with one evolving junction
gate, not a simultaneous expansion into channel gating, regulatory feedback,
finite extracellular volumes, or tissue geometry. Those are separate mechanisms.

## State, geometry, and ownership

Two fixed-volume well-mixed cells each have one effective bath-facing membrane.
Both membranes face one maintained, electroneutral Na/K/Cl bath at potential
zero. One fixed edge connects the cells. The edge is a transport path with no
independent material inventory or additional capacitive element in this model.

| Entity | Primary evolving arrays | Immutable layout/data |
| --- | --- | --- |
| Cell | Ion amount `n[species, cell]`, fmol | Stable identity, active mask, volume pL, amount/voltage anchors |
| Membrane | Inward leak ledger `L[species, membrane]`, fmol; signed pump-cycle ledger `P[membrane]`, fmol cycles | Identity/mask, owner cell, facing bath, area m², specific capacitance F/m², leak permeabilities m/s, pump capacity fmol cycles/s |
| Junction | Gate `g[edge]`, dimensionless; signed transfer ledger `T[species, edge]`, fmol from source to destination | Identity/mask, distinct endpoint slots, effective area m², species permeabilities m/s, closed-state residual fractions, gate parameters |
| Bath | None: explicitly maintained support | Identity, concentrations mM, potential 0 V, temperature K, ATP cycle free energy J/mol |

Species are Na, K, Cl with valences `z = (1, 1, -1)` and pump stoichiometry
`nu = (-3, 2, 0)`. Retain separate species/cell/membrane/edge axes, even in this
tiny fixture. The declared active counts are exactly two cells, two membranes,
one edge, and one bath; additional capacity slots are inactive, not extra cells.
Each membrane has one owner, and each active cell has one membrane for version 1.
No self-edge or live endpoint into inactive capacity is valid.

Amounts are the only material inventory. All three signed ledgers are history,
not additional material or inputs to the flux laws. Gate state is a real primary
degree of freedom; identical amounts/voltages need not imply identical future
responses. Initial `g` must be supplied explicitly. Do not reset it to a target
at initialization, contact release, checkpoint loading, or branching.

## Electrical closure and approximation

Use SI constants from the one-cell contract, `a = 1e-15 mol/fmol`, and
`q_f = F*a`. For each cell, `C_i = area_i * specific_capacitance_i`:

```text
Qfixed_i = C_i Vref_i - q_f sum_s(z_s nref_si)
V_i = Vref_i + (q_f / C_i) sum_s[z_s (n_si - nref_si)]
deltaV_AB = V_A - V_B
```

`Qfixed_i` is immobile background charge, fixed by the initial anchors; require
the nonpositive fixed-charge domain already used by the physical cell. Voltage
is derived, not a second integrated copy of charge. Different initial reference
voltages are permitted with the corresponding declared background charges.

This is a **diagonal capacitance approximation to a common reference bath**.
The effective membrane capacitances remain fixed when junction permeability or
blocking changes. The junction area parameter controls transport only; it does
not automatically remove bath-facing membrane area or add capacitance. Mutual
cell-cell capacitance, junction charge storage, access resistance, resolved
extracellular potentials and fields are omitted. They require a separately
specified capacitance/network or field closure, not just more graph edges.

For isolated reciprocal exchange, `C_A*dV_A/dt + C_B*dV_B/dt = 0`.
The unweighted voltage sum is generally **not** conserved if capacitances differ.
Neither does conservation alone imply that endpoint voltages must become equal:
concentration gradients, selective routes and impermeant charges also matter.

## Gate, selectivity, and intervention are different things

The first gate is a synthetic symmetric relaxation law:

```text
g_inf(deltaV) = 1 / [1 + exp(a_g*(-deltaV - Vh)) + exp(a_g*(deltaV - Vh))]
dg/dt = (g_inf(deltaV) - g) / tau_g
```

Use a stable log-sum-exp evaluation. Require finite `a_g > 0` in V⁻¹,
`Vh >= 0` in V, `tau_g > 0` in s, and `0 <= g <= 1`. Boundary slopes point
inward. At fixed voltage the exact response is
`g(t) = g_inf + (g(0)-g_inf)*exp(-t/tau_g)`. That is a gate-only reference
calculation, not a claim that the pair supports ideal voltage-clamp protocols.

The opposing-gate literature describes steady voltage dependence and distinguishes
initial from steady conductance. It does not identify the relaxation time used
here. The extra differential equation and its parameters are our phenomenological
model, not a reproduction of the full microscopic gating scheme.
[Chen-Izu, Moreno & Spangler (2001)](https://cardiacsignalinglab.bme.ucdavis.edu/files/2016/01/2001_AJP_GapJunction.pdf).

For each species, define an open permeability `P_s >= 0` and a residual fraction
`0 <= r_s <= 1`. Effective permeability is
`P_s * [r_s + (1-r_s)*g]`. Thus `P_s=0` is fully impermeant, whereas `g=0`
can still permit a species with `r_s>0`. Neither permeability nor conductance
amplitude is itself a probability. This interface separates ionic and molecular
selectivity without claiming that our synthetic fractions fit a connexin.

Experiments on Cx43 found a residual state that still conducted ions while
excluding tested charged dyes. This supports separating transport selectivity
from a single binary connectivity flag; it does not establish miRNA passage or
provide parameters for this model.
[Bukauskas, Bukauskiene & Verselis (2002)](https://pubmed.ncbi.nlm.nih.gov/11815667/).

The independent scheduled contact control is `0 <= u_AB(t) <= 1`. It multiplies
transport but does **not** freeze or overwrite `g`. A blocked edge remains an
identified edge, and the gate continues responding to the cells' voltages.
Inactive padding, pharmacological inhibition, and physical edge deletion have
different meanings. Topology mutation is not supported by this first pair.

An algebraic gate or a fast-gate reduction is a different declared model choice.
Never interpret `tau_g=0` as a hidden switch to one. In particular, the pinned
BITSEY gate is algebraic, not this evolving state; see the correspondence map.

## Oriented conservative transport

For the single stored orientation A -> B, with concentrations `c = n / volume`
(fmol/pL equals mM and mol/m³ numerically), define:

```text
B(x) = x / (exp(x)-1), with B(0)=1
x_s = z_s F (V_A - V_B) / (R temperature)
J_s = (area_AB P_s / a) u_AB [r_s + (1-r_s)g]
      * [c_As B(-x_s) - c_Bs B(x_s)]           # fmol/s, A -> B
dT_s/dt = J_s
dn_As/dt += -J_s
dn_Bs/dt += +J_s
```

Evaluate and scatter each edge flux once. Reversing the storage orientation
reverses the voltage argument and ledger sign, not the physical prediction.
At zero voltage this reduces to Fick exchange. With neutral valence it has the
same diffusion limit; neutral species are an equation check, not an added
species in `bioelectric_pair@1`.

For ideal-solution electrochemical potential change
`delta_mu_s = RT log(c_Bs/c_As) + z_s F(V_B - V_A)`, require
`J_s*delta_mu_s <= 0`. Each permeant species has zero flux at its Nernst
condition. These are the new physical law's requirements, not assertions about
the source's upwind approximation. Passive flux need not follow concentration
alone when an electrical gradient is present.

Bath leaks and pumps use the unchanged one-cell equations. All mechanisms read
the same stage amounts, derived voltages and gate state. No operator may use an
old gate or voltage unless a later, separately qualified splitting method says so.

## Accounting, energy, and support

For an initial zero ledger, with `P_i` denoting signed pump cycles:

```text
n_A - nref_A = L_A + nu*P_A - T
n_B - nref_B = L_B + nu*P_B + T
sum_i C_i*(V_i - Vref_i) = q_f sum_s z_s sum_i(L_si + nu_s*P_i)
```

Internal transfers cancel separately for each species. When reporting a branch,
preserve original anchors and accumulated history rather than redefining them
at the checkpoint. Independent exchange/cycle controls remain independently
auditable even when their effects on net amounts cancel.

For fixed volumes and the common maintained bath, the resolved bath-relative
potential, up to constants, is
`Omega = a RT sum_si n_si[log(c_si/cbath_s)-1] + sum_i C_i V_i²/2`.
Its derivative equals supplied ATP power minus leak, pump-cycle and junction
dissipation, using the one-cell sign convention. Junction dissipation is
`-a sum_s J_s*delta_mu_s >= 0`.

Gate conformational energy, gating current, synthesis and turnover costs are
not represented. The balance is for resolved ionic/capacitive/pump variables,
not a claim of a complete thermodynamic model of channel proteins. The bath
and ATP drive remain unlimited external support, not autonomous metabolism.

## Synthetic fixture for independent qualification

The following values are engineering inputs, not biological estimates or a fit
to a successful source assay. Cell A uses the one-cell baseline. Cell B differs
only in its initial ionic concentrations and voltage. Both cells otherwise use
volume 1 pL, membrane area 1e-9 m², specific capacitance 0.01 F/m², Na/K/Cl
leak permeabilities `(1e-10, 1e-9, 1e-10)` m/s, and pump capacity 0.02 fmol/s.
Bath concentrations are `(145, 5, 150)` mM, temperature 298.15 K, ATP drive
-50000 J/mol cycles. Horizons below are in seconds, not nominal EMT source time.

| Parameter | Initial value |
| --- | --- |
| Cell A concentration / reference voltage | `(12, 140, 10)` mM / -0.065 V |
| Cell B concentration / reference voltage | `(18, 130, 15)` mM / -0.045 V |
| Junction effective area | 1e-11 m² |
| Junction Na/K/Cl open permeabilities | `(1e-8, 5e-9, 2e-9)` m/s |
| Junction Na/K/Cl residual fractions | `(0.1, 0.1, 0)` |
| Gate sensitivity / half-voltage / relaxation time | 100 V⁻¹ / 0.04 V / 0.2 s |
| Initial gate / contact control | 0.25 / 1 |

The initial gate target is 0.8788782427321509, slope 3.144391213660754 s⁻¹,
and signed transfer is approximately `(-5.84236e-4, -1.53707e-3, 2.24023e-5)`
fmol/s. These are checked instantaneous values, not simulated endpoints.

## NUM-003 gate: original qualification requirements

The following panel and targets were subsequently frozen and qualified by
[NUM-003](SELECTIVE_CONTACT_NUMERICS.md). The wording below preserves the design
requirements; the qualified candidate is RK4/1 ms with cubic observations, not
the old one-cell 5 ms bound. MODEL-004 production acceptance is a separate,
now-completed gate; its evidence is linked at the top of this document.

Implement an independent CPU pair reference without importing Cells' mechanisms.
Before fitting any implementation timestep, freeze this panel and accuracy
targets. Use independent stiff methods (Radau/BDF), tightening their tolerances
and comparing results before treating either as an oracle. Retain failed trials.
The starting panel below has 20 cases; all unspecified values use the fixture.

| Case | Deliberate variation and horizon |
| --- | --- |
| Q00 | Baseline, 10 s |
| Q01 | Contact blocked throughout, 10 s; recover two independently integrated physical cells |
| Q02 | All membrane leaks and pumps off, 10 s; closed two-cell material accounting |
| Q03 | All transport and pumps off, 1 s; fixed amounts/voltages and analytic gate relaxation |
| Q04 | Identical cells using A's initial condition, 10 s; zero junction flux by symmetry |
| Q05 | B volume 1.7 pL, membrane area 1.6e-9 m², same initial concentrations, 10 s |
| Q06 | Reverse stored endpoints and transfer-ledger orientation, 10 s |
| Q07 | Initial gate zero, 1 s |
| Q08 | Initial gate one, 1 s |
| Q09 | Gate relaxation 0.02 s, 1 s |
| Q10 | Gate relaxation 2 s, 10 s |
| Q11 | Multiply all junction permeabilities by 10, 1 s |
| Q12 | Multiply all junction permeabilities by 0.1, 10 s |
| Q13 | All residual fractions zero, 1 s |
| Q14 | K junction permeability zero, 10 s |
| Q15 | All residual fractions one, 1 s; gate evolves but no longer modulates transport |
| Q16 | Contact blocked on `[0, 0.123)`, then released, 1 s |
| Q17 | Contact blocked only on `[0.1234, 0.1241)`, 1 s; sub-5-ms event pair |
| Q18 | A leaks off at 0.117 s, B pump off at 0.211 s, contact blocked `[0.301, 0.437)`, 1 s |
| Q19 | Bath leaks off throughout, pumps retained, 1 s; independent controls and cycle accounting |

Freeze exact configurations in NUM-003 before reference runs. Configuration
changes during development must be recorded, not used to delete inconvenient
cases. No arbitrary-parameter guarantee follows from this bounded panel.

Proposed maximum absolute production/reference errors across accepted and
requested observation times: 1e-6 V, 1e-7 fmol for amounts and each ledger,
1e-7 for gate fraction, and 1e-6 pJ for integrated resolved energy/dissipation
diagnostics. Reference-method disagreements should be at most one tenth of
those limits. Independently test per-cell material residual <=1e-8 fmol and
charge-voltage residual <=1e-8 V. These are engineering targets to qualify,
not achieved pair results or claims of experimental measurement accuracy.

RK4 with the existing event union and interval-correct cubic observations is a
candidate, not a selected timestep. **Do not inherit MODEL-003's 5 ms bound.**
Measure refinement of the complete coupled state and observations, including
gate dynamics and all controls. If a faster case is stiff, first refine or
qualify a different method; do not loosen targets or rely on a larger GPU.

Require positive finite active amounts, finite ledgers and valid gate fractions
at every numerical stage and accepted endpoint; membrane and junction
dimensionless voltages must satisfy `abs(z F deltaV / RT) <= 50` in the candidate
domain. Inactive slots are safe to evaluate and remain exactly zero. No clipping
or hidden concentration/gate projection. Invalid trials stop with a numerical
error, not a biological outcome. Cubic observations also require domain and
accuracy checks: valid endpoints do not prove an interpolated gate stays in range.

MODEL-004 then needs eager/JIT agreement, stable cell/edge identity and capacity
permutation checks, complete-state restart including `g` and `T`, future-only
branches, observation-schedule independence, source/runtime refusal, and all
earlier-model regressions. Archive verified 0.5.0 before changing package source.
CONTACT-003 still separately needs a source-compatible coupled trajectory panel.

## Computational multiscale implications

Keep sparse gather/evaluate/scatter kernels, array state, explicit masks and
host-resolved controls. Gate arrays belong on device with ion state; no Python
gate object per cell/edge or host callback per integration stage. Independent
world batching remains distinct from a communicating graph or multiple organs.

Electrical relaxation, gate relaxation and amount equilibration can have
different timescales. Profile them on qualified coupled workloads before choosing
subcycling, implicit blocks or a quasi-steady reduction. An eliminated gate can
remove history dependence; any reduced model needs explicit carried state and
held-out intervention/recovery checks. Resolution/fidelity, numerical method,
precision and CPU/GPU placement remain separately recorded choices. Organ presets
and future inter-organ ports stay data-defined, without adding unused machinery
to this first pair.
