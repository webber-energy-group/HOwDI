from pathlib import Path

import pandas as pd

from HOwDI.arg_parse import parse_command_line
from HOwDI.preprocessing.geocode import geocode_hubs
from HOwDI.preprocessing.create_arcs import create_arcs


def main():
    args = parse_command_line("create_hub_data")

    hub_dir = Path(args.hub_dir)
    if args.out == None:
        out_dir = hub_dir
    else:
        out_dir = Path(args.out)
        out_dir.mkdir(exist_ok=True)

    print("Geocoding...")
    geohubs = geocode_hubs(hub_dir / "hubs.csv")
    geohubs.to_file(out_dir / "hubs.geojson", driver="GeoJSON")

    if args.replace_model_inputs:
        if args.model_inputs_dir is None:
            raise ValueError(
                "The '--replace_model_inputs' setting was chosen, but a directory wasn't specified. Use '-i' to do so."
            )
        else:
            model_hubs_original_path = Path(args.model_inputs_dir) / "hubs.csv"
            model_hubs_original = pd.read_csv(model_hubs_original_path).set_index("hub")

            # remove/add new hubs; index in the same order as geohubs so counties line up
            model_hubs = model_hubs_original.reindex(geohubs.index)
            if args.price_multipliers:
                print("Adding price multipliers.")
                pm = pd.read_csv(Path(args.price_multipliers))

                pm_column = args.price_multipliers_column  # Only supports "county" atm
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
        create_fig=args.create_fig,
        shpfile=args.shapefile,
    )

    files["arcs"].to_csv(out_dir / "arcs.csv")

    if args.replace_model_inputs:
        files["arcs"].to_csv(Path(args.model_inputs_dir) / "arcs.csv")

    files["roads"].to_csv(out_dir / "roads.csv")

    if args.create_fig:
        files["fig"].savefig(out_dir / "fig.png")

    print("Done!")


if __name__ == "__main__":
    main()
