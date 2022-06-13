"""
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
    
"""
import time

import numpy
import pandas
import pyomo
import pyomo.environ as pe

import hydrogen_model.create_graph as create_graph

start = time.time()


class hydrogen_inputs:
    """
    stores all of the input files needed to run the hydrogen model
    stores some hard coded variables used for the hydrogen model
    """

    def __init__(
        self,
        inputs,
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
        **kwargs
    ):
        """
        carbon_price_dollars_per_ton: dollars per ton penalty on CO2 emissions
        investment_interest: interest rate for financing capital investments
        investment_period: number of years over which capital is financed
        time_slices: used to get from investment_period units to the simulation timestep units. Default is 365 because the investment period units are in years (20 years default) and the simulation units are in days.
        """
        # generic data
        self.producers = pandas.DataFrame(inputs["production"])
        self.storage = pandas.DataFrame(inputs["storage"])
        self.distributors = pandas.DataFrame(inputs["distribution"])
        self.converters = pandas.DataFrame(inputs["conversion"])
        self.demand = pandas.DataFrame(inputs["demand"])
        self.ccs_data = pandas.DataFrame(inputs["ccs"])
        self.ccs_data.set_index("type", inplace=True)

        # data specific to the real world network being analyzed
        self.nodes = pandas.DataFrame(inputs["{}nodes".format(csv_prefix)])
        self.arcs = pandas.DataFrame(inputs["{}arcs".format(csv_prefix)])
        self.producers_existing = pandas.DataFrame(
            inputs["{}production_existing".format(csv_prefix)]
        )

        # Scalars
        # get rid of:
        self.e_price = industrial_electricity_usd_per_kwh
        self.ng_price = industrial_ng_usd_per_mmbtu
        self.time_slices = float(time_slices)
        self.carbon_price = float(carbon_price_dollars_per_ton)
        self.carbon_capture_credit = carbon_capture_credit_dollars_per_ton
        self.A = (
            # yearly amortized payment = capital cost / A
            (((1 + investment_interest) ** investment_period) - 1)
            / (investment_interest * (1 + investment_interest) ** investment_period)
        )
        # unit conversion 120,000 MJ/tonH2, 1,000,000 g/tonCO2:
        self.carbon_g_MJ_to_t_tH2 = 120000.0 / 1000000.0
        self.price_tracking_array = numpy.arange(**price_tracking_array)
        self.price_hubs = price_hubs
        self.price_demand = price_demand
        self.find_prices = find_prices

        # for the scenario where hydrogen infrastructure is subsidized
        self.subsidy_dollar_billion = subsidy_dollar_billion  # how many billions of dollars are available to subsidize infrastructure
        self.subsidy_cost_share_fraction = subsidy_cost_share_fraction  # what fraction of dollars must industry spend on new infrastructure--e.g., if = 0.6, then for a $10Billion facility, industry must spend $6Billion (which counts toward the objective function) and the subsidy will cover $4Billion (which is excluded from the objective function).


def create_node_sets(m):
    """Creates all pe.Sets associated with nodes used by the model"""
    # set of all nodes
    m.node_set = pe.Set(initialize=list(m.g.nodes()))

    # helpful iterable that contains tuples of node and respective class
    # saves memory
    nodes_with_class = m.g.nodes(data="class")

    # set of node names where all nodes are producers
    producer_nodes = [
        node for node, node_class in nodes_with_class if node_class == "producer"
    ]
    m.producer_set = pe.Set(initialize=producer_nodes)

    # set of node names where all nodes have existing production
    producer_existing_nodes = [
        node
        for node, producer_already_exists in m.g.nodes(data="existing")
        if producer_already_exists == 1
    ]
    m.producer_existing_set = pe.Set(initialize=producer_existing_nodes)

    # set of node names where all nodes are consumers,
    # which includes demandSectors and price hubs.
    consumer_nodes = [
        node
        for node, node_class in nodes_with_class
        if ("demandSector" in node_class) or (node_class == "price")
    ]
    m.consumer_set = pe.Set(initialize=consumer_nodes)

    # set of node names where all nodes are converters
    conversion_nodes = [
        node for node, node_class in nodes_with_class if "converter" in node_class
    ]
    m.converter_set = pe.Set(initialize=conversion_nodes)

    # set of node names where all nodes are fuelDispensers
    fuelStation_nodes = [
        node for node, node_class in nodes_with_class if "fuelDispenser" in node_class
    ]
    m.fuelStation_set = pe.Set(initialize=fuelStation_nodes)

    # set of node names where all nodes are truck distribution nodes
    truck_nodes = [
        node for node, node_class in nodes_with_class if "dist_truck" in node_class
    ]
    m.truck_set = pe.Set(initialize=truck_nodes)


def create_arc_sets(m):
    """Creates all pe.Sets associated with arcs used by the model"""
    # set of all arcs
    m.arc_set = pe.Set(initialize=list(m.g.edges()), dimen=None)

    # helpful iterable that saves memory since it is used a few times
    edges_with_class = m.g.edges(data="class")

    distribution_arcs = [
        (node1, node2)
        for node1, node2, class_type in edges_with_class
        if class_type != None
    ]
    m.distribution_arcs = pe.Set(initialize=distribution_arcs)

    # set of all existing arcs (i.e., pipelines)
    distribution_arcs_existing = [
        (node1, node2)
        for node1, node2, already_exists in m.g.edges(data="existing")
        if already_exists == True
    ]
    m.distribution_arc_existing_set = pe.Set(initialize=distribution_arcs_existing)

    # set of all arcs that have flow to a demand sector
    consumer_arcs = [
        (node1, node2)
        for node1, node2, class_type in edges_with_class
        if class_type == "flow_to_demand_sector"
    ]
    m.consumer_arc_set = pe.Set(initialize=consumer_arcs)

    # set of all arcs where either node is a consumer
    conversion_arcs = [
        (node1, node2)
        for node1, node2 in m.g.edges()
        if ("converter" in m.g.nodes[node1]["class"])
        or ("converter" in m.g.nodes[node2]["class"])
    ]
    m.converter_arc_set = pe.Set(initialize=conversion_arcs)


def create_params(m):
    """Loads parameters from network object (m.g) into pe.Param objects, which are used as coefficients in the model objective"""
    # TODO Add units ?

    ## Distribution
    m.dist_cost_capital = pe.Param(
        m.distribution_arcs,
        initialize=lambda m, i, j: m.g.adj[i][j].get("capital_usdPerUnit", 0),
    )
    m.dist_cost_fixed = pe.Param(
        m.distribution_arcs,
        initialize=lambda m, i, j: m.g.adj[i][j].get("fixed_usdPerUnitPerDay", 0),
    )
    m.dist_cost_variable = pe.Param(
        m.distribution_arcs,
        initialize=lambda m, i, j: m.g.adj[i][j].get("variable_usdPerTon", 0),
    )
    m.dist_flowLimit = pe.Param(
        m.distribution_arcs,
        initialize=lambda m, i, j: m.g.adj[i][j].get("flowLimit_tonsPerDay", 0),
    )

    ## Production
    m.prod_cost_capital_coeff = pe.Param(
        m.producer_set,
        initialize=lambda m, i: m.g.nodes[i].get("capital_usd_coefficient", 0),
    )
    m.prod_cost_fixed = pe.Param(
        m.producer_set, initialize=lambda m, i: m.g.nodes[i].get("fixed_usdPerTon", 0)
    )
    m.prod_kwh_variable_coeff = pe.Param(
        m.producer_set, initialize=lambda m, i: m.g.nodes[i].get("kWh_coefficient", 0)
    )
    m.prod_ng_variable_coeff = pe.Param(
        m.producer_set, initialize=lambda m, i: m.g.nodes[i].get("ng_coefficient", 0)
    )
    m.prod_cost_variable = pe.Param(
        m.producer_set,
        initialize=lambda m, i: m.g.nodes[i].get("variable_usdPerTon", 0),
    )
    m.prod_carbonRate = pe.Param(
        m.producer_set,
        initialize=lambda m, i: m.g.nodes[i].get("carbon_g_MJ", 0)
        * m.H.carbon_g_MJ_to_t_tH2,
    )
    m.prod_utilization = pe.Param(
        m.producer_set, initialize=lambda m, i: m.g.nodes[i].get("utilization", 0)
    )

    ## Conversion
    m.conv_cost_capital_coeff = pe.Param(
        m.converter_set,
        initialize=lambda m, i: m.g.nodes[i].get("capital_usd_coefficient", 0),
    )
    m.conv_cost_fixed = pe.Param(
        m.converter_set,
        initialize=lambda m, i: m.g.nodes[i].get("fixed_usdPerTonPerDay", 0),
    )
    m.conv_kwh_variable_coeff = pe.Param(
        m.converter_set, initialize=lambda m, i: m.g.nodes[i].get("kWh_coefficient", 0)
    )
    m.conv_cost_variable = pe.Param(
        m.converter_set,
        initialize=lambda m, i: m.g.nodes[i].get("variable_usdPerTon", 0),
    )
    m.conv_utilization = pe.Param(
        m.converter_set, initialize=lambda m, i: m.g.nodes[i].get("utilization", 0)
    )

    ## Consumption
    m.cons_price = pe.Param(
        m.consumer_set, initialize=lambda m, i: m.g.nodes[i].get("breakevenPrice", 0)
    )
    m.cons_size = pe.Param(
        m.consumer_set, initialize=lambda m, i: m.g.nodes[i].get("size", 0)
    )
    m.cons_carbonSensitive = pe.Param(
        m.consumer_set, initialize=lambda m, i: m.g.nodes[i].get("carbonSensitive", 0)
    )
    m.cons_breakevenCarbon = pe.Param(
        m.consumer_set,
        initialize=lambda m, i: m.g.nodes[i].get("breakevenCarbon_g_MJ", 0)
        * m.H.carbon_g_MJ_to_t_tH2,
    )

    ## CCS Retrofitting
    # binary, 1: producer can build CCS1, defaults to zero
    m.can_ccs1 = pe.Param(
        m.producer_set, initialize=lambda m, i: m.g.nodes[i].get("can_ccs1", 0)
    )
    # binary, 1: producer can build CCS2, defaults to zero
    m.can_ccs2 = pe.Param(
        m.producer_set, initialize=lambda m, i: m.g.nodes[i].get("can_ccs2", 0)
    )


def create_variables(m):
    """Creates variables associated with model"""
    # TODO once we have definitions written out for all of these, add the definitions and units here

    ## Distribution
    # daily capacity of each arc
    m.dist_capacity = pe.Var(m.arc_set, domain=pe.NonNegativeIntegers)
    # daily flow along each arc
    m.dist_h = pe.Var(m.arc_set, domain=pe.NonNegativeReals)

    ## Production
    # binary that tracks if a producer was built or not
    m.prod_exists = pe.Var(m.producer_set, domain=pe.Binary)
    # daily capacity of each producer
    m.prod_capacity = pe.Var(m.producer_set, domain=pe.NonNegativeReals)
    # daily production of each producer
    m.prod_h = pe.Var(m.producer_set, domain=pe.NonNegativeReals)

    ## Conversion
    # daily capacity of each converter
    m.conv_capacity = pe.Var(m.converter_set, domain=pe.NonNegativeReals)

    # Consumption
    # consumer's daily demand for hydrogen
    m.cons_h = pe.Var(m.consumer_set, domain=pe.NonNegativeReals)
    # consumer's daily demand for CHECs
    m.cons_checs = pe.Var(m.consumer_set, domain=pe.NonNegativeReals)

    ## CCS Retrofitting
    m.ccs1_built = pe.Var(m.producer_set, domain=pe.Binary)
    m.ccs2_built = pe.Var(m.producer_set, domain=pe.Binary)
    # daily capacity of CCS1 for each producer in tons CO2
    m.ccs1_capacity_co2 = pe.Var(m.producer_set, domain=pe.NonNegativeReals)
    # daily capacity of CCS2 for each producer in tons CO2
    m.ccs2_capacity_co2 = pe.Var(m.producer_set, domain=pe.NonNegativeReals)
    # daily capacity of CCS1 for each producer in tons h2
    m.ccs1_capacity_h2 = pe.Var(m.producer_set, domain=pe.NonNegativeReals)
    # daily capacity of CCS2 for each producer in tons h2
    m.ccs2_capacity_h2 = pe.Var(m.producer_set, domain=pe.NonNegativeReals)

    ## Carbon accounting
    # daily production of CHECs for each producer (sans retrofitted CCS)
    m.prod_checs = pe.Var(m.producer_set, domain=pe.NonNegativeReals)
    # daily production of CHECs for CCS1 for each producer
    m.ccs1_checs = pe.Var(m.producer_set, domain=pe.NonNegativeReals)
    # daily production of CHECs for CCS2 for each producer
    m.ccs2_checs = pe.Var(m.producer_set, domain=pe.NonNegativeReals)
    # carbon emissions for each consumer that is not using hydrogen
    m.co2_nonHydrogenConsumer = pe.Var(m.consumer_set, domain=pe.Reals)
    # carbon emissions for each hydrogen producer
    m.co2_emitted = pe.Var(m.producer_set, domain=pe.Reals)

    ## Infrastructure subsidy
    # subsidy dollars used to reduce the capital cost of converter[cv]
    m.fuelStation_cost_capital_subsidy = pe.Var(
        m.fuelStation_set, domain=pe.NonNegativeReals
    )


def obj_rule(m):
    """Defines the objective function.

    Some values are described as "regional prices", which means that a
    regional cost multiplier was used in `create_graph.py` to get
    the regional coefficient
    """
    # TODO units?

    # get data needed from m.H:
    ccs1_percent_co2_captured = m.H.ccs_data.loc["ccs1", "percent_CO2_captured"]
    ccs2_percent_co2_captured = m.H.ccs_data.loc["ccs2", "percent_CO2_captured"]
    ccs1_varible_usdPerTon = m.H.ccs_data.loc["ccs1", "variable_usdPerTonCO2"]
    ccs2_varible_usdPerTon = m.H.ccs_data.loc["ccs2", "variable_usdPerTonCO2"]

    ## Utility

    # consumer daily utility from buying hydrogen is the sum of
    # [(consumption of hydrogen at a node) * (price of hydrogen at a node)]
    # over all consumers
    U_hydrogen = sum(m.cons_h[c] * m.cons_price[c] for c in m.consumer_set)

    # consumer daily utility from buying checs (clean hydrogen energy credits) is the sum of
    # [(amount of checs consumed at a node * TODO ... at a node * carbon price)]
    # over all consumers
    U_carbon = (
        sum(m.cons_checs[c] * m.cons_breakevenCarbon[c] for c in m.consumer_set)
        * m.H.carbon_price
    )

    # TODO describe this equation
    U_carbon_capture_credit = (
        sum(
            m.ccs1_checs[p] * (m.prod_carbonRate[p] * (1 - ccs1_percent_co2_captured))
            + m.ccs2_checs[p] * (m.prod_carbonRate[p] * (1 - ccs2_percent_co2_captured))
            for p in m.producer_set
        )
        * m.H.carbon_capture_credit
    )

    ## Production

    # Variable costs of production per ton is the sum of
    # (the produced hydrogen at a node) * (the cost to produce hydrogen at that node)
    # over all producers
    P_variable = sum(m.prod_h[p] * m.prod_cost_variable[p] for p in m.producer_set)

    # daily electricity cost
    # TODO this is going to change
    P_electricity = (
        sum(m.prod_h[p] * m.prod_kwh_variable_coeff[p] for p in m.producer_set)
        * m.H.e_price
    )

    # daily natural gas cost
    # TODO this is going to change
    P_naturalGas = (
        sum(m.prod_h[p] * m.prod_ng_variable_coeff[p] for p in m.producer_set)
        * m.H.ng_price
    )

    # The fixed cost of production per ton is the sum of
    # (the capacity of a producer) * (the fixed regional cost of a producer)
    # for each producer
    P_fixed = sum(m.prod_capacity[p] * m.prod_cost_fixed[p] for p in m.producer_set)

    # The daily capital costs of production per ton are
    # (the production capacity of a node) * (the regional capital cost coefficient of a node) / amortization factor
    # for each producer
    P_capital = (
        sum(m.prod_capacity[p] * m.prod_cost_capital_coeff[p] for p in m.producer_set)
        / m.H.A
        / m.H.time_slices
    )

    # Daily price of producing checs (clean hydrogen energy credits) is the sum of
    # TODO
    P_carbon = (
        sum(
            m.prod_checs[p] * m.prod_carbonRate[p]
            + m.ccs1_checs[p] * (m.prod_carbonRate[p] * (1 - ccs1_percent_co2_captured))
            + m.ccs2_checs[p] * (m.prod_carbonRate[p] * (1 - ccs2_percent_co2_captured))
            for p in m.producer_set
        )
        * m.H.carbon_price
    )

    # ccs variable cost per ton of produced hydrogen
    # TODO
    CCS_variable = sum(
        (m.ccs1_capacity_co2[p] * ccs1_varible_usdPerTon)
        + (m.ccs2_capacity_co2[p] * ccs2_varible_usdPerTon)
        for p in m.producer_set
    )

    ## Distribution

    # The daily variable cost of distribution is the sum of
    # (hydrogen distributed) * (variable cost of distribution)
    # for each distribution arc
    D_variable = sum(m.dist_h[d] * m.dist_cost_variable[d] for d in m.distribution_arcs)

    # The daily fixed cost of distribution is the sum of
    # (distribution capacity) * (regional fixed cost)
    # for each distribution arc
    D_fixed = sum(
        m.dist_capacity[d] * m.dist_cost_fixed[d] for d in m.distribution_arcs
    )

    # The daily capital cost of distribution is the sum of
    # (distribution capacity) * (regional capital cost) / amortization factor
    D_capital = sum(
        (m.dist_capacity[d] * m.dist_cost_capital[d]) / m.H.A / m.H.time_slices
        for d in m.distribution_arcs
    )

    ## Converters

    # The daily variable cost of conversion is the sum of
    # (conversion capacity) * (conversion utilization) * (conversion variable costs)
    # for each convertor
    CV_variable = sum(
        m.conv_capacity[cv] * m.conv_utilization[cv] * m.conv_cost_variable[cv]
        for cv in m.converter_set
    )

    # TODO will change once electricity format is changed
    CV_electricity = sum(
        (m.conv_capacity[cv] * m.conv_utilization[cv] * m.conv_kwh_variable_coeff[cv])
        * m.H.e_price
        for cv in m.converter_set
    )

    # The daily fixed cost of conversion is the sum of
    # (convertor capacity) * (regional fixed cost)
    # for each convertor
    CV_fixed = sum(
        m.conv_capacity[cv] * m.conv_cost_fixed[cv] for cv in m.converter_set
    )

    # The daily fixed cost of conversion is the sum of
    # (convertor capacity) * (regional capital cost) / (amortization factor)
    # for each convertor
    CV_capital = sum(
        (m.conv_capacity[cv] * m.conv_cost_capital_coeff[cv]) / m.H.A / m.H.time_slices
        for cv in m.converter_set
    )

    # TODO fuel station subsidy
    CV_fuelStation_subsidy = sum(
        m.fuelStation_cost_capital_subsidy[fs] / m.H.A / m.H.time_slices
        for fs in m.fuelStation_set
    )

    totalSurplus = (
        U_hydrogen
        + U_carbon
        + U_carbon_capture_credit
        - P_variable
        - P_electricity
        - P_naturalGas
        - P_fixed
        - P_capital
        - P_carbon
        - CCS_variable
        - D_variable
        - D_fixed
        - D_capital
        - CV_variable
        - CV_electricity
        - CV_fixed
        - CV_capital
        + CV_fuelStation_subsidy
    )
    return totalSurplus


def apply_constraints(m):
    """Applies constraints to the model"""

    ## Distribution

    def rule_flowBalance(m, node):
        """Mass conservation for each node

        Constraint:
            sum of(
                + flow into a node
                - flow out a node
                + flow produced by a node
                - flow consumed by a node
                ) == 0

        Set:
            All nodes
        """
        expr = 0
        if m.g.in_edges(node):
            expr += pe.summation(m.dist_h, index=m.g.in_edges(node))
        if m.g.out_edges(node):
            expr += -pe.summation(m.dist_h, index=m.g.out_edges(node))
        # the equality depends on whether the node is a producer, consumer, or hub
        if node in m.producer_set:  # if producer:
            constraint = m.prod_h[node] + expr == 0.0
        elif node in m.consumer_set:  # if consumer:
            constraint = expr - m.cons_h[node] == 0.0
        else:  # if hub:
            constraint = expr == 0.0
        return constraint

    m.constr_flowBalance = pe.Constraint(m.node_set, rule=rule_flowBalance)

    def rule_flowCapacityExisting(m, startNode, endNode):
        """Force existing pipelines

        Constraint:
            Existing pipelines' capacity is greater than or equal to 1

        Set:
            Existing distribution arcs (existing pipelines)
        """
        constraint = (
            m.dist_capacity[startNode, endNode]
            >= m.g.edges[startNode, endNode]["existing"]
        )
        return constraint

    m.constr_flowCapacityExisting = pe.Constraint(
        m.distribution_arc_existing_set, rule=rule_flowCapacityExisting
    )

    def rule_flowCapacity(m, startNode, endNode):
        """Capacity-distribution relationship

        Constraint:
            (amount of hydrogen through a distribution arc)
            <=
            (capacity of the arc (# of pipelines or trucks))
            * (the allowable flow through one unit of capacity)

        Set:
            All distribution arcs
        """
        constraint = (
            m.dist_h[startNode, endNode]
            <= m.dist_capacity[startNode, endNode]
            * m.dist_flowLimit[startNode, endNode]
        )
        return constraint

    m.constr_flowCapacity = pe.Constraint(m.distribution_arcs, rule=rule_flowCapacity)

    def rule_truckConsistency(m, truck_dist_node):
        """Truck mass balance

        Constraint:
            The number of trucks entering a node must be >=
            the number of trucks leaving a node

        Set:
            All nodes relevant to trucks (all distribution
            nodes in distribution.csv that include truck)
        """
        in_trucks = pe.summation(m.dist_capacity, index=m.g.in_edges(truck_dist_node))
        out_trucks = pe.summation(m.dist_capacity, index=m.g.out_edges(truck_dist_node))

        constraint = in_trucks - out_trucks >= 0
        return constraint

    m.const_truckConsistency = pe.Constraint(m.truck_set, rule=rule_truckConsistency)

    def rule_flowCapacityConverters(m, converterNode):
        """Flow across a convertor is limited
        by the capacity of the conversion node

        Note: utilization =/= efficiency

        Constraint:
            flow out of a conversion node <=
            (capacity of convertor) * (utilization of convertor)

        Set:
            All convertor nodes
        """
        flow_out = pe.summation(m.dist_h, index=m.g.out_edges(converterNode))
        constraint = (
            flow_out
            <= m.conv_capacity[converterNode] * m.conv_utilization[converterNode]
        )
        return constraint

    m.constr_flowCapacityConverters = pe.Constraint(
        m.converter_set, rule=rule_flowCapacityConverters
    )

    def rule_flowCapacityBetweenConverters(m, converterNode):
        """Convertor mass balance

        TODO Work on this constraint as I don't think it is correct yet.
        If the <= is changed to == or >=, the number of trucks at a distribution
        node is not correct. But with the constraint, the it build too much capacity at
        other convertors.

        For convertors, the capacity is the de facto
        distribution capacity at the end of the chain of conversion.

        A conversion capacity of x would mean that the convertor is supplying
        x dist_pipeline (always 1 since this is a local node) or
        x dist_trucks (which is the number of trucks)

        Constraint:
            Flow capacity in <= flow capacity out (?)

        Set:
            All convertors (?)
        """
        in_capacity = pe.summation(m.dist_capacity, index=m.g.in_edges(converterNode))
        out_capacity = pe.summation(m.dist_capacity, index=m.g.out_edges(converterNode))
        constraint = in_capacity - out_capacity <= 0
        return constraint

    m.constr_flowCapacityBetweenConverters = pe.Constraint(
        m.converter_set, rule=rule_flowCapacityBetweenConverters
    )

    ## production and ccs

    def rule_forceExistingProduction(m, node):
        """Existing production must be built

        Constraint:
            Binary tracking if producer built or not == 1

        Set:
            Existing producers
        """
        constraint = m.prod_exists[node] == True
        return constraint

    m.const_forceExistingProduction = pe.Constraint(
        m.producer_existing_set, rule=rule_forceExistingProduction
    )

    def rule_productionCapacityExisting(m, node):
        """Capacity of existing producers equals their existing capacity

        Constrains:
            Model's variable tracking capacity == existing capacity

        Set:
            Existing producers
        """
        constraint = m.prod_capacity[node] == m.g.nodes[node]["capacity_tonPerDay"]
        return constraint

    m.constr_productionCapacityExisting = pe.Constraint(
        m.producer_existing_set, rule=rule_productionCapacityExisting
    )

    def rule_productionCapacity(m, node):
        """Each producer's production capacity
        cannot exceed its capacity

        Constraint:
            production of hydrogen <=
            producer's capacity * producers utilization

        Set:
            All producers
        """
        constraint = m.prod_h[node] <= m.prod_capacity[node] * m.prod_utilization[node]
        return constraint

    m.constr_productionCapacity = pe.Constraint(
        m.producer_set, rule=rule_productionCapacity
    )

    def rule_minProductionCapacity(m, node):
        """Minimum bound of production for a producer
        (only on new producers)

        Constraint:
            Produced hydrogen >=
            allowed minimum value * binary tracking if producer is built

            If prod_exists is zero, the minimum allowed hydrogen production is zero.
            Paired with the maximum constraint, the forces capacity of producers
            not built to be zero.

        Set:
            All producer nodes, but all potential producer nodes in effect
        """
        if node in m.producer_existing_set:
            # if producer is an existing producer, don't constrain by minimum value
            constraint = m.prod_h[node] >= 0
        else:
            # multiply by "prod_exists" (a binary) so that constraint is only enforced if the producer exists
            # this gives the model the option to not build the producer
            constraint = (
                m.prod_h[node] >= m.g.nodes[node]["min_h2"] * m.prod_exists[node]
            )
        return constraint

    m.constr_minProductionCapacity = pe.Constraint(
        m.producer_set, rule=rule_minProductionCapacity
    )

    def rule_maxProductionCapacity(m, node):
        """M bound of production for a producer
        (only on new producers)

        Constraint:
            Produced hydrogen <=
            allowed maximum value * binary tracking if producer is built

            If prod_exists is zero, the maximum allowed hydrogen production is zero
            Paired with the minimum constraint, the forces capacity of producers
            not built to be zero.

        Set:
            All producer nodes, but all potential producer nodes in effect
        """
        if node in m.producer_existing_set:
            # if producer is an existing producer, don't constrain by minimum value
            constraint = m.prod_h[node] <= 1e12  # arbitrarily large number
        else:
            # multiply by "prod_exists" (a binary) so that constraint is only enforced if the producer exists
            # with the prior constraint, forces 0 production if producer DNE
            constraint = (
                m.prod_h[node] <= m.g.nodes[node]["max_h2"] * m.prod_exists[node]
            )
        return constraint

    m.constr_maxProductionCapacity = pe.Constraint(
        m.producer_set, rule=rule_maxProductionCapacity
    )

    def rule_onlyOneCCS(m, node):
        """Existing producers can only build one of the ccs tech options

        Constraint:
            NAND(ccs1_built, ccs2_built)
            - but this can't be solved numerically, thus

            sum of (binary tracking if a ccs technology was built)
            over all ccs techs <= 1

        Set:
            All producers, defacto existing producers

        """
        constraint = m.ccs1_built[node] + m.ccs2_built[node] <= 1
        return constraint

    m.constr_onlyOneCCS = pe.Constraint(m.producer_set, rule=rule_onlyOneCCS)

    ccs1_percent_CO2_captured = m.H.ccs_data.loc["ccs1", "percent_CO2_captured"]

    def rule_ccs1CapacityRelationship(m, node):
        """Define CCS1 CO2 Capacity

        Constraint:
            Amount of CO2 captured ==
            the amount of hydrogen produced that went through CCS1
            * the amount of CO2 produced per unit of hydrogen produced
            * the efficiency of CCS1

        Set:
            All producers, defacto existing producers
        """
        constraint = (
            m.ccs1_capacity_co2[node] * m.can_ccs1[node]
            == m.ccs1_capacity_h2[node]
            * m.prod_carbonRate[node]
            * ccs1_percent_CO2_captured
        )
        return constraint

    m.constr_ccs1CapacityRelationship = pe.Constraint(
        m.producer_set, rule=rule_ccs1CapacityRelationship
    )

    ccs2_percent_CO2_captured = m.H.ccs_data.loc["ccs2", "percent_CO2_captured"]

    def rule_ccs2CapacityRelationship(m, node):
        """Define CCS1 CO2 Capacity

        Constraint:
            Amount of CO2 captured ==
            the amount of hydrogen produced that went through CCS1
            * the amount of CO2 produced per unit of hydrogen produced
            * the efficiency of CCS1

        Set:
            All producers, defacto existing producers
        """
        constraint = (
            m.ccs2_capacity_co2[node] * m.can_ccs2[node]
            == m.ccs2_capacity_h2[node]
            * m.prod_carbonRate[node]
            * ccs2_percent_CO2_captured
        )
        return constraint

    m.constr_ccs2CapacityRelationship = pe.Constraint(
        m.producer_set, rule=rule_ccs2CapacityRelationship
    )

    def rule_mustBuildAllCCS1(m, node):
        """To build CCS1, it must be built over the entire possible capacity

        Constraint:
            If CCS1 is built:
                Amount of hydrogen through CCS1 == Amount of hydrogen produced

        Set:
            All producers, defacto existing producers
        """
        constraint = m.ccs1_capacity_h2[node] == m.ccs1_built[node] * m.prod_h[node]
        return constraint

    m.constr_mustBuildAllCCS1 = pe.Constraint(
        m.producer_set, rule=rule_mustBuildAllCCS1
    )

    def rule_mustBuildAllCCS2(m, node):
        """To build CCS2, it must be built over the entire possible capacity

        Constraint:
            If CCS2 is built:
                Amount of hydrogen through CCS2 == Amount of hydrogen produced

        Set:
            All producers, defacto existing producers
        """
        constraint = m.ccs2_capacity_h2[node] == m.ccs2_built[node] * m.prod_h[node]
        return constraint

    m.constr_mustBuildAllCCS2 = pe.Constraint(
        m.producer_set, rule=rule_mustBuildAllCCS2
    )

    def rule_ccs1Checs(m, node):
        """CHECs produced from CCS1 cannot exceed the clean hydrogen from CCS1

        Constraint:
            CHECs from CCS1 <= Clean Hydrogen as a result of CCS1

        Set:
            All producers, defacto existing producers
        """
        constraint = m.ccs1_checs[node] <= m.ccs1_capacity_h2[node]
        return constraint

    m.constr_ccs1Checs = pe.Constraint(m.producer_set, rule=rule_ccs1Checs)

    def rule_ccs2Checs(m, node):
        """CHECs produced from CCS2 cannot exceed the clean hydrogen from CCS2

        Constraint:
            CHECs from CCS2 <= Clean Hydrogen as a result of CCS2

        Set:
            All producers, defacto existing producers
        """
        constraint = m.ccs2_checs[node] <= m.ccs2_capacity_h2[node]
        return constraint

    m.constr_ccs2Checs = pe.Constraint(m.producer_set, rule=rule_ccs2Checs)

    def rule_productionChec(m, node):
        """CHEC production cannot exceed hydrogen production

        Constraint:
            CHECs produced <= hydrogen produced

        Set:
            All producers
        """

        total_checs_produced = (
            m.prod_checs[node] + m.ccs1_checs[node] + m.ccs2_checs[node]
        )

        constraint = total_checs_produced <= m.prod_h[node]
        return constraint

    m.constr_productionChecs = pe.Constraint(m.producer_set, rule=rule_productionChec)

    ## Consumption

    def rule_consumerSize(m, node):
        """Each consumer's consumption cannot exceed its size

        Constraint:
            consumed hydrogen <= consumption size

        Set:
            All consumers
        """
        constraint = m.cons_h[node] <= m.cons_size[node]
        return constraint

    m.constr_consumerSize = pe.Constraint(m.consumer_set, rule=rule_consumerSize)

    def rule_consumerChecs(m, node):
        """Each carbon-sensitive consumer's consumption of CHECs
            equals its consumption of hydrogen

        Constraint:
            consumer CHECs ==
                consumed hydrogen * binary tracking if consumer is carbon-sensitive

        Set:
            ALl consumers
        """
        constraint = m.cons_checs[node] == m.cons_h[node] * m.cons_carbonSensitive[node]
        return constraint

    m.constr_consumerChec = pe.Constraint(m.consumer_set, rule=rule_consumerChecs)

    ## Carbon Accounting

    def rule_checsBalance(m):
        """CHECs mass balance

        Constraint:
            total CHECs consumed <= checs produced

        Set:
            All producers and consumers

        TODO prod_checs not fully implemented
        """
        checs_produced = sum(
            m.prod_checs[p] + m.ccs1_checs[p] + m.ccs2_checs[p] for p in m.producer_set
        )
        checs_consumed = sum(m.cons_checs[c] for c in m.consumer_set)
        constraint = checs_consumed <= checs_produced
        return constraint

    m.constr_checsBalance = pe.Constraint(rule=rule_checsBalance)

    def rule_co2Producers(m, node):
        """CO2 Production

        Constraint:
            CO2 emitted ==
                carbon produced per ton of hydrogen * (
                    hydrogen produced - clean hydrogen produced by CCS
                )

        Set:
            All producers
        """
        ccs1_clean_hydrogen = (
            m.ccs1_capacity_h2[node] * m.H.ccs_data.loc["ccs1", "percent_CO2_captured"]
        )
        cc2_clean_hydrogen = (
            m.ccs2_capacity_h2[node] * m.H.ccs_data.loc["ccs2", "percent_CO2_captured"]
        )

        constraint = m.co2_emitted[node] == m.prod_carbonRate[node] * (
            m.prod_h[node] - (ccs1_clean_hydrogen + cc2_clean_hydrogen)
        )
        return constraint

    m.constr_co2Producers = pe.Constraint(m.producer_set, rule=rule_co2Producers)

    # co2 emissions for consumers that are not using hydrogen
    def rule_co2Consumers(m, node):
        """CO2 from consumption that was not satisfied with Hydrogen -
            i.e., CO2 from the existing methods of satisfying demand
            that were not displaced by hydrogen infrastructure

        Constraint:
            Amount of CO2 produced by demand not satisfied with H2 ==

        Set:
            All consumers

        TODO Double check description
        """
        consumer_co2_rate = m.cons_breakevenCarbon[node]
        consumption_not_satisfied_by_h2 = m.cons_size[node] - m.cons_h[node]

        constraint = (
            m.co2_nonHydrogenConsumer[node]
            == consumption_not_satisfied_by_h2 * consumer_co2_rate
        )
        return constraint

    m.constr_co2Consumers = pe.Constraint(m.consumer_set, rule=rule_co2Consumers)

    ###subsidy for infrastructure
    # total subsidy dollars must be less than or equal to the available subsidy funds
    # =============================================================================
    # def rule_subsidyTotal(m, node):
    #     constraint = sum(m.fuelStation_cost_capital_subsidy[fs] for fs in m.fuelStation_set) <= (m.H.subsidy_dollar_billion * 1E9)
    #     return constraint
    # m.constr_subsidyTotal = pe.Constraint(rule=rule_subsidyTotal)
    # =============================================================================

    # conversion facility subsidies
    def rule_subsidyConverter(m, node):
        """Subsidies for a convertor is equal to the cost share fraction

        Constraint:
            Subsidies from conversion ==
                Cost of conversion * fraction of cost paid by subsidies

        Set:
            All fuel stations
        """

        conversion_cost = m.conv_capacity[node] * m.conv_cost_capital_coeff[node]

        constraint = m.fuelStation_cost_capital_subsidy[node] == conversion_cost * (
            1 - m.H.subsidy_cost_share_fraction
        )
        # note that existing production facilities have a cost_capital_coeff of zero, so they cannot be subsidized
        return constraint

    m.constr_subsidyConverter = pe.Constraint(
        m.fuelStation_set, rule=rule_subsidyConverter
    )


def build_h2_model(inputs, input_parameters):
    print("Building model")
    ## Load inputs into `hydrogen_inputs` object,
    ## which contains all input data
    H = hydrogen_inputs(inputs=inputs, **input_parameters)

    ## create the network graph object
    H_network = create_graph.hydrogen_network(H)
    g = H_network.g

    ## create the pyomo model object and load the inputs and graph objects into it
    m = pe.ConcreteModel()
    m.H = H
    m.g = g

    ## Define sets, which are efficient ways of classifying nodes and arcs
    create_node_sets(m)
    create_arc_sets(m)

    # Create parameters, which are the coefficients in the equation
    create_params(m)

    # Create variables
    create_variables(m)

    # objective function
    # maximize total surplus
    m.OBJ = pe.Objective(rule=obj_rule, sense=pe.maximize)

    # apply constraints
    apply_constraints(m)

    # solve model
    print("Time elapsed: %f" % (time.time() - start))
    print("Solving model")
    solver = pyomo.opt.SolverFactory(input_parameters["solver"])
    solver.options["mipgap"] = 0.01
    results = solver.solve(m, tee=False)
    # m.solutions.store_to(results)
    # results.write(filename='results.json', format='json')
    print("Model Solved with objective value {}".format(m.OBJ()))
    print("Time elapsed: %f" % (time.time() - start))

    return m

    ##

    # output
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
