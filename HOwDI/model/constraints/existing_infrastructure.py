# SPDX-License-Identifier: GPL-3.0-or-later

import pyomo.environ as pe
from networkx import DiGraph

from HOwDI.model.HydrogenData import HydrogenData


def rule_flowCapacityExisting(m: pe.ConcreteModel, g: DiGraph):
    """
    Force existing pipelines.

    The capacity along an existing distribution arc must be greater than or equal to the existing capacity.
    This allows the model to build additional capacity.

    It is worth noting that the model allows for unrestricted flow through pipelines.
    Capacity for distribution arcs is the number of transporters, not the amount of hydrogen flow.
    Thus, the existence of a pipeline is represented by :math:`\\rho_d(e) = 1`.

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.
    g : networkx.DiGraph
        A `networkx.DiGraph` object representing the hydrogen network.


    **Constraint**:
        Existing pipelines' capacity is greater than or equal to 1.
        (Where a capacity of "1" corresponds to one pipeline.)

    .. math ::

        \\rho_d(e) \\ge 1
        \\quad
        \\forall e_\\text{exist} \\in E_\\text{exist}

    The capacity :math:`\\rho_d` of a distribution edge :math:`e` is greater than or equal to 1
    for all existing distribution edges :math:`e_\\text{exist} \\in E_\\text{exist}`.

    Set:
        Existing distribution arcs (existing pipelines) :math:`e_\\text{exist} \\in E_\\text{exist}`.

    """

    def rule(m, startNode, endNode):
        # the nodes on each existing arc are unpacked into startNode and endNode
        constraint = (
            m.dist_capacity[startNode, endNode]
            >= g.edges[startNode, endNode]["existing"]
        )
        return constraint

    m.constr_flowCapacityExisting = pe.Constraint(
        m.distribution_arc_existing_set, rule=rule
    )


def rule_forceExistingProduction(m: pe.ConcreteModel):
    """Existing production must be built

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.


    **Constraint**:
        Binary tracking if producer built or not :math:`z_p` must equal 1 for all existing producers
        :math:`n_{p_\\text{exist}} \\in N_{p_\\text{exist}}`.

    .. math ::
        z_p(n) = 1
        \\quad
        \\forall n_{p_\\text{exist}} \\in N_{p_\\text{exist}}

    Set:
        Existing producers nodes :math:`n_{p_\\text{exist}} \\in N_{p_\\text{exist}}`.
    """

    def rule(m, node):
        constraint = m.prod_exists[node] == 1
        return constraint

    m.const_forceExistingProduction = pe.Constraint(m.existing_producers, rule=rule)


def rule_productionCapacityExisting(m: pe.ConcreteModel, g: DiGraph):
    """
    .. _rule_productionCapacityExisting:

    Capacity of existing producers equals their existing capacity

    This does not necessarily mean an existing producer can not retire.
    A producer can have a non-zero capacity while producing zero tons per day,
    meaning there are not associated variable costs.
    Since capital (upfront) costs of an existing plant are zero,
    an existing producer retires (does not spend capital) when :math:`h_p = 0`.

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.
    g: networkx.DiGraph
        A `networkx.DiGraph` object representing the hydrogen network.


    **Constraint**::

        Amount of capacity of producer in model == existing capacity

    .. math ::

        \\rho_p(n) = \\text{Existing Capacity}|_n
        \\quad
        \\forall n_{p_\\text{exist}} \\in N_{p_\\text{exist}}

    The amount of capacity :math:`\\rho_p` of a producer :math:`p` is equal to the existing capacity
    for all existing producer nodes :math:`n_{p_\\text{exist}} \\in N_{p_\\text{exist}}`.

    Set:
        Existing producers :math:`n_{p_\\text{exist}} \\in N_{p_\\text{exist}}`.

    Note
    ----
    Maybe this could be removed to allow retirement of existing production?
    """

    def rule(m, node):
        constraint = m.prod_capacity[node] == g.nodes[node]["capacity_tonPerDay"]
        return constraint

    m.constr_productionCapacityExisting = pe.Constraint(m.existing_producers, rule=rule)


def rule_onlyOneCCS(m: pe.ConcreteModel):
    """
    .. _only-one-ccs:

    Existing producers can only build one of the ccs tech options

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.


    **Constraint**:
        NAND(ccs1_built, ccs2_built), but this can't be solved numerically; thus,
        the sum of the binary variables tracking if a ccs technology is built :math:`z_{CCS}` over
        all CCS technologies :math:`\\psi \\in \\Psi` must be less than or equal to 1
        for all existing producer nodes :math:`n_{p_\\text{exist}} \\in N_{p_\\text{exist}}`.
        Consequently, either only one CCS technology is built or none are built.

    .. math ::

        \\sum_\\psi^\\Psi z_{CCS}(\\psi,n) \\le 1
        \\quad
        \\forall n_{p_\\text{exist}} \\in N_{p_\\text{exist}}

    Set:
        Existing producers :math:`n_{p_\\text{exist}} \\in N_{p_\\text{exist}}`.

    """

    def rule(m, node):
        constraint = m.ccs1_built[node] + m.ccs2_built[node] <= 1
        return constraint

    m.constr_onlyOneCCS = pe.Constraint(m.existing_producers, rule=rule)


def rule_ccs1CapacityRelationship(m: pe.ConcreteModel, H: HydrogenData):
    """
    .. _rule_ccs1CapacityRelationship:

    Define CCS1 CO2 Capacity

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.
    H : HydrogenData
        A `HydrogenData` object representing that stores data about hydrogen production.
        Namely, the percent of CO2 captured by CCS1.


    **Constraint**::

        Amount of CO2 captured ==
        the amount of hydrogen produced that went through CCS1
        * the amount of CO2 produced per unit of hydrogen produced
        * the efficiency of CCS1

    .. math ::

        \\theta_{CCS}(\\psi^n,n)
        \\cdot
        \\zeta(\\psi,n)
        =
        h_{CCS}(\\psi^n,n)
        \\cdot
        B_{\\text{exist}}(n)
        \\cdot
        \\beta(psi^n)
        \\quad
        \\forall n_{p_\\text{exist}} \\in N_{p_\\text{exist}}

    The amount of CO2 captured :math:`\\theta_{CCS}` by CCS1 :math:`\\psi^n` at node :math:`n`
    times the binary tracking if CCS1 is built :math:`\\zeta(\\psi,n)` where :math:`\\psi =` CCS1
    must equal the amount of hydrogen produced that went through CCS1 :math:`h_{CCS}(\\psi^n=\\text{CCS1},n)`
    times a baseline emissions rate :math:`B(n)` (tons CO2 per ton hydrogen produced of the unabated producer)
    times the percent of CO2 captured by CCS1 :math:`\\beta(\\psi^n=\\text{CCS1})`.

    Set:
        Existing producers :math:`n_{p_\\text{exist}} \\in N_{p_\\text{exist}}`.
    """

    def rule(m, node):
        constraint = (
            m.ccs1_co2_captured[node] * m.can_ccs1[node]
            == m.ccs1_capacity_h2[node]
            * m.co2_emissions_rate[node]
            * H.ccs1_percent_co2_captured
        )
        return constraint

    m.constr_ccs1CapacityRelationship = pe.Constraint(m.existing_producers, rule=rule)


def rule_ccs2CapacityRelationship(m: pe.ConcreteModel, H: HydrogenData):
    """
    Define CCS2 CO2 Capacity.

    See :func:`rule_ccs1CapacityRelationship` for equivalent details.
    """

    def rule(m, node):
        constraint = (
            m.ccs2_co2_captured[node] * m.can_ccs2[node]
            == m.ccs2_capacity_h2[node]
            * m.co2_emissions_rate[node]
            * H.ccs2_percent_co2_captured
        )
        return constraint

    m.constr_ccs2CapacityRelationship = pe.Constraint(m.existing_producers, rule=rule)


def rule_mustBuildAllCCS1(m: pe.ConcreteModel):
    """
    To build CCS1, it must be built over the entire possible capacity

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.


    **Constraint**::

        If CCS1 is built:
            Amount of hydrogen through CCS1 == Amount of hydrogen produced

    .. math ::

        h_{CCS}(\\psi,n) =
        z_{CCS}(\\psi,n)
        \\cdot
        h_p(n)
        \\quad
        \\forall n_{p_\\text{exist}} \\in N_{p_\\text{exist}}
        , \\quad
        \\forall \\psi \\in \\Psi

    The amount of hydrogen that has the associated carbon emissions cleaned by CCS :math:`h_{CCS}(\\psi,n)`
    for a given CCS technology :math:`\\psi` (is either CCS1 or CCS2) at node :math:`n`
    must equal the binary tracking if CCS is built :math:`z_{CCS}(\\psi,n)` times the amount
    of hydrogen produced at the node :math:`h_p(n)`.

    Set:
        Existing producers :math:`n_{p_\\text{exist}} \\in N_{p_\\text{exist}}`, for each
        CCS technology :math:`\\psi \\in \\Psi`.
    """

    def rule(m, node):
        constraint = m.ccs1_capacity_h2[node] == m.ccs1_built[node] * m.prod_h[node]
        return constraint

    m.constr_mustBuildAllCCS1 = pe.Constraint(m.existing_producers, rule=rule)


def rule_mustBuildAllCCS2(m: pe.ConcreteModel):
    """To build CCS2, it must be built over the entire possible capacity

    See :func:`rule_mustBuildAllCCS1` for equivalent details.
    """

    def rule(m, node):
        constraint = m.ccs2_capacity_h2[node] == m.ccs2_built[node] * m.prod_h[node]
        return constraint

    m.constr_mustBuildAllCCS2 = pe.Constraint(m.existing_producers, rule=rule)


def apply_existing_infrastructure_constraints(
    m: pe.ConcreteModel, g: DiGraph, H: HydrogenData
):
    """
    Apply all constraints related to existing infrastructure.

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.
    g : networkx.DiGraph
        A `networkx.DiGraph` object representing the network.
    H : HydrogenData
        A `HydrogenData` object representing that stores data about hydrogen production.
        Namely, the percent of CO2 captured by CCS1 and CCS2.
    """
    rule_flowCapacityExisting(m, g)
    rule_forceExistingProduction(m)
    rule_productionCapacityExisting(m, g)
    rule_onlyOneCCS(m)
    rule_ccs1CapacityRelationship(m, H)
    rule_ccs2CapacityRelationship(m, H)
    rule_mustBuildAllCCS1(m)
    rule_mustBuildAllCCS2(m)
