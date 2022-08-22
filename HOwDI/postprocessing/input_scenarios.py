import pandas as pd
from dash import Dash

from HOwDI.util import create_db_engine
from HOwDI.model.HydrogenData import init_multiple


def input_scenarios():

    app = Dash(__name__)
    # set up input options

    engine = create_db_engine()

    # get possible uuids here
    uuid = "ae83c384-8da6-41e6-99a7-13732a7f520d"

    hs = init_multiple(uuid, engine)
    prices = [h.get_prices_dict() for h in hs]

    pass
    # TODO set up selecting input parameters to show on graph


def main():
    input_scenarios()


if __name__ == "__main__":
    main()
