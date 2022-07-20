from pathlib import Path

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

    print("Creating arcs...")
    files = create_arcs(
        geohubs=geohubs,
        hubs_dir=hub_dir,
        create_fig=args.create_fig,
        shpfile=args.shapefile,
    )

    files["arcs"].to_csv(out_dir / "arcs.csv")
    files["roads"].to_csv(out_dir / "roads.csv")

    if args.create_fig:
        files["fig"].savefig(out_dir / "fig.png")

    print("Done!")


if __name__ == "__main__":
    main()
