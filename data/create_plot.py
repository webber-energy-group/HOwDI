"""
Creates plot from outputs of model
Author: Braden Pecora

In the current version, there are next to no features,
but the metadata should be fairly easy to access and utilize.
"""
import json
import warnings

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

try:
    from data.hubs.roads_to_gdf import roads_to_gdf
except ModuleNotFoundError:
    from hubs.roads_to_gdf import roads_to_gdf

# ignore warning about plotting empty frame
warnings.simplefilter(action="ignore", category=UserWarning)


def main(data, data_dir, scenario_dir):
    """
    data: outputs of model
    data_dir: location of data for hubs and shapefile
    scenario_dir: figure outputted to scenario_dir/outputs/fig.png
    therm_prod: thermal production dataframe
    """

    hub_data = json.load(open(data_dir / "hubs" / "hubs.geojson"))["features"]
    locations = {d["properties"]["hub"]: d["geometry"]["coordinates"] for d in hub_data}

    # clean data
    def get_relevant_dist_data(hub_data):
        # returns a list of dicts used in a dict comprehension with only the `relevant_keys`
        outgoing_dicts = hub_data["distribution"]["outgoing"]
        relevant_keys = ["source_class", "destination", "destination_class"]
        for _, outgoing_dict in outgoing_dicts.items():
            for key in list(outgoing_dict.keys()):
                if key not in relevant_keys:
                    del outgoing_dict[key]
        return [outgoing_dict for _, outgoing_dict in outgoing_dicts.items()]

    dist_data = {
        hub: get_relevant_dist_data(hub_data)
        for hub, hub_data in data.items()
        if hub_data["distribution"] != {"local": {}, "outgoing": {}, "incoming": {}}
    }

    def get_relevant_p_or_c_data(hub_data_p_or_c):
        # p_or_c = production or consumption
        # turns keys of hub_data['production'] or hub_data['consumption'] into a set,
        # used in the dictionary comprehensions below
        if hub_data_p_or_c != {}:
            return set(hub_data_p_or_c.keys())
        else:
            return None

    prod_data = {
        hub: get_relevant_p_or_c_data(hub_data["production"])
        for hub, hub_data in data.items()
    }
    cons_data = {
        hub: get_relevant_p_or_c_data(hub_data["consumption"])
        for hub, hub_data in data.items()
    }

    def get_production_capacity(hub_data_prod):
        if hub_data_prod != {}:
            return sum(
                [
                    prod_data_by_type["prod_h"]
                    for _, prod_data_by_type in hub_data_prod.items()
                ]
            )
        else:
            return 0

    prod_capacity = {
        hub: get_production_capacity(hub_data["production"])
        for hub, hub_data in data.items()
    }

    marker_size_default = 20
    prod_capacity_values = list(prod_capacity.values())
    number_of_producers = sum(
        [1 for prod_capacity_value in prod_capacity_values if prod_capacity_value > 0]
    )
    avg_prod_value = sum(prod_capacity_values) / number_of_producers
    marker_size_factor = (
        marker_size_default / avg_prod_value
    )  # the default marker size / the average production value across non-zero producers

    def get_marker_size(prod_capacity):
        if prod_capacity != 0:
            size = marker_size_factor * prod_capacity
        else:
            # prod capacity is zero for non-producers, which would correspond to a size of zero.
            # Thus, we use the default size for non-producers
            size = marker_size_default
        return size

    prod_capacity_marker_size = {
        hub: get_marker_size(prod_capacity)
        for hub, prod_capacity in prod_capacity.items()
    }

    features = []
    for hub, hub_connections in dist_data.items():
        hub_latlng = locations[hub]
        hub_geodata = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": hub_latlng},
            "properties": {
                "name": hub,
                "production": prod_data[hub],
                "consumption": cons_data[hub],
                "production_capacity": prod_capacity[hub],
                "production_marker_size": prod_capacity_marker_size[hub],
            },
        }
        features.append(hub_geodata)

        for hub_connection in hub_connections:

            dest = hub_connection["destination"]
            dist_type = hub_connection["source_class"]
            dest_latlng = locations[dest]

            line_geodata = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [hub_latlng, dest_latlng],
                },
                "properties": {
                    "name": hub + " to " + dest,
                    "start": hub,
                    "end": dest,
                    "dist_type": dist_type,
                },
            }
            features.append(line_geodata)

    geo_data = {"type": "FeatureCollection", "features": features}
    distribution = gpd.GeoDataFrame.from_features(geo_data)

    ########
    # Plot

    # initialize figure
    fig, ax = plt.subplots(figsize=(10, 10), dpi=300)
    # get Texas plot
    us_county = gpd.read_file(data_dir / "US_COUNTY_SHPFILE" / "US_county_cont.shp")
    # us_county = gpd.read_file('US_COUNTY_SHPFILE/US_county_cont.shp')
    tx_county = us_county[us_county["STATE_NAME"] == "Texas"]
    tx = tx_county.dissolve()
    tx.plot(ax=ax, color="white", edgecolor="black")

    # Plot hubs
    hubs = distribution[distribution.type == "Point"]
    hub_plot_tech = {  # Options for hub by technology
        "default": {
            "name": "No Production (Color)",
            "color": "#219ebc",
            "marker": ".",
            "set": None,
            "b": lambda df: df["production"].isnull(),
        },
        "smr": {
            "name": "New SMR (Color)",
            "color": "red",
            "set": set(("smr",)),
            "b": lambda df: df["production"] == set(("smr",)),
        },
        "smrExisting": {
            "name": "Existing SMR (Color)",
            "color": "yellow",
            "set": set(("smrExisting",)),
            "b": lambda df: df["production"] == set(("smrExisting",)),
        },
        "smr+smrExisting": {
            "name": "New and Existing SMR (Color)",
            "color": "orange",
            "set": set(("smr", "smrExisting")),
            "b": lambda df: df["production"] == set(("smr", "smrExisting"))
            # I want a better way to do this, but I could not find one
            # I tried to find a way to have the color split, but
            # a) I could not get it to work, and
            # b) it seems you can only split with two colors in matplotlib
            # ... seems like all the permutations will get hair fairly fast,
            # we should probably find a way to do this
        },
        "electrolyzer": {
            "name": "Electrolysis (Color)",
            "color": "green",
            "set": set(("electrolyzer",)),
            "b": lambda df: df["production"] == set(("electrolyzer",)),
        }
        # and so on... (ccs not implemented -> can't plot ccs, haven't gone through all combinations yet)
        # TODO maybe have makers colored by percent production:
        #   https://stackoverflow.com/questions/41167300/multiple-color-fills-in-matplotlib-markers
        # or maybe only plot "smr","electrolysis","smr+electrolysis" where "smr" includes "smr" and "smrExisting"?
    }
    hub_plot_type = {  # Options for hub by Production, Consumption, or both
        # 'none' :
        #     {
        #         'b' : lambda df: df['production'].isnull() & df['consumption'].isnull(),
        #         'marker' : '.',
        #     },
        "production": {
            "name": "Production (Shape)",
            "b": lambda df: df["production"].notnull() & df["consumption"].isnull(),
            "marker": "^",
        },
        "consumption": {
            "name": "Consumption (Shape)",
            "b": lambda df: df["production"].isnull() & df["consumption"].notnull(),
            "marker": "v",
        },
        "both": {
            "name": "Production and Consumption (Shape)",
            "b": lambda df: df["production"].notnull() & df["consumption"].notnull(),
            "marker": "D",
        },
    }
    # Plot hubs based on production/consumption (marker) options and production tech (color) options
    # in short, iterates over both of the above option dictionaries
    # the 'b' (boolean) key is a lambda function that returns the locations of where the hubs dataframe
    #   matches the specifications. An iterable way of doing stuff like df[df['production'] == 'smr']
    [
        hubs[type_plot["b"](hubs) & tech_plot["b"](hubs)].plot(
            ax=ax,
            color=tech_plot["color"],
            marker=type_plot["marker"],
            zorder=5,
            markersize=hubs[type_plot["b"](hubs) & tech_plot["b"](hubs)][
                "production_marker_size"
            ],
        )
        for tech, tech_plot in hub_plot_tech.items()
        for type_name, type_plot in hub_plot_type.items()
    ]

    # Plot connections:
    dist_pipelineLowPurity_col = "#9b2226"
    dist_pipelineHighPurity_col = "#6A6262"
    dist_truckLiquefied_color = "#fb8500"
    dist_truckCompressed_color = "#bb3e03"

    connections = distribution[distribution.type == "LineString"]
    roads_connections = connections.copy()

    if not roads_connections.empty:

        # get data from roads csv, which draws out the road path along a connection
        roads = roads_to_gdf(data_dir / "hubs")

        for row in roads.itertuples():
            # get road geodata for each connection in connections df
            hubA = row.hubA
            hubB = row.hubB
            roads_connections.loc[
                (roads_connections["start"] == hubA)
                & (roads_connections["end"] == hubB),
                "geometry",
            ] = row.geometry
            roads_connections.loc[
                (roads_connections["end"] == hubA)
                & (roads_connections["start"] == hubB),
                "geometry",
            ] = row.geometry

        connections[connections["dist_type"] == "dist_pipelineLowPurity"].plot(
            ax=ax, color=dist_pipelineLowPurity_col, zorder=1
        )
        connections[connections["dist_type"] == "dist_pipelineHighPurity"].plot(
            ax=ax, color=dist_pipelineHighPurity_col, zorder=1
        )

        # change 'road_connections' to 'connections' to plot straight lines
        roads_connections[connections["dist_type"] == "dist_truckLiquefied"].plot(
            ax=ax, color=dist_truckLiquefied_color, zorder=1
        )
        roads_connections[connections["dist_type"] == "dist_truckCompressed"].plot(
            ax=ax, color=dist_truckCompressed_color, legend=True, zorder=1
        )

    legend_elements = []
    legend_elements.extend(
        [
            Line2D(
                [0],
                [0],
                color=dist_pipelineLowPurity_col,
                lw=2,
                label="Gas Pipeline (Low Purity)",
            ),
            Line2D(
                [0],
                [0],
                color=dist_pipelineHighPurity_col,
                lw=2,
                label="Gas Pipeline (High Purity)",
            ),
            Line2D(
                [0],
                [0],
                color=dist_truckLiquefied_color,
                lw=2,
                label="Liquid Truck Route",
            ),
            Line2D(
                [0],
                [0],
                color=dist_truckCompressed_color,
                lw=2,
                label="Gas Truck Route",
            ),
        ]
    )

    legend_elements.extend(
        [
            Line2D(
                [0],
                [0],
                color=tech_plot["color"],
                label=tech_plot["name"],
                marker="o",
                lw=0,
            )
            for tech, tech_plot in hub_plot_tech.items()
        ]
    )
    legend_elements.extend(
        [
            Line2D(
                [0],
                [0],
                color="black",
                label=type_plot["name"],
                marker=type_plot["marker"],
                lw=0,
            )
            for type_name, type_plot in hub_plot_type.items()
        ]
    )

    ax.legend(handles=legend_elements, loc="upper left")

    fig.savefig(scenario_dir / "outputs" / "fig.png")


if __name__ == "__main__":
    from json import load
    from pathlib import Path

    scenario_path = Path("base")
    data_path = scenario_path / "outputs" / "outputs.json"
    data = load(open(data_path))
    main(data, Path("."), scenario_path)
