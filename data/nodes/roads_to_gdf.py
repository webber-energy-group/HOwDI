"""
Author: Braden Pecora

Converts roads.csv into a GeoDataFrame object

This is necessary since .geojson files can not handle LineStrings with multiple points.
Road geodata are stored as csv, where the geodata are stored as literal strings.
The shapely.wkt function "loads" can interpret this literal string and convert into a LineString object
"""
from shapely.wkt import loads
import geopandas as gpd

def roads_to_gdf(wd=''):
    #wd is path to this current directory, '/nodes'

    # get nodes for crs
    nodes = gpd.read_file(wd+'nodes.geojson')

    # read csv and convert geometry column
    roads = gpd.read_file(wd+'roads.csv')
    roads['geometry'] = roads['road_geometry'].apply(loads) # convert string into Linestring
    roads = roads.set_crs(nodes.crs)
    del roads['road_geometry']

    return roads

if __name__ == "__main__":
    roads = roads_to_gdf()
    print(roads)