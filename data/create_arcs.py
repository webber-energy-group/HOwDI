# https://github.com/Project-OSRM/osrm-backend/blob/master/docs/http.md#trip-service
# https://2.python-requests.org/en/master/user/advanced/#session-objects
import pandas as pd
import geopandas as gpd
import itertools
from shapely.geometry import LineString
import matplotlib.pyplot as plt
import requests
import json

s = requests.Session() # improve performance over API calls

# def sort_dict(d:dict) -> dict:
#     return dict(sorted(d.items(), key=lambda x:x[1]))

class Node:
    """Used in make_route function"""
    def __init__(self, coords):
        self.x = coords[0]
        self.y = coords[1]
    def __str__(self):
        return "{},{}".format(self.x,self.y)

def get_route(nodeA, nodeB):
    url = "http://router.project-osrm.org/route/v1/driving/{};{}?geometries=geojson".format(nodeA,nodeB)
    r = s.get(url)
    return json.loads(r.text)['routes'][0]
    
def make_route(row):
    line = list(row.coords)
    nodeA = Node(line[0])
    nodeB = Node(line[1])

    route = get_route(nodeA,nodeB)
    road_geometry = LineString(route['geometry']['coordinates'])
    km_distance = route['distance']/1000
    duration = route['duration']

    return pd.Series([duration,km_distance,road_geometry])

def main():
    # read files and establish parameters
    current_dir = ''
    
    nodes_df = pd.read_csv(current_dir+'nodes/nodes.csv').set_index('node')
    nodes_df = nodes_df.sort_values(by=['minor'],ascending=False) # sort by minor; important for indexing direction
    nodes = nodes_df.index.tolist()

    epsg=3082
    geonodes=gpd.read_file(current_dir+'nodes/nodes.geojson')
    lat_long_crs = geonodes.crs
    geonodes = geonodes.set_index('node')
    geonodes = geonodes.to_crs(epsg=epsg)

    existing_arcs = pd.read_csv(current_dir+'nodes/existing_arcs.csv')

    # length factors (lf) are effective reach
    # length factor > 1, restricts max distance to min*lf
    # length factor < 1, loosens max distance to min*lf (in short)
    minor_length_factor = 5
    major_length_factor = 0.8
    regular_length_factor = 0.9

    # minimum number of connections for each node
    min_nodes = 3 # 4 is not bad either

    # Initialize Figure with Texas base
    fig, ax = plt.subplots(figsize=(10,10),dpi=300)
    us_county = gpd.read_file(current_dir+'US_COUNTY_SHPFILE/US_county_cont.shp')
    tx_county = us_county[us_county['STATE_NAME'] == 'Texas']
    tx = tx_county.dissolve().to_crs(epsg=epsg)
    tx.plot(ax=ax,color='white',edgecolor='black')

    # get all possible combinations of size 2, output is list of tuples turned into a multiindex
    nodes_combinations = list(itertools.combinations(nodes,2))
    index = pd.MultiIndex.from_tuples(nodes_combinations,names=['nodeA','nodeB'])
    gdf = gpd.GeoDataFrame(index=index)

    nodeA = gdf.join(geonodes.rename_axis('nodeA'))
    nodeB = gdf.join(geonodes.rename_axis('nodeB'))

    # create line from nodeA to nodeB (for plotting purposes)
    gdf['LINE'] = [LineString([(a.x, a.y),(b.x, b.y)])for (a,b) in zip(nodeA.geometry, nodeB.geometry)]
    gdf = gpd.GeoDataFrame(gdf, geometry='LINE').set_crs(epsg=epsg)

    # get euclidian distance
    gdf['mLength_euclid'] = nodeA.distance(nodeB) 

    class _Connections:
        def __init__(self, node):
            self.node = node

            # get list of tuples that describe the connection for this node
            self.connections = list(filter(lambda x:node in x, nodes_combinations))
            
            # number of connections
            self.n = len(self.connections)

            # get the nodes that are not the current node (destinations)
            self.dests = [x[0] if x[0] != node else x[1] for x in self.connections]

            self.lengths = self._make_length_dict()

            self.series = nodes_df.loc[node]
            self.major = self.series['major']
            self.minor = self.series['minor']

        def _make_length_dict(self):
            # make dictionary that describes euclidian distance to destination
            distances = list(gdf.loc[self.connections]['mLength_euclid'])
            d = {self.dests[i] : distances[i] for i in range(len(distances))}
            # considered sorting for optimization purposes but didn't seem to do anything 
            return d

        def connection_with(self, nodeB):
            """Returns the tuple used for indexing connection (since multiindexing requires order)"""
            tuple1 = (self.node, nodeB.node)
            tuple2 = (nodeB.node, self.node)

            is_in_both = lambda t: (t in self.connections and t in nodeB.connections)

            if is_in_both(tuple1):
                return tuple1
            elif is_in_both(tuple2):
                return tuple2
            else:
                return None

        def get_length(self, nodeB):
            # nodeB is a _Connections object (can do typing but pylance gets mad)
            return self.lengths[nodeB.node]
        def remove_connection(self, nodeB):
            # nodeB should be of type _Connections
            # think of self as nodeA
            a_str = self.node
            b_str = nodeB.node

            self.dests.remove(b_str)
            nodeB.dests.remove(a_str)

            connection = self.connection_with(nodeB)
            self.connections.remove(connection)
            nodeB.connections.remove(connection)

            del self.lengths[b_str]
            del nodeB.lengths[a_str]

            self.n = self.n - 1
            nodeB.n = nodeB.n - 1

        def has_remaining_valid_connections(self, current_length, length_factor):
            # returns boolean if has enough remaining valid connections
            # (has a number of connections greater than min_nodes with length less than length_factor times current length)
            return len([length for length in self.lengths if self.lengths[length] < length_factor*current_length]) >= min_nodes

        def get_smallest_length(self):
            """Returns length of smallest connection"""
            return min(self.lengths.values())
            

    # initialize nodal connections
    nodal_c = {node: _Connections(node) for node in nodes} 

    # initial trim based on `has_remaining_valid_connections` method
    for _, _nodeA in nodal_c.items():
        for _nodeB in [nodal_c[node] for node in _nodeA.lengths.keys()]:
            current_length = _nodeA.get_length(_nodeB)
            if _nodeA.major or _nodeB.major:
                lf= major_length_factor
            else:
                lf = regular_length_factor
            if _nodeB.has_remaining_valid_connections(current_length, lf) and _nodeA.has_remaining_valid_connections(current_length, lf):
                _nodeA.remove_connection(_nodeB)

    # trim minor nodes (only include nodes whose length <= minor_length_factor * length of smallest connection)
    # an alternate method would be to only connect to the n shortest connections
    for _, _nodeA in nodal_c.items():
        if _nodeA.minor:
            max_length = minor_length_factor*_nodeA.get_smallest_length()
            lengths_copy = _nodeA.lengths.copy() # need a copy since deleting items through iterations
            for _nodeB, distance in lengths_copy.items():
                if distance > max_length:
                    _nodeA.remove_connection(nodal_c[_nodeB])

    valid_connections = []
    [valid_connections.extend(nodal_c[node].connections) for node in nodal_c]
    
    # add arcs from existing arcs and correspoindg 'exist_pipeline'
    gdf['exist_pipeline'] = 0
    for _, row in existing_arcs.iterrows():
        nodeA_str = row['startNode']
        nodeB_str = row['endNode']
        _nodeA = nodal_c[nodeA_str]
        _nodeB = nodal_c[nodeB_str]
        
        # get correct indexing used in gdf
        connection = _nodeA.connection_with(_nodeB) # returns None if connection DNE
        if connection == None: # if connection DNE
            c1 = (nodeA_str,nodeB_str)
            c2 = (nodeB_str,nodeA_str)
            if c1 in nodes_combinations:
                connection = c1
            elif c2 in nodes_combinations:
                connection = c2
            valid_connections.append(connection) #add to 'trimmer'

        gdf.at[connection,'exist_pipeline'] = 1
    
    # make connections unique
    valid_connections = list(set(valid_connections))

    # trim gdf based on valid connections and plot
    gdf_trimmed = gdf.loc[valid_connections]

    # get gdf in latlong coords, turn find road distances and geometries
    gdf_latlong = gdf_trimmed.to_crs(crs=lat_long_crs)
    gdf_latlong[['road_duration','kmLength_road','road_geometry']] = gdf_latlong['LINE'].apply(make_route)
    gdf_roads = gdf_latlong.set_geometry('road_geometry').to_crs(epsg=epsg)

    # save roads data
    roads_df = gdf_roads.to_crs(crs=lat_long_crs)
    roads_df = pd.DataFrame(roads_df.geometry)
    roads_df.to_csv('nodes/roads.csv')

    gdf_trimmed.plot(ax=ax,color='grey')
    gdf_roads.plot(ax=ax)
    fig.savefig('nodes/fig.png')

    # convert to df and format
    df = pd.DataFrame(gdf_roads)
    df['mLength_euclid'] = df['mLength_euclid']/1000
    df = df.rename(columns={'mLength_euclid':'kmLength_euclid'})
    df = df.rename_axis(['startNode','endNode'])

    return df[['kmLength_euclid','kmLength_road','exist_pipeline']]

if __name__ == '__main__':
    df = main()
    df.to_csv('base/inputs/texas_arcs.csv')