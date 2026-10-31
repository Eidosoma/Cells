# Normal ECM material, network and field timestep

Chief authorized a separate `betse_normal_ecm_field_join` branch. Preparation is
static only; no scientific imports, evaluations, collection, jobs or polling.
Existing scientific components and their frozen/failed evidence stay untouched.

The actual normal source has an initial `update_V` call at Simulator1041 after
`init_dynamics` and `clear_storage`, then per-step reset/events/pump, ordinary
moving-ion membrane/GJ/ECM/intra operations, genuine GRN dispatch1306–1319,
deferred `update_all_concs`1357, `update_V`1360 and `check_v`1363. The new boundary
will execute the initial field call on an explicitly prepared phase and the
normal suffix after each material/network call. Full phase construction,
scheduling/events/noise/fluid/deformation, pump/channel handler laws and full
solver sampling/persistence remain outside the bounded composition.

The original bootstrap calls only `update_V`, with no `check_v`. The normal
suffix's `check_v` tests only `np.isnan(vm)` and even permits infinite vm.
The port's finite field/current/voltage guards are explicitly stricter admission.
The complete original `get_current` in field-native capture is reusable. The
old voltage-native adapter only executes a current-prefix/BVP substitute and
must not be presented as complete field reconstruction. New native code must
put the entire original `update_V` and `check_v` into the field namespace with
the actual complete `get_current`, HH/Gaussian/FD bodies and derived operators.
Port current/environment/voltage components can be joined using one binding:
the voltage operator/map derives from the field geometry, with original
`cells.diviterm = cell_vol/cell_sa` and original radial-vector/radius statements.
No inverse, mapping, radius or old E-field is accepted as prepared user input.
Initial membrane voltage remains a source state input, consumed by bootstrap
`update_V`; subsequent old E-fields come exclusively from the previous source
field result. Applied voltage boundaries remain explicit external drives.

The initial sigma/ko cache uses original configured-temperature initialization
material and q/F/kb/NAv constants. It stays fixed during subsequent calls.
`update_V.sigma_cell` is separately recomputed from current cell material using
F²/(R*T), a species mean and the source0.1 factor, distinct from initializer sums.
The complete source field and cell-voltage outputs must carry, including local
and total currents, HH intermediate arrays, boundary Phi, environment voltage,
E_env, E_cell, normal fields, vm_ave and dvm. GRN extra rho/current publications
are read at the end of the same step and are distinct from reconstructed J.
GJ voltage/open/field caches remain exactly where the source updates them; an
end-of-step vm update must not silently refresh those earlier caches.

Use bounded manufactured, nominally electroneutral starting material by
declaring P=Na+K-Cl for bulk, membrane and E-grid inputs; derive reservoir P in
the same input recipe. This is a new declared case family, not repair of the
retained signed_environment failure. A fixed small declared dt and explicit
capacitance suit the existing artificial metre-scale geometry; no numerical
outcomes may select values or budgets. Normal and polarized voltage branches,
rectangular/duplicate maps, smoothing, source cache hold and publication carry
need explicit coverage. Unsupported charged cold compensation stays outside
this prefix; real nonempty X/Y GRN cold readers and normal dispatch remain.

Independent checks have three actual conditional boundaries: before ordinary
material, before GRN and before final current/field/voltage computation, plus
cold/bootstrap input capture. Each uses freshly archived actual inputs before
outgoing computation; no independently carried trajectory claim. Reuse the
unchanged ordinary Decimal reference for one actual material call (compare
ionic/flux/ledger outputs while distinguishing molecule-induced vm nonces),
and the qualified ECM GRN local reference. The field reference independently
derives geometry, initializer cache, inverse, Gaussian, currents, HH and voltage.
Typed, reference-fixed gross budgets must propagate cancellation through
F*z*c dot products, derivative neighbor sums, absolute inverse/Gaussian operators,
screening factors and voltage reconstruction. Relative-only allowances around
nearly neutral rho cannot establish accuracy. Actual outgoing arrays never set
their own allowances; retain complete lower/target/actual/error/budget buffers.

Preserve raw partial failures at material, first/second molecular and field or
voltage boundaries. A stricter finite guard is distinct from a native exception:
`check_v` only inspects vm and may permit nonfinite environment/cell fields.
Existing source defects (HH Dirichlet inverse and corner order, source FD edge
signs, repeated-membrane area denominator, Gaussian modes, fast duplicate-last
exchange, shell/cache timing, unweighted mean vm, and boundary subtraction only
in the zero-polarizability branch) remain visible. No physical/global material,
charge or energy conservation, full initialization, field lifecycle, biological
or trajectory claim follows. The old material39/40 failure remains failed, and
its missing separately retained complete reference buffers are not recreated.
