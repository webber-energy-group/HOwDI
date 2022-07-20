from pathlib import Path

from HOwDI.model.create_model import build_h2_model
from HOwDI.model.create_network import build_hydrogen_network
from HOwDI.model.read_inputs import HydrogenData
from HOwDI.postprocessing.create_plot import main as create_plot
from HOwDI.postprocessing.generate_outputs import generate_outputs


def main():

    scenario_dir = Path("scenarios") / "base"

    # read inputs
    H = HydrogenData(scenario_dir)
    # generate network
    g = build_hydrogen_network(H)
    # build model
    m = build_h2_model(H, g)

    # clean outputs
    H.output_dfs, H.output_json = generate_outputs(m, H)

    # write outputs dataframes
    H.write_output_dataframes()

    # write outputs to json
    H.write_output_json()

    # create figure
    create_plot(H).savefig(H.outputs_dir / "fig.png")


if __name__ == "__main__":
    main()
