# Full calcium/fuel bath INIT → SIM handoff

Ready for Chief capture and qualification. This feature closes the risk that a
new SIM phase could drop a chemical/fuel/work history or validate turnover
against fresh pools instead of the carried state. Worker checks are AST, lint,
raw recipe metadata and import audits only. No model parser, state constructor,
RHS, integrator, pytest collection, numerical job or active-job poll ran here.
Machine-readable paths and source hashes: `open_calcium_bath_epoch_workqueue.json`.

Six new product modules define `resolved_open_calcium_bath_epoch@1` and
`resolved_open_calcium_energy_bath_epoch@1`, with exact classes
`SurfaceOpenCalciumBathEpochModel` and `SurfaceOpenCalciumEnergyBathEpochModel`.
`schema.scheduled_spec` returns the corresponding ordinary bath owner. Bridge
`open_calcium_bath_phase_handoff` exposes KIND/REQUEST_KIND, capture/decode,
prepare/replay, and read/write preparation APIs. Existing helpers and wrappers
remain unchanged; Root owns shared routes, tissue_phase and public integration.

Every one of the 35/39 non-clock arrays carries bit for bit, including owned
chemistry, ER gates/transport/work, actual ATP/ADP/Pi, regeneration and variable
reservoir chemical work. Only `phase_clock_s` resets to zero. Original amounts,
chemical/fuel anchors, geometry and fixed background are preserved. The complete
typed INIT source, accepted step/control position, both clocks and original
layout are archived. SIM sources are refused, including an empty SIM schedule.

The new SIM bath contributes a separate declared initial dose, compensating
electrode charge and chemical/electrical work against the original anchors.
Source physical arrays and the new physical operation are separately recorded.
The existing native overwrite laws, Cl guard, real M ownership, full56 kinetics
and actual calcium/fuel feedback remain. Field and observer paths delegate to
the ordinary complete owner with the actual carried arrays.

New admission first checks actual carried chemical ions plus the conservative
SIM pulse envelope against the unchanged hard ionic ceilings. It checks the
carried state at all declared SIM control and critical bath clocks. For finite
fuel, every independent pulse-box corner and held control is evaluated using
the carried chemical/gate state and original amounts plus the actual saved
ATP/ADP/Pi increments. Gross hydrolysis plus synthesis divided by the smallest
actual pool retains the 0.05 step ceiling. All ordinary ramp, gate, chemical,
fuel and strict stage-domain checks remain. No fresh initial-pool estimate
substitutes for this carried-state check.

The handoff seals the actual carried-pool amounts, increments, worst corner,
control and fractional rate. Replay recomputes that witness. Shape capacities,
field solver and declared max_steps/max_trace_bytes are retained. All eight
source/SIM recipe pairs retain their full 8 µs definitions and original quotas;
the source test checkpoint is one accepted 62.5 ns INIT step. Root's public
fixtures provide separate 1/2 ns interface probes while retaining full recipes.

The independent reference audits typed source arrays/padding, gates, accepted
clock/control indices, original ionic/chemical/ER/fuel anchors, full source
conservation, new controller operation and actual carried-domain admission.
It computes gross turnover by summing absolute rates of each real Na/K, PMCA,
ER and regeneration route, so opposing routes cannot cancel. Its 35-file import
closure contains no Cells/JAX imports. Production alone verifies opaque solver
factorization buffers against the exact original layout; independent checks
derive physical anchors and budgets from declared material and geometry.

The two unit files declare 140 cases: exact 35/39-array carry, original-anchor
material/charge/ER/fuel/work checks, full36/40-field stage comparisons, replay,
typed source/padding/history/anchor/clock refusals, capacity/owner refusals,
source-pool witness substitution, actual SIM prefix conservation and separate
two-step empty-SIM reduction to the static owner from the carried history.
Turnover and ionic-envelope boundary probes are explicitly isolated guard
tests; no other production guard is bypassed, and no full trajectory result
is implied. All numerical cases remain unexecuted by the worker.

Final static receipt: `host_checks/open_calcium_bath_epoch_f84cc0225dbbc140.json`
(SHA256 `3c95cc7a3e55fc9f5406ab44c40d83c060c71c7406c449345f73bcce7fe58d43`).
All ten Python files pass Ruff/AST; eight raw recipe metadata checks pass.
Ordinary bath production/reference/fixture files, existing phase helpers and
the immutable full8us02 bundle remain unchanged. Root's ordinary test-only
corrections and shared window-validation fix are separate work. No feature
edit is planned after this handoff unless qualification identifies a defect.
