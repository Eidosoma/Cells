# Modern ECM catalog with CaATP and fields — source audit and planned boundary

Chief assigned new `betse_normal_ecm_catalog_join` ownership after calcium01.
Static preparation only: no science imports/evaluations, collection, runs,
polls, PROGRESS edits or changes to field01/calcium01/shared components.

Normal order is ordinary moving-ion refresh → CaATP (ER remains disabled) →
explicit late-flux seam → genuine GRN clear_run_loop → channels → modulators →
GRN chemistry/molecular transport → deferred ordinary ionic commit → complete
current/environment/voltage fields → NaN-only check_v. Real cold gene config
reads `channels` and sets its owner flag; do not inject channels=True.

Current qualified GRN subset intentionally rejects channel config and its
seven-field wire/cache drops all Channel/core gate fields. The old whole catalog
join is scalar-bath/noECM and requires disabled CaATP. These are real missing
seams, not permission to relabel or bypass their guards. A new literal cold
reader/factory/dispatch and complete channel cache/restore namespace is required
under this prefix. Reuse unchanged catalog class math, ECM update_Co/electroflux,
CaATP and complete field components; leave their source and scopes intact.

All55 modern classes come from7 actual factory families Na/K/Cl/Ca/Fun/Cat/ML.
Their class gates read Vm and dt, with no implicit free-Ca state.23 route Ca,
including CatLeak's zero-weight Ca route; this does not make them Ca-sensitive
gates. Source channel activator/inhibitor expressions can explicitly read live
Ca from membrane aliases or the mapped environment, with optional voltage-
sensitive Km. The standalone legacy cagPotassium function has no runtime caller
and is not a modern factory class; retain it as a separate refused dependency.

Cold class initialization reads prepared initial Vm before bootstrap update_V.
Each normal population updates once from the current shared Vm, then each
class-ordered ion route reads fresh bulk cell_concs gathered by owner (not the
possibly stale membrane shell), current full E-grid env_concs mapped to membranes,
and actual Vm/runtime T/rho_channel. update_Co directly updates bulk, membrane
and E-grid aliases before the next route/population. Source fluxes_mem is not
incremented; core.extra_J_mem accumulates channel current and later molecular
current before publication. Final chan_flux/DChan cache is last-route only.
Zero-weight routes still run electroflux/update_Co and consume voltage nonce.
CaATP sampled its earlier membrane Ca and stored flux, with ordinary commit
still deferred. No instantaneous CaATP→bulk-Ca update may be invented.

The factory's all-target branch derives cells.mem_i. Named-profile targets
require explicit original tissue index preparation on sim.dyna, preserving
ordering/duplicates and np.asarray dtype semantics. Empty profile targets retain
their native float-index refusal. Expression profiles require separately owned
expression/tissue data and should be explicit dependency refusals in this scope.
INIT-only channel skip is not active in normal SIM; init_activeFalse does not
skip cold initialization or normal SIM updates. No forced INIT flags.

Independent checks need actual before-channels and actual post-channels/pre-
modulator inputs, because the inherited pre-GRN checkpoint is after clear but
before channels. Existing GRN local equations can use the post-channel snapshot
and its incoming_channel_current; they must not claim to predict channels from
the earlier state. Material reference must include scalar direct channel
updates before deferred ordinary commit, with source-effective/true-grid/scatter
books separated. Full original caches, parents, intermediate returns and raw
partial failures must precede comparisons. Preserve every fixed inherited
gate/flux/material/current/field budget and old Cav_G/ER/material failures.
