# TODO monte carlo on settings as well

import copy
import json
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from joblib import Parallel, delayed
from sqlalchemy import create_engine

from HOwDI.model.create_model import build_h2_model
from HOwDI.model.create_network import build_hydrogen_network
from HOwDI.model.HydrogenData import HydrogenData
from HOwDI.postprocessing.generate_outputs import create_outputs_dfs


class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)


class MonteCarloParameter:
    def __init__(
        self,
        file: str,
        column: str,
        row: str,
        distribution_data,
        number_of_trials,
        files,
    ):
        self.file = file
        self.column = column
        self.row = row
        self.distribution = getattr(np.random, distribution_data["distribution"])(
            size=number_of_trials,
            **adjust_parameters(
                files, file, row, column, distribution_data["parameters"]
            )
        )

    def __getitem__(self, n):
        return MonteCarloTrial(self, n)


class MonteCarloTrial:
    def __init__(self, mcp: MonteCarloParameter, n: int):
        self.file = mcp.file
        self.column = mcp.column
        self.row = mcp.row
        self.value = mcp.distribution[n]

    def update_file(self, files):
        """updates file with Monte Carlo'd value"""
        files[self.file].at[self.row, self.column] = self.value


def run_model(settings, trial, uuid, trial_number):
    H = HydrogenData(read_type="DataFrame", settings=settings, dfs=trial, uuid=uuid)
    g = build_hydrogen_network(H)
    m = build_h2_model(H, g)
    H.output_dfs = create_outputs_dfs(m, H)

    metadata = {"uuid": str(uuid), "trial": trial_number}
    H.add_value_to_all_dfs(**metadata)
    return H


def read_yaml(fn):
    with open(fn) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def adjust_parameters(files, file_name, row, column, parameters):
    none_keys = [k for k, v in parameters.items() if v is None]
    if none_keys != []:
        default_value = files[file_name].loc[row, column]
        parameters.update({k: default_value for k in none_keys})
    return parameters


def generate_monte_carlo_trial(files, mc_distributions, n):
    files = copy.deepcopy(files)
    [mc_distribution[n].update_file(files) for mc_distribution in mc_distributions]
    return files


def monte_carlo():
    # temp
    base_dir = Path("../scenarios/base")
    mc_dict = read_yaml(base_dir / "monte_carlo.yml")
    # end temp

    run_uuid = str(uuid.uuid4())
    metadata = mc_dict.get("metadata")
    distributions = mc_dict.get("distributions")

    # instantiate metadata
    base_input_dir = base_dir / metadata.get("base_input_dir", "inputs")
    engine = create_engine(metadata.get("sql_engine"))
    number_of_trials = metadata.get("number_of_trials", 1)

    # read base data
    files = {
        file.stem: pd.read_csv(file, index_col=0)
        for file in base_input_dir.glob("*.csv")
    }
    settings = read_yaml(base_input_dir / "settings.yml")

    # generate distributions
    mc_distributions = [
        MonteCarloParameter(
            file=file,
            column=column,
            row=row,
            distribution_data=distribution_data,
            number_of_trials=number_of_trials,
            files=files,
        )
        for file, row_data in distributions.items()
        for row, column_data in row_data.items()
        for column, distribution_data in column_data.items()
    ]

    # put distributions into files
    trials = [
        generate_monte_carlo_trial(files, mc_distributions, n)
        for n in range(number_of_trials)
    ]

    # temp
    for trial in trials:
        [file.reset_index(inplace=True) for file in trial.values()]
    # end temp

    # set up model run
    def run_trial(n, trial):
        return run_model(settings=settings, trial=trial, uuid=run_uuid, trial_number=n)

    # run model
    model_instances = Parallel(
        n_jobs=metadata.get("number_of_jobs", 1), backend="loky"
    )(delayed(run_trial)(n, trial) for n, trial in zip(range(number_of_trials), trials))

    # upload data to sql
    [model_instance.upload_to_sql(engine=engine) for model_instance in model_instances]

    # upload metadata
    metadata_df = pd.DataFrame(
        {"uuid": [run_uuid], "metadata": [json.dumps(mc_dict, cls=NpEncoder)]}
    )
    metadata_df.to_sql("metadata", con=engine, if_exists="append")


def main():
    monte_carlo()


if __name__ == "__main__":
    main()
