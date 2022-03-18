"""
Creates plot from outputs of model
Author: Braden Pecora

In the current version, there are next to no features,
but the metadata should be fairly easy to access and utilize.
"""
import geocoder
import geopandas as gpd
import matplotlib.pyplot as plt

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
            dest_latlng = locations[dest]
            line_geodata = {
                'type' : 'Feature',
                'geometry' : {
                    'type': 'LineString',
                    'coordinates': [node_latlng, dest_latlng]
                },
                'properties' : {
                    'name': node + ' to ' + dest
                }
            }
            features.append(line_geodata)

    geo_data = {'type': 'FeatureCollection', 'features' : features}
    distribution = gpd.GeoDataFrame.from_features(geo_data)

    # get Texas plot
    us_county = gpd.read_file(path + 'US_COUNTY_SHPFILE/US_county_cont.shp')
    tx_county = us_county[us_county['STATE_NAME'] == 'Texas']
    tx = tx_county.dissolve()

    # plot
    base = tx.plot(color='white',edgecolor='black')
    distribution.plot(ax=base)
    plt.savefig(path + 'outputs/fig.png')

if __name__ == '__main__':
    from json import load
    data = load(open('outputs/outputs.json'))
    path = ''
    main(data, path)