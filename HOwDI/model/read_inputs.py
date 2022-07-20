# TODO add upload_to_sql method.

from inspect import getsourcefile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


class HydrogenData:
    """
    stores all of the input files needed to run the hydrogen model
    stores some hard coded variables used for the hydrogen model
    """

    def __init__(
        self, scenario_dir: Path, store_outputs=True, raiseFileNotFoundError=True
    ):
        """
        carbon_price_dollars_per_ton: dollars per ton penalty on CO2 emissions
        investment_interest: interest rate for financing capital investments
        investment_period: number of years over which capital is financed
        time_slices: used to get from investment_period units to the simulation
            timestep units. Default is 365 because the investment period units are in
            years (20 years default) and the simulation units are in days.
        """
        self.raiseFileNotFoundError_bool = raiseFileNotFoundError

        self.scenario_dir = scenario_dir
        self.inputs_dir = scenario_dir / "inputs"
        self.outputs_dir = scenario_dir / "outputs"

        if store_outputs:
            # if being used in a model run, make outputs dir if DNE
            self.outputs_dir.mkdir(exist_ok=True)

        # read yaml settings file
        try:
            with open(self.inputs_dir / "settings.yml") as file:
                settings = yaml.load(file, Loader=yaml.FullLoader)
        except FileNotFoundError:
            self.raiseFileNotFoundError(self.inputs_dir / "settings.yml")

        self.data_dir = (
            Path(getsourcefile(lambda: 0)).absolute().parent.parent.parent / "data"
        )

        try:
            with open(self.data_dir / "data_mapping.yml") as file:
                data_mapping = yaml.load(file, Loader=yaml.FullLoader)
        except KeyError:
            data_mapping = None
            # TODO logger.warning("Data mapping not found")

        def find_data_mapping_setting(setting_name):
            # see if setting_name is in settings
            setting_name_value = settings.get(setting_name)

            if setting_name_value is None:
                # otherwise, get from "data" dir.
                if data_mapping is None:
                    raise  # TODO
                setting_name_value = data_mapping.get(setting_name)

                data_mapping_path = self.data_dir / setting_name_value
            else:
                data_mapping_path = Path(setting_name_value)

            return data_mapping_path

        self.hubs_dir = find_data_mapping_setting("hubs_dir")
        self.shpfile = (
            self.data_dir / "US_COUNTY_SHPFILE" / "US_county_cont.shp"
        )  # TODO make generic

        ## File
        self.prod_therm = self.read_file("production_thermal")
        self.prod_elec = self.read_file("production_electric")
        self.storage = self.read_file("storage")
        self.distributors = self.read_file("distribution")
        self.converters = self.read_file("conversion")
        self.demand = self.read_file("demand")
        self.hubs = self.read_file("hubs")
        self.arcs = self.read_file("arcs")
        self.producers_existing = self.read_file("production_existing")

        ## (Retrofitted) CCS data
        # in the future change to nested dictionaries please!
        ccs_data = self.read_file("ccs")
        ccs_data.set_index("type", inplace=True)
        self.ccs1_percent_co2_captured = ccs_data.loc["ccs1", "percent_CO2_captured"]
        self.ccs2_percent_co2_captured = ccs_data.loc["ccs2", "percent_CO2_captured"]
        self.ccs1_h2_tax_credit = ccs_data.loc["ccs1", "h2_tax_credit"]
        self.ccs2_h2_tax_credit = ccs_data.loc["ccs2", "h2_tax_credit"]
        self.ccs1_variable_usdPerTon = ccs_data.loc["ccs1", "variable_usdPerTonCO2"]
        self.ccs2_variable_usdPerTon = ccs_data.loc["ccs2", "variable_usdPerTonCO2"]

        ## Price tracking settings
        self.price_tracking_array = np.arange(**settings.get("price_tracking_array"))
        self.price_hubs = settings.get("price_hubs")
        self.price_demand = settings.get("price_demand")
        self.find_prices = settings.get("find_prices")

        ## Carbon settings
        self.carbon_price = settings.get("carbon_price_dollars_per_ton")
        self.carbon_capture_credit = settings.get(
            "carbon_capture_credit_dollars_per_ton"
        )
        # Carbon rate the produces 0 CHECs
        self.baseSMR_CO2_per_H2_tons = settings.get("baseSMR_CO2_per_H2_tons")
        # unit conversion 120,000 MJ/tonH2, 1,000,000 g/tonCO2:
        self.carbon_g_MJ_to_t_tH2 = 120000.0 / 1000000.0

        # Investment Settings
        self.time_slices = settings.get("time_slices")
        investment_interest = settings.get("investment_interest")
        investment_period = settings.get("investment_period")
        self.A = (
            # yearly amortized payment = capital cost / A
            (((1 + investment_interest) ** investment_period) - 1)
            / (investment_interest * (1 + investment_interest) ** investment_period)
        )

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

        # other options
        self.fractional_chec = settings.get("fractional_chec", True)

        # initialize
        self.output_dfs = None
        self.output_json = None

    def raiseFileNotFoundError(self, fn):
        if self.raiseFileNotFoundError_bool:
            raise FileNotFoundError("The file {} was not found.".format(fn))
        # TODO
        # else:
        #   logger.warning("The file {} was not found.".format(fn))

    def read_file(self, fn) -> pd.DataFrame:
        """reads file in input directory,
        fn is filename w/o .csv"""
        file_name = self.inputs_dir / "{}.csv".format(fn)
        try:
            return pd.read_csv(file_name)
        except FileNotFoundError:
            self.raiseFileNotFoundError(file_name)

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

    def write_output_dataframes(self):
        [
            df.to_csv(self.outputs_dir / "{}.csv".format(key))
            for key, df in self.output_dfs.items()
        ]

    def write_output_json(self):
        from json import dump

        with (self.outputs_dir / "outputs.json").open("w", encoding="utf-8") as f:
            dump(self.output_json, f, ensure_ascii=False, indent=4)
