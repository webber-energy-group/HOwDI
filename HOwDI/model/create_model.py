import time

import pyomo
import pyomo.environ as pe
from networkx import DiGraph

from HOwDI.model.HydrogenData import HydrogenData

start = time.time()


def create_node_sets(m: pe.ConcreteModel, g: DiGraph):
    """Creates all pe.Sets associated with nodes used by the model"""
    # set of all nodes
    m.node_set = pe.Set(initialize=list(g.nodes()))

    # helpful iterable that contains tuples of node and respective class
    # saves memory
    nodes_with_class = g.nodes(data="class")

    # set of node names where all nodes are producers
    producer_nodes = [
        node for node, node_class in nodes_with_class if node_class == "producer"
    ]
    m.producer_set = pe.Set(initialize=producer_nodes)

    # set of node names where all nodes have existing production
    producer_existing_nodes = [
        node
        for node, producer_already_exists in g.nodes(data="existing")
        if producer_already_exists == 1
    ]
    m.existing_producers = pe.Set(initialize=producer_existing_nodes)

    # set of potential producers
    m.new_producers = m.producer_set - m.existing_producers

    # set of new thermal producers
    producer_thermal = [
        node
        for node, prod_type in g.nodes(data="prod_tech_type")
        if prod_type == "thermal"
    ]
    m.thermal_producers = pe.Set(initialize=producer_thermal)

    m.new_thermal_producers = m.new_producers & m.thermal_producers

    m.new_electric_producers = m.new_producers - m.new_thermal_producers

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


def create_arc_sets(m: pe.ConcreteModel, g: DiGraph):
    """Creates all pe.Sets associated with arcs used by the model"""
    # set of all arcs
    m.arc_set = pe.Set(initialize=list(g.edges()), dimen=None)

    # helpful iterable that saves memory since it is used a few times
    edges_with_class = g.edges(data="class")

    distribution_arcs = [
        (node1, node2)
        for node1, node2, class_type in edges_with_class
        if class_type != None
    ]
    m.distribution_arcs = pe.Set(initialize=distribution_arcs)

    # set of all existing arcs (i.e., pipelines)
    distribution_arcs_existing = [
        (node1, node2)
        for node1, node2, already_exists in g.edges(data="existing")
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
        for node1, node2 in g.edges()
        if ("converter" in g.nodes[node1]["class"])
        or ("converter" in g.nodes[node2]["class"])
    ]
    m.converter_arc_set = pe.Set(initialize=conversion_arcs)


def create_params(m: pe.ConcreteModel, H: HydrogenData, g: DiGraph):
    """Loads parameters from network object (g) into pe.Param objects, which are
    used as coefficients in the model objective"""
    # TODO Add units ?

    ## Distribution
    m.dist_cost_capital = pe.Param(
        m.distribution_arcs,
        initialize=lambda m, i, j: g.adj[i][j].get("capital_usdPerUnit", 0),
    )
    m.dist_cost_fixed = pe.Param(
        m.distribution_arcs,
        initialize=lambda m, i, j: g.adj[i][j].get("fixed_usdPerUnitPerDay", 0),
    )
    m.dist_cost_variable = pe.Param(
        m.distribution_arcs,
        initialize=lambda m, i, j: g.adj[i][j].get("variable_usdPerTon", 0),
    )
    m.dist_flowLimit = pe.Param(
        m.distribution_arcs,
        initialize=lambda m, i, j: g.adj[i][j].get("flowLimit_tonsPerDay", 0),
    )

    ## Production
    m.prod_cost_capital = pe.Param(
        m.producer_set,
        initialize=lambda m, i: g.nodes[i].get("capital_usdPerTonPerDay", 0),
    )
    m.prod_cost_fixed = pe.Param(
        m.producer_set, initialize=lambda m, i: g.nodes[i].get("fixed_usdPerTon", 0)
    )
    m.prod_e_price = pe.Param(
        m.producer_set, initialize=lambda m, i: g.nodes[i].get("e_price", 0)
    )
    m.prod_ng_price = pe.Param(
        m.producer_set, initialize=lambda m, i: g.nodes[i].get("ng_price", 0)
    )
    m.prod_cost_variable = pe.Param(
        m.producer_set,
        initialize=lambda m, i: g.nodes[i].get("variable_usdPerTon", 0),
    )
    m.co2_emissions_rate = pe.Param(
        m.producer_set,
        initialize=lambda m, i: g.nodes[i].get("co2_emissions_per_h2_tons", 0),
    )
    m.grid_intensity = pe.Param(
        m.new_electric_producers,
        initialize=lambda m, i: g.nodes[i].get("grid_intensity_tonsCO2_per_h2"),
    )
    m.prod_utilization = pe.Param(
        m.producer_set, initialize=lambda m, i: g.nodes[i].get("utilization", 0)
    )
    m.chec_per_ton = pe.Param(
        m.new_producers, initialize=lambda m, i: g.nodes[i].get("chec_per_ton", 0)
    )
    m.ccs_capture_rate = pe.Param(
        m.new_thermal_producers,
        initialize=lambda m, i: g.nodes[i].get("ccs_capture_rate", 0),
    )
    m.h2_tax_credit = pe.Param(
        m.new_producers, initialize=lambda m, i: g.nodes[i].get("h2_tax_credit", 0)
    )

    ## Conversion
    m.conv_cost_capital = pe.Param(
        m.converter_set,
        initialize=lambda m, i: g.nodes[i].get("capital_usdPerTonPerDay", 0),
    )
    m.conv_cost_fixed = pe.Param(
        m.converter_set,
        initialize=lambda m, i: g.nodes[i].get("fixed_usdPerTonPerDay", 0),
    )
    m.conv_e_price = pe.Param(
        m.converter_set, initialize=lambda m, i: g.nodes[i].get("e_price", 0)
    )
    m.conv_cost_variable = pe.Param(
        m.converter_set,
        initialize=lambda m, i: g.nodes[i].get("variable_usdPerTon", 0),
    )
    m.conv_utilization = pe.Param(
        m.converter_set, initialize=lambda m, i: g.nodes[i].get("utilization", 0)
    )

    ## Consumption
    m.cons_price = pe.Param(
        m.consumer_set, initialize=lambda m, i: g.nodes[i].get("breakevenPrice", 0)
    )
    m.cons_size = pe.Param(
        m.consumer_set, initialize=lambda m, i: g.nodes[i].get("size", 0)
    )
    m.cons_carbonSensitive = pe.Param(
        m.consumer_set, initialize=lambda m, i: g.nodes[i].get("carbonSensitive", 0)
    )
    # consumer's current rate of carbon emissions
    m.avoided_emissions = pe.Param(
        m.consumer_set,
        initialize=lambda m, i: g.nodes[i].get("avoided_emissions_tonsCO2_per_H2", 0),
    )

    ## CCS Retrofitting
    # binary, 1: producer can build CCS1, defaults to zero
    m.can_ccs1 = pe.Param(
        m.producer_set, initialize=lambda m, i: g.nodes[i].get("can_ccs1", 0)
    )
    # binary, 1: producer can build CCS2, defaults to zero
    m.can_ccs2 = pe.Param(
        m.producer_set, initialize=lambda m, i: g.nodes[i].get("can_ccs2", 0)
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
    m.ccs1_built = pe.Var(m.existing_producers, domain=pe.Binary)
    m.ccs2_built = pe.Var(m.existing_producers, domain=pe.Binary)
    # daily capacity of CCS1 for each producer in tons CO2
    m.ccs1_co2_captured = pe.Var(m.existing_producers, domain=pe.NonNegativeReals)
    # daily capacity of CCS2 for each producer in tons CO2
    m.ccs2_co2_captured = pe.Var(m.existing_producers, domain=pe.NonNegativeReals)
    # daily capacity of CCS1 for each producer in tons h2
    m.ccs1_capacity_h2 = pe.Var(m.existing_producers, domain=pe.NonNegativeReals)
    # daily capacity of CCS2 for each producer in tons h2
    m.ccs2_capacity_h2 = pe.Var(m.existing_producers, domain=pe.NonNegativeReals)

    ## Carbon accounting
    # daily production of CHECs for each producer (sans retrofitted CCS)
    m.prod_checs = pe.Var(m.new_producers, domain=pe.NonNegativeReals)
    # daily production of CHECs for CCS1 for each producer
    m.ccs1_checs = pe.Var(m.existing_producers, domain=pe.NonNegativeReals)
    # daily production of CHECs for CCS2 for each producer
    m.ccs2_checs = pe.Var(m.existing_producers, domain=pe.NonNegativeReals)

    ## Infrastructure subsidy
    # subsidy dollars used to reduce the capital cost of converter[cv]
    m.fuelStation_cost_capital_subsidy = pe.Var(
        m.fuelStation_set, domain=pe.NonNegativeReals
    )


def obj_rule(m: pe.ConcreteModel, H: HydrogenData):
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

    # Utility gained with carbon capture with new SMR+CCS
    # Hydrogen produced (tons H2) * Total CO2 Produced (Tons CO2/ Tons H2)
    #    * % of CO2 Captured * Carbon Capture Price ($/Ton CO2)
    U_carbon_capture_credit_new = (
        sum(
            m.prod_h[p] * H.baseSMR_CO2_per_H2_tons * m.ccs_capture_rate[p]
            for p in m.new_thermal_producers
        )
        * H.carbon_capture_credit
    )

    # Utility gained by retrofitting existing SMR
    # CO2 captured (Tons CO2)  * Carbon Capture Price ($/Ton)
    U_carbon_capture_credit_retrofit = (
        sum(
            m.ccs1_co2_captured[p] + m.ccs2_co2_captured[p]
            for p in m.existing_producers
        )
        * H.carbon_capture_credit
    )

    # Utility gained by adding a per-ton-h2 produced tax credit
    U_h2_tax_credit = sum(m.prod_h[p] * m.h2_tax_credit[p] for p in m.new_producers)

    U_h2_tax_credit_retrofit_ccs = sum(
        m.ccs1_capacity_h2[p] * H.ccs1_h2_tax_credit
        + m.ccs2_capacity_h2[p] * H.ccs2_h2_tax_credit
        for p in m.existing_producers
    )

    # Utility gained from from avoiding emissions by switching to hydrogen
    U_carbon = (
        sum(m.cons_h[c] * m.avoided_emissions[c] for c in m.consumer_set)
    ) * H.carbon_price

    ## Production

    # Variable costs of production per ton is the sum of
    # (the produced hydrogen at a node) * (the cost to produce hydrogen at that node)
    # over all producers
    P_variable = sum(m.prod_h[p] * m.prod_cost_variable[p] for p in m.producer_set)

    # daily electricity cost (regional value for e_price)
    P_electricity = sum(m.prod_h[p] * m.prod_e_price[p] for p in m.producer_set)

    # daily natural gas cost (regional value for ng_price)
    P_naturalGas = sum(m.prod_h[p] * m.prod_ng_price[p] for p in m.producer_set)

    # The fixed cost of production per ton is the sum of
    # (the capacity of a producer) * (the fixed regional cost of a producer)
    # for each producer
    # P_fixed = sum(m.prod_capacity[p] * m.prod_cost_capital[p] for p in m.producer_set) * H.fixedcost_percent # add this 2% as term in settings file

    # The daily capital costs of production per ton are
    # (the production capacity of a node) * (the regional capital cost coefficient of a node)
    # / amortization factor for each producer
    P_capital = (
        sum(m.prod_capacity[p] * m.prod_cost_capital[p] for p in m.producer_set)
        / H.A
        / H.time_slices
        * (1 + H.fixedcost_percent)
    )

    # Cost of producing carbon is
    # [
    #   Produced Hydrogen (Ton H2) * CO2 Emissions (Ton CO2/ Ton H2)
    #   + H2 produced with existing SMR
    #       * total CO2 produced by SMR
    #       * (1 - ccs capture %)
    # ] * Price of carbon emissions ($/Ton CO2)
    #
    # CO2 emissions of new builds are (1 - ccs capture %) * H.baseSMr_CO2_per_H2_tons
    P_carbon = (
        sum(m.prod_h[p] * m.co2_emissions_rate[p] for p in m.new_producers)
        + sum(
            m.ccs1_capacity_h2[p] * m.co2_emissions_rate[p]
            for p in m.existing_producers
        )
        * (1 - H.ccs1_percent_co2_captured)
        + sum(
            m.ccs2_capacity_h2[p] * m.co2_emissions_rate[p]
            for p in m.existing_producers
        )
        * (1 - H.ccs2_percent_co2_captured)
    ) * H.carbon_price

    # Retrofitted ccs variable cost per ton of CO2 captured
    CCS_variable = sum(
        (m.ccs1_co2_captured[p] * H.ccs1_variable_usdPerTon)
        + (m.ccs2_co2_captured[p] * H.ccs2_variable_usdPerTon)
        for p in m.existing_producers
    )

    ## Distribution

    # The daily variable cost of distribution is the sum of
    # (hydrogen distributed) * (variable cost of distribution)
    # for each distribution arc
    D_variable = sum(m.dist_h[d] * m.dist_cost_variable[d] for d in m.distribution_arcs)

    # The daily fixed cost of distribution is the sum of
    # (distribution capacity) * (regional fixed cost)
    # for each distribution arc
    # D_fixed = sum(
    #     m.dist_capacity[d] * m.dist_cost_fixed[d] for d in m.distribution_arcs
    # )

    # The daily capital cost of distribution is the sum of
    # (distribution capacity) * (regional capital cost) / amortization factor
    D_capital = sum(
        (m.dist_capacity[d] * m.dist_cost_capital[d]) / H.A / H.time_slices
        for d in m.distribution_arcs
    ) * (1 + H.fixedcost_percent)

    ## Converters

    # The daily variable cost of conversion is the sum of
    # (conversion capacity) * (conversion utilization) * (conversion variable costs)
    # for each convertor
    CV_variable = sum(
        m.conv_capacity[cv] * m.conv_utilization[cv] * m.conv_cost_variable[cv]
        for cv in m.converter_set
    )

    # Cost of electricity, with a regional electricity price
    CV_electricity = sum(
        (m.conv_capacity[cv] * m.conv_utilization[cv] * m.conv_e_price[cv])
        for cv in m.converter_set
    )

    # The daily fixed cost of conversion is the sum of
    # (convertor capacity) * (regional fixed cost)
    # for each convertor
    # CV_fixed = sum(
    #    m.conv_capacity[cv] * m.conv_cost_fixed[cv] for cv in m.converter_set
    # )

    # The daily fixed cost of conversion is the sum of
    # (convertor capacity) * (regional capital cost) / (amortization factor)
    # for each convertor
    CV_capital = sum(
        (m.conv_capacity[cv] * m.conv_cost_capital[cv]) / H.A / H.time_slices
        for cv in m.converter_set
    ) * (1 + H.fixedcost_percent)

    # TODO fuel station subsidy
    # CV_fuelStation_subsidy = sum(
    #     m.fuelStation_cost_capital_subsidy[fs] / H.A / H.time_slices
    #    for fs in m.fuelStation_set
    # )

    totalSurplus = (
        U_hydrogen
        + U_carbon_capture_credit_new
        + U_carbon_capture_credit_retrofit
        + U_h2_tax_credit
        + U_h2_tax_credit_retrofit_ccs
        # + U_carbon
        - P_variable
        - P_electricity
        - P_naturalGas
        - P_capital
        - P_carbon
        - CCS_variable
        - D_variable
        - D_capital
        - CV_variable
        - CV_electricity
        - CV_capital
        # + CV_fuelStation_subsidy
    )
    return totalSurplus


def apply_constraints(m: pe.ConcreteModel, H: HydrogenData, g: DiGraph):
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
        if g.in_edges(node):
            expr += pe.summation(m.dist_h, index=g.in_edges(node))
        if g.out_edges(node):
            expr += -pe.summation(m.dist_h, index=g.out_edges(node))
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
            >= g.edges[startNode, endNode]["existing"]
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

    def rule_truckCapacityConsistency(m, truck_dist_node):
        """Truck mass balance

        Constraint:
            The number of trucks entering a node must be >=
            the number of trucks leaving a node

        Set:
            All nodes relevant to trucks (all distribution
            nodes in distribution.csv that include truck)
        """
        # in_trucks = pe.summation(m.dist_capacity, index=g.in_edges(truck_dist_node))
        # out_trucks = pe.summation(m.dist_capacity, index=g.out_edges(truck_dist_node))

        in_trucks = sum(
            m.dist_capacity[(in_node, truck_dist_node)]
            for in_node, _ in g.in_edges(truck_dist_node)
            if "converter" in in_node
        )
        out_trucks = sum(
            m.dist_capacity[(truck_dist_node, out_node)]
            for _, out_node in g.out_edges(truck_dist_node)
            if "converter" in out_node or "dist" in out_node or "demand" in out_node
        )

        constraint = in_trucks - out_trucks == 0
        return constraint

    m.const_truckConsistency = pe.Constraint(
        m.truck_set, rule=rule_truckCapacityConsistency
    )

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
        flow_out = pe.summation(m.dist_h, index=g.out_edges(converterNode))
        constraint = (
            flow_out
            <= m.conv_capacity[converterNode] * m.conv_utilization[converterNode]
        )
        return constraint

    m.constr_flowCapacityConverters = pe.Constraint(
        m.converter_set, rule=rule_flowCapacityConverters
    )

    ## Production

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
        m.existing_producers, rule=rule_forceExistingProduction
    )

    def rule_productionCapacityExisting(m, node):
        """Capacity of existing producers equals their existing capacity

        Constraint:
            Amount of capacity of producer in model == existing capacity

        Set:
            Existing producers

        NOTE maybe this could be removed to allow retirement of existing production
        """
        constraint = m.prod_capacity[node] == g.nodes[node]["capacity_tonPerDay"]
        return constraint

    m.constr_productionCapacityExisting = pe.Constraint(
        m.existing_producers, rule=rule_productionCapacityExisting
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
            New producers
        """
        # multiply by "prod_exists" (a binary) so that constraint is only enforced if the producer exists
        # this gives the model the option to not build the producer
        constraint = (
            m.prod_capacity[node] >= g.nodes[node]["min_h2"] * m.prod_exists[node]
        )
        return constraint

    m.constr_minProductionCapacity = pe.Constraint(
        m.new_producers, rule=rule_minProductionCapacity
    )

    def rule_maxProductionCapacity(m, node):
        """Upper bound of production for a producer
        (only on new producers)

        Constraint:
            Produced hydrogen <=
            allowed maximum value * binary tracking if producer is built

            If prod_exists is zero, the maximum allowed hydrogen production is zero
            Paired with the minimum constraint, the forces capacity of producers
            not built to be zero.

        Set:
            New producers
        """
        # multiply by "prod_exists" (a binary) so that constraint is only enforced
        # if the producer exists with the prior constraint, forces 0 production
        # if producer DNE
        constraint = (
            m.prod_capacity[node] <= g.nodes[node]["max_h2"] * m.prod_exists[node]
        )
        return constraint

    m.constr_maxProductionCapacity = pe.Constraint(
        m.new_producers, rule=rule_maxProductionCapacity
    )

    ## CCS (Retrofit)

    def rule_onlyOneCCS(m, node):
        """Existing producers can only build one of the ccs tech options

        Constraint:
            NAND(ccs1_built, ccs2_built)
            - but this can't be solved numerically, thus

            sum of (binary tracking if a ccs technology was built)
            over all ccs techs <= 1

        Set:
            Existing producers

        """
        constraint = m.ccs1_built[node] + m.ccs2_built[node] <= 1
        return constraint

    m.constr_onlyOneCCS = pe.Constraint(m.existing_producers, rule=rule_onlyOneCCS)

    def rule_ccs1CapacityRelationship(m, node):
        """Define CCS1 CO2 Capacity

        Constraint:
            Amount of CO2 captured ==
            the amount of hydrogen produced that went through CCS1
            * the amount of CO2 produced per unit of hydrogen produced
            * the efficiency of CCS1

        Set:
            Existing producers
        """
        constraint = (
            m.ccs1_co2_captured[node] * m.can_ccs1[node]
            == m.ccs1_capacity_h2[node]
            * m.co2_emissions_rate[node]
            * H.ccs1_percent_co2_captured
        )
        return constraint

    m.constr_ccs1CapacityRelationship = pe.Constraint(
        m.existing_producers, rule=rule_ccs1CapacityRelationship
    )

    def rule_ccs2CapacityRelationship(m, node):
        """Define CCS2 CO2 Capacity

        Constraint:
            Amount of CO2 captured ==
            the amount of hydrogen produced that went through CCS1
            * the amount of CO2 produced per unit of hydrogen produced
            * the efficiency of CCS1

        Set:
            Existing Producers
        """
        constraint = (
            m.ccs2_co2_captured[node] * m.can_ccs2[node]
            == m.ccs2_capacity_h2[node]
            * m.co2_emissions_rate[node]
            * H.ccs2_percent_co2_captured
        )
        return constraint

    m.constr_ccs2CapacityRelationship = pe.Constraint(
        m.existing_producers, rule=rule_ccs2CapacityRelationship
    )

    def rule_mustBuildAllCCS1(m, node):
        """To build CCS1, it must be built over the entire possible capacity

        Constraint:
            If CCS1 is built:
                Amount of hydrogen through CCS1 == Amount of hydrogen produced

        Set:
            Existing producers
        """
        constraint = m.ccs1_capacity_h2[node] == m.ccs1_built[node] * m.prod_h[node]
        return constraint

    m.constr_mustBuildAllCCS1 = pe.Constraint(
        m.existing_producers, rule=rule_mustBuildAllCCS1
    )

    def rule_mustBuildAllCCS2(m, node):
        """To build CCS2, it must be built over the entire possible capacity

        Constraint:
            If CCS2 is built:
                Amount of hydrogen through CCS2 == Amount of hydrogen produced

        Set:
            Existing producers
        """
        constraint = m.ccs2_capacity_h2[node] == m.ccs2_built[node] * m.prod_h[node]
        return constraint

    m.constr_mustBuildAllCCS2 = pe.Constraint(
        m.existing_producers, rule=rule_mustBuildAllCCS2
    )

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

    ## CHECs

    def rule_ccs1Checs(m, node):
        """CHECs produced from CCS1 cannot exceed the clean hydrogen from CCS1

        Constraint:
            CHECs from CCS1 <= Clean Hydrogen as a result of CCS1

        Set:
            All producers, defacto existing producers
        """
        if H.fractional_chec:
            constraint = (
                m.ccs1_checs[node]
                <= m.ccs1_capacity_h2[node] * H.ccs1_percent_co2_captured
            )
        else:
            constraint = m.ccs1_checs[node] <= m.ccs1_capacity_h2[node]
        return constraint

    m.constr_ccs1Checs = pe.Constraint(m.existing_producers, rule=rule_ccs1Checs)

    def rule_ccs2Checs(m, node):
        """CHECs produced from CCS2 cannot exceed the clean hydrogen from CCS2

        Constraint:
            CHECs from CCS2 <= Clean Hydrogen as a result of CCS2

        Set:
            All producers, defacto existing producers
        """
        if H.fractional_chec:
            constraint = (
                m.ccs2_checs[node]
                <= m.ccs2_capacity_h2[node] * H.ccs2_percent_co2_captured
            )
        else:
            constraint = m.ccs2_checs[node] <= m.ccs2_capacity_h2[node]
        return constraint

    m.constr_ccs2Checs = pe.Constraint(m.existing_producers, rule=rule_ccs2Checs)

    def rule_productionChec(m, node):
        """The amount of CHECs produced by a producer =
            hydrogen produced * checs / ton

            NOTE I don't think this is necessary, it is just a definition

        Constraint:
            CHECs produced == hydrogen produced * checs/ton

        Set:
            New producers
        """

        constraint = m.prod_checs[node] == m.prod_h[node] * m.chec_per_ton[node]
        return constraint

    m.constr_productionChecs = pe.Constraint(m.new_producers, rule=rule_productionChec)

    def rule_consumerChecs(m, node):
        """Each carbon-sensitive consumer's consumption of CHECs
            equals its consumption of hydrogen

            NOTE I don't think this is necessary, it is just a definition

        Constraint:
            consumer CHECs ==
                consumed hydrogen * binary tracking if consumer is carbon-sensitive

        Set:
            All consumers
        """
        constraint = m.cons_checs[node] == m.cons_h[node] * m.cons_carbonSensitive[node]
        return constraint

    m.constr_consumerChec = pe.Constraint(m.consumer_set, rule=rule_consumerChecs)

    def rule_checsBalance(m):
        """CHECs mass balance

        Constraint:
            total CHECs consumed <= checs produced

        Set:
            All producers and consumers
        """
        checs_produced = pe.summation(m.prod_checs)
        checs_produced += pe.summation(m.ccs1_checs)
        checs_produced += pe.summation(m.ccs2_checs)

        checs_consumed = pe.summation(m.cons_checs)

        constraint = checs_consumed <= checs_produced
        return constraint

    m.constr_checsBalance = pe.Constraint(rule=rule_checsBalance)

    ###subsidy for infrastructure
    # total subsidy dollars must be less than or equal to the available subsidy funds
    # =============================================================================
    # def rule_subsidyTotal(m, node):
    #     constraint = sum(m.fuelStation_cost_capital_subsidy[fs] for fs in m.fuelStation_set) <= (H.subsidy_dollar_billion * 1E9)
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

        conversion_cost = m.conv_capacity[node] * m.conv_cost_capital[node]

        constraint = m.fuelStation_cost_capital_subsidy[node] == conversion_cost * (
            1 - H.subsidy_cost_share_fraction
        )
        # note that existing production facilities have a cost_capital
        #  of zero, so they cannot be subsidized
        return constraint

    m.constr_subsidyConverter = pe.Constraint(
        m.fuelStation_set, rule=rule_subsidyConverter
    )


def build_h2_model(H: HydrogenData, g: DiGraph):
    print("Building model")
    m = pe.ConcreteModel()

    ## Define sets, which are efficient ways of classifying nodes and arcs
    create_node_sets(m, g)
    create_arc_sets(m, g)

    # Create parameters, which are the coefficients in the equation
    create_params(m, H, g)

    # Create variables
    create_variables(m)

    # objective function
    # maximize total surplus
    m.OBJ = pe.Objective(rule=obj_rule(m, H), sense=pe.maximize)

    # apply constraints
    apply_constraints(m, H, g)

    # solve model
    print("Time elapsed: %f" % (time.time() - start))
    print("Solving model")
    solver = pyomo.opt.SolverFactory(H.solver_settings.get("solver", "glpk"))
    solver.options["mipgap"] = H.solver_settings.get("mipgap", 0.01)
    results = solver.solve(m, tee=H.solver_settings.get("debug", 0))
    # m.solutions.store_to(results)
    # results.write(filename='results.json', format='json')
    print("Model Solved with objective value {}".format(m.OBJ()))
    print("Time elapsed: %f" % (time.time() - start))

    return m
