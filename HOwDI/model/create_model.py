import time

import pyomo
import pyomo.environ as pe
from networkx import DiGraph

from HOwDI.model.constraints.capacity_relationships import apply_capacity_relationships
from HOwDI.model.constraints.checs import apply_CHECs
from HOwDI.model.constraints.existing_infrastructure import (
    apply_existing_infrastructure_constraints,
)
from HOwDI.model.constraints.mass_conservation import apply_mass_conservation
from HOwDI.model.constraints.subsidies import apply_subsidy_constraints
from HOwDI.model.HydrogenData import HydrogenData

start = time.time()


def create_node_sets(m: pe.ConcreteModel, g: DiGraph):
    r"""Creates all pe.Sets associated with nodes used by the model

    Parameters
    ----------
    m : pe.ConcreteModel
    g : DiGraph


    .. container::
        :name: table:model_node_sets

        .. table:: Model Node Sets

            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | Index                      | Set                            |                       | Description                           |
            +============================+================================+=======================+=======================================+
            | :math:`n`                  | :math:`\in N`                  |                       | Set of all nodes                      |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`n_p`                | :math:`\in N_p`                | :math:`\subseteq N`   | Producer nodes                        |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`n_{p_\text{exist}}` | :math:`\in N_{p_\text{exist}}` | :math:`\subseteq N_p` | Existing producer nodes               |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`n_{p_\text{new}}`   | :math:`\in N_{p_\text{new}}`   | :math:`\subseteq N_p` | New build producer nodes              |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`n_{p_t}`            | :math:`\in N_{p_t}`            | :math:`\subseteq N_p` | Thermal producer nodes                |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`n_{p_e}`            | :math:`\in N_{p_e}`            | :math:`\subseteq N_p` | Electric producer nodes               |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`n_{cv}`             | :math:`\in N_{cv}`             | :math:`\subseteq N`   | Converter nodes                       |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`n_{u}`              | :math:`\in N_{u}`              | :math:`\subseteq N`   | Consumption/demand nodes              |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`n_{\text{truck}}`   | :math:`\in N_{\text{truck}}`   | :math:`\subseteq N`   | Truck distribution nodes              |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`\omega`             | :math:`\in \Omega`             |                       | Set of all hubs                       |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`\phi`               | :math:`\in \Phi`               |                       | Set of all producer types             |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`\delta`             | :math:`\in \Delta`             |                       | Set of all distribution methods       |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`\pi`                | :math:`\in \Pi`                |                       | Set of all conversion methods         |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`\xi`                | :math:`\in \Xi`                |                       | Set of all unique demand sectors      |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`\psi`               | :math:`\in \Psi`               |                       | Set of all retrofit CCS technologies  |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+

    """
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
    r"""Creates all pe.Sets associated with arcs used by the model

    Parameters
    ----------
    m : pe.ConcreteModel
    g : DiGraph


    .. container::
        :name: table:model_arc_sets

        .. table:: Model Arc Sets

            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | Index                      | Set                            |                       | Description                           |
            +============================+================================+=======================+=======================================+
            | :math:`e`                  | :math:`\in E`                  |                       | Set of all edges/arcs                 |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`e_\text{exist}`     | :math:`\in E_\text{exist}`     | :math:`\subseteq E`   | Existing edges (existing pipelines)   |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`e_d`                | :math:`\in E_d`                | :math:`\subseteq E`   | Between demand node and demand sector |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`e_c`                | :math:`\in E_c`                | :math:`\subseteq E`   | Between demand node and demand sector |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`e^n`                | :math:`\in E^n`                | :math:`\subseteq E`   | All edges connected to node :math:`n` |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`e_{in}^n`           | :math:`\in E_{in}^n`           | :math:`\subseteq E`   | All edges entering node :math:`n`     |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+
            | :math:`e_{out}^n`          | :math:`\in E_{out}^n`          | :math:`\subseteq E`   | All edges exiting node :math:`n`      |
            +----------------------------+--------------------------------+-----------------------+---------------------------------------+

    """
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
    r"""Loads parameters from network object (g) into pe.Param objects, which are
    used as coefficients in the model objective

    .. container::
        :name: table:model_parameters

        .. table:: Model Parameters

            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | Parameter                                      | Unit                                               | Description                                     |
            +================================================+====================================================+=================================================+
            | :math:`\kappa`                                 | %                                                  | Fixed cost percentage                           |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`A`                                      | %                                                  | Amortization factor                             |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`t`                                      | Days                                               | Time slices                                     |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`U'_{\text{CO}_2}`                       | :math:`\$`/ton\ :math:`\text{CO}_2`                | Carbon emissions tax                            |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`\tau_{\text{CO}_2}`                     | :math:`\$`/ton\ :math:`\text{CO}_2`                | Carbon capture tax credit                       |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`B`                                      | ton\ :math:`\text{CO}_2`/ton\ :math:`\text{H}_2`   | Baseline emissions rate                         |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`\varepsilon(\omega)`                    | $/kWh                                              | Electricity price at a hub                      |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`\gamma(\omega)`                         | $/MMBtu                                            | Gas price at a hub                              |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`\lambda(\omega)`                        | %                                                  | Capital price multiplier at a hub               |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`D_c(\delta)`                            | $/:math:`\delta`-unit                              | Capital cost of a distribution method           |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`D_v(\delta)`                            | $/ton\ :math:`\text{H}_2`                          | Variable cost of a distribution method          |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`y_{d}^{\text{max}}(\delta)`             | ton\ :math:`\text{H}_2`/day                        | Flow limit of a distribution method             |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`P_c(\phi)`                              | $/ton\ :math:`\text{H}_2`/day                      | Capital cost of a production method             |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`P_v(\phi)`                              | $/ton\ :math:`\text{H}_2`                          | Variable cost of a production method            |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`P_e(\phi)`                              | kWh/ton\ :math:`\text{H}_2`                        | Electric costs of a production method           |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`P_g(\phi)`                              | MMBtu/ton\ :math:`\text{H}_2`                      | Gas cost of a production method                 |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`\mu_p(\phi)`                            | %                                                  | Utilization of a production method              |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`G(\phi_{\text{electric}})`              | ton\ :math:`\text{CO}_2`/ton\ :math:`\text{H}_2`   | Carbon grid intensity of an electric producer   |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`\beta(\phi_{\text{new, thermal}})`      | %                                                  | CCS rate of a thermal producer                  |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`\tau_{\text{new}}(\phi)`                | $/ton\ :math:`\text{H}_2`                          | Tax credit of a producer                        |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`y_{p}^{\text{max}}(\phi)`               | ton\ :math:`\text{H}_2`                            | Upper limit of capacity for a producer          |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`y_{p}^{\text{min}}(\phi)`               | ton\ :math:`\text{H}_2`                            | Lower limit of capacity for a producer          |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`C_c(\pi)`                               | $/ton\ :math:`\text{H}_2`/day                      | Capital cost of a converter                     |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`C_v(\pi)`                               | $/ton\ :math:`\text{H}_2`                          | Variable cost of a converter                    |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`C_e(\pi)`                               | kWh/ton\ :math:`\text{H}_2`                        | Electricity costs of a converter                |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`\mu_c(\pi)`                             | %                                                  | Utilization of a conversion method              |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`U_{bp}(\xi)`                            | $/ton\ :math:`\text{H}_2`                          | Breakeven price of a demand sector              |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`Q_{\text{H}_2}(\omega, \xi)`            | ton\ :math:`\text{H}_2`                            | Amount of hydrogen demanded by a sector         |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`Q'_{\text{CO}_2}(\xi)`                  | ton\ :math:`\text{CO}_2`/ton\ :math:`\text{H}_2`   | Avoided carbon emissions of a sector            |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`S_{\text{CO}_2}(\xi)`                   | :math:`\{0,1\}`                                    | Binary for demand sector’s carbon sensitivity   |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`CCS_v(\psi)`                            | :math:`\$`/ton\ :math:`\text{CO}_2`                | Variable costs of retrofitted CCS               |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`\beta(\psi)`                            | %                                                  | CCS rate of a CCS retrofit technology           |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`\tau_{\text{H}_2}(\psi)`                | :math:`\$`/ton\ :math:`\text{H}_2`                 | Tax credit for hydrogen cleaned by retrofit CCS |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`\zeta_{CCS}(n_{p_{\text{exist}}})`      | :math:`\{0,1\}`                                    | Binary allowing CCS retrofitting                |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+
            | :math:`B_{\text{exist}}(n_{p_{\text{exist}}})` | ton\ :math:`\text{CO}_2`/ton\ :math:`\text{H}_2`   | Carbon production rate of existing producers    |
            +------------------------------------------------+----------------------------------------------------+-------------------------------------------------+

    """
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
    r"""Creates variables associated with model

    .. container::
        :name: table:model_variables

        .. table:: Model Variables

            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | Variable                                       | Units                          | Set                    | Description                                 |
            +================================================+================================+========================+=============================================+
            | :math:`\rho_d(e)`                              | Pipelines or trucks            | :math:`\mathbb{Z}_0^+` | Capacity of a distribution edge             |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | :math:`h_d(e)`                                 | ton\ :math:`\text{H}_2`/day    | :math:`\mathbb{R}_0^+` | Hydrogen flow through edge per day          |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | :math:`\rho_p(n_p)`                            | ton\ :math:`\text{H}_2`        | :math:`\mathbb{R}_0^+` | Capacity of a producer                      |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | :math:`h_p(n_p)`                               | ton\ :math:`\text{H}_2`/day    | :math:`\mathbb{R}_0^+` | Amount of hydrogen produced in one day      |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | :math:`\chi_p(n_p)`                            | CHECs/day                      | :math:`\mathbb{R}_0^+` | Amount of CHECs produced                    |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | :math:`z_p(n_p)`                               |                                | :math:`\{0,1\}`        | Binary tracking if producer is built        |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | :math:`\rho_{cv}(n_{cv})`                      | ton\ :math:`\text{H}_2`        | :math:`\mathbb{R}_0^+` | Capacity of a converter                     |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | :math:`h_u(n_u)`                               | ton\ :math:`\text{H}_2`/day    | :math:`\mathbb{R}_0^+` | Amount of hydrogen consumed at a node       |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | :math:`\chi_d(n_u)`                            | CHECs/day                      | :math:`\mathbb{R}_0^+` | Amount of CHECs demanded                    |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | :math:`z_{CCS}(\psi, n_{p_\text{exist}})`      |                                | :math:`\{0,1\}`        | Binary tracking if retrofitted CCS is built |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | :math:`\theta_{CCS}(\psi, n_{p_\text{exist}})` | ton\ :math:`\text{CO}_2`/day   | :math:`\mathbb{R}_0^+` | CO2 captured by retrofitted CCS             |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | :math:`h_{CCS}(\psi, n_{p_\text{exist}})`      | ton\ :math:`\text{H}_2`/day    | :math:`\mathbb{R}_0^+` | Hydrogen "cleaned" by retrofitted CCS       |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+
            | :math:`\rho_{CCS}(\psi, n_{p_\text{exist}})`   | ton\ :math:`\text{CO}_2`       | :math:`\mathbb{R}_0^+` | Capacity of retrofitted CCS                 |
            +------------------------------------------------+--------------------------------+------------------------+---------------------------------------------+

    """

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


def obj_rule(
    m: pe.ConcreteModel, H: HydrogenData
) -> pyomo.core.expr.numeric_expr.SumExpression:
    r"""Defines the objective function.

    Parameters
    ----------
    m : ConcreteModel
        The Pyomo model object
    H : HydrogenData
        The HydrogenData object

    Returns
    -------
    pyomo.core.expr.numeric_expr.SumExpression
    
    
    Objective Definition
    --------------------
    The model objective is to maximize system profit, which includes system-value gained from
    consumer's consumption of hydrogen, value associated with tax credits, and the avoided carbon taxes.
    It also includes costs associated with production, distribution, and conversion.
    
    The model objective is defined as:
    
    .. math::
    
        \text{max} \left (
        \hat{U}_{\text{H}_2}
        + \hat{U}'_{\text{CO}_2}
        + \hat{U}_{\text{CCS}}
        + \hat{U}_{\text{tax credit}}
        - \hat{P}_c
        - \hat{P}_v
        - \hat{P}_e
        - \hat{P}_g
        - \hat{P}_{\text{CO}_2 \text{ tax}}
        \right .
        \\
        \left .
        - \hat{CCS}_v
        - \hat{D}_c
        - \hat{D}_v
        - \hat{C}_c
        - \hat{C}_v
        - \hat{C}_e
        \right )
        
    .. code-block:: python
    
        def obj_rule(m, H):
            ...
            totalSurplus = (
            U_hydrogen
            + U_carbon_capture_credit_new
            + U_carbon_capture_credit_retrofit
            + U_h2_tax_credit
            + U_h2_tax_credit_retrofit_ccs
            + U_carbon
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
    
        m.OBJ = pe.Objective(rule=obj_rule(m, H), sense=pe.maximize)

    .. _utility-gained-through-consumption-of-hydrogen:
        
    Utility gained by consumption of hydrogen
    +++++++++++++++++++++++++++++++++++++++++
    The utility gained by the consumption of hydrogen :math:`\hat{U}_{\text{H}_2}` is the amount consumed 
    :math:`h_u` times the (breakeven) price :math:`U_{bp}` that the consumer at the node's corresponding demand
    sector :math:`\xi` is willing to pay, summed over all consumers :math:`n_u \in N_u`.
    
    .. math::
    
        \hat{U}_{\text{H}_2}
        =
        \sum_{n_u}^{N_u}
        U_{bp}(\xi^{n})
        \cdot
        h_u(n)
        
    .. code-block:: python

        U_hydrogen = sum(m.cons_h[c] * m.cons_price[c] for c in m.consumer_set)
        
    .. _utility-gained-through-avoided-carbon-taxes:    
        
    Utility gained by consumers by avoiding a carbon tax
    ++++++++++++++++++++++++++++++++++++++++++++++++++++
    Although not directly a source of profit, consumers avoid paying some share of carbon taxes
    when switching from carbon-intensive sources of energy to hydrogen.
    This reduction is dependent on the avoided emissions, which is calculated by each demand sector
    and external to the scope of this model.
    
    The utility gained by consumers by avoiding a carbon tax :math:`\hat{U}_{\text{tax credit}}` is the carbon
    emissions tax :math:`U'_{\text{CO}_2}` in dollars per ton of CO2 emitted times the amount of CO2 avoided.
    The amount of CO2 avoided is the avoided emissions :math:`Q'_{\text{CO}_2}` of a demand sector :math:`\xi`
    times the amount of hydrogen consumed :math:`h_u` by a consumer :math:`n_u` in that demand sector.

    .. math::
    
        \hat{U}'_{\text{CO}_2}
        =
        U'_{\text{CO}_2}
        \left (
        \sum_{n_u}^{N_u}
        Q'_{\text{CO}_2}(\xi^{n})
        \cdot
        h_u(n)
        \right )
        
    .. code-block:: python
    
        U_carbon = (
            sum(m.cons_h[c] * m.avoided_emissions[c] for c in m.consumer_set)
        ) * H.carbon_price
        
    .. _utility-gained-through-carbon-capture-tax-credits:    
        
    Utility gained through carbon capture tax credits
    +++++++++++++++++++++++++++++++++++++++++++++++++
    Producers can gain capital through tax credits for the capture of CO2.
    The model treats carbon capture connected to new and existing thermal production separately.
    Existing production is not currently equipped with CCS, and the model determines if retrofitting 
    CCS to these generators would increase the model objective.

    On the other hand, each new thermal producer :math:`\phi` is assumed to be built with CCS.
    The emissions rate of an unabated consumer :math:`B` is used to calculate the relative amount of carbon captured.
    This is specified in settings and is most likely the emissions rate of an unabated steam methane reformer.
    
    .. math::
    
        \hat{U}_{CCS}
        = 
        \tau_{\text{CO}_2}
        \left [
        \left (
        \sum_{n_{p_\text{exist}}}^{N_{p_\text{exist}}}
        \sum_\psi^\Psi
        \theta_{CCS}(\psi, n)
        \right )
        +
        B
        \left (
        \sum_{n_{p_\text{new}}}^{N_{p_\text{new}}}
        \beta(\psi^n)
        \cdot
        h_p(n)
        \right )
        \right ]
        
    where :math:`\tau_{\text{CO}_2}` is the tax credit per ton of CO2 captured, :math:`\theta_{CCS}` is the
    CO2 captured by retrofitted CCS (see :func:`HOwDI.model.constraints.existing_infrastructure.rule_ccs1CapacityRelationship`),
    :math:`B` is the emissions rate of an unabated consumer, :math:`\beta` is the prescribed CCS rate of a new thermal producer 
    :math:`\phi`, and :math:`h_p` is the amount of hydrogen consumed by a producer at node :math:`n_p`.
    
    .. code-block:: python
     
        U_carbon_capture_credit_retrofit = (
            sum(
                m.ccs1_co2_captured[p] + m.ccs2_co2_captured[p]
                for p in m.existing_producers
            )
            * H.carbon_capture_credit
        )
    
        U_carbon_capture_credit_new = (
            sum(
                m.prod_h[p] * H.baseSMR_CO2_per_H2_tons * m.ccs_capture_rate[p]
                for p in m.new_thermal_producers
            )
            * H.carbon_capture_credit
        )
        
    .. _utility-gained-through-clean-hydrogen-production-tax-credits:
        
    Utility gained through clean hydrogen production tax credits
    ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    Producers can also gain tax credits for the production of clean hydrogen. 
    The tax credit :math:`\tau` a specific type of new producer :math:`\phi` or retrofitted CCS :math:`\psi` will get 
    is pre-calculated external to the model and specified by the user.
    When the model chooses to retrofit an existing producer with CCS, the amount of hydrogen that is clean and qualifies
    for a tax credit is dependent on the carbon capture rate (i.e., if CCS captures 70% of the carbon produced,
    70% of the hydrogen produced will yield the tax credit, :math:`h_\text{CCS} = 0.70 h_p`). 
    
    The utility gained by producers through clean hydrogen production tax credits :math:`\hat{U}_{\text{tax credit}}` is the
    tax credit :math:`\tau` for the given producer type :math:`\phi` times the amount of hydrogen produced 
    :math:`h_p` at the producer node :math:`n_p`. 
    
    For retrofitted CCS, the amount of hydrogen that qualifies for the tax credit :math:`\tau_{\text{H}_2}(\psi)`
    is the amount of :ref:`hydrogen cleaned by CCS <rule_ccs1CapacityRelationship>`, :math:`h_\text{CCS}`.
    To the model, this amount is unique for each potential CCS retrofit technology :math:`\psi`.
    However, all or all but one of these technologies will have :ref:`a capacity of zero <only-one-ccs>`.
    
    .. math::
    
        \hat{U}_\text{tax credit} = 
        \left (
        \sum_{n_{p_\text{exist}}}^{N_{p_\text{exist}}}
        \sum_\psi^\Psi
        \tau_{\text{H}_2}(\psi) 
        \cdot 
        h_{CCS}(\psi, n)
        \right )
        +
        \left (
        \sum_{n_{p_\text{new}}}^{N_{p_\text{new}}}
        \tau_\text{new}(\phi^n)
        \cdot
        h_p(n)
        \right )
        
    .. code-block:: python

        U_h2_tax_credit_retrofit_ccs = sum(
            m.ccs1_capacity_h2[p] * H.ccs1_h2_tax_credit
            + m.ccs2_capacity_h2[p] * H.ccs2_h2_tax_credit
            for p in m.existing_producers
        )

        U_h2_tax_credit = sum(m.prod_h[p] * m.h2_tax_credit[p] for p in m.new_producers)
        
    Costs of production
    +++++++++++++++++++
    
    .. _capital-costs-of-production:
    
    Capital costs of production
    ***************************
    The total capital cost of a production :math:`\hat{P}_c` is the capital cost of :math:`P_c` of a
    production method :math:`\phi` times the capacity of that production method :math:`\rho_p` at a
    production node :math:`n_p`.
    That cost is multiplied by a regional capital cost adjustment factor :math:`\lambda` at the hub :math:`\omega`
    corresponding to node :math:`n_p`.
    The capital cost is summed over all production nodes, divided by the amortization factor :math:`A/t`, and multiplied
    by :math:`1+\kappa` to account for fixed costs as :math:`\kappa` percent of capital costs.
    
    .. math::
    
        \hat{P}_c
        =
        \frac{1+\kappa}{A/t}
        \left (
        \sum_{n_{p}}^{N_{p}}
        \lambda(\omega^n)
        \cdot
        P_c(\phi^n)
        \cdot
        \rho_p(n)
        \right )
        
    .. code-block:: python
    
        # m.prod_cost_capital[p] is already multiplied by the regional cost adjustment factor
        P_capital = (
            sum(m.prod_capacity[p] * m.prod_cost_capital[p] for p in m.producer_set)
            / H.A
            / H.time_slices
            * (1 + H.fixedcost_percent)
        )
        
    .. _variable-costs-production:
        
    Variable costs of production
    ****************************
    Variable costs :math:`\hat{P}_v` are the sum of variable costs :math:`P_v` of a production method :math:`\phi` per ton of hydrogen
    produced times the amount of hydrogen produced :math:`h_p` at a production node :math:`n_p`.
    
    .. math::
    
        \hat{P}_v =
        \sum_{n_{p}}^{N_{p}}
        P_v(\phi^n)
        \cdot
        h_p(n)
        
    .. code-block:: python
    
        P_variable = sum(m.prod_h[p] * m.prod_cost_variable[p] for p in m.producer_set)
        
    .. _electricity-costs-of-production:
    
    Electricity costs of production
    *******************************
    The total costs of electricity :math:`\hat{P}_e` is the product of local electricity price :math:`\varepsilon` at the hub :math:`\omega`
    corresponding to the producer node :math:`n_p`, the amount of electricity (kWh/ton H2) consumed to produce a ton of
    hydrogen :math:`P_e` corresponding to the producer type :math:`\phi`, and the amount of hydrogen produced :math:`h_p` at a production node :math:`n_p`.
    
    .. math::
    
        \hat{P}_e
        =
        \sum_{n_{p}}^{N_{p}}
        \varepsilon(\omega^n)
        \cdot
        P_e(\phi^n)
        \cdot
        h_p(n)
        
    .. code-block:: python

        P_electricity = sum(m.prod_h[p] * m.prod_e_price[p] for p in m.producer_set)
        
    .. note::
        
        Thermal plants and are not excluded here.
        Conversion also uses electricity and thus has associated :ref:`electricity costs <electricity-costs-of-conversion>`.
    
    .. _natural-gas-costs:
    
    Natural gas costs of production (SMRs)
    **************************************
    The total costs of natural gas :math:`\hat{P}_g` is the product of local natural gas price :math:`\gamma` at the hub :math:`\omega`
    corresponding to the thermal producer node :math:`n_p`, the amount of natural gas (MMBtu/ton H2) consumed to produce a ton of 
    hydrogen :math:`P_g` corresponding to the thermal producer type :math:`\phi`, and the amount of hydrogen produced :math:`h_p` at a production node :math:`n_p`.
    
    .. math::

        \hat{P}_g
        =
        \sum_{n_{p}}^{N_{p}}
        \gamma(\omega^n)
        \cdot
        P_g(\phi^n)
        \cdot
        h_p(n)
        
    .. code-block:: python
    
        P_naturalGas = sum(m.prod_h[p] * m.prod_ng_price[p] for p in m.producer_set)
        
    .. _carbon-tax-costs:
        
    Carbon tax costs
    ****************
    Carbon tax costs are dependent on the carbon emissions tax :math:`U'_{\text{CO}_2}` and the carbon emissions of the producer.
    
    For new and existing thermal producers, the carbon emissions are one minus the CCS capture percentage :math:`\beta` times the
    unabated emissions rate :math:`B` (tonCO2/tonH2) times the amount of hydrogen produced :math:`h_p` at new thermal production node :math:`n_p`
    or the amount of hydrogen processed by retrofit CCS :math:`h_{CCS}` (all or none, see 
    :func:`HOwDI.model.constraints.existing_infrastructure.rule_mustBuildAllCCS1`) at existing thermal production nodes.
    
    For electric producers, the carbon emissions are the amount of hydrogen produced :math:`h_p` at new electric production node :math:`n_p`
    times the carbon intensity :math:`G` of the electricity used to produce the hydrogen (tonCO2/tonH2) for the electric producer
    :math:`\psi` that corresponds to the node.
    
    .. math::
    
        \hat{P}_{\text{CO}_2 \text{ tax}}
        = 
        U'_{\text{CO}_2}
        \left [
        \left (
        \sum_{n_{p_\text{exist}}}^{N_{p_\text{exist}}}
        \sum_\psi^\Psi
        (1-\beta(\psi))
        \cdot
        B_{\text{exist}}(n)
        \cdot
        h_{CCS}(\psi, n_{p})
        \right )
        \right.
        \\
        \left.
        +
        \left (
        \sum_{n_{p_\text{new, thermal}}}^{N_{p_\text{new, thermal}}}
        (1-\beta(\psi^n))
        \cdot
        B
        \cdot
        h_p(n)
        \right )
        +
        \left (
        \sum_{n_{p_\text{new, electric}}}^{N_{p_\text{new, electric}}}
        G(\psi^n)
        \cdot
        h_p(n)
        \right )
        \right ]
    
    .. code-block:: python
    
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
        
    .. _variable-costs-of-retrofitted-ccs:
    
    Variable costs of retrofitted CCS
    +++++++++++++++++++++++++++++++++
    Retrofitting an existing thermal producer with CCS technologies incurs a variable cost.
    The total variable cost :math:`\hat{CCS}_v` is dependent on the amount of CO2 captured :math:`\theta_{CCS}` at an existing
    thermal producer node :math:`n_p` for a given CCS technology :math:`\psi`, and the variable cost of CCS :math:`CCS_V` for
    that CCS technology.
    
    .. math::
    
        \hat{CCS}_v
        =
        \sum_{n_{p_\text{exist}}}^{N_{p_\text{exist}}}
        \sum_\psi^\Psi
        CCS_v(\psi^n)
        \cdot
        \theta_{CCS}(\psi, n_{p})
    
    .. code-block:: python
    
        CCS_variable = sum(
            (m.ccs1_co2_captured[p] * H.ccs1_variable_usdPerTon)
            + (m.ccs2_co2_captured[p] * H.ccs2_variable_usdPerTon)
            for p in m.existing_producers
        )
        
    Costs of distribution
    +++++++++++++++++++++
    
    .. _capital-costs-of-distribution:
    
    Capital costs of distribution
    *****************************
    The capital cost of distribution depends on the distribution method :math:`\delta`.
    Capital costs :math:`D_c` are in units of $/pipeline if :math:`\delta` is pipeline, and $/truck if :math:`\delta` is truck.
    The capital cost of distribution is multiplied by the capacity of the distribution method (pipelines or trucks).
    
    NOTE
    ----
    Given that the model allows for unrestricted flow in a pipeline, the capacity of a pipeline will either be 0 or 1.
    There is no need for a second pipeline that would add additional infinite flow.
    
    
    The capital costs are multiplied by the average of the regional capital cost multipliers of the connected hubs,
    notated as :math:`\overline{\lambda}(e)` where :math:`e` is the edge.
    The total capital costs of distribution, summed over all edges, is divided by the amortization factor :math:`A` that is divided into time slices :math:`t`.
    The whole term is multiplied by :math:`1+\kappa` to account for fixed costs.
    
    .. math::
    
        \hat{D}_c
        =
        \frac{1+\kappa}{A/t}
        \left (
        \sum_{e}^{E}
        \overline{\lambda}(e)
        \cdot
        D_c(\delta^e)
        \cdot
        \rho_d(e)
        \right )
    
    .. code-block:: python
    
        # m.dist_cost_capital contains the regional multiplier
        # m.dist_cost_capital for pipelines is in $/pipeline, distance is already calculated in km
        D_capital = sum(
            (m.dist_capacity[d] * m.dist_cost_capital[d]) / H.A / H.time_slices
            for d in m.distribution_arcs
        ) * (1 + H.fixedcost_percent)
        
    .. _variable-costs-of-distribution: 
        
    Variable costs of distribution
    ******************************
    The variable cost of distribution along an edge :math:`e` is the variable cost of distribution :math:`D_v` ($/tonH2) of the
    distribution method :math:`\delta` multiplied by the amount of hydrogen :math:`h_d` (tonH2/day) that is distributed along the edge.
    
    .. math::
    
        \hat{D}_v =
        \sum_{e}^{E}
        D_v(\delta^e)
        \cdot
        h_d(e)
        
    .. code-block:: python
    
        D_variable = sum(m.dist_h[d] * m.dist_cost_variable[d] for d in m.distribution_arcs)
        
    Costs of conversion
    +++++++++++++++++++
    
    .. _capital-costs-of-conversion:
    
    Capital costs of conversion
    ***************************
    The capital cost of conversion :math:`\hat{C}_c` is dependent on the converter type :math:`\pi`, the capital cost of that convertor type
    :math:`C_c`, and the capacity of that convertor :math:`\rho_{cv}` at that node :math:`n`, and the regional capital cost multiplier :math:`\lambda`
    associated with the hub :math:`\omega` associated with the node.
    
    The whole term is divided by the amortization factor :math:`A` that is divided by time slices :math:`t`.
    Fixed costs are accounted for by multiplying the whole term by :math:`1+\kappa`.
    
    .. math::
    
        \hat{C}_c
        =
        \frac{1+\kappa}{A/t}
        \left (
        \sum_{n_{cv}}^{N_{cv}}
        \lambda(\omega^n)
        \cdot
        C_c(\pi^n)
        \cdot
        \rho_{cv}(n)
        \right )
        
    .. code-block:: python
    
        CV_capital = sum(
            (m.conv_capacity[cv] * m.conv_cost_capital[cv]) / H.A / H.time_slices
            for cv in m.converter_set
        ) * (1 + H.fixedcost_percent)
        
    .. _variable-costs-of-conversion:
        
    Variable costs of conversion
    ****************************
    The total variable cost of conversion :math:`\hat{C}_v` is the variable cost of conversion :math:`C_v` of the converter :math:`\pi`
    times the utilization of the converter :math:\mu_{c}` times the built capacity of the converter :math:`\rho_{cv}` at the node :math:`n`.
    
    .. math::
    
        \hat{C}_v =
        \sum_{n_{cv}}^{N_{cv}}
        C_v(\pi^n)
        \cdot
        \mu(\pi^n)
        \cdot
        \rho_{cv}(n)
        
    .. code-block:: python
    
        CV_variable = sum(
            m.conv_capacity[cv] * m.conv_utilization[cv] * m.conv_cost_variable[cv]
            for cv in m.converter_set
        )
        
    .. _electricity-costs-of-conversion:
        
    Electricity costs of conversion
    *******************************
    The price of electricity for conversion is the price of electricity :math:`\varepsilon` at the hub :math:`\omega` associated
    with the node :math:`n` at which the converter is located times the electricity efficiency of the convertor :math:`C_e` (kwH/tonH2)
    multiplied by the utilization :math:`\mu` and the capacity :math:`\rho_{cv}`.
    
    .. math::
    
        \hat{C}_e
        = 
        \sum_{n_{cv}}^{N_{cv}}
        \varepsilon(\omega^n)
        \cdot
        C_e(\pi^n)
        \cdot
        \mu(\pi^n)
        \cdot
        \rho_{cv}(n)
        
    .. code-block:: python
        
        CV_electricity = sum(
            (m.conv_capacity[cv] * m.conv_utilization[cv] * m.conv_e_price[cv])
            for cv in m.converter_set
        )
        
    TODO
    ----
    The electricity associated with the converter does not have a carbon tax or remove CHECs.
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
    # TODO maybe the two below equations could be combined for efficiency?
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


def apply_constraints(m, H: HydrogenData, g: DiGraph):
    """Apply constraints to the model"""
    apply_mass_conservation(m, g)
    apply_existing_infrastructure_constraints(m, g, H)
    apply_capacity_relationships(m, g)
    apply_CHECs(m, H)
    apply_subsidy_constraints(m, H)


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
