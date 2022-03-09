from json import load
from hydrogen_v33fuelstationsubsidy import build_h2_model
from generate_outputs import main as generate_outputs

def main():
    inputs = load(open('inputs/data.json'))
    m = build_h2_model(inputs)
    generate_outputs(m, 'csv')
    
if __name__ == '__main__':
    main()
    
