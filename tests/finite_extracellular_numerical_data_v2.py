"""NUM-009 v2 binding. V1 physics, checks, inputs and failed evidence stay frozen."""

from tests import finite_extracellular_numerical_data as v1

ROOT, spec, sha, layout = v1.ROOT, v1.spec, v1.sha, v1.layout
PANEL = ROOT / "configs/reference/finite_extracellular_trajectories_v2.json"
PANEL_SHA256 = "91d7e85deddcc98c4e0ea1a474192d4224bda86edbfce85d563c663d008bcaa8"


def load_panel():
    if sha(PANEL) != PANEL_SHA256:
        raise ValueError("Frozen NUM-009 v2 panel changed")
    plan = spec.ion.load_json(PANEL)
    old, cases = v1.load_panel()
    for key, value in old.items():
        if key not in ("schema", "coordinate_contract") and plan[key] != value:
            raise ValueError("V2 must retain V1 physical inputs, settings and limits")
    previous = plan["supersedes"]
    if (
        previous["panel_sha256"] != v1.PANEL_SHA256
        or sha(ROOT / previous["failed_attempt"]) != previous["failure_sha256"]
    ):
        raise ValueError("Prior stopped attempt identity changed")
    return plan, cases
