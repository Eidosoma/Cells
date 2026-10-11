# One-cell multispecies membrane contract

SPEC-005, 2026-09-09. This is an **instantaneous engineering reference**, not a
registered Cells model or a numerical trajectory qualification. It implements
the scope of [the stage-1 brief](MULTISPECIES_MEMBRANE_NEXT.md). The existing
`bioelectric_cell@1`, its equations, timesteps and saved evidence remain unchanged.

## Ownership and data contract

The proposed reference identity is `cells.multispecies_membrane_reference@1`.
JSON contains exactly the following objects; unknown fields, duplicate JSON
keys, missing bindings and nonfinite numbers are errors. Units are in field
names, not selectable strings. There are no executable configuration expressions.

| Object | Required fields and meaning |
| --- | --- |
| Root | `schema`, `species`, `cell`, `bath`, `membrane` |
| Species list | Records with unique `id` and integer `valence`; order is storage order, not chemical identity |
| Cell | `id`, `volume_pL`, `initial_amount_fmol` keyed by every species, signed `fixed_charge_equivalent_fmol`, `initial_voltage_V` |
| Maintained bath | `id`, `temperature_K`, `concentration_mM` keyed by every species, signed `background_charge_mM` |
| Membrane | `id`, `inside` cell ID, `outside` bath ID, `area_m2`, `specific_capacitance_F_per_m2`, `passive`, `pump` |
| Passive mechanism | `law: constant_field@1`, `permeability_m_per_s` keyed by every species |
| Optional pump | `null`, or `id`, `law: nak_atp_affinity_tanh@1`, `roles`, `stoichiometry`, `capacity_fmol_per_s`, `drive_J_per_mol` |
| Pump roles | `sodium` and `potassium` explicitly bound to distinct, monovalent-positive species IDs |
| Pump stoichiometry | Exactly those two bound IDs with inward coefficients -3 and +2, respectively; all other coefficients are zero |

Species IDs need not literally be `Na` or `K`: a role binding declares that
record's chemical role. A valence check is not independent verification of its
chemical identity. This first contract does not accept arbitrary kinetic laws,
additional pumps, mixed valence/speciation, neutral tracers or channel states.

All amounts and bath concentrations are strictly positive, including species
whose transport is off. Volume, area, specific capacitance and temperature are
positive. Permeabilities and pump capacity are nonnegative. Signed valence is
an integer in {-3, -2, -1, 1, 2, 3}; this bounds reference arithmetic, not future
biology. Each evaluated species must satisfy `abs(z F V / (R T)) <= 50`.
Finite inputs must also yield finite derived quantities. There are no amount
floors, voltage clipping, automatic bath repairs or dropped charged species.
Rate controls lie in [0, 1]; omitted reference controls mean all routes enabled.

Host resolution turns IDs and mappings into immutable, aligned tuples: valence,
amount anchors, bath concentrations, permeabilities and pump stoichiometry.
The scalar reference uses these resolved values without importing Cells/JAX.
A future production operator can use array leaves with the same ownership;
this reference neither installs that array schema nor defines padding/sharding.

## Units, boundary and one-membrane closure

Use exact SI defining constants `N_A = 6.02214076e23`,
`e = 1.602176634e-19 C`, `k_B = 1.380649e-23 J/K`, with
`F = e N_A`, `R = k_B N_A`. Let `a = 1e-15 mol/fmol` and
`b = 1e-15 m3/pL`; then `q_f = a F C/fmol` and
`c_i,s = a n_s / (b volume_pL) = n_s / volume_pL` in mol/m3 (numerically mM).

The bath potential is zero. Bath concentrations, background charge and
temperature are externally maintained. Require
`sum(z_s c_o,s) + background_charge_mM = 0` within 1e-12 mM charge equivalent.
Background charge has no transport route or dynamic inventory. Its scalar
charge does not identify a chemical composition or osmolarity. External support
must supply/remove each net exchanged species; the exchange ledger is not a
finite reservoir. Fixed volume also assumes mechanical/osmotic support.

The single membrane owns `C = area * specific_capacitance`. Its voltage is
inside minus outside. For signed fixed charge equivalent `X` in fmol,

```text
Q_fixed = q_f X
C V = Q_fixed + q_f sum(z_s n_s)
C V_ref = q_f [X + sum(z_s n_ref,s)]
V(n) = V_ref + (q_f / C) sum[z_s (n_s - n_ref,s)]
C dV/dt = q_f sum(z_s dn_s/dt)
```

Both `X` and `V_ref` are explicit inputs: the latter is a consistency assertion
and stable numerical anchor, not another dynamical degree of freedom. Refuse
inconsistent inputs when the direct initial-charge voltage differs by more
than 1e-10 V; retain and report the residual caused by decimal/binary rounding.
Never recalculate X to force a desired voltage or reset anchors at a new state.
Adding a charged species without explicitly reconciling the declared initial
charge must fail. An existing definition cannot gain a species at runtime.
Bulk intracellular electroneutrality is not an additional equation.

This derivation has exactly one membrane, constant geometry and no electrode.
It is not a closure for several membrane surfaces, evolving volume/area,
intracellular subcompartments, finite external potentials or spatial fields.

## Transport and signed energy

For each species, positive flux means bath to cell, in fmol/s:

```text
x_s = z_s F V / (R T)
B(x) = x / expm1(x),  B(0) = 1
J_s = (A P_s u_s / a) [c_o,s B(x_s) - c_i,s B(-x_s)]
mu_s = R T log(c_i,s / c_o,s) + z_s F V
```

Use the removable-singularity series near zero. `P_s = 0` or `u_s = 0` gives
exact zero transport but keeps that species in concentration/charge accounting.
At zero voltage the law reduces to ordinary diffusion. At
`V = R T log(c_o,s/c_i,s)/(z_s F)` that species' passive flux vanishes.
Swapping concentrations and reversing voltage reverses flux. Passive
dissipation is `-a J_s mu_s >= 0` W, subject to floating-point residuals.

The only pump law in this version deliberately reproduces SPEC-001's synthetic
reversible, externally energized cycle, not a calibrated ATPase:

```text
nu_Na = -3, nu_K = +2, other nu = 0
G_cycle = G_drive + sum(nu_s mu_s)
r = capacity * u_pump * tanh[-G_cycle / (2 R T)]
J_pump,s = nu_s r
```

Roles, not storage positions, define nu. Forward cycles export one net positive
charge; stall occurs at `G_cycle = 0`, and positive cycle energy reverses the
cycle. Capacity is per membrane in fmol cycles/s, **not** per area. Doubling
area doubles passive flux and capacitance, not an independently specified pump
capacity. Drive is signed J/mol cycles; chemical power supplied to the cell
is `-a G_drive r` and cycle dissipation is `-a r G_cycle >= 0` W. No ATP,
calcium-binding or buffer pool is implicit in these equations.

## Material, charge and energy interfaces

```text
dn_s/dt = J_s + nu_s r
dL_s/dt = J_s                         # passive transfer ledger
dP/dt = r                            # signed cycle ledger; absent pump means zero
n_s - n_ref,s = L_s + nu_s P
bath_exchange_s = -(L_s + nu_s P)     # signed transfer into maintained bath
I_in = q_f sum[z_s (J_s + nu_s r)]
I_out = -I_in
C (V - V_ref) = q_f sum[z_s (L_s + nu_s P)]
```

Negative signed ledgers are valid; negative amounts are not. Instantaneous
material rates and algebraically constructed nonzero ledgers can check these
identities without integrating a trajectory. For the ideal dilute, fixed-bath
relative chemical energy plus capacitor energy, the rate is
`dE/dt = a R T sum[log(c_i/c_o) dn/dt] + C V dV/dt`.
It must equal supplied chemical power minus total passive/pump dissipation.
This is an open-system energy identity, not conservation of an isolated cell
or a full metabolic/thermal budget.

## Frozen synthetic panel and tolerances

[multispecies_membrane_v1.json](../configs/reference/multispecies_membrane_v1.json)
is written before evaluation. Its two cases are not fitted to RPTEC or BETSE:

- `nakcl_reduction`: exact previous Na/K/Cl parameters and initial anchor, with
  an explicitly supplied rounded fixed-charge equivalent from SPEC-001.
- `divalent_with_background`: those Na/K parameters plus 0.001 fmol of a +2
  species, bath concentration 2 mM and permeability 1e-11 m/s. Bath chloride is
  explicitly 156 mM, with +2 mM charge-equivalent maintained background. Fixed
  intracellular charge is explicitly 0.002 fmol more negative. These are new
  declared inputs, not a normalization operation on the first case.

The panel freezes a deterministic passive-law grid, signed pump-drive probes,
zero/stall/off/area/orientation/permutation checks and nonzero ledger probes.
The passive grid compares binary64 with an independent 70-digit Decimal
direct exponential expression. Na/K/Cl reduction compares with the existing
independent hyperbolic reference, not production kernels. Positive/negative
valences up to three are arithmetic probes; only +2 extends the assembled
species fixture. Non-identifiability of concentrations, permeability and drive
from voltage alone is not resolved by this engineering panel.

All comparisons use `abs(error) <= atol + rtol * abs(expected)`, unless exact
zero, a domain rejection or a signed inequality is specified. Tolerances are
frozen in the JSON: they are engineering arithmetic limits, not statistical
uncertainty or biological acceptance. Record failed checks; any needed physical
or tolerance revision requires an explained, versioned protocol, not tuning.

## Gate after this contract

NUM-006 must separately freeze trajectory cases, reference methods/refinement,
stage-domain checks, energy/material residuals, controls and error budgets in
the new regime. No old RK4 timestep is inherited. CORE-006 may then implement a
new versioned pure-array assembly and qualify eager/JIT execution, snapshots,
event semantics and regressions. Later GPU and multiscale work retain the
[execution contracts](MULTISCALE_EXECUTION_ARCHITECTURE.md); instantaneous
scalar arithmetic is not device qualification or interacting-organ support.
