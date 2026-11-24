"""FR-38's second registered comparison: the judge's reader (CRITERIA.md C0; D334, D308, D323).

The reader is the judge's only path to the references' values. It reads each file of the code-blind
references (validation/gene_regulation/fr38_v2/references/out/) by structure, from the spec folder
alone: SPEC.md §7's layout, amendment 1's route-2 and survival entries and the blank's contents,
and amendment 2's layout rulings. Its first read is the references' invented file,
`reference_invented.json`, before any engine run and before any real reference is read.

**C0, as the reader applies it.** It refuses a file on any fault and names each one. A refusal is
never read as a gap.
- **Layout.** Every registered key is present: SPEC.md §7's, with amendment 1's `route2` and
  survival entries. Keys it does not know are ignored (amendment 2, Q6), `hash_seeds_checked`
  among them. The blank carries `series` and `checks` only (amendment 1, item 3).
- **Units:** SPEC.md §7's `units`, with copy_fmol the double 1.6605390671738468e-09.
- **Times.** `times_s` is the family's grid exactly and `samples_s` its sample times. Every series
  has one entry per output time, in order. Every run, and every readout of READOUTS.md §1 and §2
  for its family, is present.
- **Classes,** entry by entry and both ways, against SPEC.md §4's rules and amendment 1's (for
  `released_present_gross`, route 2 and survival). A `constant` entry stands where the rules require
  one and nowhere else; its value is +0.0 by its bits and its accuracy null. Every other entry is
  `stepped`, with a finite value and a finite, non-negative accuracy. `spread`, and any other
  class, is refused (CRITERIA.md §2).
- **Accuracy.** Every judged stepped entry (READOUTS.md §4) has accuracy <= 1e-11 s_y. s_y is
  recomputed here by READOUTS.md §3 from the file's own values, and the file's `scale` is held to
  it within SCALE_RTOL. Route 2 is judged against its own scale (amendment 1, item 1), a survival
  ratio against 1. A constant entry's scale is never read.
- **Inputs** (the lead's echo rule, 24 November 2026). In the five registered families every
  echoed input is checked by name against SPEC.md's (or A1's sheet's) stated value, to 1e-12
  relative. The names are the references agent's, which the lead read from the files (names only)
  before the reader's tag; README.md maps each to its SPEC.md quantity. A stated value the file
  lacks is a refusal; a file key with no stated value is listed in the read's summary as unchecked,
  never refused. The invented family's inputs are checked for their own consistency: grid, window,
  sample times and runs.
- **Values.** Every number is finite. NaN and the infinities are refused at the parse.
- **The file's own definitions,** cross-checked:
  - `released_present_gross` is the sum of its three classes;
  - the five classes sum to their row within their accuracies;
  - route 2's and survival's counts are the `win` class at their times, bit for bit, with its
    accuracy;
  - the excess over the blank is the row minus the blank's, within their accuracies;
  - each plant's relative distance is |planted − honest| / scale.

**Reported, not refused:**
- the plants' sizing against CRITERIA.md §6's 10x rule;
- the references' own checks and method differences;
- the echoed inputs not checked by name.

**Independence.** The tables here are the judge's own transcription of SPEC.md, READOUTS.md and
CRITERIA.md (with both amendments). They are separate from the builder's worlds, so C0's check of
an engine run's definition compares two transcriptions. The reader imports neither the engine nor
the references' code. `read` returns one normalised structure (Reference) for the judge.

**Commands:**
- `python -m validation.gene_regulation.fr38_v2.reader --check-reader [--sample FILE --sums FILE]`
  runs, in order:
  - the first read of the invented file (by default from the references' tag, through git), with
    its sha256 checked against the tag's SHA256SUMS;
  - made-up documents in the layouts of AF, AN, B, C and D;
  - planted faults, each of which must be refused by name, beside controls that must pass.
- `python -m validation.gene_regulation.fr38_v2.reader read FILE...` reads files and prints each
  one's summary and faults.
- `python -m validation.gene_regulation.fr38_v2.reader c0 DIR` is C0 on the references' folder:
  every file's sha256 against DIR/SHA256SUMS, then each file read. Run it only after the reader's
  tag.
"""

import argparse
import copy
import hashlib
import json
import math
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REFERENCES_TAG = "fr38-v2-references-2026-11-24"  # The references' tag (D339).
REFERENCES_DIR = "validation/gene_regulation/fr38_v2/references/out"
SAMPLE = "reference_invented.json"
FILES = {f"reference_{name}.json": name for name in ("AF", "AN", "B", "C", "D", "invented")}

KIND = "cells.fr38_v2.reference@1"
N_A = 6.02214076e23  # 1/mol, exact (SI 2019)
K_B = 1.380649e-23  # J/K, exact (SI 2019)
T_K = 310.15
R_GAS = N_A * K_B  # fl(N_A k_B), the engine's double path (amendment 1, reading 5)
RT_J = R_GAS * T_K  # J/mol
RT_KJ = RT_J / 1000.0  # kJ/mol: fmol times kJ/mol is pJ
COPY_FMOL = 1.6605390671738468e-09  # SPEC.md §0: 1e15/N_A as a double
C_STANDARD_mM = 1000.0
UNITS = {"amount": "fmol", "energy": "pJ", "time": "s", "volume": "pL", "copy_fmol": COPY_FMOL}
CONSTANTS = {"N_A_per_mol": N_A, "RT_J_per_mol": RT_J, "R_J_per_mol_K": R_GAS, "T_K": T_K,
             "c_standard_mM": C_STANDARD_mM, "copy_fmol": COPY_FMOL,
             "k_B_J_per_K": K_B}  # fmt: skip

REQUIREMENT = 1e-11  # SPEC.md §3: a judged value's accuracy <= 1e-11 s_y
INPUT_RTOL = 1e-12  # CRITERIA.md C0: inputs to 1e-12 relative
SCALE_RTOL = 1e-12  # the file's scale against READOUTS.md §3's, recomputed (sums of a few terms)
EPS = 2.0**-52
SAFETY_FACTOR = 2.0  # SPEC.md §3: at least 2
RUN_TIMES = "out/run_times.json"  # amendment 2, Q5

CONSTANT, STEPPED = "constant", "stepped"
FATES = ("durable", "short_lived")
ROW = {"durable": "R", "short_lived": "R_s"}
FATE_OF_ROW = {row: fate for fate, row in ROW.items()}
LABEL_CLASSES = ("resyn", "pool0", "pre", "win", "post")
RELEASED = ("pre", "win", "post")
LABEL_RE = re.compile(r"label_(R|R_s)_(resyn|pool0|pre|win|post)")
GROSS_RE = re.compile(r"released_present_gross_(durable|short_lived)")
RELEASE_RE = re.compile(r"(?:int_Q_tx_release|H_rel_tx_release)_(durable|short_lived)")

# ------------------------------------------------------------------ READOUTS.md §1 and §2


def _stages(chain):
    return tuple(f"C_{chain}_{j}" for j in range(1, 9))


TX = ("H_tx_release", *_stages("tx"), "E_tx", "W_tx", "F_pol", "int_J_I_tx", "int_S_tx",
      "int_Q_tx", "int_Q_tx_release_durable", "int_Q_tx_release_short_lived", "int_D_R",
      "int_D_R_s", "H_tx", "H_deg_R", "H_deg_R_s", "H_rel_tx_release_durable",
      "H_rel_tx_release_short_lived", "G_minus_G0")  # fmt: skip
LABELS = tuple(f"label_{row}_{c}" for row in ("R", "R_s") for c in LABEL_CLASSES)
GROSS = tuple(f"released_present_gross_{fate}" for fate in FATES)
HOLD_ROWS = ("N", "M", "Pi", "R", "R_s")
HOLD_SERIES = (*(f"n_{r}" for r in HOLD_ROWS), *TX, *LABELS, *GROSS)
STORE_SERIES = ("n_Mx", "H_store")
WATER_SERIES = ("V", "H_water", "W_bath")
B_ROWS = ("X", "N", "M", "A", "ATP", "ADP", "Pi", "R", "R_s", "P")


def _translation(chain):
    return (*_stages(chain), f"E_{chain}", f"W_{chain}", f"int_J_I_{chain}", f"int_S_{chain}",
            f"int_Q_{chain}")  # fmt: skip


B_SERIES = (*(f"n_{r}" for r in B_ROWS), *TX, "F_rib", *_translation("tl"), *_translation("tl_s"),
            "int_D_P", "int_J_C", "H_tl", "H_deg_P", "H_rc", *LABELS, *GROSS)  # fmt: skip
# READOUTS.md §4: arm A reports the stage complexes and W_tx (D334); arm B judges FR-38's quantities
A_REPORTED = (*_stages("tx"), "W_tx")
B_JUDGED = ("H_tx_release", "int_Q_tx_release_durable", "int_Q_tx_release_short_lived", "n_R",
            "n_R_s", "int_D_R", "int_D_R_s", "H_deg_R", "H_deg_R_s", "H_rel_tx_release_durable",
            "H_rel_tx_release_short_lived", *LABELS, *GROSS)  # fmt: skip
HOLD_HEATS = ("H_tx", "H_deg_R", "H_deg_R_s", "H_rel_tx_release_durable",
              "H_rel_tx_release_short_lived")  # fmt: skip
B_HEATS = (*HOLD_HEATS, "H_tl", "H_deg_P", "H_rc")
# SPEC.md §4: zero by the model's structure in the blank, at every output
BLANK_ZEROS = frozenset(("H_tx_release", "int_Q_tx", "int_J_I_tx", "int_S_tx", *_stages("tx"),
                         "E_tx", "W_tx", "H_tx"))  # fmt: skip

# ------------------------------------------------------------------ SPEC.md §1 and §2: the families

MU_N = 24.8672029410015
MU_FATE = {"AF": 10319.123756415122, "AN": -12442.6668}  # SPEC.md §1.1: 1200 mu°_res, literals
MU_RES_DECLARED = {"AF": 8.599269797012601, "AN": -10.368889}
B_MU = {"ATP": 12.409206388416035, "ADP": 0.0, "Pi": 0.0, "N": MU_N, "M": 0.0, "A": 0.0,
        "R": 10319.123756415122, "R_s": 10319.123756415122, "P": 2336.405378810971}  # fmt: skip
P_OF = {"p=0": ((0.0, 0.0),), "p=1": ((0.0, 1.0),), "p_sched": ((0.0, 0.7), (2700.0, 0.25)),
        "p=0.55": ((0.0, 0.55),)}  # fmt: skip
HOLD_RUN_NAMES = {
    "AF": ("p=0 returned", "p=0 held", "p=1 returned", "p=1 held", "p_sched returned",
           "p_sched held", "blank"),
    "AN": ("p=0 returned", "p=1 returned", "p_sched returned", "p_sched held", "blank"),
    "C": ("p_sched returned", "blank"),
    "D": ("p_sched returned", "blank"),
}  # fmt: skip
B_RUN_NAMES = ("p=0.55 returned", "p=0.55 held")
RUN_NAME_RE = re.compile(r"(p=0|p=1|p_sched|p=0\.55) (returned|held)")
HOLD_BACKGROUND_FMOL = {"K": 140.0, "Y": 140.0}  # 140 mM in the 1 pL cell (SPEC.md §1.1)


@dataclass(frozen=True)
class RunDef:
    """A run of SPEC.md §1.3's names: its machine, its p schedule ((time, p), ...) and whether it
    is the blank (H(0) = 0 and k_I = 0; its p and machine change nothing, SPEC.md §1.1)."""

    name: str
    machine: str
    p: tuple
    blank: bool

    @property
    def idle(self):
        """The fate a constant p of 0 or 1 never feeds (SPEC.md §4), else None."""
        values = {v for _, v in self.p}
        if self.blank:
            return None
        if values == {0.0}:
            return "durable"
        if values == {1.0}:
            return "short_lived"
        return None


@dataclass(frozen=True)
class Chain:
    """A chain's residue term in G (LAWS.md §5): mu°_res/RT = fl(mu°_product/L) (amendment 1,
    reading 6), its residues in transit's series, its hold's series (or None) and its L."""

    mu_res: float
    transit: str
    hold: str | None
    residues: int


@dataclass(frozen=True)
class Family:
    name: str
    arm: str  # "A" (the hold worlds) or "B"
    extra: str | None  # "store" (C), "water" (D) or None
    horizon: float
    every: float
    window: tuple
    samples: tuple
    runs: dict
    mu: dict  # G's rows: mu°/RT at 1 M
    chains: tuple
    background: dict = field(default_factory=dict)  # D: K and Y in the cell (fmol), in G
    volume: float = 1.0

    @property
    def times(self):
        n = int(round(self.horizon / self.every))
        return [self.every * i for i in range(n + 1)]

    @property
    def has_blank(self):
        return "blank" in self.runs

    @property
    def series(self):
        if self.arm == "B":
            return B_SERIES
        extra = {"store": STORE_SERIES, "water": WATER_SERIES}.get(self.extra, ())
        return (*HOLD_SERIES, *extra)

    @property
    def judged(self):
        if self.arm == "B":
            return frozenset(B_JUDGED)
        return frozenset(self.series) - frozenset(A_REPORTED)

    @property
    def heats(self):
        if self.arm == "B":
            return B_HEATS
        return (*HOLD_HEATS, *{"store": ("H_store",), "water": ("H_water",)}.get(self.extra, ()))

    @property
    def cohort_net(self):
        """Runs carrying `not_compared`: P1's mapping reads cohort_net in AF and AN (SPEC.md §6)."""
        return self.name in ("AF", "AN", "invented")


def _fl_res(mu_row, residues):
    return mu_row / residues  # fl(mu°_row / L), as the engine forms it (amendment 1, reading 6)


def registered(name):
    """The judge's transcription of SPEC.md's family `name` (AF, AN, B, C or D)."""
    if name == "B":
        return Family(
            name="B", arm="B", extra=None, horizon=21600.0, every=60.0, window=(2400.0, 6000.0),
            samples=(6000.0, 9600.0, 13200.0),
            runs={n: RunDef(n, n.split(" ")[1], P_OF["p=0.55"], False) for n in B_RUN_NAMES},
            mu=dict(B_MU),
            chains=(Chain(_fl_res(B_MU["R"], 1200), "W_tx", "H_tx_release", 1200),
                    Chain(_fl_res(B_MU["P"], 400), "W_tl", None, 400),
                    Chain(_fl_res(B_MU["P"], 400), "W_tl_s", None, 400)),
        )  # fmt: skip
    if name not in HOLD_RUN_NAMES:
        raise ValueError(f"no registered family {name!r}")
    potentials = "AF" if name == "AF" else "AN"
    mu = {"N": MU_N, "M": 0.0, "Pi": 0.0, "R": MU_FATE[potentials], "R_s": MU_FATE[potentials]}
    extra = {"C": "store", "D": "water"}.get(name)
    background = {}
    if extra == "store":
        mu["Mx"] = 0.0  # SPEC.md §1.5: Mx's mu°/RT at 1 M
    if extra == "water":  # LAWS.md §5: every species row, K and Y at mu° 0 (amendment 1, item 7)
        mu |= {"K": 0.0, "Y": 0.0}
        background = dict(HOLD_BACKGROUND_FMOL)
    runs = {}
    for n in HOLD_RUN_NAMES[name]:
        if n == "blank":
            runs[n] = RunDef(n, "returned", P_OF["p=0"], True)
        else:
            p, machine = n.split(" ")
            runs[n] = RunDef(n, machine, P_OF[p], False)
    return Family(
        name=name, arm="A", extra=extra, horizon=14400.0, every=30.0, window=(1800.0, 5400.0),
        samples=(5400.0, 9000.0, 12600.0), runs=runs, mu=mu,
        chains=(Chain(_fl_res(MU_FATE[potentials], 1200), "W_tx", "H_tx_release", 1200),),
        background=background,
    )  # fmt: skip


def invented(inputs):
    """The invented family (SPEC.md §8), from the file's own inputs, in arm A's layout."""
    runs = {}
    for name, entry in inputs["runs"].items():
        blank = name == "blank"
        p = tuple((float(t), float(v)) for t, v in entry["p"])
        runs[name] = RunDef(name, entry["machine"], p, blank)
    mu = {k: float(v) for k, v in inputs["mu0_RT_at_1M"].items()}
    length = int(inputs["L_residues"])
    return Family(
        name="invented", arm="A", extra=None, horizon=float(inputs["horizon_s"]),
        every=float(inputs["output_interval_s"]), window=tuple(map(float, inputs["window_s"])),
        samples=tuple(map(float, inputs["samples_s"])), runs=runs, mu=mu,
        chains=(Chain(float(inputs["mu_res_RT"]), "W_tx", "H_tx_release", length),),
        volume=float(inputs["volume_pL"]),
    )  # fmt: skip


# ------------------------------------------------------------------ SPEC.md §4: the classes


def expected_class(run, name, t, window):
    """SPEC.md §4's class of (run, readout, time), with amendment 1's for released_present_gross:
    `constant` (+0.0 by the model's structure) or `stepped`."""
    t1, t2 = window
    label = LABEL_RE.fullmatch(name)
    if label:
        row, c = label.groups()
        if c in RELEASED:
            if run.blank or run.idle == FATE_OF_ROW[row]:
                return CONSTANT
            if (c == "pre" and t == 0.0) or (c == "win" and t <= t1) or (c == "post" and t <= t2):
                return CONSTANT
        return STEPPED
    gross = GROSS_RE.fullmatch(name)
    if gross:
        if run.blank or run.idle == gross.group(1) or t == 0.0:
            return CONSTANT
        return STEPPED
    release = RELEASE_RE.fullmatch(name)
    if release and (run.blank or run.idle == release.group(1)):
        return CONSTANT
    if run.blank and name in BLANK_ZEROS:
        return CONSTANT
    return STEPPED


# ------------------------------------------------------------------ READOUTS.md §3: the scales


def _max_abs(values):
    return max((abs(v) for v in values), default=0.0)


def heat_scale(fam, values):
    """max over the outputs of sum_c |H_c| over the run's heat classes (in D, plus |W_bath|)."""
    names = [*fam.heats, *(["W_bath"] if fam.extra == "water" else [])]
    return max(math.fsum(abs(values[h][i]) for h in names) for i in range(len(values[names[0]])))


def _moves(series):
    return any(v != series[0] for v in series)


def g_scale(fam, values):
    """G_minus_G0's s_y (READOUTS.md §3, amendment 1, item 7): the heat scale, plus max over the
    outputs of sum n_r RT (|mu°_r| + |ln(n_r/(V c°))| + 1) over the rows whose term in G moves,
    plus max over the outputs of RT sum_chains |mu°_res| (W + L H)."""
    count = len(values["G_minus_G0"])
    volume = values["V"] if fam.extra == "water" else [fam.volume] * count
    rows = []
    for row, mu in fam.mu.items():
        if row in fam.background:
            rows.append((mu, [fam.background[row]] * count))
        elif fam.extra == "water" or _moves(values[f"n_{row}"]):
            rows.append((mu, values[f"n_{row}"]))
    term = max(
        (math.fsum(n[i] * RT_KJ * (abs(mu) + abs(math.log(n[i] / (volume[i] * C_STANDARD_mM))) + 1)
                   for mu, n in rows) for i in range(count)),
        default=0.0,
    )  # fmt: skip
    residue = max(
        math.fsum(RT_KJ * abs(c.mu_res)
                  * (values[c.transit][i] + (c.residues * values[c.hold][i] if c.hold else 0.0))
                  for c in fam.chains)
        for i in range(count)
    )  # fmt: skip
    return heat_scale(fam, values) + term + residue


def series_scale(fam, name, values):
    """READOUTS.md §3's s_y of a series from a run's values {readout: [value per output]}."""
    label = LABEL_RE.fullmatch(name)
    gross = GROSS_RE.fullmatch(name)
    if label:
        return _max_abs(values[f"n_{label.group(1)}"])
    if gross:
        return _max_abs(values[f"n_{ROW[gross.group(1)]}"])
    if name == "G_minus_G0":
        return g_scale(fam, values)
    if name in fam.heats or name == "W_bath":
        return heat_scale(fam, values)
    return _max_abs(values[name])


def excess_scale(fate, values, blank_values):
    """max over the outputs of (n_f + n_f^blank)."""
    n, b = values[f"n_{ROW[fate]}"], blank_values[f"n_{ROW[fate]}"]
    return max(x + y for x, y in zip(n, b, strict=True))


def route2_scale(fate, values):
    """max over the outputs of the fate's release counter (amendment 1, item 1)."""
    return _max_abs(values[f"int_Q_tx_release_{fate}"])


# ------------------------------------------------------------------ the inputs echoed (C0)
#
# The echo's key names are the references agent's. The lead read them from the five files, names
# only, and gave them to the judge before the reader's tag. AF and AN use the invented file's 37,
# C adds `store` and D adds `water`; B has 46. README.md maps each to its SPEC.md quantity. The rule
# (the lead's ruling, 24 November 2026):
# - every known key is checked by name against SPEC.md's (or A1's sheet's) stated value, to 1e-12
#   relative;
# - a key whose value the spec states but the file lacks is a C0 refusal;
# - a file key with no stated value is listed as unchecked, never refused.


class Alt(tuple):
    """Stated values, any one of which matches: where SPEC.md fixes the quantity but not the form
    of its echo (a constant or its one-entry schedule; D's bath before or after its dilution)."""


def _hold_echo(name):
    """SPEC.md §1's inputs for a hold family, under the invented file's 37 names, plus C's `store`
    and D's `water` (the lead's names)."""
    an = name != "AF"
    potentials = "AN" if an else "AF"
    mu_fate = MU_FATE[potentials]
    out = {
        "H0_copies": 160, "K_N_mM": 0.02, "L_residues": 1200, "N_per_residue": 1,
        "Pi_per_residue": 2, "bath_mM": {"K": 140.0, "Y": 140.0}, "bath_trace_mM": 1e-15,
        "bath_volume_pL": 1.0, "blank": {"H0_copies": 0, "k_I_per_mM_s": 0.0},
        "cell_background_mM": {"K": 140.0, "Y": 140.0}, "constants": dict(CONSTANTS),
        "horizon_s": 14400.0, "initial_copies": {"R": 20, "R_s": 15},
        "initial_label_shares": {"pool0": 1.0},
        "initial_mM": {"M": 4.0e-3 if an else 0.05, "N": 2.0, "Pi": 5.0},
        "k_I_per_mM_s": 3.0e3, "k_d_per_s": 1 / 9000, "k_s_per_s": 1 / 1350,
        "label_schedule_s": {"pre": 0.0, "win": 1800.0, "post": 5400.0},
        "moieties": {"nucleoside": {"M": 1, "N": 1, "R": 1200, "R_s": 1200},
                     "phosphorus": {"M": 1, "N": 3, "Pi": 1, "R": 1200, "R_s": 1200}},
        "mu0_RT_at_1M": {"M": 0.0, "N": MU_N, "Pi": 0.0, "R": mu_fate, "R_s": mu_fate},
        "mu_res_RT": _fl_res(mu_fate, 1200), "mu_res_declared_RT": MU_RES_DECLARED[potentials],
        "output_interval_s": 30.0, "p_sched": [list(x) for x in P_OF["p_sched"]],
        "patch_area_m2": 1e-10, "patch_solute_permeability": 0.0, "pool_machines_copies": 10000,
        "samples_s": [5400.0, 9000.0, 12600.0], "speed_nt_per_s": 50.0, "stages": 8,
        "tau_s": 2400.0, "template_copies": 1, "trace_mM": 1e-15, "volume_pL": 1.0,
        "window_s": [1800.0, 5400.0], "runs": {},
    }  # fmt: skip
    for run in HOLD_RUN_NAMES[name]:
        if run == "blank":
            out["runs"][run] = {"H0_copies": 0, "k_I_per_mM_s": 0.0}
        else:
            p, machine = run.split(" ")
            out["runs"][run] = {"machine": machine, "p": [list(x) for x in P_OF[p]]}
    if name == "C":  # SPEC.md §1.5
        out["store"] = {
            "Mx_initial_mM": 1.0e-6, "Mx_moieties": {"nucleoside": 1, "phosphorus": 1},
            "forward_per_s_at_c0": 1 / 3000, "mu0_Mx_RT_at_1M": 0.0,
            "multiplier": Alt((1.0, [[0.0, 1.0]])), "network_c0_mM": 1.0,
            "network_mu0_RT_at_c0": {"M": -6.907755278982137, "Mx": -6.907755278982137},
        }  # fmt: skip
    if name == "D":  # SPEC.md §1.6: the bath at 0.4 of §1.1's amounts, so K and Y at 56 mM
        out["water"] = {
            "L_p_m_per_Pa_s": 2.8029294930351318e-14, "V_max_pL": 3.0, "V_min_pL": 0.5,
            "V_ref_pL": 1.0, "availability": Alt((1.0, [[0.0, 1.0]])),
            "bath_fraction_of_section_1_1": 0.4, "bath_pressure_Pa": 0.0, "bulk_modulus_Pa": 0.0,
            "impermeant_fmol": 0.0, "pressure_offset_Pa": 0.0,
        }  # fmt: skip
        # The 37 keys name §1.1's bath; D's echo may give it before or after the dilution, which
        # water.bath_fraction_of_section_1_1 states (README.md).
        out["bath_mM"] = {"K": Alt((0.4 * 140.0, 140.0)), "Y": Alt((0.4 * 140.0, 140.0))}
        out["bath_trace_mM"] = Alt((0.4 * 1e-15, 1e-15))
    return out


def _b_echo():
    """SPEC.md §2's inputs for B, with A1's sheet values (§5.1's table), under B's 46 names: the
    invented file's 19 that B shares, and B's own 27."""
    a1_moieties = {
        "adenine": {"ATP": 1, "ADP": 1},
        "phosphorus": {"N": 3, "M": 1, "ATP": 3, "ADP": 2, "Pi": 1, "R": 1200, "R_s": 1200},
        "nucleoside": {"N": 1, "M": 1, "R": 1200, "R_s": 1200},
        "amino acid": {"A": 1, "P": 400},
        "amino_acid": {"A": 1, "P": 400},
    }
    return {
        "H0_copies": 0, "constants": dict(CONSTANTS), "horizon_s": 21600.0,
        "initial_label_shares": {"pool0": 1.0},
        "initial_mM": {"X": 1.0e-3, "N": 2.0, "M": 0.05, "A": 2.0, "ATP": 5.0, "ADP": 0.5,
                       "Pi": 5.0, "R": 1.0e-12, "R_s": 1.0e-12, "P": 1.0e-12},
        "k_I_per_mM_s": 1.2e4, "k_d_per_s": 1 / 8000, "k_s_per_s": 1 / 1100,
        "label_schedule_s": {"pre": 0.0, "win": 2400.0, "post": 6000.0},
        "moieties": a1_moieties, "mu0_RT_at_1M": dict(B_MU), "output_interval_s": 60.0,
        "p_sched": Alt(([[0.0, 0.55]], None)),
        "runs": {n: {"machine": n.split(" ")[1], "p": Alt(([[0.0, 0.55]], 0.55))}
                 for n in B_RUN_NAMES},
        "samples_s": [6000.0, 9600.0, 13200.0], "tau_s": 1500.0, "template_copies": 1,
        "volume_pL": 1.0, "window_s": [2400.0, 6000.0],
        "K_ATP_rc_mM": 0.1, "K_ATP_tl_mM": 0.02, "K_A_tl_mM": 0.02, "K_M_rc_mM": 0.1,
        "K_N_tx_mM": 0.02, "K_X_mM": 1.0e-3, "L_P_aa": 400, "L_R_nt": 1200,
        "M_pol_copies": 1.0e4, "M_rib_copies": 1.0e6, "P_on_fmol_per_s": 2.0e-6,
        "V_C_mM_per_s": 0.01, "b_X": 0.02, "k_I_tl_per_mM_s": 120.0, "k_I_tx_per_mM_s": 1.2e4,
        "k_P_per_s": 5.0e-4, "k_X_per_s": 2.0e-3, "m_tl": 8, "m_tx": 8,
        "mu_res_P_RT": _fl_res(B_MU["P"], 400), "mu_res_R_RT": _fl_res(B_MU["R"], 1200),
        "n_X": 2, "p": 0.55, "t_end_s": 21600.0, "t_off_s": 10800.0, "v_tl_aa_per_s": 16.0,
        "v_tx_nt_per_s": 50.0,
    }  # fmt: skip


def expected_echo(name):
    return _b_echo() if name == "B" else _hold_echo(name)


def optional(name, path):
    """Paths checked where present, never required: B's moieties, whose rows and names SPEC.md
    leaves to the sheet's §1.4 table (`amino acid` written either way)."""
    return name == "B" and path[0] == "moieties"


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _close(a, b, rtol=INPUT_RTOL):
    if _number(a) and _number(b):
        return a == b or abs(a - b) <= rtol * max(abs(a), abs(b))
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(x, y, rtol) for x, y in zip(a, b, strict=True))
    return a == b


def _same(got, want):
    if isinstance(want, Alt):
        return any(_same(got, w) for w in want)
    if want is None:
        return got is None
    return _close(got, want)


def resolved(tree):
    """The expected echo with each Alt at its first value (for made-up documents)."""
    if isinstance(tree, Alt):
        return resolved(tree[0])
    if isinstance(tree, dict):
        return {k: resolved(v) for k, v in tree.items()}
    if isinstance(tree, list):
        return [resolved(v) for v in tree]
    return tree


def flatten(tree, prefix=()):
    """{path: leaf}: dicts are walked; a list, a scalar or an Alt is a leaf."""
    out = {}
    if isinstance(tree, dict):
        for k, v in tree.items():
            out |= flatten(v, (*prefix, k))
    else:
        out[prefix] = tree
    return out


def echo_problems(name, inputs):
    """(problems, unchecked paths): a registered file's echoed inputs against SPEC.md's, by name."""
    if not isinstance(inputs, dict):
        return ["inputs: not an object"], []
    expected = expected_echo(name)
    problems = [f"inputs.{k}: missing (a key SPEC.md states)" for k in expected if k not in inputs]
    want = flatten(expected)
    got = flatten(inputs)
    for path, value in want.items():
        where = "inputs." + ".".join(path)
        if path not in got:
            if path[0] in inputs and not optional(name, path):
                problems.append(f"{where}: missing (SPEC.md states it)")
            continue
        if not _same(got[path], value):
            problems.append(f"{where}: {got[path]!r}, where SPEC.md's is {value!r}")
    unchecked = sorted(".".join(p) for p in got if p not in want)
    return problems, unchecked


def invented_problems(fam, inputs):
    """The invented family's inputs, held to their own consistency (SPEC.md §8)."""
    problems = []
    t1, t2 = fam.window
    if fam.samples[0] != t2:
        problems.append("inputs: the first sample time is not the window's end t2")
    schedule = inputs.get("label_schedule_s", {})
    if schedule != {"pre": 0.0, "win": t1, "post": t2}:
        problems.append("inputs.label_schedule_s: not pre at 0, win at t1 and post at t2")
    p_sched = [tuple(map(float, x)) for x in inputs.get("p_sched", [])]
    for name, run in fam.runs.items():
        if name == "blank":
            entry = inputs["runs"][name]
            if entry.get("H0_copies") != 0 or entry.get("k_I_per_mM_s") != 0.0:
                problems.append("inputs.runs.blank: H(0) and k_I are not 0")
            continue
        match = RUN_NAME_RE.fullmatch(name)
        if not match:
            problems.append(f"inputs.runs: {name!r} is not one of SPEC.md §1.3's names")
            continue
        p, machine = match.groups()
        want = tuple(p_sched) if p == "p_sched" else P_OF[p]
        if run.machine != machine or tuple(run.p) != want:
            problems.append(f"inputs.runs.{name}: its machine or p differs from its name")
    mu_res = float(inputs["mu0_RT_at_1M"]["R"]) / int(inputs["L_residues"])
    if float(inputs["mu_res_RT"]) != mu_res:
        problems.append("inputs.mu_res_RT: not fl(mu°_R/L) (amendment 1, reading 6)")
    return problems


# ------------------------------------------------------------------ reading a file


def _refuse_constant(token):
    raise ValueError(f"a non-finite number ({token}) in the file")


def parse(text):
    """JSON with NaN and the infinities refused (Python's json accepts them by default)."""
    return json.loads(text, parse_constant=_refuse_constant)


def _is_float(v):
    return isinstance(v, float)


def _plus_zero(v):
    return isinstance(v, float) and v == 0.0 and math.copysign(1.0, v) > 0.0


def _finite(v):
    return _is_float(v) and math.isfinite(v)


@dataclass
class Series:
    classes: list
    values: list
    accuracy: list
    scale: float


@dataclass
class Run:
    series: dict  # {readout: Series}
    excess: dict  # {fate: Series}, non-blank runs of a family with a blank
    route2: dict  # {(fate, ts): entry}
    survival: dict  # {(fate, ts): entry}
    not_compared: dict  # {name: [value per output]}
    checks: dict


@dataclass
class Reference:
    """One reference file, normalised for the judge: the reader's only output of values."""

    family: Family
    times: list
    samples: list
    runs: dict  # {run name: Run}
    plants: list
    summary: dict


class Reader:
    """One document's C0 (module docstring): problems accumulate; nothing raises midway."""

    def __init__(self, doc, family_name=None):
        self.doc = doc
        self.problems = []
        self.summary = {}
        self.expect_family = family_name
        self.worst = (0.0, None)  # the largest accuracy / (1e-11 s_y) of a judged entry

    def fault(self, text):
        self.problems.append(text)

    def _need(self, mapping, keys, where):
        if not isinstance(mapping, dict):
            self.fault(f"{where}: not an object")
            return False
        missing = [k for k in keys if k not in mapping]
        for k in missing:
            self.fault(f"{where}: the registered key {k!r} is missing")
        return not missing

    def _judge_accuracy(self, accuracy, scale, where, limit_scale=None):
        bound = REQUIREMENT * (scale if limit_scale is None else limit_scale)
        if accuracy > bound:
            self.fault(f"{where}: accuracy {accuracy!r} exceeds 1e-11 s_y = {bound!r}")
        ratio = accuracy / bound if bound > 0 else (math.inf if accuracy > 0 else 0.0)
        if ratio > self.worst[0]:
            self.worst = (ratio, where)

    def read(self):
        doc = self.doc
        top = ("kind", "family", "inputs", "units", "times_s", "samples_s", "runs", "plants",
               "method", "provenance")  # fmt: skip
        if not self._need(doc, top, "the file"):
            return None
        if doc["kind"] != KIND:
            self.fault(f"kind: {doc['kind']!r}, not {KIND!r}")
        name = doc["family"]
        if self.expect_family is not None and name != self.expect_family:
            self.fault(f"family: {name!r} in a file named for {self.expect_family!r}")
        if doc["units"] != UNITS or not all(
            type(doc["units"].get(k)) is type(v) for k, v in UNITS.items()
        ):
            self.fault(f"units: {doc['units']!r}, not SPEC.md §7's {UNITS!r}")
        try:
            fam = invented(doc["inputs"]) if name == "invented" else registered(name)
        except (KeyError, TypeError, ValueError) as error:
            self.fault(f"family {name!r}: its inputs cannot be read ({error!r})")
            return None
        if name == "invented":
            self.problems += invented_problems(fam, doc["inputs"])
        else:
            problems, unchecked = echo_problems(name, doc["inputs"])
            self.problems += problems
            self.summary["inputs_unchecked_by_name"] = unchecked
        times = doc["times_s"]
        if not (isinstance(times, list) and all(_is_float(t) for t in times)
                and times == fam.times):  # fmt: skip
            self.fault(f"times_s: not the grid 0, {fam.every}, ..., {fam.horizon} s")
            return None
        if doc["samples_s"] != list(fam.samples) or not all(t in times for t in fam.samples):
            self.fault(f"samples_s: {doc['samples_s']!r}, not {list(fam.samples)!r}")
        if fam.samples[0] != fam.window[1]:
            self.fault("the first sample time is not the window's end t2")
        runs = doc["runs"]
        if not isinstance(runs, dict):
            self.fault("runs: not an object")
            return None
        for run in fam.runs:
            if run not in runs:
                self.fault(f"runs: the run {run!r} is missing")
        # A run the family does not register is an extra key, ignored and listed (amendment 2, Q6).
        self.summary["runs_ignored"] = sorted(run for run in runs if run not in fam.runs)
        values = {}
        out = {}
        blank = runs.get("blank") if fam.has_blank else None
        if fam.has_blank and isinstance(blank, dict):
            out["blank"], values["blank"] = self.run(fam, "blank", blank, times, None)
        for run_name, run in runs.items():
            if run_name == "blank" or run_name not in fam.runs:
                continue
            out[run_name], values[run_name] = self.run(fam, run_name, run, times,
                                                       out.get("blank"))  # fmt: skip
        plants = self.plants(fam, doc["plants"], times, values)
        self.method(doc["method"])
        self.provenance(doc["provenance"], registered_family=name != "invented")
        self.summary["worst_accuracy_over_requirement"] = {"ratio": self.worst[0],
                                                           "where": self.worst[1]}  # fmt: skip
        if self.problems:
            return None
        return Reference(fam, times, list(doc["samples_s"]), out, plants, self.summary)

    # ---------------------------------------------------------------- one run

    def series(self, expect, entry, times, where, judged, scale_value):
        """One series: its classes against `expect(t)`, its constants +0.0 with null accuracy,
        its stepped entries finite, and a judged entry's accuracy against 1e-11 s_y."""
        if not self._need(entry, ("class", "value", "accuracy", "scale"), where):
            return None
        classes, values, accuracy, scale = (entry[k] for k in ("class", "value", "accuracy",
                                                                 "scale"))  # fmt: skip
        if not all(isinstance(x, list) and len(x) == len(times)
                   for x in (classes, values, accuracy)):  # fmt: skip
            self.fault(f"{where}: class, value and accuracy need one entry per output time "
                       f"({len(times)})")  # fmt: skip
            return None
        if not (_finite(scale) and scale >= 0.0):
            self.fault(f"{where}: scale {scale!r} is not a finite non-negative float")
        for i, t in enumerate(times):
            c, v, a = classes[i], values[i], accuracy[i]
            at = f"{where} at {t:g} s"
            if c not in (CONSTANT, STEPPED):
                self.fault(f"{at}: class {c!r} is refused (constant or stepped only)")
                continue
            want = expect(t)
            if c != want:
                self.fault(f"{at}: class {c!r}, where SPEC.md §4 gives {want!r}")
            if c == CONSTANT:
                if not _plus_zero(v):
                    self.fault(f"{at}: a constant entry's value {v!r} is not +0.0")
                if a is not None:
                    self.fault(f"{at}: a constant entry's accuracy {a!r} is not null")
            else:
                if not _finite(v):
                    self.fault(f"{at}: value {v!r} is not a finite float")
                if not (_finite(a) and a >= 0.0):
                    self.fault(f"{at}: accuracy {a!r} is not a finite non-negative float")
                elif judged and _finite(scale_value):
                    self._judge_accuracy(a, scale_value, at)
        return Series(list(classes), list(values), list(accuracy), scale)

    def run(self, fam, name, run, times, blank):
        where = f"runs[{name!r}]"
        rd = fam.runs[name]
        need = ["series", "checks"]
        if not rd.blank:
            need += ["survival", "route2"]
            if fam.has_blank:
                need.append("excess_over_blank")
            if fam.cohort_net:
                need.append("not_compared")
        else:
            for k in ("survival", "route2", "excess_over_blank", "not_compared"):
                if k in run:
                    self.fault(f"{where}: the blank carries {k!r} (amendment 1, item 3)")
        empty = Run({}, {}, {}, {}, {}, {})
        if not self._need(run, need, where):
            return empty, {}
        series = run["series"]
        if not isinstance(series, dict):
            self.fault(f"{where}.series: not an object")
            return empty, {}
        missing = [s for s in fam.series if s not in series]
        for s in missing:
            self.fault(f"{where}.series: the readout {s!r} is missing")
        if missing:
            return empty, {}
        values = {}
        for s in fam.series:
            entry = series[s]
            v = entry.get("value") if isinstance(entry, dict) else None
            if not (isinstance(v, list) and len(v) == len(times) and all(_finite(x) for x in v)):
                self.fault(f"{where}.series[{s!r}]: its values are not one finite float per "
                           "output time")  # fmt: skip
                return empty, {}
            values[s] = v
        scales = {s: series_scale(fam, s, values) for s in fam.series}
        out = {}
        for s in fam.series:
            at = f"{where}.series[{s!r}]"
            parsed = self.series(lambda t, s=s: expected_class(rd, s, t, fam.window), series[s],
                                 times, at, s in fam.judged, scales[s])  # fmt: skip
            if parsed is None:
                return empty, {}
            out[s] = parsed
            if STEPPED in parsed.classes:  # An all-constant series' scale is never read.
                self._scale_matches(parsed.scale, scales[s], at)
        self._identities(fam, rd, out, times, where)
        excess = {}
        if not rd.blank and fam.has_blank and blank is not None and blank.series:
            excess = self.excess(run["excess_over_blank"], times, out, blank.series, where)
        route2, survival = {}, {}
        if not rd.blank:
            route2 = self.route2(fam, rd, run["route2"], out, values, where)
            survival = self.survival(fam, rd, run["survival"], out, scales, where)
        not_compared = {}
        if not rd.blank and fam.cohort_net:
            not_compared = self.not_compared(run["not_compared"], times, where)
        checks = self.checks(run["checks"], where)
        return Run(out, excess, route2, survival, not_compared, checks), values

    def _scale_matches(self, published, mine, where):
        if not _finite(published):
            return
        if abs(published - mine) > SCALE_RTOL * max(abs(published), abs(mine)):
            self.fault(f"{where}: scale {published!r}, where READOUTS.md §3 gives {mine!r}")

    def _identities(self, fam, rd, out, times, where):
        """The file's own definitions: the gross is the sum of the three released classes; the
        five classes sum to their row within their accuracies and rounding."""
        worst_gross, worst_sum = 0.0, 0.0
        for fate, row in ROW.items():
            scale = _max_abs(out[f"n_{row}"].values)
            gross = out[f"released_present_gross_{fate}"]
            parts = [out[f"label_{row}_{c}"] for c in RELEASED]
            for i, t in enumerate(times):
                total = (parts[0].values[i] + parts[1].values[i]) + parts[2].values[i]
                gap = abs(gross.values[i] - total)
                bound = 4 * EPS * scale + sum(p.accuracy[i] or 0.0 for p in parts)
                worst_gross = max(worst_gross, gap / scale if scale else gap)
                if gap > bound:
                    self.fault(f"{where}: released_present_gross_{fate} at {t:g} s is not the "
                               f"sum of its three classes ({gap!r} > {bound!r})")  # fmt: skip
                classes = [out[f"label_{row}_{c}"] for c in LABEL_CLASSES]
                gap = abs(math.fsum(c.values[i] for c in classes) - out[f"n_{row}"].values[i])
                bound = 8 * EPS * scale + sum(c.accuracy[i] or 0.0 for c in classes)
                bound += out[f"n_{row}"].accuracy[i] or 0.0
                worst_sum = max(worst_sum, gap / scale if scale else gap)
                if gap > bound:
                    self.fault(f"{where}: the classes of {row} at {t:g} s do not sum to n_{row} "
                               f"within their accuracies ({gap!r} > {bound!r})")  # fmt: skip
        largest = self.summary.setdefault("own_definitions_largest_relative", {})
        largest["gross_vs_sum"] = max(largest.get("gross_vs_sum", 0.0), worst_gross)
        largest["classes_vs_row"] = max(largest.get("classes_vs_row", 0.0), worst_sum)

    def excess(self, block, times, out, blank, where):
        """The excess over the blank (SPEC.md §3, item 5): every entry stepped (SPEC.md §4), judged
        against max (n_f + n_f^blank), and the row minus the blank's within their accuracies."""
        if not self._need(block, FATES, f"{where}.excess_over_blank"):
            return {}
        parsed = {}
        for fate in FATES:
            at = f"{where}.excess_over_blank[{fate!r}]"
            row, base = out[f"n_{ROW[fate]}"], blank[f"n_{ROW[fate]}"]
            scale = max(x + y for x, y in zip(row.values, base.values, strict=True))
            series = self.series(lambda t: STEPPED, block[fate], times, at, True, scale)
            if series is None:
                continue
            for i, t in enumerate(times):
                if series.classes[i] != STEPPED or not _finite(series.accuracy[i]):
                    continue
                gap = abs(series.values[i] - (row.values[i] - base.values[i]))
                bound = (series.accuracy[i] + (row.accuracy[i] or 0.0) + (base.accuracy[i] or 0.0)
                         + 4 * EPS * scale)  # fmt: skip
                if gap > bound:
                    self.fault(f"{at} at {t:g} s: not n - n_blank within their accuracies "
                               f"({gap!r} > {bound!r})")  # fmt: skip
            self._scale_matches(series.scale, scale, at)
            parsed[fate] = series
        return parsed

    def route2(self, fam, rd, entries, out, values, where):
        at = f"{where}.route2"
        if not isinstance(entries, list):
            self.fault(f"{at}: not a list")
            return {}
        found = {}
        keys = ("fate", "ts_s", "class", "value", "accuracy", "scale")
        for k, e in enumerate(entries):
            if not self._need(e, keys, f"{at}[{k}]"):
                continue
            if (e["fate"], e["ts_s"]) in found:
                self.fault(f"{at}[{k}]: a second entry for ({e['fate']!r}, {e['ts_s']!r})")
            found[(e["fate"], e["ts_s"])] = e
        parsed = {}
        index = {t: i for i, t in enumerate(fam.times)}
        for fate in FATES:
            win = out[f"label_{ROW[fate]}_win"]
            scale = route2_scale(fate, values)
            for ts in fam.samples:
                e = found.pop((fate, ts), None)
                where_e = f"{at} ({fate}, {ts:g} s)"
                if e is None:
                    self.fault(f"{where_e}: missing")
                    continue
                i = index[ts]
                want = CONSTANT if rd.idle == fate else STEPPED
                if e["class"] != want:
                    self.fault(f"{where_e}: class {e['class']!r}, where amendment 1 gives "
                               f"{want!r}")  # fmt: skip
                if want == CONSTANT:
                    if not _plus_zero(e["value"]) or e["accuracy"] is not None:
                        self.fault(f"{where_e}: an idle fate's entry is +0.0 with null accuracy")
                else:
                    if not (_finite(e["value"]) and _finite(e["accuracy"]) and e["accuracy"] >= 0
                            and _finite(e["scale"])):  # fmt: skip
                        self.fault(f"{where_e}: value, accuracy and scale are finite floats")
                    else:
                        self._judge_accuracy(e["accuracy"], scale, where_e)
                        self._scale_matches(e["scale"], scale, where_e)
                if not _same_bits(e["value"], win.values[i]) or not _same_bits(
                    e["accuracy"], win.accuracy[i]
                ):
                    self.fault(f"{where_e}: not the win class at that time, with its accuracy "
                               "(amendment 1, item 1)")  # fmt: skip
                parsed[(fate, ts)] = e
        for fate, ts in found:
            self.fault(f"{at}: an entry ({fate!r}, {ts!r}) at no fate and sample time")
        return parsed

    def survival(self, fam, rd, entries, out, scales, where):
        at = f"{where}.survival"
        if not isinstance(entries, list):
            self.fault(f"{at}: not a list")
            return {}
        found = {}
        keys = ("fate", "t2_s", "ts_s", "alive_t2", "alive_ts", "ratio", "accuracy")
        for k, e in enumerate(entries):
            if self._need(e, keys, f"{at}[{k}]"):
                if (e["fate"], e["ts_s"]) in found:
                    self.fault(f"{at}[{k}]: a second entry for ({e['fate']!r}, {e['ts_s']!r})")
                found[(e["fate"], e["ts_s"])] = e
        index = {t: i for i, t in enumerate(fam.times)}
        t2 = fam.samples[0]
        parsed = {}
        for fate in FATES:
            label = f"label_{ROW[fate]}_win"
            win = out[label]
            for ts in fam.samples[1:]:
                e = found.pop((fate, ts), None)
                where_e = f"{at} ({fate}, {ts:g} s)"
                if e is None:
                    self.fault(f"{where_e}: missing")
                    continue
                if e["t2_s"] != t2:
                    self.fault(f"{where_e}: t2_s {e['t2_s']!r}, not {t2!r}")
                acc = e["accuracy"]
                if not (isinstance(acc, list) and len(acc) == 3):
                    self.fault(f"{where_e}: accuracy is a list of three")
                    continue
                i2, i_s = index[t2], index[ts]
                if rd.idle == fate:
                    if not (_plus_zero(e["alive_t2"]) and _plus_zero(e["alive_ts"])):
                        self.fault(f"{where_e}: an idle fate's counts are +0.0")
                    if e["ratio"] is not None:
                        self.fault(f"{where_e}: an idle fate's ratio is null (undefined), not "
                                   f"{e['ratio']!r} (amendment 1, item 3)")  # fmt: skip
                    if acc != [None, None, None]:
                        self.fault(f"{where_e}: an idle fate's accuracies are null")
                else:
                    numbers = [e["alive_t2"], e["alive_ts"], e["ratio"], *acc]
                    if not all(_finite(x) for x in numbers) or min(acc) < 0:
                        self.fault(f"{where_e}: counts, ratio and accuracies are finite floats")
                        continue
                    if e["alive_t2"] == 0.0:
                        self.fault(f"{where_e}: a stepped count at t2 is zero")
                        continue
                    if abs(e["ratio"] - e["alive_ts"] / e["alive_t2"]) > 4 * EPS * abs(e["ratio"]):
                        self.fault(f"{where_e}: the ratio is not alive_ts / alive_t2")
                    self._judge_accuracy(acc[0], scales[label], f"{where_e} alive_t2")
                    self._judge_accuracy(acc[1], scales[label], f"{where_e} alive_ts")
                    self._judge_accuracy(acc[2], 1.0, f"{where_e} ratio")
                if not (_same_bits(e["alive_t2"], win.values[i2])
                        and _same_bits(e["alive_ts"], win.values[i_s])
                        and _same_bits(acc[0], win.accuracy[i2])
                        and _same_bits(acc[1], win.accuracy[i_s])):  # fmt: skip
                    self.fault(f"{where_e}: the counts are not the win class at t2 and ts, with "
                               "its accuracy")  # fmt: skip
                parsed[(fate, ts)] = e
        for fate, ts in found:
            self.fault(f"{at}: an entry ({fate!r}, {ts!r}) at no fate and later sample time")
        return parsed

    def not_compared(self, block, times, where):
        names = tuple(f"cohort_net_{fate}" for fate in FATES)
        if not self._need(block, names, f"{where}.not_compared"):
            return {}
        out = {}
        for name in names:
            v = block[name]
            if not (isinstance(v, list) and len(v) == len(times) and all(_finite(x) for x in v)):
                self.fault(f"{where}.not_compared[{name!r}]: one finite float per output time")
                continue
            out[name] = list(v)
        return out

    def checks(self, block, where):
        names = ("membership_sum_largest_relative", "hold_identity_largest_fmol",
                 "G_identity_largest_pJ")  # fmt: skip
        if not self._need(block, names, f"{where}.checks"):
            return {}
        for k, v in block.items():
            if _number(v) and not math.isfinite(v):
                self.fault(f"{where}.checks[{k!r}]: not finite")
        largest = self.summary.setdefault("references_checks_largest", {})
        for k, v in block.items():
            if _number(v):
                largest[k] = max(largest.get(k, 0.0), abs(v))
        return dict(block)

    # ------------------------------------------------------------ the plants, method, provenance

    def plants(self, fam, entries, times, values):
        if not isinstance(entries, list):
            self.fault("plants: not a list")
            return []
        need = ("plant", "run", "quantity", "time_s", "honest", "planted", "relative_distance")
        known = {*fam.series, *(f"route2_{f}" for f in FATES),
                 *(f"excess_over_blank_{f}" for f in FATES)}  # fmt: skip
        parsed = []
        for k, e in enumerate(entries):
            where = f"plants[{k}]"
            if not self._need(e, need, where):
                continue
            if e["plant"] not in PLANTS:
                self.fault(f"{where}: plant {e['plant']!r} is not one of CRITERIA.md §6's")
                continue
            if e["run"] not in fam.runs or fam.runs[e["run"]].blank:
                self.fault(f"{where}: run {e['run']!r} is not one of the family's runs")
            if e["quantity"] not in known:
                self.fault(f"{where}: quantity {e['quantity']!r} is not a readout of READOUTS.md")
            if e["time_s"] not in times:
                self.fault(f"{where}: time_s {e['time_s']!r} is not an output time")
            numbers = [e["honest"], e["planted"], e["relative_distance"]]
            if e["plant"] == "P1′":
                if not self._need(e, ("route2_bound", "distance_in_route2_bounds"), where):
                    continue
                numbers += [e["route2_bound"], e["distance_in_route2_bounds"]]
            if "scale" in e:
                numbers.append(e["scale"])
            if not all(_finite(x) for x in numbers) or e["relative_distance"] < 0:
                self.fault(f"{where}: its numbers are finite floats")
                continue
            scale = e.get("scale")
            if scale:
                want = abs(e["planted"] - e["honest"]) / scale
                if abs(e["relative_distance"] - want) > 1e-9 * max(want, 1e-300):
                    self.fault(f"{where}: relative_distance is not |planted - honest| / scale")
            parsed.append(dict(e))
        required = PLANTS_REQUIRED[fam.name]
        present = {e["plant"] for e in parsed}
        for plant in sorted(required - present):
            self.fault(f"plants: no entry of {plant} (SPEC.md §6 sizes it in this family)")
        self.summary["plant_sizing"] = sizing(fam, parsed)
        return parsed

    def method(self, block):
        need = ("primary", "second", "tolerances", "safety_factor",
                "largest_difference_between_methods", "run_time_s")  # fmt: skip
        if not self._need(block, need, "method"):
            return
        factor = block["safety_factor"]
        if not (_number(factor) and math.isfinite(factor) and factor >= SAFETY_FACTOR):
            self.fault(f"method.safety_factor: {factor!r}, where SPEC.md §3 asks at least 2")
        if block["run_time_s"] != RUN_TIMES:
            self.fault(f"method.run_time_s: {block['run_time_s']!r}, not the sidecar's path "
                       f"{RUN_TIMES!r} (amendment 2, Q5)")  # fmt: skip
        diffs = block["largest_difference_between_methods"]
        if isinstance(diffs, dict):
            rel = [v.get("relative_to_scale") for v in diffs.values() if isinstance(v, dict)]
            rel = [r for r in rel if _number(r)]
            self.summary["methods_largest_relative_difference"] = max(rel, default=None)

    def provenance(self, block, *, registered_family):
        need = ("revision", "dirty_paths", "writer_version", "python", "numpy", "scipy", "mpmath",
                "sha256_of_this_file_excluded")  # fmt: skip
        if not self._need(block, need, "provenance"):
            return
        if block["sha256_of_this_file_excluded"] is not True:
            self.fault("provenance.sha256_of_this_file_excluded: not true (amendment 2, Q5)")
        if not (isinstance(block["revision"], str)
                and re.fullmatch(r"[0-9a-f]{40}", block["revision"])):  # fmt: skip
            self.fault("provenance.revision: not a full Git revision")
        if not isinstance(block["dirty_paths"], list):
            self.fault("provenance.dirty_paths: not a list")
        elif registered_family and block["dirty_paths"]:
            self.fault(f"provenance.dirty_paths: {block['dirty_paths']!r}: a registered "
                       "reference is generated from a clean tree")  # fmt: skip
        self.summary["provenance"] = {k: block[k] for k in ("revision", "writer_version")}


def _same_bits(a, b):
    if a is None or b is None:
        return a is None and b is None
    return (
        _is_float(a)
        and _is_float(b)
        and math.copysign(1.0, a) == math.copysign(1.0, b)
        and (a == b)
    )


# ------------------------------------------------------------------ CRITERIA.md §6: the plants

PLANTS = ("P1", "P1′", "P1″", "P2", "P3a", "P3b", "P4", "P5", "P6", "P7", "P8", "P9")
PLANTS_REQUIRED = {
    "AF": {"P1", "P1″", "P2", "P5", "P6", "P7"},
    "AN": {"P1", "P1′", "P1″", "P3a", "P3b", "P4"},
    "B": {"P4"},
    "C": {"P8"},
    "D": {"P9"},
    "invented": {"P1", "P1′", "P1″", "P2", "P3a", "P3b", "P4", "P5", "P6", "P7"},
}
# The must-catch worlds (CRITERIA.md §6) and the readouts that catch each plant by C2. P2 and P1″
# at an idle fate are caught by C1, bit for bit, so no sizing applies there.
MUST_CATCH = {
    "P1": {"AN": None}, "P1′": {"AN": None}, "P1″": {"AN": None},
    "P3a": {"AN": ("p_sched returned",)}, "P3b": {"AN": ("p_sched returned",)},
    "P4": {"AN": ("p_sched returned",), "B": ("p=0.55 returned",)},
    "P5": {"AF": ("p_sched returned",)}, "P6": {"AF": ("p_sched returned",)},
    "P7": {"AF": ("p_sched held",)}, "P8": {"C": None}, "P9": {"D": None},
}  # fmt: skip
CATCHING = {
    "P1": r"label_(R|R_s)_win", "P1′": r"route2_.*", "P1″": r"released_present_gross_.*",
    "P3a": r"label_(R|R_s)_win", "P3b": r"label_(R|R_s)_win", "P4": r"label_(R|R_s)_win",
    "P5": r"n_R_s|int_D_R_s|label_R_s_.*", "P6": r"G_minus_G0", "P7": r"F_pol|E_tx",
    "P8": r"n_M|n_Mx|excess_over_blank_.*|label_(R|R_s)_resyn",
    "P9": r"n_R|n_R_s|label_.*|H_rel_.*|G_minus_G0",
}  # fmt: skip
# The honest relative tolerances CRITERIA.md §6 expects, from the protocol's probe
EXPECTED = {"label": 2e-8, "amount": 1e-9, "G": 1e-8, "heat": 5e-8, "route2": 1e-5}
HEAT_NAMES = re.compile(r"H_(tx|tl|deg_.*|rel_.*|rc|store|water)|W_bath")


def expected_tolerance(quantity):
    if quantity.startswith(("label_", "released_present_gross_")):
        return EXPECTED["label"]
    if quantity.startswith("route2_"):
        return EXPECTED["route2"]
    if quantity == "G_minus_G0":
        return EXPECTED["G"]
    if HEAT_NAMES.fullmatch(quantity):
        return EXPECTED["heat"]
    return EXPECTED["amount"]


def sizing(fam, entries):
    """CRITERIA.md §6's rule, reported: each must-catch plant's largest relative distance over its
    catching readouts, in units of 10 times the expected honest tolerance (>= 1 passes)."""
    out = {}
    for plant, worlds in MUST_CATCH.items():
        if plant not in PLANTS_REQUIRED[fam.name]:
            continue
        if fam.name not in worlds and fam.name != "invented":
            continue
        runs = worlds.get(fam.name)
        best = None
        for e in entries:
            if e["plant"] != plant or not re.fullmatch(CATCHING[plant], e["quantity"]):
                continue
            if runs is not None and e["run"] not in runs:
                continue
            if (
                fam.runs.get(e["run"]) is not None
                and fam.runs[e["run"]].idle is not None
                and (plant == "P1″")
            ):
                continue  # P1″ at an idle fate: C1
            ratio = e["relative_distance"] / (10 * expected_tolerance(e["quantity"]))
            if best is None or ratio > best["over_10x"]:
                best = {"over_10x": ratio, "quantity": e["quantity"], "run": e["run"],
                        "time_s": e["time_s"]}  # fmt: skip
        out[plant] = best
    return out


# ------------------------------------------------------------------ entry points


def read_document(doc, family_name=None):
    """(Reference or None, summary, problems) of a parsed document."""
    reader = Reader(doc, family_name)
    reference = reader.read()
    return reference, reader.summary, reader.problems


def read(path):
    """(Reference or None, summary, problems) of one reference file. Its family is its name's."""
    path = Path(path)
    try:
        doc = parse(path.read_text())
    except ValueError as error:
        return None, {}, [f"{path.name}: {error}"]
    return read_document(doc, FILES.get(path.name))


def sums_of(text):
    """{file name: sha256} from a SHA256SUMS text (sha256sum's format)."""
    out = {}
    for line in text.splitlines():
        if line.strip():
            digest, name = line.split(None, 1)
            out[name.strip().lstrip("*")] = digest
    return out


def c0(directory):
    """C0 on the references' folder: each file's sha256 against SHA256SUMS, then each read.
    Returns {file: {"reference": Reference or None, "summary", "problems"}}; refuses nothing
    silently."""
    directory = Path(directory)
    sums = sums_of((directory / "SHA256SUMS").read_text())
    out = {}
    for name in FILES:
        path = directory / name
        if name not in sums:
            out[name] = {"reference": None, "summary": {}, "problems": ["not in SHA256SUMS"]}
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != sums[name]:
            out[name] = {"reference": None, "summary": {},
                         "problems": [f"sha256 {digest} differs from SHA256SUMS"]}  # fmt: skip
            continue
        reference, summary, problems = read(path)
        out[name] = {"reference": reference, "summary": summary, "problems": problems,
                     "sha256": digest}  # fmt: skip
    return out


# ------------------------------------------------------------------ --check-reader


def _git_show(spec):
    return subprocess.run(["git", "show", spec], cwd=ROOT, capture_output=True,
                          check=True).stdout  # fmt: skip


def load_sample(sample=None, sums=None):
    """(the invented file's bytes, the SHA256SUMS text): from the paths given; else from the
    checkout's references folder where the references are merged; else from the references' tag
    through git (the first read, made with no real reference on disk)."""
    folder = ROOT / REFERENCES_DIR
    if sample is None and (folder / SAMPLE).exists() and (folder / "SHA256SUMS").exists():
        sample, sums = folder / SAMPLE, sums or folder / "SHA256SUMS"
    data = Path(sample).read_bytes() if sample else _git_show(
        f"{REFERENCES_TAG}:{REFERENCES_DIR}/{SAMPLE}")  # fmt: skip
    text = Path(sums).read_text() if sums else _git_show(
        f"{REFERENCES_TAG}:{REFERENCES_DIR}/SHA256SUMS").decode()  # fmt: skip
    return data, text


def made_up(name, seed=1):
    """A made-up document in family `name`'s layout (AF, AN, B, C or D): every registered key, the
    family's runs, series and classes, values that satisfy the file's own definitions, and the
    scales READOUTS.md §3 gives. Not physics: a structure for the reader's checks (and the judge's
    synthetic end-to-end check)."""
    fam = registered(name)
    times = fam.times
    count = len(times)
    t1, t2 = fam.window
    rows = [s[2:] for s in fam.series if s.startswith("n_")]

    def wave(base, k, grow=0.0):
        return [base * (1.0 + 0.05 * math.sin(1e-3 * t + k + seed) + grow * t / fam.horizon)
                for t in times]  # fmt: skip

    def values_of(run):
        v = {}
        for k, row in enumerate(rows):
            v[f"n_{row}"] = wave(10.0 ** (-(k % 5)) * 2.0, k, 0.1)
        if fam.extra == "water":
            v["V"] = wave(1.5, 7, 0.5)
        for s in fam.series:
            if s not in v:
                v[s] = wave(1e-6 * (1 + len(s) % 7), len(s), 0.2)
        for fate, row in ROW.items():  # the classes sum to the row; released ones by the rules
            for c in RELEASED:
                name_c = f"label_{row}_{c}"
                v[name_c] = [
                    0.0
                    if expected_class(run, name_c, t, fam.window) == CONSTANT
                    else 0.01 * v[f"n_{row}"][i]
                    for i, t in enumerate(times)
                ]
            v[f"label_{row}_resyn"] = [0.001 * x for x in v[f"n_{row}"]]
            v[f"label_{row}_pool0"] = [
                v[f"n_{row}"][i] - math.fsum(v[f"label_{row}_{c}"][i]
                                             for c in ("resyn", *RELEASED))
                for i in range(count)
            ]  # fmt: skip
            v[f"released_present_gross_{fate}"] = [
                (v[f"label_{row}_pre"][i] + v[f"label_{row}_win"][i]) + v[f"label_{row}_post"][i]
                for i in range(count)
            ]  # fmt: skip
        for s in fam.series:
            for i, t in enumerate(times):
                if expected_class(run, s, t, fam.window) == CONSTANT:
                    v[s][i] = 0.0
        return v

    def series_block(run, v):
        out = {}
        for s in fam.series:
            classes = [expected_class(run, s, t, fam.window) for t in times]
            scale = series_scale(fam, s, v)
            out[s] = {"class": classes, "value": v[s],
                      "accuracy": [None if c == CONSTANT else 1e-30 * scale for c in classes],
                      "scale": scale}  # fmt: skip
        return out

    runs, blank_v = {}, None
    if fam.has_blank:
        blank_v = values_of(fam.runs["blank"])
        runs["blank"] = {"series": series_block(fam.runs["blank"], blank_v),
                         "checks": {"membership_sum_largest_relative": 0.0,
                                    "hold_identity_largest_fmol": 0.0,
                                    "G_identity_largest_pJ": 0.0}}  # fmt: skip
    for run_name, run in fam.runs.items():
        if run.blank:
            continue
        v = values_of(run)
        block = {
            "series": series_block(run, v),
            "checks": {
                "membership_sum_largest_relative": 0.0,
                "hold_identity_largest_fmol": 0.0,
                "G_identity_largest_pJ": 0.0,
            },
        }
        win = {f: block["series"][f"label_{ROW[f]}_win"] for f in FATES}
        index = {t: i for i, t in enumerate(times)}
        block["route2"] = [
            {"fate": f, "ts_s": ts, "class": win[f]["class"][index[ts]],
             "value": win[f]["value"][index[ts]], "accuracy": win[f]["accuracy"][index[ts]],
             "scale": route2_scale(f, v) if run.idle != f else 0.0}
            for f in FATES for ts in fam.samples
        ]  # fmt: skip
        block["survival"] = []
        for f in FATES:
            for ts in fam.samples[1:]:
                a, b = index[t2], index[ts]
                idle = run.idle == f
                block["survival"].append({
                    "fate": f, "t2_s": t2, "ts_s": ts, "alive_t2": win[f]["value"][a],
                    "alive_ts": win[f]["value"][b],
                    "ratio": None if idle else win[f]["value"][b] / win[f]["value"][a],
                    "accuracy": [win[f]["accuracy"][a], win[f]["accuracy"][b],
                                 None if idle else 1e-30],
                })  # fmt: skip
        if fam.has_blank:
            block["excess_over_blank"] = {}
            for f in FATES:
                n, b = v[f"n_{ROW[f]}"], blank_v[f"n_{ROW[f]}"]
                scale = excess_scale(f, v, blank_v)
                block["excess_over_blank"][f] = {
                    "class": [STEPPED] * count, "value": [x - y for x, y in zip(n, b, strict=True)],
                    "accuracy": [1e-30 * scale] * count, "scale": scale}  # fmt: skip
        if fam.cohort_net:
            block["not_compared"] = {f"cohort_net_{f}": [0.9 * x for x in win[f]["value"]]
                                     for f in FATES}  # fmt: skip
        runs[run_name] = block
    echo = resolved(expected_echo(name))
    plants = []
    some_run = next(r for r in fam.runs if not fam.runs[r].blank)
    for plant in sorted(PLANTS_REQUIRED[name]):
        e = {
            "plant": plant,
            "run": some_run,
            "quantity": "n_R",
            "time_s": times[-1],
            "honest": 1.0,
            "planted": 2.0,
            "relative_distance": 1.0,
            "scale": 1.0,
        }
        if plant == "P1′":
            e |= {"quantity": "route2_durable", "route2_bound": 1e-9,
                  "distance_in_route2_bounds": 1e9}  # fmt: skip
        plants.append(e)
    return {
        "kind": KIND, "family": name, "inputs": echo, "units": dict(UNITS), "times_s": times,
        "samples_s": list(fam.samples), "runs": runs, "plants": plants,
        "method": {"primary": "made up", "second": "made up", "tolerances": "made up",
                   "safety_factor": 2.0, "largest_difference_between_methods": {},
                   "run_time_s": RUN_TIMES},
        "provenance": {"revision": "0" * 40, "dirty_paths": [], "writer_version": "made up",
                       "python": "-", "numpy": "-", "scipy": "-", "mpmath": "-",
                       "sha256_of_this_file_excluded": True},
    }  # fmt: skip


def _mutants():
    """(label, family, mutation, the fault's words or None for a control that must pass)."""

    def drop(path):
        def apply(d):
            *head, last = path
            node = d
            for k in head:
                node = node[k]
            del node[last]

        return apply

    def setter(path, value):
        def apply(d):
            *head, last = path
            node = d
            for k in head:
                node = node[k]
            node[last] = value(node[last]) if callable(value) else value

        return apply

    ps = ("runs", "p_sched returned")
    series = (*ps, "series")
    return [
        (
            "a missing registered top-level key",
            "invented",
            drop(("method",)),
            "registered key 'method' is missing",
        ),
        (
            "a missing run",
            "invented",
            drop(("runs", "p=1 returned")),
            "run 'p=1 returned' is missing",
        ),
        ("a missing readout", "invented", drop((*series, "n_R")), "readout 'n_R' is missing"),
        (
            "a missing output time in one series",
            "invented",
            setter((*series, "int_D_R", "value"), lambda v: v[:-1]),
            "one finite float per output",
        ),
        (
            "a missing output time in times_s",
            "invented",
            setter(("times_s",), lambda v: v[:-1]),
            "times_s",
        ),
        (
            "a constant entry at -0.0",
            "invented",
            setter((*series, "label_R_win", "value", 0), -0.0),
            "is not +0.0",
        ),
        (
            "a constant entry with an accuracy",
            "invented",
            setter((*series, "label_R_win", "accuracy", 0), 0.0),
            "accuracy 0.0 is not null",
        ),
        (
            "stepped where SPEC.md §4 gives constant",
            "invented",
            setter((*series, "label_R_post", "class", 3), STEPPED),
            "where SPEC.md §4 gives",
        ),
        (
            "constant where SPEC.md §4 gives stepped",
            "invented",
            setter((*series, "n_R", "class", 5), CONSTANT),
            "where SPEC.md §4 gives",
        ),
        (
            "a spread class",
            "invented",
            setter((*series, "n_M", "class", 7), "spread"),
            "class 'spread' is refused",
        ),
        (
            "a non-finite value (in the parsed document)",
            "invented",
            setter((*series, "n_N", "value", 4), math.nan),
            "one finite float per output",
        ),
        ("a wrong unit", "invented", setter(("units", "energy"), "nJ"), "units:"),
        ("a wrong kind", "invented", setter(("kind",), "cells.fr38.reference@1"), "kind:"),
        (
            "a judged accuracy over 1e-11 s_y",
            "invented",
            setter((*series, "n_R", "accuracy", 9), lambda a: 2e-11 * 7e-8),
            "exceeds 1e-11 s_y",
        ),
        (
            "a scale that is not READOUTS.md §3's",
            "invented",
            setter((*series, "H_tx", "scale"), lambda s: 2 * s),
            "where READOUTS.md §3 gives",
        ),
        (
            "an idle fate's survival ratio of 0.0",
            "invented",
            setter(("runs", "p=0 returned", "survival", 0, "ratio"), 0.0),
            "ratio is null",
        ),
        (
            "route 2's value apart from the win class",
            "invented",
            setter((*ps, "route2", 1, "value"), lambda v: v * (1 + 1e-9)),
            "not the win class",
        ),
        (
            "the blank carrying route 2",
            "invented",
            setter(("runs", "blank", "route2"), []),
            "the blank carries 'route2'",
        ),
        (
            "a P1′ entry without route 2's bound",
            "invented",
            lambda d: [e.pop("route2_bound") for e in d["plants"] if e["plant"] == "P1′"],
            "registered key 'route2_bound' is missing",
        ),
        (
            "no entry of P5",
            "invented",
            setter(("plants",), lambda p: [e for e in p if e["plant"] != "P5"]),
            "no entry of P5",
        ),
        (
            "an excess entry declared constant",
            "invented",
            setter((*ps, "excess_over_blank", "durable", "class", 2), CONSTANT),
            "where SPEC.md §4 gives 'stepped'",
        ),
        (
            "a gross that is not the sum of its classes",
            "invented",
            setter((*series, "released_present_gross_durable", "value", 20), lambda v: v * 1.001),
            "not the sum of its three classes",
        ),
        (
            "a survival count apart from the win class",
            "invented",
            setter((*ps, "survival", 0, "alive_t2"), lambda v: v * (1 + 1e-12)),
            "not the win class at t2",
        ),
        (
            "a safety factor below 2",
            "invented",
            setter(("method", "safety_factor"), 1.5),
            "safety_factor",
        ),
        (
            "the run times in the file, not the sidecar",
            "invented",
            setter(("method", "run_time_s"), 12.5),
            "sidecar",
        ),
        (
            "sha256_of_this_file_excluded false",
            "invented",
            setter(("provenance", "sha256_of_this_file_excluded"), False),
            "sha256_of_this_file_excluded",
        ),
        (
            "the classes not summing to their row",
            "invented",
            setter((*series, "label_R_s_pool0", "value", 30), lambda v: v * 1.01),
            "do not sum to n_R_s",
        ),
        (
            "an invented run whose p differs from its name",
            "invented",
            setter(("inputs", "runs", "p=1 returned", "p"), [[0.0, 0.9]]),
            "differs from its name",
        ),
        (
            "a mutated echoed input (AN's tau)",
            "AN",
            setter(("inputs", "tau_s"), 2400.0001),
            "inputs.tau_s",
        ),
        (
            "a missing echoed input (AF's k_s)",
            "AF",
            drop(("inputs", "k_s_per_s")),
            "inputs.k_s_per_s: missing",
        ),
        (
            "C's store rate mutated",
            "C",
            setter(("inputs", "store", "forward_per_s_at_c0"), 1 / 3001),
            "inputs.store.forward_per_s_at_c0",
        ),
        (
            "D's water L_p missing",
            "D",
            drop(("inputs", "water", "L_p_m_per_Pa_s")),
            "inputs.water.L_p_m_per_Pa_s: missing",
        ),
        ("D's water block missing", "D", drop(("inputs", "water")), "inputs.water: missing"),
        ("B's A1 value mutated (K_X)", "B", setter(("inputs", "K_X_mM"), 1.1e-3), "inputs.K_X_mM"),
        (
            "B's R_s initial missing",
            "B",
            drop(("inputs", "initial_mM", "R_s")),
            "inputs.initial_mM.R_s: missing",
        ),
        (
            "B: a win class stepped before its window opens",
            "B",
            setter(("runs", "p=0.55 returned", "series", "label_R_win", "class", 0), STEPPED),
            "where SPEC.md §4 gives",
        ),
        (
            "B: a missing translation readout",
            "B",
            drop(("runs", "p=0.55 held", "series", "C_tl_s_8")),
            "readout 'C_tl_s_8' is missing",
        ),
        (
            "D: the G scale changed by 1e-6",
            "D",
            setter(
                ("runs", "p_sched returned", "series", "G_minus_G0", "scale"),
                lambda s: s * (1 - 1e-6),
            ),
            "where READOUTS.md §3 gives",
        ),
        (
            "D: a missing volume series",
            "D",
            drop(("runs", "blank", "series", "V")),
            "readout 'V' is missing",
        ),
        (
            "C: a judged store heat over 1e-11 s_y",
            "C",
            setter(
                ("runs", "p_sched returned", "series", "H_store", "accuracy", 40), lambda a: 1.0
            ),
            "exceeds 1e-11 s_y",
        ),
        (
            "a dirty registered reference",
            "AN",
            setter(("provenance", "dirty_paths"), ["x.py"]),
            "clean tree",
        ),
        # Controls, which must pass:
        (
            "control: an extra key at the top, in a run and in a plant entry",
            "invented",
            lambda d: (
                d.update(extra=1),
                d["runs"]["p_sched returned"].update(extra=2),
                d["plants"][0].update(extra=3),
            ),
            None,
        ),
        (
            "control: hash_seeds_checked present",
            "invented",
            setter(("provenance", "hash_seeds_checked"), [0, 1, 4242]),
            None,
        ),
        (
            "control: a reported readout's accuracy over 1e-11 s_y (C_tx_3)",
            "invented",
            setter((*series, "C_tx_3", "accuracy", 9), lambda a: 2e-11 * 1e-7),
            None,
        ),
        (
            "control: B's reported readout over 1e-11 s_y (F_rib)",
            "B",
            setter(("runs", "p=0.55 held", "series", "F_rib", "accuracy", 3), lambda a: 1.0),
            None,
        ),
        (
            "control: B's p echoed as 0.55 in a run, and p_sched null",
            "B",
            lambda d: (
                d["inputs"]["runs"]["p=0.55 held"].update(p=0.55),
                d["inputs"].update(p_sched=None),
            ),
            None,
        ),
        (
            "control: D's bath echoed at §1.1's 140 mM",
            "D",
            lambda d: d["inputs"].update(bath_mM={"K": 140.0, "Y": 140.0}, bath_trace_mM=1e-15),
            None,
        ),
        (
            "control: an unknown echoed key, listed unchecked",
            "AN",
            lambda d: d["inputs"].update(made_up_note=1.0),
            None,
        ),
        (
            "control: an extra run, ignored and listed",
            "invented",
            lambda d: d["runs"].update({"p=0 held": copy.deepcopy(d["runs"]["p=0 returned"])}),
            None,
        ),
        (
            "a second route-2 entry for one fate and time",
            "invented",
            lambda d: d["runs"]["p_sched held"]["route2"].append(
                dict(d["runs"]["p_sched held"]["route2"][0])
            ),
            "a second entry",
        ),
    ]


def check_reader(sample=None, sums=None):
    """The first read and the reader's planted faults (module docstring): {label: {"ok": ...}}."""
    out = {}
    data, sums_text = load_sample(sample, sums)
    digest = hashlib.sha256(data).hexdigest()
    listed = sums_of(sums_text).get(SAMPLE)
    out["the invented file's sha256 is the tag's SHA256SUMS line"] = {
        "sha256": digest,
        "listed": listed,
        "ok": digest == listed,
    }
    doc = parse(data.decode())
    reference, summary, problems = read_document(doc, "invented")
    out["the first read: reference_invented.json passes C0"] = {
        "problems": problems[:20],
        "summary": summary,
        "ok": reference is not None,
    }
    for name in ("AF", "AN", "B", "C", "D"):
        reference, summary, problems = read_document(made_up(name), name)
        out[f"a made-up document in {name}'s layout passes"] = {
            "problems": problems[:10],
            "ok": reference is not None and not problems,
        }
    docs = {"invented": doc, **{n: made_up(n) for n in ("AF", "AN", "B", "C", "D")}}
    for label, family, mutate, words in _mutants():
        d = copy.deepcopy(docs[family])
        mutate(d)
        reference, _, problems = read_document(d, family)
        if words is None:
            ok = reference is not None and not problems
        else:
            ok = reference is None and any(words in p for p in problems)
        out[("refused: " if words else "") + label] = {"problems": problems[:3], "ok": ok}
    try:
        parse('{"a": NaN}')
        refused = False
    except ValueError:
        refused = True
    out["refused: NaN in the text, at the parse"] = {"ok": refused}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check-reader", action="store_true")
    parser.add_argument("--sample", help="the invented file (default: the references' tag)")
    parser.add_argument("--sums", help="its SHA256SUMS (default: the references' tag)")
    parser.add_argument("command", nargs="?", choices=("read", "c0"))
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)
    if args.check_reader:
        results = check_reader(args.sample, args.sums)
        print(json.dumps(results, indent=1, default=str))
        failed = [label for label, r in results.items() if not r["ok"]]
        print(json.dumps({"checks": len(results), "failed": failed}))
        return 0 if not failed else 1
    if args.command == "read":
        bad = 0
        for path in args.paths:
            reference, summary, problems = read(path)
            print(
                json.dumps(
                    {
                        "file": path,
                        "passes": reference is not None,
                        "problems": problems,
                        "summary": summary,
                    },
                    indent=1,
                    default=str,
                )
            )
            bad += reference is None
        return 0 if not bad else 1
    if args.command == "c0":
        results = c0(args.paths[0])
        report = {name: {"passes": r["reference"] is not None, "problems": r["problems"],
                         "summary": r["summary"], "sha256": r.get("sha256")}
                  for name, r in results.items()}  # fmt: skip
        print(json.dumps(report, indent=1, default=str))
        return 0 if all(r["passes"] for r in report.values()) else 1
    parser.error("give --check-reader, read FILE... or c0 DIR")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
