"""Deferred existing ordinary cases; no new enabled-flow equation specimen."""

from validation.betse.betse_normal_ecm_mechanics_join_fixtures import fixture as ordinary_fixture

CASES = ("coupled-osmotic", "mechanics-disabled")
REFUSALS = ("enabled-flow", "nonzero-disabled-flow-drive")


def fixture(case=CASES[0]):
    if case not in CASES:
        raise ValueError("Undeclared disabled-flow ownership case")
    return dict(
        kind="cells.betse_normal_ecm_flow_join_inputs@1",
        case_id=case,
        ordinary_inputs=ordinary_fixture(case),
    )
