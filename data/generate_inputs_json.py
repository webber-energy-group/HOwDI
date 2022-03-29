"""
Converts inputs csvs into a single JSON
Author: Braden Pecora
"""

import json, os, pandas as pd, numpy as np

def main(inputs_dir,filename='data'):
    file_names = [file.replace('.csv','') for file in os.listdir('./{}'.format(inputs_dir)) if file.endswith('.csv')]

    def to_list(file_name):
        df = pd.read_csv('./{}'.format(inputs_dir) + file_name + '.csv')

        for column_name in df.columns:
            if df[column_name].dtypes == np.int64: # replace all 'int64' types with floats
                if not df[column_name].isin([0,1]).all(): # check if column is booleans
                    df[column_name] = pd.to_numeric(df[column_name], downcast='float')

        data_dict = json.loads(df.to_json(orient='index'))
        data_list = [value for key, value in data_dict.items()]
        return data_list

    output = {file_name: to_list(file_name) for file_name in file_names}

    with open('{}/{}'.format(inputs_dir,filename), 'w') as f:
        json.dump(output, f)

    return output #aka inputs files

if __name__ == '__main__':
    main(inputs_dir='inputs/')