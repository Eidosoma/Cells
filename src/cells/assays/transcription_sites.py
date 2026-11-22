"""Called transcription sites: roster denominators, two-channel ratios and per-copy detection.

External analysis instruments for transcription-site microscopy (FR-38, item 4). They read only
the tables or simulated means passed to them. They never feed back into a simulation, book no
energy and read no hidden simulation state. Every statistic is named for its denominator, and
detection acts on each gene copy before anything is averaged.
"""

import math
from collections.abc import Iterable, Mapping
from numbers import Integral, Real

import numpy as np
from scipy.special import betainc, gammainc


class IncompleteObservation(ValueError):
    """The tables do not pair every counted site, or every rostered cell, with one measurement.

    `issues` holds every offending record at once, each a dict with its `kind` and IDs, so a
    table can be corrected in one pass. Malformed values raise a plain ValueError instead.
    """

    def __init__(self, issues):
        self.issues = tuple(issues)
        named = [
            f"{issue['kind']}({', '.join(f'{k}={v!r}' for k, v in issue.items() if k != 'kind')})"
            for issue in self.issues[:6]
        ]
        if len(self.issues) > 6:
            named.append(f"and {len(self.issues) - 6} more")
        count = len(self.issues)
        super().__init__(f"Incomplete observation, {count} issue(s): " + "; ".join(named))


def _identity(value, what):
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, Integral) and not isinstance(value, bool):
        return int(value)
    raise ValueError(f"{what} must be a nonblank string or an integer, not {value!r}")


def _order(identity):
    """Sort key for IDs that mix integers and strings; integers come first."""
    return isinstance(identity, str), identity


def _count(value, what):
    if isinstance(value, Integral) and not isinstance(value, bool) and value >= 0:
        return int(value)
    raise ValueError(f"{what} must be a nonnegative integer, not {value!r}")


def _finite(value, what):
    if isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    raise ValueError(f"{what} must be a finite real number, not {value!r}")


def _fields(row, width, what):
    try:
        fields = tuple(row)
    except TypeError:
        fields = None
    if isinstance(row, str) or fields is None or len(fields) != width:
        raise ValueError(f"Each {what} row has {width} fields, not {row!r}")
    return fields


def summarize_called_sites(roster, spots):
    """Per-sample summaries of called transcription sites, with every denominator explicit.

    `roster` rows are (sample, cell, declared_sites): one row for each cell examined, with the
    number of sites called in it. A confirmed zero-site cell is a row with 0, and it counts in
    every per-cell denominator. `spots` rows are (sample, cell, spot, brightness): one row for
    each called site. Brightness is a finite real (background-corrected values may be
    negative), or None when the spot was counted but not measured. IDs are nonblank strings or
    integers. A cell ID is scoped by its sample and a spot ID by its cell, so IDs may recur in
    other samples. Samples are never pooled: give each preparation its own sample ID.

    The result maps each sample ID to a record carrying that ID and:
    - roster_cells, positive_cells (at least one called site) and zero_site_cells;
    - called_sites, the counted spots, and called_sites_per_roster_cell;
    - mean_brightness_per_called_site, pooled over the sample's called spots;
    - called_signal_per_roster_cell, the summed spot brightness divided by all roster cells,
      zero-site cells included;
    - mean_of_positive_cell_mean_brightness, each positive cell's own mean spot brightness,
      averaged over positive cells;
    - cells: per cell, its spot IDs, called sites, summed brightness (called_signal) and mean
      brightness (None for a zero-site cell).
    A statistic without a denominator is None, with its reason under `undefined`. Samples, cells
    and spot IDs are sorted, and sums are exactly rounded, so row order does not matter.

    An incomplete table is refused, not summarised. Each of these raises IncompleteObservation,
    which names every offending ID at once:
    - a spot that matches no roster cell;
    - a duplicated cell or spot;
    - a spot whose brightness is None;
    - a cell whose declared count differs from its spot rows.
    One incomplete sample refuses the whole call. A partial summary would invite an average over
    whatever survived. Refusal makes any exclusion an explicit act of the calling analysis, for
    example removing a cell from the roster. The other readouts here likewise refuse rather than
    substitute a missing observation. Malformed values raise a plain ValueError: booleans, NaN
    or infinite brightness (None, not NaN, marks an unmeasured spot), negative or non-integer
    counts, blank IDs, rows of the wrong width and an empty roster.
    """
    declared, issues = {}, []
    for row in roster:
        sample, cell, sites = _fields(row, 3, "roster")
        key = _identity(sample, "A sample ID"), _identity(cell, "A cell ID")
        sites = _count(sites, "A declared number of called sites")
        if key in declared:
            issues.append(dict(kind="duplicated_cell", sample=key[0], cell=key[1]))
        declared[key] = sites
    if not declared:
        raise ValueError("An empty roster has no per-cell denominator")
    brightness = {}
    for row in spots:
        sample, cell, spot, value = _fields(row, 4, "spot")
        key = (
            _identity(sample, "A sample ID"),
            _identity(cell, "A cell ID"),
            _identity(spot, "A spot ID"),
        )
        value = None if value is None else _finite(value, "A spot brightness")
        where = dict(sample=key[0], cell=key[1], spot=key[2])
        if key in brightness:
            issues.append(dict(kind="duplicated_spot", **where))
        elif key[:2] not in declared:
            issues.append(dict(kind="unmatched_spot", **where))
        elif value is None:
            issues.append(dict(kind="unmeasured_spot", **where))
        brightness.setdefault(key, value)
    recorded = {key: [] for key in declared}
    for sample, cell, spot in brightness:
        recorded.get((sample, cell), []).append(spot)
    for (sample, cell), sites in declared.items():
        if len(recorded[sample, cell]) != sites:
            issues.append(
                dict(
                    kind="count_mismatch",
                    sample=sample,
                    cell=cell,
                    declared_sites=sites,
                    spot_records=len(recorded[sample, cell]),
                )
            )
    if issues:
        raise IncompleteObservation(issues)
    samples = {}
    for sample, cell in declared:
        samples.setdefault(sample, []).append(cell)
    return {
        sample: _sample_record(sample, sorted(cells, key=_order), recorded, brightness)
        for sample, cells in sorted(samples.items(), key=lambda item: _order(item[0]))
    }


def _sample_record(sample, cell_ids, recorded, brightness):
    cells, values = [], []
    for cell in cell_ids:
        spot_ids = tuple(sorted(recorded[sample, cell], key=_order))
        own = [brightness[sample, cell, spot] for spot in spot_ids]
        values += own
        signal = math.fsum(own)
        cells.append(
            dict(
                cell=cell,
                called_sites=len(own),
                spot_ids=spot_ids,
                called_signal=signal,
                mean_brightness=signal / len(own) if own else None,
            )
        )
    total, sites = math.fsum(values), len(values)
    positive = [record["mean_brightness"] for record in cells if record["called_sites"]]
    undefined = {}
    if not sites:
        undefined["mean_brightness_per_called_site"] = "the sample has no called site"
        undefined["mean_of_positive_cell_mean_brightness"] = "no roster cell has a called site"
    return dict(
        sample=sample,
        roster_cells=len(cells),
        positive_cells=len(positive),
        zero_site_cells=len(cells) - len(positive),
        called_sites=sites,
        called_sites_per_roster_cell=sites / len(cells),
        mean_brightness_per_called_site=total / sites if sites else None,
        called_signal_per_roster_cell=total / len(cells),
        mean_of_positive_cell_mean_brightness=(
            math.fsum(positive) / len(positive) if positive else None
        ),
        cells=tuple(cells),
        undefined=undefined,
    )


def two_channel_ratios(cell_ids, numerator, denominator):
    """Two named ratio statistics for signals in two channels on one explicit roster of cells.

    `cell_ids` is the roster of one sample: distinct nonblank-string or integer IDs.
    `numerator` and `denominator` map each roster cell to its finite signal in that channel.
    Background-corrected signals may be negative. A signal that was not measured is None.

    - ratio_of_pooled_means: the mean numerator signal over the mean denominator signal, equal
      to the ratio of the pooled sums. It is undefined unless the pooled denominator is positive.
    - mean_of_within_cell_ratios: each cell's own numerator/denominator ratio, averaged over the
      roster. It is undefined unless every cell's denominator signal is positive, since a zero
      denominator has no ratio and a negative one flips its sign.
    The two estimate different quantities and generally differ, so each keeps its own name and
    neither stands in for the other. An undefined statistic is None, and its reason, naming the
    cells concerned, is under `undefined`. The channel means and the number of cells with a
    positive denominator are reported too.

    Both channels must cover exactly the roster. A missing, unrostered or unmeasured (None)
    signal raises IncompleteObservation, naming every such cell and channel, for the reasons
    given in `summarize_called_sites`. Malformed values raise a plain ValueError: booleans,
    NaN, infinities, blank or duplicated roster IDs and an empty roster.
    """
    roster = [_identity(cell, "A roster cell ID") for cell in cell_ids]
    if not roster or len(set(roster)) != len(roster):
        raise ValueError("Two-channel ratios need a nonempty roster of distinct cell IDs")
    signals, issues = {}, []
    for channel, mapping in (("numerator", numerator), ("denominator", denominator)):
        if not isinstance(mapping, Mapping):
            raise ValueError(f"The {channel} channel must map cell IDs to signals")
        keys = {_identity(cell, f"A {channel} cell ID") for cell in mapping}
        for cell in roster:
            if cell not in keys:
                issues.append(dict(kind="missing_signal", channel=channel, cell=cell))
            elif mapping[cell] is None:
                issues.append(dict(kind="unmeasured_signal", channel=channel, cell=cell))
            else:
                signals[channel, cell] = _finite(mapping[cell], f"A {channel} signal")
        issues += [
            dict(kind="unrostered_signal", channel=channel, cell=cell)
            for cell in sorted(keys - set(roster), key=_order)
        ]
    if issues:
        raise IncompleteObservation(issues)
    top = [signals["numerator", cell] for cell in roster]
    bottom = [signals["denominator", cell] for cell in roster]
    pooled_top, pooled_bottom = math.fsum(top), math.fsum(bottom)
    nonpositive = tuple(
        sorted((cell for cell, value in zip(roster, bottom, strict=True) if value <= 0), key=_order)
    )
    undefined = {}
    if pooled_bottom <= 0:
        undefined["ratio_of_pooled_means"] = (
            f"the pooled denominator signal is {pooled_bottom!r}, not positive"
        )
    if nonpositive:
        undefined["mean_of_within_cell_ratios"] = (
            f"{len(nonpositive)} cell(s) have a nonpositive denominator signal: {nonpositive!r}"
        )
    cells = len(roster)
    return dict(
        roster_cells=cells,
        cell_ids=tuple(sorted(roster, key=_order)),
        numerator_mean=pooled_top / cells,
        denominator_mean=pooled_bottom / cells,
        cells_with_positive_denominator=cells - len(nonpositive),
        ratio_of_pooled_means=pooled_top / pooled_bottom if pooled_bottom > 0 else None,
        mean_of_within_cell_ratios=(
            None
            if nonpositive
            else math.fsum(t / b for t, b in zip(top, bottom, strict=True)) / cells
        ),
        undefined=undefined,
    )


_PER_COPY = (
    "A gene copy is a called site when its own chain count reaches the threshold (at least "
    "`threshold` chains). Calls are made per copy before any average over copies or cells, and "
    "per-cell values are expectations over cells."
)
_ASSUMPTIONS = dict(
    poisson=(
        "Chains per copy are Poisson about the given mean. This is exact for Poisson arrivals, "
        "homogeneous or not, with residence times independent of each other and of the arrivals, "
        "on a copy that starts empty or with a Poisson load. It is not exact for a definite "
        "initial count, exclusion between chains, or promoter switching and bursts."
    ),
    negative_binomial=(
        "Chains per copy are negative binomial about the given mean with the declared Fano "
        "factor F (variance F times the mean). This is exact for the stationary count from bursts "
        "at Poisson times, each of a geometric number of chains on 1, 2, ... with mean F, every "
        "chain leaving independently after an exponential residence. Otherwise it is a declared "
        "two-moment form."
    ),
    supplied_counts=(
        "Chains per copy follow the empirical distribution of the supplied counts, with no family "
        "assumed. The expectations carry the sampling error of those draws, not estimated here."
    ),
)


def _threshold(value):
    if isinstance(value, Integral) and not isinstance(value, bool) and value >= 1:
        return int(value)
    raise ValueError(f"The detection threshold must be an integer of at least 1, not {value!r}")


def _per_class(values, what):
    """Finite nonnegative reals, one per copy class, checked before any coercion."""
    if isinstance(values, np.ndarray):
        numeric = values.dtype.kind in "iuf" and values.ndim <= 1
        items = values.reshape(-1).tolist() if numeric else None
    elif isinstance(values, Real):
        items = [values]
    elif isinstance(values, Iterable) and not isinstance(values, str):
        items = list(values)
    else:
        items = None
    if not items or not all(
        isinstance(v, Real) and not isinstance(v, bool) and math.isfinite(v) and v >= 0
        for v in items
    ):
        raise ValueError(f"{what} must be finite nonnegative numbers, one per copy class")
    return np.array(items, dtype=np.float64)


def _draws(values):
    if isinstance(values, np.ndarray):
        whole = values.dtype.kind in "iu" and values.ndim == 1
    elif isinstance(values, Iterable) and not isinstance(values, str):
        values = list(values)
        whole = all(isinstance(v, Integral) and not isinstance(v, bool) for v in values)
    else:
        whole = False
    counts = np.asarray(values, dtype=np.int64) if whole and len(values) else None
    if counts is None or (counts < 0).any():
        raise ValueError(
            "Each copy class needs a nonempty sequence of nonnegative integer chain counts "
            "(floats are refused, even when whole, so that a mean cannot pass as a count)"
        )
    return counts


def _expectation(distribution, parameters, threshold, copies, means, called, visible):
    called_sites = math.fsum((copies * called).tolist())
    visible_chains = math.fsum((copies * visible).tolist())
    undefined = {}
    if called_sites <= 0:
        undefined["chains_per_called_site"] = "the expected number of called sites per cell is 0"
    return dict(
        distribution=distribution,
        parameters=parameters,
        assumptions=(_PER_COPY, _ASSUMPTIONS[distribution]),
        threshold=threshold,
        copy_classes=len(copies),
        copies_per_cell=math.fsum(copies.tolist()),
        mean_chains_per_copy=tuple(means.tolist()),
        call_probability_per_copy=tuple(called.tolist()),
        called_sites_per_cell=called_sites,
        visible_chains_per_cell=visible_chains,
        all_chains_per_cell=math.fsum((copies * means).tolist()),
        chains_per_called_site=visible_chains / called_sites if called_sites > 0 else None,
        undefined=undefined,
    )


def expected_called_sites(
    mean_chains_per_copy, copies_per_cell, *, threshold, distribution, fano_factor=None
):
    """Expected called sites per cell from mean chain occupancy, thresholded per gene copy.

    A copy is a called site when it carries at least `threshold` chains, an integer of at least
    1. The call acts on each copy's own count before anything is averaged. Thresholding a mean,
    or pooling copies with different means, gives a different answer, because the call is not
    linear in the count. A deterministic simulation gives only the mean, so the distribution of
    the count about it is a required, named input:

    - "poisson": the count on each copy is Poisson with the given mean. This is exact when
      chains arrive on the copy as a Poisson process, homogeneous or not, and each stays for a
      residence time independent of the others and of the arrivals, of any distribution. The
      copy must start empty or with a Poisson load whose chains also leave independently. This
      is the infinite-server queue (Eick, Massey and Whitt 1993, Oper. Res. 41:731). It is not
      exact for a definite nonzero initial count, which leaves a binomial part, for exclusion
      or interference between chains on one copy, or for promoter switching and bursts, which
      widen the distribution.
    - "negative_binomial": the count is negative binomial with the given mean mu and the
      declared Fano factor F > 1, so its variance is F mu and its shape mu / (F - 1). One
      mechanism gives exactly this: the stationary count when bursts arrive as a Poisson
      process, each adding a geometric number of chains on 1, 2, ... with mean F, and every
      chain leaves independently after an exponentially distributed residence. Away from that
      stationary state, or with other residence times, it is a two-moment form, and F is the
      user's declaration, not an inference. The same bursts with one fixed residence time give
      a Fano factor of 2F - 1.

    `mean_chains_per_copy` gives the mean number of attached chains on one gene copy, one
    entry per copy class (for example per allele or per promoter state). It is a molecule count,
    not an amount, and never a per-cell or population average over copies with different means.
    `copies_per_cell` gives the mean number of copies of each class per cell. Fractional values
    express a population average of copy number, since only expectations are formed.

    The record names the distribution, its parameters and its assumptions. Per cell, it gives:
    - called_sites_per_cell;
    - visible_chains_per_cell, the chains on copies that reach the threshold;
    - all_chains_per_cell, called or not.
    It also gives chains_per_called_site, the ratio of visible chains to called sites. That is
    a ratio of expectations, the expected counterpart of a pooled mean per called site, and not
    an average of per-cell means. It is None, with the reason under `undefined`, when no site
    can be called.
    """
    k = _threshold(threshold)
    means = _per_class(mean_chains_per_copy, "Mean chains per copy")
    copies = _per_class(copies_per_cell, "Copies per cell")
    if means.shape != copies.shape:
        raise ValueError("Give one mean and one copy number per copy class")
    if distribution == "poisson":
        if fano_factor is not None:
            raise ValueError("A Fano factor is declared only with the negative binomial")
        parameters = {}
        called = gammainc(k, means)
        # E[N; N >= k] = mu P(N >= k - 1) for a Poisson count N.
        visible = means * gammainc(k - 1, means) if k > 1 else means
    elif distribution == "negative_binomial":
        fano = None if fano_factor is None else _finite(fano_factor, "The Fano factor")
        if fano is None or fano <= 1:
            raise ValueError("The negative binomial needs a declared Fano factor above 1")
        parameters = dict(fano_factor=fano)
        occupied = means > 0
        shape = np.where(occupied, means / (fano - 1), 1.0)
        spread = (fano - 1) / fano
        called = np.where(occupied, betainc(k, shape, spread), 0.0)
        # E[N; N >= k] = mu P(N' >= k - 1), with N' of shape r + 1 and the same spread.
        visible = (
            means * np.where(occupied, betainc(k - 1, shape + 1, spread), 0.0) if k > 1 else means
        )
    else:
        raise ValueError(
            "Name the distribution of chains per copy, 'poisson' or 'negative_binomial', "
            f"not {distribution!r}"
        )
    return _expectation(distribution, parameters, k, copies, means, called, visible)


def called_sites_from_counts(chain_counts_per_copy, copies_per_cell, *, threshold):
    """The same expectations as `expected_called_sites`, from supplied counts per gene copy.

    `chain_counts_per_copy` holds one sequence per copy class. Each is a nonempty set of whole
    chain counts seen on single copies of that class, zeros included, from data or from draws
    of a stochastic run. Counts must be integers. Floats are refused even when whole, so that a
    simulated mean cannot pass as a count. The empirical distribution of each class replaces a
    named family. The threshold acts on each counted copy before averaging, and the
    expectations are sample means. They carry the sampling error of the draws, which this
    function does not estimate. The record gives the draws and the called draws per class.
    """
    k = _threshold(threshold)
    copies = _per_class(copies_per_cell, "Copies per cell")
    if not isinstance(chain_counts_per_copy, Iterable) or isinstance(chain_counts_per_copy, str):
        raise ValueError("Give one sequence of chain counts per copy class")
    classes = [_draws(values) for values in chain_counts_per_copy]
    if len(classes) != len(copies):
        raise ValueError("Give one sequence of chain counts and one copy number per copy class")
    draws = [len(values) for values in classes]
    called_draws = [int(np.count_nonzero(values >= k)) for values in classes]
    called = np.array([n / d for n, d in zip(called_draws, draws, strict=True)])
    visible = np.array([int(values[values >= k].sum()) / len(values) for values in classes])
    means = np.array([int(values.sum()) / len(values) for values in classes])
    parameters = dict(
        draws_per_copy_class=tuple(draws), called_draws_per_copy_class=tuple(called_draws)
    )
    return _expectation("supplied_counts", parameters, k, copies, means, called, visible)
