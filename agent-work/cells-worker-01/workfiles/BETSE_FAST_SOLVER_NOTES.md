# Pinned BETSE fast equivalent circuit component

Chief assigned new source/capture/reference/component files only. Root owns
initialization and shared docs; Specialist owns combined global-control
readouts. CPU3 and CPU7 qualifications stay untouched. This task maps and
prepares source-level validation without numerical execution until a free CPU
is coordinated. No conservative tissue solver or qualified source is changed.

The source is BETSE1.5.0, revision5269a714aa2593ed2a6708c4516289977d8ae1a2.
The private capture will authenticate checkout and installed bytes. It executes
the actual fast initializer and complete fast loop under normalized phase,
logging, storage and exception interfaces, with networks and voltage-sensitive
junction callbacks disabled. Explicit current/control inputs remain caller
declarations, not a captured network or global-control implementation.

Initialization order is material: init_dynamics computes conductivity as an
ion sum using q*F/kb, then calls fast_sim_init; run_sim_core subsequently calls
update_V, which overwrites sigma_cell with an ion mean using F^2/R. The latter
conductivity enters the fast readouts. Actual initial voltage remains caller
owned; the new component does not recreate charge conditioning or update_V's
full current/electrostatic initializer.

For each enabled source ion, fast_sim_init uses the mean intracellular
concentration, a mean extracellular grid concentration when is_ecm=True, and
the membrane-indexed extracellular vector otherwise. Runtime self.T enters
Nernst/GHK potentials; configured p.T enters conductivities. Dm is m2/s and is
divided by membrane thickness; it is not a permeability input. The GHK leak
formula groups all valences by sign, including multivalent ions; its leak
voltage is distinct from each ion's z-dependent Nernst reversal potential.

Let n_i be the membrane count, a_m/A_i the membrane/cell surface ratio, and
v_m=V_neighbor-V_owner from the old cell voltage. Native conductances are
G_leak_i=sum_m(sigma_mem_m*a_m)/A_i and G_gj_i=sum_ion(sigma_gj)/n_i.
The literal Euler update is
V_i'=V_i+dt/Cm*(G_gj_i*sum_owned(v_m)-sum_owned(J_extra_m*a_m)/A_i
-G_leak_i*(V_i-E_leak_i)). Current readouts use old v_m even after publishing
new V: Jn_m=-v_m*G_gj_owner+J_extra_m. They omit leak current. These are source
equations, not a physical charge/energy-conserving tissue model.

The fast loop updates gjopen but does not multiply it into either the voltage
update or Jn. Event-time permeability/temperature changes likewise do not
recompute the prepared conductances in this loop. Molecule/GRN hooks can evolve
their own states and supply current; cuts can reinitialize coefficients, but
neither is part of the small circuit component. There is no built-in ionic
concentration evolution, Na/K pump step, full native channel/protein-noise loop,
extracellular voltage solve, calorimetric heat or work ledger here.

Boundary faces have the same owner/neighbor and zero gap voltage. The loop
imposes no time-varying extracellular Dirichlet voltage. Its membrane field
readout calls single_cell_div_free with cbound=False, including boundary faces.
Cell field readouts divide by an additional0.1*sigma_cell. They are literal
diagnostic arrays, not a qualified physical electric field solution.

Original INIT/SIM linspace labels span N*dt in N calls while elapsed time
advances by dt on every call, including the t=0 label. SIM fires events before
the circuit step; INIT does not. Sampling does not determine evolution.
The component uses the existing explicit native calendar and preserves its
original count/cursor. It accepts caller-supplied post-hook current/block
packets on SIM calls; INIT keeps its declared carried packet.

Source check_v rejects NaN voltage only. The component will preserve literal
raw trials and additionally refuse nonfinite results, with the stricter guard
explicit in diagnostics. It will not repair singular GHK inputs, clamp Euler
steps, invent a heat law or claim unconditional Euler stability. A monotone
Euler step bound can be reported separately from literal-source admission.

Validation must independently reconstruct all initialization coefficients and
carry complete circuit/readout histories, use authenticated native code in a
separate process, exercise both environment modes, asymmetric geometry and
ion valences, distinguish configured/runtime temperature and old/new readouts,
preserve actual nonfinite failures, and test INIT/SIM labels, block omission,
sampling, terminal/refused calls and immutable parent state. Exact source/RNG
absence plus finite/domain/unit tolerances remain explicit. Full physical,
network, electrostatic initialization and GPU parity are outside this claim.
