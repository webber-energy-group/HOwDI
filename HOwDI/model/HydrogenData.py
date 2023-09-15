# SPDX-License-Identifier: GPL-3.0-or-later
"""
This module defines the `HydrogenData` class, which is used to store and manipulate data for the HOwDI model.
"""

import copy
import json
import uuid
from inspect import getsourcefile
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

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
    A class used primarily to store data in one central location.

    Parameters
    ----------
    uuid : Union[uuid.UUID, str], optional
        A unique identifier for the instance. If not provided, a new UUID4 will be generated.
    read_type : str
        Either "csv" or "dataframe", determines whether or not to read from csvs in a
        prescribed directory or to read inputs from a dictionary of `pd.DataFrame`. Defaults to "csv".
    settings : Dict[str, Any], optional
        A dictionary of settings to use when initializing the instance. If not specified,
        reads from the `settings.yaml` file in the `scenario_dir`.
    scenario_dir : Union[str, Path]
        Inputs and outputs dir are relative to this dir. Defaults to ".".
    inputs_dir : Union[str, Path]
        The directory containing the input data for the model. Defaults to "inputs".
    outputs_dir : Union[str, Path]
        The directory where output data will be written. Defaults to "outputs".
    store_outputs : bool
        If true, saves outputs to file. Defaults to True.
    raiseFileNotFoundError : bool
        Raise error if an expected file does not exist. Set to false only when using this class
        for pre and postprocessing. Defaults to True.
    read_output_dir : bool
        If set to True, will load data from the outputs dir. Useful if the model has already been
        run and postprocessing with this class is desired. Defaults to False.
    dfs : Dict[str, pd.DataFrame], optional
        A dictionary of `pd.DataFrame` to use when initializing the instance. Only used if
        `read_type` is "dataframe". Defaults to None.
    outputs : Dict[str, Any], optional
        A dictionary of output data to use when initializing the instance. Only used if `read_type`
        is "dataframe". Defaults to None.
    trial_number : int, optional
        The trial number to use when initializing the instance. Only used if `read_type` is "sql".
        Defaults to None.
    sql_database : str, optional
        The SQL database to use when initializing the instance. Only used if `read_type` is "sql".
        Defaults to None.
    sql_table : str, optional
        The SQL table to use when initializing the instance. Only used if `read_type` is "sql".
        Defaults to None.

    Attributes
    ----------
    uuid : uuid.UUID
        A unique identifier for the instance.
    raiseFileNotFoundError_bool : bool
        If true, raises error if an expected file does not exist.
    trial_number : int
        The trial number to use when initializing the instance for Monte Carlo runs
    scenario_dir : Path
        Inputs and outputs dir are relative to this dir.
    inputs_dir : Path
        The directory containing the input data for the model, relative to scenario_dir
    outputs_dir : Path
        The directory where output data will be written, relative to scenario_dir
    prod_therm : pd.DataFrame
        A `pd.DataFrame` containing thermal production data, corresponding to the `production_thermal.csv` input file.
    prod_elec : pd.DataFrame
        A `pd.DataFrame` containing electric production data, corresponding to the `production_electric.csv` input file.
    distributors : pd.DataFrame
        A `pd.DataFrame` containing distributor data, corresponding to the `distribution.csv` input file.
    converters : pd.DataFrame
        A `pd.DataFrame` containing converter data, corresponding to the `conversion.csv` input file.
    demand : pd.DataFrame
        A `pd.DataFrame` containing demand data, corresponding to the `demand.csv` input file.
    hubs : pd.DataFrame
        A `pd.DataFrame` containing hub data, corresponding to the `hubs.csv` input file.
    arcs : pd.DataFrame
        A `pd.DataFrame` containing arc data, corresponding to the `arcs.csv` input file.
    producers_existing : pd.DataFrame
        A `pd.DataFrame` containing existing producer data, corresponding to the `producers_existing.csv` input file.
    ccs_data : pd.DataFrame
        A `pd.DataFrame` containing carbon capture and storage data, corresponding to the `ccs.csv` input file.
    ccs1_percent_co2_captured : float
        The percentage of CO2 captured by the first CCS unit. Read from the `ccs.csv` file.
    ccs2_percent_co2_captured : float
        The percentage of CO2 captured by the second CCS unit. Read from the `ccs.csv` file.
    ccs1_h2_tax_credit : float
        The tax credit for hydrogen "cleaned" by CCS1 ($/ton H2). Read from the `ccs.csv` file.
    ccs2_h2_tax_credit : float
        The tax credit for hydrogen "cleaned" by CCS2 ($/ton H2). Read from the `ccs.csv` file.
    ccs1_variable_usdPerTon : float
        The variable cost of CCS1 ($/ton CO2). Read from the `ccs.csv` file.
    ccs2_variable_usdPerTon : float
        The variable cost of CCS2 ($/ton CO2). Read from the `ccs.csv` file.
    price_tracking_array : numpy.ndarray
       Used in the approximation for finding delivered prices at hubs. Has a start, stop, and step
       based on the settings file. Model will test if hydrogen can be delivered at each price.
       More steps will result in a more accurate approximation, but will take longer to run.
    price_hubs : Union[str, List[str]]
        The hubs for which to track prices. Specified in settings.yml. More hubs will result in a
        longer runtime.
    price_demand : float
        The price at "price hubs" pay for a unit of hydrogen. Specified in settings.yml.
        For the "price hubs" option to work, this value must be non-zero. However, the value
        should also be close to zero as to not interfere with the model's results.
    find_prices : bool
        A flag indicating whether to find prices using the price tracking/price hubs feature.
    carbon_price : float
        Dollars per ton penalty on CO2 emissions
    carbon_capture_credit : float
        The credit for carbon capture in dollars per ton.
    baseSMR_CO2_per_H2_tons : float
        The carbon rate that produces 0 CHECs.
    carbon_g_MJ_to_t_tH2 : float
        The unit conversion factor for carbon.
    time_slices : int
        used to get from investment_period units to the simulation
        timestep units. Default is 365 because the investment period units are in
        years (20 years default) and the simulation units are in days.
    A : float
        The yearly amortized payment.
    subsidy_dollar_billion : float
        The amount of billions of dollars available to subsidize infrastructure
        (for scenarios where hydrogen infrastructure is subsidized).
        e.g., if = 0.6, then for a $10Billion facility, industry must spend $6Billion
         (which counts toward the objective function) and the subsidy will cover $4Billion
         (which is excluded from the objective function).
    subsidy_cost_share_fraction : float
        The fraction of dollars that industry must spend on new infrastructure.
    solver_settings : Dict[str, Any]
        A dictionary of solver settings to pass to pyomo. Currently supports:
        - solver: The solver to use. Defaults to "glpk" but "gurobi" is recommended.
        - mipgap: The mipgap to use. Defaults to 0.01.
        - debug: A flag indicating whether to print debug information for the solver. Defaults to False.
    fractional_chec : bool
        A flag indicating whether to use fractional CHECs or whole CHECs.
        Fractional CHEC: 1 CHEC per 1 ton of clean hydrogen produced, 0.5 CHECs if
        the hydrogen produced has 50% of the associated carbon emissions of an unabated SMR.
    fixedcost_percent : float
        The percentage of capital costs used to estimate fixed costs.
    dat_dir : Path
        The directory containing geographic and other base data for the model, independent of the scenario.
    hubs_dir : Path
        The directory containing hub data for the model, independent of the scenario. Within the data_dir
    shpfile_dir : Path
        The shapefile used to create the background map for the model.
    outputs_dfs : Dict[str, pd.DataFrame]
        A dictionary of dataframes containing the outputs from the model. Keys are
        "production", "conversion", "consumption", and "distribution".
    """

    def __init__(
        self,
        uuid: Optional[Union[uuid.UUID, str]] = None,
        read_type: str = "csv",
        settings: Optional[Dict[str, Any]] = None,
        scenario_dir: Union[str, Path] = ".",
        inputs_dir: Union[str, Path] = "inputs",
        outputs_dir: Union[str, Path] = "outputs",
        store_outputs: bool = True,
        raiseFileNotFoundError: bool = True,
        read_output_dir: bool = False,
        dfs: Optional[Dict[str, pd.DataFrame]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        trial_number: Optional[int] = None,
        sql_database: Optional[str] = None,
    ) -> None:
        """
        Initialize a `HydrogenData` instance.
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
            self.create_output_dfs()

        if outputs is not None:
            self.output_dfs = outputs

    def init_files(self, how: Callable[[str], pd.DataFrame]) -> None:
        """
        Initialize the `HydrogenData` instance, reading files or data based on the passed function `how`.

        Parameters
        ----------
        how : Callable[[str], pd.DataFrame]
            A function that takes a filename and returns a pandas DataFrame.

        Returns
        -------
        None
            This method does not return anything.

        Raises
        ------
        FileNotFoundError
            If a required file is not found and `raiseFileNotFoundError` is `True`.
        """
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
        """
        Create a dictionary of output DataFrames for the `HydrogenData` instance.
        """
        from HOwDI.postprocessing.generate_outputs import create_output_dict

        self.output_dict = create_output_dict(self)

    def init_outputs(self, how: Callable[[str], pd.DataFrame]) -> None:
        """
        Initialize the output DataFrames for the `HydrogenData` instance.

        TODO Currently only used for SQL data, and always set to true. Should be refactored

        Parameters
        ----------
        how : Callable[[str], pd.DataFrame]
            A function that takes a string argument (the name of an output DataFrame) and returns a pandas DataFrame.

        Returns
        -------
        None
            This method does not return anything.

        Notes
        -----
        The `self.output_dfs` attribute is a dictionary containing the output DataFrames for the `HydrogenData` instance.
        The keys of the dictionary are the names of the output DataFrames ("production", "consumption", "conversion", and "distribution").
        The values of the dictionary are pandas DataFrames containing the output data.
        """
        # FIXME temp:
        self.initialize_outputs = True

        if self.initialize_outputs:
            self.output_dfs = {
                x: how(x)
                for x in ["production", "consumption", "conversion", "distribution"]
            }

            self.create_output_dict()

    def init_from_csvs(
        self,
        scenario_dir: Union[str, Path],
        inputs_dir: Union[str, Path],
        outputs_dir: Union[str, Path],
        store_outputs: bool,
        settings: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize the `HydrogenData` instance from CSV files.

        Parameters
        ----------
        scenario_dir : Union[str, Path]
            The directory containing the scenario data.
        inputs_dir : Union[str, Path]
            The directory containing the input data for the model.
        outputs_dir : Union[str, Path]
            The directory where output data will be written.
        store_outputs : bool
            If true, saves outputs to file.
        settings : Optional[Dict[str, Any]], optional
            A dictionary of settings to use when initializing the instance (default is None).

        Returns
        -------
        None

        Raises
        ------
        FileNotFoundError
            If a required file is not found and raiseFileNotFoundError is True.
        """
        self.scenario_dir = Path(scenario_dir)
        self.inputs_dir = self.scenario_dir / inputs_dir
        self.make_output_dir(outputs_dir, store_outputs)

        try:
            self.init_files(how=self.read_file)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Could not find required file: {e.filename}"
            ) from e

        ## settings
        settings = self.get_settings(settings)
        self.get_other_data(settings)

    def init_from_dfs(
        self, dfs: Dict[str, pd.DataFrame], settings: Dict[str, Any]
    ) -> None:
        """
        Initialize the `HydrogenData` instance from a dictionary of pandas DataFrames.

        Parameters
        ----------
        dfs : Dict[str, pd.DataFrame]
            A dictionary of pandas DataFrames containing input data. Keys are file names.
        settings : Dict[str, Any]
            A dictionary of settings for the `HydrogenData` instance (see settings.yml in scenario dict).

        Returns
        -------
        None

        Raises
        ------
        FileNotFoundError
            If a required file is not found and `raiseFileNotFoundError` is `True`.
        """

        def init_dfs_method(name: str) -> Optional[pd.DataFrame]:
            """
            Gets a DataFrame from the dictionary of DataFrames `dfs` by name,
            and sets the index to the first column. Used in the `how` argument of `init_files`.
            """
            try:
                return first_column_as_index(dfs[name])
            except KeyError:
                self.raiseFileNotFoundError(name)
                return None

        self.init_files(how=init_dfs_method)

        # settings
        settings = self.get_settings(settings)
        self.get_other_data(settings)

    def read_sql(self, table_name: str, engine: db.engine.base.Engine) -> pd.DataFrame:
        """
        Read data from a SQL table for the `HydrogenData` instance.

        Parameters
        ----------
        table_name : str
            The name of the SQL table to read data from.
        engine : db.engine.base.Engine
            The SQLAlchemy engine to use for connecting to the database.

        Returns
        -------
        pd.DataFrame
            A pandas DataFrame containing the data from the specified SQL table.
        """
        sql = f"""SELECT * FROM '{table_name}'
                  WHERE uuid = '{self.uuid}'
                  AND trial = {self.trial_number}"""

        df = pd.read_sql(sql=sql, con=engine)
        df = df.drop(columns=["uuid", "trial"])
        df = first_column_as_index(df)

        return df

    def init_from_sql(self, engine: Union[str, db.engine.base.Engine]) -> None:
        """
        Initialize the `HydrogenData` instance from data stored in a SQL database.

        Parameters
        ----------
        engine : Union[str, db.engine.base.Engine]
            The SQLAlchemy engine to use for connecting to the database.
        trial_number : Optional[int], optional
            The trial number to use (default is None), by default None.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If a trial number is not specified.
        """
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

        # read inputs from SQL
        self.init_files(how=read_inputs)

        # read settings from SQL, which is stored as a JSON string
        settings_df = read_inputs("settings")
        settings_json_str = settings_df.iloc[0]["settings"]
        settings = json.loads(settings_json_str)

        settings = self.get_settings(settings)
        self.get_other_data(settings)

        self.init_outputs(read_outputs)

    def raiseFileNotFoundError(self, fn: str) -> None:
        """
        Raise a `FileNotFoundError` exception if `self.raiseFileNotFoundError_bool` is True.

        Parameters
        ----------
        fn : str
            The path to the file that was not found.

        Returns
        -------
        None
        """
        # WIP: Else, print FNF to logger
        if self.raiseFileNotFoundError_bool:
            raise FileNotFoundError("The file {} was not found.".format(fn))
        else:
            return None
        # TODO
        # else:
        #   logger.warning("The file {} was not found.".format(fn))

    def read_file(self, fn: str) -> pd.DataFrame:
        """
        Read a CSV file from the input directory. Used as callable for `init_files`.

        Parameters
        ----------
        fn : str
            The name of the file to read, without the ".csv" extension.

        Returns
        -------
        pd.DataFrame
            A pandas DataFrame containing the data from the file.

        Raises
        ------
        FileNotFoundError
            If the specified file does not exist and `raiseFileNotFoundError` is `True`.
        """
        file_name = self.inputs_dir / "{}.csv".format(fn)
        try:
            return pd.read_csv(file_name, index_col=0)
        except FileNotFoundError:
            self.raiseFileNotFoundError(file_name)

    def get_hubs_list(self) -> list:
        """
        Get a list of the hub names in the `HydrogenData` instance.

        Returns
        -------
        List[str]
            A list of the hub names.
        """
        return list(self.hubs.index)

    def get_price_hub_params(self) -> dict:
        """
        Get a dictionary of price hub parameters.

        Returns
        -------
        dict
            A dictionary containing the `find_prices`, `price_hubs`, and `price_demand` parameters.
        """
        return {
            "find_prices": self.find_prices,
            "price_hubs": self.price_hubs,
            "price_demand": self.price_demand,
        }

    def get_prod_types(self) -> dict:
        """
        Get a dictionary of production types.

        Returns
        -------
        dict
            A dictionary containing the `thermal` and `electric` production types.
        """
        return {
            "thermal": list(self.prod_therm.index),
            "electric": list(self.prod_elec.index),
        }

    def write_output_dataframes(self) -> None:
        """Write the output DataFrames to CSV files in the `outputs` directory."""

        [
            df.to_csv(self.outputs_dir / "{}.csv".format(key))
            for key, df in self.output_dfs.items()
        ]

    def write_output_dict(self) -> None:
        """Write the output dictionary to a JSON file in the `outputs` directory."""
        from json import dump

        with (self.outputs_dir / "outputs.json").open("w", encoding="utf-8") as f:
            dump(self.output_dict, f, ensure_ascii=False, indent=4)

    def create_output_dfs(self) -> None:
        """Create pandas DataFrames from CSV files in the `outputs` directory."""
        self.output_dfs = {
            x: pd.read_csv(self.outputs_dir / (x + ".csv"), index_col=0).fillna(0)
            for x in ["production", "conversion", "consumption", "distribution"]
        }

    def find_data_mapping_setting(
        self,
        settings: Dict[str, Any],
        setting_name: str,
        data_mapping: Optional[Dict[str, str]] = None,
    ) -> Path:
        """
        Find the path to a setting. Settings dictionary is searched first,
        then data mapping dictionary, which should be read from data/data_mapping.yml
        (This order is hopefully intuitive since it should allow easier flexibility between
        runs or Monte Carlo trials).

        Parameters
        ----------
        settings : Dict[str, Any]
            A dictionary of settings.
        setting_name : str
            The name of the setting to find.
        data_mapping : Optional[Dict[str, str]], optional
            A dictionary of data mappings (default is None), by default None.

        Returns
        -------
        Path
            The path to the data mapping setting.

        Raises
        ------
        KeyError
            If the specified `setting_name` is not found in the `settings` dictionary and `data_mapping` is not provided.
        """
        # see if setting_name is in settings
        setting_name_value = settings.get(setting_name)

        if setting_name_value is None:
            # otherwise, get from "data" dir.
            if data_mapping is None:
                raise Exception(
                    f"Setting '{setting_name}' not found in settings or data mapping."
                )
            setting_name_value = data_mapping.get(setting_name)

            data_mapping_path = self.data_dir / setting_name_value
        else:
            data_mapping_path = Path(setting_name_value)

        return data_mapping_path

    def read_yaml(
        self, fn: str, force_no_error: bool = False
    ) -> Union[Dict[str, Any], None]:
        """
        Read a YAML file and return its contents as a dictionary.

        Parameters
        ----------
        fn : str
            The path to the YAML file.
        force_no_error : bool, optional
            Whether to suppress the `FileNotFoundError` exception (default is False).

        Returns
        -------
        Union[Dict[str, Any], None]
            A dictionary containing the contents of the YAML file, or None if the file was not found and `force_no_error` is True.

        Raises
        ------
        FileNotFoundError
            If the YAML file is not found and `force_no_error` is False.
        """
        try:
            with open(fn) as file:
                return yaml.load(file, Loader=yaml.FullLoader)
        except FileNotFoundError:
            if not force_no_error:
                self.raiseFileNotFoundError(fn)

    def make_output_dir(self, outputs_dir: Path, store_outputs: bool) -> None:
        """
        Create the output directory for the `HydrogenData` instance.

        Parameters
        ----------
        outputs_dir : Path
            The directory where output data will be written.
        store_outputs : bool
            If true, saves outputs to file.

        Returns
        -------
        None
            This method does not return anything.
        """
        self.outputs_dir = self.scenario_dir / outputs_dir

        # If outputs are to be stored to file, make the dir if it DNE
        if store_outputs:
            self.outputs_dir.mkdir(exist_ok=True)

    def find_data_dir(self) -> Path:
        """
        Find the path to the `data` directory, containing geographic data.

        TODO Refactor in __init__, doesn't need to be a method
        """
        # HydrogenData.py/../../../data
        return Path(getsourcefile(lambda: 0)).absolute().parent.parent.parent / "data"

    def get_settings(
        self, settings: Optional[Union[Path, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Get the settings for the `HydrogenData` instance.

        Parameters
        ----------
        settings : Optional[Union[Path, Dict[str, Any]]]
            The settings for the `HydrogenData` instance, either as a dictionary or a file path.

        Returns
        -------
        Dict[str, Any]
            A dictionary of settings for the `HydrogenData` instance.

        Raises
        ------
        FileNotFoundError
            If the specified settings file is not found and `raiseFileNotFoundError` is `True`.
        """
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
        self.carbon_price = settings.get(
            "carbon_price_dollars_per_ton"
        )  # dollars per ton penalty on CO2 emissions
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
        """
        investment_interest: interest rate for financing capital investments
        investment_period: number of years over which capital is financed
        time_slices: used to get from investment_period units to the simulation
            timestep units. Default is 365 because the investment period units are in
            years (20 years default) and the simulation units are in days.
        """
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

    def initialize_ccs(self, ccs_data: Optional[pd.DataFrame]) -> None:
        """
        Initialize the CCS data for the `HydrogenData` instance.

        Parameters
        ----------
        ccs_data : Optional[pd.DataFrame]
            A pandas DataFrame containing the CCS data.

        Returns
        -------
        None

        Raises
        ------
        FileNotFoundError
            If the CCS data file is not found and `raiseFileNotFoundError` is `True`.

        TODO
        ----
        The way this is currently implemented is limiting and should be refactored.
        """
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

    def get_other_data(self, settings: Dict[str, Any]) -> None:
        """
        Get other data for the `HydrogenData` instance. This includes:

        * The "data" directory, which is relative to this file and contains a yaml file describing the location of the hubs directory within `/data`, the hubs directory, and a shapefile for the geography.

        * The "hubs" directory, which contains the hubs data (hubs.geojson and roads.csv). Only used for generating output images

        * The shapefile, which is the background for generated images

        Parameters
        ----------
        settings : Dict[str, Any]
            A dictionary of settings for the `HydrogenData` instance.

        Returns
        -------
        None
        """
        self.data_dir = self.find_data_dir()
        data_mapping = self.read_yaml(
            self.data_dir / "data_mapping.yml", force_no_error=True
        )
        # TODO this should be optional
        self.hubs_dir = self.find_data_mapping_setting(
            setting_name="hubs_dir", data_mapping=data_mapping, settings=settings
        )

        # TODO make generic (i.e., a passed parameter)
        self.shpfile = self.data_dir / "US_COUNTY_SHPFILE" / "US_county_cont.shp"

        # initialize output attributes so they can be used later
        self.output_dfs = None
        self.output_dict = None

    def all_dfs(self):
        """Return a dictionary of all the dataframes in the `HydrogenData` instance."""
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

    def append_value_to_all_dfs(self, **kwargs):
        """
         Append value to all columns in all DataFrames in the `HydrogenData` instance.

        Parameters
        ----------
        **kwargs : Any
            Keyword arguments representing the values to add to the DataFrames.

        Examples
        --------
        >>> self.append_value_to_all_dfs(**{"a": 1})
        For all tables returned by `self.all_dfs()`, add a column "a" with value 1.
        """
        all_dfs = self.all_dfs()
        for k, v in kwargs.items():
            for table in all_dfs.values():
                table[k] = v

    def add_uuid_to_all_dfs(self):
        """Add uuid to all DataFrames in the `HydrogenData` instance."""
        self.append_value_to_all_dfs(**{"uuid": self.uuid})

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


def first_column_as_index(df: pd.DataFrame) -> pd.DataFrame:
    """Set the first column of a pandas DataFrame as the index."""
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
