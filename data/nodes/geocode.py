import pandas as pd
import geopandas as gpd
import geopy # necessary installation, unnecessary import

def main(file):
    """Generates a GeoJSON file from geocoded locations of nodes (detailed nodes.csv)"""
    nodes = pd.read_csv(file)['node'].tolist()
    geonodes = gpd.tools.geocode([node + ' Texas' for node in nodes], provider='arcgis').set_index(pd.Series(nodes,name='node'))
    geonodes.to_file('nodes.geojson',driver='GeoJSON')

if __name__ == '__main__':
    main('nodes.csv')