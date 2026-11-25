"""Names and numbers of the contract (`spec/CRITERIA.md`, `spec/READOUTS.md`, `spec/TABLE.md`).
Nothing here is fitted.
"""

from __future__ import annotations

import hashlib

PROTOCOL = "ensemble-reexpression-v1"
PART = 1

EPS = 2.0**-52
V_STAR = 0.12  # V, the gate law's domain (SPEC section 5)
CLOSE_SHARE = 4e-12  # of a scale (SPEC section 6)
PHI_CLOSE_SHARE = 4.3e-12  # of V_STAR, for phi_out (SPEC section 6)
ROUND_COUNT = 8  # e_round = 8 eps (S + 1) s
STORE_COUNT = 2.5  # e_store = 2.5 eps (S + 1) amount_refs
THRESHOLD = 10  # theta = 10 (e_round + e_store)
ORDER_TOP = 4.5  # the window is [p - 1/2, 4 1/2]
LEGACY_ORDER = 4
POWER_FACTOR = 10  # tested when beta <= D / 10
PLANT_RULE = 10  # the sizing rule of PLANTS section 1

TIME_TOL_S = 1e-12  # a time matches a registered one within this
ECHO_RTOL = 1e-12  # SPEC section 2.4
GRID_TOL = 2 * EPS  # of t, SPEC section 4

TABLE_KIND = "ensemble-reexpression engine table, version 1"
STRINGS_KIND = "ensemble-reexpression registered strings, version 1"
RETRY_KIND = "ensemble-reexpression retry owed, version 1"
POWER_KIND = "ensemble-reexpression power, version 1"
C0_KIND = "ensemble-reexpression judge C0, version 1"
RECORD_KIND = "ensemble-reexpression judge record, version 1"
HASHES_KIND = "ensemble-reexpression table hashes, version 1"
SETTLEMENTS_KIND = "ensemble-reexpression settlements, version 1"

UNITS = {"amount": "fmol", "energy": "pJ", "potential": "V", "time": "s"}
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()

POOL_ARRAYS = (
    "occupied",
    "bonds",
    "free",
    "fragments",
    "time_s",
    "last_event_time_s",
    "event_count",
    "pending_time_s",
    "pending_event",
    "pending_valid",
    "reaction_counts",
    "removed",
    "single_returns",
    "dissolved",
    "dwell_completed_s",
    "first_passage_s",
    "full_first_s",
    "full_dwell_completed_s",
    "fault",
)

BOOLEAN_ARRAY = "pending_valid"  # the only captured array of booleans (Amendment 2, item 7 (d))

# TABLE section 3: every key of a run's entry.
RUN_KEYS = (
    "status",
    "world",
    "variant",
    "seed_index",
    "world_id",
    "step_s",
    "steps",
    "t",
    "rows",
    "potential_t",
    "potentials",
    "pool",
    "path",
    "inputs",
    "strings",
    "declared_strings",
    "definition",
    "checks",
    "restart",
    "host_patch",
    "refusal",
    "source",
    "record",
    "record_sha256",
)
SOURCE_STRINGS = (
    "engine_revision",
    "snapshot",
    "snapshot_patch_sha256",
    "python",
    "numpy",
    "jax",
    "jaxlib",
    "cpu_model",
)
REFUSAL_KINDS = ("definition", "domain", "check", "harness")
ASSEMBLY_KEYS = ("assembly_observable", "composed_file_fingerprint", "pool_seeds", "switch_list")

# The labels that TABLE section 5 lists, and the one that Amendment 1 (item 5) adds for the
# rehearsal.
LABELS = (
    "inner_model",
    "rk4",
    "field_solver",
    "field_solver_floor",
    "closure",
    "constant_field",
    "kv15_mh",
    "nak_pump_positive",
    "maintained_fuel",
    "junction_relaxation",
    "logmean_face",
    "pool_model",
    "pool_topology",
    "assembly_observable",
)

# The texts of the spec folder that this judge's code was written from, beside its own (CRITERIA
# section 5). The second is the exporter's copy: what its builder receives of Amendment 2.
AMENDMENTS = ("AMENDMENT-1-2026-11-25.md", "AMENDMENT-2-2026-11-25.md")
EXPORTER_COPY = "AMENDMENT-2-2026-11-25_EXPORTER.md"
EXPORTER_ITEMS = ("2", "4", "7", "8", "9.1", "10")

# The flags that the checker settles (README section 6), by kind: the corner of item 5 (a), the
# readings 12 and 24, and the reload of a restart (CRITERIA section 4.1 and reading 25).
CORNER = "untested outside its window"
AT_ZERO = "row at time 0"
NOT_FINITE = "non-finite value"
RELOAD = "restart to confirm"

# What a settled flag counts as (README section 6). The checker says which.
BY_THE_RULE = "by the rule"
COUNTS_AS = (BY_THE_RULE, "fail", "inconclusive")
STANDS = "stands"
LIFTED = "lifted"
PENDING = "pending"  # a state of a verdict: nothing but unsettled flags keeps it from a pass

# The outcomes of an entry.
PASS = "pass"
FAIL = "fail"
INCONCLUSIVE = "inconclusive"
NOT_FORMED = "not formed"
NOT_TESTED = "not tested"
REPORTED = "reported"
