import pandas as pd
from dash import Dash

from HOwDI.util import (
    create_db_engine,
    get_truncated_monte_carlo_options_dict,
    monte_carlo_keys,
)
from HOwDI.model.HydrogenData import init_multiple


def input_scenarios():

    app = Dash(__name__)
    # set up input options

    engine = create_db_engine()

    # get possible uuids here
    uuid = "9f03eed3-bc14-4f19-8328-846c0d096e96"

    # keys for selecting options
    keys = monte_carlo_keys(uuid, engine)

    # dict structure for matching
    monte_carlo_data_filter = get_truncated_monte_carlo_options_dict(uuid, engine)

    hs = init_multiple(uuid, engine, monte_carlo_data_filter)
    prices = [h.get_prices_dict() for h in hs]

    pass

    # TODO get function that filters outputs to show
    #      price not satisfied
    #      - maybe get h to be stored in H object


def main():
    input_scenarios()


if __name__ == "__main__":
    main()
