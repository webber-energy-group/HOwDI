import time

import numpy
import pandas
import pyomo
import pyomo.environ as pe

from hydrogen_model.create_graph import build_hydrogen_network

start = time.time()


class HydrogenInputs:
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
        self.ccs1_percent_co2_captured = self.ccs_data.loc[
            "ccs1", "percent_CO2_captured"
        ]
        self.ccs2_percent_co2_captured = self.ccs_data.loc[
            "ccs2", "percent_CO2_captured"
        ]
        self.ccs1_variable_usdPerTon = self.ccs_data.loc[
            "ccs1", "variable_usdPerTonCO2"
        ]
        self.ccs2_variable_usdPerTon = self.ccs_data.loc[
            "ccs2", "variable_usdPerTonCO2"
        ]

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
            m.ccs1_checs[p]
            * (m.prod_carbonRate[p] * (1 - m.H.ccs1_percent_co2_captured))
            + m.ccs2_checs[p]
            * (m.prod_carbonRate[p] * (1 - m.H.ccs2_percent_co2_captured))
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
            + m.ccs1_checs[p]
            * (m.prod_carbonRate[p] * (1 - m.H.ccs1_percent_co2_captured))
            + m.ccs2_checs[p]
            * (m.prod_carbonRate[p] * (1 - m.H.ccs2_percent_co2_captured))
            for p in m.producer_set
        )
        * m.H.carbon_price
    )

    # ccs variable cost per ton of produced hydrogen
    # TODO
    CCS_variable = sum(
        (m.ccs1_capacity_co2[p] * m.H.ccs1_variable_usdPerTon)
        + (m.ccs2_capacity_co2[p] * m.H.ccs2_variable_usdPerTon)
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
            * m.H.ccs1_percent_co2_captured
        )
        return constraint

    m.constr_ccs1CapacityRelationship = pe.Constraint(
        m.producer_set, rule=rule_ccs1CapacityRelationship
    )

    def rule_ccs2CapacityRelationship(m, node):
        """Define CCS2 CO2 Capacity

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
            * m.H.ccs2_percent_co2_captured
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
    m = pe.ConcreteModel()
    ## Load inputs into `hydrogen_inputs` object,
    ## which contains all input data
    m.H = HydrogenInputs(inputs=inputs, **input_parameters)

    ## create the network graph object
    m.g = build_hydrogen_network(m.H)

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
    results = solver.solve(m, tee=input_parameters["solver_debug"])
    # m.solutions.store_to(results)
    # results.write(filename='results.json', format='json')
    print("Model Solved with objective value {}".format(m.OBJ()))
    print("Time elapsed: %f" % (time.time() - start))

    return m
