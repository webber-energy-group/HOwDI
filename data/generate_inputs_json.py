"""
Converts inputs csvs into a single JSON
Author: Braden Pecora
"""

import json
import os

import numpy as np
import pandas as pd


def main(inputs_path, filename="inputs.json"):
    # file_names = [file.replace('.csv','') for file in os.listdir('./{}'.format(inputs_dir)) if file.endswith('.csv')]
    files = list(inputs_path.glob("*.csv"))

    def to_list(file):
        df = pd.read_csv(file)

        for column_name in df.columns:
            if df[column_name].dtypes == np.int64:
                # replace all 'int64' types with floats
                if not df[column_name].isin([0, 1]).all():
                    # check if column is booleans
                    df[column_name] = pd.to_numeric(df[column_name], downcast="float")

        data_dict = json.loads(df.to_json(orient="index"))
        data_list = [value for key, value in data_dict.items()]
        return data_list

    output = {
        os.path.basename(file).replace(".csv", ""): to_list(file) for file in files
    }

    output_file = inputs_path / filename

    with output_file.open("w") as f:
        json.dump(output, f)

    return output


if __name__ == "__main__":
    main(inputs_dir="inputs/")
