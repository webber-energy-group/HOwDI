# TODO docstrings, but maybe not needed as most functions are a few lines

import copy
import json
import uuid
from inspect import getsourcefile
from pathlib import Path

import numpy as np
import pandas as pd
import sqlalchemy as db
import yaml
from HOwDI.util import (
    dict_keys_to_list,
    flatten_dict,
    get_number_of_trials,
    read_config,
    set_index,
)


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
        outputs=None,
        # if read_type == "sql"
        trial_number=None,
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
        self.trial_number = trial_number

        if read_type == "csv":
            self.init_from_csvs(
                scenario_dir, inputs_dir, outputs_dir, store_outputs, settings
            )
        elif read_type == "dataframe" or read_type == "DataFrame" or read_type == "df":
            self.init_from_dfs(dfs, settings)

        elif read_type == "sql":
            self.init_from_sql(sql_database)
        else:
            raise ValueError

        if read_output_dir:
            self.create_outputs_dfs()

        if outputs is not None:
            self.output_dfs = outputs

    def init_files(self, how):
        self.prod_therm = set_index(how("production_thermal"), "type")
        self.prod_elec = set_index(how("production_electric"), "type")
        # self.storage = how("storage")
        self.distributors = set_index(how("distribution"), "distributor")
        self.converters = set_index(how("conversion"), "converter")
        self.demand = set_index(how("demand"), "sector")
        self.hubs = set_index(how("hubs"), "hub")
        self.arcs = set_index(how("arcs"), "startHub")
        self.producers_existing = set_index(how("production_existing"), "type")

        ## (Retrofitted) CCS data
        # in the future change to nested dictionaries please!
        ccs_data = set_index(how("ccs"), "type")
        self.initialize_ccs(ccs_data)

    def create_output_dict(self):
        from HOwDI.postprocessing.generate_outputs import create_output_dict

        self.output_dict = create_output_dict(self)

    def init_outputs(self, how):
        # temp:
        self.initialize_outputs = True

        if self.initialize_outputs:
            self.output_dfs = {
                x: how(x)
                for x in ["production", "consumption", "conversion", "distribution"]
            }

            self.create_output_dict()

    def init_from_csvs(
        self, scenario_dir, inputs_dir, outputs_dir, store_outputs, settings
    ):
        self.scenario_dir = Path(scenario_dir)
        self.inputs_dir = self.scenario_dir / inputs_dir
        self.make_output_dir(outputs_dir, store_outputs)

        self.init_files(how=self.read_file)

        ## settings
        settings = self.get_settings(settings)
        self.get_other_data(settings)

    def init_from_dfs(self, dfs, settings):
        # get_df = lambda key: read_df_from_dict(dfs=dfs, key=key)
        def init_dfs_method(name):
            try:
                return first_column_as_index(dfs[name])
            except KeyError:
                self.raiseFileNotFoundError(name)
                return None

        self.init_files(init_dfs_method)

        ## (Retrofitted) CCS data
        # in the future change to nested dictionaries please!
        # self.initialize_ccs(dfs.get("ccs"))

        # settings
        settings = self.get_settings(settings)
        self.get_other_data(settings)

    def read_sql(self, table_name, engine):
        sql = f"""SELECT * FROM '{table_name}'
                  WHERE uuid = '{self.uuid}'
                  AND trial = {self.trial_number}"""

        df = pd.read_sql(sql=sql, con=engine)
        df = df.drop(columns=["uuid", "trial"])
        df = first_column_as_index(df)

        return df

    def init_from_sql(self, engine):
        if self.trial_number is None:
            return ValueError(
                "Tried to pull data from SQL but a run number was not specified"
            )

        if isinstance(engine, str):
            engine = db.create_engine(engine)

        assert isinstance(engine, db.engine.base.Engine)

        # sql tables names are "input/output-{file_name}"
        read_table = lambda table_name: self.read_sql(
            table_name=table_name,
            engine=engine,
        )
        read_inputs = lambda file_name: read_table("input-" + file_name)
        read_outputs = lambda file_name: read_table("output-" + file_name)

        self.init_files(read_inputs)

        settings_df = read_inputs("settings")
        settings_json_str = settings_df.iloc[0]["settings"]
        settings = json.loads(settings_json_str)

        settings = self.get_settings(settings)
        self.get_other_data(settings)

        self.init_outputs(read_outputs)

    def raiseFileNotFoundError(self, fn):
        """Raises FileNotFoundError if self.raiseFileNotFoundError_bool is True,
        WIP: Else, print FNF to logger."""
        if self.raiseFileNotFoundError_bool:
            raise FileNotFoundError("The file {} was not found.".format(fn))
        else:
            return None
        # TODO
        # else:
        #   logger.warning("The file {} was not found.".format(fn))

    def read_file(self, fn) -> pd.DataFrame:
        """reads file in input directory,
        fn is filename w/o .csv"""

        file_name = self.inputs_dir / "{}.csv".format(fn)
        try:
            return pd.read_csv(file_name, index_col=0)
        except FileNotFoundError:
            self.raiseFileNotFoundError(file_name)

    def get_hubs_list(self) -> list:
        return list(self.hubs.index)

    def get_price_hub_params(self) -> dict:
        return {
            "find_prices": self.find_prices,
            "price_hubs": self.price_hubs,
            "price_demand": self.price_demand,
        }

    def get_prod_types(self) -> dict:
        return {
            "thermal": list(self.prod_therm.index),
            "electric": list(self.prod_elec.index),
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
        if self.price_hubs == "all" and self.hubs is not None:
            self.price_hubs = self.get_hubs_list()
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

        self.fixedcost_percent = settings.get("fixedcost_percent", 0.02)

        return settings

    def initialize_ccs(self, ccs_data):
        if ccs_data is not None:
            self.ccs_data = ccs_data
            self.ccs1_percent_co2_captured = ccs_data.loc[
                "ccs1", "percent_CO2_captured"
            ]
            self.ccs2_percent_co2_captured = ccs_data.loc[
                "ccs2", "percent_CO2_captured"
            ]
            self.ccs1_h2_tax_credit = ccs_data.loc["ccs1", "h2_tax_credit"]
            self.ccs2_h2_tax_credit = ccs_data.loc["ccs2", "h2_tax_credit"]
            self.ccs1_variable_usdPerTon = ccs_data.loc["ccs1", "variable_usdPerTonCO2"]
            self.ccs2_variable_usdPerTon = ccs_data.loc["ccs2", "variable_usdPerTonCO2"]
        else:
            self.ccs_data = self.raiseFileNotFoundError("ccs")

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
            "input-production_thermal": self.prod_therm,
            "input-production_electric": self.prod_elec,
            "input-distribution": self.distributors,
            "input-conversion": self.converters,
            "input-demand": self.demand,
            "input-hubs": self.hubs,
            "input-arcs": self.arcs,
            "input-ccs": self.ccs_data,
            "input-production_existing": self.producers_existing,
            "output-production": self.output_dfs["production"],
            "output-consumption": self.output_dfs["consumption"],
            "output-conversion": self.output_dfs["conversion"],
            "output-distribution": self.output_dfs["distribution"],
        }

    def add_value_to_all_dfs(self, **kwargs):
        all_dfs = self.all_dfs()
        for k, v in kwargs.items():
            for table in all_dfs.values():
                table[k] = v

    def add_uuid_to_all_dfs(self):
        self.add_value_to_all_dfs(**{"uuid": self.uuid})

    def upload_to_sql(self, engine):
        def _upload_indiv_table(table, table_name, chunksize=499):
            try:
                table.to_sql(
                    name=table_name,
                    con=engine,
                    if_exists="append",
                    method="multi",
                    chunksize=chunksize,
                )
            except db.exc.OperationalError:
                # if a column is missing in database, update schema
                # NOTE allows for sql injection by changing name of producer
                print("Updating schema of {}".format(table_name))
                import sqlite3

                db2 = sqlite3.connect(engine.url.database)
                cursor = db2.execute(f"""SELECT * from '{table_name}'""")
                columns_in_sql = set(
                    [description[0] for description in cursor.description]
                )

                columns_in_table = set(table.columns)
                new_columns_for_sql = columns_in_table - columns_in_sql

                for c in new_columns_for_sql:
                    db2.execute(f"""ALTER TABLE '{table_name}' ADD COLUMN '{c}'""")
                db2.close()

                table.to_sql(
                    name=table_name,
                    con=engine,
                    if_exists="append",
                    method="multi",
                    chunksize=chunksize,
                )

        [
            _upload_indiv_table(table, table_name)
            for table_name, table in self.all_dfs().items()
        ]

    def output_vector_dict(self):
        vectors = {
            name: create_dataframe_vector(name, df)
            for name, df in self.output_dfs.items()
        }

        return vectors

    def output_vector(self):
        vectors = self.output_vector_dict()
        vectors = list(vectors.values())
        for df in vectors:
            df.index = df.index.map("-".join)

        output_vector = pd.concat(vectors)

        assert len(output_vector) == sum([len(df) for df in vectors])
        return output_vector

    def plot(self):
        from HOwDI.postprocessing.create_plot import create_plot

        if self.output_dict is None:
            self.create_output_dict()
        return create_plot(self)

    def get_prices_dict(self):
        consumption_df = self.output_dfs.get("consumption")
        if consumption_df is None:
            raise ValueError
        ph_dict = {ph: get_prices_at_hub(consumption_df, ph) for ph in self.price_hubs}
        self.prices = ph_dict
        return ph_dict

    def get_trial_info(self):
        prices = self.get_prices_dict()
        prices = flatten_dict(prices)
        prices = pd.DataFrame(prices, index=[self.trial_number])
        prices.index.name = "trial"

        all_dfs = self.all_dfs()

        ### quick and dirty to get consumption
        consumption = all_dfs["output-consumption"]["cons_h"]
        consumption = pd.DataFrame(consumption).T
        consumption.columns = "cons_h/" + consumption.columns
        consumption.index = [self.trial_number]
        consumption.index.name = "trial"

        trial_vector = pd.concat(
            [
                transform_df_to_trial(df, name, self.trial_number)
                for name, df in all_dfs.items()
                if name.startswith("input")
            ]
            + [prices, consumption],
            axis=1,
        )

        return trial_vector


def first_column_as_index(df):
    df = df.reset_index().set_index(df.columns[0])
    df = df.drop(columns="index", errors="ignore")
    return df


def read_df_from_dict(dfs, key):
    df = dfs.get(key)
    return first_column_as_index(df)


def add_name_to_index(df, name):
    df.index = name + "-" + df.index

    return df


def create_dataframe_vector(name, df):
    index = [[name] * len(df), df.index]
    df.set_index([[name] * len(df), df.index], inplace=True)
    if name == "distribution":
        index.append("arc_end")

    df = df.set_index(index)

    return df.stack()


def init_multiple(uuid, engine, data_filter: dict = None):
    """Returns a list of all HydrogenData objects from the database {engine} that have uuid {uuid}"""
    sql = lambda table_name: f"""SELECT * FROM '{table_name}' WHERE uuid = '{uuid}'"""
    read_table = lambda table_name: pd.read_sql(sql=sql(table_name), con=engine)

    if data_filter:
        # remove "settings" from data_filter, if it exists
        data_filter.pop("settings", None)

        input_tables_names = dict_keys_to_list(data_filter)
        input_tables = ["input-" + x for x in input_tables_names]
        tables_map = {
            name_with_prefix: name
            for name, name_with_prefix in zip(input_tables_names, input_tables)
        }

        index_columns = read_config().get("database_index_columns")
        tables2columns_dict = {
            table: index_columns.get(table) for table in input_tables
        }

        sql_statements = [
            "SELECT "
            + ", ".join(
                [index]
                + list(data_filter[tables_map[table_name]].values())[0]
                + ["trial"]
            )
            + f" FROM '{table_name}' WHERE uuid = '{uuid}' AND "
            + "("
            + " OR ".join(
                [
                    f"{index} = '{row}'"
                    for row in data_filter[tables_map[table_name]].keys()
                ]
            )
            + ")"
            for table_name, index in tables2columns_dict.items()
            # for row, columns in data_filter[tables_map[table_name]].items()
        ]

        input_dfs = {
            table: pd.read_sql(sql=sql_statement, con=engine)
            for table, sql_statement in zip(input_tables, sql_statements)
        }
    else:
        input_tables = [
            "input-production_thermal",
            "input-production_electric",
            "input-distribution",
            "input-conversion",
            "input-demand",
            "input-hubs",
            "input-arcs",
            "input-ccs",
            "input-production_existing",
        ]
        input_dfs = {table: read_table(table) for table in input_tables}

    output_tables = [
        "output-production",
        "output-consumption",
        "output-conversion",
        "output-distribution",
    ]

    output_dfs = {table: read_table(table) for table in output_tables}

    settings_table = read_table("input-settings")

    number_of_trials = get_number_of_trials(uuid, engine)

    inputs = [
        {
            table_name.replace("input-", ""): first_column_as_index(
                table[table["trial"] == trial]
            )
            for table_name, table in input_dfs.items()
        }
        for trial in range(number_of_trials)
    ]
    outputs = [
        {
            table_name.replace("output-", ""): first_column_as_index(
                table[table["trial"] == trial]
            )
            for table_name, table in output_dfs.items()
            if table_name.startswith("output-")
        }
        for trial in range(number_of_trials)
    ]
    settings = [
        json.loads(
            settings_table[settings_table["trial"] == trial]["settings"].values[0]
        )
        for trial in range(number_of_trials)
    ]

    raise_fnf = not bool(data_filter)

    h_objs = [
        HydrogenData(
            uuid=uuid,
            read_type="dataframe",
            dfs=input_dfs,
            outputs=output_dfs,
            settings=settings_instance,
            raiseFileNotFoundError=raise_fnf,
            trial_number=trial_number,
        )
        for input_dfs, output_dfs, settings_instance, trial_number in zip(
            inputs, outputs, settings, range(number_of_trials)
        )
    ]

    return h_objs


def get_prices_at_hub(df, hub):
    price_str = f"{hub}_price"
    prices_df = df[df.index.str.startswith(price_str)]
    prices_list = list(prices_df.index.str.replace(price_str, ""))
    price_list_separate = [x.split("_") for x in prices_list]
    price_dict = {sector: amount for sector, amount in price_list_separate}
    return price_dict


def transform_df_to_trial(df, file_name, trial_number):
    if df is None:
        return None

    df = df.drop(columns=["trial"])

    df = pd.concat(
        [
            add_index_to_row(row, index_name, trial_number)
            for index_name, row in df.iterrows()
        ],
        axis=1,
    )

    df.columns = file_name + "/" + df.columns
    return df


def add_index_to_row(row, index, trial_number):
    row = copy.deepcopy(row)
    row.index = index + "/" + row.index
    row = row.to_frame().T
    row.index = [trial_number]
    row.index.name = "trial"
    return row
