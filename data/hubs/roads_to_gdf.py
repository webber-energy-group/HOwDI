"""
Author: Braden Pecora

Converts roads.csv into a GeoDataFrame object

This is necessary since .geojson files can not handle LineStrings with multiple points.
Road geodata are stored as csv, where the geodata are stored as literal strings.
The shapely.wkt function "loads" can interpret this literal string and convert into a LineString object
"""
import geopandas as gpd
from shapely.wkt import loads


def roads_to_gdf(wd):
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


if __name__ == "__main__":
    from pathlib import Path

    roads = roads_to_gdf(Path("."))
    print(roads)
