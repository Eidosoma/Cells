"""The rehearsal's invented worlds: inputs_rehearsal.json and the legacy definitions (SPEC 8).

Every number here is invented. `exclusions.py` checks mechanically that none of the spec folder's
volumes, amounts, permeabilities, rates, seeds, times, steps and horizons is among them, with the
exceptions that SPEC section 8 and the channel law name. A world is written once, in `WORLDS`, and
gives
- its block in inputs.json's form (SPEC section 2.5) with `scales`, `amount_refs`, `closure_terms_V`
  and
`p` by rules.py, and
- the legacy definitions at h, h/2 and h/4 in the captured form, for the frozen snapshot.

    make_inputs.py write
    validation/ensemble_reexpression/rehearsal/inputs_rehearsal.json
    make_inputs.py origin DIR SNAPSHOT [WORLD ...]   the legacy definitions, the job list that
                                          validation/legacy_port's capture.sh reads and the origin's
                                          manifest, in
                                          a new folder (of every world, or of the named ones)
"""

import hashlib
import json
import sys
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules  # noqa: E402

SPECIES = {"Na": 1, "K": 1, "Cl": -1}
TOLERANCE = {"Cl": 3e-11, "K": 3e-11, "Na": 3e-11}


# ------------------------------------------------------------------ the invented numbers


def fixed(amounts, charge_C, decimals, species=SPECIES):
    """The fixed charge that closes a compartment's own charge, rounded to `decimals` decimals (the
    captured style: the decimal of the declared fixed charge is the rounded one). Exact arithmetic
    on the declared doubles, so the residual is the rounding's."""
    need = Fraction(charge_C) / Fraction(rules.F * rules.FMOL) - sum(
        (Fraction(species[x]) * Fraction(n) for x, n in amounts.items()), Fraction(0)
    )
    return float(f"{float(need):.{decimals}f}")


def off_rule(amounts, charge_C, low=1.0e-24, high=5.1e-24):
    """A fixed charge off the electroneutral rule in the captured style: a rounded decimal whose
    residual (rules.charge_residual_C) lies between `low` and `high`, as the captured ones' do (up
    to 5.1e-24 C). The decimals are tried from the longest, then a last place up or down."""
    for decimals in (14, 13, 12):
        value = fixed(amounts, charge_C, decimals)
        for k in (0, 1, -1, 2, -2, 3, -3):
            candidate = float(f"{value + k * 10.0**-decimals:.{decimals}f}")
            residual = rules.charge_residual_C(SPECIES, amounts, candidate, charge_C)
            if low <= abs(residual) <= high:
                return candidate
    raise ValueError("no decimal leaves the residual in the range")


def cell(volume, na, k, cl, voltage, area, specific, *, decimals=13, off=False):
    """A cell with its membrane's area (m^2) and specific capacitance (F/m^2)."""
    cap = rules.capacitance(area, specific)
    q = rules.charge(cap, voltage)
    amounts = {"Na": na, "K": k, "Cl": cl}
    return dict(
        volume=volume,
        amounts=amounts,
        voltage=voltage,
        area=area,
        specific=specific,
        cap=cap,
        charge=q,
        fixed=off_rule(amounts, q) if off else fixed(amounts, q, decimals),
    )


def region(volume, na, k, cl, *, faces=(), decimals=None, off=False):
    """An outside region; `faces` are the cells that face it (its charge is minus theirs)."""
    return dict(
        volume=volume, amounts={"Na": na, "K": k, "Cl": cl}, faces=faces, decimals=decimals, off=off
    )


def junction(a, b, area, na, k, cl, threshold, minimum, initial):
    return dict(
        a=a,
        b=b,
        area=area,
        perm={"Na": na, "K": k, "Cl": cl},
        thr=threshold,
        lo=minimum,
        g0=initial,
    )


def face(a, b, area, length, na, k, cl):
    return dict(a=a, b=b, area=area, length=length, diff={"Na": na, "K": k, "Cl": cl})


def pump(capacity, km_na, km_k, km_atp, atp, adp, pi, dg0):
    return dict(
        capacity=capacity, km_na=km_na, km_k=km_k, km_atp=km_atp, atp=atp, adp=adp, pi=pi, dg0=dg0
    )


def channel(p_max, abundance, m, h):
    return dict(p_max=p_max, abundance=abundance, m=m, h=h)


def leak(na, k, cl):
    return {"Na": na, "K": k, "Cl": cl}


def pool(nodes, free, volume, on, close, off, dissolve, worlds, end, max_events):
    return dict(
        nodes=nodes,
        free=free,
        volume=volume,
        on=on,
        close=close,
        off=off,
        dissolve=dissolve,
        worlds=worlds,
        end=end,
        max_events=max_events,
    )


ON = [[0.0, 1.0]]
CLUSTER = dict(
    consumer="jupiter",
    temperature=298.15,
    gauge="bath",
    p=4,
    end=0.014112,
    tolerance=TOLERANCE,
    cells={
        "cell_0": cell(0.64, 7.4, 86.5, 5.3, -0.0525, 3.3e-10, 0.0112, decimals=13),
        "cell_1": cell(0.88, 12.9, 113.0, 8.6, -0.0365, 4.2e-10, 0.0118, decimals=13),
    },
    outside={
        "bath": region(2.2, 303.6, 9.9, 246.4, faces=("cell_0", "cell_1"), decimals=13),
        "cleft": region(1.2, 151.2, 8.4, 130.8),
        "rim": region(3.3, 471.9, 10.56, 382.8),
    },
    leaks={"cell_0": leak(1.4e-11, 2.6e-10, 9.5e-11), "cell_1": leak(1.1e-11, 2.9e-10, 8.4e-11)},
    pumps={
        "cell_0": pump(0.056, 11.5, 0.245, 0.45, 1.7, 0.13, 0.14, -36400.0),
        "cell_1": pump(0.093, 11.5, 0.245, 0.45, 1.7, 0.13, 0.14, -36400.0),
    },
    channels={
        "cell_0": channel(2.7e-10, 0.55, 0.245, 0.66),
        "cell_1": channel(3.4e-10, 0.65, 0.245, 0.66),
    },
    junctions={
        "gap": junction("cell_0", "cell_1", 1.1e-10, 2.6e-10, 4.5e-10, 3.7e-10, 0.0135, 0.12, 0.58)
    },
    faces={
        "face_0": face("bath", "cleft", 1.3e-11, 2.3e-05, 1.3e-09, 1.9e-09, 2.1e-09),
        "face_1": face("cleft", "rim", 1.3e-11, 2.3e-05, 1.3e-09, 1.9e-09, 2.1e-09),
        "face_2": face("rim", "bath", 1.3e-11, 2.3e-05, 1.3e-09, 1.9e-09, 2.1e-09),
    },
    candidate=(2.4e-05, 1.2e-05, 6e-06),
    legacy=7.2e-05,
    spacing=7.2e-05,
    potentials=(0.0, 0.002016, 0.004104, 0.006048, 0.008208, 0.011088, 0.014112),
    off_grid_observation=4.1e-05,
)


def released(world, off, on):
    """The same world with both pumps off from `off` to `on` (a pump schedule)."""
    return dict(
        world, schedules={"pump": {c: [[0.0, 1.0], [off, 0.0], [on, 1.0]] for c in world["cells"]}}
    )


BOUND = dict(
    consumer="jupiter",
    temperature=298.15,
    gauge="bath",
    p=4,
    end=0.01635,
    tolerance=TOLERANCE,
    cells={
        "cell_0": cell(0.72, 8.6, 97.0, 6.1, -0.0475, 3.5e-10, 0.0121, decimals=13),
        "cell_1": cell(0.57, 6.9, 77.5, 4.7, -0.0565, 2.7e-10, 0.0109, decimals=13),
    },
    outside={
        "bath": region(2.6, 364.0, 11.7, 291.2, faces=("cell_0", "cell_1"), decimals=13),
        "cleft": region(1.1, 134.2, 8.8, 116.6),
        "rim": region(3.1, 449.5, 10.23, 362.7),
    },
    leaks={"cell_0": leak(1.2e-11, 2.1e-10, 8.7e-11), "cell_1": leak(1.5e-11, 2.4e-10, 7.6e-11)},
    pumps={
        "cell_0": pump(0.071, 13.2, 0.27, 0.55, 1.6, 0.12, 0.17, -35800.0),
        "cell_1": pump(0.062, 13.2, 0.27, 0.55, 1.6, 0.12, 0.17, -35800.0),
    },
    channels={
        "cell_0": channel(2.9e-10, 0.46, 0.27, 0.63),
        "cell_1": channel(3.6e-10, 0.52, 0.27, 0.63),
    },
    junctions={
        "gap": junction("cell_0", "cell_1", 9.4e-11, 3.3e-10, 5.2e-10, 4.1e-10, 0.0165, 0.14, 0.52)
    },
    faces={
        "face_0": face("bath", "cleft", 1.15e-11, 2.1e-05, 1.28e-09, 1.83e-09, 1.97e-09),
        "face_1": face("cleft", "rim", 1.15e-11, 2.1e-05, 1.28e-09, 1.83e-09, 1.97e-09),
        "face_2": face("rim", "bath", 1.15e-11, 2.1e-05, 1.28e-09, 1.83e-09, 1.97e-09),
    },
    candidate=(2.5e-05, 1.25e-05, 6.25e-06),
    legacy=7.5e-05,
    spacing=7.5e-05,
    potentials=(0.0, 0.002025, 0.005025, 0.007875, 0.01065, 0.012225, 0.01635),
    off_grid_observation=5.9e-05,
)

# A gated junction between capacitor components: three cells, each facing its own region, so every
# capacitor is a component of its own and the two regions that are not the gauge float (free
# offsets).
# The junction's current and its gate read the absolute potentials of both cells, so a potential
# error of
# either component and the gate enter. The first junction's voltage is about 0.1 V (the second
# factor of
# a heat is large there). The second one's is near its threshold (the gate's rates are steepest).
# Currents are small, the first capacitor is large (5e-11 F), the second small (4.2e-13 F, so that
# the
# engine's absolute charge tolerance is its largest share). The legacy family is
# spatial_extracellular@3.
CROSS = dict(
    consumer="jupiter",
    kind="spatial3",
    temperature=298.15,
    gauge="bath",
    p=4,
    end=0.014464,
    tolerance=TOLERANCE,
    cells={
        "cell_0": cell(1.7, 19.4, 214.0, 15.3, -0.0605, 4.45e-09, 0.0113),
        "cell_1": cell(0.052, 0.58, 6.83, 0.47, 0.0545, 4.05e-11, 0.0104),
        "cell_2": cell(0.74, 8.7, 99.3, 6.4, 0.0445, 2.68e-10, 0.0111),
    },
    outside={
        "bath": region(4.4, 620.4, 19.8, 506.0, faces=("cell_0",), decimals=13),
        "cleft": region(1.6, 208.0, 11.2, 171.2, faces=("cell_1",), decimals=13),
        "rim": region(3.7, 525.4, 13.32, 429.2, faces=("cell_2",), decimals=13),
    },
    leaks={
        "cell_0": leak(6.5e-14, 2.9e-13, 1.05e-13),
        "cell_1": leak(7.5e-14, 3.5e-13, 1.15e-13),
        "cell_2": leak(8.5e-14, 2.7e-13, 1.25e-13),
    },
    pumps={
        "cell_0": pump(3.1e-06, 12.1, 0.23, 0.46, 1.75, 0.135, 0.165, -36600.0),
        "cell_1": pump(2.3e-06, 12.1, 0.23, 0.46, 1.75, 0.135, 0.165, -36600.0),
        "cell_2": pump(2.7e-06, 12.1, 0.23, 0.46, 1.75, 0.135, 0.165, -36600.0),
    },
    channels={
        "cell_0": channel(2.35e-13, 0.54, 0.28, 0.67),
        "cell_1": channel(2.85e-13, 0.61, 0.28, 0.67),
        "cell_2": channel(2.55e-13, 0.44, 0.28, 0.67),
    },
    junctions={
        "gap_0": junction(
            "cell_0", "cell_1", 1.35e-10, 1.7e-13, 2.6e-13, 2.3e-13, 0.0138, 0.17, 0.59
        ),
        "gap_1": junction(
            "cell_1", "cell_2", 1.45e-10, 1.9e-13, 2.5e-13, 2.1e-13, 0.0125, 0.14, 0.62
        ),
    },
    faces={
        "face_0": face("bath", "cleft", 3.1e-17, 2.45e-04, 1.31e-09, 1.89e-09, 2.07e-09),
        "face_1": face("cleft", "rim", 3.1e-17, 2.45e-04, 1.31e-09, 1.89e-09, 2.07e-09),
        "face_2": face("rim", "bath", 3.16e-17, 2.45e-04, 1.31e-09, 1.89e-09, 2.07e-09),
    },
    candidate=(1.6e-05, 8e-06, 4e-06),
    legacy=6.4e-05,
    spacing=6.4e-05,
    potentials=(0.0, 0.002176, 0.004352, 0.006528, 0.008704, 0.011136, 0.014464),
)


# Amounts as large against s as the registered ones: small routes, small capacitors, large volumes,
# and
# fixed charges rounded so that each compartment's rule and its declared charge disagree (off_rule).
AMOUNTS = dict(
    consumer="jupiter",
    temperature=298.15,
    gauge="bath",
    p=4,
    end=0.01264,
    tolerance=TOLERANCE,
    cells={
        "cell_0": cell(1.9, 24.7183, 268.4127, 19.3421, -0.0285, 2.1e-10, 0.0117, off=True),
        "cell_1": cell(2.3, 32.2049, 331.1833, 25.3607, -0.0195, 2.6e-10, 0.0107, off=True),
    },
    outside={
        "bath": region(5.2, 722.8169, 29.1411, 608.4283, faces=("cell_0", "cell_1"), off=True),
        "cleft": region(4.7, 620.4137, 27.7291, 526.4719, off=True),
        "rim": region(6.8, 986.1023, 39.7817, 802.4391, off=True),
    },
    leaks={"cell_0": leak(1.3e-11, 3.4e-11, 8.9e-11), "cell_1": leak(1.1e-11, 3.9e-11, 7.8e-11)},
    pumps={
        "cell_0": pump(0.0027, 12.6, 0.22, 0.48, 1.45, 0.115, 0.135, -36700.0),
        "cell_1": pump(0.0034, 12.6, 0.22, 0.48, 1.45, 0.115, 0.135, -36700.0),
    },
    channels={
        "cell_0": channel(6.1e-11, 0.57, 0.26, 0.645),
        "cell_1": channel(5.3e-11, 0.49, 0.26, 0.645),
    },
    junctions={
        "gap": junction("cell_0", "cell_1", 4.6e-11, 1.9e-10, 3.1e-10, 2.8e-10, 0.0145, 0.13, 0.56)
    },
    faces={
        "face_0": face("bath", "cleft", 1.4e-14, 2.6e-04, 1.33e-09, 1.95e-09, 2.06e-09),
        "face_1": face("cleft", "rim", 1.4e-14, 2.6e-04, 1.33e-09, 1.95e-09, 2.06e-09),
        "face_2": face("rim", "bath", 1.4e-14, 2.6e-04, 1.33e-09, 1.95e-09, 2.06e-09),
    },
    candidate=(2e-05, 1e-05, 5e-06),
    legacy=8e-05,
    spacing=8e-05,
    potentials=(0.0, 0.00216, 0.00408, 0.00632, 0.00824, 0.01064, 0.01264),
    off_grid_observation=6.7e-05,
)


def gated_world(
    cells,
    edges,
    schedules,
    *,
    temperature,
    end,
    candidate,
    legacy,
    spacing,
    potentials,
    outside,
    p=4,
    off_grid_observation=None,
):
    """A cluster of cells that face one outside region and are joined by gated junctions: the
    `integrated` kind (no pump, leak or channel)."""
    return dict(
        consumer="integrated",
        temperature=temperature,
        gauge="bath",
        p=p,
        end=end,
        tolerance=TOLERANCE,
        cells=cells,
        outside={"bath": outside},
        leaks={c: leak(0.0, 0.0, 0.0) for c in cells},
        pumps={},
        channels={},
        junctions=edges,
        faces={},
        schedules={"junction": schedules},
        candidate=candidate,
        legacy=legacy,
        spacing=spacing,
        potentials=potentials,
        off_grid_observation=off_grid_observation,
        kind="finite3",
    )


# ------------------------------------------------------------------ the gated clusters (kind
# integrated)

THREE = ("cell_0", "cell_1", "cell_2")
FIVE = (*THREE, "cell_3", "cell_4")
# A schedule with one change (0.01304 s) whose double is one unit in the last place off its k h at
# every
# step, 80, 40 and 20 us, as the registered change at 0.015 s is. Constant elsewhere, and the list
# of
# junctions is in natural order while a text sort of their names would not be (SPEC section 4).
JUNCTION_PATH = [[0.0, 1.0], [0.00464, 0.6], [0.00928, 0.0], [0.01304, 1.0]]
JUNCTIONS = gated_world(
    cells={
        "cell_0": cell(0.43, 4.1, 61.0, 3.6, -0.0235, 2.75e-10, 0.0113),
        "cell_1": cell(0.51, 5.3, 73.6, 4.9, -0.0115, 3.15e-10, 0.0117),
        "cell_2": cell(0.39, 3.5, 56.1, 3.1, 0.0045, 2.45e-10, 0.0109),
        "cell_3": cell(0.62, 6.9, 88.7, 6.4, 0.0165, 3.45e-10, 0.0114),
        "cell_4": cell(0.55, 6.1, 79.9, 5.6, -0.0055, 3.05e-10, 0.0116),
    },
    edges={
        "junction_1": junction(
            "cell_0", "cell_1", 6.4e-11, 5.7e-10, 8.2e-10, 8.6e-10, 0.0115, 0.06, 0.27
        ),
        "junction_2": junction(
            "cell_1", "cell_2", 6.1e-11, 5.7e-10, 8.2e-10, 8.6e-10, 0.0155, 0.09, 0.66
        ),
        "junction_9": junction(
            "cell_2", "cell_3", 5.9e-11, 5.7e-10, 8.2e-10, 8.6e-10, 0.0195, 0.17, 0.94
        ),
        "junction_10": junction(
            "cell_3", "cell_4", 6.6e-11, 5.7e-10, 8.2e-10, 8.6e-10, 0.0115, 0.06, 0.29
        ),
        "junction_11": junction(
            "cell_4", "cell_0", 6.3e-11, 5.7e-10, 8.2e-10, 8.6e-10, 0.0155, 0.09, 0.61
        ),
        "junction_12": junction(
            "cell_1", "cell_3", 5.8e-11, 5.7e-10, 8.2e-10, 8.6e-10, 0.0195, 0.17, 0.89
        ),
    },
    schedules={
        **{j: JUNCTION_PATH for j in ("junction_1", "junction_2", "junction_9", "junction_10")},
        "junction_12": [[0.0, 1.0], [0.00824, 0.35]],
    },
    temperature=295.65,
    end=0.01736,
    candidate=(8e-05, 4e-05, 2e-05),
    legacy=8e-05,
    spacing=8e-05,
    potentials=(0.0, 0.00464, 0.00928, 0.01304, 0.01736),
    outside=region(6.1, 878.4, 29.28, 707.6, faces=FIVE, decimals=13),
    off_grid_observation=3.11e-03,
)

# The IMEX family (p = 2): strong junctions, no schedule, so that its second order is resolved by
# arithmetic (estimate.py) at 96, 48 and 24 us. The legacy runs are RK4 at the same steps, where
# their
# own fourth order is resolved too (SPEC section 8 asks nothing of it).
IMEX_P = (2.04e-08, 3e-08, 3.12e-08)
IMEX = gated_world(
    cells={
        "cell_0": cell(0.47, 4.4, 66.4, 3.9, -0.0265, 2.6e-10, 0.0119),
        "cell_1": cell(0.58, 6.2, 80.4, 5.5, 0.0135, 3.2e-10, 0.0119),
        "cell_2": cell(0.69, 8.1, 95.2, 7.4, -0.0045, 3.7e-10, 0.0119),
    },
    edges={
        "junction_1": junction("cell_0", "cell_1", 6.35e-11, *IMEX_P, 0.0117, 0.07, 0.31),
        "junction_2": junction("cell_1", "cell_2", 5.45e-11, *IMEX_P, 0.0157, 0.11, 0.72),
        "junction_10": junction("cell_2", "cell_0", 7.15e-11, *IMEX_P, 0.0197, 0.19, 0.91),
    },
    schedules={},
    temperature=303.9,
    end=0.01104,
    p=2,
    candidate=(9.6e-05, 4.8e-05, 2.4e-05),
    legacy=9.6e-05,
    spacing=9.6e-05,
    potentials=(0.0, 0.00288, 0.00528, 0.00816, 0.01104),
    outside=region(5.3, 763.2, 25.97, 619.0, faces=THREE, decimals=13),
)

# One change off the grid: 0.0041234 s is 51.54 steps of 80 us (SPEC section 8).
OFFGRID = gated_world(
    cells={
        "cell_0": cell(0.49, 4.9, 69.1, 4.3, -0.0215, 2.85e-10, 0.0106),
        "cell_1": cell(0.54, 5.8, 75.3, 5.1, 0.0085, 2.95e-10, 0.0106),
        "cell_2": cell(0.66, 7.6, 92.4, 6.9, -0.0025, 3.55e-10, 0.0106),
    },
    edges={
        "junction_3": junction(
            "cell_0", "cell_1", 6.7e-11, 6.1e-10, 8.9e-10, 9.2e-10, 0.0122, 0.08, 0.37
        ),
        "junction_4": junction(
            "cell_1", "cell_2", 5.6e-11, 6.1e-10, 8.9e-10, 9.2e-10, 0.0172, 0.13, 0.81
        ),
    },
    schedules={"junction_3": [[0.0, 1.0], [0.0041234, 0.45]]},
    temperature=294.3,
    end=0.01128,
    candidate=(8e-05,),
    legacy=8e-05,
    spacing=8e-05,
    potentials=(0.0, 0.00472, 0.00824, 0.01128),
    outside=region(5.4, 777.6, 25.92, 631.8, faces=THREE, decimals=13),
)

# The stop: RK4 at 80 us leaves an energy residual that estimate.py puts above the inner model's RK4
# allowance (2e-8 pJ) and below legacy's (1e-6 pJ). Both are read in the snapshot. Legacy runs at
# 20,
# 10 and 5 us, where the residual is far below both.
STOP_P = (3.3e-07, 5e-07, 5.2e-07)
STOP = gated_world(
    cells={
        "cell_0": cell(0.45, 4.2, 63.9, 3.7, -0.0255, 2.55e-10, 0.0107),
        "cell_1": cell(0.61, 6.6, 84.3, 5.9, 0.0125, 3.35e-10, 0.0107),
    },
    edges={"junction_5": junction("cell_0", "cell_1", 6.15e-11, *STOP_P, 0.0127, 0.105, 0.83)},
    schedules={"junction_5": [[0.0, 0.02], [0.00464, 1.0]]},
    temperature=302.6,
    end=0.00888,
    candidate=(8e-05,),
    legacy=2e-05,
    spacing=8e-05,
    potentials=(0.0, 0.00464, 0.00672, 0.00888),
    outside=region(5.6, 806.4, 27.44, 652.4, faces=("cell_0", "cell_1"), decimals=13),
)

# A schedule whose block omits defaults ([[0.0, 1.0]] throughout) that a party that reads a parsed
# definition writes out, and one whose block writes out defaults that such a party omits (a pump's
# schedule on a membrane whose pump is null) or keeps (a schedule with a repeated value).
DEFAULT_OMITTED = gated_world(
    cells={
        "cell_0": cell(0.52, 5.2, 72.6, 4.7, -0.0245, 2.9e-10, 0.0103),
        "cell_1": cell(0.57, 6.3, 78.7, 5.4, 0.0115, 3.25e-10, 0.0103),
        "cell_2": cell(0.63, 7.1, 87.9, 6.2, -0.0035, 3.4e-10, 0.0103),
    },
    edges={
        "junction_6": junction(
            "cell_0", "cell_1", 6.2e-11, 5.3e-10, 7.9e-10, 8.1e-10, 0.0128, 0.11, 0.42
        ),
        "junction_7": junction(
            "cell_1", "cell_2", 5.7e-11, 5.3e-10, 7.9e-10, 8.1e-10, 0.0158, 0.16, 0.77
        ),
    },
    schedules={"junction_6": [[0.0, 1.0], [0.00408, 0.55]]},
    temperature=297.2,
    end=0.00936,
    candidate=(8e-05, 4e-05, 2e-05),
    legacy=8e-05,
    spacing=8e-05,
    potentials=(0.0, 0.00472, 0.00936),
    outside=region(5.8, 835.2, 27.84, 675.0, faces=THREE, decimals=13),
)
DEFAULT_WRITTEN = dict(
    DEFAULT_OMITTED,
    cells={
        "cell_0": cell(0.44, 4.6, 62.7, 3.8, -0.0225, 2.65e-10, 0.0104),
        "cell_1": cell(0.59, 6.7, 81.9, 5.7, 0.0105, 3.3e-10, 0.0104),
        "cell_2": cell(0.68, 7.9, 94.1, 6.7, -0.0075, 3.65e-10, 0.0104),
    },
    outside={"bath": region(5.1, 734.4, 24.48, 592.6, faces=THREE, decimals=13)},
    junctions={
        "junction_6": junction(
            "cell_0", "cell_1", 6.9e-11, 5.9e-10, 8.4e-10, 8.7e-10, 0.0132, 0.12, 0.47
        ),
        "junction_7": junction(
            "cell_1", "cell_2", 6.45e-11, 5.9e-10, 8.4e-10, 8.7e-10, 0.0162, 0.15, 0.73
        ),
    },
    schedules={
        "junction": {
            "junction_6": [[0.0, 1.0], [0.00472, 0.65]],
            "junction_7": [[0.0, 1.0], [0.00368, 1.0]],
        }
    },
    temperature=296.9,
    end=0.00952,
    potentials=(0.0, 0.00472, 0.00952),
)

# ------------------------------------------------------------------ the assembly worlds (kinds
# cell, base)

CELL = dict(
    consumer="cell",
    kind="finite2",
    temperature=298.15,
    gauge="bath",
    p=4,
    end=0.01648,
    tolerance=TOLERANCE,
    cells={"cell_0": cell(1.14, 14.3, 157.0, 11.2, -0.0725, 9.2e-10, 0.0109)},
    outside={"bath": region(1.25, 171.0, 5.5, 145.0, faces=("cell_0",), decimals=13)},
    leaks={"cell_0": leak(4.4e-10, 1.9e-09, 1.6e-10)},
    pumps={"cell_0": pump(0.088, 11.8, 0.26, 0.52, 1.55, 0.125, 0.145, -36200.0)},
    channels={"cell_0": channel(9.1e-09, 0.92, 0.23, 0.78)},
    junctions={},
    faces={},
    candidate=(2e-05, 1e-05, 5e-06),
    legacy=8e-05,
    summaries=(0.01648,),
    pools={
        "cell_0": dict(
            stream=0,
            pool=pool([0, 1, 2, 10, 12], 57, 6.3e-15, 1.2e7, 170.0, 24.0, 1.6, 16, 0.01648, 80000),
            seeds=(70120435, 70120441),
        )
    },
    # An observation before the end, as the captured definition has one; the comparison reads the
    # end.
    observations=(0.0, 0.00824, 0.01648),
)
BASE = dict(
    consumer="base",
    temperature=298.15,
    gauge="bath",
    p=4,
    end=0.01548,
    tolerance=TOLERANCE,
    cells={
        "cell_0": cell(0.58, 6.7, 77.9, 4.9, -0.0545, 3.1e-10, 0.0115),
        "cell_1": cell(0.79, 11.4, 102.0, 7.7, -0.0385, 3.8e-10, 0.0122),
    },
    outside={
        "bath": region(2.1, 289.8, 9.24, 235.2, faces=("cell_0", "cell_1"), decimals=13),
        "cleft": region(1.3, 163.8, 8.97, 141.7),
        "rim": region(3.2, 460.8, 11.52, 374.4),
    },
    leaks={"cell_0": leak(1.6e-11, 2.2e-10, 7.9e-11), "cell_1": leak(1.2e-11, 2.7e-10, 9.1e-11)},
    pumps={
        "cell_0": pump(0.053, 12.7, 0.28, 0.47, 1.65, 0.105, 0.155, -36900.0),
        "cell_1": pump(0.087, 12.7, 0.28, 0.47, 1.65, 0.105, 0.155, -36900.0),
    },
    channels={
        "cell_0": channel(3.1e-10, 0.48, 0.21, 0.68),
        "cell_1": channel(2.8e-10, 0.63, 0.21, 0.68),
    },
    junctions={
        "gap": junction("cell_0", "cell_1", 1.2e-10, 2.8e-10, 4.7e-10, 3.9e-10, 0.0142, 0.16, 0.57)
    },
    faces={
        "face_0": face("bath", "cleft", 1.25e-11, 2.2e-05, 1.26e-09, 1.87e-09, 2.03e-09),
        "face_1": face("cleft", "rim", 1.25e-11, 2.2e-05, 1.26e-09, 1.87e-09, 2.03e-09),
        "face_2": face("rim", "bath", 1.25e-11, 2.2e-05, 1.26e-09, 1.87e-09, 2.03e-09),
    },
    candidate=(2e-05, 1e-05, 5e-06),
    legacy=6e-05,
    summaries=(0.00474, 0.01026, 0.01548),
    pools={
        "cell_0": dict(
            stream=0,
            pool=pool([3, 4, 5, 13, 15], 44, 4.6e-15, 1.4e7, 1350.0, 260.0, 1.3, 6, 0.01548, 70000),
            seeds=(70321533, 70421533),
            root=13,
        ),
        "cell_1": dict(
            stream=1,
            pool=pool(
                [11, 13, 15, 17, 19], 53, 5.7e-15, 1.1e7, 1150.0, 310.0, 1.9, 6, 0.01548, 70000
            ),
            seeds=(70321534, 70421534),
            root=11,
        ),
    },
)

WORLDS = {
    "inv_cluster": CLUSTER,
    "inv_release": released(CLUSTER, 0.004104, 0.008208),
    "inv_bound": released(BOUND, 0.005025, 0.01065),
    "inv_cross": CROSS,
    "inv_amounts": AMOUNTS,
    "inv_junctions": JUNCTIONS,
    "inv_imex": IMEX,
    "inv_offgrid": OFFGRID,
    "inv_stop": STOP,
    "inv_default_omitted": dict(DEFAULT_OMITTED, controls_style="omit"),
    "inv_default_written": dict(DEFAULT_WRITTEN, controls_style="write"),
    "inv_cell": CELL,
    "inv_base": BASE,
}


# ------------------------------------------------------------------ the block (SPEC section 2.5)


def names(world):
    """(membrane of a cell, channel of a cell): `membrane_0`, `channel_0` for the first cell, on."""
    cells = list(world["cells"])
    return (
        {c: f"membrane_{i}" for i, c in enumerate(cells)},
        {c: f"channel_{i}" for i, c in enumerate(cells) if c in world["channels"]},
    )


def schedules_of(world, family, entities):
    given = world.get("schedules", {}).get(family, {})
    return {e: [list(p) for p in given.get(k, ON)] for e, k in entities.items()}


def region_charge(world, name):
    faced = [world["cells"][c]["charge"] for c in world["outside"][name]["faces"]]
    return rules.countercharge(faced) if faced else 0.0


def region_fixed(world, name):
    r = world["outside"][name]
    if r["off"]:
        return off_rule(r["amounts"], region_charge(world, name))
    if r["decimals"] is None:  # A region that no membrane faces: the short decimal of its own sum.
        return fixed(r["amounts"], 0.0, 12)
    return fixed(r["amounts"], region_charge(world, name), r["decimals"])


def block(world):
    """The world's ionic block, in inputs.json's form."""
    membrane, chan = names(world)
    cells, outside, membranes, channels, junctions, faces = {}, {}, {}, {}, {}, {}
    for c, v in world["cells"].items():
        cells[c] = dict(
            volume_pL=v["volume"],
            initial_amount_fmol=dict(v["amounts"]),
            fixed_charge_equivalent_fmol=v["fixed"],
            initial_voltage_V=v["voltage"],
            initial_charge_C=v["charge"],
        )
    for o, v in world["outside"].items():
        outside[o] = dict(
            volume_pL=v["volume"],
            initial_amount_fmol=dict(v["amounts"]),
            fixed_charge_equivalent_fmol=region_fixed(world, o),
            initial_charge_C=region_charge(world, o),
        )
    faced = {c: o for o, v in world["outside"].items() for c in v["faces"]}
    for c, v in world["cells"].items():
        p = world["pumps"].get(c)
        membranes[membrane[c]] = dict(
            inside=c,
            outside=faced[c],
            area_m2=v["area"],
            capacitance_F=v["cap"],
            passive=dict(law="constant_field", permeability_m_per_s=dict(world["leaks"][c])),
            pump=None
            if p is None
            else dict(
                law="nak_pump_positive",
                roles={"sodium": "Na", "potassium": "K"},
                stoichiometry={"Na": -3, "K": 2},
                capacity_fmol_per_s=p["capacity"],
                km_na_mM=p["km_na"],
                km_k_mM=p["km_k"],
                km_atp_mM=p["km_atp"],
                metabolism=dict(
                    kind="maintained_fuel",
                    atp_mM=p["atp"],
                    adp_mM=p["adp"],
                    pi_mM=p["pi"],
                    delta_g0_J_per_mol=p["dg0"],
                ),
            ),
        )
        if c in chan:
            k = world["channels"][c]
            channels[chan[c]] = dict(
                membrane_id=membrane[c],
                species_id="K",
                kinetic_law="kv15_mh",
                max_permeability_m_per_s=k["p_max"],
                abundance=k["abundance"],
                initial_gate={"m": k["m"], "h": k["h"]},
            )
    for j, v in world["junctions"].items():
        junctions[j] = dict(
            from_cell=v["a"],
            to_cell=v["b"],
            area_m2=v["area"],
            permeability_m_per_s=dict(v["perm"]),
            gate=dict(
                initial_gate=v["g0"],
                law="junction_relaxation",
                minimum_open_fraction=v["lo"],
                threshold_voltage_V=v["thr"],
            ),
        )
    for f, v in world["faces"].items():
        faces[f] = dict(
            sender=v["a"],
            receiver=v["b"],
            area_m2=v["area"],
            length_m=v["length"],
            diffusivity_m2_per_s=dict(v["diff"]),
            law="logmean_face",
        )
    membrane_ids = {membrane[c]: c for c in world["cells"]}
    controls = dict(
        leak=schedules_of(world, "leak", membrane_ids),
        pump=schedules_of(
            world, "pump", {m: c for m, c in membrane_ids.items() if c in world["pumps"]}
        )
        or [],
        channel=(
            "the pool's path (SPEC.md section 3.2)"
            if world["consumer"] in ("cell", "base")
            else schedules_of(world, "channel", {chan[c]: c for c in chan}) or []
        ),
        junction=schedules_of(world, "junction", {j: j for j in world["junctions"]}) or [],
    )
    style = world.get("controls_style")
    if style == "omit":  # The defaults go: a leak schedule of 1 throughout, and a junction's.
        first = next(iter(controls["leak"]))
        controls["leak"] = {m: v for m, v in controls["leak"].items() if m == first}
        controls["junction"] = {j: v for j, v in controls["junction"].items() if v != ON}
    elif style == "write":  # A pump's schedule on membranes that have no pump.
        controls["pump"] = {m: [list(p) for p in ON] for m in membrane_ids}
    return dict(
        temperature_K=world["temperature"],
        species=dict(SPECIES),
        cells=cells,
        outside=outside,
        closure=dict(gauge_reference=world["gauge"]),
        membranes=membranes,
        channels=channels or [],
        junctions=junctions or [],
        faces=faces or [],
        controls=controls,
        material_tolerance_fmol=dict(world["tolerance"]),
        end_s=world["end"],
    )


# ------------------------------------------------------------------ the legacy definition


def legacy(world, step, *, observations):
    """The legacy definition at one step, in the captured form."""
    b = block(dict(world, controls_style=None))
    membrane, chan = names(world)
    kind = world.get("kind", "spatial2")
    model_id = {
        "spatial2": "spatial_extracellular@2",
        "spatial3": "spatial_extracellular@3",
        "finite2": "finite_extracellular@2",
        "finite3": "finite_extracellular@3",
    }[kind]
    cells = []
    for c, v in world["cells"].items():
        m, i = b["membranes"][membrane[c]], list(world["cells"]).index(c)
        pump_block = m["pump"]
        cells.append(
            dict(
                cell=dict(
                    id=c,
                    volume_pL=v["volume"],
                    initial_amount_fmol=dict(v["amounts"]),
                    initial_voltage_V=v["voltage"],
                    fixed_charge_equivalent_fmol=v["fixed"],
                ),
                channel=None
                if c not in chan
                else dict(
                    id=chan[c],
                    membrane_id=membrane[c],
                    species_id="K",
                    kinetic_law="kv1p5_mh@1",
                    max_permeability_m_per_s=world["channels"][c]["p_max"],
                    abundance=world["channels"][c]["abundance"],
                    initial_gate={"m": world["channels"][c]["m"], "h": world["channels"][c]["h"]},
                ),
                membrane=dict(
                    id=membrane[c],
                    inside=c,
                    outside=m["outside"],
                    area_m2=v["area"],
                    specific_capacitance_F_per_m2=v["specific"],
                    passive=dict(
                        law="constant_field@1", permeability_m_per_s=dict(world["leaks"][c])
                    ),
                    pump=None
                    if pump_block is None
                    else dict(
                        id=f"pump_{i}",
                        law="nak_atp_mass_action_positive@1",
                        roles=dict(pump_block["roles"]),
                        stoichiometry=dict(pump_block["stoichiometry"]),
                        capacity_fmol_per_s=pump_block["capacity_fmol_per_s"],
                        km_na_mM=pump_block["km_na_mM"],
                        km_k_mM=pump_block["km_k_mM"],
                        km_atp_mM=pump_block["km_atp_mM"],
                        metabolism=dict(
                            pump_block["metabolism"], kind="maintained_chemical_reservoirs@1"
                        ),
                    ),
                ),
            )
        )
    outside = {
        o: dict(
            id=o,
            volume_pL=v["volume_pL"],
            initial_amount_fmol=dict(v["initial_amount_fmol"]),
            fixed_charge_equivalent_fmol=v["fixed_charge_equivalent_fmol"],
        )
        for o, v in b["outside"].items()
    }
    local = next(o for o, v in world["outside"].items() if v["faces"])
    model = dict(
        id=model_id,
        species=[dict(id=x, valence=z) for x, z in SPECIES.items()],
        temperature_K=world["temperature"],
        extracellular=outside[local],
        cells=cells,
        junctions=[
            dict(
                id=j,
                from_cell=v["a"],
                to_cell=v["b"],
                area_m2=v["area"],
                permeability_m_per_s=dict(v["perm"]),
                gate=dict(
                    law="junction_voltage_relaxation@1",
                    threshold_voltage_V=v["thr"],
                    minimum_open_fraction=v["lo"],
                    initial_gate=v["g0"],
                ),
            )
            for j, v in world["junctions"].items()
        ],
    )
    execution = dict(
        backend="cpu",
        precision="float64",
        solver="rk4",
        jit=True,
        dt=step,
        max_steps=10000,
        max_trace_bytes=268435456,
        material_balance_atol_fmol=dict(world["tolerance"]),
        capacity=len(cells) + 1,
        membrane_capacity=len(cells) + 2,
        channel_capacity=len(chan) + (1 if chan else 0),
        edge_capacity=len(world["junctions"]) + (1 if world["junctions"] else 0),
        extracellular_capacity=len(outside) + 2,
    )
    if kind in ("spatial2", "spatial3"):
        law, solver = {
            "spatial2": (
                "capacitive_components_current_continuity@1",
                "gauged_dense_kirchhoff@1",
            ),
            "spatial3": ("capacitive_regions_ghk_return_current@1", "gauged_damped_newton@1"),
        }[kind]
        model.update(
            closure=dict(law=law, gauge_reference=world["gauge"]),
            surroundings=[outside[o] for o in outside if o != local],
            faces=[
                dict(
                    id=f,
                    sender=v["a"],
                    receiver=v["b"],
                    area_m2=v["area"],
                    length_m=v["length"],
                    diffusivity_m2_per_s=dict(v["diff"]),
                    law="logmean_electrodiffusion@1",
                )
                for f, v in world["faces"].items()
            ],
        )
        execution.update(field_solver=solver, face_capacity=len(world["faces"]) + 1)
    else:
        execution["extracellular_capacity"] = 1
    controls = b["controls"]

    membrane_controls = []
    for c in world["cells"]:
        mid = membrane[c]
        membrane_controls.append(
            dict(
                membrane_id=mid,
                leak=[
                    dict(time=t, multipliers={x: v for x in SPECIES})
                    for t, v in controls["leak"].get(mid, ON)
                ],
                pump=[
                    dict(time=t, multiplier=v)
                    for t, v in (controls["pump"].get(mid, ON) if controls["pump"] else ON)
                ],
            )
        )
    return dict(
        schema_version=1,
        model=model,
        experiment=dict(
            end_time=world["end"],
            observation_times=list(observations),
            membrane_controls=membrane_controls,
            channel_controls=[
                dict(
                    channel_id=chan[c],
                    schedule=[
                        dict(time=t, availability=v)
                        for t, v in (
                            controls["channel"][chan[c]]
                            if isinstance(controls["channel"], dict)
                            and chan[c] in controls["channel"]
                            else ON
                        )
                    ],
                )
                for c in chan
            ],
            junction_controls=[
                dict(
                    junction_id=j,
                    schedule=[
                        dict(time=t, open_fraction=v) for t, v in controls["junction"].get(j, ON)
                    ],
                )
                for j in world["junctions"]
            ],
        ),
        execution=execution,
    )


# ------------------------------------------------------------------ the pools


def pool_block(world, cell_id):
    """The pool's block in inputs.json's form, its defaults written out."""
    entry = world["pools"][cell_id]
    v = entry["pool"]
    nodes = list(v["nodes"])
    root = entry.get("root", 10)
    return dict(
        model="pool_model",
        topology="pool_topology",
        initial_nodes=nodes,
        initial_bond_indices=bonds_of(nodes),
        root_node=root,
        initial_free_trimers=v["free"],
        pool_volume_L=v["volume"],
        k_on_M_inv_s=v["on"],
        k_close_s_inv=v["close"],
        k_off_s_inv=v["off"],
        k_fragment_dissolve_s_inv=v["dissolve"],
        world_id_start=0,
        worlds=v["worlds"],
        end_time_s=v["end"],
        max_events_per_world=v["max_events"],
    )


# The dodecahedron's edges as the pool's own graph orders them (the generalised Petersen graph
# G(10,2):
# outer i to i + 1, spoke i to i + 10, inner i + 10 to (i + 2) mod 10 + 10), written again here.
EDGES = sorted(
    {
        tuple(sorted(e))
        for i in range(10)
        for e in ((i, (i + 1) % 10), (i, i + 10), (i + 10, (i + 2) % 10 + 10))
    }
)


def bonds_of(nodes):
    s = set(nodes)
    return [i for i, (a, b) in enumerate(EDGES) if a in s and b in s]


HARNESS = dict(
    event_chunk_size=128, recording="summary", max_output_bytes=268435456, max_wall_seconds=600.0
)


def legacy_pool(world, cell_id, seed, *, cluster):
    """The legacy pool definition in the captured form: defaults left out as in the captured ones,
    but for a root other than the default."""
    b = pool_block(world, cell_id)
    out = dict(
        model="finite_bond_assembly@1",
        initial_nodes=b["initial_nodes"],
        initial_free_trimers=b["initial_free_trimers"],
        pool_volume_L=b["pool_volume_L"],
        k_on_M_inv_s=b["k_on_M_inv_s"],
        k_close_s_inv=b["k_close_s_inv"],
        k_off_s_inv=b["k_off_s_inv"],
        k_fragment_dissolve_s_inv=b["k_fragment_dissolve_s_inv"],
        worlds=b["worlds"],
        end_time_s=b["end_time_s"],
        event_chunk_size=HARNESS["event_chunk_size"],
        max_events_per_world=b["max_events_per_world"],
        max_wall_seconds=HARNESS["max_wall_seconds"],
        recording=HARNESS["recording"],
        max_output_bytes=HARNESS["max_output_bytes"],
    )
    if b["root_node"] != 10:
        out["root_node"] = b["root_node"]
    if cluster:
        out["world_id_start"] = 0
    out["seed"] = seed
    return out


COUPLING = dict(
    law="root_component_has_cycle@1", inactive_availability=0.0, active_availability=1.0
)


def legacy_assembly(world, step, seed_index):
    ionic = legacy(world, step, observations=world.get("observations", (0.0, *world["summaries"])))
    if world["consumer"] == "cell":
        (c,) = world["pools"]
        return dict(
            model="assembly_regulated_cell@1",
            pool=legacy_pool(world, c, world["pools"][c]["seeds"][seed_index], cluster=False),
            ionic=ionic,
            coupling=dict(COUPLING),
            window_ticks=32,
        )
    return dict(
        model="assembly_regulated_cluster@1",
        pools=[
            dict(
                cell_id=c,
                stream_id=e["stream"],
                pool=legacy_pool(world, c, e["seeds"][seed_index], cluster=True),
                coupling=dict(COUPLING),
            )
            for c, e in world["pools"].items()
        ],
        ionic=ionic,
        window_ticks=32,
    )


# ------------------------------------------------------------------ the runs (SPEC section 4,
# section 8)

SEEDS, IDS = 2, 4  # Two seeds and the world IDs 0 to 3 of each are the ionic judged families.
POOL_RESTART = {"inv_cell": 0.00744, "inv_base": 0.00666}
IONIC_RESTART = {
    "inv_cluster": 0.007056,
    "inv_junctions": 0.00776,
    "inv_cell": ("s1 w1", 0.00824),
    "inv_base": ("s0 w2", 0.00774),
}
UNKNOWN = "inv_unknown_junction_law"  # A label of no law: an unknown label passes through as it is.


def run(
    name,
    world,
    *,
    family=None,
    seed=None,
    world_id=None,
    step=None,
    role="judged",
    variant=None,
    change=None,
):
    out = dict(
        name=name,
        consumer=WORLDS[world]["consumer"],
        family=family,
        world=world,
        seed_index=seed,
        world_id=world_id,
        step_s=step,
        role=role,
        variant=variant,
    )
    if change is not None:
        out["declared_change"] = change
    return out


def runs():
    out = []
    for w, world in WORLDS.items():
        if world["consumer"] in ("cell", "base"):
            continue
        single = len(world["candidate"]) == 1
        for h in world["candidate"]:
            out.append(run(f"{w} h={h!r}", w, family=None if single else w, step=h))
    for w in ("inv_cluster", "inv_junctions"):
        h = WORLDS[w]["candidate"][0]
        out.append(
            run(
                f"{w} h={h!r} restart",
                w,
                step=h,
                role="support",
                variant=f"restart at {IONIC_RESTART[w]!r}",
            )
        )
    # The engine plants of the jupiter kind: both channels' maximal permeability x 1.01, as a
    # declared
    # change and, in the other world, by the registered variant alone.
    channels = WORLDS["inv_cluster"]["channels"]
    h3 = WORLDS["inv_cluster"]["candidate"][2]
    out.append(
        run(
            "inv_cluster plant channel",
            "inv_cluster",
            family="inv_cluster",
            step=h3,
            role="plant",
            variant="inv_EP1",
            change=[
                {
                    "path": ["channels", f"channel_{i}", "max_permeability_m_per_s"],
                    "value": v["p_max"] * 1.01,
                }
                for i, v in enumerate(channels.values())
            ],
        )
    )
    out.append(
        run(
            "inv_release plant channel",
            "inv_release",
            family="inv_release",
            step=h3,
            role="plant",
            variant="EP1",
        )
    )
    # A refusal of each kind (TABLE section 4) on the world with a schedule. Each is one run, and no
    # family. `harness` is made by the driver's clock (README).
    h = WORLDS["inv_junctions"]["candidate"][1]

    def refuse(kind, change):
        return run(
            f"inv_junctions refused {kind}",
            "inv_junctions",
            step=h,
            variant=f"refused {kind}",
            change=change,
        )

    out.append(
        refuse(
            "definition", [{"path": ["junctions", "junction_2", "gate", "law"], "value": UNKNOWN}]
        )
    )
    out.append(refuse("domain", [{"path": ["temperature_K"], "value": 150.0}]))
    out.append(
        run("inv_junctions refused harness", "inv_junctions", step=h, variant="refused harness")
    )
    for w in ("inv_cell", "inv_base"):
        world = WORLDS[w]
        for s in range(SEEDS):
            out.append(run(f"{w} s{s} pool", w, seed=s, variant="pool"))
        out.append(
            run(
                f"{w} s0 pool restart",
                w,
                seed=0,
                role="support",
                variant=f"pool restart at {POOL_RESTART[w]!r}",
            )
        )
        for s in range(SEEDS):
            for k in range(IDS):
                for h in world["candidate"]:
                    out.append(
                        run(
                            f"{w} s{s} w{k} h={h!r}",
                            w,
                            family=f"{w} s{s} w{k}",
                            seed=s,
                            world_id=k,
                            step=h,
                            variant="ionic",
                        )
                    )
        fam, at = IONIC_RESTART[w]
        s, k = (int(v[1:]) for v in fam.split())
        h = world["candidate"][0]
        out.append(
            run(
                f"{w} {fam} h={h!r} restart",
                w,
                seed=s,
                world_id=k,
                step=h,
                role="support",
                variant=f"restart at {at!r}",
            )
        )
    h3 = WORLDS["inv_base"]["candidate"][2]
    fam = "inv_base s0 w2"
    out.append(
        run(
            "inv_base plant swapped",
            "inv_base",
            family=fam,
            seed=0,
            world_id=2,
            step=h3,
            role="plant",
            variant="inv_EP2",
            change=[{"exchange_channels": ["cell_0", "cell_1"]}],
        )
    )
    out.append(
        run(
            "inv_base plant swapped by variant",
            "inv_base",
            family=fam,
            seed=0,
            world_id=2,
            step=h3,
            role="plant",
            variant="EP2",
        )
    )
    return out


# ------------------------------------------------------------------ the inputs file


def inputs():
    worlds = {}
    for name, w in WORLDS.items():
        b = block(w)
        out = dict(consumer=w["consumer"], ionic=b)
        if w["consumer"] in ("jupiter", "integrated"):
            out["history_times"] = dict(first_s=0.0, last_s=w["end"], spacing_s=w["spacing"])
            out["potential_times_s"] = list(w["potentials"])
        else:
            out["final_s"] = w["end"]
            out["summary_times_s"] = list(w["summaries"])
            out["pools"] = {
                c: dict(
                    channel=f"channel_{list(w['cells']).index(c)}",
                    stream_id=e["stream"],
                    pool=pool_block(w, c),
                    harness=dict(HARNESS),
                    seeds=list(e["seeds"]),
                )
                for c, e in w["pools"].items()
            }
            out["coupling"] = dict(law="assembly_observable", active=1.0, inactive=0.0)
        derived = rules.derived(w["consumer"], b)
        out["scales"] = derived["scales"]
        out["p"] = w["p"]
        out["amount_refs"] = derived["amount_refs"]
        out["closure_terms_V"] = derived["closure_terms_V"]
        worlds[name] = out
    return dict(
        schema="ensemble-reexpression inputs, version 1",
        part=1,
        constants=dict(F_C_per_mol=rules.F, R_J_per_mol_K=rules.R, fmol_to_mol=rules.FMOL),
        worlds=worlds,
        runs=runs(),
    )


# ------------------------------------------------------------------ the legacy origin


def jobs(only=None):
    """The job list of capture.sh, as capture_worlds.py writes one: (job, kind, definition, ...)."""
    out = []
    for w, world in WORLDS.items():
        if only and w not in only:
            continue
        for step, k in (("h", 1), ("h2", 2), ("h4", 4)):
            dt = world["legacy"] / k
            if world["consumer"] in ("jupiter", "integrated"):
                out.append(
                    dict(
                        job=f"{w}-{step}",
                        kind="ionic",
                        definition=f"science/ionic/{w}/{step}.json",
                        world=w,
                        step=step,
                        order=rules.grid_steps(world["end"], dt),
                    )
                )
                continue
            for s in range(SEEDS):
                command = "assembly-cell" if world["consumer"] == "cell" else "assembly-cluster"
                out.append(
                    dict(
                        job=f"{w}-{step}-s{s}",
                        kind="assembly",
                        command=command,
                        definition=f"science/assembly/{w}/{step}-s{s}.json",
                        world=w,
                        step=step,
                        seed_index=s,
                        ticks=rules.grid_steps(world["end"], dt),
                        order=(10**6 if command == "assembly-cell" else 10**5)
                        + rules.grid_steps(world["end"], dt),
                    )
                )
    return out


def observations(world):
    out = [0.0, *[t for t in world["potentials"] if t]]
    if world.get("off_grid_observation"):
        out.append(world["off_grid_observation"])
    return sorted(out)


def definition(name, step):
    world, dt = WORLDS[name], WORLDS[name]["legacy"] / {"h": 1, "h2": 2, "h4": 4}[step]
    return legacy(world, dt, observations=observations(world))


def snapshot_record(snapshot):
    """The snapshot's own manifest, as the captured origin's manifest holds it."""
    manifest = Path(snapshot) / "SNAPSHOT.json"
    value = json.loads(manifest.read_text())
    return dict(
        path=str(snapshot),
        git_revision=value["git_revision"],
        clean=value["selected_status_porcelain_v1_z"] == "",
        patch_sha256=value["patch_sha256"],
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
    )


def origin(folder, snapshot, *only):
    """The legacy definitions, job list and manifest of every world, or of the named ones."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    for job in jobs(only):
        w, world = job["world"], WORLDS[job["world"]]
        path = folder / job["definition"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if job["kind"] == "ionic":
            value = dict(name=job["step"], definition=definition(w, job["step"]))
        else:
            dt = world["legacy"] / {"h": 1, "h2": 2, "h4": 4}[job["step"]]
            value = legacy_assembly(world, dt, job["seed_index"])
        path.write_text(json.dumps(value, indent=1, allow_nan=False) + "\n")
    ordered = sorted(jobs(only), key=lambda j: -j["order"])
    (folder / "jobs-science.json").write_text(json.dumps(ordered, indent=1) + "\n")
    (folder / "manifest.json").write_text(
        json.dumps(
            dict(
                kind="cells.legacy_rehearsal@1",
                utc=datetime.now(UTC).isoformat(timespec="seconds"),
                made_by="validation/ensemble_reexpression/rehearsal/make_inputs.py",
                snapshot=snapshot_record(snapshot),
                worlds={
                    w: dict(
                        kind=WORLDS[w].get("kind", "spatial2"),
                        consumer=WORLDS[w]["consumer"],
                        steps_s=[WORLDS[w]["legacy"] / k for k in (1, 2, 4)],
                        step_counts=[
                            rules.grid_steps(WORLDS[w]["end"], WORLDS[w]["legacy"] / k)
                            for k in (1, 2, 4)
                        ],
                        seeds=[
                            [e["seeds"][i] for e in WORLDS[w]["pools"].values()]
                            for i in range(SEEDS)
                        ]
                        if "pools" in WORLDS[w]
                        else None,
                    )
                    for w in sorted(only or WORLDS)
                },
                files_sha256={
                    str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(folder.rglob("*.json"))
                    if p.name != "manifest.json"
                },
            ),
            indent=1,
        )
        + "\n"
    )
    print(f"{len(ordered)} jobs in {folder}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["write"]:
        target = rules.HERE / "inputs_rehearsal.json"
        target.write_text(json.dumps(inputs(), indent=1, allow_nan=False) + "\n")
        print(target)
    elif sys.argv[1:2] == ["origin"]:
        origin(*sys.argv[2:])
    else:
        raise SystemExit(__doc__)
