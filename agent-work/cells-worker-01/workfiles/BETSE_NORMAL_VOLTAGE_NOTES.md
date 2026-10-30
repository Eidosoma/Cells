# Scoped normal boundary, cell field and voltage correspondence

Chief approved the B25 dependency boundary and CPU1 guarded qualification.
The new files connect the qualified B24 ion/material join, B23 current prefix
and the normal update_V body. Root owns shared numerical refinement and batch
continuation; Specialist owns thermal clocks. Frozen prior sources stay exact.

The native adapter executes full update_V against actual intracellular
get_current prefix and the actual seven-statement boundary-potential block.
The omitted no-ECM HH/Gaussian environment arrays do not feed these outputs:
update_V consumes rho_cells, Jn, J_cell_x/y and Phi_b, then computes sigma itself.
No environment field, inverse/gauge construction, event program, initializer
or whole-native correspondence is claimed. The grid inverse and its original
ravel axes/gauge provenance are explicit caller inputs; fixtures manufacture
a dense operator to qualify the arithmetic, not a Poisson solve.

Chronology is B24 material calls and their source voltage nonce; B23 current
from committed bulk/flux; boundary potential; ion-mean conductivity overwrite;
voltage, cell fields and dvm; candidate voltage fed into next B24. The membrane
concentration and gap-field caches retain their actual earlier source timing.
Elapsed start/end and dt are recorded per call with a call index; this is not
an event-calendar or conditioning contract. Every parent, phase, raw drive,
intermediate and candidate is retained through immutable arrays and hashes.

Boundary assignments are R,L,T,B: top/bottom overwrite corners. The direct
branch computes rho*diviterm/cm - Phi_b[map]. The polarized branch uses old vm,
Jn, sigma, dt/cm and membrane radius, omits Phi_b subtraction, and responds
only to whether polarizability is zero. Cell voltage averages are unweighted
membrane means. Conductivity is the mean over every supplied ion, including
stationary/zero-diffusion species, using configured temperature. Direct fields
divide current by sigma; polarized fields reconstruct the voltage deviation
using source normals/areas and true-size/radius ratio. dvm uses nonce-updated
pre-voltage, not the prior call's original voltage.

The independent reference uses Decimal90/140 voltage/boundary equations and
the frozen stdlib B23/B24 equation references. Binary64 component stores are
explicit. Gross feedback scales carry charge cancellation into later GHK
fluxes using |B(alpha)|<=1+|alpha| and |B'(alpha)|<=1; amount, current,
conductivity and voltage scales are then propagated in their own units.
Host native arrays/dtypes must also match exactly, independently of budgets.

Qualification plans40 checks:12 three-call coupled histories,36 calls/720
material-stage states,16 native captures and24 fresh reference forms. Cases
cover both branches, flag magnitude, boundary corners/zero bounds/aliases,
temperature split, cancellation, moving order, unequal areas, stale membrane
state, zero conductivity and complete actual nonfinite trials. Source check_v
is NaN-only; finite voltage with nonfinite fields or infinity may complete.
The component refuses nonfinite published outputs with raw partial lineage.

The first39-check attempt passed38 and exposed material instability in the
zero-conductivity polarized history at dt0.002s. Its original raw input is
retained byte-for-byte as an adversarial replay fixture. The native adapter
and coupling exception now retain failed material arrays before voltage, in
addition to complete successful prefixes. The ordinary zero-conductivity
comparison explicitly uses dt1e-6s. Constitutive equations and physical/error
tolerances are unchanged; source numerical instability is not repaired.

One CPU1 thread,480s maximum,1GiB tree RSS and8GiB host reserve use established
supervision. The two historical grid/specs hashes affected by Chief's announced
shared edits remain recorded;129 other prior files are protected. Scientific
children deny/import-guard production code as appropriate and report actual
CPU affinity. No physical tolerances, conservative solver, shared APIs or
active jobs are changed. Own queue/receipts hold results for Chief review.
