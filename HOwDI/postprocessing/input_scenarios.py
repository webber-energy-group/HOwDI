import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from dash import Dash
from sklearn.cluster import KMeans

from HOwDI.util import (
    create_db_engine,
    get_truncated_monte_carlo_options_dict,
    monte_carlo_keys,
    set_index,
    scale_by_distance_from_mean,
)
from HOwDI.model.HydrogenData import HydrogenData, init_multiple

# TODO get function that filters outputs to show
#      price not satisfied
#      - maybe get h to be stored in H object


def recover_full_data(h, engine):
    return HydrogenData(
        uuid=h.uuid, sql_database=engine, read_type="sql", trial_number=h.trial_number
    )


def add_average(data, column_filter):
    data["average/" + column_filter] = (
        data[[c for c in data.columns if "/" + column_filter in c]]
        .astype(float)
        .mean(axis=1)
    )
    return data


def get_monte_carlo_info(
    uuid, engine=None, normalize=True, price_types=["FuelStation"]
):
    """_summary_

    Args:
        uuid (str): uuid of dataset
        engine (sqlite connection, optional): Connection to sqlite db. Defaults to engine in config_local.yml.
        normalize (bool, optional): Normalize data. Defaults to True.
        price_types (list, optional): Prices to average. Defaults to ["FuelStation"].

    Returns:
        DataFrame: Contains montecarlo info
    """
    if engine is None:
        engine = create_db_engine()

    # keys for selecting options
    keys = monte_carlo_keys(uuid, engine)

    # dict structure for matching
    monte_carlo_data_filter = get_truncated_monte_carlo_options_dict(uuid, engine)

    hs = init_multiple(uuid, engine, monte_carlo_data_filter)
    h_base = recover_full_data(hs[0], engine)
    for h in hs:
        h.price_hubs = h_base.price_hubs
    # prices = [h.get_prices_dict() for h in hs]
    monte_carlo_info = pd.concat([h.get_trial_info() for h in hs])
    monte_carlo_info = set_index(monte_carlo_info, "trial")
    monte_carlo_info = monte_carlo_info.astype(float)

    # normalize
    if normalize == True:
        monte_carlo_normalized = monte_carlo_info
        input_keys = ["input-" + key for key in keys if not ("settings" in key)]
        monte_carlo_normalized[input_keys] = scale_by_distance_from_mean(
            monte_carlo_normalized[input_keys]
        )
        monte_carlo_info = monte_carlo_normalized

    for price_type in price_types:
        monte_carlo_info = add_average(monte_carlo_info, price_type)

    return monte_carlo_info
    # plot_info = monte_carlo_info.T.astype(float)


def cluster_monet_carlo_info(
    mc_info, value_column="average/FuelStation", n_bins=5, n_clusters=3
):
    keep_columns = [col for col in mc_info.columns if "input" in col]
    mc_info = mc_info[keep_columns + [value_column]]

    rename_columns = {col: col.split("/")[-2] for col in keep_columns}
    mc_info.rename(columns=rename_columns, inplace=True)
    in_columns = list(rename_columns.values())

    # min_price = mc_info[value_column].min()
    # max_price = mc_info[value_column].max()
    # bins = np.linspace(min_price, max_price, n_bins + 1)
    # bins[-1] += 1e-6  # adjust for <=
    # bins = [(bins[i], bins[i + 1]) for i in range(len(bins) - 1)]

    # binned_data = [
    #     mc_info[
    #         (mc_info[value_column] >= lower_bound)
    #         & (mc_info[value_column] < upper_bound)
    #     ]
    #     for lower_bound, upper_bound in bins
    # ]

    bin_model = KMeans(n_clusters=n_bins)
    prices = mc_info[value_column].values.reshape(-1, 1)
    bin_model.fit(prices)
    mc_info["bin"] = bin_model.predict(prices)

    bins = mc_info[["bin", value_column]].groupby("bin").mean()[value_column]

    clustered_data = []
    distortions = []
    for bin_number, value in bins.items():
        bin_data = mc_info[mc_info["bin"] == bin_number]
        cluster_model = KMeans(n_clusters=n_clusters)
        cluster_model.fit(bin_data[rename_columns.values()])

        clustered_data_for_bin = pd.DataFrame(
            cluster_model.cluster_centers_, columns=in_columns
        )
        clustered_data_for_bin["bin"] = bin_number
        clustered_data_for_bin[value_column] = value
        clustered_data.append(clustered_data_for_bin)

        distortions.append({"bin": bin_number, "Inertia": cluster_model.inertia_})

    clustered_data = pd.concat(clustered_data)
    clustered_data = clustered_data.reset_index()
    clustered_data = clustered_data.rename(columns={"index": "cluster"})

    distortions = pd.DataFrame(distortions).set_index("bin")
    # melt = pd.melt(
    #     clustered_data[clustered_data["bin"] == 1],
    #     id_vars=[value_column, "bin", "cluster"],
    # )

    # fix, ax = plt.subplots()
    # g = sns.lineplot(
    #     x="variable",
    #     y="value",
    #     data=melt,
    #     hue=value_column,
    #     units="cluster",
    #     style="cluster",
    #     estimator=None,
    #     lw=1,
    # )
    # plt.xticks(rotation=45)
    # ax.legend().remove()

    return clustered_data, distortions


def main():
    engine = create_db_engine(
        "sqlite:///C:/Users/bpeco/Box/h2@scale/h2_model/test.sqlite"
    )
    mc_info = get_monte_carlo_info(
        uuid="f646d589-043f-4937-bbef-5f0aa3b00027",
        engine=engine,
    )
    cluster_monet_carlo_info(mc_info)


if __name__ == "__main__":
    main()
