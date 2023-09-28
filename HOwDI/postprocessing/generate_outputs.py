"""
Converts outputs of Hydrogen model into dataframes and a dictionary
Author: Braden Pecora
"""

from functools import reduce
from typing import Any, Dict

import pandas as pd
from idaes.core.util import to_json
from numpy import int64, isclose, where

from HOwDI.model.HydrogenData import HydrogenData

pd.options.mode.chained_assignment = None


def _recursive_clean(nested_dict):
    """Removes unnecessary data from Pyomo model serialized as a JSON dict"""
    black_list = ["__type__", "__id__", "_mutable", "fixed", "stale", "lb", "ub"]
    for key in list(nested_dict):
        if key in black_list:
            del nested_dict[key]
        elif type(nested_dict[key]) is int64:
            nested_dict[key] = int(nested_dict[key])
        elif type(nested_dict[key]) is dict:
            if key == "data":
                nested_dict = _recursive_clean(nested_dict[key])
            else:
                nested_dict[key] = _recursive_clean(nested_dict[key])

    return nested_dict


def _create_df(label, data):
    """Creates dataframe from dictionary {data}, changing name of 'value' column to {label}"""
    df = pd.DataFrame.from_dict(data, orient="index")
    df = df.rename(columns={"value": label})
    return df


def _find_first_non_empty_df(dfs: list[pd.DataFrame]):
    """Returns first non-empty dataframe in list of dataframes {dfs}"""
    for df in dfs:
        if not df.empty:
            return df.copy()
    raise ValueError("All dataframes are empty")


def _join_multiple_dfs(dfs_labels, dfs_values, na_value="n/a"):
    """From a dictionary of dataframes ({label: data_frame}) {dfs_values},
    merges all dataframes with label in {dfs_labels}"""
    dfs = {label: dfs_values[label] for label in dfs_labels}

    # check if any dfs are empty
    # first need to find non-empty df
    non_empty_df = _find_first_non_empty_df(dfs.values())
    non_empty_df_index = non_empty_df.index
    # then check if any other dfs are empty
    for label, _df in dfs.items():
        if _df.empty:
            # build empty df with same index as non-empty df
            dfs[label] = pd.DataFrame(
                data=na_value, index=non_empty_df_index, columns=[label]
            )

    df = reduce(
        lambda left, right: pd.merge(
            left, right, how="outer", left_index=True, right_index=True
        ),
        dfs.values(),
    )
    df.reset_index(inplace=True)
    df = df.fillna(na_value)
    return df


def _tuple_split(df, index, name1, name2):
    """Assuming df[index] is a tuple, splits df[index] into df[name1] df[name2]"""
    # unpack tuples from string, delete old index
    df[index] = df[index].apply(eval)
    df.index = pd.MultiIndex.from_tuples(df[index], names=[name1, name2])
    del df[index]

    return df


def _create_hub_data(
    df: pd.DataFrame, hub: str, start: int = -1
) -> Dict[str, Dict[str, Any]]:
    """
    Create a dictionary of data for a specific hub from a pandas DataFrame.

    :param df: The pandas DataFrame to extract data from.
    :type df: pd.DataFrame
    :param hub: The name of the hub to extract data for.
    :type hub: str
    :param start: The index in the split string to start from (default is -1).
    :type start: int
    :return: A dictionary of data for the specified hub.
    :rtype: Dict[str, Dict[str, Any]]

    The returned dictionary has the following structure:

    {
        "data1": {
            "column1": value1,
            "column2": value2,
            ...
        },
        "data2": {
            "column1": value3,
            "column2": value4,
            ...
        },
        ...
    }

    where `data1`, `data2`, etc. are the index values of the rows in the pandas DataFrame that match the specified hub name,
    and `column1`, `column2`, etc. are the column names of the pandas DataFrame.
    """
    index_column = df.index.name
    df = df.reset_index()
    # find values in index column that match the hub name
    df = df[df[index_column].str.startswith(hub + "_")]
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


def _create_hub_distribution_data(df, hub):
    # this is largely an abstraction tool to make main less messy
    """
    Create a dictionary of distribution data for a specific hub from a pandas DataFrame.

    :param df: The pandas DataFrame to extract data from.
    :type df: pd.DataFrame
    :param hub: The name of the hub to extract data for.
    :type hub: str
    :return: A dictionary of distribution data for the specified hub.
    :rtype: Dict[str, Dict[str, Any]]

    The returned dictionary has the following structure:

    {
        "local": {
            "arc1_TO_arc2": {
                "source_class": "class1",
                "destination_class": "class2",
                "dist_h": value1,
                "source": "arc1",
                "destination": "arc2",
                "destination_class": "class2",
            },
            "arc3_TO_arc4": {
                "source_class": "class3",
                "destination_class": "class4",
                "dist_h": value2,
                "source": "arc3",
                "destination": "arc4",
                "destination_class": "class4",
            },
            ...
        },
        "outgoing": {
            "arc5_TO_hub2": {
                "source_class": "class5",
                "destination_class": "hub2_class",
                "dist_h": value3,
                "source": "arc5",
                "destination": "hub2",
                "destination_class": "hub2_class",
            },
            "arc6_TO_hub2": {
                "source_class": "class6",
                "destination_class": "hub2_class",
                "dist_h": value4,
                "source": "arc6",
                "destination": "hub2",
                "destination_class": "hub2_class",
            },
            ...
        },
        "incoming": {
            "arc7_TO_hub1": {
                "source_class": "class7",
                "destination_class": "hub1_class",
                "dist_h": value5,
                "source": "arc7",
                "destination": "hub1",
                "destination_class": "hub1_class",
            },
            "arc8_TO_hub1": {
                "source_class": "class8",
                "destination_class": "hub1_class",
                "dist_h": value6,
                "source": "arc8",
                "destination": "hub1",
                "destination_class": "hub1_class",
            },
            ...
        },
    }

    where `arc1_TO_arc2`, `arc3_TO_arc4`, etc. are the index values of the rows in the pandas DataFrame that match the specified hub name,
    and `source_class`, `destination_class`, `dist_h`, `source`, `destination`, and `destination_class` are the column names of the pandas DataFrame.
    """
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

    def _out_in_add_info(df):
        # I'm not sure how python's "pass by object reference" works in for loops so I
        # opted for a function to avoid repeating code/boiler-plating
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

    outgoing = _out_in_add_info(outgoing)
    incoming = _out_in_add_info(incoming)

    return {
        "local": local.to_dict("index"),
        "outgoing": outgoing.to_dict("index"),
        "incoming": incoming.to_dict("index"),
    }


def create_outputs_dfs(m, H):
    hubs_list = H.get_hubs_list()

    outputs = to_json(m, return_dict=True)
    outputs = outputs["unknown"]["data"]["None"]["__pyomo_components__"]
    outputs = _recursive_clean(outputs)

    ## CREATE DATAFRAME OUTPUTS
    # create relevant dataframes from json output
    black_list = ["OBJ"]
    all_dfs = {
        key: _create_df(key, value)
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
        "cons_carbonSensitive",
        "cons_h",
        "cons_checs",
        "cons_price",
        "cons_size",
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
        name: _join_multiple_dfs(df_whitelist, all_dfs)
        for name, df_whitelist in merge_lists.items()
    }

    # split tuple string in distribution index
    # ! if my guess on arc_start and arc_end was incorrect, swap arc_start and arc_end in the function arguments
    dfs["distribution"] = _tuple_split(
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

    tol = 1e-3

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

    ## Post Processing print
    print("Summary Results:")

    total_h_consumed = dfs["consumption"]["cons_h"].sum()
    total_h_produced = dfs["production"]["prod_h"].sum()
    print("Hydrogen Consumed (Tonnes/day): {}".format(total_h_consumed))
    print("Hydrogen Produced (Tonnes/day): {}".format(total_h_produced))

    return dfs


def create_output_dict(H: HydrogenData) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    Create a dictionary of output DataFrames for each hub in the `HydrogenData` instance.

    :param H: The `HydrogenData` instance to create output DataFrames from.
    :type H: HydrogenData
    :return: A dictionary of output DataFrames for each hub.
    :rtype: Dict[str, Dict[str, pd.DataFrame]]

    The returned dictionary has the following structure:

    {
        hub1: {
            "production": production_df_for_hub1,
            "consumption": consumption_df_for_hub1,
            "conversion": conversion_df_for_hub1,
            "distribution": distribution_df_for_hub1,
        },
        hub2: {
            "production": production_df_for_hub2,
            "consumption": consumption_df_for_hub2,
            "conversion": conversion_df_for_hub2,
            "distribution": distribution_df_for_hub2,
        },
        ...
    }

    where `hub1`, `hub2`, etc. are the names of the hubs in the `HydrogenData` instance, and
    `production_df_for_hub1`, `consumption_df_for_hub1`, etc. are pandas DataFrames containing
    the output data for each hub.
    """
    hubs_list = H.get_hubs_list()
    dfs = H.output_dfs
    hub_dict = {hub: {} for hub in hubs_list}

    for hub in hubs_list:
        hub_dict[hub]["production"] = _create_hub_data(dfs["production"], hub)
        hub_dict[hub]["conversion"] = _create_hub_data(dfs["conversion"], hub)
        hub_dict[hub]["consumption"] = _create_hub_data(dfs["consumption"], hub, 1)
        hub_dict[hub]["distribution"] = _create_hub_distribution_data(
            dfs["distribution"], hub
        )

    return hub_dict
