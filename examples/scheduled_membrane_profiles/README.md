# Scheduled passive membrane profiles

This manufactured example applies four ion-specific regional membrane events
to a passive tissue. It retains the complete static profile preparation, native
defaults, stable membrane owners, explicit thickness and SIM phase policy.
The parameters are numerical fixtures, not fitted biological measurements.

Validate the ordinary input from the repository root:

```bash
python -m cells validate examples/scheduled_membrane_profiles/definition.json
```

`artifact.json` carries the complete preparation and scheduled-model identity.
To verify its replay through the Python API:

```python
import json
from pathlib import Path
from cells.core import surface_profile_interventions_spec as scheduled

folder = Path("examples/scheduled_membrane_profiles")
spec = scheduled.replay(json.loads((folder / "artifact.json").read_text()))
assert spec.to_dict() == json.loads((folder / "definition.json").read_text())
```

Fresh SIM starts with a zero phase clock. A saved checkpoint retains its evolved
clock and complete physical state; ordinary restart never resets the phase.
The event law is sampled at RK stages. The separate
[INIT-to-SIM workflow](../../docs/TISSUE_PHASES.md) carries evolved passive state
into a new experiment. Native solver-loop equivalence remains separate.

See [the model contract](../../docs/TISSUE_RETURN_CURRENT.md#scheduled-passive-membrane-profiles)
for supported events and [Progress](../../PROGRESS.md) for qualification scope.
Write run outputs under `/mnt/workspaces/Cells`, using a new directory per run.
