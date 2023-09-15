"""
Finds a list of relevant arcs from all possible connections between hubs.
Finds the road and euclidian distance for said arcs.

In the context of finding all possible connections between nodes on a graph,
there are often many arcs (connections) that are not worth considering, especially
if the model complexity increases significantly with the number of arcs.
For example, a truck driving from Dallas to San Antonio will always drive through Austin -
there is no need to consider a route that goes directly from Dallas to San Antonio without going through Austin [#f1]_.

If there are n nodes in a graph, there are :math:`n(n-1)/2` possible arcs. If the (computational) work
done on each arc is expensive, it is worth reducing the number of arcs considered.

For the case of this file, the computational work done on each arc is
an API call to determine road and euclidian distance between two hubs.
In the scope of HOwDI, each additional arc adds several variables to the optimization
model, which increases the runtime of the model.

A heuristic method is used to reduce the number of arcs considered.
A rigorous approach is not required since run times are on the order of minutes, not days or hours.
Briefly, the heuristic method is as follows:

.. code-block:: python

    for node in nodes:
        c = sort_by_distance(node.all_possible_connections, how="ascending")
        
        shortest_distance = c[0].distance
        farthest_distance_allowed = shortest_distance * length_factor
        # the length factor is determined by classifying the node as major, minor, or regular
        
        connections_to_keep = c[0:minimum_number_of_connections - 1] 
        uncertain_connections = c[minimum_number_of_connections:]
        
        for connection in uncertain_connections:
            if connection.distance <= farthest_distance_allowed:
                connections_to_keep.append(connection)
                
Further explanation of the algorithm is outside of the scope of this documentation
and can be sought out within the code itself.

.. rubric:: Footnotes

.. [#f1] I acknowledge that SH130 exists, but the difference this edge case would cause is marginal and unrealistic since trucks rarely utilize toll roads.   
"""
import warnings
from shapely.errors import ShapelyDeprecationWarning

warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)
warnings.simplefilter(action="ignore", category=DeprecationWarning)
# ignore warning :
# The array interface is deprecated and will no longer work in Shapely 2.0.
# Convert the '.coords' to a numpy array instead.
# arr = construct_1d_object_array_from_listlike(values)
import itertools
import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import requests
from shapely.geometry import LineString

# https://2.python-requests.org/en/master/user/advanced/#session-objects
s = requests.Session()  # improve performance over API calls

# def sort_dict(d:dict) -> dict:
#     return dict(sorted(d.items(), key=lambda x:x[1]))


class Hub:
    """
    A class representing a hub location on a map. For use in :func:`get_route`.

    Parameters
    -----------
    coords : tuple of float
        A tuple containing the latitude and longitude coordinates of the hub.

    Attributes
    -----------
    x : float
        The latitude coordinate of the hub.
    y : float
        The longitude coordinate of the hub.

    Methods
    --------
    __str__():
        Returns a string representation of the hub in the format "latitude,longitude".

    Example:
    --------
    >>> hub = Hub((37.7749, -122.4194))
    >>> print(hub)
    37.7749,-122.4194
    """

    def __init__(self, coords):
        self.x = coords[0]
        self.y = coords[1]

    def __str__(self):
        return "{},{}".format(self.x, self.y)


def get_route(hubA, hubB):
    """
    Returns the shortest driving route between two hubs using the Open Source Routing Machine (OSRM) API.

    Parameters
    -----------
    hubA : str
        The starting hub for the route.
    hubB : str
        The ending hub for the route.

    Returns
    --------
    dict
        A dictionary containing the route geometry as a GeoJSON object and other route information.

    Raises
    -------
    requests.exceptions.RequestException
        If there was an error making the request to the OSRM API.
    IndexError
        If there are no routes returned by the OSRM API.
    """
    # REF https://github.com/Project-OSRM/osrm-backend/blob/master/docs/http.md#trip-service
    url = "http://router.project-osrm.org/route/v1/driving/{};{}?geometries=geojson".format(
        hubA, hubB
    )
    r = s.get(url)
    return json.loads(r.text)["routes"][0]


def make_route(row):
    """
    Calculates the shortest driving route between two hubs and returns route information.

    Parameters
    -----------
    row : pandas.Series
        A pandas Series containing the coordinates of two hubs.

    Returns
    --------
    pandas.Series
        A pandas Series containing the duration, distance, and geometry of the shortest driving route.

    Example
    --------
    >>> row = pd.Series({"coords": [(37.7749, -122.4194), (37.8716, -122.2727)]})
    >>> make_route(row)
    duration      1308.7
    distance      19.019
    """

    line = list(row.coords)
    hubA = Hub(line[0])
    hubB = Hub(line[1])

    route = get_route(hubA, hubB)
    road_geometry = LineString(route["geometry"]["coordinates"])
    km_distance = route["distance"] / 1000
    duration = route["duration"]

    return pd.Series([duration, km_distance, road_geometry])


def create_arcs(
    hubs_dir,
    geohubs=None,
    create_fig=False,
    shpfile=None,
    epsg: int = 3082,
    existing_arcs: pd.DataFrame = None,
    blacklist_arcs: pd.DataFrame = None,
    minor_length_factor: float = 5,
    major_length_factor: float = 0.8,
    regular_length_factor: float = 0.9,
    min_hubs: int = 3,
):
    """
    Creates a list of relevant arcs from all possible connections between hubs.
    With a large number of hubs, the number of possible connections is very large and must be scaled down.
    Hubs can be denoted as major (+1), minor (-1), or regular (0) hubs.
    A major hub hub will incur less cost to connect to a connect to more hubs.
    The opposite is true for minor hubs.

    Parameters
    -----------
    hubs_dir : str or pathlib.Path
        The directory containing the hubs.csv, hubs.geojson, arcs_whitelist.csv, and arcs_blacklist.csv files.
    geohubs : geopandas.GeoDataFrame, optional
        A GeoDataFrame containing the hubs and their geometries. If not provided, the hubs.geojson file in the hubs_dir will be used.
    create_fig : bool, optional
        If True, a figure of the hubs and arcs will be created and saved to the hubs_dir.
    shpfile : str or pathlib.Path, optional
        The underlying shapefile for the figure produced.
    epsg : int, optional
        The EPSG code for the coordinate reference system of the hubs. Default is 3082 (NAD83 / California Albers).
    existing_arcs : pandas.DataFrame, optional
        A DataFrame containing the existing arcs between hubs. If not provided, the arcs_whitelist.csv file in the hubs_dir will be used.
    blacklist_arcs : pandas.DataFrame, optional
        A DataFrame containing the arcs that should not be considered. If not provided, the arcs_blacklist.csv file in the hubs_dir will be used.
    minor_length_factor : float, optional
        Effective reach multiplier.
        Default is 5.
    major_length_factor : float, optional
        Effective reach multiplier.
        Default is 0.8.
    regular_length_factor : float, optional
        Effective reach multiplier.
        Default is 0.9.
    min_hubs : int, optional
        The minimum number of hubs that a hub must be connected to. Supersedes length factor constraints.
        Default is 3. 4 is also a good value.

    """
    plt.style.use("dark_background")
    # read files and establish parameters

    hubs_df = pd.read_csv(hubs_dir / "hubs.csv").set_index("hub")
    # sort by minor; important for indexing direction
    hubs_df = hubs_df.sort_values(by=["status"], ascending=True)
    hubs = hubs_df.index.tolist()

    if geohubs is None:
        geohubs = gpd.read_file(hubs_dir / "hubs.geojson")
        geohubs = geohubs.set_index("hub")
    lat_long_crs = geohubs.crs
    geohubs = geohubs.to_crs(epsg=epsg)

    if existing_arcs is None:
        existing_arcs = pd.read_csv(hubs_dir / "arcs_whitelist.csv")
    if blacklist_arcs is None:
        blacklist_arcs = pd.read_csv(hubs_dir / "arcs_blacklist.csv")

    # length factors (lf) are effective reach
    # length factor > 1, restricts max distance to min*lf
    # length factor < 1, loosens max distance to min*lf (in short)

    # Initialize Figure with Texas base
    if create_fig:
        fig, ax = plt.subplots(figsize=(10, 10), dpi=300)
        if shpfile is None:
            # logger.warning()
            print(
                "An arcs figure is being generated but no underlying shapefile exists!"
            )
        else:
            # TODO make generic
            us_county = gpd.read_file(shpfile)
            tx_county = us_county[us_county["STATE_NAME"] == "Texas"]
            tx = tx_county.dissolve().to_crs(epsg=epsg)
            tx.plot(ax=ax, color="white", edgecolor="black")

    # get all possible combinations of size 2, output is list of tuples turned into a multiindex
    hubs_combinations = list(itertools.combinations(hubs, 2))
    index = pd.MultiIndex.from_tuples(hubs_combinations, names=["startHub", "endHub"])
    gdf = gpd.GeoDataFrame(index=index)

    hubA = gpd.GeoDataFrame(gdf.join(geohubs.rename_axis("startHub")))
    hubB = gpd.GeoDataFrame(gdf.join(geohubs.rename_axis("endHub")))

    # create line from hubAA to hubB (for plotting purposes)
    gdf["LINE"] = [
        LineString([(a.x, a.y), (b.x, b.y)])
        for (a, b) in zip(hubA.geometry, hubB.geometry)
    ]
    gdf = gpd.GeoDataFrame(gdf, geometry="LINE").set_crs(epsg=epsg)

    # get euclidian distance
    gdf["mLength_euclid"] = hubA.distance(hubB)

    class _Connections:
        def __init__(self, hub):
            """Class to hold information about connections for a given hub"""
            self.hub = hub

            # get list of tuples that describe the connection for this hub
            self.connections = list(filter(lambda x: hub in x, hubs_combinations))

            # number of connections
            self.n = len(self.connections)

            # get the hubs that are not the current hub (destinations)
            self.dests = [x[0] if x[0] != hub else x[1] for x in self.connections]

            self.lengths = self._make_length_dict()

            self.series = hubs_df.loc[hub]

            status = int(self.series["status"])
            if status == 1:
                self.major = 1
                self.minor = 0
            elif status == 0:
                self.major = 0
                self.minor = 0
            elif status == -1:
                self.major = 0
                self.minor = 1
            else:
                raise ValueError(
                    "Status of {} is not specified properly".format(self.hub)
                )

        def _make_length_dict(self):
            """Makes a dictionary of euclidian distances to destinations"""
            # make dictionary that describes euclidian distance to destination
            distances = list(gdf.loc[self.connections]["mLength_euclid"])
            d = {self.dests[i]: distances[i] for i in range(len(distances))}
            # considered sorting for optimization purposes but didn't seem to do anything
            return d

        def connection_with(self, hubB: "_Connections"):
            """Returns the tuple used for indexing connection (since multiindexing requires order)"""
            tuple1 = (self.hub, hubB.hub)
            tuple2 = (hubB.hub, self.hub)

            is_in_both = lambda t: (t in self.connections and t in hubB.connections)

            if is_in_both(tuple1):
                return tuple1
            elif is_in_both(tuple2):
                return tuple2
            else:
                return None

        def get_length(self, hubB: "_Connections"):
            """Returns the length of the connection between self and hubB"""
            return self.lengths[hubB.hub]

        def remove_connection(self, hubB: "_Connections"):
            """Removes the connection between self and hubB"""
            # hubB should be of type _Connections
            # think of self as hubA
            a_str = self.hub
            b_str = hubB.hub

            try:
                self.dests.remove(b_str)

                hubB.dests.remove(a_str)

                connection = self.connection_with(hubB)
                self.connections.remove(connection)
                hubB.connections.remove(connection)

                del self.lengths[b_str]
                del hubB.lengths[a_str]

                self.n = self.n - 1
                hubB.n = hubB.n - 1
            except ValueError:
                print(
                    "Tried to remove connection '{} to {}', but this connection was not created in the first place!".format(
                        a_str, b_str
                    )
                )
                pass

        def has_remaining_valid_connections(self, current_length, length_factor):
            """Returns boolean if has enough remaining valid connections based on length_factor and min_hubs"""
            # returns boolean if has enough remaining valid connections
            # (has a number of connections greater than min_hubs with length less than length_factor times current length)
            return (
                len(
                    [
                        length
                        for length in self.lengths
                        if self.lengths[length] < length_factor * current_length
                    ]
                )
                >= min_hubs
            )

        def get_smallest_length(self):
            """Returns length of smallest connection"""
            return min(self.lengths.values())

    # initialize hub connections
    hub_conn = {hub: _Connections(hub) for hub in hubs}

    # initial trim based on `has_remaining_valid_connections` method
    for _, _hubA in hub_conn.items():
        for _hubB in [hub_conn[hub] for hub in _hubA.lengths.keys()]:
            current_length = _hubA.get_length(_hubB)
            if _hubA.major or _hubB.major:
                lf = major_length_factor
            else:
                lf = regular_length_factor
            if _hubB.has_remaining_valid_connections(
                current_length, lf
            ) and _hubA.has_remaining_valid_connections(current_length, lf):
                _hubA.remove_connection(_hubB)

    # trim minor hubs (only include hubs whose length <= minor_length_factor * length of smallest connection)
    # an alternate method would be to only connect to the n shortest connections
    for _, _hubA in hub_conn.items():
        if _hubA.minor:
            max_length = minor_length_factor * _hubA.get_smallest_length()
            lengths_copy = (
                _hubA.lengths.copy()
            )  # need a copy since deleting items through iterations
            for _hubB, distance in lengths_copy.items():
                if distance > max_length:
                    _hubA.remove_connection(hub_conn[_hubB])

    # remove blacklisted arcs
    [
        hub_conn[_hubA].remove_connection(hub_conn[_hubB])
        for _hubA, _hubB in zip(blacklist_arcs["startHub"], blacklist_arcs["endHub"])
    ]

    valid_connections = []
    [valid_connections.extend(hub_conn[hub].connections) for hub in hub_conn]

    # add arcs from existing arcs and corresponding 'exist_pipeline'
    gdf["exist_pipeline"] = 0
    for _, row in existing_arcs.iterrows():
        hubA_str = row["startHub"]
        hubB_str = row["endHub"]
        _hubA = hub_conn[hubA_str]
        _hubB = hub_conn[hubB_str]

        # get correct indexing used in gdf
        connection = _hubA.connection_with(_hubB)  # returns None if connection DNE
        if connection == None:  # if connection DNE
            c1 = (hubA_str, hubB_str)
            c2 = (hubB_str, hubA_str)
            if c1 in hubs_combinations:
                connection = c1
            elif c2 in hubs_combinations:
                connection = c2
            valid_connections.append(connection)  # add to 'trimmer'

        gdf.at[connection, "exist_pipeline"] = 1

    # make connections unique
    valid_connections = list(set(valid_connections))

    # trim gdf based on valid connections and plot
    gdf_trimmed = gdf.loc[valid_connections]

    # get gdf in latlong coords, turn find road distances and geometries
    gdf_latlong = gdf_trimmed.to_crs(crs=lat_long_crs)
    gdf_latlong[["road_duration", "kmLength_road", "road_geometry"]] = gdf_latlong[
        "LINE"
    ].apply(make_route)
    gdf_roads = (
        gdf_latlong.set_geometry("road_geometry")
        .set_crs(crs=lat_long_crs)
        .to_crs(epsg=epsg)
    )

    # save roads data
    roads_df = gdf_roads.to_crs(crs=lat_long_crs)
    roads_df = pd.DataFrame(roads_df.geometry)
    # roads_df.to_csv(hubs_dir / "roads.csv")

    if create_fig:
        gdf_roads.plot(ax=ax, color="grey", zorder=1)
        geohubs.plot(
            ax=ax,
            color="white",
            marker=".",
            markersize=200,
            edgecolors="black",
            zorder=10,
        )

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])

        # gdf_trimmed.plot(ax=ax, color="grey", marker="*")

        fig.savefig(hubs_dir / "fig.png", transparent=True)

    else:
        fig = None

    # convert to df and format
    df = pd.DataFrame(gdf_roads)
    df["mLength_euclid"] = df["mLength_euclid"] / 1000
    df = df.rename(columns={"mLength_euclid": "kmLength_euclid"})
    df = df.rename_axis(["startHub", "endHub"])

    return {
        "arcs": df[["kmLength_euclid", "kmLength_road", "exist_pipeline"]],
        "roads": roads_df,
        "fig": fig,
    }


def main():
    create_arcs()


if __name__ == "__main__":
    main()
