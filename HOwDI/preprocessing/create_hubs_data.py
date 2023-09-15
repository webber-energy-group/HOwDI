from pathlib import Path

import pandas as pd

from HOwDI.arg_parse import parse_command_line
from HOwDI.preprocessing.geocode import geocode_hubs
from HOwDI.preprocessing.create_arcs import create_arcs


def create_hubs_data(
    hub_dir,
    out,
    replace_model_inputs,
    model_inputs_dir,
    price_multipliers,
    price_multipliers_column,
    create_fig,
    shapefile,
):
    """
    Creates hub and arc data to be used in the HOwDI model.

    Parameters
    -----------
    hub_dir : str
        The directory containing the hubs.csv, arcs_blacklist.csv, and arcs_whitelist.csv files.
            - `hubs.csv`: lists all the hubs (locations) to be used by the model. Columns include:
                - hub: The name of the hub.
                - status: The "priority" of the hub. 1 means the hub will be more likely to connect to other hubs, -1 means it will be less likely, and 0 means it will be treated as a normal hub.
            - `arcs_blacklist.csv`: lists all the hubs that should not be connected to each other. Columns include:
                - start_hub: The name of the starting hub of the blacklisted arc.
                - end_hub: The name of the ending hub of the blacklisted arc.
            - `arcs_whitelist.csv`: lists all the hubs that should be connected to each other. Columns include:
                - start_hub: The name of the starting hub of the whitelisted arc.
                - end_hub: The name of the ending hub of the whitelisted arc.
                - exist_pipeline: Binary value indicating whether a pipeline already exists between the two hubs.
    out : str
        The directory to output the hub and arc data to. If None, the hub_dir will be used. Output files include:
            - `hubs.geojson`:: A GeoJSON file containing the location of each hub.
            - `arcs.csv`: An input file for the model containing relevant arcs between hubs. Columns include:
                - start_hub: The name of the hub the arc starts at.
                - end_hub: The name of the hub the arc ends at.
                - kmLength_euclid: The Euclidean (straight line) distance between the two hubs.
                - kmLength_road: The distance a truck would have to travel to get from one hub to the other.
                - exist_pipeline: Binary value indicating whether a pipeline already exists between the two hubs.
            - `roads.csv`: A file containing the road geometry between hubs. Used for creating figures. Columns include:
                - start_hub: The name of the hub the road starts at.
                - end_hub: The name of the hub the road ends at.
                - road_geometry: The geometry of the road between the two hubs. A string representing a shapely.geometry.LineString object.
            - `fig.png`: A figure showing the hubs and roads between them. Only saved if create_fig is True.
    replace_model_inputs : bool
        Whether to replace the model's input files with the newly created hub and arc data. Rather than creating a new "hubs.csv" file and manually combining it with the other columns in an existing "hubs.csv" file, this option will replace the existing "hubs.csv" file with the new one and preserve the other columns. This is useful if you want to adjust model hubs, but do not want to worry about the dozen or so other columns that would have to be merged. The "arcs.csv" has no extraneous columns, so it will be replaced by the new file.
    model_inputs_dir : str
        The directory containing the model's input files.
    price_multipliers : str
        The path to the CSV file containing capital price multipliers, natural gas prices, and electricity prices for each county. The methods used for generating this file are found in `data/price_multipliers/original_files`, which uses data from `here <https://github.com/joshdr83/The-Full-Cost-of-Electricity-LCOE-maps>`_. Columns include:
            - County: The name of the county.
            - ng_usd_per_mmbtu: The price of natural gas in USD per MMBtu.
            - e_usd_per_kwh: The price of electricity in USD per kWh.
            - capital_pm: The capital price multiplier for the county
    price_multipliers_column : str
        The name of the column in the price_multipliers CSV file to use for matching hubs. Default is "County"
    create_fig : bool
        Whether to create a figure of the hub and arc data. Stored in out_dir as "fig.png".
    shapefile : str
        The path to the shapefile to use for adding a background to the image generated (if create_fig is True).
        Should end in `.shp` and be in a folder containing other relevant files.
    """

    # get hub dir, where hubs.csv, arcs_blacklist.csv, arcs_whitelist.csv are stored
    hub_dir = Path(hub_dir)

    # get output dir, using hub dir if not specified
    if out == None:
        out_dir = hub_dir
    else:
        out_dir = Path(out)
        out_dir.mkdir(exist_ok=True)

    # get location of hubs specified in hubs.csv
    print("Geocoding...")
    geohubs = geocode_hubs(hub_dir / "hubs.csv")
    geohubs.to_file(out_dir / "hubs.geojson", driver="GeoJSON")

    if replace_model_inputs:
        # finds the model's "hubs.csv" and "arcs.csv" and replaces them with the new ones, preserving the other columns such as
        # wether or not to build a technology, existing tonnesperday, etc.
        if model_inputs_dir is None:
            raise ValueError(
                "The '--replace_model_inputs' setting was chosen, but a directory wasn't specified. Use '-i' to do so."
            )
        else:
            model_hubs_original_path = Path(model_inputs_dir) / "hubs.csv"
            model_hubs_original = pd.read_csv(model_hubs_original_path).set_index("hub")

            # remove/add new hubs; index in the same order as geohubs so counties line up
            model_hubs = model_hubs_original.reindex(geohubs.index)
            if price_multipliers:
                print("Adding price multipliers.")
                pm = pd.read_csv(Path(price_multipliers))

                pm_column = price_multipliers_column  # Only supports "county" atm
                model_hubs[pm_column] = geohubs[pm_column]

                model_hubs = model_hubs.drop(
                    columns=["ng_usd_per_mmbtu", "e_usd_per_kwh", "capital_pm"],
                    errors="ignore",
                )
                model_hubs = (
                    model_hubs.reset_index().merge(pm, on=pm_column).set_index("hub")
                )
                model_hubs = model_hubs.drop(columns=[pm_column])

            model_hubs.to_csv(model_hubs_original_path)

    print("Creating arcs...")
    files = create_arcs(
        geohubs=geohubs,
        hubs_dir=hub_dir,
        create_fig=create_fig,
        shpfile=shapefile,
    )

    files["arcs"].to_csv(out_dir / "arcs.csv")

    if replace_model_inputs:
        files["arcs"].to_csv(Path(model_inputs_dir) / "arcs.csv")

    files["roads"].to_csv(out_dir / "roads.csv")

    if create_fig:
        files["fig"].savefig(out_dir / "fig.png")

    print("Done!")


def main():
    args = parse_command_line("create_hub_data")

    create_hubs_data(
        hub_dir=args.hub_dir,
        out=args.out,  # default is None
        create_fig=args.create_fig,  # default is True
        shapefile=args.shapefile,  # default is None
        price_multipliers=args.price_multipliers,  # default is False
        price_multipliers_column=args.price_multipliers_column,  # default is "County"
        replace_model_inputs=args.replace_model_inputs,  # default is True
        model_inputs_dir=args.model_inputs_dir,  # default is None
    )


if __name__ == "__main__":
    main()
