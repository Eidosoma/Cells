"""One skip reason for tests that ran the BETSE-order family through the Cells runner.

On 8 November 2026 (D131) the BETSE-order kernel family left the engine and became
this emulator. The engine registry, spec parser and control schedule no longer
dispatch to it, so tests and assays that executed it through cells.core.runner,
batch, windows or checkpoints cannot run until they are re-hosted on a Cells
physical model. Each such test module sets

    pytestmark = pytest.mark.skip(reason=REHOST_REASON)

so lifting the skips is one grep. rehost_pending.json lists the affected test and
assay modules and what each needs from a Cells model.
"""

LAST_RUNNABLE_COMMIT = "432e62b"
REHOST_REASON = (
    "D131: the BETSE-order model left the engine registry; this assay awaits re-hosting "
    f"on a Cells physical model. Last runnable at commit {LAST_RUNNABLE_COMMIT}."
)

# Byte-identical files the move relocated; frozen protocols still name the old paths.
MOVED = {
    f"configs/{name}": f"validation/betse/emulator/configs/{name}"
    for name in (
        "betse_spatial_active.json",
        "betse_spatial_interventions.json",
        "betse_spatial_interventions_long.json",
        "betse_spatial_junction.json",
    )
}


def moved(relative):
    """Current checkout location of a path named by a frozen protocol."""
    return MOVED.get(relative, relative)
