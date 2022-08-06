# TODO add upload_to_sql method.
# TODO docstrings, but maybe not needed as most functions are a few lines

import uuid

from inspect import getsourcefile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


class HydrogenData:
    """
    A class used primarily to store data in one central location

    Parameters
    -----
    read_type : str
        Either "csv" or "dataframe", determines whether or not to read from
        csvs in a prescribed directory or to read inputs from a dictionary of dataframes.
    scenario_dir : str, Path
        Inputs and outputs dir are relative to this dir
    inputs_dir : str, Path
    outputs_dir : str, Path
    store_outputs : Boolean
        If true, saves outputs to file
    raiseFileNotFoundError : Boolean
        Raise error if an expected file does not exist.
        Set to false only when using this class for pre and postprocessing
    read_output_dir : Boolean
        If set to True, will load data from the outputs dir. Useful if the model has already
        been run and postprocessing with this class is desired

    """

    def __init__(
        self,
        uuid=uuid.uuid4(),
        read_type="csv",
        settings=None,
        # if read_type == "csv"
        scenario_dir=".",
        inputs_dir="inputs",
        outputs_dir="outputs",
        store_outputs=True,
        raiseFileNotFoundError=True,
        read_output_dir=False,
        # if read_type == "dataframe"
        dfs=None,
        upload_to_sql=False,
        sql_database=None,
    ):
        """
        carbon_price_dollars_per_ton: dollars per ton penalty on CO2 emissions
        investment_interest: interest rate for financing capital investments
        investment_period: number of years over which capital is financed
        time_slices: used to get from investment_period units to the simulation
            timestep units. Default is 365 because the investment period units are in
            years (20 years default) and the simulation units are in days.
        """
        self.uuid = uuid
        self.raiseFileNotFoundError_bool = raiseFileNotFoundError

        if read_type == "csv":
            self.init_from_csvs(
                scenario_dir,
                inputs_dir,
                outputs_dir,
                store_outputs,
                raiseFileNotFoundError,
                read_output_dir,
            )
        elif read_type == "dataframe" or read_type == "DataFrame" or read_type == "df":
            self.init_from_dfs(dfs)

        settings = self.get_settings(settings)
        self.get_other_data(settings)

        if read_output_dir:
            self.create_outputs_dfs()

    def init_from_csvs(
        self,
        scenario_dir,
        inputs_dir,
        outputs_dir,
        store_outputs,
        raiseFileNotFoundError,
        read_output_dir,
    ):

        self.scenario_dir = Path(scenario_dir)
        self.inputs_dir = self.scenario_dir / inputs_dir
        self.make_output_dir(outputs_dir, store_outputs)

        ## File
        self.prod_therm = self.read_file("production_thermal")
        self.prod_elec = self.read_file("production_electric")
        # self.storage = self.read_file("storage")
        self.distributors = self.read_file("distribution")
        self.converters = self.read_file("conversion")
        self.demand = self.read_file("demand")
        self.hubs = self.read_file("hubs")
        self.arcs = self.read_file("arcs")
        self.producers_existing = self.read_file("production_existing")

        ## (Retrofitted) CCS data
        # in the future change to nested dictionaries please!
        ccs_data = self.read_file("ccs")
        self.initialize_ccs(ccs_data)

    def init_from_dfs(self, dfs):
        self.prod_therm = dfs.get("production_thermal")
        self.prod_elec = dfs.get("production_electric")
        # self.storage = dfs.get("storage")
        self.distributors = dfs.get("distribution")
        self.converters = dfs.get("conversion")
        self.demand = dfs.get("demand")
        self.hubs = dfs.get("hubs")
        self.arcs = dfs.get("arcs")
        self.producers_existing = dfs.get("production_existing")
        self.initialize_ccs(dfs.get("ccs"))

    def raiseFileNotFoundError(self, fn):
        """Raises FileNotFoundError if self.raiseFileNotFoundError_bool is True,
        WIP: Else, print FNF to logger."""
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

    def write_output_dict(self):
        from json import dump

        with (self.outputs_dir / "outputs.json").open("w", encoding="utf-8") as f:
            dump(self.output_dict, f, ensure_ascii=False, indent=4)

    def create_output_dfs(self):
        self.output_dfs = {
            x: pd.read_csv(self.outputs_dir / (x + ".csv"), index_col=0).fillna(0)
            for x in ["production", "conversion", "consumption", "distribution"]
        }

    def find_data_mapping_setting(self, settings, setting_name, data_mapping=None):
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

    def read_yaml(self, fn, force_no_error=False):
        try:
            with open(fn) as file:
                return yaml.load(file, Loader=yaml.FullLoader)
        except FileNotFoundError:
            if not force_no_error:
                self.raiseFileNotFoundError(fn)

    def make_output_dir(self, outputs_dir, store_outputs):
        self.outputs_dir = self.scenario_dir / outputs_dir

        # If outputs are to be stored to file, make the dir if it DNE
        if store_outputs:
            self.outputs_dir.mkdir(exist_ok=True)

    def find_data_dir(self):
        return Path(getsourcefile(lambda: 0)).absolute().parent.parent.parent / "data"

    def get_settings(self, settings=None):
        if settings is None:
            settings = self.inputs_dir / "settings.yml"
        if isinstance(settings, Path):
            settings = self.read_yaml(settings)

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
        self.baseSMR_CO2_per_H2_tons = settings.get(
            "baseSMR_CO2_per_H2_tons"
        )  # Carbon rate that produces 0 CHECs
        self.carbon_g_MJ_to_t_tH2 = (
            120000.0 / 1000000.0
        )  # unit conversion 120,000 MJ/tonH2, 1,000,000 g/tonCO2

        ## Investment Settings
        self.time_slices = settings.get("time_slices")
        investment_interest = settings.get("investment_interest")
        investment_period = settings.get("investment_period")
        self.A = (((1 + investment_interest) ** investment_period) - 1) / (
            investment_interest * (1 + investment_interest) ** investment_period
        )  # yearly amortized payment = capital cost / A

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

        return settings

    def initialize_ccs(self, ccs_data):
        ccs_data.set_index("type", inplace=True)

        self.ccs1_percent_co2_captured = ccs_data.loc["ccs1", "percent_CO2_captured"]
        self.ccs2_percent_co2_captured = ccs_data.loc["ccs2", "percent_CO2_captured"]
        self.ccs1_h2_tax_credit = ccs_data.loc["ccs1", "h2_tax_credit"]
        self.ccs2_h2_tax_credit = ccs_data.loc["ccs2", "h2_tax_credit"]
        self.ccs1_variable_usdPerTon = ccs_data.loc["ccs1", "variable_usdPerTonCO2"]
        self.ccs2_variable_usdPerTon = ccs_data.loc["ccs2", "variable_usdPerTonCO2"]

    def get_other_data(self, settings):
        self.data_dir = self.find_data_dir()
        data_mapping = self.read_yaml(
            self.data_dir / "data_mapping.yml", force_no_error=True
        )
        self.hubs_dir = self.find_data_mapping_setting(
            setting_name="hubs_dir", data_mapping=data_mapping, settings=settings
        )

        self.shpfile = (
            self.data_dir / "US_COUNTY_SHPFILE" / "US_county_cont.shp"
        )  # TODO make generic

        # initialize
        self.output_dfs = None
        self.output_dict = None

    def all_dfs(self):
        return {
            "input-thermal_production": self.prod_therm,
            "input-electric_production": self.prod_elec,
            "input-distribution": self.distributors,
            "input-conversion": self.converters,
            "input-demand": self.demand,
            "input-hubs": self.hubs,
            "input-arcs": self.arcs,
            "input-existing_production": self.producers_existing,
            "output-production": self.output_dfs["production"],
            "output-consumption": self.output_dfs["consumption"],
            "output-conversion": self.output_dfs["conversion"],
            "output-distribution": self.output_dfs["distribution"],
        }

    def add_uuid_to_all_dfs(self):
        all_dfs = self.all_dfs()
        for _, table in all_dfs.items():
            table["uuid"] = str(self.uuid)

        return self.uuid

    def upload_to_sql(self, engine):
        instance_uuid = self.add_uuid_to_all_dfs()

        for table_name, table in self.all_dfs().items():
            table.to_sql(table_name, con=engine, if_exists="append")

        return instance_uuid
