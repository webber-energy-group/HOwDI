# SPDX-License-Identifier: GPL-3.0-or-later

"""
Clean Hydrogen Energy Credits (CHECs) ensure that the amount of hydrogen consumed
by carbon-sensitive consumers is equal to the amount of clean hydrogen produced.
It is important to note that CHECs do not necessitate that carbon-sensitive demand
is met by clean hydrogen.
Instead, CHECs serve as a non-physical commodity market that couples clean production
with carbon-sensitive demand.

For every ton of clean hydrogen produced, one CHEC is produced.
For every ton of satisfied carbon-sensitive demand, one CHEC is consumed.
The model is constrained such that the amount of CHECs produced exceeds the number of CHECs consumed.
In other words, there must be more clean hydrogen production than carbon-sensitive demand met.

The amount of CHECs generated per ton of hydrogen is calculated with the plant's emission rate
relative to the emission rate of an unabated SMR plant.
"""

import pyomo.environ as pe

from HOwDI.model.HydrogenData import HydrogenData


def rule_ccs1Checs(m: pe.ConcreteModel, H: HydrogenData):
    """
    CHECs produced from CCS1 cannot exceed the the amount of "carbon free"" hydrogen from CCS1

    If the model is using "fractional CHECs", the amount of carbon free hydrogen is the CCS1 capacity
    times the percent of CO2 captured.

    If the model is not using "fractional CHECs", the amount of carbon free hydrogen is the CCS1 capacity.

    Parameters
    ----------
    m : pe.ConcreteModel
        Pyomo ConcreteModel object
    H : HydrogenData
        HydrogenData object


    **Constraint**::

        CHECs from CCS1 <= Hydrogen cleaned by retrofitted CCS


    .. math ::

        \\chi_p(n)
        =
        h_{CCS}(\\phi^n,n)
        \\quad
        \\forall n_{p_\\text{exist}} \\in N_{p_\\text{exist}}


    For fractional CHECs::

        CHECs from CCS1 <= CCS1 capacity * percent of CO2 captured


    .. math ::

        \\chi_p(n)
        \\le
        \\rho_\\text{CCS} (\\psi, n_{p_\\text{exist}} )
        \\cdot
        \\beta(\\psi)
        \\quad
        \\forall n_{p_\\text{exist}} \\in N_p | \\zeta(\\psi = \\text{CCS1}, n_{p_\\text{exist}})=1


    The amount of CHECs produced :math:`\\chi_p` at a node :math:`n` as a result of retrofitted CCS1 is
    less than or equal to the capacity of retrofitted CCS :math:`\\rho_\\text{CCS}(\\psi, n_{p_\\text{exist}} )`
    times the percent of CO2 captured :math:`\\beta(\\psi)`. This constraint is applied to all producers, but only
    (existing) nodes with retrofitted CCS1 with have a non-zero value for
    :math:`\\rho_\\text{CCS}(\\psi=\\text{CCS1}, n_{p_\\text{exist}} )`.

    Else::

        CHECs from CCS1 <=  CCS1 capacity

    .. math ::

        \\chi_p(n)
        \\le
        \\rho_\\text{CCS} (\\psi, n_{p_\\text{exist}} )
        \\cdot
        \\quad
        \\forall n_{p_\\text{exist}} \\in N_p | \\zeta(\\psi = \\text{CCS1}, n_{p_\\text{exist}})=1

    Set:
        All producers, but in defacto existing producers that have CCS1
        :math:`n_{p_\\text{exist}} \\in N_p | \\zeta(\\psi = \\text{CCS1}, n_{p_\\text{exist}})=1`

    """

    def rule(m, node):
        if H.fractional_chec:
            constraint = (
                m.ccs1_checs[node]
                <= m.ccs1_capacity_h2[node] * H.ccs1_percent_co2_captured
            )
        else:
            constraint = m.ccs1_checs[node] <= m.ccs1_capacity_h2[node]
        return constraint

    m.constr_ccs1Checs = pe.Constraint(m.existing_producers, rule=rule)


def rule_ccs2Checs(m: pe.ConcreteModel, H: HydrogenData):
    """
    CHECs produced from CCS2 cannot exceed the clean hydrogen from CCS2

    Parameters
    ----------
    m : pe.ConcreteModel
        Pyomo ConcreteModel object
    H : HydrogenData
        HydrogenData object


    See :func:`rule_ccs1Checs` for corresponding details.

    """

    def rule(m, node):
        if H.fractional_chec:
            constraint = (
                m.ccs2_checs[node]
                <= m.ccs2_capacity_h2[node] * H.ccs2_percent_co2_captured
            )
        else:
            constraint = m.ccs2_checs[node] <= m.ccs2_capacity_h2[node]
        return constraint

    m.constr_ccs2Checs = pe.Constraint(m.existing_producers, rule=rule)


def rule_productionChec(m: pe.ConcreteModel):
    """
    The amount of CHECs produced by a producer is equal to the amount of hydrogen produced
    times the CHEC rate of the producer (CHEC/ton).

    Parameters
    ----------
    m : pe.ConcreteModel
        Pyomo ConcreteModel object


    **Constraint**::

        CHECs produced == hydrogen produced * checs/ton


    For thermal producers:

    .. math ::

        \\chi_p(n)
        =
        h_{p}(n)
        \\cdot
        \\beta(\\phi^n)
        \\quad
        \\forall n_{p_\\text{new, thermal}} \\in N_{p_\\text{new, thermal}}

    The amount of CHECs produced :math:`\\chi_p` at a node :math:`n` as a result of thermal production is
    equal to the amount of hydrogen produced :math:`h_{p}(n)` times the CCS rate :math:`\\beta(\\phi^n)` of the
    thermal producer :math:`\\phi^n` represented by the node.

    .. _electric-chec:

    For electric producers:

    .. math ::

        \\chi_p(n)
        =
        h_{p}(n)
        \\cdot
        \\left (
        1-\\frac{G(\\phi^n)}{B}
        \\right )
        \\quad
        \\forall n_{p_\\text{new, electric}} \\in N_{p_\\text{new, electric}}

    The amount of CHECs produced :math:`\\chi_p` at a node :math:`n` as a result of electric production is
    equal to the amount of hydrogen produced :math:`h_{p}(n)` times the compliment of the ratio of carbon intensity
    of the electricity :math:`G(\\phi^n)` to an established baseline emissions rate :math:`B`.

    Set:
        New producers

    """

    def rule(m, node):
        constraint = m.prod_checs[node] == m.prod_h[node] * m.chec_per_ton[node]
        return constraint

    m.constr_productionChecs = pe.Constraint(m.new_producers, rule=rule)


def rule_consumerChecs(m: pe.ConcreteModel):
    """
    .. _rule_consumerChecs:

    Each carbon-sensitive consumer's consumption of CHECs
    equals its consumption of hydrogen

    Parameters
    ----------
    m : pe.ConcreteModel
        Pyomo ConcreteModel object


    **Constraint**:
        A consumer consumes one CHEC per ton of H2 they consume if they are carbon sensitive.

    ::

        consumer CHECs == consumed hydrogen * binary tracking if consumer is carbon-sensitive


    .. math ::

        \\chi_d(n)
         =
         h_u(n)
         \\cdot
         S_{\\text{CO2}}(\\xi^n)
         \\quad
         \\forall n_{u} \\in N_{u}

    The amount of CHECs consumed :math:`\\chi_d` at a node :math:`n` as a result of consumption is
    equal to the amount of hydrogen consumed :math:`h_{u}(n)` times the carbon sensitivity binary
    :math:`S_{\\text{CO2}}(\\xi^n)` of the demand sector :math:`\\xi^n` represented by the node.

    Set:
        All consumers :math:`n_{u} \\in N_{u}`
    """

    def rule(m, node):
        constraint = m.cons_checs[node] == m.cons_h[node] * m.cons_carbonSensitive[node]
        return constraint

    m.constr_consumerChec = pe.Constraint(m.consumer_set, rule=rule)


def rule_checsBalance(m: pe.ConcreteModel):
    """
    CHECs mass balance

    Parameters
    ----------
    m : pe.ConcreteModel
        Pyomo ConcreteModel object


    **Constraint**:
        The number of CHECs produced :math:`\\chi_p` must be greater than or equal to the number of CHECs consumed :math:`\\chi_u`.

    .. math ::
        \\sum_{n_p}^{N_p}\\chi_p(n_p)
        \\ge
        \\sum_{n_u}^{N_u}\\chi_u(n_u).

    Set:
        All producers :math:`n_{p} \\in N_{p}` and consumers :math:`n_{u} \\in N_{u}`

    Note
    ----
        The sum of CHECs produced is inclusive of all producers, including those that are new and those that
        are existing and retrofitted with CCS.
    """

    def rule(m):
        checs_produced = pe.summation(m.prod_checs)
        checs_produced += pe.summation(m.ccs1_checs)
        checs_produced += pe.summation(m.ccs2_checs)

        checs_consumed = pe.summation(m.cons_checs)

        constraint = checs_consumed <= checs_produced
        return constraint

    m.constr_checsBalance = pe.Constraint(rule=rule)


def apply_CHECs(m: pe.ConcreteModel, H: HydrogenData):
    """
    Apply all CHEC constraints

    Parameters
    ----------
    m : pe.ConcreteModel
        Pyomo ConcreteModel object
    H : HydrogenData
        HydrogenData object

    """

    rule_ccs1Checs(m, H)
    rule_ccs2Checs(m, H)
    rule_productionChec(m)
    rule_consumerChecs(m)
    rule_checsBalance(m)
