# Native membrane redistribution: compact source correspondence

Ordinary BETSE v1.5.0 has no enabled membrane redistribution seam to implement.
`Parameters.load` sets `sim_eosmosis=False`; its mobility and charge readers are
commented out. `Simulator.init_dynamics` comments out construction of
`MoveChannel` and actively sets `rho_pump=rho_channel=1` after molecular/GRN
setup. The GRN-only runner and optimizer also contain identity resets, not
moving-weight updates. The audit indexes every explicit tracked attribute and
subscript writer across all 332 native Python files and checks installed byte
identity. This is a source inventory, not runtime reachability evidence.

`MoveChannel` has no active import, constructor or caller in that tree. Its
`run` method would update channels before pumps. After a successful constructor,
ordinary parameters lack `z_channel`, then `D_membrane`; supplying those still
leaves `sim_toolbox.single_cell_div_free(flux,cells)` absent. The original flux
formula precedes the missing projector and the density assignment follows it.
Thus an exception there prevents the channel assignment and subsequent pump
update. These are static failure-order observations; no forced call or partial
runtime record was manufactured. `sim.Ec` has only a zero initializer and reads
in the dormant class. `Cells.single_cell_div_free(self,uxo,uyo)` is a separate
two-component vector method and cannot silently replace the missing API.

| Native consumer | Existing explicit source correspondence | Scope and remaining gap |
| --- | --- | --- |
| Ordinary Na/K pump | `betse_normal_pump_join` and `betse_normal_ecm_init_phase_pump` multiply raw Na/K flux once, then apply boundary masking. The rate proxy stays raw. | Existing `redistributed` fixture declares supplied nonunit weights. It does not activate native movement. |
| Primary ion electroflux | `betse_ecm_transport._electroflux` receives the declared membrane `channel_multiplier`, matching native `rho_channel` multiplication. | Supplied membrane axis and downstream material/field books already exist. No new weight producer. |
| Modern channel catalog | `betse_normal_ecm_catalog_join_source` passes `sim.rho_channel` to native-shaped channel flux operations. | Existing `rho_blocked` declaration supplies zero; maximum-zero and empty-channel declarations are separate controls. Their declarations are inventoried, not rerun. |
| Molecular transport | `betse_ecm_grn_source.Molecule.transport` passes `sim.rho_channel`; frozen molecule-dispatch01 retains distinct general/GRN owners and general-then-GRN current publication. | Ordinary identity weighting is already composed. Active molecular pumps/gating and extra configured transporters are outside that packet. |
| ECM CaATP | `betse_normal_ecm_calcium_join.calcium` explicitly binds `rho_pump=1`, matching ordinary setup. | Conditional nonunit native ECM weights multiply the cached flux once and the applied flux twice. The proxy aliases the boundary-masked handler flux. That nonunit branch is not qualified by the unit-weight packet. |
| Configured transporters | Native `MasterOfNetworks.run_loop_transporters` multiplies its evaluated flux by `sim.rho_pump`. `betse_normal_transporter_join` provides a separate rectangular no-ECM composition. | An ECM general-owner transporter composition remains a supported separate integration job. It must not imply enabled moving weights. |

The existing material, charge, full-field and owner-cache ledgers remain the
appropriate consumers of weighted ion/molecule flux. A dimensionless multiplier
does not establish a membrane pump/channel population inventory, trafficking
balance or energy law. Native `Molecule.pump` and `Molecule.gating` contain
additional rho reads; their enabled branches need their own supplied state and
coverage. Existing Cells surface-redistribution models express a different
physical law and are not a replacement for the missing native projector.

Dependencies are explicit: frozen INIT02 manifest
`528a1c7d1df0be152919b9dd446f3247676856585652f2c2924d82840c27d36f`
and molecule-dispatch01 manifest
`e51f7eead8d6bfe3a0e4f669005386e6f4271632f0531084754320025b1ed922`.
The JSON receipt binds source anchors and complete native hashes to those
manifests. All investigation uses stdlib parsing/hashing only. No new numerical
panel, driver, product module or scientific pass is proposed. Existing failures,
oracle domains, budgets, frozen packets and active computations are untouched.

Reproduce the static receipt from the repository with:

```sh
/mnt/workspaces/Cells/venv-cpu/bin/python -B agent-work/cells-worker-01/workfiles/betse_normal_ecm_redistribution_audit.py
```
