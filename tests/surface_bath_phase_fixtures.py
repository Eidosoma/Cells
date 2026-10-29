"""Public bath epochs with short accepted restart boundaries in the full schedule."""

from functools import lru_cache

from cells.tissue_phase import prepare_request
from tests.surface_bath_events_fixtures import PREFIX_DT
from validation.topology import surface_bath_phase_fixtures as component

OWNERS = {family: row[1:] for family, row in component.OWNERS.items()}
source_checkpoint = component.source_checkpoint


def request(family):
    raw = component.request(family)
    experiment = raw["simulation"]["experiment"]
    schedule = experiment["membrane_controls"][0]["schedule"]
    value = schedule[0]["availability"]
    schedule.extend(dict(time=t, availability=value) for t in (PREFIX_DT, 2 * PREFIX_DT))
    schedule.sort(key=lambda row: row["time"])
    experiment["observation_times"] = sorted(
        {*experiment["observation_times"], PREFIX_DT, 2 * PREFIX_DT}
    )
    return raw


@lru_cache
def prepared(family):
    return prepare_request(request(family))
