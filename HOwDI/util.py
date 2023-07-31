import copy
import json
from pathlib import Path
from importlib_metadata import distributions

import pandas as pd
import yaml
from pydantic.v1.utils import deep_update
from sqlalchemy import create_engine


def read_yaml(fn):
    with open(fn) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def read_config() -> dict:
    p = Path(__file__).parents[0]
    yaml_out = read_yaml(p / "config.yml")

    config_local_path = p / "config_local.yml"
    if config_local_path.exists():
        yaml_out.update(read_yaml(config_local_path))

    return yaml_out


def create_db_engine(db=None):
    config = read_config()
    if db is None:
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


def nested_get(d, keys):
    """Returns value of nested dictionary based on keys"""
    if len(keys) == 1:
        return d[keys[0]]
    else:
        return nested_get(d[keys[0]], keys[1:])


def _recurse_find_params(d, update_function):
    for k, v in d.items():
        if all([not isinstance(v1, dict) for _, v1 in v.items()]):
            d[k] = update_function(v)
        else:
            _recurse_find_params(d[k], update_function)


def get_monte_carlo_distributions(uuid, engine=None):
    metadata = get_metadata(uuid=uuid, engine=engine)
    distributions = metadata.get("distributions", {})

    linked_distributions = metadata.get("linked_distributions")
    if linked_distributions is not None:
        for ld in linked_distributions:
            update_function = lambda v: {
                "distribution": ld["distribution"],
                "parameters": v,
            }
            _recurse_find_params(ld["values"], update_function)
            distributions = deep_update(distributions, ld["values"])
            # distributions_keys.update(
            #     flatten_dict(dd=ld["values"], flattener=_continue_flattening)
            # )
    return distributions


def get_flat_monte_carlo_options_dict(uuid, engine=None):
    """flattens dict:
    keys are key/key/key/key
    values are the remaining values based on filter (distribution/parameters dicts)
    """
    distributions = get_monte_carlo_distributions(uuid=uuid, engine=engine)
    distributions_keys = flatten_dict(dd=distributions, flattener=_continue_flattening)

    return distributions_keys


def get_truncated_monte_carlo_options_dict(uuid, engine=None):
    """truncates dict:
    keys are key/key/key/key
    values are a list of the remaining keys based on the filter
    (removes distribution/parameter dicts)"""

    distributions = get_monte_carlo_distributions(uuid=uuid, engine=engine)
    return truncate_dict(distributions)


def dict_keys_to_list(d):
    return list(d.keys())


def monte_carlo_keys(uuid, engine=None):
    d = get_flat_monte_carlo_options_dict(uuid, engine)
    return dict_keys_to_list(d)


def set_index(df, index_name):
    df = copy.deepcopy(df)
    if df is None:
        return None
    try:
        if not isinstance(df.index, pd.RangeIndex):
            df[df.index.name] = df.index
        df = df.set_index(index_name)
    except KeyError:
        assert df.index.name == index_name

    return df


def normalize_df(df):
    return df / df.abs().max()


def scale_by_distance_from_mean(df):
    return normalize_df(df - df.mean())
