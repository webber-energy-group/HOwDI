"""
Creates plot from outputs of model
Author: Braden Pecora

In the current version, there are next to no features,
but the metadata should be fairly easy to access and utilize.
"""
import geocoder
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import json

## for development 
#data = json.load(open('outputs/outputs.json'))
#path='data/'

def main(data, path='data/'):
    
    # it seems that geopandas has a built in geocoder, but this was the first thing that worked
    # maybe its worth changing eventually...
    locations = {node: geocoder.arcgis(node + ' Texas').latlng for node in data.keys()} # takes ~ 30 seconds
    for _, latlong in locations.items():
        latlong.reverse() # is in opposite order of how geopandas will interpret 
    
    # clean data
    def get_relevant_data(nodal_data):
        outgoing_dicts = nodal_data['distribution']['outgoing']
        relevant_keys = ['source_class','destination','destination_class']
        for _, outgoing_dict in outgoing_dicts.items():
            for key in list(outgoing_dict.keys()):
                if key not in relevant_keys:
                    del outgoing_dict[key]
        return [outgoing_dict for _, outgoing_dict in outgoing_dicts.items()]
    clean_data = {node: get_relevant_data(nodal_data) for node, nodal_data in data.items() if nodal_data['distribution'] != {"local": {},"outgoing": {},"incoming": {} }}

    features = []
    for node, nodal_connections in clean_data.items():
        node_latlng = locations[node]
        node_geodata = {
            'type' : 'Feature',
            'geometry' : {
                'type' : 'Point',
                'coordinates' : node_latlng
            },
            'properties' : {
                'name' : node
            }
        }
        features.append(node_geodata)

        for nodal_connection in nodal_connections:

            dest = nodal_connection['destination']
            dist_type = nodal_connection['source_class']
            dest_latlng = locations[dest]

            line_geodata = {
                'type' : 'Feature',
                'geometry' : {
                    'type': 'LineString',
                    'coordinates': [node_latlng, dest_latlng]
                },
                'properties' : {
                    'name': node + ' to ' + dest,
                    'dist_type': dist_type
                }
            }
            features.append(line_geodata)

    geo_data = {'type': 'FeatureCollection', 'features' : features}
    distribution = gpd.GeoDataFrame.from_features(geo_data)

    # get Texas plot
    us_county = gpd.read_file(path + 'US_COUNTY_SHPFILE/US_county_cont.shp')
    # us_county = gpd.read_file('US_COUNTY_SHPFILE/US_county_cont.shp')
    tx_county = us_county[us_county['STATE_NAME'] == 'Texas']
    tx = tx_county.dissolve()

    nodes = distribution[distribution.type == 'Point']
    connections = distribution[distribution.type == 'LineString']

    # plot
    node_color = '#219ebc'
    dist_pipelineLowPurity_col = '#9b2226'
    dist_truckLiquefied_color = '#fb8500'
    dist_truckCompressed_color = '#bb3e03'

    base = tx.plot(color='white',edgecolor='black')
    nodes.plot(ax=base, color = node_color)
    connections[connections['dist_type'] == 'dist_pipelineLowPurity'].plot(ax=base, color = dist_pipelineLowPurity_col)
    connections[connections['dist_type'] == 'dist_truckLiquefied'].plot(ax=base, color = dist_truckLiquefied_color)
    connections[connections['dist_type'] == 'dist_truckCompressed'].plot(ax=base, color = dist_truckCompressed_color, legend=True)

    legend_elements = [Line2D([0], [0], color=dist_pipelineLowPurity_col, lw=2, label='Gas Pipeline'), 
    Line2D([0], [0], color=dist_truckLiquefied_color, lw=2, label='Liquid Truck Route'), 
    Line2D([0], [0], color=dist_truckCompressed_color, lw=2, label='Gas Truck Route'),
    Line2D([0], [0], marker='o', color=node_color, label='Node', markerfacecolor=node_color, markersize=5, lw=0)]

    base.legend(handles=legend_elements, loc='upper left')


    plt.savefig(path + 'outputs/fig.png')

if __name__ == '__main__':
    from json import load
    data = load(open('outputs/outputs.json'))
    path = ''
    main(data, path)