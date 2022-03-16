from json import load, dump
from hydrogen_model.hydrogen_v33fuelstationsubsidy import build_h2_model
from data.generate_outputs import main as generate_outputs

def main():
    inputs = load(open('data/inputs/data.json'))
    nodes_list = [node_data['node'] for node_data in inputs['texas_nodes']]

    m = build_h2_model(inputs)
    
    output_dfs, output_json = generate_outputs(m, nodes_list)
    output_location = 'data/outputs/'
    [df.to_csv(output_location + key + '.csv') for key, df in output_dfs.items()]
    with open(output_location + 'outputs.json', 'w', encoding='utf-8') as f:
        dump(output_json, f, ensure_ascii=False, indent=4)
    
if __name__ == '__main__':
    main()
    
