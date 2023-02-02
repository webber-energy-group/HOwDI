from HOwDI.arg_parse import parse_command_line
from HOwDI.model.create_model import build_h2_model
from HOwDI.model.create_network import build_hydrogen_network
from HOwDI.model.HydrogenData import HydrogenData
from HOwDI.postprocessing.create_plot import create_plot
from HOwDI.postprocessing.generate_outputs import create_outputs_dfs, create_output_dict


def main():
    args = parse_command_line()
    # read inputs
    H = HydrogenData(
        scenario_dir=args.scenario_dir,
        inputs_dir=args.inputs_dir,
        outputs_dir=args.outputs_dir,
    )
    # generate network
    g = build_hydrogen_network(H)
    # build model
    m = build_h2_model(H, g)

    # clean outputs
    H.output_dfs = create_outputs_dfs(m, H)

    # write outputs dataframes
    if args.output_csvs:
        H.write_output_dataframes()

    # write outputs to json
    if args.output_json:
        H.output_dict = create_output_dict(H)
        H.write_output_dict()

    # create figure
    if args.output_fig:
        if not args.output_json:
            H.output_dict = create_output_dict(H)
        create_plot(H).savefig(
            H.outputs_dir / "fig.png",
            bbox_inches="tight",
            pad_inches=0,
            # facecolor="black",
            transparent=True,
        )


if __name__ == "__main__":
    main()
