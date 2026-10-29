# Explicit INIT-to-SIM preparation

`continued.request.json` embeds a manufactured evolved passive INIT checkpoint
and a new SIM experiment. All twelve physical state arrays and their original
accounting references survive. SIM starts a new phase clock while retaining
both INIT clocks and the complete source history.

From the repository root:

```bash
python -m cells tissue-phase prepare examples/tissue_phase/continued.request.json \
  --output /mnt/workspaces/Cells/phase-example
python -m cells tissue-phase validate /mnt/workspaces/Cells/phase-example
```

The request comes from the checked component's 10-microsecond evolved INIT
case. It is a numerical fixture, not fitted biological data. Preparation does
not run SIM. See [the phase guide](../../docs/TISSUE_PHASES.md) for snapshot
input, replay, clocks and execution settings, and [Progress](../../PROGRESS.md)
for qualification scope.
