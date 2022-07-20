"""
hydrogen model module
takes data from demand.csv
uses normal distribution to create a number of discrete demand-price consumers with or without carbon sensitivity
"""

"""NOT USED"""

import numpy
import pandas


def normal_dist(x, mean, std):
    prob_density = (numpy.pi * std) * numpy.exp(-0.5 * ((x - mean) / std) ** 2)
    return prob_density


def discrete_pdf(demandSector, demand_csv):
    """
    demandSector = string in "sector" column of demand_csv
    demand_csv = a csv with price, carbon, and other information about each demand sector

    returns a pandas dataframe with discrete consumers whose price points and carbon sensitivity match a normal distribution based on data from demand_csv

    """
    demand_csv_short = demand_csv[demand_csv["sector"] == demandSector]
    # define the inputs for the normal distribution
    mean = demand_csv_short["breakevenPriceMean"].iloc[0]
    std = demand_csv_short["breakevenPriceStd"].iloc[0]
    discrete_consumers = demand_csv_short["discreteConsumersPerSector"].iloc[0]
    discrete_price_points = numpy.linspace(
        mean - 2 * std, mean + 2 * std, discrete_consumers
    )
    # calcualte the probability density function
    pdf = normal_dist(discrete_price_points, mean, std)
    # account for carbon-sensitive consumers
    carbon_sensitive_fraction = demand_csv_short["carbonSensitiveFraction"].iloc[0]
    # construct the dataframe capturing the discrete consumers
    consumers_regular = pandas.DataFrame(
        {
            "sector": demandSector,
            "firm": discrete_price_points.round(0).astype(int).astype(str),
            "breakevenPrice": discrete_price_points.round(0),
            "size": pdf / (pdf.sum()) * (1 - carbon_sensitive_fraction),
            "carbonSensitive": 0,
            "breakevenCarbon_g_MJ": demand_csv_short["breakevenCarbon_g_MJ"].iloc[0],
            "fuelingStation": demand_csv_short["fuelingStation"].iloc[0],
            "storageDays": demand_csv_short["storageDays"].iloc[0],
        }
    )
    consumers_carbon = pandas.DataFrame(
        {
            "sector": demandSector,
            "firm": [
                s + "_c"
                for s in list(discrete_price_points.round(0).astype(int).astype(str))
            ],
            "breakevenPrice": discrete_price_points.round(0),
            "size": pdf / (pdf.sum()) * (carbon_sensitive_fraction),
            "carbonSensitive": 1,
            "breakevenCarbon_g_MJ": demand_csv_short["breakevenCarbon_g_MJ"].iloc[0],
            "fuelingStation": demand_csv_short["fuelingStation"].iloc[0],
            "storageDays": demand_csv_short["storageDays"].iloc[0],
        }
    )
    # concat the dataframes to the global consumers dataframe
    consumers_add = pandas.concat([consumers_regular, consumers_carbon])
    consumers_add = consumers_add.reset_index(drop=True)
    return consumers_add


def node_discrete_consumers(node, consumers_df, nodes_csv):
    """
    node = string in "node" column of nodes_csv
    consumers_df = dataframe returned by the discrete_pdf() function
    nodes_csv = a csv with node name, and tonnes-per-day of potential demand for different sectors

    returns a pandas dataframe with discrete consumers for each node where size is now in terms of tonnes-per-day instead of a probability density function

    """
    node_consumers_add = pandas.concat(
        [
            pandas.DataFrame({"node": numpy.repeat(node, len(consumers_df))}),
            consumers_df.copy(),
        ],
        axis=1,
    )
    node_sector_size_list = list(
        nodes_csv[nodes_csv["node"] == node][consumers_df["sector"]].iloc[0]
    )
    node_consumers_add["size"] = node_consumers_add["size"] * node_sector_size_list
    node_consumers_add = node_consumers_add[node_consumers_add["size"] != 0]
    return node_consumers_add


def add_existing_demand(node_consumers_df, existing_consumers_df):
    """
    node_consumers_df = dataframe returned by the node_discrete_consumers() function
    existing_consumers_df = a csv (demand_existing.csv) with columns matching the node_consumers_df dataframe

    concatenates these two dataframes

    """
    node_consumers_df = pandas.concat([node_consumers_df, existing_consumers_df])
    return node_consumers_df


def main(H):
    """
    H: a hydrogen_inputs object created in the hydrogen model
    run the functions above
    return the node_consumers dataframe
    """
    #
    demand_csv = H.demand
    nodes_csv = H.nodes
    consumers_existing = H.consumers_existing
    # empty dataframes to concatentate the results to
    consumers = pandas.DataFrame(
        columns=[
            "sector",
            "firm",
            "breakevenPrice",
            "size",
            "carbonSensitive",
            "breakevenCarbon_g_MJ",
            "fuelingStation",
        ]
    )
    node_consumers = pandas.DataFrame(
        columns=[
            "node",
            "sector",
            "firm",
            "breakevenPrice",
            "size",
            "carbonSensitive",
            "breakevenCarbon_g_MJ",
            "fuelingStation",
        ]
    )
    # for each sector, create a discrete pdf for normal and carbon-sensitive consumers
    for ds in demand_csv["sector"].unique():
        consumers = pandas.concat([consumers, discrete_pdf(ds, demand_csv)])
        consumers = consumers.reset_index(drop=True)
    # distribute the sectors across the various nodes
    for n in nodes_csv["node"]:
        node_consumers = pandas.concat(
            [node_consumers, node_discrete_consumers(n, consumers, nodes_csv)]
        )
        node_consumers = node_consumers.reset_index(drop=True)
    # add existing demand
    node_consumers = add_existing_demand(node_consumers, consumers_existing)
    # index and return
    node_consumers["name"] = (
        node_consumers["node"]
        + "_"
        + node_consumers["sector"]
        + "_"
        + node_consumers["firm"]
    )
    node_consumers = node_consumers.set_index("name")
    return node_consumers
