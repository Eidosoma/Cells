"""BETSE target-selection conventions, built on the engine's tissue target selectors.

The engine selects explicit stable-owner targets (`cells.processes.tissue_target_selectors`).
BETSE v1.5.0's global gap-junction selection has a quirk: it shuffles a copy that
is then discarded, so the actual prefix of the membrane list wins. That reference
behaviour lives here, for the BETSE-loop reproduction only. Engine names are
re-exported unchanged.
"""

from cells.processes import tissue_target_selectors as _selectors

globals().update({k: v for k, v in vars(_selectors).items() if not k.startswith("__")})
from cells.processes.tissue_target_selectors import (  # noqa: E402
    _number,
    _target,
    validate_layout,
)


def global_gj_prefix_targets(layout, requested_percent):
    """Native global GJ target bug: shuffled copy is unused; actual prefix wins."""
    t = validate_layout(layout)
    if not _number(requested_percent):
        raise ValueError("Require finite numeric global GJ percentage")
    percent = min(100, max(1, int(requested_percent)))
    return _target(t, "membrane", t.membrane_ids[: int((percent / 100) * len(t.membrane_ids))])
