import copy
import json
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from HOwDI.model.create_model import build_h2_model
from HOwDI.model.create_network import build_hydrogen_network
from HOwDI.model.HydrogenData import HydrogenData
from HOwDI.postprocessing.generate_outputs import create_outputs_dfs
from HOwDI.util import create_db_engine, read_yaml


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
        if self.file == "settings":
            update_nested_dict_with_slash(files, self.row, self.value)
        else:
            files[self.file].at[self.row, self.column] = self.value


class MovingList:
    def __init__(self, l):
        self.l = l
        self.len = len(l)
        self.i = 0

    def update_index(self):
        self.i += 1

    def get(self):
        if self.i >= self.len:
            out = None
        else:
            out = self.l[self.i]
        self.update_index()
        return out


def run_model(settings, trial, uuid, trial_number):
    H = HydrogenData(read_type="DataFrame", settings=settings, dfs=trial, uuid=uuid)
    g = build_hydrogen_network(H)
    m = build_h2_model(H, g)
    H.output_dfs = create_outputs_dfs(m, H)

    metadata = {"uuid": str(uuid), "trial": trial_number}
    H.add_value_to_all_dfs(**metadata)
    return H


def nested_dict_with_slash(d: dict, dict_path: str):
    moving_list = MovingList([p for p in dict_path.split("/")])

    def recurse_through_dict(r):
        path = moving_list.get()
        if path is not None:
            return recurse_through_dict(r.get(path))
        else:
            return r

    return recurse_through_dict(d)


def update_nested_dict_with_slash(d: dict, dict_path: str, new_value):
    paths = [p for p in dict_path.split("/")]
    moving_list = MovingList(paths[0:-1])

    def recurse_through_dict(r):
        path = moving_list.get()
        if path is not None:
            return recurse_through_dict(r.get(path))
        else:
            r[paths[-1]] = new_value

    recurse_through_dict(d)


def adjust_parameters(files, file_name, row, column, parameters):
    none_keys = [k for k, v in parameters.items() if v is None]
    if none_keys != []:
        if file_name == "settings":
            default_value = nested_dict_with_slash(files, row)
        else:
            default_value = files[file_name].loc[row, column]
        parameters.update({k: default_value for k in none_keys})
    return parameters


def generate_monte_carlo_trial(files, mc_distributions, n):
    files = copy.deepcopy(files)
    [mc_distribution[n].update_file(files) for mc_distribution in mc_distributions]
    return files


def generate_monte_carlo_trial_settings(settings, distrs, n):
    settings = copy.deepcopy(settings)
    [distr[n].update_file(settings) for distr in distrs]
    return settings


def monte_carlo(base_dir=Path("."), monte_carlo_file=None):
    if monte_carlo_file == None:
        from HOwDI.arg_parse import parse_command_line

        args = parse_command_line(module="monte_carlo")
        monte_carlo_file = args.monte_carlo_file
    mc_dict = read_yaml(base_dir / (monte_carlo_file.replace(".yml", "") + ".yml"))

    run_uuid = str(uuid.uuid4())
    metadata = mc_dict.get("metadata")
    distributions = mc_dict.get("distributions")

    # instantiate metadata
    base_input_dir = base_dir / metadata.get("base_input_dir", "inputs")
    engine = create_db_engine()
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
        if file != "settings"
        for row, column_data in row_data.items()
        for column, distribution_data in column_data.items()
    ]

    # put distributions into files
    # TODO put this stuff into the function that is run in parallel to save memory?
    trials = [
        generate_monte_carlo_trial(files, mc_distributions, n)
        for n in range(number_of_trials)
    ]

    if "settings" in distributions.keys():
        settings_distr = [
            MonteCarloParameter(
                file="settings",
                row=key,
                column=None,
                distribution_data=value,
                number_of_trials=number_of_trials,
                files=settings,
            )
            for key, value in distributions["settings"].items()
        ]
        settings_trials = [
            generate_monte_carlo_trial_settings(settings, settings_distr, n)
            for n in range(number_of_trials)
        ]
    else:
        settings_trials = [settings] * number_of_trials

    # # temp
    # for trial in trials:
    #     [file.reset_index(inplace=True) for file in trial.values()]
    # # end temp

    # set up model run
    def run_trial(n, trial, settings):
        return run_model(settings=settings, trial=trial, uuid=run_uuid, trial_number=n)

    # run model
    model_instances = Parallel(
        n_jobs=metadata.get("number_of_jobs", 1), backend="loky"
    )(
        delayed(run_trial)(n, trial, settings)
        for n, trial, settings in zip(range(number_of_trials), trials, settings_trials)
    )

    # upload data to sql
    [model_instance.upload_to_sql(engine=engine) for model_instance in model_instances]

    # upload settings to sql
    settings_df = pd.DataFrame(
        [
            {
                "settings": json.dumps(settings_trial, cls=NpEncoder),
                "uuid": run_uuid,
                "trial": n,
            }
            for settings_trial, n in zip(settings_trials, range(number_of_trials))
        ]
    )
    settings_df.to_sql("input-settings", con=engine, if_exists="append")

    # upload metadata
    metadata_df = pd.DataFrame(
        {"uuid": [run_uuid], "metadata": [json.dumps(mc_dict, cls=NpEncoder)]}
    )
    metadata_df.to_sql("metadata", con=engine, if_exists="append")

    print(run_uuid)


def main():
    monte_carlo(Path("../scenarios/base"), "monte_carlo")


if __name__ == "__main__":
    main()
