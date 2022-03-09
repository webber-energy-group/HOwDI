from json import dump
from numpy import int64
import pandas as pd
from idaes.core.util import to_json
from functools import reduce

def recursive_clean(nested_dict):
    """ Removes unnecessary data from Pyomo model serialized as a JSON dict """
    black_list = ['__type__', '__id__', '_mutable', 'fixed','stale','lb','ub']
    for key in list(nested_dict): 
        if key in black_list:
            del nested_dict[key]
        elif type(nested_dict[key]) is int64:
            nested_dict[key] = int(nested_dict[key])
        elif type(nested_dict[key]) is dict:
            if key == 'data':
                nested_dict = recursive_clean(nested_dict[key])
            else:
                nested_dict[key] = recursive_clean(nested_dict[key])

    return nested_dict

def create_df(label, data):
    """ Creates dataframe from dictionary {data}, changing name of 'value' column to {label} """
    df = pd.DataFrame.from_dict(data, orient='index')
    df = df.rename(columns={'value': label})
    return df

def join_multiple_dfs(dfs_labels, dfs_values):
    """ From a dictionary of dataframes ({label: data_frame}) {dfs_values}, 
    merges all dataframes with label in {dfs_labels} """
    dfs = [dfs_values[label] for label in dfs_labels]
    df = reduce(lambda left, right: pd.merge(left, right, how='outer', left_index=True, right_index=True), dfs)
    df.reset_index(inplace=True)
    return df

def tuple_split(df, index, name1, name2):
    """Assuming df[index] is a tuple, splits df[index] into df[name1] df[name2]"""
    # rearrange column ordering
    columns = df.columns.tolist()
    columns.remove(index)
    columns = [name1, name2] + columns

    # unpack tuples from string, delete old index
    df[index] = df[index].apply(eval)
    df[name1], df[name2] = zip(*df[index])
    del df[index]

    # assign column ordering
    df = df[columns]

    return df

def main(m, option='json'):
    outputs = to_json(m, return_dict=True)
    outputs = outputs['unknown']['data']['None']['__pyomo_components__']
    outputs = recursive_clean(outputs)

    # create relevant dataframes from json output
    black_list = ['OBJ', 'arc_class']
    all_dfs = {key : create_df(key, value) for key, value in outputs.items() if not("constr_" in key) and not(key in black_list)}

    # join relevant dataframes
    merge_lists = {}
    merge_lists['production'] = ['can_ccs1','can_ccs2','ccs1_capacity_co2','ccs1_capacity_h2','ccs1_hblack',
                                    'ccs2_capacity_co2','ccs2_capacity_h2','ccs2_hblack','co2_producer',
                                    'prod_capacity','prod_carbonRate','prod_cost_capital_coeff','prod_cost_fixed','prod_cost_variable',
                                    'prod_h','prod_hblack','prod_kwh_variable_coeff','prod_ng_variable_coeff','prod_utilization']
    merge_lists['conversion'] = ['conv_capacity','conv_cost_capital_coeff','conv_cost_fixed','conv_cost_variable',
                                    'conv_kwh_variable_coeff','conv_utilization','fuelStation_cost_capital_subsidy']
    merge_lists['consumption'] = ['co2_nonHydrogenConsumer','cons_breakevenCarbon','cons_carbonSensitive','cons_h',
                                'cons_hblack','cons_price','cons_size']
    merge_lists['distribution'] = ['dist_capacity','dist_cost_capital','dist_cost_fixed','dist_cost_variable','dist_flowLimit','dist_h']
    merged_dfs = {name : join_multiple_dfs(df_whitelist, all_dfs) for name, df_whitelist in merge_lists.items()}

    # split tuple string in distribution index
    merged_dfs['distribution'] = tuple_split(merged_dfs['distribution'], 'index', 'source','destination')

    # rename 'index' column
    index_rename = {'consumption':'consumer','conversion':'convertor','production':'producer'}
    for file_name, new_index in index_rename.items():
        merged_dfs[file_name] = merged_dfs[file_name].rename(columns={'index':new_index})

    # if option == 'json':
    #     with open('outputs/outputs.json', 'w', encoding='utf-8') as f:
    #         dump(outputs, f, ensure_ascii=False, indent=4)

    if option == 'csv':
        [df.to_csv('outputs/' + key + '.csv') for key, df in merged_dfs.items()]
        