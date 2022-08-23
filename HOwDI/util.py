import json
from pathlib import Path

import yaml
from sqlalchemy import create_engine


def read_yaml(fn):
    with open(fn) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def create_db_engine():
    p = Path(__file__) / ".."
    config = read_yaml(p / "config.yml")
    db = config.get("db")
    engine = create_engine(db)
    return engine


def get_metadata(uuid, engine=None):
    if engine is None:
        engine = create_db_engine()

    with engine.connect() as con:
        metadata = con.execute(
            f"""SELECT metadata FROM metadata WHERE uuid = '{uuid}'"""
        )
        metadata = [r for r in metadata][0][0]

    metadata = json.loads(metadata)
    return metadata


def get_number_of_trials(uuid, engine=None):
    metadata = get_metadata(uuid=uuid, engine=engine)
    return metadata["metadata"]["number_of_trials"]


def _continue_flattening(dd):
    """Filter than returns true if
    item is dictionary but dictionary does not have keys
    "distribution" or "parameters".
    """
    if isinstance(dd, dict):
        ks = dd.keys()
        if "distriubiton" in ks or "parameters" in ks:
            return False
        else:
            return True
    else:
        return False


def flatten_dict(
    dd, flattener=lambda ddd: isinstance(ddd, dict), separator="/", prefix=""
):
    """
    adapted from
    https://www.geeksforgeeks.org/python-convert-nested-dictionary-into-flattened-dictionary/

    Flattens dict based on `_continue_flattening`, which stop flattening
    the dict if the next value is a) not a dict or b) has the keys
    "distribution" and/or "parameters".
    """
    return (
        {
            prefix + separator + k if prefix else k: v
            for kk, vv in dd.items()
            for k, v in flatten_dict(vv, flattener, separator, kk).items()
        }
        if flattener(dd)
        else {prefix: dd}
    )


def truncate_dict(d, filter=_continue_flattening):
    """Truncates a dictionary based on a filter
    At the spot of truncation, the value becomes the keys"""

    def truncate_dict_inner(dd):
        """Filtered sets become null dictionaries"""
        return {
            key1: truncate_dict_inner(val1) if isinstance(val1, dict) else val1
            for key1, val1 in dd.items()
            if filter(dd)
        }

    d1 = truncate_dict_inner(d)

    def remove_null(dd):
        """Turns location of null dictionaries into list of keys"""
        if isinstance(dd, dict):
            if any([v == {} for v in dd.values()]):
                return dict_keys_to_list(dd)
            else:
                return {k: remove_null(v) for k, v in dd.items()}

    d2 = remove_null(d1)
    return d2


def get_flat_monte_carlo_options_dict(uuid, engine=None):
    """flattens dict:
    keys are key/key/key/key
    values are the remaining values based on filter (distribution/parameters dicts)
    """
    metadata = get_metadata(uuid=uuid, engine=engine)
    distributions = metadata["distributions"]
    distributions_keys = flatten_dict(dd=distributions, flattener=_continue_flattening)
    return distributions_keys


def get_truncated_monte_carlo_options_dict(uuid, engine=None):
    """truncates dict:
    keys are key/key/key/key
    values are a list of the remaining keys based on the filter
    (removes distribution/parameter dicts)"""
    metadata = get_metadata(uuid=uuid, engine=engine)
    distributions = metadata["distributions"]
    return truncate_dict(distributions)


def dict_keys_to_list(d):
    return list(d.keys())


def monte_carlo_keys(uuid, engine=None):
    d = get_flat_monte_carlo_options_dict(uuid, engine)
    return dict_keys_to_list(d)
