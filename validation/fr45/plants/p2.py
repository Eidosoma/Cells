"""P2 (C1): the two populations' k_off crossed, by declaration (CRITERIA:120; TABLE §8.1, B6). The two are the first
shared set's first two populations: matrix_L1 and matrix_L2 in a registered W1p. No code is patched."""

import copy

ID = "P2"
CHANGE = "inputs: the two populations' k_off crossed (planted by declaration)"


def declare(inputs):
    inputs = copy.deepcopy(inputs)
    shared = next(s["id"] for s in inputs["sets"] if s["shared"])
    a, b = [p for p in inputs["populations"] if p["set"] == shared][:2]
    a["k_off"], b["k_off"] = b["k_off"], a["k_off"]
    return inputs, [f"populations[id={a['id']}].k_off", f"populations[id={b['id']}].k_off"]


def apply():
    pass
