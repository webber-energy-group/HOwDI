"""
hydrogen model module
takes input csvs and creates the networkx graph object needed to run the pyomo-based hydrogen model
"""

#import
import networkx
import pandas

class hydrogen_network:
    '''
    uses the hydrogen_inputs object to create a networkx directional graph of the hydrogen network
    '''
    def __init__(self, H):
        '''
        H: a hydrogen_inputs object
        '''

        #define the data
        self.nodes_csv = H.nodes
        self.arcs_csv = H.arcs
        self.distributors_csv = H.distributors
        self.demand_csv = H.demand
        self.producers_csv = H.producers
        self.existing_producers_csv = H.producers_existing
        self.converters_csv = H.converters
        self.price_range = H.price_tracking_array
        self.price_hubs = H.price_hubs
        self.price_demand = H.price_demand
        self.find_prices = H.find_prices
        #run the scripts to create and expand the graph
        self.g = self.create_graph(self.nodes_csv, self.arcs_csv, self.distributors_csv)
        self.g = self.add_consumers(self.g, self.nodes_csv, self.demand_csv)  
        self.g = self.add_producers(self.g, self.nodes_csv, self.producers_csv, self.existing_producers_csv)  
        self.g = self.add_converters(self.g, self.nodes_csv, self.converters_csv) 
        self.g = self.add_price_nodes(self.g, self.price_range, self.price_hubs, self.price_demand)
        #self.g = self.add_storage(self.g, self.storage_csv)





    def create_graph(self, node_df, arcs_df, distributors_df):
        '''
        create a directional graph to represent the hydrogen distribution system
        ---
        node_df = a pandas dataframe containing data for the nodes
        arcs_df = a pandas dataframe containing data for the arcs
        distributors_df = a pandas dataframe containing data for the distributors (i.e., the truck technologies)
        '''
        #create the directional graph object
        g = networkx.DiGraph()
        
        #1) create the nodes and associated data for each hub_name
        for num,arow in node_df.iterrows():
            #1.1) add a node for each of the hubs, separating low-purity from high-purity (i.e., fuel cell quality)
            hub_name = arow['node'] #the name of the hub where the production, demand, terminals, etc. are located, e.g., "baytown"
            for purity_type in ['lowPurity', 'highPurity']:
                arow['node'] = '%s_hub_%s'%(hub_name, purity_type)
                arow['class'] = arow['node'].replace('%s_'%hub_name, '') #drop the hub name from the node name
                arow['hub_name'] = hub_name
                g.add_node(arow['node'], **(dict(arow)))
            #1.2) add a node for each distribution type (i.e., pipelines and trucks)
            for d in distributors_df['distributor']:
                #add both low and high purity pipelines
                if d == 'pipeline':
                    for purity_type in ['LowPurity', 'HighPurity']:
                        node_char = {}
                        node_char['node'] = '%s_dist_%s%s'%(hub_name, d, purity_type)
                        node_char['class'] = node_char['node'].replace('%s_'%hub_name, '')
                        node_char['hub_name'] = hub_name
                        g.add_node(node_char['node'], **(node_char))
                #trucks are assumed to be high purity
                else:
                    node_char = {}
                    node_char['node'] = '%s_dist_%s'%(hub_name, d)
                    node_char['class'] = node_char['node'].replace('%s_'%hub_name, '')
                    node_char['hub_name'] = hub_name
                    g.add_node(node_char['node'], **(node_char))           
            #1.3) add a node for each demand type
            for demand_type in ['lowPurity', 'highPurity', 'fuelStation']:
                node_char = {}
                node_char['node'] = '%s_demand_%s'%(hub_name, demand_type)
                node_char['class'] = node_char['node'].replace('%s_'%hub_name, '')
                node_char['hub_name'] = hub_name
                g.add_node(node_char['node'], **(node_char))    
            
            #2) connect the hub nodes, distribution nodes, and demand nodes
            #2.1) the connection of hub node to pipeline distribution hub is a free arc with unlimited flow--it simply allows the model to flow hydrogen within the hub
            connection_char = {'kmLength': 0.0,
                               'capital_usdPerUnit': 0.0,
                               'fixed_usdPerUnitPerDay': 0.0,
                               'variable_usdPerTon': 0.0,
                               'flowLimit_tonsPerDay': 99999999.9,
                               'class': 'flow_within_hub'}
            g.add_edge('%s_hub_lowPurity'%hub_name, '%s_dist_pipelineLowPurity'%hub_name, **(connection_char)) 
            g.add_edge('%s_hub_highPurity'%hub_name, '%s_dist_pipelineHighPurity'%hub_name, **(connection_char)) 


            # bsp:, allows for h2 to be distributed through a pipeline and then converted
            connection_char = {'kmLength': 0.0,
                               'capital_usdPerUnit': 0.0,
                               'fixed_usdPerUnitPerDay': 0.0,
                               'variable_usdPerTon': 0.0,
                               'flowLimit_tonsPerDay': 99999999.9,
                               'class': 'reverse_flow_within_hub'}
            g.add_edge('%s_dist_pipelineLowPurity'%hub_name, '%s_hub_lowPurity'%hub_name, **(connection_char)) 
            g.add_edge('%s_dist_pipelineHighPurity'%hub_name, '%s_hub_highPurity'%hub_name, **(connection_char)) 
            
            #2.2) the connection of hub node to truck distribution hub incorporates the capital and fixed cost of the trucks--it represents the trucking fleet that is based out of that hub. The truck fleet size ultimately limits the amount of hydrogen that can flow from the hub node to the truck distribution hub.   
            for truck_type in list(distributors_df[distributors_df['distributor'].str.contains('truck')]['distributor']):
                            #costs and flow limits, (note the the unit for trucks is an individual truck, as compared to km for pipelines--i.e., when the model builds 1 truck unit, it is building 1 truck, but when it builds 1 pipeline unit, it is building 1km of pipeline. However, truck variable costs are in terms of km. This is why we separate the truck capital and fixed costs onto this arc, and the variable costs onto the arcs that go from one hub to another.)
                            capital_usdPerUnit = distributors_df[distributors_df['distributor']==truck_type]['capital_usdPerUnit'].iloc[0]
                            fixed_usdPerUnitPerDay = distributors_df[distributors_df['distributor']==truck_type]['fixed_usdPerUnitPerDay'].iloc[0]
                            flowLimit_tonsPerDay = distributors_df[distributors_df['distributor']==truck_type]['flowLimit_tonsPerDay'].iloc[0]
                            depot_char = {'startNode': '%s_hub_highPurity'%hub_name,
                                          'endNode': '%s_dist_%s'%(hub_name, truck_type),
                                          'kmLength': 0.0,
                                          'capital_usdPerUnit': capital_usdPerUnit,
                                          'fixed_usdPerUnitPerDay': fixed_usdPerUnitPerDay,
                                          'variable_usdPerTon': 0.0,
                                          'flowLimit_tonsPerDay': flowLimit_tonsPerDay,
                                          'class': 'hub_depot_%s'%truck_type}
                            g.add_edge(depot_char['startNode'], depot_char['endNode'], **(depot_char)) 
            #2.3) the connection of distribution hub nodes to demand nodes is a free arc with unlimited flow--it simply allows the model to flow hydrogen within the hub
            connection_char = {'kmLength': 0.0,
                               'capital_usdPerUnit': 0.0,
                               'fixed_usdPerUnitPerDay': 0.0,
                               'variable_usdPerTon': 0.0,
                               'flowLimit_tonsPerDay': 99999999.9,
                               'class': 'flow_to_demand_node'}
            #demand_fuelStation requires high purity hydrogen
            g.add_edge('%s_dist_pipelineHighPurity'%hub_name, '%s_demand_fuelStation'%hub_name, **(connection_char)) 
            g.add_edge('%s_dist_truckCompressed'%hub_name, '%s_demand_fuelStation'%hub_name, **(connection_char)) 
            g.add_edge('%s_dist_truckLiquefied'%hub_name, '%s_demand_fuelStation'%hub_name, **(connection_char)) 
            #demand_highPurity requires high purity hydrogen
            g.add_edge('%s_dist_pipelineHighPurity'%hub_name, '%s_demand_highPurity'%hub_name, **(connection_char)) 
            g.add_edge('%s_dist_truckCompressed'%hub_name, '%s_demand_highPurity'%hub_name, **(connection_char)) 
            g.add_edge('%s_dist_truckLiquefied'%hub_name, '%s_demand_highPurity'%hub_name, **(connection_char))
            #demand_lowPurity can use low or high purity hydrogen
            g.add_edge('%s_dist_pipelineLowPurity'%hub_name, '%s_demand_lowPurity'%hub_name, **(connection_char)) 
            g.add_edge('%s_dist_pipelineHighPurity'%hub_name, '%s_demand_lowPurity'%hub_name, **(connection_char)) 
            g.add_edge('%s_dist_truckCompressed'%hub_name, '%s_demand_lowPurity'%hub_name, **(connection_char)) 
            g.add_edge('%s_dist_truckLiquefied'%hub_name, '%s_demand_lowPurity'%hub_name, **(connection_char))
            #2.4) connect the hub_lowPurity to the hub_highPurity. We will add a purifier between the two using the add_converters function
            connection_char = {'kmLength': 0.0,
                               'capital_usdPerUnit': 0.0,
                               'fixed_usdPerUnitPerDay': 0.0,
                               'variable_usdPerTon': 0.0,
                               'flowLimit_tonsPerDay': 99999999.9,
                               'class': 'flow_through_purifier'}
            #demand_fuelStation requires high purity hydrogen
            g.add_edge('%s_hub_lowPurity'%hub_name, '%s_hub_highPurity'%hub_name, **(connection_char)) 
                
        #3) create the arcs and associated data that connect hub_names to each other (e.g., baytown to montBelvieu): i.e., add pipelines and truck routes between connected hub_names
        for num,arow in arcs_df.iterrows():
            arow_dict = dict(arow)
            
            pipeline_length = arow['kmLength_road'] #TODO adjust this value, `arow['kmLength_euclid]` is the straight line distance
            road_length = arow['kmLength_road']
            #for each low purity and high purity distribution hub
            for purity_type in ['LowPurity', 'HighPurity']:
                #2.1) add a pipeline going in each direction to allow bi-directional flow
                #if it's an existing pipeline, we assume it's a low purity pipeline
                if purity_type=='HighPurity':
                    arow['exist_pipeline'] = 0
                for arc in [(arow_dict['startNode'], arow_dict['endNode']), 
                            (arow_dict['endNode'], arow_dict['startNode'])]:  
                    pipeline_char = {'startNode': arc[0]+'_dist_pipeline%s'%purity_type,
                                     'endNode': arc[1]+'_dist_pipeline%s'%purity_type,
                                     # alternate way of connecting nodes, remove the second half of 2.1 if this is used
                                     #'endNode': arc[1]+'_hub_%s'%(purity_type[0].lower()+purity_type[1:]), #lowercase for the first letter of purity type
                                     'kmLength': pipeline_length,
                                     'capital_usdPerUnit': distributors_df[distributors_df['distributor']=='pipeline']['capital_usdPerUnit'].iloc[0]*pipeline_length,
                                     'fixed_usdPerUnitPerDay': distributors_df[distributors_df['distributor']=='pipeline']['fixed_usdPerUnitPerDay'].iloc[0]*pipeline_length,
                                     'variable_usdPerTon': distributors_df[distributors_df['distributor']=='pipeline']['variable_usdPerKilometer-Ton'].iloc[0]*pipeline_length,
                                     'flowLimit_tonsPerDay': distributors_df[distributors_df['distributor']=='pipeline']['flowLimit_tonsPerDay'].iloc[0],
                                     'class': 'arc_pipeline%s'%purity_type,
                                     'existing': arow['exist_pipeline']}
                    #add the edge to the graph
                    g.add_edge(pipeline_char['startNode'], pipeline_char['endNode'], **(pipeline_char)) 
        
                    #2.2) add truck routes and their variable costs, note that that the capital and fixed costs of the trucks are stored on the (hubName_hub_highPurity, hubName_dist_truckType) arcs
                    if purity_type == 'HighPurity':
                        for truck_type in list(distributors_df[distributors_df['distributor'].str.contains('truck')]['distributor']):
                            #information for the trucking routes between hydrogen hubs
                            truck_route_dict = {'startNode': arc[0]+'_dist_%s'%truck_type,
                                          'endNode': arc[1]+'_dist_%s'%truck_type,
                                          'kmLength': road_length,
                                          'capital_usdPerUnit': 0.0,
                                          'fixed_usdPerUnitPerDay': 0.0,
                                          'variable_usdPerTon': distributors_df[distributors_df['distributor']==truck_type]['variable_usdPerKilometer-Ton'].iloc[0]*road_length,
                                          'class': 'arc_%s'%truck_type}
                            #add the distribution arc for the truck
                            g.add_edge(truck_route_dict['startNode'], truck_route_dict['endNode'], **(truck_route_dict)) 
        
        #4) clean up and return
        #add startNode and endNode to any edges that don't have them
        edges_without_startNode = [s for s in list(g.edges) if 'startNode' not in g.edges[s]]
        for e in edges_without_startNode:
            g.edges[e]['startNode'] = e[0]
            g.edges[e]['endNode'] = e[1]
        #return
        return g
    
    
    
    def add_consumers(self, g, node_df, demand_df):
        '''
        add consumers to the graph
        for each hub, there are arcs from the nodes that represent demand type (e.g., fuelStation, lowPurity, highPurity) to the nodes that represent different demand sectors (e.g., industrialFuel, transportationFuel). In practice, one could create multiple sectors that connect to the same demand type (e.g., long-haul HDV, regional MDV, and LDV all connecting to a fuel station)
        ---
        g = a graph object created using networkx and the create_graph function
        node_df = a pandas dataframe containing data for the nodes
        demand_df = a pandas dataframe containing data for the demand sectors
        '''
        #loop through the hubs, add a node for each demand, and connect it to the appropriate demand hub
        #loop through the hub names, add a network node for each type of demand, and add a network arc connecting that demand to the appropriate demand hub
        for num,arow in node_df.iterrows():
            hub_name = arow['node']
            for demand_sector in demand_df['sector']:
                #add the demandSector nodes
                if arow['%s_tonnesperday'%demand_sector]==0:
                    pass
                else:
                    #1) create a carbon sensitive and a carbon indifferent version of the demandSector based on the 0--1 fraction value of the "carbonSensitiveFraction" in the csv file.
                    #1.1) create the carbon indifferent version
                    #1.1.a) build the node dictionary
                    #initilize with a dictionary object equal to the matching row of the demand_df dataframe (the demand.csv file)
                    demand_node_char = (demand_df[demand_df['sector']==demand_sector].iloc[0]).to_dict() 
                    demand_node_char['node'] = '%s_demandSector_%s'%(hub_name, demand_sector)
                    demand_node_char['class'] = demand_node_char['node'].replace('%s_'%hub_name, '')
                    demand_node_char['size'] = arow['%s_tonnesperday'%demand_sector] * (1 - demand_node_char['carbonSensitiveFraction'])
                    demand_node_char['carbonSensitive'] = 0
                    demand_node_char['hub_name'] = hub_name
                    #1.1.b) build the arc dictionary
                    demand_arc_char = {'kmLength': 0.0,
                                       'capital_usdPerUnit': 0.0,
                                       'fixed_usdPerUnitPerDay': 0.0,
                                       'variable_usdPerTon': 0.0,
                                       'flowLimit_tonsPerDay': 99999999.9,
                                       'class': 'flow_to_demand_sector'}
                    #1.2) create the carbon sensitive version
                    #1.2.a) build the node dictionary
                    #start with the dictionary from the carbon indifferent version
                    demand_node_char_carbon = demand_node_char.copy()
                    #update the characteristics as needed
                    demand_node_char_carbon['node'] = '%s_demandSector_%s_carbonSensitive'%(hub_name, demand_sector)
                    demand_node_char_carbon['size'] = arow['%s_tonnesperday'%demand_sector] * (demand_node_char_carbon['carbonSensitiveFraction'])
                    demand_node_char_carbon['carbonSensitive'] = 1
                    #1.2.b) build the arc dictionary
                    #start with the dictionary from the carbon indifferent version
                    demand_arc_char_carbon = demand_arc_char.copy()
                    #update the characteristics as needed
                    #...in this case, the arc dictionaries are the same, but leaving this here for future versions where they might differ
                    #2) connect the demandSector nodes to the demand nodes
                    #query the demandType to know which demand node to connect to (lowPurity, highPurity, or fuelStation)
                    demandType = demand_df[demand_df['sector']==demand_sector]['demandType'].iloc[0]
                    #add the nodes and arcs to the graph
                    #carbon indifferent
                    g.add_node(demand_node_char['node'], **(demand_node_char))
                    g.add_edge('%s_demand_%s'%(hub_name, demandType), demand_node_char['node'], **(demand_arc_char)) 
                    #carbon sensitive
                    g.add_node(demand_node_char_carbon['node'], **(demand_node_char_carbon))
                    g.add_edge('%s_demand_%s'%(hub_name, demandType), demand_node_char_carbon['node'], **(demand_arc_char_carbon)) 
        return g

    
    
    def add_producers(self, g, node_df, producers_df, existing_producers_df):
        '''
        add producers to the graph
        each producer is a node that send hydrogen to a hub_lowPurity or hub_highPurity node
        ---
        g = a graph object created using networkx and the create_graph function
        node_df = a pandas dataframe containing data for the nodes
        producers_df = a pandas dataframe containing data for the producers
        existing_producers_df = comes from production_existing.csv
        '''
        #loop through the nodes and producers to add the necessary nodes and arcs
        for ni,nrow in node_df.iterrows():
            for pi,prow in producers_df.iterrows():
                #if the node is unable to build that producer type, pass
                if nrow['build_%s'%prow['type']] == 0:
                    pass
                else:
                    #add node
                    prow['node'] = '%s_production_%s'%(nrow['node'], prow['type'])
                    prow['class'] = 'producer'
                    prow['existing'] = 0
                    prow['hub_name'] = nrow['node']
                    g.add_node(prow['node'], **(dict(prow)))
                    #add edge
                    production_purity = prow['purity']
                    edge_dict = {'startNode':prow['node'], 
                                 'endNode':'%s_hub_%sPurity'%(nrow['node'], production_purity), 
                                 'kmLength':0.0, 
                                 'capital_usdPerUnit':0.0, 
                                 'class':'flow_from_producer'}
                    g.add_edge(prow['node'], '%s_hub_%sPurity'%(nrow['node'], production_purity), **(edge_dict))
        #loop through the existing producers and add them       
        for pi,prow in existing_producers_df.iterrows(): 
            pass
            hub_name = prow['hub_name']
            prow['node'] = '%s_production_%sExisting'%(hub_name, prow['type'])
            prow['class'] = 'producer'
            prow['existing'] = 1
            g.add_node(prow['node'], **(dict(prow)))
            #add edge
            production_purity = producers_df[producers_df['type']==prow['type']]['purity'].iloc[0]
            edge_dict = {'startNode':prow['node'], 
                         'endNode':'%s_hub_%sPurity'%(hub_name, production_purity), 
                         'kmLength':0.0, 
                         'capital_usdPerUnit':0.0, 
                         'class':'flow_from_producer'}
            g.add_edge(prow['node'], '%s_hub_%sPurity'%(hub_name, production_purity), **(edge_dict))
        return g

    
    
    def add_converters(self, g, node_df, converters_df):
        '''
        add converters to the graph
        each converter is a node and arc that splits an existing arc into two
        ---
        g = a graph object created using networkx and the create_graph function
        node_df = a pandas dataframe containing data for the nodes
        converters_df = a pandas dataframe containing data for the converters
        '''
        #loop through the nodes and converters to add the necessary nodes and arcs   
        for cvi,cvrow in converters_df.iterrows():  
            if cvrow['arc_start_class'] == 'pass':
                    pass
            else:               
                for n in list(g.nodes):
                    nrow = pandas.Series(g.nodes[n])
                    if g.nodes[nrow['node']]['class'] != cvrow['arc_start_class']:
                        pass
                    else:    
                        #add a new node for the converter at the hub
                        hub_name = nrow['hub_name'] 
                        cvrow['hub_name'] = hub_name
                        cvrow['node'] = hub_name + '_converter_' + str(cvrow['converter'])
                        cvrow['class'] = cvrow['node'].replace('%s_'%hub_name, '')          
                        g.add_node(cvrow['node'], **(dict(cvrow)))
                        #grab the tuples of any edges that have the correct arc_end type--i.e., any edges where the start_node is equal to the node we are working on in our for loop, and where the end_node has a class equal to the "arc_end_class" parameter in converters_df           
                        change_edges_list = [s for s in list(g.edges) if ((nrow['node']==s[0]) & (cvrow['arc_end_class'] == g.nodes[s[1]]['class']))]
                        #loop through the tuples and add a new node and arc to each
                        for ce in change_edges_list:
                            g.add_edge(g.edges[ce]['startNode'], cvrow['node'], **{'startNode':g.edges[ce]['startNode'],
                                                                                   'endNode':cvrow['node'],
                                                                                   'kmLength':0.0,
                                                                                   'class':cvrow['class']})
                            #change the original arc's start node to the new conversion node
                            g.add_edge(cvrow['node'], g.edges[ce]['endNode'], **g.edges[ce])
                            g.edges[(cvrow['node'], g.edges[ce]['endNode'])]['startNode'] = cvrow['node']
                            g.remove_edge(*ce)
        return g



    def add_price_nodes(self, g, price_range, price_hubs, total_hub_demand_tons):
            '''
            add price nodes to the graph
            each price is a node that has very little demand and series of breakeven price points to help us estimate the price that customers are paying for hydrogen at that node.
            ---
            g = a graph object created using networkx and the create_graph function
            price_range is a iterable array of prices. The model will use this array of discrete prices as fake consumers. In the solution, the price of hydrogen at that node is between the most expensive "price consumer" who does not use hydrogen and the least expensive "price consumer" who does.
            price_hubs is a list of the hubs where we want to calculate prices for. if it equals 'all' then all of the hubs will be priced
            total_hub_demand_tons is the total amount of pricing demand at each hub. this can be set to a higher value if you are trying to just test sensitivity to amount of demand
            '''                       
            if not self.find_prices:
                return g
            else:
                if price_hubs=='all':
                    price_hubs = set([s[1] for s in list(g.nodes(data="hub_name"))])
                for ph in price_hubs:
                    #add nodes to store pricing information
                    for p in price_range:
                        #1) fuelStation prices
                        price_node_dict = {'node': ph + '_priceFuelStation_%f'%p,
                                           'sector': 'price',
                                           'hub_name': ph, 
                                           'breakevenPrice': p*1000,
                                           'size': total_hub_demand_tons,
                                           'carbonSensitiveFraction': 0,
                                           'breakevenCarbon_g_MJ': 0,
                                           'demandType': 'fuelStation',
                                           'class': 'price'}
                        g.add_node(price_node_dict['node'], **price_node_dict)
                        #add the accompanying edge
                        price_edge_dict = {'startNode': ph + '_demand_fuelStation',
                                          'endNode': price_node_dict['node'],
                                          'kmLength': 0.0,
                                          'capital_usdPerUnit': 0.0}
                        g.add_edge(price_edge_dict['startNode'], price_edge_dict['endNode'], **price_edge_dict)    
                return g
                    




#%%

# =============================================================================
# test = [s for s in list(g.edges) if (('storage_flow' in  g.edges[s].keys()))]
# test = [s for s in test if ((g.edges[s]['storage_flow']=='gas'))]
# 
# test = pandas.DataFrame([s for s in list(g.edges)]).to_clipboard()
# 
# test = pandas.DataFrame([g.nodes[s]['class'] for s in list(g.nodes)])
# test.to_clipboard()
# 
# 
# test = []
# for s in list(g.nodes):
#     print (s)
#     print (g.nodes[s])
#     print ('***')
# =============================================================================


                    
