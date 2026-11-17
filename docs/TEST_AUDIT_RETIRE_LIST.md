# Test audit: the retire list (D187)

**Status: approved by the user (D189), retired at 6ac27c38, tag `pre-retire-2026-11-16`** (at fa19d80c,
before any removal). Every retired test stays recoverable from the tag, and the frozen evidence (each
row's log) is kept (D187). Eight firm rows moved to held:
- seven before anything was deleted;
- one restored at 351d7b6b, after the gate showed a remaining test reads it by path.

They are listed below with their reasons. The tables after that section are the list as approved.

## As retired (D189)

D189's two checks ran first. Rows that failed one, and rows a remaining test needs, moved to held.
- **Check (a), a whole file that tests a module on the 42-coupling list.** 11 of the 15 firm tier-3
  files reach a coupling target, but only through other test modules' imports.
  - Four execute one and are held (below).
  - Seven import only comparison helpers (`exact`, `assert_states`, `evidence`), which execute no
    coupling target, and stay firm.
- **Check (b), a skipped case that the L4 block runs.** There is none. The block's scripts
  (`06-l4.sh`, `06-l4-c.sh`, `06-l4-p.sh` and their `l4-*.sh`) run four validation drivers and no
  tests.

| | Tier 3 | Tiers 1/2 |
| --- | --- | --- |
| Whole files retired | 11 (844 tests) | 40 |
| Cases retired | 23, in 4 files | 788, in 38 files |
| Saved per run | 5.5 core-hours per tier-3 run | 2.0 minutes per tier 1+2 gate |

Every retired case is a whole test function (219 functions). Each was identified per test ID: the tier-3
cases from the frozen record, and the tier-1/2 cases from one JUnit run of each file at fa19d80c, put in
the list's clusters on each message's first line, as the list counted them. Each file's count equals
the list's.

**Checks on the result:**
- The edited files' 1731 remaining tier-1/2 tests keep their outcomes per test ID.
- At the merged head c96eb080 the collected IDs are 18482: the 20792 before, minus exactly the 2322
  retired IDs, plus the 12 tests added since (one merged from fr45-next, nine from the BLAS pin, two
  for the tier tool).
- `tests/tier3_record.json` lost the retired files and IDs, and names D189 and the tag. Its 218 files'
  IDs equal the tree's.
- The evidence is in `/mnt/workspaces/Cells/test-audit-20261116-01/retire-fa19d80c/`.

**Moved to held, with the reasons:**

| File | Tier | Firm unit | Reason |
| --- | --- | --- | --- |
| unit/test_surface_calcium.py | 3 | file | Check (a): its `test_existing_resolved_kinetics_preserve_rates_and_energy` runs test_surface_kinetic's `test_independent_stage_rates_and_accounting`, which tests `cells.models.surface_kinetic`, a coupling target |
| unit/test_surface_calcium_channels.py | 3 | file | Check (a): it imports and so runs the same test (from test_surface_calcium) |
| unit/test_surface_calcium_hcn_full.py | 3 | file | Check (a): as test_surface_calcium_channels |
| unit/test_surface_calcium_sodium_full.py | 3 | file | Check (a): as test_surface_calcium_channels |
| unit/test_betse_junction_runtime.py | 1 | file | A remaining test depends on it: test_betse_charge_precision's two remaining tests use its `definition_arrays`, `common.evidence` and `BACKEND` |
| unit/test_betse_spatial_runtime.py | 1 | file | A remaining test depends on it, through test_betse_junction_runtime, which imports it |
| unit/test_cells_betse_compare.py | 1 | cases (3) | The 3 listed cases pass in a checkout with Git history (20 passed, 0 skipped at fa19d80c). They skip only in history-less snapshots, so they are not dead: the user's call |
| unit/test_voltage_gated_artifact_audit.py | 1 | file | A remaining test depends on it, by path: test_voltage_gated_dynamics' `test_shortened_synthetic_session_roundtrip_and_budget_receipt` copies the source files that `scripts/qualify_voltage_gated_reference.py` lists, this file among them. The gate found it (a FileNotFoundError), and the file was restored at 351d7b6b |

Regenerated at main a83d8f15 (16 November 2026), after today's lanes landed. Sources:
- the frozen tier-3 record, `tests/tier3_record.json`: D172's final tier-3 table per test ID, c1-3c10b833 (ab267c39's tests). At a83d8f15 its 229 files keep the same test IDs; tier 3 adds the four files F6's fix moved there;
- the tier record `tests/test_tiers.json` at a83d8f15; the chronic tier 1/2 skips and reds, with their reasons from D172's c1 tiers-1+2 logs (no chronic row changed since, but F6's four files left tiers 1/2);
- the legacy inventory at a83d8f15 (`scripts/legacy_inventory.py`): families, couplings and which families each test imports;
- the triage generator, its hand classification and every intermediate file: `/mnt/workspaces/Cells/test-audit-20261116-01/` (this list: `a83d8f15/triage/`).

Units: a whole file retires when it never completes within the 1800 s cap or nothing in it passes; otherwise only its failing or skipping cases retire and the file's time stays. Savings count whole files only, since per-test times are not recorded.

## Firm totals, before and after

| | Tier 3 files (whole) | Tier 3 tests in whole files, cases | Core-hours saved per tier-3 run | Tiers 1/2 files (whole) | Tiers 1/2 cases | Minutes saved per tier 1+2 gate |
| --- | --- | --- | --- | --- | --- | --- |
| Before, at 27e7aa16 | 19 (15) | 1185, 23 | 7.5 | 82 (43) | 1591 | 2.1 |
| After, at a83d8f15 | 19 (15) | 1185, 23 | 7.5 | 82 (43) | 1591 | 2.1 |

## Green at a83d8f15: none of these is on the retire list

core-fixes (merged at d2fabb6a) closed findings F1, F3 and F6. None of the now-green files was on the firm list before, so nothing was taken off it. They are kept out of the candidates too: they carry the fixes' regression checks.

| File | Finding | Where it is now | Evidence (under `/mnt/workspaces/Cells/core-fixes-20261116/`) |
| --- | --- | --- | --- |
| unit/test_gated_calcium.py | F6 | tier 3 since the record | logs/recheck-998c3cdb-f6a.log: with test_plasma_calcium, 85 passed, 2 skipped |
| unit/test_ip3_calcium.py | F6 | tier 3 since the record | logs/recheck-998c3cdb-f6b.log: with test_tissue_calcium, 67 passed, 2 skipped (also logs/recheck-67432203-f6b.log) |
| unit/test_plasma_calcium.py | F6 | tier 3 since the record | logs/recheck-998c3cdb-f6a.log: with test_gated_calcium, 85 passed, 2 skipped (also logs/recheck-67432203-f6a-2.log) |
| unit/test_surface_excision.py | F3 | in the record (tier 3) | 43 of 43 (PROGRESS at a83d8f15): logs/excision-9637cb77.log 42 passed, its one failure (test_offline_sixteen_gpu_plan_preserves_cut_epoch_and_source) passes alone in logs/excision-gpuplan-9637cb77.log; the two unsolvable cuts pass in the f1 groups |
| unit/test_surface_kinetic.py | F1 | in the record (tier 3) | logs/recheck-67432203-f1.log (38 passed) and logs/recheck-998c3cdb-f1-admission.log (68 passed): tools/recheck.sh's f1 and tools/recheck2.sh's f1-admission groups run every test_inconsistent_definitions_are_rejected case of this file, [anchor] included |
| unit/test_surface_tissue.py | F1 | in the record (tier 3) | as test_surface_kinetic (the same two groups run this file's test_inconsistent_definitions_are_rejected cases) |
| unit/test_tissue_calcium.py | F6 | tier 3 since the record | logs/recheck-998c3cdb-f6b.log: with test_ip3_calcium, 67 passed, 2 skipped |

**Firm.** Tier 3: 19 files (15 whole, 1185 tests; the failing cases of the rest, 23 cases), 7.5 core-hours saved per tier-3 run. Tiers 1/2: 82 files (43 whole; 1591 cases in all), 2.1 minutes saved per tier 1+2 gate. Savings count whole files only: per-test times are not recorded.

**Held.** Tier 3: 2 files (1 whole, 13 tests; the failing cases of the rest, 14 cases), 0.5 core-hours saved per tier-3 run. Tiers 1/2: 8 files (5 whole; 60 cases in all), 0.2 minutes saved per tier 1+2 gate. Savings count whole files only: per-test times are not recorded.

Evidence paths are under `/mnt/workspaces/Cells/d172-restructure-20261115-01/endgame/c1-3c10b833/`.

## Firm: tier 3

| File | Kind | Unit | Tests | s saved per run | Family class | Reason | Alternative | Hold | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| betse_physiology/integration/test_physiology_initial_loop.py | cannot run here | cases | 8 | 0.0 | none | needs CELLS_BETSE_SOURCE, the BETSE source tree its static-site reference reads; the tier harness never sets it, so 8 of 24 tests cannot run here | the harness exports CELLS_BETSE_SOURCE from venv-betse's installed package; or retire the 8 cases with the file's BETSE physiology line |  | `tiers-3/logs/tests__betse_physiology__integration__test_physiology_initial_loop.py.log` |
| betse_physiology/integration/test_physiology_protein_batch_loop.py | chronic timeout, no registry family | file | 79 | 1800.01 | none | times out at the 1800 s cap: 19 of 79 tests reached (c1-10) | split below the cap, or retire with the BETSE physiology line |  | `tiers-3-attrib/c1-10/logs/tests__betse_physiology__integration__test_physiology_protein_batch_loop.py.log` |
| betse_physiology/unit/test_physiology_initial_preparation.py | cannot run here | cases | 12 | 0.0 | none | needs CELLS_BETSE_SOURCE (as above); 12 of 38 cannot run here | as test_physiology_initial_loop |  | `tiers-3/logs/tests__betse_physiology__unit__test_physiology_initial_preparation.py.log` |
| integration/test_joint_water_profile_barrier_phase_cli.py | chronic timeout in a frozen family | file | 10 | 1800.03 | legacy | times out at the 1800 s cap: 9 of 10 tests reached (c1-9) |  |  | `tiers-3-attrib/c1-9/logs/tests__integration__test_joint_water_profile_barrier_phase_cli.py.log` |
| unit/test_joint_water_profile_barriers.py | chronic timeout in a frozen family | file | 133 | 1800.04 | legacy | times out at the 1800 s cap: 39 of 133 tests reached (c1-38) |  |  | `tiers-3-attrib/c1-38/logs/tests__unit__test_joint_water_profile_barriers.py.log` |
| unit/test_owned_calcium_profile_phase_handoff.py | chronic timeout in a frozen family | file | 62 | 1800.02 | legacy | times out at the 1800 s cap: 45 of 62 tests reached (c1-23) |  |  | `tiers-3-attrib/c1-23/logs/tests__unit__test_owned_calcium_profile_phase_handoff.py.log` |
| unit/test_surface_calcium.py | chronic timeout in a frozen family | file | 82 | 1800.91 | legacy | times out at the 1800 s cap: 79 of 82 tests reached (c1-57) |  |  | `tiers-3-attrib/c1-57/logs/tests__unit__test_surface_calcium.py.log` |
| unit/test_surface_calcium_cav_full.py | chronic timeout in a frozen family | file | 87 | 1800.67 | legacy | times out at the 1800 s cap: 72 of 87 tests reached (c1-35) |  |  | `tiers-3-attrib/c1-35/logs/tests__unit__test_surface_calcium_cav_full.py.log` |
| unit/test_surface_calcium_channels.py | chronic timeout in a frozen family | file | 90 | 1800.9 | legacy | times out at the 1800 s cap: 83 of 90 tests reached (c1-54) |  |  | `tiers-3-attrib/c1-54/logs/tests__unit__test_surface_calcium_channels.py.log` |
| unit/test_surface_calcium_energy_mitochondria_excision.py | chronic timeout in a frozen family | file | 123 | 1800.02 | legacy | times out at the 1800 s cap: 51 of 123 tests reached (c1-25) |  |  | `tiers-3-attrib/c1-25/logs/tests__unit__test_surface_calcium_energy_mitochondria_excision.py.log` |
| unit/test_surface_calcium_energy_regulated.py | test of retired code | cases | 1 | 0.0 | legacy | a frozen-source identity test reading src/cells/processes/betse_network_modulation.py, removed on 8 November with the BETSE-specific code (tag native-betse-frozen-2026-11-08): a test of retired code |  |  | `tiers-3-resume1/logs/tests__unit__test_surface_calcium_energy_regulated.py.log` |
| unit/test_surface_calcium_energy_regulated_v2_excision_full_schedule.py | test of retired code | cases | 2 | 0.0 | legacy | its frozen 29 October external reference names the pre-8-November law finite_atp_er_1ca_betse_positive@1; the law was renamed in the neutral sweep, so the reference no longer parses (ConfigError: finite calcium pumps require their explicit finite-pool law) | refreeze the reference through the rename map, or retire with the frozen family |  | `tiers-3-resume1/logs/tests__unit__test_surface_calcium_energy_regulated_v2_excision_full_schedule.py.log` |
| unit/test_surface_calcium_energy_transport_excision.py | chronic timeout in a frozen family | file | 99 | 1800.26 | legacy | times out at the 1800 s cap: 94 of 99 tests reached (c1-50) |  |  | `tiers-3-attrib/c1-50/logs/tests__unit__test_surface_calcium_energy_transport_excision.py.log` |
| unit/test_surface_calcium_energy_water_excision.py | chronic timeout in a frozen family | file | 106 | 1800.1 | legacy | times out at the 1800 s cap: 101 of 106 tests reached (c1-52) |  |  | `tiers-3-attrib/c1-52/logs/tests__unit__test_surface_calcium_energy_water_excision.py.log` |
| unit/test_surface_calcium_hcn_full.py | chronic timeout in a frozen family | file | 85 | 1800.79 | legacy | times out at the 1800 s cap: 73 of 85 tests reached (c1-29) |  |  | `tiers-3-attrib/c1-29/logs/tests__unit__test_surface_calcium_hcn_full.py.log` |
| unit/test_surface_calcium_kv1_full.py | chronic timeout in a frozen family | file | 86 | 1800.73 | legacy | times out at the 1800 s cap: 72 of 86 tests reached (c1-43) |  |  | `tiers-3-attrib/c1-43/logs/tests__unit__test_surface_calcium_kv1_full.py.log` |
| unit/test_surface_calcium_sodium_full.py | chronic timeout in a frozen family | file | 84 | 1800.92 | legacy | times out at the 1800 s cap: 74 of 84 tests reached (c1-46) |  |  | `tiers-3-attrib/c1-46/logs/tests__unit__test_surface_calcium_sodium_full.py.log` |
| unit/test_surface_mobile_pump_repair.py | chronic timeout in a frozen family | file | 45 | 1800.41 | legacy | times out at the 1800 s cap: 43 of 45 tests reached (c1-33) |  |  | `tiers-3-attrib/c1-33/logs/tests__unit__test_surface_mobile_pump_repair.py.log` |
| unit/test_surface_repair_recovery.py | chronic timeout in a frozen family | file | 14 | 1800.3 | legacy | times out at the 1800 s cap: 10 of 14 tests reached (c1-31) |  |  | `tiers-3-attrib/c1-31/logs/tests__unit__test_surface_repair_recovery.py.log` |

## Firm: tiers 1 and 2

| File | Tier | Unit | Cases | File s | Family class | Reason | Hold | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| betse_physiology/unit/test_native_noise.py | 1 | cases | 42 | 13.21 | none | run only by a bounded external wrapper that supplies native captures; in every tier run they skip |  | `tiers-1+2/logs/tests__betse_physiology__unit__test_native_noise.py.log` |
| unit/test_betse_charge_precision.py | 1 | cases | 18 | 3.38 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_betse_charge_precision.py.log` |
| unit/test_betse_ecm_material_callback.py | 1 | file | 10 | 0.57 | none | tests of the BETSE-specific code removed on 8 November (tag native-betse-frozen-2026-11-08) |  | `tiers-1+2/logs/tests__unit__test_betse_ecm_material_callback.py.log` |
| unit/test_betse_environment_transport.py | 1 | cases | 46 | 9.92 | none | run only by a bounded external wrapper that supplies native captures; in every tier run they skip |  | `tiers-1+2/logs/tests__unit__test_betse_environment_transport.py.log` |
| unit/test_betse_geometry.py | 1 | file | 66 | 1.84 | none | run only by a bounded external wrapper that supplies native captures; in every tier run they skip |  | `tiers-1+2/logs/tests__unit__test_betse_geometry.py.log` |
| unit/test_betse_junction_runtime.py | 1 | file | 72 | 3.64 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_betse_junction_runtime.py.log` |
| unit/test_betse_mixed_interventions.py | 1 | file | 30 | 4.54 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_betse_mixed_interventions.py.log` |
| unit/test_betse_spatial_intervention_refinement.py | 1 | file | 64 | 3.7 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_betse_spatial_intervention_refinement.py.log` |
| unit/test_betse_spatial_interventions.py | 1 | file | 38 | 3.17 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_betse_spatial_interventions.py.log` |
| unit/test_betse_spatial_runtime.py | 1 | file | 46 | 2.97 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_betse_spatial_runtime.py.log` |
| unit/test_betse_tissue_profiles.py | 1 | cases | 64 | 6.68 | none | run only by a bounded external wrapper that supplies native captures; in every tier run they skip |  | `tiers-1+2/logs/tests__unit__test_betse_tissue_profiles.py.log` |
| unit/test_cell_zone_transport.py | 1 | cases | 40 | 8.5 | none | run only by a bounded external wrapper that supplies native captures; in every tier run they skip |  | `tiers-1+2/logs/tests__unit__test_cell_zone_transport.py.log` |
| unit/test_cells_betse_compare.py | 1 | cases | 3 | 1.98 | none | needs a comparator commit absent from this history |  | `tiers-1+2/logs/tests__unit__test_cells_betse_compare.py.log` |
| unit/test_channel_compensation.py | 1 | file | 54 | 5.49 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_channel_compensation.py.log` |
| unit/test_cue_separation.py | 1 | file | 13 | 3.32 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_cue_separation.py.log` |
| unit/test_distributed_cue.py | 1 | file | 8 | 3.37 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_distributed_cue.py.log` |
| unit/test_distributed_timing.py | 1 | file | 12 | 4.6 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_distributed_timing.py.log` |
| unit/test_finite_extracellular_artifact_audit.py | 1 | cases | 12 | 0.57 | none | need an optional immutable September reference session that no frozen tree holds |  | `tiers-1+2/logs/tests__unit__test_finite_extracellular_artifact_audit.py.log` |
| unit/test_finite_extracellular_artifact_audit_v2.py | 1 | cases | 1 | 0.72 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_finite_extracellular_artifact_audit_v2.py.log` |
| unit/test_finite_extracellular_attempt_audit.py | 1 | cases | 7 | 0.62 | none | needs a retained September attempt that no frozen tree holds |  | `tiers-1+2/logs/tests__unit__test_finite_extracellular_attempt_audit.py.log` |
| unit/test_finite_extracellular_build_audit.py | 1 | file | 1 | 1.67 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_finite_extracellular_build_audit.py.log` |
| unit/test_finite_extracellular_dynamics.py | 1 | cases | 75 | 6.98 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_finite_extracellular_dynamics.py.log` |
| unit/test_finite_extracellular_ownership.py | 1 | file | 6 | 1.92 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_finite_extracellular_ownership.py.log` |
| unit/test_finite_extracellular_production_context.py | 1 | cases | 4 | 0.72 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_finite_extracellular_production_context.py.log` |
| unit/test_finite_extracellular_reference.py | 1 | cases | 1 | 1.07 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_finite_extracellular_reference.py.log` |
| unit/test_finite_extracellular_tangent.py | 1 | cases | 37 | 2.52 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_finite_extracellular_tangent.py.log` |
| unit/test_finite_extracellular_test_context.py | 1 | cases | 3 | 0.82 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_finite_extracellular_test_context.py.log` |
| unit/test_graph_candidate.py | 1 | cases | 7 | 6.63 | none | assert the CPU affinity of their original candidate runs; read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_graph_candidate.py.log` |
| unit/test_graph_diagnostics.py | 1 | cases | 2 | 9.28 | none | assert the CPU affinity of their original candidate runs; read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_graph_diagnostics.py.log` |
| unit/test_graph_evidence.py | 1 | cases | 2 | 10.38 | none | assert the CPU affinity of their original candidate runs; read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_graph_evidence.py.log` |
| unit/test_graph_reference_panel.py | 1 | cases | 23 | 3.93 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_graph_reference_panel.py.log` |
| unit/test_graph_refinement.py | 1 | cases | 21 | 2.73 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_graph_refinement.py.log` |
| unit/test_hcn_extra_reference.py | 1 | cases | 55 | 0.72 | none | as the bounded-wrapper skips |  | `tiers-1+2/logs/tests__unit__test_hcn_extra_reference.py.log` |
| unit/test_joint_water_epoch_reference_refinement.py | 1 | file | 6 | 1.8 | none | need an explicit external bundle (an environment variable or a frozen evidence root) the tier harness never supplies |  | `tiers-1+2/logs/tests__unit__test_joint_water_epoch_reference_refinement.py.log` |
| unit/test_joint_water_epoch_reference_refinement_contracts.py | 1 | cases | 5 | 1.87 | none | need an explicit external bundle (an environment variable or a frozen evidence root) the tier harness never supplies |  | `tiers-1+2/logs/tests__unit__test_joint_water_epoch_reference_refinement_contracts.py.log` |
| unit/test_joint_water_epoch_transients.py | 1 | file | 6 | 2.73 | legacy | need an explicit external bundle (an environment variable or a frozen evidence root) the tier harness never supplies |  | `tiers-1+2/logs/tests__unit__test_joint_water_epoch_transients.py.log` |
| unit/test_kinetic_finite_legacy.py | 1 | file | 1 | 0.57 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_kinetic_finite_legacy.py.log` |
| unit/test_local_channel.py | 1 | file | 90 | 3.77 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_local_channel.py.log` |
| unit/test_long_observation.py | 1 | file | 12 | 3.33 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_long_observation.py.log` |
| unit/test_multispecies_artifact_audit.py | 1 | file | 4 | 0.73 | none | need an optional immutable September reference session that no frozen tree holds |  | `tiers-1+2/logs/tests__unit__test_multispecies_artifact_audit.py.log` |
| unit/test_multispecies_build_audit.py | 1 | cases | 8 | 9.25 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_multispecies_build_audit.py.log` |
| unit/test_native_mapping_setup_diagnostic.py | 1 | cases | 3 | 0.92 | none | tests of the BETSE-specific code removed on 8 November (tag native-betse-frozen-2026-11-08) |  | `tiers-1+2/logs/tests__unit__test_native_mapping_setup_diagnostic.py.log` |
| unit/test_network_control.py | 1 | cases | 54 | 13.02 | none | run only by a bounded external wrapper that supplies native captures; in every tier run they skip |  | `tiers-1+2/logs/tests__unit__test_network_control.py.log` |
| unit/test_owned_barrier_transients.py | 1 | file | 6 | 1.72 | none | need an explicit external bundle (an environment variable or a frozen evidence root) the tier harness never supplies |  | `tiers-1+2/logs/tests__unit__test_owned_barrier_transients.py.log` |
| unit/test_physical_ionic_graph_artifact_audit.py | 1 | cases | 10 | 0.82 | none | need an optional immutable September reference session that no frozen tree holds |  | `tiers-1+2/logs/tests__unit__test_physical_ionic_graph_artifact_audit.py.log` |
| unit/test_physical_ionic_graph_build_audit.py | 1 | file | 1 | 2.58 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_physical_ionic_graph_build_audit.py.log` |
| unit/test_physical_ionic_graph_dynamics.py | 1 | cases | 86 | 8.14 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_physical_ionic_graph_dynamics.py.log` |
| unit/test_physical_ionic_graph_reference.py | 1 | cases | 1 | 1.92 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_physical_ionic_graph_reference.py.log` |
| unit/test_source_graph_continuation.py | 1 | cases | 19 | 3.23 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_source_graph_continuation.py.log` |
| unit/test_source_graph_paths.py | 1 | cases | 34 | 4.34 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_source_graph_paths.py.log` |
| unit/test_source_order.py | 1 | file | 15 | 4.07 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_source_order.py.log` |
| unit/test_source_order_coupling_transfer.py | 1 | file | 38 | 5.29 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_source_order_coupling_transfer.py.log` |
| unit/test_source_order_long.py | 1 | file | 15 | 3.52 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_source_order_long.py.log` |
| unit/test_source_order_precision.py | 1 | file | 15 | 3.37 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_source_order_precision.py.log` |
| unit/test_source_order_pulse_confirmation.py | 1 | file | 17 | 3.52 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_source_order_pulse_confirmation.py.log` |
| unit/test_source_order_pulse_spacing.py | 1 | file | 17 | 3.47 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_source_order_pulse_spacing.py.log` |
| unit/test_source_order_selected.py | 1 | file | 17 | 3.42 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_source_order_selected.py.log` |
| unit/test_source_order_spanning.py | 1 | file | 16 | 3.48 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_source_order_spanning.py.log` |
| unit/test_source_preparations.py | 1 | cases | 1 | 6.98 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_source_preparations.py.log` |
| unit/test_spatial_extracellular_acceptance_resources.py | 1 | cases | 3 | 6.63 | none | frozen-evidence identity checks of September protocols whose evidence is not in the tree; read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_spatial_extracellular_acceptance_resources.py.log` |
| unit/test_spatial_extracellular_artifact_audit.py | 1 | file | 1 | 1.67 | none | frozen-evidence identity checks of September protocols whose evidence is not in the tree |  | `tiers-1+2/logs/tests__unit__test_spatial_extracellular_artifact_audit.py.log` |
| unit/test_spatial_extracellular_build_audit.py | 1 | file | 1 | 2.37 | legacy | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_spatial_extracellular_build_audit.py.log` |
| unit/test_spatial_extracellular_context.py | 1 | cases | 1 | 1.87 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_spatial_extracellular_context.py.log` |
| unit/test_spatial_extracellular_dynamics.py | 1 | file | 1 | 1.27 | none | frozen-evidence identity checks of September protocols whose evidence is not in the tree |  | `tiers-1+2/logs/tests__unit__test_spatial_extracellular_dynamics.py.log` |
| unit/test_spatial_extracellular_execution.py | 1 | file | 1 | 1.72 | legacy | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_spatial_extracellular_execution.py.log` |
| unit/test_spatial_extracellular_production.py | 1 | file | 1 | 2.43 | legacy | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_spatial_extracellular_production.py.log` |
| unit/test_spatial_extracellular_stream_audit.py | 1 | file | 1 | 2.48 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_spatial_extracellular_stream_audit.py.log` |
| unit/test_stable_seed_control_volume_environment.py | 1 | file | 8 | 1.12 | none | need an explicit external bundle (an environment variable or a frozen evidence root) the tier harness never supplies |  | `tiers-1+2/logs/tests__unit__test_stable_seed_control_volume_environment.py.log` |
| unit/test_stable_seed_control_volume_physical_bridge.py | 1 | file | 10 | 1.17 | none | need an explicit external bundle (an environment variable or a frozen evidence root) the tier harness never supplies |  | `tiers-1+2/logs/tests__unit__test_stable_seed_control_volume_physical_bridge.py.log` |
| unit/test_tissue_profile_preparation.py | 1 | cases | 2 | 11.06 | none | need an explicit external bundle (an environment variable or a frozen evidence root) the tier harness never supplies; tests of the BETSE-specific code removed on 8 November (tag native-betse-frozen-2026-11-08) |  | `tiers-1+2/logs/tests__unit__test_tissue_profile_preparation.py.log` |
| unit/test_tissue_removal.py | 1 | cases | 45 | 1.62 | none | run only by a bounded external wrapper that supplies native captures; in every tier run they skip |  | `tiers-1+2/logs/tests__unit__test_tissue_removal.py.log` |
| unit/test_two_task_readout.py | 1 | file | 15 | 3.93 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_two_task_readout.py.log` |
| unit/test_two_task_templates.py | 1 | file | 18 | 4.33 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_two_task_templates.py.log` |
| unit/test_two_task_timing_refinement.py | 1 | file | 15 | 4.29 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_two_task_timing_refinement.py.log` |
| unit/test_unstimulated_readout.py | 1 | file | 10 | 3.73 | none | tests of retired code: D131's BETSE-order model left the registry, so every test skips ('awaits re-hosting'); a skipped test cannot fail (D187 rule 3) |  | `tiers-1+2/logs/tests__unit__test_unstimulated_readout.py.log` |
| unit/test_voltage_gated_artifact_audit.py | 1 | file | 7 | 0.57 | none | need an optional immutable September reference session that no frozen tree holds |  | `tiers-1+2/logs/tests__unit__test_voltage_gated_artifact_audit.py.log` |
| unit/test_voltage_gated_build_audit.py | 1 | file | 15 | 8.64 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_voltage_gated_build_audit.py.log` |
| unit/test_voltage_gated_channel_reference.py | 1 | cases | 1 | 1.07 | none | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_voltage_gated_channel_reference.py.log` |
| unit/test_comparison_evidence.py | 2 | cases | 2 | 49.72 | none | assert the CPU affinity of their original candidate runs; read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_comparison_evidence.py.log` |
| unit/test_graph_evaluation.py | 2 | cases | 2 | 59.53 | none | assert the CPU affinity of their original candidate runs; read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here |  | `tiers-1+2/logs/tests__unit__test_graph_evaluation.py.log` |
| unit/test_network_reactions.py | 2 | cases | 50 | 20.42 | none | run only by a bounded external wrapper that supplies native captures; in every tier run they skip |  | `tiers-1+2/logs/tests__unit__test_network_reactions.py.log` |
| unit/test_surface_calcium_energy_regulated_v2.py | 2 | cases | 1 | 45.9 | legacy | tests of the BETSE-specific code removed on 8 November (tag native-betse-frozen-2026-11-08) |  | `tiers-1+2/logs/tests__unit__test_surface_calcium_energy_regulated_v2.py.log` |

## Held: tier 3

| File | Kind | Unit | Tests | s saved per run | Family class | Reason | Alternative | Hold | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unit/test_assembly_repair_recovery.py | chronic timeout in a frozen family | file | 13 | 1800.12 | legacy | times out at the 1800 s cap: 6 of 13 tests reached (c1-11) |  | its subject is the assembly package (cells.assembly*), not the model it imports | `tiers-3-attrib/c1-11/logs/tests__unit__test_assembly_repair_recovery.py.log` |
| unit/test_voltage_gated_membrane.py | cannot run here | cases | 14 | 0.0 | legacy | reads untracked reference data, runs/num-007-2026-09-09, which no frozen tree holds: 14 of its tests cannot run here |  | the active path imports these families' modules today (specs:MultispeciesSpec: 1 couplings): hold until they are resolved | `tiers-3-resume1/logs/tests__unit__test_voltage_gated_membrane.py.log` |

## Held: tiers 1 and 2

| File | Tier | Unit | Cases | File s | Family class | Reason | Hold | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unit/test_finite_extracellular_production.py | 1 | file | 1 | 1.72 | legacy | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here | the active path imports these families' modules today (specs:FiniteExtracellularSpec: 1, specs:MultispeciesSpec: 1 couplings): hold until they are resolved | `tiers-1+2/logs/tests__unit__test_finite_extracellular_production.py.log` |
| unit/test_kinetic_finite_dynamics.py | 1 | file | 1 | 1.67 | legacy | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here | the active path imports these families' modules today (specs:FiniteExtracellularSpec: 1, specs:KineticFiniteExtracellularSpec: 2 couplings): hold until they are resolved | `tiers-1+2/logs/tests__unit__test_kinetic_finite_dynamics.py.log` |
| unit/test_kinetic_finite_runner.py | 1 | file | 1 | 1.67 | legacy | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here | the active path imports these families' modules today (specs:KineticFiniteExtracellularSpec: 2 couplings): hold until they are resolved | `tiers-1+2/logs/tests__unit__test_kinetic_finite_runner.py.log` |
| unit/test_kinetic_finite_schema.py | 1 | file | 1 | 1.62 | legacy | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here | the active path imports these families' modules today (specs:FiniteExtracellularSpec: 1, specs:KineticFiniteExtracellularSpec: 2 couplings): hold until they are resolved | `tiers-1+2/logs/tests__unit__test_kinetic_finite_schema.py.log` |
| unit/test_physical_ionic_graph.py | 1 | file | 1 | 2.77 | legacy | read untracked September evidence (runs/ and reports/) that no frozen tree holds: they cannot run here | the active path imports these families' modules today (specs:MultispeciesSpec: 1, specs:PhysicalIonicGraphSpec: 1 couplings): hold until they are resolved | `tiers-1+2/logs/tests__unit__test_physical_ionic_graph.py.log` |
| unit/test_stable_seed_partition_advance.py | 1 | cases | 6 | 0.78 | legacy | need an explicit external bundle (an environment variable or a frozen evidence root) the tier harness never supplies | the active path imports these families' modules today (surface_tissue_spec: 8 couplings): hold until they are resolved | `tiers-1+2/logs/tests__unit__test_stable_seed_partition_advance.py.log` |
| unit/test_stable_seed_partition_advance_refinement.py | 1 | cases | 13 | 0.92 | legacy | need an explicit external bundle (an environment variable or a frozen evidence root) the tier harness never supplies | the active path imports these families' modules today (surface_tissue_spec: 8 couplings): hold until they are resolved | `tiers-1+2/logs/tests__unit__test_stable_seed_partition_advance_refinement.py.log` |
| unit/test_stable_seed_partition_trajectory.py | 1 | cases | 36 | 1.98 | legacy | need an explicit external bundle (an environment variable or a frozen evidence root) the tier harness never supplies | the active path imports these families' modules today (surface_tissue_spec: 8 couplings): hold until they are resolved | `tiers-1+2/logs/tests__unit__test_stable_seed_partition_trajectory.py.log` |

## Candidates, the user's call: passing tier-3 files of frozen families

tier-3 files that pass and test only frozen (legacy) families: D187 includes tests of frozen older families among those retired when they do not earn their cost; listed apart, the user's call.

91 files, 10.65 core-hours per tier-3 run; 26 of them (2.82 core-hours) are held by a coupling or the assembly subject.

| File | Tests | s | Families | Hold |
| --- | --- | --- | --- | --- |
| betse_physiology/unit/test_physiology_active_temperature.py | 50 | 89.49 | core.surface_calcium_energy_spec |  |
| integration/test_active_profile_barrier_phase_cli.py | 5 | 590.88 | core.surface_active_profile_barrier_epoch_spec, core.surface_active_profile_barrier_interventions_spec |  |
| integration/test_active_tissue_phase_cli.py | 8 | 238.94 | core.surface_active_profile_epoch_spec, core.surface_active_profile_interventions_spec |  |
| integration/test_joint_water_barrier_phase_cli.py | 8 | 752.75 | core.surface_calcium_energy_water_barrier_interventions_spec, core.surface_calcium_energy_water_repair_barrier_intervent |  |
| integration/test_joint_water_hcn_interfaces.py | 17 | 568.9 | core.surface_calcium_energy_spec |  |
| integration/test_owned_barrier_phase_cli.py | 15 | 701.21 | core.surface_active_barrier_epoch_spec, core.surface_active_barrier_interventions_spec, core.surface_calcium_barrier_epo |  |
| integration/test_owned_calcium_profile_barrier_phase_cli.py | 10 | 1669.87 | core.surface_calcium_energy_profile_barrier_epoch_spec, core.surface_calcium_energy_profile_barrier_interventions_spec,  |  |
| integration/test_owned_calcium_tissue_phase_cli.py | 18 | 488.04 | core.surface_calcium_energy_profile_epoch_spec, core.surface_calcium_profile_epoch_spec |  |
| integration/test_surface_bath_phase_public.py | 14 | 251.77 | core.surface_active_bath_events_spec, core.surface_passive_bath_events_spec |  |
| integration/test_surface_calcium_energy_atp_transport_excision_public.py | 4 | 362.21 | core.surface_calcium_energy_atp_transport_excision_spec, core.surface_calcium_energy_atp_transport_spec |  |
| integration/test_surface_calcium_energy_atp_transport_public.py | 4 | 183.23 | core.surface_calcium_energy_atp_transport_spec, core.surface_calcium_energy_transport_spec |  |
| integration/test_surface_calcium_energy_irreversible_transport_public.py | 4 | 123.72 | core.surface_calcium_energy_irreversible_transport_spec, core.surface_calcium_energy_transport_spec |  |
| unit/test_active_membrane_profile_phase_handoff.py | 36 | 433.43 | core.surface_active_profile_epoch_spec, core.surface_active_profile_interventions_spec |  |
| unit/test_active_profile_barrier_interventions.py | 51 | 298.07 | core.surface_active_profile_barrier_interventions_spec |  |
| unit/test_active_profile_barrier_interventions_dispatch.py | 6 | 69.95 | core.surface_active_profile_barrier_interventions_spec |  |
| unit/test_active_profile_barrier_phase_handoff.py | 16 | 118.25 | core.surface_active_profile_barrier_epoch_spec, core.surface_active_profile_barrier_interventions_spec |  |
| unit/test_assembly_mobile_repair.py | 35 | 1093.67 | core.surface_mobile_repair_spec | its subject is the assembly package (cells.assembly*), not the model it imports |
| unit/test_assembly_repair.py | 9 | 285.12 | core.surface_repair_spec | its subject is the assembly package (cells.assembly*), not the model it imports |
| unit/test_batch.py | 43 | 110.71 | core.specs:ModelSpec |  |
| unit/test_bioelectric_cell.py | 100 | 72.97 | core.specs:BioelectricSpec | the active path imports these families' modules today (specs:BioelectricSpec: 1 couplings): hold until they are resolved |
| unit/test_bioelectric_pair.py | 127 | 160.34 | core.specs:BioelectricPairSpec |  |
| unit/test_calcium_activated_catalog.py | 94 | 431.7 | core.surface_calcium_energy_spec, core.surface_calcium_spec, core.surface_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_channel_catalog_v2.py | 78 | 410.98 | core.surface_calcium_energy_spec, core.surface_calcium_spec, core.surface_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_environment_barrier_interventions.py | 62 | 51.52 | core.environment_barrier_interventions_spec, core.surface_tissue_spec | the active path imports these families' modules today (surface_tissue_spec: 8 couplings): hold until they are resolved |
| unit/test_er_calcium.py | 30 | 61.53 | core.er_spec |  |
| unit/test_field_floor.py | 10 | 222.41 | core.surface_tissue_spec | the active path imports these families' modules today (surface_tissue_spec: 8 couplings): hold until they are resolved |
| unit/test_finite_ecm_polygon_preparation.py | 78 | 92.38 | core.surface_tissue_spec | the active path imports these families' modules today (surface_tissue_spec: 8 couplings): hold until they are resolved |
| unit/test_hcn_extra_catalog.py | 106 | 458.6 | core.surface_calcium_spec, core.surface_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_joint_water_barrier_interventions.py | 63 | 341.39 | core.surface_calcium_energy_spec, core.surface_calcium_energy_water_hcn_extra_spec, core.surface_calcium_energy_water_re |  |
| unit/test_joint_water_barrier_interventions_dispatch.py | 12 | 149.71 | core.surface_calcium_energy_water_barrier_interventions_spec, core.surface_calcium_energy_water_repair_barrier_intervent |  |
| unit/test_joint_water_barrier_phase_handoff.py | 32 | 130.3 | core.surface_calcium_energy_water_barrier_interventions_spec, core.surface_calcium_energy_water_repair_barrier_intervent |  |
| unit/test_joint_water_profile_barrier_interventions_dispatch.py | 12 | 454.05 | core.surface_calcium_energy_water_profile_barrier_interventions_spec, core.surface_calcium_energy_water_repair_profile_b |  |
| unit/test_joint_water_profile_barrier_phase_handoff.py | 32 | 721.75 | core.surface_calcium_energy_spec, core.surface_calcium_energy_water_profile_barrier_epoch_spec, core.surface_calcium_ene |  |
| unit/test_joint_water_profile_barrier_phase_reference.py | 37 | 216.46 | core.surface_calcium_energy_water_profile_barrier_epoch_spec, core.surface_calcium_energy_water_profile_barrier_interven |  |
| unit/test_joint_water_profile_barrier_phase_turnover.py | 22 | 302.2 | core.surface_calcium_energy_water_profile_barrier_epoch_spec, core.surface_calcium_energy_water_profile_barrier_interven |  |
| unit/test_morris_lecar_catalog.py | 103 | 482.55 | core.surface_calcium_energy_spec, core.surface_calcium_spec, core.surface_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_morris_lecar_energy_water.py | 94 | 398.79 | core.surface_energy_spec, core.surface_energy_water_spec |  |
| unit/test_morris_lecar_repair_compiled.py | 2 | 286.71 | core.surface_repair_spec |  |
| unit/test_morris_lecar_water.py | 75 | 163.98 | core.surface_kinetic_spec, core.surface_water_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_multispecies_membrane.py | 108 | 66.78 | core.specs:BioelectricSpec, core.specs:MultispeciesSpec | the active path imports these families' modules today (specs:BioelectricSpec: 1, specs:MultispeciesSpec: 1 couplings): hold until they are resolved |
| unit/test_open_calcium_bath_events.py | 58 | 130.4 | core.surface_open_calcium_bath_events_spec, core.surface_open_calcium_energy_bath_events_spec |  |
| unit/test_owned_barrier_interventions_dispatch.py | 15 | 76.07 | core.surface_active_barrier_interventions_spec, core.surface_calcium_barrier_interventions_spec, core.surface_calcium_en |  |
| unit/test_owned_barrier_phase_handoff.py | 54 | 161.6 | core.surface_active_barrier_epoch_spec, core.surface_active_barrier_interventions_spec, core.surface_calcium_barrier_epo |  |
| unit/test_owned_calcium_profile_barrier_interventions_dispatch.py | 12 | 230.84 | core.surface_calcium_energy_profile_barrier_interventions_spec, core.surface_calcium_profile_barrier_interventions_spec |  |
| unit/test_owned_calcium_profile_barrier_phase_handoff.py | 32 | 456.22 | core.surface_calcium_energy_profile_barrier_epoch_spec, core.surface_calcium_energy_profile_barrier_interventions_spec,  |  |
| unit/test_owned_calcium_profile_barrier_phase_reference.py | 33 | 119.74 | core.surface_calcium_energy_profile_barrier_epoch_spec, core.surface_calcium_energy_profile_barrier_interventions_spec,  |  |
| unit/test_owned_calcium_profile_barrier_phase_turnover.py | 10 | 117.87 | core.surface_calcium_energy_profile_barrier_epoch_spec, core.surface_calcium_energy_profile_barrier_interventions_spec,  |  |
| unit/test_owned_calcium_profile_barriers.py | 90 | 1352.79 | core.surface_calcium_energy_spec, core.surface_calcium_profile_interventions_spec, core.surface_calcium_spec |  |
| unit/test_owned_calcium_profile_interventions_dispatch.py | 26 | 338.65 | core.surface_calcium_energy_profile_interventions_spec, core.surface_calcium_profile_interventions_spec |  |
| unit/test_source_pair.py | 68 | 74.58 | core.specs:SourcePairSpec |  |
| unit/test_spatial_calcium.py | 31 | 474.52 | core.spatial_calcium_spec |  |
| unit/test_surface_active_excision.py | 61 | 558.85 | core.surface_active_excision_spec, core.surface_kinetic_spec, core.surface_tissue_spec | the active path imports these families' modules today (surface_kinetic_spec: 2, surface_tissue_spec: 8 couplings): hold until they are resolved |
| unit/test_surface_calcium_catalog.py | 69 | 182.06 | core.surface_calcium_spec, core.surface_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_surface_calcium_cav.py | 18 | 114.93 | core.surface_calcium_spec, core.surface_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_surface_calcium_energy_atp_transport_excision.py | 23 | 275.67 | core.surface_calcium_energy_atp_transport_excision_spec, core.surface_calcium_energy_atp_transport_spec |  |
| unit/test_surface_calcium_energy_excision.py | 78 | 1770.32 | core.surface_calcium_energy_excision_spec, core.surface_calcium_energy_spec |  |
| unit/test_surface_calcium_energy_irreversible_transport_excision.py | 23 | 459.48 | core.surface_calcium_energy_irreversible_transport_excision_spec, core.surface_calcium_energy_irreversible_transport_spe |  |
| unit/test_surface_calcium_energy_mitochondria.py | 48 | 462.65 | core.surface_calcium_energy_mitochondria_spec |  |
| unit/test_surface_calcium_energy_regulated_v2_excision.py | 27 | 87.25 | core.surface_calcium_energy_regulated_v2_excision_spec, core.surface_calcium_energy_regulated_v2_spec |  |
| unit/test_surface_calcium_energy_transport.py | 42 | 421.92 | core.surface_calcium_energy_transport_spec |  |
| unit/test_surface_calcium_energy_water_hcn_extra.py | 24 | 257.23 | core.surface_calcium_energy_spec, core.surface_calcium_energy_water_hcn_extra_spec, core.surface_calcium_energy_water_re |  |
| unit/test_surface_calcium_energy_water_integration.py | 4 | 401.01 | core.surface_calcium_energy_water_spec |  |
| unit/test_surface_calcium_energy_water_repair_hcn_extra.py | 22 | 271.75 | core.surface_calcium_energy_water_hcn_extra_spec, core.surface_calcium_energy_water_repair_hcn_extra_spec, core.surface_ |  |
| unit/test_surface_calcium_energy_water_repair_integration.py | 4 | 534.01 | core.surface_calcium_energy_water_repair_spec |  |
| unit/test_surface_calcium_excision.py | 61 | 1123.21 | core.surface_calcium_excision_spec, core.surface_calcium_spec |  |
| unit/test_surface_calcium_hcn.py | 15 | 110.37 | core.surface_calcium_spec |  |
| unit/test_surface_calcium_kv1.py | 18 | 123.89 | core.surface_calcium_spec, core.surface_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_surface_calcium_sodium.py | 13 | 113.04 | core.surface_calcium_spec, core.surface_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_surface_calcium_water_integration.py | 4 | 287.08 | core.surface_calcium_water_spec |  |
| unit/test_surface_catalog.py | 33 | 103.66 | core.surface_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_surface_channels.py | 24 | 946.16 | core.surface_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_surface_cotransport_water_jax.py | 1 | 52.16 | core.surface_cotransport_water_spec |  |
| unit/test_surface_cotransport_water_response_capture.py | 18 | 134.9 | core.surface_cotransport_water_spec |  |
| unit/test_surface_energy_execution.py | 8 | 700.09 | core.surface_energy_spec |  |
| unit/test_surface_energy_qualification.py | 10 | 346.4 | core.surface_energy_spec, core.surface_tissue_spec | the active path imports these families' modules today (surface_tissue_spec: 8 couplings): hold until they are resolved |
| unit/test_surface_energy_water_execution.py | 8 | 860.73 | core.surface_energy_water_spec |  |
| unit/test_surface_energy_water_qualification.py | 12 | 484.94 | core.surface_energy_water_spec, core.surface_tissue_spec | the active path imports these families' modules today (surface_tissue_spec: 8 couplings): hold until they are resolved |
| unit/test_surface_hcn.py | 28 | 1365.26 | core.surface_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_surface_mobile_channel.py | 66 | 883.17 | core.surface_mobile_channel_spec, core.surface_mobile_pump_spec |  |
| unit/test_surface_mobile_pump.py | 62 | 587.6 | core.surface_mobile_pump_spec, core.surface_redistribution_spec |  |
| unit/test_surface_mobile_repair.py | 58 | 1602.73 | core.surface_mobile_repair_spec, core.surface_repair_spec |  |
| unit/test_surface_profile_epoch_dispatch.py | 8 | 147.74 | core.surface_profile_epoch_spec, core.surface_profile_interventions_spec |  |
| unit/test_surface_redistribution.py | 42 | 180.73 | core.surface_redistribution_spec, core.surface_tissue_spec | the active path imports these families' modules today (surface_tissue_spec: 8 couplings): hold until they are resolved |
| unit/test_surface_repair.py | 25 | 566.68 | core.surface_calcium_spec, core.surface_repair_spec |  |
| unit/test_surface_repair_full.py | 12 | 1164.68 | core.surface_repair_spec |  |
| unit/test_surface_sodium.py | 26 | 1154.63 | core.surface_kinetic_spec | the active path imports these families' modules today (surface_kinetic_spec: 2 couplings): hold until they are resolved |
| unit/test_surface_water.py | 39 | 199.86 | core.surface_tissue_spec, core.surface_water_spec | the active path imports these families' modules today (surface_tissue_spec: 8 couplings): hold until they are resolved |
| unit/test_surface_water_execution.py | 5 | 347.16 | core.surface_water_spec |  |
| unit/test_surface_water_kinetic.py | 51 | 437.22 | core.surface_kinetic_spec, core.surface_tissue_spec, core.surface_water_kinetic_spec, core.surface_water_spec | the active path imports these families' modules today (surface_kinetic_spec: 2, surface_tissue_spec: 8 couplings): hold until they are resolved |
| unit/test_surface_water_kinetic_execution.py | 5 | 630.47 | core.surface_water_kinetic_spec |  |
| unit/test_tissue.py | 34 | 251.31 | core.specs:SpatialJunctionSpec, core.tissue_spec |  |
