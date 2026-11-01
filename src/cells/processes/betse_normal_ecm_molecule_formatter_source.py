"""Literal BETSE1.5.0 networks.tex_val; no warm/source activation here.

Source copyright Alexis Pietak and Cecil Curry; see the pinned BETSE LICENSE.
The Python-float test, truncated logarithm and mean fallback are deliberate.
"""

import math

import numpy as np


def tex_val(v):
    """Return the original decimal/scientific text, including raw failures."""
    if type(v) is float:
        if v != 0.0:
            v_check = int(math.log10(abs(v)))
        else:
            v_check = 0
        if v_check >= 3 or v_check <= -2:
            v_str = "%.2e" % (v)
        else:
            v_str = "%.2f" % (v)
    else:
        v_str = str(np.mean(v))
    return v_str
