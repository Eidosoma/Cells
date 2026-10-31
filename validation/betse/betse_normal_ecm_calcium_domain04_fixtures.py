"""Prospective full roster with the exact saved third-call NaN domain input.

Legacy scientific fixture generators stay unchanged. Original input metadata is
retained; raw-domain classification belongs to the test/report, not the packet.
"""

import hashlib
import json
from pathlib import Path

from validation.betse import betse_normal_ecm_calcium_join_fixtures as legacy

CASES = (
    "active",
    "polarized",
    "rectangular",
    "fast_duplicate",
    "smoothed",
    "temperature_split",
    "time_dilation",
    "publication_carry",
    "zero_membrane_Ca",
    "negative_environment_Ca",
    "stationary_Ca",
    "no_CaATP",
    "neutral_genes",
    "zero_boundary",
    "cluster_open",
)
RAW_DOMAIN_CASES = ("negative_genes",)
RAW_CASES = (
    "first_gene_negative",
    "second_gene_negative",
    "CaATP_equilibrium_underflow",
    "late_CaATP_underflow",
    "bootstrap_zero_screen",
    "CaATP_alpha_overflow",
)
DEPENDENCIES = (
    "ER_requested",
    "ER_kinetics_injected",
    "maintained_override",
    "missing_Ca",
    "wrong_Ca_valence",
    "changed_rate_cache",
    "invented_rate_presence",
    "wrong_clock",
    "varying_dt",
    "supplied_old_field",
    "negative_alpha",
    "missing_network_cache",
)
COMPONENT_CONTROLS = ("stationary_Ca", "no_CaATP", "neutral_genes", "zero_boundary")
SAVED_INPUT_SHA256 = "41d5da23526aac015a219e2c7d535998c7181fc40520d5ef1a967034af808606"
fixture = legacy.fixture
raw_fixture = legacy.raw_fixture


def raw_domain_fixture(case):
    if case not in RAW_DOMAIN_CASES:
        raise ValueError("Choose the declared original-input NaN source-domain history")
    data = (
        Path(__file__)
        .with_name("betse_normal_ecm_calcium_domain04_negative_genes.json")
        .read_bytes()
    )
    if hashlib.sha256(data).hexdigest() != SAVED_INPUT_SHA256:
        raise ValueError("The exact original failing input changed")
    result = json.loads(data)
    if result["case_id"] != case:
        raise ValueError("Saved raw-domain input identity differs")
    return result
