"""FR-38's step 5, the requester's acceptance (D284; amendment S §9.16, erratum E §9.18): replace a
producer midway through a chase, then restart (validation/gene_regulation/replace_restart.py).

The driver's docstring states the world, the readouts and the limit: until amendment T's export is
built, only the newcomer's material stays in the cell, and the departing generation g0's RNA is read
from the label owner's removal record, never from a row.

Three compiles (the unlabelled run, the labelled run and the resume from snapshot files); the
seconds are stated at landing. Their reason (D224): the requester's own acceptance of producer
identity across replacement and restart, which only a compiled composition of the label owner,
replacement@1 and the gene unit reaches.
"""

from validation.gene_regulation import replace_restart as rr


def test_a_replaced_producer_restarts_bit_for_bit_with_its_generations_apart(tmp_path):
    """Every verdict of the driver's check: labels change no physics; the resume after the
    replacement reproduces every step and every readout bit for bit, the cohort counts among them;
    no g1 share before the event and no g0 share in the cell after it; the removal records agree
    with replacement@1's removed rows and the operator's H_rem; g0's and g1's per-producer
    identities.
    Then the readouts' shape: a window cohort that lives and decays before the event, g0's RNA
    departed at it, and g1's in the cell at the end."""
    record = rr.check(tmp_path)
    failed = [name for name, ok in record["verdicts"].items() if not ok]
    assert not failed, (
        failed,
        record["physical_fields_differing"],
        record["resumed_fields_differing"],
        record["record_gap_fmol"],
        record["pool_record_gap_fmol"],
        record["identities"],
    )
    survival = record["survival"]
    assert survival["at_W_copies"] > 0 and 0 < survival["fraction"] < 1
    assert survival["departed_at_T_E_copies"] > 0
    end = record["readouts"][str(rr.END)]
    assert end["g0_in_cell_copies"] == 0 and end["g0_departed_copies"] > 0
    assert end["g1_in_cell_copies"] > 0
