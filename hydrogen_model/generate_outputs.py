"""
Converts outputs of Hydrogen model into dataframes and a dictionary
Author: Braden Pecora
"""

from numpy import int64, isclose, where
import pandas as pd
from idaes.core.util import to_json
from functools import reduce

pd.options.mode.chained_assignment = None


def recursive_clean(nested_dict):
    """Removes unnecessary data from Pyomo model serialized as a JSON dict"""
    black_list = ["__type__", "__id__", "_mutable", "fixed", "stale", "lb", "ub"]
    for key in list(nested_dict):
        if key in black_list:
            del nested_dict[key]
        elif type(nested_dict[key]) is int64:
            nested_dict[key] = int(nested_dict[key])
        elif type(nested_dict[key]) is dict:
            if key == "data":
                nested_dict = recursive_clean(nested_dict[key])
            else:
                nested_dict[key] = recursive_clean(nested_dict[key])

    return nested_dict


def create_df(label, data):
    """Creates dataframe from dictionary {data}, changing name of 'value' column to {label}"""
    df = pd.DataFrame.from_dict(data, orient="index")
    df = df.rename(columns={"value": label})
    return df


def join_multiple_dfs(dfs_labels, dfs_values):
    """From a dictionary of dataframes ({label: data_frame}) {dfs_values},
    merges all dataframes with label in {dfs_labels}"""
    dfs = [dfs_values[label] for label in dfs_labels]
    df = reduce(
        lambda left, right: pd.merge(
            left, right, how="outer", left_index=True, right_index=True
        ),
        dfs,
    )
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


def create_hub_data(df, hub, start=-1):
    index_column = df.index.name
    df = df.reset_index()
    # find values in index column that match the hub name
    df = df[df[index_column].str.contains(hub + "_")]
    # split values in index column into a list based on the character "_"
    # takes the indexes from variable {start} in the list and merge back into a single string
    df[index_column] = (
        df[index_column]
        .str.split("_")
        .str[start:]
        .apply(lambda x: "_".join(map(str, x)))
    )
    df = df.set_index(index_column)

    return df.to_dict("index")


def create_hub_distribution_data(df, hub):
    # this is largely an abstraction tool to make main less messy
    df = df.reset_index()

    hub_string = hub + "_"  #
    arc_start = df["arc_start"].str.contains(hub_string)
    arc_end = df["arc_end"].str.contains(hub_string)

    local = df[arc_start & arc_end]
    outgoing = df[arc_start & (arc_end == 0)]
    incoming = df[arc_end & (arc_start == 0)]  # ?not sure this one is necessary

    local["arc_start"] = local["arc_start"].str.replace(hub_string, "")
    local["arc_end"] = local["arc_end"].str.replace(hub_string, "")
    local.index = local["arc_start"] + "_TO_" + local["arc_end"]
    local = local.rename(
        columns={"arc_start": "source_class", "arc_end": "destination_class"}
    )

    def out_in_add_info(df):
        # I'm not sure how python's "pass by object reference" works in for loops so I opted for a function to avoid repeating code
        df["source"] = df["arc_start"].str.split("_").str[0]
        df["arc_start"] = df["arc_start"].str.replace(hub_string, "")
        df.index = df["arc_start"] + "_TO_" + df["arc_end"]
        df["destination"] = df["arc_end"].str.split("_").str[0]
        df["destination_class"] = (
            df["arc_end"].str.split("_").str[1:].apply(lambda x: "_".join(map(str, x)))
        )
        df = df.rename(columns={"arc_start": "source_class"})
        df = df[df["dist_h"] > 0]
        return df

    outgoing = out_in_add_info(outgoing)
    incoming = out_in_add_info(incoming)

    return {
        "local": local.to_dict("index"),
        "outgoing": outgoing.to_dict("index"),
        "incoming": incoming.to_dict("index"),
    }


def generate_outputs(m, H):
    hubs_list = H.get_hubs_list()

    outputs = to_json(m, return_dict=True)
    outputs = outputs["unknown"]["data"]["None"]["__pyomo_components__"]
    outputs = recursive_clean(outputs)

    ## CREATE DATAFRAME OUTPUTS
    # create relevant dataframes from json output
    black_list = ["OBJ"]
    all_dfs = {
        key: create_df(key, value)
        for key, value in outputs.items()
        if not ("constr_" in key) and not (key in black_list)
    }

    # join relevant dataframes
    merge_lists = {}
    merge_lists["production"] = [
        "can_ccs1",
        "can_ccs2",
        "ccs1_built",
        "ccs2_built",
        "ccs1_capacity_h2",
        "ccs1_checs",
        "ccs2_capacity_h2",
        "ccs2_checs",
        "prod_capacity",
        "prod_utilization",
        "prod_h",
        "prod_cost_capital",
        "prod_cost_fixed",
        "prod_cost_variable",
        "prod_e_price",
        "prod_ng_price",
        "h2_tax_credit",
        "co2_emissions_rate",
        "ccs_capture_rate",
        "chec_per_ton",
        "prod_checs",
    ]
    merge_lists["conversion"] = [
        "conv_capacity",
        "conv_cost_capital",
        "conv_cost_fixed",
        "conv_cost_variable",
        "conv_e_price",
        "conv_utilization",
        "fuelStation_cost_capital_subsidy",
    ]
    merge_lists["consumption"] = [
        "cons_size",
        "cons_h",
        "carbon_sensitive_fraction",
        "cons_checs",
        "cons_price",
    ]
    merge_lists["distribution"] = [
        "dist_capacity",
        "dist_cost_capital",
        "dist_cost_fixed",
        "dist_cost_variable",
        "dist_flowLimit",
        "dist_h",
    ]
    dfs = {
        name: join_multiple_dfs(df_whitelist, all_dfs)
        for name, df_whitelist in merge_lists.items()
    }

    # split tuple string in distribution index
    # ! if my guess on arc_start and arc_end was incorrect, swap arc_start and arc_end in the function arguments
    dfs["distribution"] = tuple_split(
        dfs["distribution"], "index", "arc_start", "arc_end"
    )

    # rename 'index' column
    index_rename = {
        "consumption": "consumer",
        "conversion": "convertor",
        "production": "producer",
    }
    for file_name, new_index in index_rename.items():
        dfs[file_name] = dfs[file_name].rename(columns={"index": new_index})
        dfs[file_name][new_index] = dfs[file_name][new_index].str.replace("'", "")
        dfs[file_name] = dfs[file_name].set_index(new_index)

    # find price for price hubs
    if H.find_prices:
        if H.price_hubs == "all":
            price_hubs = hubs_list
        else:
            price_hubs = H.price_hubs

        price_demand = H.price_demand

        price_hub_min = pd.DataFrame(
            columns=dfs["consumption"].columns
        )  # empty df that will contain smallest price hub utilized
        price_hub_min.index.name = "consumer"

        for demand_type in ["priceFuelStation", "priceLowPurity", "priceHighPurity"]:
            # get all price hubs of specific demand type
            price_hubs_df_all = dfs["consumption"][
                (dfs["consumption"].index.str.contains(demand_type))
                & (isclose(dfs["consumption"]["cons_h"], price_demand))
            ]

            for price_hub in price_hubs:
                # get price hub matching 'price_hub', which are hubs that have price_hubs
                local_price_hub_df = price_hubs_df_all[
                    price_hubs_df_all.index.str.contains(price_hub)
                ]
                if not local_price_hub_df.empty:
                    # find minimum valued price hub that still buys hydrogen
                    breakeven_price_at_hub = local_price_hub_df[
                        local_price_hub_df["cons_price"]
                        == local_price_hub_df["cons_price"].min()
                    ]
                    price_hub_min = pd.concat([price_hub_min, breakeven_price_at_hub])
    # remove null data

    # find_prices is a binary, price_demand is the demand amount used with price hubs, thus,
    # if price hubs are used (find_prices binary), then data utilizing an amount of hydrogen <= price_demand will be removed
    price_hub_demand = H.find_prices * H.price_demand

    tol = 1e-6

    dfs["production"] = dfs["production"][dfs["production"]["prod_capacity"] > tol]
    dfs["consumption"] = dfs["consumption"][
        (dfs["consumption"]["cons_h"] > tol)
        & (~isclose(dfs["consumption"]["cons_h"], price_hub_demand))
    ]
    dfs["conversion"] = dfs["conversion"][dfs["conversion"]["conv_capacity"] > tol]

    dfs["distribution"] = dfs["distribution"][
        (
            (dfs["distribution"]["dist_h"] > tol)
            & (~isclose(dfs["distribution"]["dist_h"], price_hub_demand))
        )
    ]

    # re add price hub data
    if H.find_prices:
        dfs["consumption"] = pd.concat([dfs["consumption"], price_hub_min])

    ## POST PROCESSING:
    # Production
    prod = dfs["production"]
    prod["ccs_retrofit_variable_costs"] = 0

    # combine existing prod data into relevant new prod data columns
    for ccs_v, ccs_percent, ccs_tax, ccs_variable in [
        (
            1,
            H.ccs1_percent_co2_captured,
            H.ccs1_h2_tax_credit,
            H.ccs1_variable_usdPerTon,
        ),
        (
            2,
            H.ccs2_percent_co2_captured,
            H.ccs2_h2_tax_credit,
            H.ccs2_variable_usdPerTon,
        ),
    ]:
        df_filter = prod["ccs{}_built".format(ccs_v)] == 1

        if H.fractional_chec:
            chec_per_ton = ccs_percent
        else:
            chec_per_ton = 1

        for key, new_data in [
            ("prod_checs", prod["ccs{}_checs".format(ccs_v)]),
            (
                "ccs_retrofit_variable_costs",
                # co2 captured * variable costs per ton co2
                prod["prod_h"].multiply(prod["co2_emissions_rate"], axis="index")
                * ccs_percent
                * ccs_variable,
            ),
            ("co2_emissions_rate", prod["co2_emissions_rate"] * (1 - ccs_percent)),
            ("chec_per_ton", chec_per_ton),
            ("ccs_capture_rate", ccs_percent),
            ("h2_tax_credit", ccs_tax),
        ]:
            prod[key] = where(df_filter, new_data, prod[key])

    # remove some unnecessary columns
    # TODO can rewrite better and maybe move?
    # I'd also like to eventually rename some of these columns
    prod_columns = [
        x
        for x in merge_lists["production"] + ["ccs_retrofit_variable_costs"]
        if x
        not in [
            "can_ccs1",
            "can_ccs2",
            "ccs1_built",
            "ccs2_built",
            "ccs1_capacity_h2",
            "ccs1_checs",
            "ccs2_capacity_h2",
            "ccs2_checs",
        ]
    ]

    prod = prod[prod_columns].replace("n/a", 0)

    # multiply cost coefficients by prod_h to get total cost
    cols = [
        "prod_cost_capital",
        "prod_cost_fixed",
        "prod_cost_variable",
        "prod_e_price",
        "prod_ng_price",
        "h2_tax_credit",
    ]

    prod[cols] = prod[cols].multiply(prod["prod_h"], axis="index")
    prod["prod_cost_capital"] = prod["prod_cost_capital"] / H.A / H.time_slices
    # NOTE maybe:
    # prod["prod_cost_variable"] = prod["prod_cost_variable"+ prod["ccs_retrofit_variable_costs"]
    # prod_cost_variable is based on per ton h2, while ccs_retrofit_variable is on per ton co2,
    # which are related in this context. So I think it could be fine to remove the
    # ccs_retrofit_variable column and jut add it to the prod_cost_variable_column

    prod["co2_emitted"] = prod["co2_emissions_rate"] * prod["prod_h"]
    prod["carbon_tax"] = prod["co2_emitted"] * H.carbon_price

    # co2 captured = co2 rate * prod h * capture rate / (1 - capture rate)
    # only if 0 < capture rate < 1; else, co2 captured is capture rate * prod_h
    prod["co2_captured"] = where(
        prod["ccs_capture_rate"].between(0, 1, inclusive="neither"),
        prod["co2_emissions_rate"]
        .multiply(prod["prod_h"], axis="index")
        .multiply(prod["ccs_capture_rate"], axis="index")
        .divide(1 - prod["ccs_capture_rate"], axis="index"),
        prod["ccs_capture_rate"] * prod["prod_h"],
    )
    prod["carbon_capture_tax_credit"] = prod["co2_captured"] * H.carbon_capture_credit

    prod["total_cost"] = prod[
        [
            "prod_cost_capital",
            "prod_cost_fixed",
            "prod_cost_variable",
            "ccs_retrofit_variable_costs",
            "prod_e_price",
            "prod_ng_price",
            "carbon_tax",
        ]
    ].sum(axis=1) - prod[["carbon_capture_tax_credit", "h2_tax_credit"]].sum(axis=1)

    dfs["production"] = prod

    ## CREATE JSON OUTPUTS FROM DATAFRAMES
    hub_dict = {hub: {} for hub in hubs_list}
    for hub in hubs_list:
        hub_dict[hub]["production"] = create_hub_data(dfs["production"], hub)
        hub_dict[hub]["conversion"] = create_hub_data(dfs["conversion"], hub)
        hub_dict[hub]["consumption"] = create_hub_data(dfs["consumption"], hub, 1)
        hub_dict[hub]["distribution"] = create_hub_distribution_data(
            dfs["distribution"], hub
        )

    ## Post Processing print
    print("Summary Results:")

    total_h_consumed = dfs["consumption"]["cons_h"].sum()
    total_h_produced = dfs["production"]["prod_h"].sum()
    print("Hydrogen Consumed (Tonnes/day): {}".format(total_h_consumed))
    print("Hydrogen Produced (Tonnes/day): {}".format(total_h_produced))

    return dfs, hub_dict
