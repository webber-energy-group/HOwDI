import json
import uuid
from pathlib import Path
import copy

import numpy as np
import pandas as pd
import yaml
from sqlalchemy import create_engine

from HOwDI.run_and_upload import run_and_upload


def read_yaml(fn):
    with open(fn) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


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

    for n in range(number_of_trials):

        files_instance = copy.deepcopy(files)
        for file, row_data in distributions.items():
            for row, column_data in row_data.items():
                for column, distribution_data in column_data.items():
                    # use unpacking to make more efficient
                    files_instance[file].loc[row, column] = np.random.normal(
                        files[file].loc[row, column],
                        distribution_data["parameters"]["scale"],
                        1,
                    )

        [file.reset_index(inplace=True) for file in files_instance.values()]

        run_and_upload(
            engine=engine,
            settings=settings,
            dfs=files_instance,
            uuid=run_uuid,
            trial_number=n,
        )

    metadata_df = pd.DataFrame({"uuid": [run_uuid], "metadata": [json.dumps(mc_dict)]})
    metadata_df.to_sql("metadata", con=engine, if_exists="append")


def main():
    monte_carlo()


if __name__ == "__main__":
    main()
