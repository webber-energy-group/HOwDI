from json import load, dump
from data.generate_inputs_json import main as generate_inputs_json
from hydrogen_model.hydrogen_model import build_h2_model
from data.generate_outputs import main as generate_outputs
from data.create_plot import main as create_plot

def main(scenario='base', read_inputs_from_file=False):
    
    scenario = 'base'
    path = 'data/{}/'.format(scenario)

    if read_inputs_from_file == False:
        inputs = generate_inputs_json(inputs_dir=path+'inputs/',filename='inputs.json')
        # will create file to save inputs
    else:
        inputs = load(open('{}{}'.format(path+'inputs/','inputs.json')))

    input_parameters = load(open('{}{}'.format(path+'inputs/','parameters.json')))

    nodes_list = [node_data['node'] for node_data in inputs['texas_nodes']]

    m = build_h2_model(inputs, input_parameters)
    
    output_dfs, output_json = generate_outputs(m, nodes_list)
    output_path = path + 'outputs/'
    [df.to_csv(output_path + key + '.csv') for key, df in output_dfs.items()]
    with open(output_path + 'outputs.json', 'w', encoding='utf-8') as f:
        dump(output_json, f, ensure_ascii=False, indent=4)

    create_plot(output_json, path)
    
if __name__ == '__main__':
    main()
    
