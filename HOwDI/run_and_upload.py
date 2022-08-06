import pandas as pd
import yaml
from sqlalchemy import create_engine

from HOwDI.model.create_model import build_h2_model
from HOwDI.model.create_network import build_hydrogen_network
from HOwDI.model.HydrogenData import HydrogenData
from HOwDI.postprocessing.generate_outputs import create_outputs_dfs


def run_and_upload(engine, settings, dfs):
    H = HydrogenData(read_type="DataFrame", settings=settings, dfs=dfs)
    g = build_hydrogen_network(H)
    m = build_h2_model(H, g)
    H.output_dfs = create_outputs_dfs(m, H)

    uuid = H.upload_to_sql(engine=engine)

    return uuid


def main():
    engine = create_engine("sqlite:///C:/Users/bpeco/Box/h2@scale/h2_model/test.sqlite")

    with open("../scenarios/base/inputs/settings.yml") as f:
        settings = yaml.load(f, Loader=yaml.FullLoader)

    fns = [
        "production_thermal",
        "production_electric",
        "storage",
        "distribution",
        "conversion",
        "demand",
        "hubs",
        "arcs",
        "production_existing",
        "ccs",
    ]
    dfs = {fn: pd.read_csv("../scenarios/base/inputs/" + fn + ".csv") for fn in fns}

    uuid = run_and_upload(engine, settings, dfs)
    print(uuid)


if __name__ == "__main__":
    main()
