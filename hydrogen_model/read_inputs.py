from pathlib import Path

import numpy as np
import pandas as pd
import yaml


class HydrogenInputs:
    """
    stores all of the input files needed to run the hydrogen model
    stores some hard coded variables used for the hydrogen model
    """

    def __init__(self, inputs_dir: Path):
        """
        carbon_price_dollars_per_ton: dollars per ton penalty on CO2 emissions
        investment_interest: interest rate for financing capital investments
        investment_period: number of years over which capital is financed
        time_slices: used to get from investment_period units to the simulation
            timestep units. Default is 365 because the investment period units are in
            years (20 years default) and the simulation units are in days.
        """
        self.inputs_dir = inputs_dir
        # read yaml file
        try:
            with open(inputs_dir / "settings.yml") as file:
                settings = yaml.load(file, Loader=yaml.FullLoader)
        except FileNotFoundError:
            raise FileNotFoundError(
                "The file 'settings.yml' was not found in the inputs directory"
            )

        # generic data
        self.prod_therm = self.read_file("production_thermal")
        self.prod_elec = self.read_file("production_electric")
        self.storage = self.read_file("storage")
        self.distributors = self.read_file("distribution")
        self.converters = self.read_file("conversion")
        self.demand = self.read_file("demand")
        self.ccs_data = self.read_file("ccs")
        self.hubs = self.read_file("hubs")
        self.arcs = self.read_file("arcs")
        self.producers_existing = self.read_file("production_existing")

        # get ccs data
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
        # Scalars
        # TODO maybe clean this up a little bit
        self.time_slices = settings.get("time_slices")
        self.carbon_price = settings.get("carbon_price_dollars_per_ton")
        self.carbon_capture_credit = settings.get(
            "carbon_capture_credit_dollars_per_ton"
        )
        investment_interest = settings.get("investment_interest")
        investment_period = settings.get("investment_period")
        self.A = (
            # yearly amortized payment = capital cost / A
            (((1 + investment_interest) ** investment_period) - 1)
            / (investment_interest * (1 + investment_interest) ** investment_period)
        )
        # unit conversion 120,000 MJ/tonH2, 1,000,000 g/tonCO2:
        self.carbon_g_MJ_to_t_tH2 = 120000.0 / 1000000.0

        self.price_tracking_array = np.arange(**settings.get("price_tracking_array"))
        self.price_hubs = settings.get("price_hubs")
        self.price_demand = settings.get("price_demand")
        self.find_prices = settings.get("find_prices")

        # for the scenario where hydrogen infrastructure is subsidized
        # how many billions of dollars are available to subsidize infrastructure
        self.subsidy_dollar_billion = settings.get("subsidy_dollar_billion")
        # what fraction of dollars must industry spend on new infrastructure--
        #  e.g., if = 0.6, then for a $10Billion facility, industry must spend $6Billion
        #  (which counts toward the objective function) and the subsidy will cover $4Billion
        #  (which is excluded from the objective function).
        self.subsidy_cost_share_fraction = settings.get("subsidy_cost_share_fraction")

        # solver data
        self.solver_settings = settings.get("solver_settings")

    def read_file(self, fn) -> pd.DataFrame:
        """reads file in input directory,
        fn is filename w/o .csv"""
        try:
            return pd.read_csv(self.inputs_dir / "{}.csv".format(fn))
        except FileNotFoundError:
            raise FileNotFoundError(
                "The file '{}.csv' was not found in the inputs directory".format(fn)
            )

    def get_hubs_list(self) -> list:
        return list(self.hubs["hub"])

    def get_price_hub_params(self) -> dict:
        return {
            "find_prices": self.find_prices,
            "price_hubs": self.price_hubs,
            "price_demand": self.price_demand,
        }

    def get_prod_types(self) -> dict:
        return {
            "thermal": list(self.prod_therm["type"]),
            "electric": list(self.prod_elec["type"]),
        }
