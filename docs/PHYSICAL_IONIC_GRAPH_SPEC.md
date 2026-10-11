# Physical ionic graph: ownership before scale

SPEC-007 / D052, 2026-09-10. A bounded **instantaneous reference contract** after
[CORE-007](../reports/CORE007_ACCEPTANCE.md), not a new production model,
trajectory qualification, GPU implementation or biological result. Cells remains
0.12.0. This composes the accepted membrane/channel physics with the reciprocal
selective-contact law from [SPEC-002](SELECTIVE_CONTACT_SPEC.md).

## Scope and data

One fixed graph contains N positive-volume, well-mixed cells, N bath-facing
membranes, K membrane channels and E identified junctions. N >= 1; E may be zero.
All cells share one externally maintained bath, species table and temperature.
Cells may differ in volume, membrane area/capacitance, amounts, fixed charge,
voltage anchor, passive permeability, pump parameters and channel state.
For this first reference each membrane has zero or one Kv1.5-style channel;
K need not equal N. Extending the channel inventory is a separate versioned choice.

The reference identity is `cells.physical_ionic_graph_reference@1`. Its JSON has
exactly `schema`, `species`, `bath`, `cells`, `junctions`. Species and bath use the
[SPEC-005 fields](MULTISPECIES_MEMBRANE_SPEC.md). Each cell entry has exactly
`cell`, `membrane`, `channel`; the first two use SPEC-005 and `channel` is either
null or the [SPEC-006 channel record](VOLTAGE_GATED_CHANNEL_SPEC.md). Host
projection into these unchanged references is explicit, not equation duplication.

Each junction has `id`, `from_cell`, `to_cell`, `area_m2`,
`permeability_m_per_s` and `residual_fraction` keyed by every species, plus
`gate`. The gate record has `law: symmetric_opposing_relaxation@1`,
`sensitivity_per_V`, `half_voltage_V`, `tau_s`, `initial_gate`.
Species order and entity-list order are storage choices, not chemical roles.
IDs bind owners and endpoints before evaluation; kernels must never dispatch on
an assay, organ name or species spelling.

All physical entity IDs are globally unique except the single shared bath
reference. Species IDs occupy their own namespace. Self-edges, unknown endpoints,
duplicate edges including reversed duplicates, inconsistent species maps,
missing/unknown fields, duplicate JSON keys, nonfinite/bool-valued numbers and
nonfinite derived coefficients are errors. Parallel paths between the same cells
are excluded in this version to make accidental duplicate transport unambiguous.
An identified zero-permeability or inhibited edge is not a deleted edge.

The resolver never invents charge support, normalizes concentrations, equilibrates
gates, clips state, or repairs an inconsistent anchor. Synthetic fixture charges
are calculated once when declaring the inputs and stored explicitly in the panel.
No fitted physiological parameters or source-compatible EMT coordinates enter it.

## State and ownership

These are the proposed production axes, not a registered array schema yet.
The independent scalar reference uses immutable cell-/edge-major tuples to call
the previous local references; production will need an explicit axis adapter.

| Quantity | Production axes | Meaning |
| --- | --- | --- |
| Amount n | species × cell | Only mobile material inventory, fmol |
| Baseline membrane transfer L | species × membrane | Signed bath-to-cell history, fmol |
| Pump cycles P | membrane | Signed history, fmol cycles |
| Membrane dissipation Dm | membrane | Local leak + pump + channel integral, pJ |
| Membrane gates m,h | 2 × channel | Complete intrinsic channel state |
| Channel transfer H | channel | Separate signed inward history, fmol |
| Junction gate g | edge | Complete intrinsic contact state |
| Junction transfer T | species × edge | Signed history in the stored orientation, fmol |
| Junction dissipation De | edge | One nonnegative integral per physical edge, pJ |

Cell, membrane, channel and edge counts/capacities remain separate. A junction
owns no material, voltage, membrane capacitance or duplicate recipient cell.
Ledgers are not material pools and never drive the instantaneous transport law.
Local channels and junction gates are distinct state even if both are inhibited.
All histories and original electrical anchors must survive restart and branching.

## Electrical closure: a deliberate approximation

Each cell retains one diagonal capacitance to the shared bath at zero potential:

```text
C_i = A_i c_m,i
V_i = Vref_i + (q_f/C_i) sum_s z_s (n_si - nref_si)
C_i dV_i/dt = q_f sum_s z_s dn_si/dt
deltaV_e = V_from(e) - V_to(e)
```

Here q_f = F * 1e-15 C/fmol. Fixed charge, amount anchors and Vref are explicit
and consistent under SPEC-005. Junction area affects transport only; adding or
blocking a junction does not silently change bath-facing area or capacitance.
This omits mutual capacitance, access resistance, junction charge storage,
extracellular potential gradients, membrane patches and geometry remodeling.
Those require their own electrical/field closure, not merely additional edges.

The common bath is important for the energy identity below. Heterogeneous bath
chemical potentials would require explicit reservoir-work terms for internal
exchange. They are not accepted by this first graph. ATP drive may differ between
local pumps because its supplied power is explicitly counted per membrane.

## One owned flux per junction

For the stored orientation A -> B, concentrations c = n/volume in mM (numerically
mol/m3), a = 1e-15 mol/fmol, and B(x) = x/expm1(x), B(0)=1:

```text
x_se = z_s F (V_A - V_B) / (R temperature)
p_eff,se = P_se * u_e * [r_se + (1-r_se) g_e]
J_se = (A_e p_eff,se/a) [c_sA B(-x_se) - c_sB B(x_se)]
dT_se/dt = J_se
dn_sA/dt += -J_se
dn_sB/dt += +J_se
delta_mu_se = RT log(c_sB/c_sA) + z_s F (V_B-V_A)
dDe_e/dt = -1e12 a sum_s J_se delta_mu_se
```

The edge calculation is the same constant-field law as membrane permeation,
with the destination as the inside and source as the outside. Reversing storage
orientation negates J and T but changes neither endpoint amounts, gate kinetics
nor dissipation. Zero voltage gives diffusion; each species has zero flux at
its Nernst balance. Passive dissipation is nonnegative within arithmetic limits.
Permeability and residual fractions are species-specific; charge uses actual
declared valence, including an impermeant species' contribution to voltage.

The inherited phenomenological symmetric gate is:

```text
g_inf(dV) = 1 / [1 + exp(a_g*(-dV-Vh)) + exp(a_g*(dV-Vh))]
dg/dt = (g_inf(dV)-g)/tau_g
```

Use a stable exponential normalization; a_g > 0, Vh >= 0, tau_g > 0 and g in
[0,1]. The kinetics are synthetic, not a fitted connexin or microscopic BETSE
gate. u_e in [0,1] scales transport only: blocking does not freeze g, clear T or
remove the contact. r=0 closes that species at g=0; r>0 retains residual flux.
The analytic held-dV gate response is an isolated equation check, not a
whole-cell voltage clamp or a solution of the feedback-coupled graph.

Local leak, pump, membrane channel and every edge read the **same complete stage**.
For a shared recipient C, evaluate its local membrane once, then add A->C and
B->C. Summing two complete pair RHS evaluations would duplicate C's membrane
and pump; running two independent recipients would lose the shared state.

## Material, charge and energy checks

Let B_ie be the incidence matrix: -1 at the stored source, +1 at destination,
zero otherwise. This is mathematical notation; implementation need not allocate
a dense matrix. Let M_si = L_si + nu_si P_i + sum_k H_k for channels bound to i,s.

```text
n_si - nref_si = M_si + sum_e B_ie T_se
bath_exchange_si = -M_si
sum_i (n_si - nref_si + bath_exchange_si) = 0
sum_i C_i (V_i - Vref_i) = q_f sum_si z_s M_si
```

Internal transfers cancel separately for every species. In a bath-disconnected
world (all leak, pump and membrane-channel availability zero), total species
amount and capacitance-weighted voltage are conserved. The unweighted voltage
sum need not be conserved when capacitances differ. Conservation does not imply
all cells attain equal voltage or concentration under selective transport.

For the common bath, fixed geometry and ideal dilute chemistry:

```text
Omega = a RT sum_si n_si [log(c_si/cbath_s)-1] + sum_i C_i V_i^2/2
dOmega/dt = sum_i supplied_ATP_power_i - sum_i Dm_rate_i - sum_e De_rate_e
```

Do not place edge dissipation into both endpoint membrane ledgers. The finite
history identity uses Omega-Omega_initial, accumulated dissipation and signed
pump-drive work. Instantaneous checks here do not qualify integrated histories.
Gating charge, protein conformational energy/turnover, metabolism, osmotic and
mechanical work are omitted, as in the earlier local/physical-pair contracts.

Per-edge history cannot generally be recovered from current amounts: a closed
cycle can carry a signed circulation with zero net node increment. Keep T even
when a later coarse observer cannot distinguish the node states. An algebraic
circulation witness is not a dynamically generated biological memory result.

## Numerical and future GPU boundary

All real amounts are positive; all stored values and derived rates are finite;
gates remain in [0,1]. Local domains are inherited from the selected local model
(including [-0.120,0.060] V for a present Kv1.5-style channel). Every declared
species on every real junction obeys abs(z F deltaV/(RT)) <= 50, even when its
permeability/control is zero. Inactive future capacity must be sanitized before
nonlinear evaluation; inhibited real entities must still be validated.

**No graph timestep is selected here.** The one-cell 0.5 ms and old pair 1 ms
limits are not graph guarantees: coupling strength, small cell volume/capacitance
and recipient degree can create faster modes. NUM-008 must freeze coupled
trajectory/refinement cases, admissible stage and cubic-interior domains,
event/observation rules and budgets before CORE-008 production acceptance.
One physical world uses a coordinated timeline. Local leak, pump, channel and
edge controls are independent right-continuous groups with explicit time-zero
values and union-of-events splitting; schedules are a subsequent trajectory gate.

The sparse endpoint map and separate numeric axes suit later JAX gather/flux/
scatter kernels. A partition boundary must exchange the current solver-stage
endpoint amounts/voltages/gates, evaluate the edge under one deterministic owner,
and deliver the same signed integrated transfer to both sides. Do not run a
complete cell once per neighboring edge. Count edge working state and transfer
registers in memory preflight; never require a dense N-by-N transport matrix.
GPU reductions may reorder floating-point addition; conservation/error and
reproducibility policies need explicit qualification, not an assumed bitwise
cross-device guarantee. No partitioned device execution is implemented here.

## Frozen checks and progression

The [synthetic panel](../configs/reference/physical_ionic_graph_v1.json) fixes
inputs, arithmetic probes and tolerances before evaluation. It covers local
single-cell reductions, heterogeneous disconnected cells, reciprocal pairs,
three-cell shared-recipient stars, a ledger-only cycle witness, and a +2 species.
The [independent checker](../scripts/check_physical_ionic_graph.py) uses Decimal
edge arithmetic, independent incidence accounting, old hyperbolic pair reduction,
orientation/list/species permutations, disabled-route separation and per-edge
power checks. No production RHS or reference time integrator is an oracle.

The [design-check report](../reports/SPEC007_DESIGN_CHECK.md) records the result
and retained failures. Passing arithmetic establishes an internally consistent
candidate coupling, not trajectories, biological plausibility, complete BETSE
coverage or organ function. Next: NUM-008 short graph trajectory qualification;
then CORE-008 can implement a new production identity without altering the
accepted one-cell and physical-pair models. The unrelated long E02 source
campaign, GPU optimization and closed biological pilot remain deferred/unchanged.
