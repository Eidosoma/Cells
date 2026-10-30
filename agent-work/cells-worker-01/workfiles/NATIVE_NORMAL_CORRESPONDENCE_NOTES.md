# Native FULL-normal closed-loop correspondence inventory

Chief requested a source inventory and one new implementable native component.
The scope sent to Chief is the intracellular prefix of
physics/ion_current.get_current through sim.Jc: charge density, signed current
aggregation, source smoothing, inward membrane current and cell-vector/current
readouts. It uses explicit post-flux concentration/flux/current/geometry inputs.
No shared APIs, Root initialization, salt/water energy work, Specialist global
control readouts, conservative solver or field/boundary algorithm is changed.
Numerical validation for this new component awaits separate CPU coordination.

The paired machine-readable inventory is native_normal_solver_inventory.json.
It pins actual source bytes/AST sites and separates existing isolated component
coverage from unqualified full chronological composition. Presence of a source
module or a passed isolated primitive is not native closed-loop correspondence.

The native FULL order is: reset flux buffers; SIM event dispatch; Na/K pump;
for each moving ion, membrane electrodiffusion, gap-junction update, optional
ECM transport, then membrane concentration reconstruction; calcium handling;
molecule/GRN transporter/channel/modulator/network hooks; optional protein
noise; osmotic/flow/deformation hooks; membrane and then junction concentration
commit/no_negs; get_current and voltage reconstruction; NaN voltage gate;
sampling. Labels are the original native linspace labels, with dt per call.
Reproducible Root handoff and source calendar components cover explicit parts
of the lifecycle, but not this full native initialization and chronological join.

Concrete call-order differences must remain visible. update_gj can advance its
voltage-sensitive gate once per moving ion. update_intra simply copies old bulk
concentrations to membrane buffers. update_Co later refreshes those buffers for
membrane exchange, then update_all_concs adds junction changes only to bulk
concentrations. Its subsequent no_negs clips negative bulk values. Thus a
membrane buffer can lag the post-junction bulk value. Existing conservative
RK4/charged loops deliberately do not reproduce this legacy split operator.

Boundary and field gaps remain substantial. cluster_open=False masks membrane
fluxes at boundary faces; junction fluxes zero boundary faces independently.
Ionic ECM concentration transport sets perimeter concentrations before the
update, not after. Fast environment scatter overwrites coincident locations;
the dense map path is a separate native option. No-ECM update_Co returns an
unweighted mixed bath value. Existing native environment/geometry components
capture selected stencils/maps/bath semantics, not their entire feedback loop.

get_current's ECM field branch uses HH decomposition, a lapENV inverse,
surface-charge screening and Gaussian smoothing; its non-ECM branch instead
maps vm/2 into a smoothed grid field. Boundary voltage assignments are ordered
R,L,T,B, including corner overwrites. update_V calls this field/current path,
overwrites sigma_cell using an ion mean, then chooses direct charge/boundary
voltage reconstruction or polarized voltage relaxation. The polarized branch
omits the direct boundary subtraction used by the zero-polarizability branch.
Native inverse/gauge, Gaussian padding, old/new field timing, screening,
voltage initialization and bath/current consistency need an explicit future
coupling contract. Qualified conservative field/energy equations are distinct.

The selected current prefix is well defined without those field choices:
rho=F*sum(z*c_bulk)+rho_extra; Jmem=-F*sum(z*f_mem)+J_extra;
Jgj=F*sum(z*f_gj); Jraw=Jmem+Jgj. Native membrane flux is positive inward,
junction flux is positive outward, and Jraw/Jn are outward current densities.
Javg_cell=sum(Jraw*A_mem)/A_cell;
Jn=w_mem*Jraw+w_other*Javg_cell[owner]; I_mem=-Jn*A_mem.
Jcell_x/y=sum(Jn*n_x/y*A_mem)/A_cell; Jc=Jcell[owner] dot n.
Units are mol/m3, mol/(m2*s), C/m3, A/m2 and A. No electrical work or charge
conservation is inferred merely from these diagnostic arrays.

Smoothing initialization also needs literal semantics. Parameters computes
smooth_cells=1/float(sharpness_cell). init_dynamics uses nfrac=smooth_cells,
w_other=1/(nfrac*n_mems) and w_mem=(nfrac*n_mems-1)/(nfrac*n_mems).
The native comment about sharpness is not substituted for these equations.
Zero sharpness fails during parameter division. Positive values outside the
documented range can produce nonconvex finite weights; the component records
that diagnostic without silently clipping. Total surface current is preserved
by this smoothing only when the supplied cell area equals its membrane-area
sum. The actual ratio and residual must be retained, not repaired.

The new component will keep all original axes/IDs and full float64 inputs,
refuse ambiguous shapes/nonfinite published outputs, retain raw refused
numeric trials, and compute independent equations at two Decimal precisions.
Validation must include exact host source correspondence, independent gross-
scale cancellation budgets, unequal owner counts/areas, neutral/multivalent
species, extra charge/current, sharpness conversion, negative weights,
overflow/nonfinite trials, permutation, unchanged parents and actual CPU/source
pins. It adds one missing readout primitive, not full native solver parity.
