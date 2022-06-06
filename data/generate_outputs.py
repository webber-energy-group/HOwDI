"""
Converts outputs of Hydrogen model into dataframes and a dictionary
Author: Braden Pecora
"""

from numpy import int64, isclose
import pandas as pd
from idaes.core.util import to_json
from functools import reduce
pd.options.mode.chained_assignment = None

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
    df = df.fillna("n/a")
    return df

def tuple_split(df, index, name1, name2):
    """Assuming df[index] is a tuple, splits df[index] into df[name1] df[name2]"""
    # unpack tuples from string, delete old index
    df[index] = df[index].apply(eval)
    df.index = pd.MultiIndex.from_tuples(df[index], names=[name1, name2])
    del df[index]

    return df

def create_nodal_data(df, node,start = -1):
    index_column = df.index.name
    df = df.reset_index()
    # find values in index column that match the node name
    df = df[df[index_column].str.contains(node + '_')]
    # split values in index column into a list based on the character "_"
    # takes the indexes from variable {start} in the list and merge back into a single string
    df[index_column] = df[index_column].str.split('_').str[start:].apply(lambda x: '_'.join(map(str,x)))
    df = df.set_index(index_column)

    return df.to_dict('index')

def create_nodal_distribution_data(df, node):
    # this is largely an abstraction tool to make main less messy
    df = df.reset_index()
    
    node_string = node + '_' # 
    arc_start = df['arc_start'].str.contains(node_string)
    arc_end = df['arc_end'].str.contains(node_string)

    local = df[arc_start & arc_end]
    outgoing = df[arc_start & (arc_end==0)]
    incoming = df[arc_end & (arc_start==0)] # ?not sure this one is necessary

    local['arc_start'] = local['arc_start'].str.replace(node_string,'')
    local['arc_end'] = local['arc_end'].str.replace(node_string,'')
    local.index = local['arc_start'] + '_TO_' + local['arc_end']
    local = local.rename(columns = {'arc_start':'source_class','arc_end':'destination_class'})

    def out_in_add_info(df):
        # I'm not sure how python's "pass by object reference" works in for loops so I opted for a function to avoid repeating code
        df['source'] = df['arc_start'].str.split('_').str[0]
        df['arc_start'] = df['arc_start'].str.replace(node_string,'')
        df.index = df['arc_start'] + '_TO_' + df['arc_end']
        df['destination'] = df['arc_end'].str.split('_').str[0]
        df['destination_class'] = df['arc_end'].str.split('_').str[1:].apply(lambda x: '_'.join(map(str,x)))
        df = df.rename(columns = {'arc_start':'source_class'})
        df = df[df['dist_h'] > 0]
        return df
    outgoing = out_in_add_info(outgoing)
    incoming = out_in_add_info(incoming)

    return {'local' : local.to_dict('index'), 'outgoing': outgoing.to_dict('index'), 'incoming': incoming.to_dict('index')}

def main(m, nodes_list, parameters):
    outputs = to_json(m, return_dict=True)
    outputs = outputs['unknown']['data']['None']['__pyomo_components__']
    outputs = recursive_clean(outputs)

    ## CREATE DATAFRAME OUTPUTS
    # create relevant dataframes from json output
    black_list = ['OBJ']
    all_dfs = {key : create_df(key, value) for key, value in outputs.items() if not("constr_" in key) and not(key in black_list)}

    # join relevant dataframes
    merge_lists = {}
    merge_lists['production'] = ['can_ccs1','can_ccs2','ccs1_capacity_co2','ccs1_capacity_h2','ccs1_checs',
                                    'ccs2_capacity_co2','ccs2_capacity_h2','ccs2_checs','co2_emitted',
                                    'prod_capacity','prod_carbonRate','prod_cost_capital_coeff','prod_cost_fixed','prod_cost_variable',
                                    'prod_h','prod_checs','prod_kwh_variable_coeff','prod_ng_variable_coeff','prod_utilization']
    merge_lists['conversion'] = ['conv_capacity','conv_cost_capital_coeff','conv_cost_fixed','conv_cost_variable',
                                    'conv_kwh_variable_coeff','conv_utilization','fuelStation_cost_capital_subsidy']
    merge_lists['consumption'] = ['co2_nonHydrogenConsumer','cons_breakevenCarbon','cons_carbonSensitive','cons_h',
                                'cons_checs','cons_price','cons_size']
    merge_lists['distribution'] = ['dist_capacity','dist_cost_capital','dist_cost_fixed','dist_cost_variable','dist_flowLimit','dist_h']
    dfs = {name : join_multiple_dfs(df_whitelist, all_dfs) for name, df_whitelist in merge_lists.items()}

    # split tuple string in distribution index
    # ! if my guess on arc_start and arc_end was incorrect, swap arc_start and arc_end in the function arguments
    dfs['distribution'] = tuple_split(dfs['distribution'], 'index', 'arc_start','arc_end')

    # rename 'index' column
    index_rename = {'consumption':'consumer','conversion':'convertor','production':'producer'}
    for file_name, new_index in index_rename.items():
        dfs[file_name] = dfs[file_name].rename(columns={'index':new_index})
        dfs[file_name][new_index] = dfs[file_name][new_index].str.replace('\'','')
        dfs[file_name] = dfs[file_name].set_index(new_index)
    
    # find price for price nodes
    if parameters['find_prices']:
        if parameters['price_hubs'] == 'all':
            price_hubs = nodes_list
        else:
            price_hubs = parameters['price_hubs']

        price_demand = parameters['price_demand']

        price_hub_min = pd.DataFrame(columns=dfs['consumption'].columns) # empty df that will contain smallest price hub utilized
        price_hub_min.index.name = 'consumer'
        
        for demand_type in ['priceFuelStation','priceLowPurity','priceHighPurity']:
            # get all price hubs of specific demand type
            price_hubs_df_all = dfs['consumption'][(dfs['consumption'].index.str.contains(demand_type)) & (isclose(dfs['consumption']['cons_h'],price_demand))]

            for price_hub in price_hubs:
                # get price hub matching 'price_hub', which are nodal hubs that have price_hubs
                local_price_hub_df = price_hubs_df_all[price_hubs_df_all.index.str.contains(price_hub)]
                if not local_price_hub_df.empty:
                    # find minimum valued price hub that still buys hydrogen
                    breakeven_price_at_hub = local_price_hub_df[local_price_hub_df['cons_price'] == local_price_hub_df['cons_price'].min()]
                    price_hub_min = pd.concat([price_hub_min, breakeven_price_at_hub])
    # remove null data

    # find_prices is a binary, price_demand is the demand amount used with price nodes, thus,
    # if price nodes are used (find_prices binary), then data utilizing an amount of hydrogen <= price_demand will be removed
    price_hub_demand = parameters['find_prices']*parameters['price_demand'] 

    tol = 1e-6

    dfs['production'] = dfs['production'][dfs['production']['prod_capacity']>tol]
    dfs['consumption'] = dfs['consumption'][(dfs['consumption']['cons_h']>tol) & (~isclose(dfs['consumption']['cons_h'],price_hub_demand))]
    dfs['conversion'] = dfs['conversion'][dfs['conversion']['conv_capacity']>tol]

    dfs['distribution'] = dfs['distribution'].replace(['n/a'],-99.99) # change na to -99.99 for conditional
    dfs['distribution'] = dfs['distribution'][(dfs['distribution']['dist_capacity']>tol) | (( dfs['distribution']['dist_h']>tol)&(~isclose(dfs['distribution']['dist_h'],price_hub_demand)))]
    dfs['distribution'] = dfs['distribution'].replace([-99.99],'n/a') # and change back

    # re add price hub data
    if parameters['find_prices']:
        dfs['consumption'] = pd.concat([dfs['consumption'],price_hub_min])

    # post processing
    dfs['production']['total_co2_produced'] = dfs['production']['prod_h']*dfs['production']['prod_carbonRate']
    dfs['production']['co2_captured'] = dfs['production']['total_co2_produced']-dfs['production']['co2_emitted']
    dfs['production'][r'%co2_captured'] = dfs['production']['co2_captured']/dfs['production']['total_co2_produced']

    ## CREATE JSON OUTPUTS FROM DATAFRAMES
    node_dict = {node: {} for node in nodes_list}
    for node in nodes_list:
        node_dict[node]['production'] = create_nodal_data(dfs['production'], node)
        node_dict[node]['conversion'] = create_nodal_data(dfs['conversion'], node)
        node_dict[node]['consumption'] = create_nodal_data(dfs['consumption'], node,1)
        node_dict[node]['distribution'] = create_nodal_distribution_data(dfs['distribution'], node)


    ## Post Processing print
    print("Summary Results:")
    
    total_h_consumed = dfs['consumption']['cons_h'].sum()
    total_h_produced = dfs['production']['prod_h'].sum()
    print("Hydrogen Consumed (Tonnes/day): {}".format(total_h_consumed))
    print("Hydrogen Produced (Tonnes/day): {}".format(total_h_produced))



    return dfs, node_dict