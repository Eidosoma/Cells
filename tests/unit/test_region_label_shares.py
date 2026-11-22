"""FR-33's labels as FR-42's shares (D289; D300 retired D1's label families): the synapse
acceptance and FR-33's first test (validation/regions/example.py), each beside plain rows of the
same material, which every law moves exactly, as the reference.

Three compiled programs (the synapse world's, and the first test's two, since only its local-loss
control declares turnover) and four runs of 200 steps: about 90 s on a light CPU. Their reason
(D224): FR-33's acceptance on regions and FR-42 stage 2's on faces. They were moved here from
tests/unit/test_region_readouts.py, unchanged, to keep each file under the tier cap.
"""

import numpy as np

from cells.definitions.specs import parse_spec
from cells.registry.models import get_model
from validation.regions import example, readouts


def _shares_against_reference(spec, times, states, label, row, nodes):
    """(by shares, by the exact row) [time, node] at every saved state, and the row's scale."""
    shared = readouts.label_nodes(spec, times, states, "P", label)
    _, layout = get_model(spec.model).initial_values(spec)
    exact = readouts.world_map(spec, row)
    by_shares = np.array([[shared["node_fmol"][n][k] for n in nodes] for k in range(len(times))])
    index = [exact["nodes"].index(n) for n in nodes]
    by_row = np.array([readouts.node_records(spec, layout, s, exact)[0][index] for s in states])
    return by_shares, by_row, float(np.max(np.abs(by_row)))


def test_the_synapse_label_follows_its_exact_rows_by_shares():
    """FR-33's acceptance on the synapse regions, its label as FR-42's shares (D289; D300 retired
    D1's families; validation/regions/example.synapse_world). One compiled program, two runs of
    200 steps (the rates are data). The label moves between syn_1 and syn_2 by the engine's own
    face law, carried as shares by the label owner, beside the plain row P_L of the same material,
    which each law moves exactly:
    - at every step and node the shares give P_L's amount within 2e-6 of its scale (the share
      update's and @3's trapezoid's second order);
    - pure redistribution (no clearance): the label's total is stable at rounding (by the world's
      symmetry; in general it holds to the share update's second order);
    - degradation (clearance in syn_1, alike on P, P_L and P_U): the label's total falls as
      P_L's does, within the same bound."""
    eps = np.finfo(float).eps
    for degrade in (0.0, 0.5):
        spec = parse_spec(example.synapse_world(degrade=degrade))
        times, states = readouts.runs(spec)
        shares, exact, scale = _shares_against_reference(
            spec, times, states, "labelled", "P_L", example.SYNAPSES
        )
        assert np.max(np.abs(shares - exact)) <= 2e-6 * scale
        total = shares.sum(axis=1)
        if degrade == 0.0:
            assert np.max(np.abs(total - total[0])) <= 64 * eps * scale
        else:
            assert total[0] - total[-1] > 0.05
        assert shares[-1, 1] - shares[0, 1] > 0.1  # The label reached syn_2.


def test_fr33s_first_test_two_named_regions_joined_by_one_face():
    """FR-33's first test, as its requester asked (validation/regions/example.first_test; two
    compiled programs, since only the local-loss control declares turnover, and two runs of 200
    steps): two named regions, donor and receiver, joined by one bidirectional face, the label as
    FR-42's shares of the protein row P (D300 retired D1's families), the receiver starting with no
    label (the usual trace) and the face's heat booked exactly (F2). At every saved time, in fmol:
    - pure transfer (the face open, no clearance): the label total is conserved and the receiver's
      gain is the donor's loss, at rounding (by the world's symmetry; in general to the share
      update's second order), and nothing is cleared;
    - the local-loss control (the face closed, clearance at the donor): the receiver stays flat,
      and the cumulative clearance accounts for the donor's missing label, at rounding;
    - the label by shares gives the exact row P_L's amounts within 2e-6 of its scale (the share
      update's and @3's trapezoid's second order; at rounding in the local-loss control, where no
      arrival changes a share).
    Each region keeps its ID and declared volume in the record, and "whole-cell label" is stated
    there as the sum over the two regions."""
    eps = np.finfo(float).eps
    for case in example.FIRST_TEST_CASES:
        record = example.first_test(case)
        assert record["regions"] == [dict(id=r, node=r, volume_pL=example.FIRST_TEST_VOLUME_pL)
                                     for r in example.FIRST_TEST_REGIONS]  # fmt: skip
        assert record["units"] == "fmol"
        assert record["definitions"]["whole_cell_label_fmol"] == example.WHOLE_CELL_LABEL
        donor, receiver = record["donor_label_fmol"], record["receiver_label_fmol"]
        whole, cleared = record["whole_cell_label_fmol"], record["cleared_fmol"]
        assert len(record["times_s"]) == len(donor) == len(receiver) == len(whole) == len(cleared)
        for k in range(len(donor)):
            tol = 64 * eps * (abs(donor[0]) + abs(receiver[0]) + abs(donor[k]) + abs(receiver[k]))
            assert whole[k] == donor[k] + receiver[k]
            if case == "transfer":
                assert cleared[k] == 0.0
                assert abs(whole[k] - whole[0]) <= tol
                assert abs((receiver[k] - receiver[0]) - (donor[0] - donor[k])) <= tol
            else:
                assert receiver[k] == receiver[0]
                assert abs((donor[0] - donor[k]) - (cleared[k] - cleared[0])) <= tol + 64 * eps * (
                    abs(cleared[k])
                )
        reference = record["reference_fmol"]
        scale = max(abs(v) for v in reference["donor"])
        bound = 2e-6 if case == "transfer" else 64 * eps
        for ours, exact in ((donor, "donor"), (receiver, "receiver"), (cleared, "cleared")):
            assert np.max(np.abs(np.asarray(ours) - np.asarray(reference[exact]))) <= bound * scale
        moved = donor[0] - donor[-1]
        assert moved > 0.05, case  # Transfer, or clearance, actually happened.
