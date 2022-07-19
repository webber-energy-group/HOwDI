from json import dump
from pathlib import Path

from HOwDI.model.create_model import build_h2_model
from HOwDI.model.create_network import build_hydrogen_network
from HOwDI.model.read_inputs import HydrogenInputs
from HOwDI.postprocessing.create_plot import main as create_plot
from HOwDI.postprocessing.generate_outputs import generate_outputs


def main():

    scenario_dir = Path("scenarios") / "base"

    # read inputs
    H = HydrogenInputs(scenario_dir)
    # generate network
    g = build_hydrogen_network(H)
    # build model
    m = build_h2_model(H, g)

    # clean outputs
    output_dfs, output_json = generate_outputs(m, H)

    # write outputs dataframes
    [df.to_csv(H.outputs_dir / "{}.csv".format(key)) for key, df in output_dfs.items()]

    # write outputs to json
    with (H.outputs_dir / "outputs.json").open("w", encoding="utf-8") as f:
        dump(output_json, f, ensure_ascii=False, indent=4)

    # create figure
    create_plot(output_json, H)


if __name__ == "__main__":
    main()
