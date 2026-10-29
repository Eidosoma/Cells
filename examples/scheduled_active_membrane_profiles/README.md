# Scheduled membrane profiles with active channels and pumps

This manufactured example applies regional Na/K/Cl/Ca membrane pulses to the
complete active tissue model, including all 56 channel laws and maintained-fuel
pumps. It retains the native profile recipe, stable owners, explicit thickness,
all physical and accounting state, and a saved SIM phase clock. Parameters are
numerical fixtures, not fitted biological measurements.

Validate the input from the repository root:

```bash
python -m cells validate examples/scheduled_active_membrane_profiles/definition.json
```

The sealed artifact replays the complete definition:

```python
import json
from pathlib import Path
from cells.core import surface_active_profile_interventions_spec as scheduled

folder = Path("examples/scheduled_active_membrane_profiles")
spec = scheduled.replay(json.loads((folder / "artifact.json").read_text()))
assert spec.to_dict() == json.loads((folder / "definition.json").read_text())
```

Scheduled pulses change background membrane permeability. Channel gates, channel
conductance and pump kinetics retain their physical rules and separate controls.
Closing a background route preserves its earlier transfers and work history.
Snapshots keep all twenty fields, including the phase clock. Ordinary restart
cannot reset the clock or switch between INIT and SIM.

This example uses eager CPU execution. Component checks include independent
equations, short trajectory refinement and exact restart. Compiled active-profile
trajectories and GPU execution remain separate qualification work. A separate
[active INIT-to-SIM adapter](../../docs/TISSUE_PHASES.md) uses the shared
`tissue-phase` commands to carry evolved gates and physical/accounting history
into a new experiment; its qualification is tracked separately in Progress.

See the [model contract](../../docs/TISSUE_RETURN_CURRENT.md#scheduled-active-membrane-profiles)
and [Progress](../../PROGRESS.md) for scope and evidence. Write outputs to a new
directory under `/mnt/workspaces/Cells`.
