"""Where each plant and each named check acts: CRITERIA section 6.1 for the registered worlds, this folder's own choices for
the invented ones. Steps and times are the JSON floats of the inputs files.
"""

REGISTERED = {
    "equal_volumes": ("F1", "F2"),                  # the equal-volume chain and its reverse (check 1)
    "chains": ("F1", "F2", "F3", "F4"),             # every chain of arm 3 (check 2)
    "request_state": {"N-buffered": (16.0, (8, 2)), "N-clean": (16.0, (8, 2)), "N-none": (16.0, (8, 2))},
    "P1": {"worlds": ("F1", "F2"), "step": 1.0, "time": 8.0},
    "P2": {"worlds": ("F1", "F3"), "step": 1.0},
    "P3": {"equal": "F1", "unequal": "F3", "step": 1.0},
    "P4": {"world": "F1", "step": 1.0},
    "P5": {"world": "H1"},
    "P7": {"worlds": ("H2", "H3", "H4")},
    "P8 event": {"run": "P8 event", "world": "N-buffered", "step": 0.25},
    "P8 flow": {"run": "P8 flow", "world": "F1", "step": 1.0},
    "P9": {"world": "G1"},
    "P10": {"world": "F1", "step": 1.0, "time": 8.0},
    "P11": {"world": "F1L", "step": 8.0},
    "P14": {"world": "r4-mid"},
    "P15": {"worlds": ("eq-lo", "eq-mid", "eq-hi"), "step": 0.25},
    "P16": {"world": "eq-mid"},
    "P17": {"world": "N-buffered"},
    "P19": {"world": "J1"},
}

INVENTED = {
    "equal_volumes": ("inv-F1", "inv-F2"),
    "chains": ("inv-F1", "inv-F2", "inv-F3"),
    "P1": {"worlds": ("inv-F1", "inv-F2"), "step": 1.03125, "time": 8.25},
    "P2": {"worlds": ("inv-F1", "inv-F3"), "step": 1.03125},
    "P3": {"equal": "inv-F1", "unequal": "inv-F3", "step": 1.03125},
    "P4": {"world": "inv-F1", "step": 1.03125},
    "P5": {"world": "inv-H1"},
    "P7": {"worlds": ("inv-H2",)},
    "P8 event": {"run": "inv-P8 event", "world": "inv-N-buffered", "step": 0.171875},
    "P8 flow": {"run": "inv-P8 flow", "world": "inv-F1", "step": 1.03125},
    "P9": {"world": "inv-G1"},
    "P10": {"world": "inv-F1", "step": 1.03125, "time": 8.25},
    "P11": {"world": "inv-F1L", "step": 8.25},
    "P14": {"world": "inv-r4-mid"},
    "P15": {"worlds": ("inv-eq-mid",), "step": 0.15625},
    "P16": {"world": "inv-eq-mid"},
    "P17": {"world": "inv-N-buffered"},
    "P19": {"world": "inv-J1"},
}
