"""Pure saved-sample diagnostic checks, with no integration or accepted-evidence edits."""

import numpy as np
import pytest

from scripts import diagnose_graph_reference_disagreement as diagnostic


def test_normalization_and_first_tied_maximum():
    result = diagnostic.worst_sample(
        np.array([0, 1]), np.array([[0, 3], [0, 3]]), np.ones((2, 2)), {"atol": 1, "rtol": 1}
    )
    assert result["time"] == 0 and result["column"] == 1
    assert result["score"] == 1 and result["absolute_difference"] == 2
    assert result["candidate_budget_at_expected"] == 2


def test_regulatory_and_oriented_history_coordinate_mapping():
    case = {"cell_ids": [100, 200, 300], "edge_ids": [10, 20]}
    assert diagnostic.coordinate(case, "regulatory_state", 5) == {
        "coordinate": "Zeb_mRNA_total",
        "kind": "primary",
        "cell_id": 300,
    }
    assert diagnostic.coordinate(case, "regulatory_history", 5) == {
        "coordinate": "Zeb_mRNA_total",
        "kind": "local_regulatory_history",
        "cell_id": 300,
    }
    assert diagnostic.coordinate(case, "regulatory_history", 10) == {
        "coordinate": "miRNA_exchange_history",
        "kind": "oriented_edge_history",
        "edge_id": 20,
    }


def test_nonfinite_sample_is_not_a_diagnostic_witness():
    with pytest.raises(ValueError, match="Invalid diagnostic"):
        diagnostic.worst_sample(
            np.array([0]), np.array([[np.nan]]), np.zeros((1, 1)), {"atol": 1, "rtol": 0}
        )
