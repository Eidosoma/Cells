"""P1's positivity predictor (docs/CORE_SEAMS_DESIGN.md §17; §19 as amended: the general layout
only), @3's part. The selector is the binding owner's ruling (a) of 19 November 2026: each stage
row may name its read's law as a third item.

- Stage rows are shared by their (species, node), whatever law a third item names: two kinds'
  reads on one row under different laws are refused at binding, where a key on the whole row
  would admit them (the plant), and a row of any other length is refused.
"""

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.registry import kind_registry
from tests.unit.test_kind_rules import declaring, reader, registry


def test_stage_rows_are_shared_by_species_and_node_whatever_law_each_names():
    shared = registry(
        reader("alpha", "alpha_block", (("K", "cell_0", "tests.law_a@1"),)),
        reader("beta", "beta_block", (("K", "cell_0", "tests.law_b@1"),)),
    )
    with kind_registry.scope(shared):
        with pytest.raises(
            ConfigError, match=r"tests.alpha@1 and tests.beta@1 both read row \('K', 'cell_0'\)"
        ):
            parse_spec(declaring("alpha_block", "beta_block"))
    apart = registry(
        reader("alpha", "alpha_block", (("K", "cell_0", "tests.law_a@1"),)),
        reader("beta", "beta_block", (("Na", "cell_0", "tests.law_a@1"),)),
    )
    with kind_registry.scope(apart):
        parse_spec(declaring("alpha_block", "beta_block"))  # Disjoint rows: admitted.


def test_a_stage_row_is_two_or_three_items():
    with kind_registry.scope(registry(reader("alpha", "alpha_block", (("K",),)))):
        with pytest.raises(ConfigError, match=r"stage row \('K',\) is not \(species, node ID\)"):
            parse_spec(declaring("alpha_block"))
