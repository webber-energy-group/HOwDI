'''
H2@Scale Hydrogen Economy Model
version: 1.1
last updated: March 16, 2021
Thomas Deetjen

v1.1
improved the inclusion of fixed and capital costs of production and distribution in the model

v1.2
added carbon by including the variable "hydrogen black", which is a commodity that is tied to the CO2 emissions of hydrogen. When a consumer is carbon-sensitive, it must purchase hydrogen black in addition to hydrogen. The cost of hydrogen black depends on the producers' carbon emissions rate and the carbon price. The utility of buying carbon black depends on the consumers' breakeven carbon emissions rate and the carbon price.

v1.3
added carbon capture and sequestration

v1.4
added trucks (compressed H2 and liquefied H2) to the distribution methods

v1.5
Added the discretize_demand module to create consumers for each node
Updated distribution fixed costs to PerDay
Updated costs so that only capital is divided by 365 (to convert to daily). All other inputs are already in terms of daily cost--but capital cost input data is in overnight costs, so it needs to be amortized and then converted into a daily cos. Therefore--the model is now in terms of a daily viewpoint--i.e., the solution shows daily production, daily consumption, daily cost, daily emissions
Changed carbon inputs from tonsCO2/tonsH2 to gCO2/MJ, which translates better across fuel types. The model itself still operates in terms of tonsCO2/tonsH2
Added liquefaction, compression converters to get hydrogen to trucks
Created the hydrogen_inputs class to store and pass around the input data

v1.6
Improved the output reporting
Fixed an error in create_graph where it was creating duplicates of consumer nodes with the wrong values (it was doing a for over nodes, but not filtering by nodes: i.e., I had to add "(consumers_df['node']==nrow['node'])" to the "for ci,crow" loop)
Added tracking for co2 emissions
Added existing pipelines, nodes, demand, and production

v1.7
Added a liquefaction model with linear economies of scale (capital) and efficiencies of scale (kWh). The liquefaction model assumes a capacity factor of 100%.
Added an industrial electricity cost that can be changed as a part of sensitivity analysis. The goal is for any variable costs that depend on electricity cost to be indexed to this variable (e.g., liquefaction cost)
Fixed an error where truck fleet capacity was inhibiting flow on the hub-to-hub trucking arcs. The truck fleet capacity should only influence flow from the pipeline node to the truck node within the same hub--i.e., the model needs to build trucking capacity at the hub, but once that capacity is built, it does not need to build capacity along the trucking routes between hubs. 

v1.8
Fixed an error where the truck routes had a maximum capacity of zero. This had to do with how I was creating sets--basically, I had created a distribution arc set that captured capital, fixed, variable costs and also flow capacity limits. The problem was that not every distribution arc had all of thoe qualities, so I was leaving the truck route arcs out of the flow constraint equations, which automatically capped their capacity at zero. I am now defining those sets more intelligently by including things in those sets that have the relevant characteristics.
Added natural gas price as an input. Currently this applies only to SMR variable costs, but in the future it could be used for industry breakeven prices also. 

v1.9
Added CCS tax credit 45Q
Added utilization rates for production and conversion technologies. For example, if a fuel station is 70% utilized, then the capacity needs to be (1/.7) larger than the demand it serves. I am not currently applying this rule to storage, pipelines, and trucks.
Add truck terminals

v.20 
Added storage

v.30
Removed the discretize demand function--we're taking a simpler approach to demand where we just tell the model what the demand is and give it a single breakeven price.
Removed storage
Updated the flowchart of the network model
Updated the conversion csv to use class names as the start and end points of inserting a converter into the network

v.31
Fixed the ability to determine prices at each node.

v.32
Removed the intercepts from the costs and efficiencies--this method was intended to capture economies of scale, but it doesn't actually accomplish that.

v.33 
Added the ability to inject subsidies into the infrastructure investment. The model can be given a amount of cash that it can use, and the percentage cost-share needed to spend that cash.



TO DO

Troubleshoot the infrastructure subsidy scenario. It looks like conversion subsidies may not be impacting the price of hydrogen in Austin, though production and distribution subsidies do seem to have an impact. It could be that the conversion subsidies are being spent on infrastructure that doesn't actually impact the Austin market? Not sure, but it's worth a bit of digging. Would probably help to home in on which technologies are receiving the subsidies. 

Added minimum capacities to technologies. This makes it easier to capture economies of scale of building larger units at lower capital costs and operational costs.



IDEAS
assign different electricity rate structures and gas structures to different sized plants?
    
consider adding a node at each hub to denote the trucking fleet size. Right now, this information is held in the arc between the compressor/liquefier and the trucking distribution node at that hub. Might be cleaner if we just had a truck_hub_node that stored the number of trucks that that hub invests in, and then we can just limit the flow of the outgoing edges to be constrained by the capacity at that node.


fyi:
Texas currently consumes ~10,000 tons of H2 per day
a carbon price of 100 $/ton translates to roughly 1.00 $/kg for SMR hydrogen
breakeven for different distribution methods, approximately:
    choose compressed trucks if distance < 150 km, and demand < 16 tons per day
    choose liquefied trucks if distance > 150 km, and demand < 30 tons per day
    otherwise, use pipelines for the most part
    note that compared to the ~10,000 tons per day daily H2 demand, these numbers are quite small, but a refueling station might only consume 4 tons per day, so it's possible that if the model has a series of refueling stations that are each 50+ km away from each other, that trucks will win out over pipelines.
    
'''

import pyomo
import pyomo.environ as pe
import pandas
import time
import numpy
#hydrogen modules
#import discretize_demand
import hydrogen_model.create_graph as create_graph

start = time.time()

class hydrogen_inputs:
    '''
    stores all of the input files needed to run the hydrogen model
    stores some hard coded variables used for the hydrogen model
    '''
    def __init__(self, inputs,
                    industrial_electricity_usd_per_kwh, 
                    industrial_ng_usd_per_mmbtu, 
                    carbon_price_dollars_per_ton, 
                    carbon_capture_credit_dollars_per_ton, 
                    price_tracking_array, 
                    price_hubs, 
                    price_demand, 
                    find_prices, 
                    csv_prefix, 
                    investment_interest,
                    investment_period, 
                    time_slices, 
                    subsidy_dollar_billion, 
                    subsidy_cost_share_fraction,
                    minimum_producer_size_tonnes_per_day,
                    **kwargs):
                    # industrial_electricity_usd_per_kwh=0.05, 
                    # industrial_ng_usd_per_mmbtu=3.50, 
                    # carbon_price_dollars_per_ton=100, 
                    # carbon_capture_credit_dollars_per_ton=50., 
                    # price_tracking_array = numpy.arange(0,20,0.1), 
                    # price_hubs='all', 
                    # price_demand=0.01, 
                    # find_prices=False, 
                    # csv_prefix = '', 
                    # investment_interest=0.06, 
                    # investment_period=20, 
                    # time_slices=365, 
                    # subsidy_dollar_billion=0, 
                    # subsidy_cost_share_fraction=1):
        '''
        carbon_price_dollars_per_ton: dollars per ton penalty on CO2 emissions 
        investment_interest: interest rate for financing capital investments
        investment_period: number of years over which capital is financed
        time_slices: used to get from investment_period units to the simulation timestep units. Default is 365 because the investment period units are in years (20 years default) and the simulation units are in days.
        '''
        #generic data
        self.producers = pandas.DataFrame(inputs['production'])
        self.storage = pandas.DataFrame(inputs['storage'])
        self.distributors = pandas.DataFrame(inputs['distribution'])
        self.converters = pandas.DataFrame(inputs['conversion'])
        self.demand = pandas.DataFrame(inputs['demand'])
        self.ccs_data = pandas.DataFrame(inputs['ccs'])
        self.ccs_data.set_index('type', inplace=True)
        #data specific to the real world network being analyzed
        self.nodes = pandas.DataFrame(inputs['{}nodes'.format(csv_prefix)])
        self.arcs = pandas.DataFrame(inputs['{}arcs'.format(csv_prefix)])
        #self.consumers_existing = inputs['%sdemand_existing.csv'%csv_prefix)
        self.producers_existing = pandas.DataFrame(inputs['{}production_existing'.format(csv_prefix)])

        ###hard coded scalars
        self.e_price = industrial_electricity_usd_per_kwh
        self.ng_price = industrial_ng_usd_per_mmbtu
        self.time_slices = float(time_slices) 
        self.carbon_price = float(carbon_price_dollars_per_ton)
        self.carbon_capture_credit = carbon_capture_credit_dollars_per_ton
        self.A = (((1+investment_interest)**investment_period)-1)/(investment_interest*(1+investment_interest)**investment_period) #yearly amortized payment = capital cost / A
        self.carbon_g_MJ_to_t_tH2 = 120000./1000000. #unit conversion 120,000 MJ/tonH2, 1,000,000 g/tonCO2
        self.price_tracking_array = numpy.arange(**price_tracking_array)
        self.price_hubs = price_hubs
        self.price_demand = price_demand
        self.find_prices = find_prices
        #for the scenario where hydrogen infrastructure is subsidized
        self.subsidy_dollar_billion = subsidy_dollar_billion #how many billions of dollars are available to subsidize infrastructure
        self.subsidy_cost_share_fraction = subsidy_cost_share_fraction #what fraction of dollars must industry spend on new infrastructure--e.g., if = 0.6, then for a $10Billion facility, industry must spend $6Billion (which counts toward the objective function) and the subsidy will cover $4Billion (which is excluded from the objective function).
        
        self.min_prod_h = minimum_producer_size_tonnes_per_day # define a minimum amount of hydrogen that can be produced

def build_h2_model(inputs, input_parameters):
    print ('Building model')
    ###create the hydrogen_inputs object
    H = hydrogen_inputs(inputs= inputs, **input_parameters)
                        # csv_prefix='texas_', 
                        # price_tracking_array = numpy.arange(3,9,0.05), 
                        # #price_hubs=['austin', 'pasadena', 'elPaso'],
                        # price_hubs=['austin', 'pasadena'],
                        # find_prices=True,
                        # industrial_electricity_usd_per_kwh=0.075, 
                        # industrial_ng_usd_per_mmbtu=3.50, 
                        # carbon_price_dollars_per_ton=0,
                        # subsidy_dollar_billion=0, 
                        # subsidy_cost_share_fraction=0.9)
    #use the discretize_demand module to add individual consumers to the hydrogen_inputs object
    #H.consumers = discretize_demand.main(H) #no longer using this

    #create the network graph
    H_network = create_graph.hydrogen_network(H)
    g = H_network.g

    

    ###create the pyomo model
    #create the model
    m = pe.ConcreteModel()
    #load the hydrogen_inputs into the model
    m.H = H
    #create the problem data
    #load graph into the model
    m.g = g


    #sets
    #calculate sets and subsets
    producer_nodes = []
    producer_existing_nodes = []
    consumer_nodes = []
    consumer_arcs = []
    distribution_arcs_capital = []
    distribution_arcs_fixed = []
    distribution_arcs_variable = []
    distribution_arcs_flowConstrained = []
    distribution_arcs_existing = []
    conversion_nodes = []
    conversion_arcs = []
    fuelStation_nodes = []
    for n in m.g.nodes:
        if (m.g.nodes[n]['class'])=='producer':
            producer_nodes.append(n)
            if m.g.nodes[n]['existing']==1:
                producer_existing_nodes.append(n)  
        if (('demandSector' in m.g.nodes[n]['class']) | ((m.g.nodes[n]['class'])=='price')):
            consumer_nodes.append(n)
        if 'converter' in (m.g.nodes[n]['class']):
            conversion_nodes.append(n)
        if 'fuelDispenser' in (m.g.nodes[n]['class']):
            fuelStation_nodes.append(n)
                
    for e in m.g.edges:
        if 'class' in m.g.edges[e].keys():
            if 'capital_usdPerUnit' in m.g.edges[e].keys():
                if m.g.edges[e]['capital_usdPerUnit'] > 0:
                    distribution_arcs_capital.append(e)
            if 'fixed_usdPerUnitPerDay' in m.g.edges[e].keys():
                if m.g.edges[e]['fixed_usdPerUnitPerDay'] > 0:
                    distribution_arcs_fixed.append(e)    
            if 'variable_usdPerTon' in m.g.edges[e].keys():
                if m.g.edges[e]['variable_usdPerTon'] > 0:
                    distribution_arcs_variable.append(e)    
            if 'flowLimit_tonsPerDay' in m.g.edges[e].keys():
                if m.g.edges[e]['flowLimit_tonsPerDay'] != 0:
                    distribution_arcs_flowConstrained.append(e)                                   
            if 'existing' in m.g.edges[e].keys():
                if m.g.edges[e]['existing']==1:
                    distribution_arcs_existing.append(e)  
            if m.g.edges[e]['class']=='flow_to_demand_sector':
                consumer_arcs.append(e)  
        if (('converter' in (m.g.nodes[e[0]]['class'])) | ('converter' in (m.g.nodes[e[1]]['class']))):
            conversion_arcs.append(e)
    #assign sets in model
    m.node_set = pe.Set(initialize=list(m.g.nodes()))
    m.arc_set = pe.Set(initialize=list(m.g.edges()), dimen=None)      
    m.producer_set = pe.Set(initialize=producer_nodes)
    m.producer_existing_set = pe.Set(initialize=producer_existing_nodes)
    m.consumer_set = pe.Set(initialize=consumer_nodes)
    m.consumer_arc_set = pe.Set(initialize=consumer_arcs)
    m.distribution_arcs_capital_set = pe.Set(initialize=distribution_arcs_capital)
    m.distribution_arcs_fixed_set = pe.Set(initialize=distribution_arcs_fixed)
    m.distribution_arcs_variable_set = pe.Set(initialize=distribution_arcs_variable)
    m.distribution_arcs_flowConstrained_set = pe.Set(initialize=distribution_arcs_flowConstrained)
    m.distribution_arc_existing_set = pe.Set(initialize=distribution_arcs_existing)
    m.converter_set = pe.Set(initialize=conversion_nodes)
    m.converter_arc_set = pe.Set(initialize=conversion_arcs)
    m.fuelStation_set = pe.Set(initialize=fuelStation_nodes)


    #parameters
    #tracking
    m.arc_class = pe.Param(m.arc_set, initialize=lambda m, i,j: m.g.adj[i][j].get('class',0), within=pe.Any) 
    #distribution
    m.dist_cost_capital = pe.Param(m.distribution_arcs_capital_set, initialize=lambda m, i,j: m.g.adj[i][j].get('capital_usdPerUnit',0))
    m.dist_cost_fixed = pe.Param(m.distribution_arcs_fixed_set, initialize=lambda m, i,j: m.g.adj[i][j].get('fixed_usdPerUnitPerDay',0))
    m.dist_cost_variable = pe.Param(m.distribution_arcs_variable_set, initialize=lambda m, i,j: m.g.adj[i][j].get('variable_usdPerTon',0))
    m.dist_flowLimit = pe.Param(m.distribution_arcs_flowConstrained_set, initialize=lambda m, i,j: m.g.adj[i][j].get('flowLimit_tonsPerDay',0)) 
    #production
    m.prod_cost_capital_coeff = pe.Param(m.producer_set, initialize=lambda m, i: m.g.nodes[i].get('capital_usd_coefficient',0))
    m.prod_cost_fixed= pe.Param(m.producer_set, initialize=lambda m, i: m.g.nodes[i].get('fixed_usdPerTon',0))
    m.prod_kwh_variable_coeff = pe.Param(m.producer_set, initialize=lambda m, i: m.g.nodes[i].get('kWh_coefficient',0))
    m.prod_ng_variable_coeff = pe.Param(m.producer_set, initialize=lambda m, i: m.g.nodes[i].get('ng_coefficient',0))
    m.prod_cost_variable = pe.Param(m.producer_set, initialize=lambda m, i: m.g.nodes[i].get('variable_usdPerTon',0))
    m.prod_carbonRate = pe.Param(m.producer_set, initialize=lambda m, i: m.g.nodes[i].get('carbon_g_MJ',0) * m.H.carbon_g_MJ_to_t_tH2) 
    m.prod_utilization = pe.Param(m.producer_set, initialize=lambda m, i: m.g.nodes[i].get('utilization',0))
    #conversion
    m.conv_cost_capital_coeff = pe.Param(m.converter_set, initialize=lambda m, i: m.g.nodes[i].get('capital_usd_coefficient',0))
    m.conv_cost_fixed = pe.Param(m.converter_set, initialize=lambda m, i: m.g.nodes[i].get('fixed_usdPerTonPerDay',0))
    m.conv_kwh_variable_coeff = pe.Param(m.converter_set, initialize=lambda m, i: m.g.nodes[i].get('kWh_coefficient',0))
    m.conv_cost_variable = pe.Param(m.converter_set, initialize=lambda m, i: m.g.nodes[i].get('variable_usdPerTon',0))
    m.conv_utilization = pe.Param(m.converter_set, initialize=lambda m, i: m.g.nodes[i].get('utilization',0))
    #consumption
    m.cons_price = pe.Param(m.consumer_set, initialize=lambda m, i: m.g.nodes[i].get('breakevenPrice',0))
    m.cons_size = pe.Param(m.consumer_set, initialize=lambda m, i: m.g.nodes[i].get('size',0))
    m.cons_carbonSensitive = pe.Param(m.consumer_set, initialize=lambda m, i: m.g.nodes[i].get('carbonSensitive',0))
    m.cons_breakevenCarbon = pe.Param(m.consumer_set, initialize=lambda m, i: m.g.nodes[i].get('breakevenCarbon_g_MJ',0) * m.H.carbon_g_MJ_to_t_tH2)
    #ccs
    m.can_ccs1 = pe.Param(m.producer_set, initialize=lambda m, i: m.g.nodes[i].get('can_ccs1',0)) #binary, 1: producer can build CCS1
    m.can_ccs2 = pe.Param(m.producer_set, initialize=lambda m, i: m.g.nodes[i].get('can_ccs2',0)) #binary, 1: producer can build CCS2


    #variables
    #distribution
    m.dist_capacity = pe.Var(m.arc_set, domain=pe.NonNegativeIntegers) #daily capacity of each arc
    m.dist_h = pe.Var(m.arc_set, domain=pe.NonNegativeReals) #daily flow along each arc
    #production
    m.prod_exists = pe.Var(m.producer_set, domain=pe.Binary) # binary that tracks if a producer was built or not
    m.prod_capacity = pe.Var(m.producer_set, domain=pe.NonNegativeReals) #daily capacity of each producer
    m.prod_h = pe.Var(m.producer_set, domain=pe.NonNegativeReals) #daily production of each producer
    #conversion
    m.conv_capacity = pe.Var(m.converter_set, domain=pe.NonNegativeReals) #daily capacity of each converter
    #consumption
    m.cons_h = pe.Var(m.consumer_set, domain=pe.NonNegativeReals) #consumer's daily demand for hydrogen
    m.cons_hblack = pe.Var(m.consumer_set, domain=pe.NonNegativeReals) #consumer's daily demand for hydrogen black
    #ccs
    m.ccs1_capacity_co2 = pe.Var(m.producer_set, domain=pe.NonNegativeReals) #daily capacity of CCS1 for each producer in tons CO2
    m.ccs2_capacity_co2 = pe.Var(m.producer_set, domain=pe.NonNegativeReals) #daily capacity of CCS2 for each producer in tons CO2
    m.ccs1_capacity_h2 = pe.Var(m.producer_set, domain=pe.NonNegativeReals) #daily capacity of CCS1 for each producer in tons h2
    m.ccs2_capacity_h2 = pe.Var(m.producer_set, domain=pe.NonNegativeReals) #daily capacity of CCS2 for each producer in tons h2
    #carbon
    m.prod_hblack = pe.Var(m.producer_set, domain=pe.NonNegativeReals) #daily production of hydrogen black for each producer
    m.ccs1_hblack = pe.Var(m.producer_set, domain=pe.NonNegativeReals) #daily production of hydrogen black for CCS1 for each producer
    m.ccs2_hblack = pe.Var(m.producer_set, domain=pe.NonNegativeReals) #daily production of hydrogen black for CCS2 for each producer
    m.co2_nonHydrogenConsumer = pe.Var(m.consumer_set, domain=pe.Reals) #carbon emissions for each consumer that is not using hydrogen
    m.co2_emitted = pe.Var(m.producer_set, domain=pe.Reals) #carbon emissions for each hydrogen producer
    #infrastructure subsidy
    m.fuelStation_cost_capital_subsidy = pe.Var(m.fuelStation_set, domain=pe.NonNegativeReals) #subsidy dollars used to reduce the capital cost of converter[cv]

    #objective function
    #maximize total surplus
    def obj_rule(m):
        U_hydrogen = sum(m.cons_h[c] * m.cons_price[c] for c in m.consumer_set) #consumer daily utility from buying hydrogen
        U_carbon = sum(m.cons_hblack[c] * m.cons_breakevenCarbon[c] * m.H.carbon_price for c in m.consumer_set) #consumer daily utility from buying hydrogen black
        U_carbon_capture_credit = sum((m.ccs1_hblack[p]*(m.prod_carbonRate[p]*(1-m.H.ccs_data.loc['ccs1','percent_CO2_captured'])) + m.ccs2_hblack[p]*(m.prod_carbonRate[p]*(1-m.H.ccs_data.loc['ccs2','percent_CO2_captured']))) * m.H.carbon_capture_credit for p in m.producer_set)
        P_variable = sum(m.prod_h[p] * m.prod_cost_variable[p] for p in m.producer_set) #production variable cost per ton
        P_electricity = sum((m.prod_h[p] * m.prod_kwh_variable_coeff[p]) * m.H.e_price for p in m.producer_set) #daily electricity cost
        P_naturalGas = sum((m.prod_h[p] * m.prod_ng_variable_coeff[p]) * m.H.ng_price for p in m.producer_set)
        P_fixed = sum(m.prod_capacity[p] * m.prod_cost_fixed[p] for p in m.producer_set) #production daily fixed cost per ton
        P_capital = sum((m.prod_capacity[p] * m.prod_cost_capital_coeff[p]) / m.H.A / m.H.time_slices for p in m.producer_set) #production daily capital cost per ton
        P_carbon = sum((m.prod_hblack[p]*m.prod_carbonRate[p] + m.ccs1_hblack[p]*(m.prod_carbonRate[p]*(1-m.H.ccs_data.loc['ccs1','percent_CO2_captured'])) + m.ccs2_hblack[p]*(m.prod_carbonRate[p]*(1-m.H.ccs_data.loc['ccs2','percent_CO2_captured']))) * m.H.carbon_price for p in m.producer_set) #cost to produce hydrogen black
        CCS_variable = sum((m.ccs1_capacity_co2[p] * m.H.ccs_data.loc['ccs1', 'variable_usdPerTonCO2']) + (m.ccs2_capacity_co2[p] * m.H.ccs_data.loc['ccs2', 'variable_usdPerTonCO2'])  for p in m.producer_set) #ccs variable cost per ton of produced hydrogen
        #distribution
        D_variable = sum(m.dist_h[d] * m.dist_cost_variable[d] for d in m.distribution_arcs_variable_set) #daily variable cost
        D_fixed = sum(m.dist_capacity[d] * m.dist_cost_fixed[d] for d in m.distribution_arcs_fixed_set) #daily fixed cost
        D_capital = sum((m.dist_capacity[d] * m.dist_cost_capital[d]) / m.H.A / m.H.time_slices for d in m.distribution_arcs_capital_set) #daily capital cost
        #converters
        CV_variable = sum(m.conv_capacity[cv] * m.conv_utilization[cv] * m.conv_cost_variable[cv] for cv in m.converter_set) #daily variable cost
        CV_electricity = sum((m.conv_capacity[cv] * m.conv_utilization[cv] * m.conv_kwh_variable_coeff[cv]) * m.H.e_price for cv in m.converter_set) #daily electricity cost
        CV_fixed = sum(m.conv_capacity[cv] * m.conv_cost_fixed[cv] for cv in m.converter_set) #daily fixed cost
        CV_capital = sum((m.conv_capacity[cv] * m.conv_cost_capital_coeff[cv]) / m.H.A / m.H.time_slices  for cv in m.converter_set) #daily amortized capital cost
        CV_fuelStation_subsidy = sum(m.fuelStation_cost_capital_subsidy[fs] / m.H.A / m.H.time_slices  for fs in m.fuelStation_set)
        
        totalSurplus = U_hydrogen + U_carbon + U_carbon_capture_credit - P_variable - P_electricity - P_naturalGas - P_fixed - P_capital - P_carbon - CCS_variable - D_variable - D_fixed - D_capital - CV_variable - CV_electricity - CV_fixed - CV_capital + CV_fuelStation_subsidy
        return (totalSurplus)
    m.OBJ = pe.Objective(rule=obj_rule, sense=pe.maximize)


    #constraints
    #distribution and conversion
    #flow balance constraints for each node
    def rule_flowBalance(m, node):    
        expr = 0  
        if m.g.in_edges(node):
            expr += pe.summation(m.dist_h, index=m.g.in_edges(node))
        if m.g.out_edges(node):
            expr += - pe.summation(m.dist_h, index=m.g.out_edges(node))
        #the equality depends on whether the node is a producer, consumer, or hub
        if node in m.producer_set: #if producer:
            constraint = (m.prod_h[node] + expr == 0.)
        elif node in m.consumer_set: #if consumer:
            constraint = (expr - m.cons_h[node] == 0.)
        else: #if hub:
            constraint = (expr == 0.)
        return constraint
    m.constr_flowBalance = pe.Constraint(m.node_set, rule=rule_flowBalance)
    #existing pipelines' capacity is greater than or equal to 1
    def rule_flowCapacityExisting(m, startNode, endNode):
        constraint = (m.dist_capacity[startNode,endNode] >= m.g.edges[startNode,endNode]['existing'])
        return constraint
    m.constr_flowCapacityExisting = pe.Constraint(m.distribution_arc_existing_set, rule=rule_flowCapacityExisting)
    #each distributor's flow cannot exceed its capacity * flowLimit
    def rule_flowCapacity(m, startNode, endNode):
        constraint = (m.dist_h[startNode,endNode] <= m.dist_capacity[startNode,endNode] * m.dist_flowLimit[startNode,endNode])
        return constraint
    m.constr_flowCapacity = pe.Constraint(m.distribution_arcs_flowConstrained_set, rule=rule_flowCapacity)


    #flow across conversion arcs is limited by the capacity of the conversion node
    def rule_flowCapacityConverters(m, converterNode):
        expr = pe.summation(m.dist_h, index=m.g.out_edges(converterNode))
        constraint = (expr <= m.conv_capacity[converterNode] * m.conv_utilization[converterNode])
        return constraint
    m.constr_flowCapacityConverters = pe.Constraint(m.converter_set, rule=rule_flowCapacityConverters)




    #production and ccs
    # Prohibit model from not deploying existing producers
    def rule_forceExistingProduction(m,node):
        constraint = (m.prod_exists[node] == True)
        return constraint
    m.const_forceExistingProduction = pe.Constraint(m.producer_existing_set, rule=rule_forceExistingProduction)
    #existing producers' capacity equals their existing capacity
    def rule_productionCapacityExisting(m, node):
        constraint = (m.prod_capacity[node] == m.g.nodes[node]['capacity_tonPerDay'])
        return constraint
    m.constr_productionCapacityExisting = pe.Constraint(m.producer_existing_set, rule=rule_productionCapacityExisting)
    #each producer's production cannot exceed its capacity
    def rule_productionCapacity(m, node):
        constraint = (m.prod_h[node] <= m.prod_capacity[node] * m.prod_utilization[node])
        return constraint
    m.constr_productionCapacity = pe.Constraint(m.producer_set, rule=rule_productionCapacity)
    # production must exceed minimum production value, if not already existing
    def rule_minProductionCapacity1(m,node):
        if node in m.producer_existing_set:
            # if producer is an existing producer, don't constrain by minimum value
            # note - do not confuse node with hub. node in this case would be something akin to 'dallas_smrExisting', not 'dallas'
            constraint = (m.prod_h[node] >= 0)
        else:
            constraint = (m.prod_h[node] >= m.H.min_h * m.prod_exists[node])
        return constraint
    m.constr_minProductionCapacity1 = pe.Constraint(m.producer_set, rule=rule_minProductionCapacity1)
    def rule_minProductionCapacity2(m,node):
        constraint = (m.prod_h[node] <= 1e12 * m.prod_exists[node]) #1e12 is just a large number, not specific since python doesn't have anything like int.max
        return constraint
    m.constr_minProductionCapacity2 = pe.Constraint(m.producer_set, rule=rule_minProductionCapacity2)

    #ccs capacity in terms of CO2 is related to its capacity in terms of H2, which must be zero if m.ccs#_can==0
    def rule_ccs1CapacityRelationship(m, node):
        constraint = (m.ccs1_capacity_co2[node] * m.can_ccs1[node] == m.ccs1_capacity_h2[node] * m.prod_carbonRate[node] * m.H.ccs_data.loc['ccs1', 'percent_CO2_captured'])
        return constraint
    m.constr_ccs1CapacityRelationship = pe.Constraint(m.producer_set, rule=rule_ccs1CapacityRelationship)
    def rule_ccs2CapacityRelationship(m, node):
        constraint = (m.ccs2_capacity_co2[node] * m.can_ccs2[node] == m.ccs2_capacity_h2[node] * m.prod_carbonRate[node] * m.H.ccs_data.loc['ccs2', 'percent_CO2_captured'])
        return constraint
    m.constr_ccs2CapacityRelationship = pe.Constraint(m.producer_set, rule=rule_ccs2CapacityRelationship)
    #each producer's ccs capacity (h2) cannot exceed its production capacity 
    def rule_ccsCapacity(m, node):  
        constraint = (m.ccs1_capacity_h2[node] + m.ccs2_capacity_h2[node] <= m.prod_capacity[node])
        return constraint
    m.constr_ccsCapacity = pe.Constraint(m.producer_set, rule=rule_ccsCapacity)
    #ccs hydrogen black production cannot exceed ccs capacity (h2)
    def rule_ccs1HBlack(m, node):
        constraint = (m.ccs1_hblack[node] <= m.ccs1_capacity_h2[node])
        return constraint
    m.constr_ccs1HBlack = pe.Constraint(m.producer_set, rule=rule_ccs1HBlack)
    def rule_ccs2HBlack(m, node):
        constraint = (m.ccs2_hblack[node] <= m.ccs2_capacity_h2[node])
        return constraint
    m.constr_ccs2HBlack = pe.Constraint(m.producer_set, rule=rule_ccs2HBlack)
    #each producer's total hydrogen black production cannot exceed its hydrogen production
    def rule_productionHBlack(m, node):
        constraint = (m.prod_hblack[node] + m.ccs1_hblack[node] + m.ccs2_hblack[node] <= m.prod_h[node])
        return constraint
    m.constr_productionHBlack = pe.Constraint(m.producer_set, rule=rule_productionHBlack)

    #consumption
    #each consumer's consumption cannot exceed its size
    def rule_consumerSize(m, node):
        constraint = (m.cons_h[node] <= m.cons_size[node])
        return constraint
    m.constr_consumerSize = pe.Constraint(m.consumer_set, rule=rule_consumerSize)
    #each consumer's consumption of hydrogen black equals its consumption of hydrogen if it is a carbon-sensitive consumer
    def rule_consumerHBlack(m, node):
        constraint = (m.cons_hblack[node] == m.cons_h[node] * m.cons_carbonSensitive[node])
        return constraint
    m.constr_consumerHBlack = pe.Constraint(m.consumer_set, rule=rule_consumerHBlack)

    #carbon
    #total hydrogen black produced must exceed total hydrogen black consumed
    def rule_hBlackBalance(m):
        hblack_produced = sum(m.prod_hblack[p] + m.ccs1_hblack[p] + m.ccs2_hblack[p] for p in m.producer_set)
        hblack_consumed = sum(m.cons_hblack[c] for c in m.consumer_set)
        constraint = (hblack_consumed <= hblack_produced)
        return constraint
    m.constr_hBlackBalance = pe.Constraint(rule=rule_hBlackBalance)

    #track the co2 emissions
    #co2 emissions for hydrogen producers
    def rule_co2Producers(m, node):
        constraint = (m.co2_emitted[node]  == m.prod_carbonRate[node] * (m.prod_h[node] - m.ccs1_capacity_h2[node] * m.H.ccs_data.loc['ccs1', 'percent_CO2_captured'] - m.ccs2_capacity_h2[node] * m.H.ccs_data.loc['ccs2', 'percent_CO2_captured']))
        return constraint
    m.constr_co2Producers = pe.Constraint(m.producer_set, rule=rule_co2Producers)

    #co2 emissions for consumers that are not using hydrogen
    def rule_co2Consumers(m, node):
        #consumer_co2_rate = m.H.consumers.loc[node, 'breakevenCarbon_g_MJ'] * m.H.carbon_g_MJ_to_t_tH2 #this threw errors after we added the price nodes, but the price nodes were not included in H.consumers
        consumer_co2_rate = m.cons_breakevenCarbon[node] # * m.H.carbon_g_MJ_to_t_tH2 #NOTE pretty sure this is a typo? I think breakevenCarbon is already multiplied by the conversion factor? -bsp
        constraint = (m.co2_nonHydrogenConsumer[node]  == (m.cons_size[node] - m.cons_h[node]) * consumer_co2_rate)
        return constraint
    m.constr_co2Consumers = pe.Constraint(m.consumer_set, rule=rule_co2Consumers)


    ###subsidy for infrastructure
    #total subsidy dollars must be less than or equal to the available subsidy funds
    # =============================================================================
    # def rule_subsidyTotal(m, node):
    #     constraint = sum(m.fuelStation_cost_capital_subsidy[fs] for fs in m.fuelStation_set) <= (m.H.subsidy_dollar_billion * 1E9)
    #     return constraint
    # m.constr_subsidyTotal = pe.Constraint(rule=rule_subsidyTotal)
    # =============================================================================

    #subsidy for a facility is equal to the cost share fraction
    #conversion facility subsidies
    def rule_subsidyConverter(m, node):
        constraint = (m.fuelStation_cost_capital_subsidy[node] == m.conv_capacity[node] * m.conv_cost_capital_coeff[node] * (1-m.H.subsidy_cost_share_fraction))
        #note that existing production facilities have a cost_capital_coeff of zero, so they cannot be subsidized
        return constraint
    m.constr_subsidyConverter = pe.Constraint(m.fuelStation_set, rule=rule_subsidyConverter)


    ###
    ###solve the model
    ###
    print('Time elapsed: %f'%(time.time() - start))
    print ('Solving model')
    solver = pyomo.opt.SolverFactory(input_parameters["solver"])
    solver.options["mipgap"] = 0.01
    results = solver.solve(m, tee=False)
    # m.solutions.store_to(results)
    # results.write(filename='results.json', format='json')
    print('Model Solved with objective value {}'.format(m.OBJ()))
    print('Time elapsed: %f'%(time.time() - start))

    return m

    ##

    #output
    # output = {}

    # for output_var in ['cons_h', 'cons_hblack', 'prod_capacity', 'prod_h', 'prod_hblack', 'ccs1_hblack', 'ccs2_hblack', 'arc_class', 'dist_h', 'co2_emitted', 'co2_nonHydrogenConsumer', 'conv_capacity']: #'dist_capacity'
    #     if output_var == 'dist_capacity':
    #         output_var_dict = {}
    #         for i, v in m.dist_capacity.items():
    #             try:
    #                 value = pyomo.core.value(v)
    #             except:
    #                 value = 0.0
    #             output_var_dict[i]=value
    #         output[output_var] = pandas.DataFrame.from_dict(output_var_dict)
    #     else:
    #         run_code = "output[output_var] = pandas.DataFrame.from_dict({i: pyomo.core.value(v) for i, v in m.%s.items()}, orient='index', columns=['val'])"%(output_var)
    #         exec(run_code)
        



    # r_production = pandas.DataFrame({'producer': list(output['prod_capacity'].index), 'capacity': output['prod_capacity']['val']})
    # r_production = r_production.merge(output['prod_h'], left_index=True, right_index=True)
    # r_production = r_production.merge(output['prod_hblack'], left_index=True, right_index=True)
    # r_production = r_production.merge(output['ccs1_hblack'], left_index=True, right_index=True)
    # r_production = r_production.merge(output['ccs2_hblack'], left_index=True, right_index=True)
    # r_production = r_production.merge(output['co2_emitted'], left_index=True, right_index=True)
    # r_production.columns=['producer', 'capacity', 'production', 'hblack', 'hblack_ccs1', 'hblack_ccs2', 'co2_tons']
    # r_production = r_production[r_production['capacity'] > 0]
    # r_production = r_production.reset_index(drop=True)


    # r_consumption = pandas.DataFrame({'consumer': list(output['cons_h'].index), 'demand': output['cons_h']['val']})
    # #remove pricing nodes
    # if m.H.find_prices:
    #     price_nodes_df = r_consumption[r_consumption['consumer'].str.contains('price')].copy()
    #     r_consumption = r_consumption[~r_consumption['consumer'].str.contains('price')]
    # r_consumption = r_consumption.merge(output['cons_hblack'], left_index=True, right_index=True)
    # r_consumption = r_consumption.merge(output['co2_nonHydrogenConsumer'], left_index=True, right_index=True)
    # r_consumption.columns=['consumer', 'demand', 'hblack_demand', 'co2_tons_nonHydrogenConsumption']
    # r_consumption = r_consumption[r_consumption['demand'] > 0]
    # r_consumption = r_consumption.reset_index(drop=True)


    # #distribution_df = pandas.DataFrame({'arc': list(output['dist_capacity'].index), 'capacity': output['dist_capacity']['val']})
    # distribution_df = pandas.DataFrame({'arc': list(output['dist_h'].index), 'capacity': output['dist_h']['val']})
    # distribution_df = distribution_df.merge(output['arc_class'], left_index=True, right_index=True)
    # distribution_df = distribution_df.merge(output['dist_h'], left_index=True, right_index=True)
    # distribution_df[['arc_start', 'arc_end']] = pandas.DataFrame(distribution_df['arc'].tolist(), index=distribution_df.index)
    # distribution_df = distribution_df[['arc_start', 'arc_end', 'val_x', 'capacity', 'val_y']]
    # distribution_df.columns=['arc_start', 'arc_end', 'class', 'capacity', 'flow']
    # #distribution_df = distribution_df[['arc_start', 'arc_end', 'capacity', 'val']]
    # #distribution_df.columns=['arc_start', 'arc_end', 'capacity', 'flow']
    # distribution_df = distribution_df[(distribution_df['capacity']>0)|(distribution_df['flow']>0)]
    # non_demand_edges = ~(distribution_df.index.str[0].str.contains('demand') | distribution_df.index.str[1].str.contains('demand'))
    # distribution_df = distribution_df[non_demand_edges] 


    # r_dist_pipelineLowPurity = distribution_df[distribution_df['class'].str.contains('arc_pipelineLowPurity')]
    # r_dist_pipelineHighPurity = distribution_df[distribution_df['class'].str.contains('arc_pipelineHighPurity')]
    # r_dist_truckLiquefied = distribution_df[distribution_df['class'].str.contains('arc_truckLiquefied')]
    # r_dist_truckCompressed = distribution_df[distribution_df['class'].str.contains('arc_truckCompressed')]




    # conversion_df = pandas.DataFrame({'arc': list(output['conv_capacity'].index), 'capacity': output['conv_capacity']['val']})

    # r_liquefiers = conversion_df[(conversion_df['arc'].str.contains('liquefaction')) & (conversion_df['capacity']>0)]

    # r_compressors = conversion_df[(conversion_df['arc'].str.contains('compressor')) & (conversion_df['capacity']>0)]

    # r_terminals = conversion_df[(conversion_df['arc'].str.contains('terminal')) & (conversion_df['capacity']>0)]

    # r_fuelDispensers = conversion_df[(conversion_df['arc'].str.contains('fuelDispenser')) & (conversion_df['capacity']>0)]

    # r_purifiers = conversion_df[(conversion_df['arc'].str.contains('purification')) & (conversion_df['capacity']>0)]


    # #find prices for each hub
    # if m.H.find_prices:
    #     r_prices = pandas.DataFrame(columns=['demand_hub', 'demand_type', 'price'])
    #     for h in price_nodes_df['consumer'].str.split('_').str[0].unique():
    #         #find the index where demand goes from 0 to positive
    #         r_prices_temp = price_nodes_df[price_nodes_df['consumer'].str.contains(h+'_')].copy()    
    #         r_prices_temp['boolean'] = 0 
    #         r_prices_temp.loc[r_prices_temp['demand'] == r_prices_temp['demand'].max(), 'boolean'] = 1
    #         r_prices_temp['diff'] = r_prices_temp['boolean'].diff()
    #         r_prices_temp = r_prices_temp[r_prices_temp['diff'] == 1]
    #         #pull out the market prices for that node
    #         r_prices_add = pandas.DataFrame({'demand_hub': h,
    #                                         'demand_type': r_prices_temp['consumer'].str.split('_').str[1],
    #                                         'price': r_prices_temp['consumer'].str.split('_price')[0][1].split('_')[1]})
    #         r_prices = pandas.concat([r_prices, r_prices_add])
    #     r_prices.reset_index(inplace=True, drop=True)



    # #summary values
    # #carbon intensity of the hydrogen production
    # hydrogen_CI = (r_production['co2_tons'].sum()) / (r_production['production'].sum()) / m.H.carbon_g_MJ_to_t_tH2
    # #total CO2 of the hydrogen production and the non-hydrogen consumers. Compare this to the baseline to show how much emissions have changed.
    # total_CO2 = r_production['co2_tons'].sum() + r_consumption['co2_tons_nonHydrogenConsumption'].sum()



    # #print some results for the infrastructure subsidy

    # # =============================================================================
    # # subsidy_prod = 0
    # # subsidy_dist = 0
    # # subsidy_conv = 0
    # # for p in m.producer_set:
    # #     subsidy_prod += m.prod_cost_capital_subsidy[p].value/1e9
    # # 
    # # for d in m.distribution_arcs_capital_set:
    # #     subsidy_dist += m.dist_cost_capital_subsidy[d].value/1e9
    # # 
    # # for p in m.converter_set:
    # #     subsidy_conv += m.conv_cost_capital_subsidy[p].value/1e9
    # # =============================================================================

    # subsidy_fuelStation = 0
    # for p in m.fuelStation_set:
    #     subsidy_fuelStation += m.fuelStation_cost_capital_subsidy[p].value/1e9


    # #print ('Austin Price:')
    # #print (r_prices[r_prices['demand_hub']=='austin']['price'].iloc[0])
    # #print ('')
    # print ('Flow via Liquid Trailers:')
    # print (r_dist_truckLiquefied['flow'].sum())
    # print ('')
    # print ('Flow via High Purity Pipelines:')
    # print (r_dist_pipelineHighPurity['flow'].sum())
    # print ('')
    # print ('New Production Capacity:')
    # print (r_production[~r_production['producer'].str.contains('Existing')]['capacity'].sum())
    # print ('')
    # print ('Subsidy applie to:')
    # #print ('     Production:   %.2f $B'%subsidy_prod)
    # #print ('     Distribution: %.2f $B'%subsidy_dist)
    # #print ('     Conversion:   %.2f $B'%subsidy_conv)
    # print ('     FuelStation:   %.2f $B'%subsidy_fuelStation)



    # #%%

    # test = 'pasadena'

    # # for e in g.edges:
    # #     if test in e[0]:
    # #         print (e)





    # #%%

    # subsidy_prod = 0
    # subsidy_dist = 0
    # subsidy_conv = 0
    # for p in m.producer_set:
    #     subsidy_prod += m.prod_cost_capital_subsidy[p].value/1e9

    # for d in m.distribution_arcs_capital_set:
    #     subsidy_dist += m.dist_cost_capital_subsidy[d].value/1e9

    # for p in m.converter_set:
    #     subsidy_conv += m.conv_cost_capital_subsidy[p].value/1e9



    # #%%





    # print('     -------')
    # print('Consumption:')
    # for c in m.cons_h:
    #     print(str(m.cons_h[c].value) + ': ' + c)
    # print('     -------')
    # print('Production Capacity:')
    # for p in m.prod_capacity:
    #     print(str(m.prod_capacity[p].value) + ': ' + p)
    #     if m.can_ccs1[p]:
    #         print(str(m.ccs1_capacity_h2[p].value) + ': ' + p + '_ccs1 tH2')
    #     if m.can_ccs2[p]:
    #         print(str(m.ccs2_capacity_h2[p].value) + ': ' + p + '_ccs2 tH2')
    # print('     -------')
    # print('Production:')
    # for p in m.ccs1_capacity_h2:
    #     print(str(m.ccs1_capacity_h2[p].value) + ': ' + p)
    # print('     -------')
    # print('Distribution and Conversion Capacity (Units):')
    # for d in m.dist_capacity:
    #     if d in m.distribution_arc_set:
    #         print(str(m.dist_capacity[d].value) + ': ' + d[0] + '_' + d[1])   
    # print('     -------')
    # print('Distribution Flow (Tons):')
    # for d in m.dist_h:
    #     if m.dist_h[d].value > 0.0:
    #         print(str(m.dist_h[d].value) + ': ' + d[0] + '_' + d[1])  
    # print('     -------')
    # print('Hydrogen Black Production:')
    # for p in m.prod_capacity:
    #     print(str(m.prod_hblack[p].value) + ': ' + p)   
    #     print(str(m.ccs1_hblack[p].value) + ': ' + p + '_ccs1')   
    #     print(str(m.ccs2_hblack[p].value) + ': ' + p + '_ccs2')   
    # print('     -------')
    # print('Hydrogen Black Consumption:')
    # for c in m.cons_h:
    #     print(str(m.cons_hblack[c].value) + ': ' + c)   


    # #the results of the objective function
    # U_hydrogen = 0.
    # U_carbon = 0.
    # P_variable = 0.
    # P_fixed = 0.
    # P_capital = 0.
    # P_carbon = 0.
    # CCS_variable = 0.
    # D_variable = 0.
    # D_fixed = 0.
    # D_capital = 0.
    # cons_H = 0.
    # for c in m.consumer_set:
    #     U_hydrogen += m.cons_h[c].value * m.cons_price[c]
    #     U_carbon += m.cons_hblack[c].value  * m.cons_breakevenCarbon[c]  * m.H.E
    #     cons_H += m.cons_h[c].value
    # for p in m.producer_set:
    #     P_variable += m.prod_h[p].value * m.prod_cost_variable[p]
    #     P_fixed += m.prod_capacity[p].value * m.prod_cost_fixed[p]
    #     P_capital += m.prod_capacity[p].value * m.prod_cost_capital[p] / m.H.A / m.H.time_slices
    #     P_carbon += (m.prod_hblack[p].value*m.prod_carbonRate[p] + m.ccs1_hblack[p].value*(m.prod_carbonRate[p]*(1-m.H.ccs_data.loc['ccs1','percent_CO2_captured'])) + m.ccs2_hblack[p].value*(m.prod_carbonRate[p]*(1-m.H.ccs_data.loc['ccs2','percent_CO2_captured']))) * m.H.E
    #     CCS_variable += (m.ccs1_capacity_co2[p].value * m.H.ccs_data.loc['ccs1', 'variable_usdPerTonCO2']) + (m.ccs2_capacity_co2[p].value * m.H.ccs_data.loc['ccs2', 'variable_usdPerTonCO2'])
    # for d in m.arc_set:
    #     D_variable += m.dist_h[d].value * m.dist_cost_variable[d]
    # for d in m.distribution_arc_set:   
    #     D_fixed += m.dist_capacity[d].value * m.dist_cost_fixed[d]       
    #     D_capital += m.dist_capacity[d].value * m.dist_cost_capital[d] / m.H.A / m.H.time_slices 
    # print('     -------')
    # print('     -------')
    # print('Utility, hydrogen            : %.0f'%U_hydrogen)
    # print('Production Costs, variable   : %.0f'%P_variable)
    # print('Production Costs, fixed      : %.0f'%P_fixed)
    # print('Production Costs, capital    : %.0f'%P_capital)
    # print('Distribution Costs, variable : %.0f'%D_variable)
    # print('Distribution Costs, fixed    : %.0f'%D_fixed)
    # print('Distribution Costs, capital  : %.0f'%D_capital)
    # print('Utility, carbon              : %.0f'%U_carbon)
    # print('Production Costs, carbon     : %.0f'%P_carbon)
    # print('CCS Costs, carbon            : %.0f'%CCS_variable)
    # print('     -------')
    # print('Total Utility : %.0f'%(U_hydrogen + U_carbon))
    # print('Total Cost    : %.0f'%(P_variable + P_fixed + P_capital + P_carbon + CCS_variable + D_variable + D_fixed + D_capital))
    # print('Total Surplus : %.0f'%(U_hydrogen + U_carbon - P_variable - P_fixed - P_capital - P_carbon - CCS_variable - D_variable - D_fixed - D_capital))
    # print('     -------')
    # print('Total Consumption [tons] : %.0f'%cons_H)


    ###
    ###make some prettier results
    ###






    #%% change in CO2 emissions

    # co2_0 = (m.H.consumers['size'] * m.H.consumers['breakevenCarbon_g_MJ'] * m.H.carbon_g_MJ_to_t_tH2).sum()

    # co2_f = consumption_df['co2_tons_nonHydrogenConsumption'].sum() +  production_df['co2_tons'].sum()

    # print ('change in CO2 emissions: ' + str(co2_f - co2_0) + ' tons CO2 per day')
    # print ('change in CO2 emissions: ' + str(round(((co2_f - co2_0) / co2_0) * 100, 1)) + ' percent')

    # #%% #spreadsheet of nodes
    # hub = 'freeport'
    # test_df = pandas.DataFrame([n for n in list(g.nodes) if (hub in g.nodes[n]['node'])])
    # test_df.to_clipboard()

    # #%% #spreadsheet of arcs
    # hub = 'freeport'
    # test_df = pandas.DataFrame([n for n in list(g.edges) if ((hub in g.nodes[n[0]]['node']) | (hub in g.nodes[n[1]]['node']))])
    # test_df.to_clipboard()

    # #%% distribution by hub

    # h = 'freeport_'

    # dist_hub_edges = distribution_df[(distribution_df['arc_start'].str.contains(h)) | (distribution_df['arc_end'].str.contains(h))]






