# Carry an active INIT state into SIM

`continued.request.json` embeds an evolved active INIT checkpoint and a new SIM
experiment. It preserves all nineteen physical and accounting arrays, including
intrinsic gates, transferred ions, pump cycles, heat and maintained-fuel work.
Only the phase clock resets. The source contains the full 56-law channel catalog.

From the repository root:

```bash
python -m cells tissue-phase prepare examples/active_tissue_phase/continued.request.json \
  --output /mnt/workspaces/Cells/active-phase-example
python -m cells tissue-phase validate /mnt/workspaces/Cells/active-phase-example
python -m cells tissue-phase replay /mnt/workspaces/Cells/active-phase-example/provenance.json \
  --output /mnt/workspaces/Cells/active-phase-replayed
```

The prepared model is `resolved_active_membrane_profile_epoch@1`. The request
contains an 8-microsecond INIT history and declares an 8-microsecond SIM with
changed membrane, junction, channel and pump controls. Independent full-state
solutions and timestep refinement check both phases. This is a manufactured
numerical case, not a measured tissue or a demonstration of biological settling.
Its maintained fuel does not represent finite ATP pools.

Preparation and replay do not advance SIM. Both output directories must be new.
The [phase guide](../../docs/TISSUE_PHASES.md) explains snapshots, clocks and
execution settings. [Progress](../../PROGRESS.md) records the separate scientific,
public-interface and execution qualification scopes.
