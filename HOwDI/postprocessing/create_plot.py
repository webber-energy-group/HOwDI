"""
Creates plot from outputs of model
Author: Braden Pecora

In the current version, there are next to no features,
but the metadata should be fairly easy to access and utilize.
"""
import json
import warnings
from itertools import combinations

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.wkt import loads

from HOwDI.arg_parse import parse_command_line
from HOwDI.model.HydrogenData import HydrogenData

# ignore warning about plotting empty frame
warnings.simplefilter(action="ignore", category=UserWarning)


def roads_to_gdf(wd):
    """Converts roads.csv into a GeoDataFrame object

    This is necessary since .geojson files can not handle LineStrings with multiple points.
    Road geodata are stored as csv, where the geodata are stored as literal strings.
    The shapely.wkt function "loads" can interpret this literal string and convert into a LineString object
    """
    # wd is path where 'hubs.geojson' and 'roads.csv' are located

    # get hubs for crs
    hubs = gpd.read_file(wd / "hubs.geojson")

    # read csv and convert geometry column
    roads = gpd.read_file(wd / "roads.csv")
    roads["geometry"] = roads["road_geometry"].apply(
        loads
    )  # convert string into Linestring
    roads = roads.set_crs(hubs.crs)
    del roads["road_geometry"]

    return roads


def _all_possible_combos(items: list, existing=False) -> list:
    """Returns a list of all possible combos as sets.

    If "existing" is True, extends items with a duplicate of items
    where each item in items is followed by "Existing"

    For example

    all_possible_combos([1,2,3])
    returns
    [{1}, {2}, {3}, {1, 2}, {1, 3}, {2, 3}, {1, 2, 3}]

    This function is used for filtering dataframes.
    The dataframe has a set corresponding to the production
    types at each hub. For example, a hub could have a corresponding
    production value of {"smr","smrExisting"} or just {"smr",}, and we
    want to see if all values of this set are in the list "items" of production
    types (defined by therm/elec_production.csv "type" column).
    To do this, we must turn "items" into a list of all possible combinations.

    """
    if existing == True:
        # append "Existing" versions
        items.extend([i + "Existing" for i in items])
    out = []
    for length in range(len(items)):
        out.extend([frozenset(combo) for combo in combinations(items, length + 1)])
    return out


def _find_max_length_set_from_list(a: list):
    """From a list of sublists (or similar sub-object),
    returns the longest sublist (or sub-object as a list)"""
    return list(max(x) for x in a)


def _diff_of_list(a: list, b: list) -> list:
    """From two outputs of 'all_possible_combos',
    gets all possible difference sets

    For example, if the items in "a" are {A,B,C} and the
    items in "b" are {1,2,3}, this would return
    [{A,1},{A,2},{A,3},{A,1,2},{A,1,3},{A,2,3},{A,B,1},...]
    but wouldn't include sets where all items are contained by
    either a or b.
    """

    # get the unique items from a and b,
    # basically undo all_possible_combos
    # just an easy way of not writing the same thing twice
    a_unique, b_unique = map(_find_max_length_set_from_list, (a, b))

    # get all possible combos between a_unique and b_unique
    all_possible = _all_possible_combos(a_unique + b_unique)

    # find the difference
    difference = set(all_possible) - set(a) - set(b)
    return list(difference)


def create_plot(H: HydrogenData):
    """
    Parameters:
    H is a HydrogenData object with the following:

    H.hubs_dir: directory where hubs geo files are stored (hubs.geojson, roads.csv)
    H.output_dict: output dictionary of model
    H.shpfile: location of shapefile to use as background
    H.prod_therm and H.prod_elec: DataFrame with column "Type",
     used for determining if a node has thermal, electric, or both types of production.

    Returns:
    fig: a matplotlib.plt object which is a figure of the results.
    """

    hub_data = json.load(open(H.hubs_dir / "hubs.geojson"))["features"]
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
        for hub, hub_data in H.output_dict.items()
        if hub_data["distribution"] != {"local": {}, "outgoing": {}, "incoming": {}}
    }

    def get_relevant_p_or_c_data(hub_data_p_or_c):
        # p_or_c = production or consumption
        # turns keys of hub_data['production'] or hub_data['consumption'] into a set,
        # used in the dictionary comprehensions below
        if hub_data_p_or_c != {}:
            return frozenset(hub_data_p_or_c.keys())
        else:
            return None

    prod_data = {
        hub: get_relevant_p_or_c_data(hub_data["production"])
        for hub, hub_data in H.output_dict.items()
    }
    cons_data = {
        hub: get_relevant_p_or_c_data(hub_data["consumption"])
        for hub, hub_data in H.output_dict.items()
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
        for hub, hub_data in H.output_dict.items()
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
    us_county = gpd.read_file(H.shpfile)
    # us_county = gpd.read_file('US_COUNTY_SHPFILE/US_county_cont.shp')
    tx_county = us_county[us_county["STATE_NAME"] == "Texas"]
    tx = tx_county.dissolve()
    tx.plot(ax=ax, color="white", edgecolor="black")

    # Plot hubs
    hubs = distribution[distribution.type == "Point"]

    prod_types = H.get_prod_types()
    thermal_prod_combos = _all_possible_combos(prod_types["thermal"], existing=True)
    electric_prod_combos = _all_possible_combos(prod_types["electric"])
    both_prod_combos = _diff_of_list(thermal_prod_combos, electric_prod_combos)
    # Options for hub by technology
    hub_plot_tech = {
        "default": {
            "name": "No Production (Color)",
            "color": "#219ebc",
            "marker": ".",
            "set": None,
            "b": lambda df: df["production"].isnull(),
        },
        "thermal": {
            "name": "Thermal Production",
            "color": "red",
            "b": lambda df: df["production"].isin(thermal_prod_combos),
        },
        "electric": {
            "name": "Electric Production",
            "color": "blue",
            "b": lambda df: df["production"].isin(electric_prod_combos),
        },
        "both": {
            "name": "Therm. and Elec. Production",
            "color": "purple",
            "b": lambda df: df["production"].isin(both_prod_combos),
        },
    }

    # Options for hub by Production, Consumption, or both
    hub_plot_type = {
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
        roads = roads_to_gdf(H.hubs_dir)

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

    return fig


def main():
    args = parse_command_line()

    H = HydrogenData(
        scenario_dir=args.scenario_dir,
        inputs_dir=args.inputs_dir,
        outputs_dir=args.outputs_dir,
        raiseFileNotFoundError=False,
    )

    try:
        H.output_dict = json.load(open(H.outputs_dir / "outputs.json"))
    except FileNotFoundError:
        from HOwDI.postprocessing.generate_outputs import create_output_dict

        H.create_output_dfs()
        H.output_dict = create_output_dict(H)
        H.write_output_dict()

    create_plot(H).savefig(H.outputs_dir / "fig.png")


if __name__ == "__main__":
    main()
